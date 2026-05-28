"""L2 obligation trace checker (paper §6.4 V3).

Runs both simulators on a scenario and attributes any IR/JoI trace
divergence back to specific obligations in the IR-FSM. The output is a
diagnosis list — what *kind* of obligation failed and at which IR path —
that R1 (retry harness) can convert into targeted retry messages.

Algorithm (MVP):
1. Synthesize a scenario from the IR (using existing event_synth).
2. Run IR sim → ground-truth trace T_ir.
3. Run JoI sim → candidate trace T_joi.
4. Group + dedup both with comparator semantics (±100ms).
5. Flatten the IR-FSM into an ordered list of `CallObligation`s (DFS).
6. For each IR group: pick the matching obligation by target (nth call →
   nth CallObligation that matches that target). Then check whether the
   corresponding JoI group satisfies it.
7. Any group present in IR but not in JoI → `missing_call` violation
   attributed to the obligation's IR path.
   Any group present in JoI but not in IR → `extra_call` violation
   attributed to nearest preceding IR obligation.
   Any group whose args differ → `arg_mismatch`.

This is deliberately a coarse first pass; refining attribution (e.g.,
through obligation-by-obligation state matching with the FSM's `after`
DAG) is a future improvement. It already provides enough granularity for
the retry harness because the IR path uniquely identifies the failing op.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from paper.simulators.catalog import load_catalog
from paper.simulators.comparator import _group_and_dedup
from paper.simulators.event_synth import synthesize_scenarios
from paper.simulators.ir_simulator import MAX_TRACE, run_ir_simulation
from paper.simulators.joi_simulator import run_joi_simulation

from paper.verifier.ir_fsm import (
    CallObligation,
    CycleObligation,
    IfObligation,
    IRFSM,
    Obligation,
    derive_fsm,
)


@dataclass
class L2Violation:
    kind: str          # missing_call | extra_call | arg_mismatch | trace_empty | timing_drift
    ir_path: str       # IR-FSM path that owns the violated obligation
    target: str        # service.method (best-effort)
    expected: object = None
    observed: object = None
    detail: str = ""
    # Number of trace groups that exhibited this violation. For acyclic IR
    # this is always 1; for cycles a single obligation may be violated once
    # per iteration. We collapse those into a single L2Violation with
    # `occurrences=N` so the obligation-attributed report stays one entry
    # per (kind, ir_path, target) instead of exploding N×.
    occurrences: int = 1


@dataclass
class L2Report:
    equivalent: bool
    violations: list[L2Violation]
    ir_group_count: int
    joi_group_count: int


def check(
    ir: dict,
    joi_block: dict,
    catalog: Optional[dict] = None,
    scenario_index: Optional[int] = None,
) -> L2Report:
    """Run both sims and produce an obligation-attributed diff.

    `synthesize_scenarios(ir)` now returns a COVERAGE SUITE (multiple scenarios
    that exercise then/else branches, guard boundaries, and sustain/reset edges
    of the IR-FSM). We run every scenario and the JoI fails equivalence if it
    diverges on ANY of them — coverage of the spec's transitions, not just the
    happy path. `scenario_index` (legacy) restricts to a single scenario.
    """
    cat = catalog or load_catalog()
    scenarios = synthesize_scenarios(ir)
    if not scenarios:
        return L2Report(equivalent=True, violations=[],
                        ir_group_count=0, joi_group_count=0)
    if scenario_index is not None:
        i = scenario_index if scenario_index < len(scenarios) else 0
        scenarios = [scenarios[i]]

    fsm = derive_fsm(ir)
    call_obs = _flatten_calls(fsm.top)

    from collections import OrderedDict
    merged: "OrderedDict[tuple, L2Violation]" = OrderedDict()
    max_ir_groups = max_joi_groups = 0
    for scn in scenarios:
        acc, n_ir, n_joi = _check_one(ir, joi_block, scn, cat, call_obs)
        max_ir_groups = max(max_ir_groups, n_ir)
        max_joi_groups = max(max_joi_groups, n_joi)
        for key, v in acc.items():
            existing = merged.get(key)
            if existing is None:
                merged[key] = v
            else:
                existing.occurrences += v.occurrences
    return L2Report(
        equivalent=not merged,
        violations=list(merged.values()),
        ir_group_count=max_ir_groups,
        joi_group_count=max_joi_groups,
    )


def _check_one(ir: dict, joi_block: dict, scn, cat,
               call_obs: list["CallObligation"]):
    """Compare IR-sim and JoI-sim traces on ONE scenario. Returns
    (acc, n_ir_groups, n_joi_groups) where acc is an OrderedDict keyed by
    (kind, ir_path, target)."""
    from collections import OrderedDict
    t_ir = run_ir_simulation(ir, scn, cat, debug=False)
    t_joi = run_joi_simulation(joi_block, scn, cat, debug=False)

    g_ir = _group_and_dedup(t_ir.records)
    g_joi = _group_and_dedup(t_joi.records)

    # Trace-cap truncation guard. A non-terminating cycle (until=null) hits the
    # MAX_TRACE cap; the cap can fall MID-iteration in one sim (e.g. after `on`
    # but before `setMode`) and at the boundary in the other, leaving the final
    # group a truncation artifact rather than a real divergence. We drop the
    # shared boundary group from both ONLY when the signature is exactly that
    # artifact: a trace is capped, BOTH sides are substantial, and their group
    # counts are within one (i.e. they otherwise track each other). This must
    # NOT fire when one side is empty/short — that is a real trace_empty /
    # missing-call divergence, not a truncation edge.
    if (t_ir.group_count >= MAX_TRACE or t_joi.group_count >= MAX_TRACE) \
            and len(g_ir) > 1 and len(g_joi) > 1 \
            and abs(len(g_ir) - len(g_joi)) <= 1:
        k = min(len(g_ir), len(g_joi)) - 1
        g_ir, g_joi = g_ir[:k], g_joi[:k]

    acc: "OrderedDict[tuple, L2Violation]" = OrderedDict()

    if g_ir and not g_joi:
        acc[("trace_empty", "timeline", "(any)")] = L2Violation(
            kind="trace_empty",
            ir_path="timeline",
            target="(any)",
            detail="IR emits but JoI emits nothing — script likely guarded out or unreachable",
        )
        return acc, len(g_ir), 0

    # Walk groups in order. The IR-FSM's flattened call list provides one
    # obligation per "expected emit" in DFS order; for cycles each obligation
    # may correspond to N realized records — we still attribute by target.
    obs_by_target: dict[str, list[CallObligation]] = {}
    for ob in call_obs:
        obs_by_target.setdefault(_target_norm(ob.target), []).append(ob)

    def _record(v: L2Violation) -> None:
        key = (v.kind, v.ir_path, v.target)
        existing = acc.get(key)
        if existing is None:
            acc[key] = v
        else:
            existing.occurrences += 1

    # Timing-drift tolerance: groups whose representative timestamps differ
    # by more than max(500ms, 10% of the IR-side expected timestamp) are flagged
    # as timing_drift. The 500ms floor covers natural tick-grid alignment slack
    # between the two simulators; the 10% relative band keeps long durations
    # tolerant (e.g. 1-hour cron drift of a few seconds is normal) while still
    # catching tick-math mistakes that scale a duration by 10×.
    _DRIFT_ABS_MS = 500
    _DRIFT_REL = 0.10

    n = max(len(g_ir), len(g_joi))
    for i in range(n):
        ir_grp = g_ir[i]["records"] if i < len(g_ir) else []
        joi_grp = g_joi[i]["records"] if i < len(g_joi) else []

        ir_keys = sorted((r.method, r.args) for r in ir_grp)
        joi_keys = sorted((r.method, r.args) for r in joi_grp)
        if ir_keys == joi_keys:
            # Same method/args set — still check temporal alignment. Group
            # representative timestamps come from the earliest record in each
            # group (groups are ±100ms wide so any record's t is within slack).
            if ir_grp and joi_grp:
                ir_t = min(r.timestamp_ms for r in ir_grp)
                joi_t = min(r.timestamp_ms for r in joi_grp)
                tol = max(_DRIFT_ABS_MS, int(ir_t * _DRIFT_REL))
                if abs(ir_t - joi_t) > tol:
                    m = ir_keys[0][0]
                    ob = _attribute_call(m, obs_by_target)
                    _record(L2Violation(
                        kind="timing_drift",
                        ir_path=ob.path if ob else "timeline",
                        target=m,
                        expected={"t_ms": ir_t},
                        observed={"t_ms": joi_t},
                        detail=(f"group #{i}: IR fired at {ir_t}ms but JoI fired at "
                                f"{joi_t}ms (delta={joi_t - ir_t}ms; tolerance ±{tol}ms)"),
                    ))
            continue

        # Categorize by method name first; only methods present on EXACTLY
        # one side become missing/extra. Methods on both sides with differing
        # args become a single `arg_mismatch` — previously this same scenario
        # emitted three violations (missing + extra + arg_mismatch) because
        # set-difference on (method, args) tuples treated them as disjoint.
        # The triple-emit confuses the retry LLM ("should I add a call or
        # remove one?") and tends to make it delete the args entirely.
        ir_by_method = {k[0]: k[1] for k in ir_keys}
        joi_by_method = {k[0]: k[1] for k in joi_keys}
        ir_only = set(ir_by_method) - set(joi_by_method)
        joi_only = set(joi_by_method) - set(ir_by_method)
        both = set(ir_by_method) & set(joi_by_method)

        for m in sorted(ir_only):
            ob = _attribute_call(m, obs_by_target)
            _record(L2Violation(
                kind="missing_call",
                ir_path=ob.path if ob else "timeline",
                target=m,
                expected={"method": m, "args": list(ir_by_method[m])},
                detail=f"first seen at group #{i}: IR emitted but JoI did not",
            ))

        for m in sorted(joi_only):
            ob = _attribute_call(m, obs_by_target)
            _record(L2Violation(
                kind="extra_call",
                ir_path=ob.path if ob else "timeline",
                target=m,
                observed={"method": m, "args": list(joi_by_method[m])},
                detail=f"first seen at group #{i}: JoI emitted but IR did not",
            ))

        for m in sorted(both):
            if ir_by_method[m] != joi_by_method[m]:
                ob = _attribute_call(m, obs_by_target)
                _record(L2Violation(
                    kind="arg_mismatch",
                    ir_path=ob.path if ob else "timeline",
                    target=m,
                    expected=list(ir_by_method[m]),
                    observed=list(joi_by_method[m]),
                    detail=f"first seen at group #{i}: args differ for {m}",
                ))

    return acc, len(g_ir), len(g_joi)


# ── Internals ───────────────────────────────────────────────────────────────

def _flatten_calls(items: list[Obligation]) -> list[CallObligation]:
    out: list[CallObligation] = []
    for ob in items:
        if isinstance(ob, CallObligation):
            out.append(ob)
        elif isinstance(ob, CycleObligation):
            out.extend(_flatten_calls(ob.body))
        elif isinstance(ob, IfObligation):
            out.extend(_flatten_calls(ob.then_body))
            out.extend(_flatten_calls(ob.else_body))
    return out


def _target_norm(target: str) -> str:
    """Normalize an IR target like `Switch.On` to a comparison key matching
    trace records. Trace records canonicalize method names to lowercase
    (see expr.canonical_name), so we lowercase for symmetry.
    """
    m = target.split(".", 1)[1] if "." in target else target
    return m.lower()


def _attribute_call(method: str, obs_by_target: dict[str, list[CallObligation]]
                    ) -> Optional[CallObligation]:
    bucket = obs_by_target.get(method.lower())
    if bucket:
        return bucket[0]
    return None
