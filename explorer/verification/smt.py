"""Path-sensitive SMT fallback for catalog numeric linear programs.

Re-executes the existing pure runners when a symbolic Boolean forks. A queue
contains BOTH feasible successors, carrying all path constraints and captured
input epochs. No representative numeric valuation is used to certify EQUIV.
"""
from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import math
import time

from explorer.runtime import expr as e, joi_parser as jp
from explorer.verification.input_coverage import merged_coverage
from explorer.runtime.interp import Unsupported
from explorer.runtime.ir_step import IrRunner
from explorer.runtime.oneshot import OneShotRunner
from explorer.verification.product import ProductResult, Divergence, replay_divergence
from explorer.runtime.runner import TerminalRunner

METHOD = 'smt-linear-trace-v1'


def smt_specs(runner_a, runner_b):
    """Narrow replacement for arithmetic D7 refusals, never a global bypass."""
    from explorer.verification.timed import unwrap, reads_clock
    from explorer.analysis.features import analyze_runner
    a, b = unwrap(runner_a), unwrap(runner_b)
    model = getattr(runner_a, 'catalog_model', None)
    if model is None or model is not getattr(runner_b, 'catalog_model', None):
        return None
    if not isinstance(a, IrRunner) or not isinstance(b, OneShotRunner):
        return None
    if reads_clock(runner_a) or reads_clock(runner_b):
        return None
    features = analyze_runner(runner_a) + analyze_runner(runner_b)
    allowed = {'joint-guard', 'derived-guard', 'arith-arg'}
    if not features or any(f.kind not in allowed for f in features):
        return None
    coverage = merged_coverage(runner_a.axes.coverage, runner_b.axes.coverage)
    if coverage.errors or coverage.writes or runner_a.axes.param_reads or runner_b.axes.param_reads:
        return None
    if any(k.startswith(('@gv:', 'clock.')) for k in coverage.predicates):
        return None

    def code_expr(x):
        if isinstance(x, (e.Lit, e.VarRef, e.DeviceRef)):
            return True
        if isinstance(x, jp.CallExpr):
            return x.args is None or all(isinstance(y, e.Lit) for y in x.args)
        if isinstance(x, e.UnaryOp):
            return x.op in ('-', 'not') and code_expr(x.operand)
        if isinstance(x, e.FuncCall):
            return x.name == 'abs' and len(x.args) == 1 and code_expr(x.args[0])
        return isinstance(x, e.BinaryOp) and x.op in ('+', '-', '*', '/', '==', '!=', '<', '<=', '>', '>=', 'and', 'or') and code_expr(x.left) and code_expr(x.right)

    def statements(stmts):
        for stmt in stmts:
            if isinstance(stmt, jp.IfStmt):
                if not code_expr(stmt.cond) or not statements(stmt.then_body) or not statements(stmt.else_body): return False
            elif isinstance(stmt, jp.Assign):
                if not code_expr(stmt.rhs): return False
            elif isinstance(stmt, jp.CallStmt):
                if not all(code_expr(arg) for arg in stmt.call.args or ()): return False
            elif isinstance(stmt, jp.WaitUntil):
                if not code_expr(stmt.cond): return False
            elif not isinstance(stmt, (jp.Delay, jp.Break)):
                return False
        return True

    def ir_expr(x):
        if x[0] in ('lit', 'var', 'read'): return True
        if x[0] in ('expr', 'not', 'abs'): return ir_expr(x[1])
        if x[0] == 'tmpl': return all(isinstance(p, str) or ir_expr(p) for p in x[1])
        return x[0] == 'bin' and x[1] in ('+', '-', '*', '/', '==', '!=', '<', '<=', '>', '>=', 'and', 'or') and ir_expr(x[2]) and ir_expr(x[3])

    for pc, x in enumerate(a.prog.ins):
        if x.kind not in ('READ', 'CALL', 'IF', 'GOTO', 'DELAY', 'WAIT', 'END'): return None
        if x.kind in ('IF', 'GOTO', 'WAIT') and x.succ <= pc: return None
        if x.cond is not None and not ir_expr(x.cond): return None
        if x.kind == 'CALL' and (not all(ir_expr(arg) for arg in x.args)
                or (x.var and not all(arg[0] == 'lit' for arg in x.args))): return None
    if not statements(b.stmts): return None
    specs = {k: model.input_spec(k) for k in coverage.predicates}
    if not specs: return None
    for spec in specs.values():
        if spec is None or spec.get('type') not in ('INTEGER', 'DOUBLE') or not spec.get('bound') or spec.get('members') is not None:
            return None
        if any(not math.isfinite(v) or abs(v) > 1e12 for v in spec['bound']): return None
        if spec['bound'][0] > spec['bound'][1]: return None
    return specs


