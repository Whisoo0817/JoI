"""Transition-boundary coverage accounting for the IR-FSM (paper §8.6, RQ3).

This is the *metric* half of the Rung-1 claim (`project-correctness-claim-2026-05-25`):
it makes "the scenario suite exercises every transition / guard-boundary / sustain
edge" a MEASURED quantity, not an assumption.

For an IR we enumerate the **target obligations** the suite is expected to cover, then
diff against what `synthesize_scenarios` actually exercises (each scenario records the
obligations it hits in `Scenario.covers`). The report lists covered vs uncovered
obligations, each uncovered one annotated with a reason — so the coverage rate and its
gaps are auditable per-IR and aggregable across the dataset.

Obligation kinds (per IR-FSM structure):
  if@<path>:then / if@<path>:else      both branch sides of every `if`
  wait@<path>:sustain                  the clean-sustain side of every `wait.for`
  wait@<path>:flap_reset               the flap/reset side of every `wait.for`
  wait@<path>:edge_<rising|falling>    the edge of every edge-triggered `wait`

(Numeric guard boundaries are exercised implicitly: an `if`'s else-scenario falsifies
a `>= c` guard to the just-below-boundary value, so :then/:else also cover the
satisfying/below-boundary partition of the guard.)
"""
from __future__ import annotations

from . import joi_parser as jp
from . import joi_simulator as joi_sim
from .catalog import load_catalog
from . import expr as _expr
from .event_synth import (
    _collect_arith_inputs,
    _collect_ifs,
    _collect_rearm_waits,
    _collect_sustained_waits,
    _iter_expr_strings,
    _read_schedule,
    _written_keys,
    synthesize_scenarios,
)
from .joi_simulator import run_joi_simulation


def enumerate_target_obligations(ir: dict) -> list[str]:
    """The obligations the coverage suite is expected to exercise for `ir`."""
    timeline = ir.get("timeline", [])
    obs: list[str] = []
    for _if, _reach, path in _collect_ifs(timeline, reach={}, path="timeline"):
        obs.append(f"if@{path}:then")
        # Only count an :else obligation when the else branch actually has actions
        # to verify. An empty else (no statements) emits nothing on the false path,
        # so there is no behavioral obligation to cover — counting it would penalize
        # coverage for a branch that, by construction, has nothing to observe.
        if (_if.get("else") or []):
            obs.append(f"if@{path}:else")
    for w, _reach, path in _collect_sustained_waits(timeline, reach={}, path="timeline"):
        obs.append(f"wait@{path}:sustain")
        obs.append(f"wait@{path}:flap_reset")
    for w, _reach, path in _collect_rearm_waits(timeline, reach={}, path="timeline"):
        obs.append(f"wait@{path}:rearm")
    # Edge-triggered waits (any nesting) — walk the timeline for edge!=none waits.
    _collect_edge_obligations(timeline, "timeline", obs)
    # Expression-boundary obligations: arithmetic / min/max/abs inputs seeded at their
    # sensor value-domain boundaries (low + high side). Live device reads -> :lo/:hi;
    # plain registers (read over time) -> :reg_lo/:reg_hi.
    live: set = set()
    regs: set = set()
    for es in _iter_expr_strings(timeline):
        try:
            _collect_arith_inputs(_expr.parse(es), live, regs)
        except Exception:
            continue
    written = _written_keys(timeline)
    live -= written
    expr_obs: list = []
    for key in sorted(live):
        expr_obs += [f"expr@{key}:lo", f"expr@{key}:hi"]
    reg_keys = {k for (v, k, _t) in _read_schedule(timeline) if v in regs and k and k not in written}
    for k in sorted(reg_keys):
        expr_obs += [f"expr@{k}:reg_lo", f"expr@{k}:reg_hi"]
    obs += list(dict.fromkeys(expr_obs))
    return obs


def _collect_edge_obligations(steps: list, path: str, obs: list) -> None:
    for i, s in enumerate(steps):
        op = s.get("op")
        sp = f"{path}[{i}]"
        if op == "wait" and s.get("edge", "none") != "none":
            obs.append(f"wait@{sp}:edge_{s['edge']}")
        elif op == "if":
            _collect_edge_obligations(s.get("then", []) or [], f"{sp}.then", obs)
            _collect_edge_obligations(s.get("else", []) or [], f"{sp}.else", obs)
        elif op == "cycle":
            _collect_edge_obligations(s.get("body", []) or [], f"{sp}.body", obs)


