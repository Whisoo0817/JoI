"""Normative cross-stage constants for the confirmed Timeline -> JoI contract.

This module intentionally contains only rules that lowering and validation must
share.  Dataset-specific repairs do not belong here.
"""

from __future__ import annotations

from timeline_ir.timeline_ir import parse_duration_to_ms


EDGE_TRIGGER_DEFAULT_PERIOD = "1 SEC"
EDGE_TRIGGER_DEFAULT_PERIOD_MS = 1000


def has_rearming_edge(cycle: dict) -> bool:
    """Return whether a cycle contains a direct re-arming edge wait."""
    return any(
        isinstance(step, dict)
        and step.get("op") == "wait"
        and step.get("edge") in ("rising", "falling")
        for step in (cycle.get("body") or [])
    )


def cycle_period_ms(cycle: dict) -> int | None:
    """Resolve a cycle period without overriding an explicitly confirmed value.

    Confirmed IR is expected to carry ``cycle.period``.  The 1-second value is
    only a compatibility default for an omitted period on a re-arming edge.
    """
    period = cycle.get("period")
    if isinstance(period, str):
        return parse_duration_to_ms(period)
    if period is None and has_rearming_edge(cycle):
        return EDGE_TRIGGER_DEFAULT_PERIOD_MS
    return None
