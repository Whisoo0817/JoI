"""JoI ↔ JoI relational miter (v2 stage: adapted-artifact certification).

The v1 miters compare IR ↔ JoI (translation validation). The v2 pipeline
edits *JoI against JoI*: an adapted artifact (device swap, feature drop,
NL edit) must leave every **preserved** output channel behaviorally
identical to the original — R4's projection equivalence

        P_new  ≡  π_preserve(P_old)

Both sides are encoded with the SAME JoI encoder over ONE shared input
model (same selector key → same symbolic timeline on both sides), so the
query reads: "is there an input on which a preserved channel's emissions
differ?"  UNSAT = the edit provably did not touch that channel.

`preserve` is a set of output-signature labels "method/nargs" (the unit a
role contract emits on). Channels outside it — the edited zone: dropped
features, substituted devices — are *projected away on both sides* before
comparison; their correctness is the contract checker's job, not the
miter's (3-zone model: zone ① = contracts, zone ②③ = this miter).
`preserve=None` compares everything (pure refactor check).

Engines (reusing the v1 encoders — this is the smt/ rewiring, not a
rewrite):
    one-shot  (cron '', period 0)  → path miter        (encode.SymExec)
    periodic  (equal periods > 0)  → tick-unroll miter (encode2.ITEExec)
    cron                           → not yet (needs the new-syntax work)

Obligations are installed per signature behind assumption switches
(smt.obligations), so a split check yields one verdict — one proof or one
localized counterexample — per preserved contract.
"""

from __future__ import annotations

import z3

from etc.smt.encode import (
    TOLERANCE_MS, InputModel, SymExec, Unsupported,
    collect_clock_landmarks, collect_keys_and_types, extract_scenario,
    joi_to_micro,
)
from etc.smt.encode2 import (
    ITEExec, MAX_TICKS, _scan_thresholds_and_delays,
    assert_ordered_mismatch, joi_to_micro2, run_joi_ticks,
)
from etc.smt.obligations import ObligationSet, decide


def sig_label(method: str, nargs: int) -> str:
    return f"{method}/{nargs}"


def emitted_sigs(joi_block: dict) -> set:
    """CANONICAL output signatures of a JoI block — the same method names the
    executors put on actions/slots, so these labels are valid `preserve`
    members. (Raw member names would silently match nothing and make the
    projection vacuous.) Harness helper: preserve sets are usually 'old sigs
    minus the dropped role's sigs' = sigs of the new code when the drop is
    clean."""
    from sim import expr as E
    from etc.smt.encode import MEmit, MIf

    def walk(ops, out):
        for op in ops:
            if isinstance(op, MEmit):
                _, method_c = E.canonical_key(op.service, op.method)
                out.add(sig_label(method_c, len(op.args)))
            elif isinstance(op, MIf):
                walk(op.then, out)
                walk(op.els, out)
        return out

    period = int(joi_block.get("period", 0) or 0)
    micro = joi_to_micro2(joi_block)[0] if period > 0 else joi_to_micro(joi_block)
    return walk(micro, set())


# ── one-shot (path) relational miter ─────────────────────────────────────────

def build_relational_m1(joi_old: dict, joi_new: dict, catalog: dict,
                        tolerance_ms: int = TOLERANCE_MS, preserve=None):
    m_a = joi_to_micro(joi_old)
    m_b = joi_to_micro(joi_new)

    keys, ti = collect_keys_and_types([m_a, m_b], {})
    clocks = collect_clock_landmarks([m_a, m_b])
    im = InputModel(keys, ti)

    ex_a = SymExec(im, ti, catalog, clocks, "old")
    ex_b = SymExec(im, ti, catalog, clocks, "new")
    paths_a = ex_a.run(m_a)
    paths_b = ex_b.run(m_b)

    def guard(p):
        return z3.And(*p.guard) if p.guard else z3.BoolVal(True)

    def proj(actions):
        if preserve is None:
            return actions
        return [a for a in actions
                if sig_label(a.method, len(a.args)) in preserve]

    obs = ObligationSet()
    for p in paths_a:
        for q in paths_b:
            g = z3.And(guard(p), guard(q))
            acts_a, acts_b = proj(p.actions), proj(q.actions)
            if len(acts_a) != len(acts_b):
                obs.add("shape:count", g)
                continue
            for a, b in zip(acts_a, acts_b):
                if a.method != b.method or len(a.args) != len(b.args):
                    obs.add("shape:method", g)
                    continue
                t_ok = z3.And(a.time - b.time <= tolerance_ms,
                              b.time - a.time <= tolerance_ms)
                arg_eqs = [ex_a.values_equal(x, y)
                           for x, y in zip(a.args, b.args)]
                obs.add(f"sig:{sig_label(a.method, len(a.args))}",
                        z3.And(g, z3.Not(z3.And(t_ok, *arg_eqs))))

    s = z3.Solver()
    for c in im.constraints:
        s.add(c)
    inst = obs.install(s, tag="rel")
    return s, im, ti, inst


