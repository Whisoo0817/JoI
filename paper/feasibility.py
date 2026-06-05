"""Structural feasibility check for the Timeline IR (grammar G membership).

`validate_ir` (timeline_ir.py) checks per-step SHAPE. This module checks the
context-sensitive STRUCTURAL rules that decide whether an IR can be lowered to
executable JoI at all. Two families:

  (A) IR-illegal structures the grammar forbids regardless of target language:
        A1. `break` outside any cycle (there is no loop to break out of)
        A2. `start_at` nested inside a branch / loop body (it may only anchor
            the whole timeline, at the top level)

  (B) Well-formed IR the target DSL cannot express:
        B1. nested cycle (a cycle inside another cycle) — JoI has no nested loop
        B2. more than one top-level cycle — JoI lowers to a single wrapper loop
            with one period; a second top-level cycle would be silently dropped

If the IR is infeasible, `check_feasibility` raises `FeasibilityError` with a
human-readable message. The pipeline catches it and terminates the row
fail-closed (no lowering attempted).
"""
from typing import Any


class FeasibilityError(ValueError):
    """Raised when a Timeline IR is structurally infeasible to deploy: it
    violates the IR grammar G or uses a structure JoI cannot express."""


def check_feasibility(ir: Any) -> None:
    """Raise FeasibilityError if `ir` is not in the deployable grammar G.

    Assumes `ir` already passed validate_ir (per-step shape is well-formed); we
    check only the context-sensitive structural rules above.
    """
    if not isinstance(ir, dict) or "error" in ir:
        return
    timeline = ir.get("timeline")
    if not isinstance(timeline, list):
        return  # shape problems are validate_ir's responsibility, not ours

    # B2 — at most one top-level cycle.
    top_cycles = [i for i, s in enumerate(timeline)
                  if isinstance(s, dict) and s.get("op") == "cycle"]
    if len(top_cycles) > 1:
        raise FeasibilityError(
            f"JoI supports a single top-level loop, but the IR has "
            f"{len(top_cycles)} top-level cycles (at timeline {top_cycles}). "
            "Two independent periodic loops cannot share one wrapper period."
        )

    _walk(timeline, cycle_depth=0, at_top=True, path="timeline")


def _walk(steps: list, cycle_depth: int, at_top: bool, path: str) -> None:
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        op = s.get("op")
        sp = f"{path}[{i}]"

        # A1 — break must be inside a cycle.
        if op == "break" and cycle_depth == 0:
            raise FeasibilityError(
                f"`break` at {sp} is outside any cycle; there is no loop to "
                "break out of. `break` may only appear inside a cycle body."
            )

        # A2 — start_at may only anchor the whole timeline at the top level.
        if op == "start_at" and not at_top:
            raise FeasibilityError(
                f"`start_at` at {sp} is nested inside a branch or loop body; "
                "it may only anchor the whole timeline at the top level."
            )

        if op == "cycle":
            # B1 — no nested loops.
            if cycle_depth >= 1:
                raise FeasibilityError(
                    f"nested cycle at {sp}: JoI has no nested-loop construct, so "
                    "a cycle may not appear inside another cycle's subtree."
                )
            _walk(s.get("body") or [], cycle_depth + 1, at_top=False, path=f"{sp}.body")

        elif op == "if":
            _walk(s.get("then") or [], cycle_depth, at_top=False, path=f"{sp}.then")
            _walk(s.get("else") or [], cycle_depth, at_top=False, path=f"{sp}.else")


# ---------------------------------------------------------------------------
# Structural class τ(IR) — computed by the same single pass over the typed
# tree that decides grammar membership (paper §5). The class records which
# grammar constructs the IR instantiates; the lowering stage routes its
# few-shot examples on this class (paper §7). The class never affects the
# verifier's accept/reject decision.
# ---------------------------------------------------------------------------

def structural_class(ir: Any) -> tuple:
    """Return the IR's structural class: the sorted tuple of grammar
    constructs the IR instantiates (e.g. ('call', 'cycle', 'cycle.until',
    'if', 'wait.edge')). Deterministic, no LLM, single tree pass."""
    feats: set[str] = set()
    if not isinstance(ir, dict):
        return ()
    timeline = ir.get("timeline")
    if not isinstance(timeline, list):
        return ()

    def walk(steps, in_cycle):
        for s in steps:
            if not isinstance(s, dict):
                continue
            op = s.get("op")
            if not op:
                continue
            feats.add(op)
            if op == "start_at":
                if s.get("cron"):
                    feats.add("start_at.cron")
            elif op == "wait":
                edge = s.get("edge")
                if edge and edge != "none":
                    feats.add("wait.edge")
                if s.get("for"):
                    feats.add("wait.for")
            elif op == "cycle":
                if s.get("until"):
                    feats.add("cycle.until")
                if s.get("count"):
                    feats.add("cycle.count")
                walk(s.get("body") or [], True)
            elif op == "if":
                if s.get("else"):
                    feats.add("if.else")
                walk(s.get("then") or [], in_cycle)
                walk(s.get("else") or [], in_cycle)
    walk(timeline, False)
    return tuple(sorted(feats))


def lowering_bucket(ir: Any) -> str:
    """Coarsest projection of the structural class used by the current
    example-routing implementation: 'cycle' if the IR instantiates the
    cycle construct at the top level, else 'noncycle'."""
    if not isinstance(ir, dict):
        return "noncycle"
    timeline = ir.get("timeline")
    if not isinstance(timeline, list):
        return "noncycle"
    for s in timeline:
        if isinstance(s, dict) and s.get("op") == "cycle":
            return "cycle"
    return "noncycle"


if __name__ == "__main__":
    # Quick self-test: 2 feasible + 4 infeasible (A1, A2, B1, B2).
    _START = {"op": "start_at", "anchor": "boot"}
    _CALL = {"op": "call", "target": "Light.On", "args": {}}
    _CYC = lambda body: {"op": "cycle", "period": "10 MIN", "body": body}

    cases = {
        "ok_flat":        {"timeline": [_START, _CALL]},
        "ok_one_cycle":   {"timeline": [_START, _CYC([_CALL, {"op": "break"}])]},
        "A1_break_top":   {"timeline": [_START, {"op": "break"}]},
        "A2_nested_start":{"timeline": [_START, _CYC([{"op": "start_at", "anchor": "boot"}])]},
        "B1_nested_cycle":{"timeline": [_START, _CYC([_CYC([_CALL])])]},
        "B2_two_cycles":  {"timeline": [_START, _CYC([_CALL]), _CYC([_CALL])]},
    }
    for name, ir in cases.items():
        try:
            check_feasibility(ir)
            print(f"  FEASIBLE   {name}")
        except FeasibilityError as e:
            print(f"  INFEASIBLE {name}: {e}")
