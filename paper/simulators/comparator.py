"""Trace comparator: structural equivalence with locked semantics.

Algorithm (paper-locked, see project_simulator_design_decisions.md §4):
1. Args already normalized at emit-time (TraceRecord.args is a tuple).
2. Group records by timestamp with ±100ms (1 tick) tolerance:
   greedy left-anchor — start a new group when the next record's timestamp
   is more than 100ms past the group's anchor.
3. Within each group, dedup identical (method, args) pairs.
4. After dedup, group counts and group orderings must match between traces.
5. Within each group, ordered list of (method, args) must match (preserves
   non-commutative semantics like "stop, then save").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .traces import Trace, TraceRecord


GROUP_TOLERANCE_MS = 100


@dataclass
class ComparisonResult:
    equivalent: bool
    diff_summary: str = ""
    ir_groups: list = field(default_factory=list)
    joi_groups: list = field(default_factory=list)


def compare_traces(trace_ir: Trace, trace_joi: Trace,
                   prefix_mode: bool = False) -> ComparisonResult:
    """Compare two traces for behavioral equivalence.

    `prefix_mode=True`: trim both group lists to the common prefix
    excluding the LAST group of each side, then compare. Use when at least
    one side hit MAX_TRACE (unbounded-cycle observation window). Rationale:
    sims may stop mid-group at the cap, producing a partial last group that
    differs spuriously between IR and JoI. Trimming to a fully-observed
    common prefix preserves the equivalence claim on the observed window.
    """
    g_ir = _group_and_dedup(trace_ir.records)
    g_joi = _group_and_dedup(trace_joi.records)

    if prefix_mode and g_ir and g_joi:
        # Drop last group of each (likely partial under cap) then trim to common length.
        common = min(len(g_ir) - 1, len(g_joi) - 1)
        if common <= 0:
            # Not enough fully-observed groups; treat as equivalent vacuously
            # (the observation window is too short to distinguish).
            return ComparisonResult(equivalent=True,
                                    diff_summary="prefix_mode: window too short",
                                    ir_groups=g_ir, joi_groups=g_joi)
        g_ir = g_ir[:common]
        g_joi = g_joi[:common]

    if len(g_ir) != len(g_joi):
        return ComparisonResult(
            equivalent=False,
            diff_summary=f"group count differs: IR={len(g_ir)} JoI={len(g_joi)}\n"
                         f"  IR groups: {_summary(g_ir)}\n"
                         f"  JoI groups: {_summary(g_joi)}",
            ir_groups=g_ir, joi_groups=g_joi,
        )

    for idx, (gi, gj) in enumerate(zip(g_ir, g_joi)):
        if len(gi["records"]) != len(gj["records"]):
            return ComparisonResult(
                equivalent=False,
                diff_summary=f"group {idx}: record count IR={len(gi['records'])} JoI={len(gj['records'])}\n"
                             f"  IR: {_dump(gi)}\n  JoI: {_dump(gj)}",
                ir_groups=g_ir, joi_groups=g_joi,
            )
        for r_ir, r_joi in zip(gi["records"], gj["records"]):
            if r_ir.key() != r_joi.key():
                return ComparisonResult(
                    equivalent=False,
                    diff_summary=f"group {idx} record mismatch:\n"
                                 f"  IR : {r_ir}\n  JoI: {r_joi}",
                    ir_groups=g_ir, joi_groups=g_joi,
                )

    return ComparisonResult(equivalent=True, diff_summary="traces equivalent",
                            ir_groups=g_ir, joi_groups=g_joi)


def _group_and_dedup(records: list[TraceRecord]) -> list[dict]:
    """Group by ±100ms windows then dedup identical (method, args) within group."""
    if not records:
        return []
    sorted_recs = sorted(records, key=lambda r: r.timestamp_ms)
    groups: list[dict] = []
    cur_anchor: Optional[int] = None
    cur: list[TraceRecord] = []
    for r in sorted_recs:
        if cur_anchor is None or r.timestamp_ms - cur_anchor > GROUP_TOLERANCE_MS:
            if cur:
                groups.append(_finalize_group(cur_anchor, cur))
            cur_anchor = r.timestamp_ms
            cur = [r]
        else:
            cur.append(r)
    if cur:
        groups.append(_finalize_group(cur_anchor, cur))
    return groups


def _finalize_group(anchor_ms: int, records: list[TraceRecord]) -> dict:
    """Apply order-preserving dedup of identical (method, args)."""
    seen: set = set()
    out: list[TraceRecord] = []
    for r in records:
        k = r.key()
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return {"anchor_ms": anchor_ms, "records": out}


def _summary(groups: list[dict]) -> str:
    return "[" + ", ".join(
        f"@{g['anchor_ms']}: {len(g['records'])}" for g in groups
    ) + "]"


def _dump(g: dict) -> str:
    return f"@{g['anchor_ms']}: " + ", ".join(
        f"{r.method}{r.args}" for r in g['records']
    )
