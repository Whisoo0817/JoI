"""Certificate for fixed-cardinality, clock-scheduled aggregation.

This is a compiler-style unrolling pass.  A daily JoI accumulator guarded by
an inclusive, fixed Hour interval is expanded into one symbolic input snapshot
per hour.  The Timeline side is independently expanded from its fixed reads
and delays.  Equal schedules and equal expression trees prove equivalence for
every catalog value; unequal trees are only reported as divergence after an
ordinary concrete replay.

The pass is deliberately narrow.  Dynamic bounds, data-dependent counts,
timestamp arithmetic, non-hour schedules and incomplete resets fall through
to the existing fail-closed engines.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import time

from explorer.runtime import expr as e, joi_parser as jp
from explorer.runtime.expr import canonical_key
from explorer.runtime.interp import Unsupported
from explorer.runtime.ir_step import IrRunner
from explorer.runtime.pause import PauseRunner
from explorer.verification.product import Divergence, ProductResult, replay_divergence


METHOD = "fixed-aggregation-unroll-v1"
MAX_SAMPLES = 32


@dataclass(frozen=True)
class Plan:
    sample_hours: tuple[int, ...]
    report_hour: int
    action: tuple
    args: tuple
    input_keys: tuple[str, ...]


def _unwrap(runner):
    while hasattr(runner, "inner"):
        runner = runner.inner
    return runner


def _lit(value):
    return ("lit", value)


def _number(value):
    return type(value) in (int, float) and not isinstance(value, bool)


def _calc(op, left, right):
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left / right if right else 0
    raise Unsupported("fixed aggregation arithmetic: " + op)


def _bin(op, left, right):
    """Fold constants but retain floating-point evaluation order."""
    if left[0] == right[0] == "lit" and _number(left[1]) and _number(right[1]):
        return _lit(_calc(op, left[1], right[1]))
    # Accumulators start at numeric zero.  Removing that first addition is
    # observation-equivalent for the supported numeric ACTION equality,
    # including signed zero (which compares equal in the runtime contract).
    if op == "+" and left == _lit(0):
        return right
    return ("bin", op, left, right)


def _const(node):
    if isinstance(node, e.Lit):
        return node.value
    if isinstance(node, e.UnaryOp) and node.op == "-":
        value = _const(node.operand)
        return -value if _number(value) else None
    return None


def _and_atoms(node):
    if isinstance(node, e.BinaryOp) and node.op == "and":
        return _and_atoms(node.left) + _and_atoms(node.right)
    return [node]


def _cmp(atom, op, left_name, right_name=None):
    if not isinstance(atom, e.BinaryOp) or atom.op != op:
        return None
    if not isinstance(atom.left, e.VarRef) or atom.left.name != left_name:
        return None
    if right_name is not None:
        return True if isinstance(atom.right, e.VarRef) and atom.right.name == right_name else None
    value = _const(atom.right)
    return value if type(value) is int else None


def _jexpr(node, env, sample_index):
    if isinstance(node, e.Lit):
        return _lit(node.value)
    if isinstance(node, e.VarRef):
        if node.name not in env:
            raise Unsupported("fixed aggregation unresolved variable: " + node.name)
        return env[node.name]
    if isinstance(node, e.DeviceRef):
        return ("input", node.key, sample_index)
    if isinstance(node, e.UnaryOp) and node.op == "-":
        return _bin("-", _lit(0), _jexpr(node.operand, env, sample_index))
    if isinstance(node, e.BinaryOp) and node.op in ("+", "-", "*", "/"):
        return _bin(node.op, _jexpr(node.left, env, sample_index),
                    _jexpr(node.right, env, sample_index))
    raise Unsupported("fixed aggregation JoI expression: " + type(node).__name__)


def _irexpr(node, env):
    tag = node[0]
    if tag == "expr":
        return _irexpr(node[1], env)
    if tag == "lit":
        return _lit(node[1])
    if tag == "var":
        if node[1] not in env:
            raise Unsupported("fixed aggregation unresolved IR variable: " + node[1])
        return env[node[1]]
    if tag == "bin" and node[1] in ("+", "-", "*", "/"):
        return _bin(node[1], _irexpr(node[2], env), _irexpr(node[3], env))
    raise Unsupported("fixed aggregation IR expression: " + str(tag))


def _ir_hour_cmp(node, op):
    if not (isinstance(node, tuple) and len(node) == 4
            and node[:2] == ("bin", op)):
        return None
    left, right = node[2], node[3]
    if left[:2] == ("read", "clock.hour") and right[0] == "lit" \
            and type(right[1]) is int:
        return right[1]
    return None


def _ir_plan(runner) -> Plan:
    ir = _unwrap(runner)
    if type(ir) is not IrRunner:
        raise Unsupported("fixed aggregation needs an IrRunner")
    ins = ir.prog.ins
    if len(ins) < 9 or ins[0].kind != "ENTER_CYCLE" or ins[1].kind != "TOP" \
            or ins[1].period != 0 or ins[1].count or ins[-2].kind != "END_ITER" \
            or ins[-1].kind != "END":
        raise Unsupported("fixed aggregation IR outer cycle")
    start = _ir_hour_cmp(ins[2].cond, "==") if ins[2].kind == "WAIT" else None
    first_wait = ins[2]
    if start is None or first_wait.edge != "none" or first_wait.for_sec \
            or first_wait.to_sec:
        raise Unsupported("fixed aggregation IR needs a fixed Hour start")

    env, keys, sample = {}, [], 0
    pc = 3
    while pc < len(ins) and ins[pc].kind == "READ":
        # The first read group is handled by the shared loop below.
        group = []
        while pc < len(ins) and ins[pc].kind == "READ":
            group.append(ins[pc]); pc += 1
        if not group or pc >= len(ins) or ins[pc].kind != "DELAY" \
                or ins[pc].for_sec != Fraction(3600, 1):
            raise Unsupported("fixed aggregation IR needs hourly read groups")
        for read in group:
            env[read.var] = ("input", read.key, sample)
            keys.append(read.key)
        sample += 1
        pc += 1
        if sample > MAX_SAMPLES:
            raise Unsupported("fixed aggregation sample cap")
        if pc >= len(ins) or ins[pc].kind != "READ":
            break
    if sample == 0 or pc >= len(ins) or ins[pc].kind != "CALL":
        raise Unsupported("fixed aggregation IR needs one final ACTION")
    call = ins[pc]
    if call.var:
        raise Unsupported("fixed aggregation result-returning call")
    args = tuple(_irexpr(arg, env) for arg in call.args)
    pc += 1
    report = (start + sample) % 24
    final_wait = ins[pc] if pc < len(ins) else None
    if start + sample >= 24 or final_wait is None or final_wait.kind != "WAIT" \
            or final_wait.edge != "none" or final_wait.for_sec or final_wait.to_sec \
            or _ir_hour_cmp(final_wait.cond, "!=") != report or pc != len(ins) - 3:
        raise Unsupported("fixed aggregation IR report/reset boundary")
    action = (call.svc, call.method, tuple(call.tags))
    return Plan(tuple(range(start, start + sample)), report, action, args,
                tuple(sorted(set(keys))))


def _joi_plan(runner) -> Plan:
    code = _unwrap(runner)
    if type(code) is not PauseRunner or not code.repeat or not code.period_ms:
        raise Unsupported("fixed aggregation needs a periodic PauseRunner")
    stmts = code.stmts
    initial, rest, env = {}, [], {}
    for stmt in stmts:
        if isinstance(stmt, jp.Assign) and stmt.op == ":=" and not rest:
            value = _const(stmt.rhs)
            if not _number(value):
                raise Unsupported("fixed aggregation initializer")
            initial[stmt.name] = env[stmt.name] = _lit(value)
        else:
            rest.append(stmt)
    if len(rest) != 3 or not isinstance(rest[0], jp.Assign) \
            or rest[0].op != "=" or not isinstance(rest[0].rhs, e.QuantRef) \
            or rest[0].rhs.key != "clock.hour" \
            or not isinstance(rest[1], jp.IfStmt) or not isinstance(rest[2], jp.IfStmt):
        raise Unsupported("fixed aggregation JoI statement shape")
    hour_name = rest[0].name
    sample_if, report_if = rest[1], rest[2]

    lo = hi = last_name = None
    for atom in _and_atoms(sample_if.cond):
        value = _cmp(atom, ">=", hour_name)
        if value is not None:
            lo = value; continue
        value = _cmp(atom, "<=", hour_name)
        if value is not None:
            hi = value; continue
        if isinstance(atom, e.BinaryOp) and atom.op == "!=" \
                and isinstance(atom.left, e.VarRef) and atom.left.name == hour_name \
                and isinstance(atom.right, e.VarRef):
            last_name = atom.right.name; continue
        raise Unsupported("fixed aggregation sample guard")
    if lo is None or hi is None or last_name not in initial or not 0 <= lo <= hi < 24 \
            or hi - lo + 1 > MAX_SAMPLES:
        raise Unsupported("fixed aggregation fixed Hour interval")
    if initial[last_name][1] in range(lo, hi + 1) or sample_if.else_body \
            or report_if.else_body:
        raise Unsupported("fixed aggregation guard/reset side path")

    report = count_name = None
    for atom in _and_atoms(report_if.cond):
        value = _cmp(atom, "==", hour_name)
        if value is not None:
            report = value; continue
        if isinstance(atom, e.BinaryOp) and atom.op == ">" \
                and isinstance(atom.left, e.VarRef) and _const(atom.right) == 0:
            count_name = atom.left.name; continue
        raise Unsupported("fixed aggregation report guard")
    if report is None or count_name not in initial or not report_if.then_body \
            or not isinstance(report_if.then_body[0], jp.CallStmt):
        raise Unsupported("fixed aggregation report shape")

    sample_hours = tuple(range(lo, hi + 1))
    keys = set()
    for index, hour in enumerate(sample_hours):
        env[hour_name] = _lit(hour)
        before_count = env[count_name]
        for stmt in sample_if.then_body:
            if not isinstance(stmt, jp.Assign) or stmt.op != "=":
                raise Unsupported("fixed aggregation sample body")
            env[stmt.name] = _jexpr(stmt.rhs, env, index)
            if isinstance(env[stmt.name], tuple) and env[stmt.name][0] == "input":
                keys.add(env[stmt.name][1])
            # Also collect reads nested under an accumulator addition.
            def collect(term):
                if term[0] == "input": keys.add(term[1])
                elif term[0] == "bin": collect(term[2]); collect(term[3])
            collect(env[stmt.name])
        if env.get(last_name) != _lit(hour):
            raise Unsupported("fixed aggregation last-hour update")
        expected_count = _bin("+", before_count, _lit(1))
        if env.get(count_name) != expected_count:
            raise Unsupported("fixed aggregation count update")

    call = report_if.then_body[0].call
    if call.quant is not None or call.fanout is not None or not call.tags:
        raise Unsupported("fixed aggregation needs one grounded ACTION")
    args = tuple(_jexpr(arg, env, len(sample_hours)) for arg in (call.args or ()))
    def collect_arg(term):
        if term[0] == "input": keys.add(term[1])
        elif term[0] == "bin": collect_arg(term[2]); collect_arg(term[3])
    for arg in args:
        collect_arg(arg)
    resets = report_if.then_body[1:]
    reset_names = set()
    for stmt in resets:
        if not isinstance(stmt, jp.Assign) or stmt.op != "=" or stmt.name not in initial \
                or _jexpr(stmt.rhs, env, len(sample_hours)) != initial[stmt.name]:
            raise Unsupported("fixed aggregation reset")
        reset_names.add(stmt.name)
    carried = set(initial) - {last_name}
    if reset_names != carried:
        raise Unsupported("fixed aggregation must reset every accumulator")
    if report <= hi or report >= 24:
        raise Unsupported("fixed aggregation report must follow samples in the same day")
    svc, method = canonical_key(call.service, call.method)
    return Plan(sample_hours, report, (svc, method, tuple(call.tags)), args,
                tuple(sorted(keys)))


def _world(plan_a, plan_b, sample_index):
    keys = sorted(set(plan_a.input_keys) | set(plan_b.input_keys))
    out = {}
    for n, key in enumerate(keys):
        # Different streams and different hours expose swapped/omitted/last
        # sample mutants while staying valid finite DOUBLE values.
        out[key] = float(1 + 10 * n + sample_index)
    return out


def _candidate_witness(runner_a, runner_b, a, b, t0_ms):
    last_hour = max(max(a.sample_hours), max(b.sample_hours), a.report_hour, b.report_hour)
    start_day = t0_ms // 86_400_000
    start = min(min(a.sample_hours), min(b.sample_hours))
    events = [(_world(a, b, 0), 0)]
    now = t0_ms
    for hour in range(start, last_hour + 1):
        target = start_day * 86_400_000 + hour * 3_600_000
        if target < now:
            continue
        index = max(0, hour - start)
        events.append((_world(a, b, index), target - now))
        now = target
    div = Divergence(len(events) - 1, events[-1][0], events[-1][1], (), (),
                     events[:-1], {}, t0_ms, 1000)
    try:
        return div if replay_divergence(runner_a, runner_b, div).confirmed else None
    except (Unsupported, ValueError, TypeError, ArithmeticError):
        return None


def fixed_aggregation_product(runner_a, runner_b, *, t0_ms,
                              horizon_ms=None, initial_gv_domains=None):
    """Return a certified result, or None when the pair is outside the pass."""
    if horizon_ms is not None or initial_gv_domains:
        return None
    try:
        a, b = _ir_plan(runner_a), _joi_plan(runner_b)
        model_a = getattr(runner_a, "catalog_model", None)
        model_b = getattr(runner_b, "catalog_model", None)
        if model_a is None or model_a is not model_b:
            raise Unsupported("fixed aggregation needs one catalog snapshot")
        for key in set(a.input_keys) | set(b.input_keys):
            spec = model_a.input_spec(key)
            if spec is None or spec.get("type") not in ("INTEGER", "DOUBLE") \
                    or spec.get("members") is not None:
                raise Unsupported("fixed aggregation numeric input: " + key)
        # The first daily sample must still be in the future.  This makes the
        # base state common; the report reset then supplies the daily induction.
        day_ms = t0_ms % 86_400_000
        code = _unwrap(runner_b)
        if day_ms >= min(a.sample_hours[0], b.sample_hours[0]) * 3_600_000 \
                or t0_ms % code.period_ms or 3_600_000 % code.period_ms:
            raise Unsupported("fixed aggregation requires a second-aligned pre-sample start")
    except Unsupported:
        return None

    started = time.perf_counter()
    same = (a.sample_hours, a.report_hour, a.action, a.args) == \
           (b.sample_hours, b.report_hour, b.action, b.args)
    result = ProductResult("EQUIV" if same else "UNKNOWN", n_states=len(a.sample_hours) + 2,
                           n_steps=0, closed=same)
    result.symbolic_certificate = {
        "schema": METHOD,
        "scope": "fixed inclusive Hour interval; one sample per hour; complete post-report reset",
        "basis": "compiler unroll to distinct symbolic input snapshots; exact expression-tree comparison",
        "ir_plan": asdict(a),
        "joi_plan": asdict(b),
        "daily_induction": "common pre-sample base; report reset; last_hour differs from next day's first hour",
    }
    result.notes.append(METHOD + ": fixed daily accumulator expanded into symbolic snapshots")
    if not same:
        div = _candidate_witness(runner_a, runner_b, a, b, t0_ms)
        if div is not None:
            result.verdict, result.closed = "DIVERGE", True
            result.divergences.append(div)
            result.notes.append("unrolled mismatch confirmed by ordinary concrete replay")
        else:
            result.notes.append("unrolled summaries differ but no concrete replay was found")
    result.seconds = time.perf_counter() - started
    return result
