"""IR simulator: linear walker of Timeline IR.

Executes IR ops against a shared World/Scenario, emitting a Trace of
external `call` invocations. Defines paper §6.2 IR operational semantics.

Semantics summary:
- `start_at(now)`: t starts at 0 (Monday 00:00).
- `start_at(cron)`: t starts at the first cron fire on/after Monday 00:00.
- `delay(ms)`: advance clock by ms.
- `read(var, src)`: vars[var] = world[src].
- `call(target, args, bind?)`: emit trace; apply effects; if `bind`, store
  a synthetic return value into vars[bind].
- `wait(cond, edge)`: advance clock 100ms at a time until cond holds. For
  edge="rising", wait for previous-false → current-true transition.
- `if(cond, then, else)`: branch on cond evaluated NOW.
- `cycle(body, until?)`: loop body. Check `until` at top of each iteration.
- `break`: raise out of innermost cycle.

Stop conditions (paper-locked):
1. Timeline fully consumed (no more ops, no pending cycle) → exit.
2. Trace size >= 1000 → exit.
3. t_ms >= 7*86400*1000 → exit.
"""

from __future__ import annotations

from typing import Any

from . import expr
from .scenario import Scenario
from .traces import Trace, normalize_args, normalize_value
from .world import World

MAX_TRACE = 1000
MAX_T_MS = 7 * 86_400_000  # 7 days
TICK_MS = 100  # for wait polling


class _BreakException(Exception):
    """Raised by `break` op to unwind to enclosing cycle."""


class _StopException(Exception):
    """Raised when global stop condition fires (trace cap or time cap)."""


def run_ir_simulation(
    ir: dict,
    scenario: Scenario,
    catalog: dict | None,
    debug: bool = False,
) -> Trace:
    """Execute an IR against the scenario and return the emitted Trace."""
    world = World(scenario)
    trace = Trace()

    timeline = ir.get("timeline", [])
    if not timeline:
        return trace

    # Handle start_at
    head = timeline[0]
    body = timeline[1:]
    if head.get("op") == "start_at":
        anchor = head.get("anchor", "now")
        if anchor == "cron":
            cron = head.get("cron", "")
            first_fire = _next_cron_fire(cron, world.t_ms, scenario)
            if first_fire is None:
                return trace  # cron never fires in window
            world.advance_to(first_fire)
        # "now" → leave t at 0
    else:
        body = timeline

    try:
        _exec_steps(body, world, trace, catalog, debug)
    except _StopException:
        pass

    return trace


# ── Step execution ──────────────────────────────────────────────────────────

def _check_stop(world: World, trace: Trace) -> None:
    if trace.group_count >= MAX_TRACE:
        raise _StopException()
    if world.t_ms >= MAX_T_MS:
        raise _StopException()


def _exec_steps(steps: list, world: World, trace: Trace, catalog, debug: bool) -> None:
    for step in steps:
        _check_stop(world, trace)
        op = step.get("op")
        if op == "delay":
            world.advance_by(int(step.get("ms", 0)))
        elif op == "read":
            _exec_read(step, world)
        elif op == "call":
            _exec_call(step, world, trace, catalog, debug)
        elif op == "wait":
            _exec_wait(step, world)
        elif op == "if":
            _exec_if(step, world, trace, catalog, debug)
        elif op == "cycle":
            _exec_cycle(step, world, trace, catalog, debug)
        elif op == "break":
            raise _BreakException()
        else:
            raise NotImplementedError(f"unknown IR op: {op}")


def _ctx(world: World) -> expr.EvalContext:
    return expr.EvalContext(world.state, world.vars, world.clock)


def _exec_read(step: dict, world: World) -> None:
    var_name = step["var"]
    src = step["src"]  # e.g., "TempSensor.Temperature"
    # src may be a dotted device.attr OR an expression — be liberal
    val = expr.eval_str(src, _ctx(world))
    world.vars[var_name] = val


