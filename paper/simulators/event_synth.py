"""IR-guided event synthesizer.

Walks an IR and generates a Scenario containing events that satisfy each
`wait` and exercise each `if` branch. Both IR and JoI simulators run on the
same generated scenario for a fair trace comparison.

Phase-1 patterns supported (per locked design):
- `X.Y == V`        → event at +1s: X.Y = V
- `X.Y >= V` / <=, > , <  → event with V (or boundary +1) at +1s
- edge "rising"     → emit prelude (X.Y = !V) then event (X.Y = V)
- edge "falling"    → emit prelude (X.Y = V) then event (X.Y = !V)
- compound `&&`/`||`: walk both sides, emit events for each leaf. (For OR,
  satisfying one leaf is enough; we satisfy both for simplicity.)

Output: a Scenario with `events` populated. Initial-world is left empty —
the IR simulator's `wait` polling will advance the clock to event times.

NOT supported in phase 1 (will hard-error): `any(#X).Y`, `all(#X).Y`,
clock-only conditions (those don't need synth — they fire from time alone),
arithmetic in cond targets (`Volume + 10 >= 100`).
"""

from __future__ import annotations

from typing import Any

from . import expr
from .scenario import Scenario
from ..timeline_ir import parse_duration_to_ms


def synthesize_scenarios(ir: dict) -> list[Scenario]:
    """Return at least one Scenario covering all wait/if branches in `ir`.

    For paper phase 1 we return a single happy-path scenario that satisfies
    every wait and takes the `then` branch of every `if`. Future phases may
    return multiple scenarios for full branch coverage.
    """
    scenario = Scenario()
    cursor_ms_box = [0]  # mutable cursor advanced as we walk waits
    _walk(ir.get("timeline", []), scenario, cursor_ms_box,
          period_stack=[])
    return [scenario]


def _walk(steps: list, scn: Scenario, cursor: list[int],
          period_stack: list[int]) -> None:
    for step in steps:
        op = step.get("op")
        if op == "wait":
            period_ctx = period_stack[-1] if period_stack else 0
            _synth_wait(step, scn, cursor, period_ms=period_ctx)
        elif op == "if":
            # Synthesize satisfying state for the if cond at the current cursor
            # time so the then-branch fires (paper-locked: happy-path coverage).
            _synth_if_cond(step, scn, cursor)
            _walk(step.get("then", []) or [], scn, cursor, period_stack)
        elif op == "cycle":
            # Push cycle.period so nested waits can align prelude/fire to it.
            cyc_period_ms = parse_duration_to_ms(step["period"]) \
                if step.get("period") else 0
            period_stack.append(cyc_period_ms)
            try:
                _walk(step.get("body", []) or [], scn, cursor, period_stack)
            finally:
                period_stack.pop()
        elif op == "delay":
            cursor[0] += parse_duration_to_ms(step.get("duration", "0 MSEC"))
        # call, read, start_at, break: no synthesis needed


def _synth_if_cond(step: dict, scn: Scenario, cursor: list[int]) -> None:
    """Set device state at cursor time so the if cond evaluates true."""
    ast = expr.parse(step["cond"])
    assignments: list[tuple[str, Any]] = []
    _gather_assignments(ast, assignments)
    # Apply at cursor time — World drains events with at_ms <= t_ms before
    # the if cond is evaluated, so this seeds state in time.
    for key, val in assignments:
        scn.add(cursor[0], key, val)


