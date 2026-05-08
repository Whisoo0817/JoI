"""JoI simulator: tick-based AST interpreter.

Defines paper §6.3 JoI operational semantics.

Execution model:
- A JoI block is `{cron, period, script}`.
- `cron == ""`: start at t=0; `period == 0`: run script once and exit.
- `cron != ""`: start at first cron fire (within 7-day window).
- `period > 0`: tick every `period` ms. First tick runs `:=` initializers
  AND the body. Subsequent ticks skip `:=` and run the body fresh.
- `:=` lvalues persist across ticks (state).
- `=` lvalues update each tick (fresh evaluation).
- `wait until(cond)` inside a tick: if cond false, abort the rest of this
  tick's execution; re-try on next tick.
- `delay(N UNIT)` inside a tick: advance the virtual clock by N ms within
  the same tick. (Rare in periodic scripts; common in one-shot.)
- `break` exits the tick loop entirely (script terminates).

Stop conditions: same as IR sim (1000 records, 7 days, no pending).
"""

from __future__ import annotations

from typing import Any

from . import expr as expr_mod
from . import joi_parser as jp
from .scenario import Scenario
from .traces import Trace, normalize_args
from .world import World
from .ir_simulator import _next_cron_fire, MAX_TRACE, MAX_T_MS

TICK_POLL_MS = 100  # tick granularity for in-tick polling (e.g., delay residue)


class _BreakException(Exception):
    pass


class _StopException(Exception):
    pass


class _AbortTick(Exception):
    """Raised by `wait until(cond)` when cond is false — skip rest of this tick."""


def run_joi_simulation(
    joi_block: dict,
    scenario: Scenario,
    catalog: dict | None,
    debug: bool = False,
) -> Trace:
    """Execute a JoI block under `scenario`, return the emitted Trace."""
    world = World(scenario)
    trace = Trace()

    cron = joi_block.get("cron", "") or ""
    period = int(joi_block.get("period", 0) or 0)
    script_src = joi_block.get("script", "") or ""

    if not script_src.strip():
        return trace

    # Parse once
    stmts = jp.parse_script(script_src)

    # Cron start
    if cron:
        first_fire = _next_cron_fire(cron, 0, scenario)
        if first_fire is None:
            return trace
        world.advance_to(first_fire)

    # Persistent var slot — survives across ticks. World already has
    # `world.vars` for fresh `=` assignments, but `:=` vars need stable storage.
    # We use the same dict — `:=` only initializes if not present, `=` overwrites.
    persisted: set[str] = set()

    try:
        if period == 0:
            # One-shot: run script body once.
            _exec_script_once(stmts, world, trace, catalog, persisted, debug,
                              first_tick=True, is_oneshot=True)
        else:
            # Tick loop with idle early-stop: if a full tick passes without any
            # new trace records AND no scenario events remain pending, the
            # script has reached a stable state with no further work. Same idea
            # as IR's "no pending" rule.
            first_tick = True
            idle_ticks_with_no_pending = 0
            while True:
                _check_stop(world, trace)
                trace_size_before = len(trace)
                try:
                    _exec_script_once(stmts, world, trace, catalog, persisted, debug,
                                      first_tick=first_tick, is_oneshot=False)
                except _AbortTick:
                    pass
                first_tick = False
                made_progress = len(trace) > trace_size_before
                if not world._pending and not made_progress:
                    idle_ticks_with_no_pending += 1
                    if idle_ticks_with_no_pending >= 2:
                        break
                else:
                    idle_ticks_with_no_pending = 0
                world.advance_by(period)
    except _StopException:
        pass
    except _BreakException:
        pass  # break in top-level — script done

    return trace


def _check_stop(world: World, trace: Trace) -> None:
    if trace.group_count >= MAX_TRACE or world.t_ms >= MAX_T_MS:
        raise _StopException()


def _exec_script_once(stmts: list, world: World, trace: Trace, catalog,
                      persisted: set, debug: bool, first_tick: bool,
                      is_oneshot: bool) -> None:
    for s in stmts:
        _check_stop(world, trace)
        _exec_stmt(s, world, trace, catalog, persisted, debug, first_tick, is_oneshot)