def _exec_call(step: dict, world: World, trace: Trace, catalog, debug: bool) -> None:
    target = step["target"]
    args_in = step.get("args", {}) or {}
    # `var` declares the variable holding the call's synthetic return.
    # Accept legacy `bind` for backward-compat with cached IR samples.
    var_name = step.get("var") or step.get("bind")

    from .catalog import split_target
    service, method = split_target(target)

    # Evaluate any expression-valued args against current state
    args_evaluated: dict = {}
    for k, v in args_in.items():
        args_evaluated[k] = _maybe_eval(v, world)

    # Emit normalized trace record
    canon_args = normalize_args(catalog, service, method, args_evaluated)
    trace.emit(world.t_ms, service, method, canon_args)

    # Apply best-effort effects to the world (so later reads see new state)
    world.apply_effect(service, method, args_evaluated)

    # Store synthetic return value (just the args dict for now — most
    # tests don't actually depend on return semantics)
    if var_name:
        world.vars[var_name] = args_evaluated

    if debug:
        print(f"[IR t={world.t_ms}] call {target}({args_evaluated}) -> trace={canon_args}")


_VAR_SUBST_RE = __import__("re").compile(r"\$([A-Za-z_][A-Za-z0-9_.]*)")


def _maybe_eval(v: Any, world: World) -> Any:
    """If `v` is an expression-string, evaluate it; else return as-is.

    Also resolves `$varname` and `$Service.Attr` substitutions so IR args like
    `"temp is $t1"` or `"weather is $Weather.Forecast"` produce the same trace
    as JoI's string-concat form.
    """
    if not isinstance(v, str):
        return v
    # First try full-expression evaluation (e.g., "Volume + 10")
    markers = set(".+-*/()<>=!&|")
    if any(c in markers for c in v):
        try:
            return expr.eval_str(v, _ctx(world))
        except Exception:
            pass  # fall through to var-substitution
    # Then $var / $Service.Attr substitution within plain strings
    if "$" in v:
        from .expr import canonical_key
        def _sub(m):
            name = m.group(1)
            if "." in name:
                # $Service.Attr → device-state lookup
                first, _, rest = name.partition(".")
                if first[:1].isupper():
                    svc, a = canonical_key(first, rest)
                    val = world.state.get(f"{svc}.{a}")
                else:
                    val = world.vars.get(name)
            else:
                val = world.vars.get(name)
            return "" if val is None else str(val)
        return _VAR_SUBST_RE.sub(_sub, v)
    return v


def _exec_wait(step: dict, world: World) -> None:
    cond_src = step["cond"]
    edge = step.get("edge", "none")
    cond_ast = expr.parse(cond_src)
    uses_clock = _cond_uses_clock(cond_ast)

    if edge == "none":
        while True:
            _check_stop_world(world)
            if expr.evaluate(cond_ast, _ctx(world)):
                return
            # Early-stop: if no pending scenario events AND cond doesn't read
            # clock, the world can't change in a way that satisfies cond.
            if not world._pending and not uses_clock:
                raise _StopException()
            world.advance_by(TICK_MS)
    elif edge in ("rising", "falling"):
        prev = bool(expr.evaluate(cond_ast, _ctx(world)))
        while True:
            _check_stop_world(world)
            if not world._pending and not uses_clock:
                raise _StopException()
            world.advance_by(TICK_MS)
            cur = bool(expr.evaluate(cond_ast, _ctx(world)))
            if edge == "rising" and (not prev) and cur:
                return
            if edge == "falling" and prev and (not cur):
                return
            prev = cur


def _cond_uses_clock(node) -> bool:
    """True if the cond AST contains any ClockRef (so time-advance can satisfy it)."""
    if isinstance(node, expr.ClockRef):
        return True
    if isinstance(node, expr.UnaryOp):
        return _cond_uses_clock(node.operand)
    if isinstance(node, expr.BinaryOp):
        return _cond_uses_clock(node.left) or _cond_uses_clock(node.right)
    return False


def _check_stop_world(world: World) -> None:
    if world.t_ms >= MAX_T_MS:
        raise _StopException()