# ── periodic (tick-unroll) relational miter ──────────────────────────────────

def build_relational_m2(joi_old: dict, joi_new: dict, catalog: dict,
                        tolerance_ms: int = TOLERANCE_MS, preserve=None):
    m_a, period_a = joi_to_micro2(joi_old)
    m_b, period_b = joi_to_micro2(joi_new)
    if period_a <= 0 or period_b <= 0:
        raise Unsupported("period 0 is the one-shot engine")
    if period_a != period_b:
        raise Unsupported(f"periods differ ({period_a} vs {period_b}) — "
                          f"period edits are contract-checked, not mitered")
    return relational_m2_from_micro(m_a, m_b, period_a, catalog,
                                    tolerance_ms, preserve)


def relational_m2_from_micro(m_a: list, m_b: list, period: int, catalog: dict,
                             tolerance_ms: int = TOLERANCE_MS, preserve=None,
                             w_cap: int = 64):
    """Mirror of encode2.build_miter_m2 with BOTH sides JoI micro. Window
    sizing, sampling-aware tolerance and phase floor follow the unroll
    engine's E-B-hardened rules verbatim, EXCEPT that the window is capped
    at `w_cap` ticks: the v1 sizing reads every `x > N` literal as a
    potential counter threshold, and v2 skeletons compare sensor values
    (co2 > 1500) and second-domain cooldowns (now-last > 1800) that would
    demand thousands of ticks. A capped window makes the verdict a
    window-bounded theorem — reported honestly in meta (`w_capped`); the
    uncapped answer for long cooldowns is relational induction, not a
    longer unroll. Micro-level entry so the v2 frontend (encode_v2
    grounding) can feed grounded skeletons/artifacts."""
    keys, ti = collect_keys_and_types([m_a, m_b], {})
    clocks = collect_clock_landmarks([m_a, m_b])
    im = InputModel(keys, ti)

    tol_eff = max(tolerance_ms, period + tolerance_ms)
    thr: set = set()
    delays: list = []
    _scan_thresholds_and_delays(m_a, thr, delays)
    _scan_thresholds_and_delays(m_b, thr, delays)
    thr_ticks = max(thr) if thr else 0
    delay_ms = sum(delays)
    w_want = max(thr_ticks + 24, -(-(delay_ms + 4 * period) // period), 24,
                 -(-(6 * tol_eff) // period) + 8)
    w_ticks = min(w_want, max(w_cap, 24, -(-(6 * tol_eff) // period) + 8))
    meta = {"w_ticks": w_ticks, "w_capped": w_ticks < w_want, "period": period}
    if w_ticks > MAX_TICKS:
        raise Unsupported(f"window {w_ticks} ticks > {MAX_TICKS}")
    w_ms = w_ticks * period
    # quiet-tail rule: uncapped windows leave thr_ticks of settle time after
    # the last input change; a capped window cannot honor a 1500-tick settle,
    # and relationally (same thresholds on both sides) it need not — keep a
    # small tail and let the mismatch queries' grace absorb the window edge
    tau_cap = max(4 * period, w_ms - 8 * period) if meta["w_capped"] \
        else max(4 * period, w_ms - (thr_ticks + 8) * period)
    t_cmp = w_ms - tolerance_ms - period
    min_phase = max(period, 100)

    ex_a = ITEExec(im, ti, catalog, clocks, "old")
    ex_b = ITEExec(im, ti, catalog, clocks, "new")
    run_joi_ticks(ex_a, m_a, period, w_ticks)
    run_joi_ticks(ex_b, m_b, period, w_ticks)

    if preserve is not None:
        ex_a.slots = [sl for sl in ex_a.slots
                      if sig_label(sl.method, len(sl.args)) in preserve]
        ex_b.slots = [sl for sl in ex_b.slots
                      if sig_label(sl.method, len(sl.args)) in preserve]

    s = z3.Solver()
    for c in im.constraints:
        s.add(c)
    for c in ex_a.constraints + ex_b.constraints:
        s.add(c)
    for key in im.taus:
        taus = im.taus[key]
        for i, tau in enumerate(taus):
            s.add(tau <= tau_cap)
            s.add(tau >= min_phase if i == 0 else tau - taus[i - 1] >= min_phase)

    # Per-channel in-window reachability, asked BEFORE the mismatch assertion
    # lands (afterwards every model is forced to violate something). An EQUIV
    # obligation on a channel no input can fire inside the capped window is a
    # vacuous proof — the certificate must say so, not count it.
    from etc.smt.encode2 import _sig
    def _active(sl):
        return z3.And(sl.guard, sl.time < t_cmp, sl.time >= 0)
    s.set("timeout", 60_000)
    reach: dict = {}
    for sig in sorted({_sig(sl) for sl in ex_a.slots + ex_b.slots}):
        acts = [_active(sl) for sl in ex_a.slots + ex_b.slots
                if _sig(sl) == sig]
        r = s.check(z3.Or(*acts))
        reach[f"{sig[0]}/{sig[1]}"] = (True if r == z3.sat else
                                       False if r == z3.unsat else None)
    s.set("timeout", 0)
    meta["reachable"] = reach

    inst = assert_ordered_mismatch(s, ex_a, ex_b, t_cmp, tol_eff)
    return s, im, ti, inst, meta


# ── entry point ──────────────────────────────────────────────────────────────

def check_relational(joi_old: dict, joi_new: dict, catalog: dict,
                     tolerance_ms: int = TOLERANCE_MS, preserve=None,
                     timeout_ms: int = 0, split: bool = True) -> dict:
    """→ {verdict, obligations?, violated?, model?, elapsed_s}.

    verdict EQUIV means: on every preserved output channel, no input makes
    the two programs' emissions differ (within tolerance) — under the same
    input model and window assumptions as the v1 gate."""
    import time
    t0 = time.perf_counter()
    cron_a = (joi_old.get("cron") or "").strip()
    cron_b = (joi_new.get("cron") or "").strip()
    per_a = int(joi_old.get("period", 0) or 0)
    per_b = int(joi_new.get("period", 0) or 0)
    try:
        if cron_a or cron_b:
            raise Unsupported("cron relational miter not yet wired")
        if per_a == 0 and per_b == 0:
            s, im, ti, inst = build_relational_m1(joi_old, joi_new, catalog,
                                                  tolerance_ms, preserve)
        else:
            s, im, ti, inst, _ = build_relational_m2(joi_old, joi_new, catalog,
                                                     tolerance_ms, preserve)
    except Unsupported as e:
        return {"verdict": "UNSUPPORTED", "reason": str(e),
                "elapsed_s": time.perf_counter() - t0}
    out = decide(s, inst, lambda m: extract_scenario(m, im, ti),
                 timeout_ms=timeout_ms, split=split,
                 timeout_verdict="TIMEOUT" if timeout_ms else "UNKNOWN")
    out["elapsed_s"] = time.perf_counter() - t0
    return out


def emitted_sigs_v2(src: str, inv, catalog: dict) -> set:
    """Canonical output signatures of a grounded v2 source."""
    from sim import expr as E
    from etc.smt.encode import MEmit, MIf
    from etc.smt.encode_v2 import to_micro2 as ground_micro

    out: set = set()

    def walk(ops):
        for op in ops:
            if isinstance(op, MEmit):
                _, method_c = E.canonical_key(op.service, op.method)
                out.add(sig_label(method_c, len(op.args)))
            elif isinstance(op, MIf):
                walk(op.then)
                walk(op.els)

    walk(ground_micro(src, inv, catalog))
    return out


def check_relational_v2(src_old: str, src_new: str, period: int, inv,
                        catalog: dict, tolerance_ms: int = TOLERANCE_MS,
                        preserve=None, timeout_ms: int = 0,
                        split: bool = True, w_cap: int = 64) -> dict:
    """v2 sources (template skeleton / adapted artifact) → grounded against
    the SAME inventory (offline devices included: the miter models programs
    as deployed; a dead device's inputs are free symbols only the old side
    reads) → periodic relational miter."""
    import time
    from etc.smt.encode_v2 import to_micro2 as ground_micro
    t0 = time.perf_counter()
    try:
        m_a = ground_micro(src_old, inv, catalog)
        m_b = ground_micro(src_new, inv, catalog)
        s, im, ti, inst_, meta = relational_m2_from_micro(
            m_a, m_b, period, catalog, tolerance_ms, preserve, w_cap=w_cap)
    except Unsupported as e:
        return {"verdict": "UNSUPPORTED", "reason": str(e),
                "elapsed_s": time.perf_counter() - t0}
    out = decide(s, inst_, lambda m: extract_scenario(m, im, ti),
                 timeout_ms=timeout_ms, split=split,
                 timeout_verdict="TIMEOUT" if timeout_ms else "UNKNOWN")
    out["elapsed_s"] = time.perf_counter() - t0
    out["meta"] = meta
    return out
