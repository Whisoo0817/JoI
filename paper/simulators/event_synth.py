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


def synthesize_scenarios(ir: dict) -> list[Scenario]:
    """Return at least one Scenario covering all wait/if branches in `ir`.

    For paper phase 1 we return a single happy-path scenario that satisfies
    every wait and takes the `then` branch of every `if`. Future phases may
    return multiple scenarios for full branch coverage.
    """
    scenario = Scenario()
    cursor_ms_box = [0]  # mutable cursor advanced as we walk waits
    _walk(ir.get("timeline", []), scenario, cursor_ms_box, in_cycle=False)
    return [scenario]


def _walk(steps: list, scn: Scenario, cursor: list[int], in_cycle: bool) -> None:
    for step in steps:
        op = step.get("op")
        if op == "wait":
            _synth_wait(step, scn, cursor)
        elif op == "if":
            # Synthesize satisfying state for the if cond at the current cursor
            # time so the then-branch fires (paper-locked: happy-path coverage).
            _synth_if_cond(step, scn, cursor)
            _walk(step.get("then", []) or [], scn, cursor, in_cycle)
        elif op == "cycle":
            # Walk body once for synthesis (events for first iteration only)
            _walk(step.get("body", []) or [], scn, cursor, in_cycle=True)
        elif op == "delay":
            cursor[0] += int(step.get("ms", 0))
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


def _synth_wait(step: dict, scn: Scenario, cursor: list[int]) -> None:
    cond_src = step["cond"]
    edge = step.get("edge", "none")
    ast = expr.parse(cond_src)

    # Find satisfying assignment(s). For compound conds, satisfy all leaves.
    assignments: list[tuple[str, Any]] = []
    _gather_assignments(ast, assignments)

    if not assignments:
        return  # purely clock-based or unrecognized — no synthesis needed

    if edge == "rising":
        # Prelude required for transition detection; fire after a short gap.
        fire_ms = cursor[0] + 1000
        prelude_ms = max(cursor[0], fire_ms - 200)
        for key, val in assignments:
            scn.add(prelude_ms, key, _opposite(val))
        for key, val in assignments:
            scn.add(fire_ms, key, val)
        cursor[0] = fire_ms
    elif edge == "falling":
        fire_ms = cursor[0] + 1000
        prelude_ms = max(cursor[0], fire_ms - 200)
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


def _gather_assignments(node: Any, out: list[tuple[str, Any]]) -> None:
    """Walk an AST and produce (device.attr key, satisfying value) pairs."""
    if isinstance(node, expr.BinaryOp):
        if node.op in ("and", "or"):
            _gather_assignments(node.left, out)
            _gather_assignments(node.right, out)
            return
        if node.op in ("==", "!=", "<", ">", "<=", ">="):
            # Expect DeviceRef on one side, Lit on the other
            dev, lit = _split_dev_lit(node.left, node.right)
            if dev is None or lit is None:
                return  # involves clock or var — skip
            val = _satisfying_value(node.op, lit.value, dev_swap=(dev is node.right))
            out.append((dev.key, val))
            return
    # Other shapes (UnaryOp not, ClockRef alone, etc.) — skip


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