def _exec_if(step: dict, world: World, trace: Trace, catalog, debug: bool) -> None:
    cond = expr.parse(step["cond"])
    branch = "then" if expr.evaluate(cond, _ctx(world)) else "else"
    _exec_steps(step.get(branch, []) or [], world, trace, catalog, debug)


def _exec_cycle(step: dict, world: World, trace: Trace, catalog, debug: bool) -> None:
    body = step.get("body", []) or []
    until_src = step.get("until")
    until_ast = expr.parse(until_src) if until_src else None
    while True:
        _check_stop(world, trace)
        if until_ast is not None and expr.evaluate(until_ast, _ctx(world)):
            return
        try:
            _exec_steps(body, world, trace, catalog, debug)
        except _BreakException:
            return


# ── Cron handling ────────────────────────────────────────────────────────────

_DOW_NAME_TO_NUM = {"MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6, "SUN": 7,
                    "0": 7, "7": 7}  # cron treats 0 and 7 as Sunday


def _next_cron_fire(cron: str, after_ms: int, scenario: Scenario) -> int | None:
    """Find the first cron fire time at or after `after_ms` within MAX_T_MS.

    Cron format: 5 fields "min hour day month dow" or simpler subsets.
    Day, month fields ignored except "*"; we operate within a single week
    starting Monday 00:00. Returns ms or None if no fire in window.
    """
    parts = cron.strip().split()
    if len(parts) != 5:
        # Treat invalid cron as "now"
        return after_ms
    minute, hour, _day, _month, dow = parts

    target_minutes = _expand_field(minute, 0, 59)
    target_hours = _expand_field(hour, 0, 23)
    target_dows = _expand_dow(dow)

    # Iterate minute by minute up to MAX_T_MS
    t = after_ms
    while t < MAX_T_MS:
        # Snap up to the next minute boundary
        if t % 60_000 != 0:
            t = ((t // 60_000) + 1) * 60_000
        # Compute hh, mm, dow at t
        ms_in_day = t % _MS_PER_DAY
        hh = ms_in_day // 3_600_000
        mm = (ms_in_day // 60_000) % 60
        days_elapsed = t // _MS_PER_DAY
        try:
            scen_dow_offset = _DAYS_STR.index(scenario.start_dow)
        except ValueError:
            scen_dow_offset = 0
        cur_dow = ((days_elapsed + scen_dow_offset) % 7) + 1  # 1..7
        if hh in target_hours and mm in target_minutes and cur_dow in target_dows:
            return t
        t += 60_000
    return None


_DAYS_STR = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_MS_PER_DAY = 86_400_000


def _expand_field(spec: str, lo: int, hi: int) -> set[int]:
    """Expand a cron field (`*`, `5`, `1,3,5`, `*/2`, `9-17`) to a set."""
    if spec == "*":
        return set(range(lo, hi + 1))
    out: set[int] = set()
    for piece in spec.split(","):
        if "/" in piece:
            base, step = piece.split("/")
            step_i = int(step)
            if base == "*":
                out.update(range(lo, hi + 1, step_i))
            elif "-" in base:
                a, b = base.split("-")
                out.update(range(int(a), int(b) + 1, step_i))
            else:
                out.update(range(int(base), hi + 1, step_i))
        elif "-" in piece:
            a, b = piece.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(piece))
    return {v for v in out if lo <= v <= hi}


def _expand_dow(spec: str) -> set[int]:
    """Expand cron dow field. Accepts numeric (0-7, 0/7=Sunday) and MON..SUN names."""
    if spec == "*":
        return set(range(1, 8))
    parts = spec.replace(",", " ").split()
    out: set[int] = set()
    for p in parts:
        p_up = p.upper()
        if p_up in _DOW_NAME_TO_NUM:
            out.add(_DOW_NAME_TO_NUM[p_up])
        else:
            try:
                n = int(p)
                if n == 0:
                    n = 7
                out.add(n)
            except ValueError:
                pass
    return out