def _synth_wait(step: dict, scn: Scenario, cursor: list[int],
                period_ms: int = 0) -> None:
    from paper.timeline_ir import parse_duration_to_ms
    cond_src = step["cond"]
    edge = step.get("edge", "none")
    for_str = step.get("for")
    for_ms = parse_duration_to_ms(for_str) if for_str else 0
    ast = expr.parse(cond_src)

    # Find satisfying assignment(s). For compound conds, satisfy all leaves.
    assignments: list[tuple[str, Any]] = []
    _gather_assignments(ast, assignments)

    if not assignments:
        return  # purely clock-based or unrecognized — no synthesis needed

    # Period-aware fire/prelude placement: when wait is inside a cycle with a
    # known period, snap fire_ms to the next period-aligned tick boundary and
    # place the prelude one full period earlier so the previous JoI tick
    # observes prev=false. Without this, large periods (e.g. 60s) cause the
    # prelude to land within the same tick window as the fire and the rising
    # edge is missed. Falls back to ±1000/200 magic for top-level waits.
    if edge in ("rising", "falling"):
        if period_ms and period_ms > 200:
            fire_ms = ((cursor[0] // period_ms) + 1) * period_ms
            prelude_offset = period_ms
        else:
            fire_ms = cursor[0] + 1000
            prelude_offset = 200
        prelude_ms = max(cursor[0], fire_ms - prelude_offset)

    if edge == "rising":
        for key, val in assignments:
            scn.add(prelude_ms, key, _opposite(val))
        for key, val in assignments:
            scn.add(fire_ms, key, val)
        cursor[0] = fire_ms
    elif edge == "falling":
        for key, val in assignments:
            scn.add(prelude_ms, key, val)
        for key, val in assignments:
            scn.add(fire_ms, key, _opposite(val))
        cursor[0] = fire_ms
    else:
        # Level-triggered: satisfy at the current cursor time (no extra delay).
        # This keeps IR-poll and JoI-tick timings aligned: both observe cond
        # true on their next clock check past `cursor[0]`.
        for key, val in assignments:
            scn.add(cursor[0], key, val)
        # cursor unchanged — wait satisfies "instantly" in this scenario

    # Sustain (`wait.for`): after the cond-true point, cond must remain true
    # CONTINUOUSLY for for_ms before wait completes. The happy-path scenario
    # leaves cond pinned (no further events flip it), so the only adjustment
    # needed here is to advance cursor by for_ms so downstream ops align with
    # the post-sustain clock. NOTE: the flap-reset coverage scenario (Scenario
    # B in §6.4 build-up) is a separate scenario whose synthesis is left for
    # a future multi-scenario synthesizer pass.
    if for_ms > 0:
        cursor[0] += for_ms


def _gather_assignments(node: Any, out: list[tuple[str, Any]]) -> None:
    """Walk an AST and produce (device.attr key, satisfying value) pairs."""
    if isinstance(node, expr.BinaryOp):
        if node.op in ("and", "or"):
            _gather_assignments(node.left, out)
            _gather_assignments(node.right, out)
            return
        if node.op in ("==", "!=", "<", ">", "<=", ">="):
            # Expect DeviceRef on one side, Lit on the other.
            # Unwrap quantifier wrappers like `avg(X) >= V` to extract inner DeviceRef.
            left = _unwrap_quantifier(node.left)
            right = _unwrap_quantifier(node.right)
            dev, lit = _split_dev_lit(left, right)
            if dev is None or lit is None:
                return  # involves clock or var — skip
            val = _satisfying_value(node.op, lit.value, dev_swap=(dev is right))
            out.append((dev.key, val))
            return
    if isinstance(node, expr.FuncCall) and node.name in ("all", "any"):
        # Top-level quantifier wrapping a relational/boolean expression
        # (e.g., `all(TemperatureSensor.Temperature >= 35)`). Recurse into the
        # inner predicate so a single-device satisfying value is seeded.
        for arg in node.args:
            _gather_assignments(arg, out)
        return
    # Other shapes (UnaryOp not, ClockRef alone, etc.) — skip


def _unwrap_quantifier(node: Any) -> Any:
    """If `node` is `avg(...)` / `all(...)` / `any(...)` over a single operand,
    return that operand so callers can pattern-match it as a DeviceRef. Otherwise
    return `node` unchanged. Single-device collapse fallback (framework 2026-05-08).
    """
    if isinstance(node, expr.FuncCall) and node.name in ("avg", "all", "any"):
        if len(node.args) == 1:
            return _unwrap_quantifier(node.args[0])
    return node


def _split_dev_lit(a: Any, b: Any) -> tuple[Any, Any]:
    """Return (device_ref, literal) regardless of operand order; (None, None) otherwise."""
    if isinstance(a, expr.DeviceRef) and isinstance(b, expr.Lit):
        return a, b
    if isinstance(b, expr.DeviceRef) and isinstance(a, expr.Lit):
        return b, a
    return (None, None)


def _satisfying_value(op: str, lit_val: Any, dev_swap: bool) -> Any:
    """Pick a value that makes (device OP literal) true.

    `dev_swap`: True if the device was on the RIGHT of the operator, in which
    case we flip the comparison direction.
    """
    # Effective op as seen from device's perspective
    effective = op
    if dev_swap:
        # `5 >= X` is equivalent to `X <= 5`
        flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
        effective = flip.get(op, op)

    if effective == "==":
        return lit_val
    if effective == "!=":
        return _opposite(lit_val)
    if effective == ">=":
        return lit_val  # boundary value satisfies
    if effective == "<=":
        return lit_val
    if effective == ">":
        if isinstance(lit_val, (int, float)):
            return lit_val + 1
        return lit_val
    if effective == "<":
        if isinstance(lit_val, (int, float)):
            return lit_val - 1
        return lit_val
    return lit_val


def _opposite(val: Any) -> Any:
    """Return a value that's NOT equal to `val` (for prelude / != cases)."""
    if isinstance(val, bool):
        return not val
    if isinstance(val, (int, float)):
        return val - 1
    if isinstance(val, str):
        return f"_not_{val}"
    return None