class Fork(Exception):
    def __init__(self, condition): self.condition = condition


class Incomplete(Exception):
    pass


class Context:
    def __init__(self, timeout_ms, total_timeout_ms, max_queries):
        import z3
        self.z3 = z3
        self.timeout_ms, self.deadline = timeout_ms, time.perf_counter() + total_timeout_ms / 1000
        self.max_queries = max_queries
        self.path, self.known, self.domains, self.cache = (), {}, {}, {}
        self.queries, self.cache_hits = [], 0
        self.float_text = z3.Function('python_float_str', z3.BitVecSort(64), z3.StringSort())

    def choose(self, condition):
        z3 = self.z3
        condition = z3.simplify(condition)
        if z3.is_true(condition): return True
        if z3.is_false(condition): return False
        key = condition.sexpr()
        if key in self.known: return self.known[key]
        raise Fork(condition)

    def solve(self, condition):
        z3 = self.z3
        condition = z3.simplify(condition)
        if z3.is_false(condition): return None
        remaining = int((self.deadline - time.perf_counter()) * 1000)
        if remaining <= 0: raise Incomplete('SMT total wall-time cap reached')
        constraints = tuple(self.domains.values()) + tuple(self.path) + (condition,)
        key = tuple(x.sexpr() for x in constraints)
        if key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        if len(self.queries) >= self.max_queries: raise Incomplete('SMT query cap reached')
        solver = z3.Solver()
        solver.set(timeout=min(self.timeout_ms, remaining), random_seed=0)
        solver.add(*constraints)
        started = time.perf_counter()
        answer = solver.check()
        self.queries.append({'smt2': solver.to_smt2(), 'result': str(answer),
                             'seconds': time.perf_counter() - started})
        if answer == z3.unknown: raise Incomplete('SMT unknown: ' + solver.reason_unknown())
        model = solver.model() if answer == z3.sat else None
        self.cache[key] = model
        return model

    def require(self, condition, reason):
        if self.solve(self.z3.Not(condition)) is not None:
            raise Unsupported(reason)


class Input:
    """A held input whose type is split only if an interpreter actually reads it."""
    _smt_input = True

    def __init__(self, ctx, key, epoch, spec):
        self.ctx, self.key, self.epoch, self.spec = ctx, key, epoch, spec
        z3 = ctx.z3
        name = str(len(key)) + ':' + key + ':' + str(epoch)
        self.n, self.kind, self.negzero = z3.Int('n_' + name), z3.Int('kind_' + name), z3.Bool('negzero_' + name)
        scale = 10 if spec['type'] == 'DOUBLE' else 1
        self.scale = scale
        self.lo, self.hi = math.ceil(Fraction(str(spec['bound'][0])) * scale), math.floor(Fraction(str(spec['bound'][1])) * scale)
        if self.lo > self.hi: raise Unsupported('SMT input has empty numeric domain')

    def force(self):
        from explorer.verification.smt_values import SmtNumber, FP, RNE
        z3, ctx = self.ctx.z3, self.ctx
        types = [1] + ([2] if self.scale == 10 else []) + ([0] if self.spec.get('nullable', True) else [])
        ctx.domains[(self.key, self.epoch)] = z3.And(self.n >= self.lo, self.n <= self.hi,
            z3.Or(*[self.kind == k for k in types]), z3.Implies(self.kind == 1, self.n % self.scale == 0))
        if self.spec.get('nullable', True) and ctx.choose(self.kind == 0): return None
        floating = self.scale == 10 and ctx.choose(self.kind == 2)
        if floating:
            term = z3.fpRealToFP(RNE, z3.ToReal(self.n) / 10, FP)
            term = z3.If(z3.And(self.n == 0, self.negzero), z3.FPVal(-0.0, FP), term)
        else:
            term = self.n / self.scale
        bound = math.nextafter(max(abs(float(v)) for v in self.spec['bound']), math.inf)
        return SmtNumber(ctx, term, 'float' if floating else 'int', bound, origin=(self.key, self.epoch))

    def concrete(self, model):
        z3 = self.ctx.z3
        if (self.key, self.epoch) not in self.ctx.domains:
            return None if self.spec.get('nullable', True) else self.lo / self.scale if self.scale == 10 else self.lo
        kind = model.eval(self.kind, model_completion=True).as_long()
        if kind == 0: return None
        n = model.eval(self.n, model_completion=True).as_long()
        if kind == 1: return n // self.scale
        if n == 0 and z3.is_true(model.eval(self.negzero, model_completion=True)): return -0.0
        from decimal import Decimal
        return float(Decimal(n) / self.scale)