# Reasons an obligation may go uncovered, keyed by kind suffix.
_UNCOVERED_REASON = {
    "flap_reset": "flap-reset scenario produced no distinguishing events "
                  "(cond not synth-able, e.g. clock-only or arithmetic guard)",
    "else": "else-branch scenario produced no distinguishing events "
            "(guard not synth-able: var-comparison / quantifier / arithmetic)",
    "then": "then-branch not reached by the happy path",
    "rearm": "re-arm scenario produced no distinguishing events (cond not synth-able)",
    "lo": "expression-boundary (low side) input has no numeric value domain to seed "
          "(enum/bool/unbounded) — arithmetic boundary not exercised",
    "hi": "expression-boundary (high side) input has no numeric value domain to seed "
          "(enum/bool/unbounded) — arithmetic boundary not exercised",
    "reg": "register-fed expression boundary not exercised (no resolvable read source "
           "or non-numeric domain)",
}


def coverage_report(ir: dict) -> dict:
    """Per-IR coverage: target obligations vs what the suite actually exercises.

    Returns {total, covered, n_covered, uncovered:[(ob, reason)], pct, n_scenarios}.
    An obligation is *covered* iff some synthesized scenario lists it in `.covers`
    AND that scenario actually emits the distinguishing events for it (an else /
    flap obligation whose guard could not be synthesized contributes no events, so
    it is reported uncovered with a reason rather than silently counted)."""
    targets = enumerate_target_obligations(ir)
    scns = synthesize_scenarios(ir)
    exercised: set[str] = set()
    # An else/flap scenario only truly covers its obligation if it has events that
    # differ from the happy baseline; otherwise the guard was un-synthesizable.
    def _sig(s):
        # A scenario distinguishes itself from happy by its events AND/OR its
        # initial-world seeds (expression-boundary scenarios differ only in
        # initial_world, so events alone would miss them).
        return (frozenset((e.at_ms, e.key, e.value) for e in s.events),
                frozenset(sorted(s.initial_world.items())))
    happy_sig = None
    for s in scns:
        if s.label == "happy":
            happy_sig = _sig(s)
            break
    happy_sig = happy_sig or (frozenset(), frozenset())
    for s in scns:
        distinguishing = (s.label == "happy") or (_sig(s) != happy_sig)
        for ob in s.covers:
            if distinguishing or ob.endswith(":then") or ob.endswith(":sustain"):
                exercised.add(ob)

    covered = [o for o in targets if o in exercised]
    uncovered = []
    for o in targets:
        if o in exercised:
            continue
        suffix = o.split(":", 1)[1] if ":" in o else o
        key = "flap_reset" if suffix == "flap_reset" else (
            "else" if suffix == "else" else suffix.split("_")[0])
        uncovered.append((o, _UNCOVERED_REASON.get(key, "no scenario targets this obligation")))

    total = len(targets)
    return {
        "total": total,
        "n_covered": len(covered),
        "covered": covered,
        "uncovered": uncovered,
        "pct": (100.0 * len(covered) / total) if total else 100.0,
        "n_scenarios": len(scns),
    }


def joi_branch_coverage(joi_block: dict, ir: dict, catalog=None) -> dict | None:
    """IMPLEMENTATION-side coverage (§8.6, user-requested two-sided argument): does
    the scenario suite drive the generated JoI through every branch/loop edge of its
    OWN code? Parses the JoI, enumerates its `if` then/else branches, runs every
    suite scenario with the branch sink active, and diffs. Returns
    {total, covered, pct, uncovered} or None if the script does not parse.

    Note: 100 % JoI branch coverage does NOT imply correctness (coincidental
    correctness), but un-exercised branches are a concrete blind spot; combined with
    spec-side `coverage_report` it gives a two-sided coverage argument."""
    script = (joi_block or {}).get("script", "") or ""
    if not script.strip():
        return {"total": 0, "covered": 0, "pct": 100.0, "uncovered": []}
    try:
        stmts = jp.parse_script(script)
    except Exception:
        return None
    branches = set(joi_sim.enumerate_joi_branches(stmts))
    if not branches:
        return {"total": 0, "covered": 0, "pct": 100.0, "uncovered": []}
    cat = catalog or load_catalog()
    sink: set = set()
    joi_sim.set_branch_sink(sink)
    try:
        for scn in synthesize_scenarios(ir):
            try:
                run_joi_simulation(joi_block, scn, cat)
            except Exception:
                pass
    finally:
        joi_sim.set_branch_sink(None)
    covered = branches & sink
    return {
        "total": len(branches),
        "covered": len(covered),
        "pct": 100.0 * len(covered) / len(branches),
        "uncovered": sorted(branches - sink),
    }
