"""IR simulator: linear walker of Timeline IR.

Executes IR ops against a shared World/Scenario, emitting a Trace of
external `call` invocations. Defines paper §6.2 IR operational semantics.

Semantics summary:
- `start_at(now)`: t starts at 0 (Monday 00:00).
- `start_at(cron)`: t starts at the first cron fire on/after Monday 00:00.
- `delay(duration)`: parse `"N UNIT"` (HOUR/MIN/SEC/MSEC) and advance clock by N units.
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
from ..timeline_ir import parse_duration_to_ms

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
            # P4 (2026-05-20): top-level start_at(cron) means "re-execute body
            # on every cron firing within the 7-day window" — not just once at
            # first fire. Matches NL semantics like "매 정각마다 X" → body fires
            # at every cron occurrence. When body has its own cycle (D-9 cron+
            # cycle composition), the cycle handles intra-fire iteration; the
            # outer cron loop just re-enters body once per cron occurrence.
            cron = head.get("cron", "")
            try:
                while True:
                    _check_stop(world, trace)
                    next_fire = _next_cron_fire(cron, world.t_ms, scenario)
                    if next_fire is None or next_fire >= MAX_T_MS:
                        return trace
                    world.advance_to(next_fire)
                    _exec_steps(body, world, trace, catalog, debug)
                    # Step past the current minute so the next cron lookup
                    # advances rather than returning the same fire.
                    world.advance_by(60_000)
            except _StopException:
                return trace
        # "now" → leave t at 0, execute body once
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
            world.advance_by(parse_duration_to_ms(step.get("duration", "0 MSEC")))
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

    # Store synthetic return value. Use the post-effect world-state slot
    # (`<svc>.<canonical-attr>`) so the captured return is symmetric with the
    # JoI sim, which stores `world.state.get(<canonical key>)` on the
    # `Var = (#X).Method(...)` path. For pure side-effect or stubbed calls
    # (e.g., cloud GenerateImage) both sides end up storing None — making
    # downstream `$Var` references compare equal across sims.
    if var_name:
        from .expr import canonical_name
        key = f"{(service or '').lower()}.{canonical_name(service, method)}"
        world.vars[var_name] = world.state.get(key)

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
    # Try full-expression evaluation only when the string looks like one.
    # `.` alone is NOT a marker — file paths ("cat.png"), URLs, qualified
    # tokens like "Building 301" would otherwise eval to None silently and
    # poison the trace. Real expressions always carry an arithmetic or
    # comparison operator (or a `$`-prefixed var ref that the var-substitution
    # path below also handles).
    markers = set("+-*/<>=!&|")
    if any(c in markers for c in v) or v.lstrip().startswith("$"):
        try:
            result = expr.eval_str(v, _ctx(world))
        except Exception:
            result = None
        # eval_str returns None on unresolved idents — only trust it when
        # something meaningful came back, otherwise fall through.
        if result is not None:
            return result
    # Then $var / $Service.Attr substitution within plain strings
    if "$" in v:
        from .expr import canonical_key
        # Standalone reference (`$VarName` or `$Service.Attr` and nothing
        # else): preserve the raw value type — None stays None, ints stay
        # ints. This keeps IR-side captured-return symmetry with the JoI
        # sim, where `Var = (#X).Method(...)` stores `world.state.get(key)`
        # raw. String-coercion is only done for embedded interpolation
        # ("temp is $t"), where concatenation forces a string anyway.
        stripped = v.strip()
        m_whole = _VAR_SUBST_RE.fullmatch(stripped)
        if m_whole:
            name = m_whole.group(1)
            if "." in name:
                first, _, rest = name.partition(".")
                if first[:1].isupper():
                    svc, a = canonical_key(first, rest)
                    return world.state.get(f"{svc}.{a}")
                return world.vars.get(name)
            return world.vars.get(name)

        def _sub(m):
            name = m.group(1)
            if "." in name:
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
    for_str = step.get("for")
    for_ms = parse_duration_to_ms(for_str) if for_str else 0
    cond_ast = expr.parse(cond_src)
    uses_clock = _cond_uses_clock(cond_ast)

    if edge == "none":
        if for_ms <= 0:
            while True:
                _check_stop_world(world)
                if expr.evaluate(cond_ast, _ctx(world)):
                    return
                # Early-stop: if no pending scenario events AND cond doesn't read
                # clock, the world can't change in a way that satisfies cond.
                if not world._pending and not uses_clock:
                    raise _StopException()
                world.advance_by(TICK_MS)
        else:
            # Sustained-true: cond must remain true CONTINUOUSLY for for_ms.
            # Flip to false → timer resets to 0.
            hold_ms = 0
            while True:
                _check_stop_world(world)
                if expr.evaluate(cond_ast, _ctx(world)):
                    hold_ms += TICK_MS
                    if hold_ms >= for_ms:
                        return
                else:
                    hold_ms = 0
                    if not world._pending and not uses_clock:
                        raise _StopException()
                world.advance_by(TICK_MS)
    elif edge in ("rising", "falling"):
        target_state = (edge == "rising")
        prev = bool(expr.evaluate(cond_ast, _ctx(world)))
        # Outer loop: each iteration is one "wait-for-edge + sustain" attempt.
        # If cond flips back during the sustain phase, we restart from edge-wait.
        while True:
            # Phase 1: wait for the edge.
            while True:
                _check_stop_world(world)
                if not world._pending and not uses_clock:
                    raise _StopException()
                world.advance_by(TICK_MS)
                cur = bool(expr.evaluate(cond_ast, _ctx(world)))
                edge_fired = (cur == target_state) and (prev != target_state)
                prev = cur
                if edge_fired:
                    break
            if for_ms <= 0:
                return
            # Phase 2: cond must remain in post-edge state for for_ms.
            hold_ms = 0
            flipped = False
            while hold_ms < for_ms:
                _check_stop_world(world)
                world.advance_by(TICK_MS)
                cur = bool(expr.evaluate(cond_ast, _ctx(world)))
                if cur == target_state:
                    hold_ms += TICK_MS
                else:
                    flipped = True
                    prev = cur
                    break
            if not flipped:
                return
            # else: loop back to Phase 1 and wait for the next edge.


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
    period_str = step.get("period")
    period_ms = parse_duration_to_ms(period_str) if period_str else None
    while True:
        _check_stop(world, trace)
        if until_ast is not None and expr.evaluate(until_ast, _ctx(world)):
            return
        iter_start_ms = world.t_ms
        try:
            _exec_steps(body, world, trace, catalog, debug)
        except _BreakException:
            return
        if period_ms is not None:
            elapsed = world.t_ms - iter_start_ms
            if elapsed < period_ms:
                world.advance_by(period_ms - elapsed)


# ── Cron handling ────────────────────────────────────────────────────────────

_DOW_NAME_TO_NUM = {"MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6, "SUN": 7,
                    "0": 7, "7": 7}  # legacy: 0/7=Sun for GT replay compat
# Canonical pipeline form is digit 1-7 (1=Mon..7=Sun). Names and "0" are
# retained ONLY to replay older test IRs / dataset GT crons without crashing.


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
    """Expand cron dow field. Canonical form is digit 1-7 (1=Mon..7=Sun) with
    optional hyphen-ranges (e.g. `1-5` for weekdays). Legacy `0` and English
    names (MON..SUN) are accepted for GT-replay compat.
    """
    if spec == "*":
        return set(range(1, 8))
    parts = spec.replace(",", " ").split()
    out: set[int] = set()

    def _to_num(tok: str) -> int | None:
        tok_up = tok.upper()
        if tok_up in _DOW_NAME_TO_NUM:
            return _DOW_NAME_TO_NUM[tok_up]
        try:
            n = int(tok)
            if n == 0:
                n = 7
            if 1 <= n <= 7:
                return n
        except ValueError:
            pass
        return None

    for p in parts:
        if "-" in p and p.count("-") == 1:
            lo_s, hi_s = p.split("-", 1)
            lo, hi = _to_num(lo_s), _to_num(hi_s)
            if lo is not None and hi is not None:
                # Wrap-around range (e.g. 6-2 meaning Sat,Sun,Mon,Tue) not in
                # canonical pipeline output but supported defensively.
                if lo <= hi:
                    out.update(range(lo, hi + 1))
                else:
                    out.update(list(range(lo, 8)) + list(range(1, hi + 1)))
                continue
        n = _to_num(p)
        if n is not None:
            out.add(n)
    return out