@dataclass
class Node:
    av: dict
    bv: dict
    now: int
    world: dict
    history: list
    path: tuple
    known: dict
    dwell: int = 0


def smt_product(runner_a, runner_b, *, horizon_ms, input_step_ms, t0_ms,
                max_states, max_transitions, max_input_combinations,
                smt_timeout_ms=1000, smt_total_timeout_ms=10000, smt_max_queries=10000):
    specs = smt_specs(runner_a, runner_b)
    if specs is None: return None
    if min(smt_timeout_ms, smt_total_timeout_ms, smt_max_queries) <= 0:
        raise ValueError('SMT caps must be positive')
    try:
        import z3
        from explorer.verification.smt_values import equal
    except ImportError as error:
        raise Unsupported('SMT fallback requires z3-solver') from error
    from explorer.verification.observation import actions_observation
    from explorer.verification.timed import next_time
    ctx = Context(smt_timeout_ms, smt_total_timeout_ms, smt_max_queries)
    result = ProductResult('EQUIV', bounded_horizon_ms=horizon_ms, input_step_ms=input_step_ms)
    started = time.perf_counter()
    certificate = {'schema': METHOD, 'input_specs': specs, 'events': [], 't0_ms': t0_ms,
        'horizon_ms': horizon_ms, 'input_step_ms': input_step_ms, 'z3_version': z3.get_version_string(),
        'numeric_model': 'exact integers / IEEE binary64 RNE; 0.1 DOUBLE grid, int representations, signed zero, declared None',
        'text_model': 'exact integer formatting; shared uninterpreted binary64 formatting, SAT requires replay',
        'scope': 'acyclic one-shot numeric programs with waits/fixed delays; no GV/clock/loop',
        'closure_kind': 'all-paths-terminated' if horizon_ms is None else 'bounded-path-exhaustion',
        'caps': {'query_ms': smt_timeout_ms, 'total_ms': smt_total_timeout_ms, 'queries': smt_max_queries},
        'queries': ctx.queries, 'both_terminated': True}
    result.symbolic_certificate = certificate
    a, b = TerminalRunner(runner_a), TerminalRunner(runner_b)
    worlds = {}

    def world_at(now):
        epoch = (now - t0_ms) // input_step_ms
        if epoch not in worlds:
            worlds[epoch] = {k: Input(ctx, k, epoch, s) for k, s in specs.items()}
        return worlds[epoch]

    queue = deque([Node({}, {}, t0_ms, world_at(t0_ms), [], (), {})])
    scheduled = 1
    seen, memo_hits = set(), 0

    def freeze(value):
        from explorer.verification.smt_values import SmtNumber, SmtText, SmtBool
        from explorer.verification.state_key import freeze_state
        if isinstance(value, SmtNumber):
            return ('number', value.kind, value.term.sexpr(), value.magnitude,
                    value.dependent, value.origin)
        if isinstance(value, SmtText): return ('text', tuple(freeze(p) for p in value.parts))
        if isinstance(value, SmtBool): return ('bool', value.term.sexpr())
        if isinstance(value, dict): return tuple(sorted((k, freeze(v)) for k, v in value.items()))
        return freeze_state(value)
    try:
        while queue:
            if result.n_steps // 2 >= max_transitions: raise Incomplete('SMT transition cap reached')
            if time.perf_counter() >= ctx.deadline: raise Incomplete('SMT total wall-time cap reached')
            node = queue.popleft()
            ctx.path, ctx.known = node.path, node.known
            result.n_steps += 2
            try:
                ra = a.step(node.av, {}, node.world, node.now, first_tick=not node.history)
                rb = b.step(node.bv, {}, node.world, node.now, first_tick=not node.history)
            except Fork as fork:
                for choice in (False, True):
                    cond = fork.condition if choice else z3.Not(fork.condition)
                    # Retain both branches, including possibly infeasible ones.
                    # A later mismatch/domain query includes the entire path.
                    # Equal traces on this overapproximation need no SAT query.
                    scheduled += 1
                    if scheduled > max_states: raise Incomplete('SMT state cap reached')
                    queue.append(Node(node.av, node.bv, node.now, node.world, node.history,
                        node.path + (cond,), {**node.known, fork.condition.sexpr(): choice}, node.dwell))
                continue
            oa, ob = actions_observation(ra.actions), actions_observation(rb.actions)
            mismatch = z3.simplify(z3.Not(equal(oa, ob, ctx)))
            history = node.history + [(node.world, node.dwell)]
            try:
                model = ctx.solve(mismatch)
            except Incomplete:
                # Resource exhaustion cannot certify equality. A cheap concrete
                # replay can still establish inequality independently of SMT.
                from explorer.verification.symbolic import _witness
                from explorer.verification.symbolic_values import InputSymbol
                candidate_history = [({k: InputSymbol(k, v.epoch, specs[k]['type'],
                    specs[k].get('nullable', True)) for k, v in world.items()}, dwell)
                    for world, dwell in history]
                witness = ProductResult('UNKNOWN', n_steps=result.n_steps, input_step_ms=input_step_ms)
                _witness(runner_a, runner_b, candidate_history, specs, witness,
                         min(max_input_combinations, 64), max_transitions, t0_ms)
                result.n_steps = witness.n_steps
                if witness.divergences:
                    result.verdict, result.divergences = 'DIVERGE', witness.divergences
                    certificate['counterexample_basis'] = 'concrete replay after SMT resource exhaustion; never sampled EQUIV'
                    break
                raise
            certificate['events'].append({'offset_ms': node.now - t0_ms,
                'equal': model is None, 'path': [x.sexpr() for x in node.path],
                'mismatch': mismatch.sexpr()})
            if model is not None:
                concrete = [({k: v.concrete(model) for k, v in world.items()}, dwell) for world, dwell in history]
                # Recompute concrete observations; never trust uninterpreted text
                # or an SMT model as an executable ACTION counterexample alone.
                av, bv, now = {}, {}, t0_ms
                for i, (world, dwell) in enumerate(concrete):
                    if result.n_steps // 2 >= max_transitions: raise Incomplete('SMT replay transition cap reached')
                    now += dwell
                    ca = a.step(av, {}, world, now, first_tick=i == 0)
                    cb = b.step(bv, {}, world, now, first_tick=i == 0)
                    result.n_steps += 2
                    ac, bc = actions_observation(ca.actions), actions_observation(cb.actions)
                    if ac != bc:
                        dv = Divergence(i, world, dwell, ac, bc, concrete[:i], {}, t0_ms, input_step_ms)
                        if replay_divergence(runner_a, runner_b, dv).confirmed:
                            result.divergences.append(dv)
                            result.verdict = 'DIVERGE'
                            break
                    av, bv = ca.vars, cb.vars
                if result.verdict != 'DIVERGE': raise Incomplete('SMT SAT model did not replay; formatting overapproximation or model discrepancy')
                break
            if ra.terminated and rb.terminated: continue
            signature = (freeze(ra.vars), freeze(rb.vars), node.now,
                         tuple(x.sexpr() for x in node.path), tuple(sorted(node.known.items())))
            if signature in seen:
                memo_hits += 1
                continue
            seen.add(signature)
            nxt = next_time(a, b, ra.vars, rb.vars, node.now, t0_ms, input_step_ms)
            if nxt is None:
                # For this acyclic path engine an unbounded positive result
                # requires termination, never an unexplained absent successor.
                if horizon_ms is None: raise Incomplete('SMT nonterminal path has no successor')
                certificate['both_terminated'] = False
                continue
            if horizon_ms is not None and nxt > t0_ms + horizon_ms:
                certificate['both_terminated'] = False
                continue
            scheduled += 1
            if scheduled > max_states: raise Incomplete('SMT state cap reached')
            queue.append(Node(ra.vars, rb.vars, nxt, world_at(nxt), history,
                              node.path, node.known, nxt - node.now))
    except Incomplete as error:
        result.verdict, result.closed = 'UNKNOWN', False
        result.notes.append(str(error))
    result.n_states = scheduled
    certificate['complete'] = result.verdict == 'EQUIV' and not queue
    certificate['cache_hits'] = ctx.cache_hits
    certificate['exact_state_memo_hits'] = memo_hits
    result.notes.append(METHOD + (': all symbolic paths terminate; no horizon' if horizon_ms is None
                                 else ': all feasible bounded paths; no numeric value enumeration'))
    result.seconds = time.perf_counter() - started
    return result