def _exec_stmt(stmt: Any, world: World, trace: Trace, catalog,
               persisted: set, debug: bool, first_tick: bool,
               is_oneshot: bool) -> None:
    if isinstance(stmt, jp.Assign):
        _exec_assign(stmt, world, persisted, first_tick)
    elif isinstance(stmt, jp.IfStmt):
        cond = _eval(stmt.cond, world)
        body = stmt.then_body if cond else stmt.else_body
        for s in body:
            _exec_stmt(s, world, trace, catalog, persisted, debug, first_tick, is_oneshot)
    elif isinstance(stmt, jp.WaitUntil):
        # In one-shot (period=0): poll-block until cond holds. Mirrors IR `wait`.
        # In periodic: abort this tick if cond is false; retry next tick.
        if is_oneshot:
            _block_until(stmt.cond, world)
        else:
            if not _eval(stmt.cond, world):
                raise _AbortTick()
    elif isinstance(stmt, jp.Delay):
        world.advance_by(stmt.ms)
    elif isinstance(stmt, jp.Break):
        raise _BreakException()
    elif isinstance(stmt, jp.CallStmt):
        _emit_call(stmt.call, world, trace, catalog, debug)
    else:
        raise NotImplementedError(f"unknown JoI stmt: {type(stmt).__name__}")


def _block_until(cond_node: Any, world: World) -> None:
    """Advance the virtual clock 100ms at a time until `cond_node` evaluates true.

    Early-exit symmetric with IR sim: if no pending events remain AND the cond
    doesn't read the clock, the value can't change — bail out (raises stop).
    """
    from . import expr as expr_mod
    uses_clock = _cond_uses_clock(cond_node)
    while True:
        if world.t_ms >= MAX_T_MS:
            raise _StopException()
        if _eval(cond_node, world):
            return
        if not world._pending and not uses_clock:
            raise _StopException()
        world.advance_by(TICK_POLL_MS)


def _cond_uses_clock(node: Any) -> bool:
    from . import expr as expr_mod
    if isinstance(node, expr_mod.ClockRef):
        return True
    if isinstance(node, expr_mod.UnaryOp):
        return _cond_uses_clock(node.operand)
    if isinstance(node, expr_mod.BinaryOp):
        return _cond_uses_clock(node.left) or _cond_uses_clock(node.right)
    return False


def _exec_assign(stmt: jp.Assign, world: World, persisted: set, first_tick: bool) -> None:
    if stmt.op == ":=":
        # Persist-init: only on first tick (or first time we see this var)
        if first_tick or stmt.name not in persisted:
            world.vars[stmt.name] = _eval(stmt.rhs, world, capture_call=True)
            persisted.add(stmt.name)
        # else: skip — value persists
    else:  # "="
        world.vars[stmt.name] = _eval(stmt.rhs, world, capture_call=True)


def _eval(node: Any, world: World, capture_call: bool = False) -> Any:
    """Evaluate an expression node against the world. Method calls in expressions
    are treated as attribute reads when args is None, or executed (returning a
    placeholder) when args is a list and `capture_call=True`."""
    if isinstance(node, jp.CallExpr):
        from .expr import canonical_name
        key = f"{(node.service or '').lower()}.{canonical_name(node.service, node.method)}"
        if node.args is None:
            return world.state.get(key)
        if capture_call:
            return world.state.get(key)
        return None
    if isinstance(node, expr_mod.DeviceRef):
        return world.state.get(node.key)
    # Reuse the shared evaluator for all other AST forms (Lit, ClockRef, VarRef,
    # UnaryOp, BinaryOp).
    ctx = expr_mod.EvalContext(world.state, world.vars, world.clock)
    return expr_mod.evaluate(node, ctx)


def _emit_call(call: jp.CallExpr, world: World, trace: Trace, catalog, debug: bool) -> None:
    # Evaluate args to concrete values
    arg_values = [_eval(a, world, capture_call=True) for a in (call.args or [])]
    # Build named-arg dict using catalog order so we can apply effects
    named: dict = {}
    if catalog is not None:
        from .catalog import get_arg_order
        order = get_arg_order(catalog, call.service, call.method)
        if order is not None:
            for i, v in enumerate(arg_values):
                if i < len(order):
                    named[order[i]] = v
    # Trace: positional list (already in code order = catalog order from JoI source)
    canon = normalize_args(catalog, call.service, call.method, arg_values)
    trace.emit(world.t_ms, call.service, call.method, canon)
    # World effect
    world.apply_effect(call.service, call.method, named)
    if debug:
        print(f"[JoI t={world.t_ms}] call {call.service}.{call.method}({arg_values}) -> {canon}")
