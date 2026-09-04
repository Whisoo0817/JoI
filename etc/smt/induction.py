"""Relational tick induction — unbounded-time preservation certificates.

The bounded relational miter proves "preserved channels equal within a
w_cap-tick window", which a 30-minute cooldown outlives. The induction closes
time entirely, the M2.6 tick-induction relationalized:

    base   run tick 0 of BOTH programs (init `:=` included) on the same
           inputs: preserved emissions equal, shared variables equal after.
    step   assume an ARBITRARY tick k>=1: shared variables hold the same
           (symbolic) values on both sides, the tick's inputs are the same
           symbols, t = k*period is symbolic. Execute ONE tick of both.
           Prove: preserved emissions this tick equal, and shared variables
           equal again at the end (the invariant survives).

Both UNSAT  ⇒  by induction the channels agree at EVERY tick — no window.

Soundness/limits (stated, not hidden):
  * the step over-approximates: the assumed state need not be reachable, so
    SAT may be spurious — the caller falls back to the bounded verdict
    (fail-closed, never a wrong certificate);
  * the invariant is "ALL variables occurring in both programs are equal".
    An edit that legitimately desynchronizes a shared variable (param
    changes feeding it) breaks the step — again: fall back to bounded;
  * device/GV read-back feedback is absent by the input model (GV = free
    input, sensors are inputs), so program variables ARE the whole state.
"""

from __future__ import annotations

import time as _time
from typing import Dict, Optional, Set

import z3

from etc.smt.encode import (HORIZON_MS, InputModel, MAssign, MEmit, MIf,
                        TOLERANCE_MS, Unsupported, collect_keys_and_types)
from etc.smt.encode2 import ITEExec, _exec_tick, _sig
from etc.smt.obligations import ObligationSet, decide


# ── variable inventory ───────────────────────────────────────────────────────

def _vars_of(ops, out: Dict[str, str], ti=None) -> Dict[str, str]:
    """var -> crude sort ('bool' | 'num'), first assignment wins."""
    from sim import expr as E
    for op in ops:
        if isinstance(op, MAssign) and op.var not in out:
            rhs = op.rhs
            if isinstance(rhs, E.Lit) and isinstance(rhs.value, bool):
                out[op.var] = "bool"
            elif isinstance(rhs, E.DeviceRef) and ti is not None \
                    and ti.kind(rhs.key) == "bool":
                out[op.var] = "bool"
            else:
                out[op.var] = "num"
        elif isinstance(op, MEmit) and op.bind and op.bind not in out:
            out[op.bind] = "num"
        elif isinstance(op, MIf):
            _vars_of(op.then, out, ti)
            _vars_of(op.els, out, ti)
    return out


def _seed(name: str, sort: str, side: str):
    return z3.Bool(f"stv_{name}_{side}") if sort == "bool" \
        else z3.Real(f"stv_{name}_{side}")


# ── one-tick emission comparison ─────────────────────────────────────────────

def _tick_obligations(ex_a: ITEExec, ex_b: ITEExec, preserve,
                      tol_ms: int) -> ObligationSet:
    """Same-tick pairing: unedited surviving code is textually identical on
    both sides, so the i-th emission of a signature pairs with the i-th."""
    obs = ObligationSet()
    def keep(sl):
        return preserve is None or f"{sl.method}/{len(sl.args)}" in preserve
    sigs = sorted({_sig(sl) for sl in ex_a.slots + ex_b.slots
                   if keep(sl)})
    for sig in sigs:
        label = f"{sig[0]}/{sig[1]}"
        xs = [sl for sl in ex_a.slots if _sig(sl) == sig]
        ys = [sl for sl in ex_b.slots if _sig(sl) == sig]
        cnt_a = z3.Sum([z3.If(sl.guard, 1, 0) for sl in xs]) if xs else z3.IntVal(0)
        cnt_b = z3.Sum([z3.If(sl.guard, 1, 0) for sl in ys]) if ys else z3.IntVal(0)
        obs.add(f"count:{label}", cnt_a != cnt_b)
        for a, b in zip(xs, ys):
            args_eq = [ex_a.values_equal(x, y) for x, y in zip(a.args, b.args)]
            t_ok = z3.And(a.time - b.time <= tol_ms, b.time - a.time <= tol_ms)
            obs.add(f"align:{label}",
                    z3.And(a.guard, b.guard, z3.Not(z3.And(t_ok, *args_eq))))
            obs.add(f"align:{label}", a.guard != b.guard)
    return obs


# ── the two queries ──────────────────────────────────────────────────────────

def _run_tick(micro, im, ti, catalog, tag, k_is_zero, t_expr, seed_env=None):
    ex = ITEExec(im, ti, catalog, [], tag)
    if seed_env:
        ex.env.update(seed_env)
    ex.time = t_expr
    ex.live = z3.BoolVal(True)
    ex.break_hit = z3.BoolVal(False)
    _exec_tick(ex, micro, z3.BoolVal(True), 0 if k_is_zero else 1, z3.IntVal(0))
    return ex


def check_inductive(m_a: list, m_b: list, period: int, catalog: dict,
                    preserve=None, tolerance_ms: int = TOLERANCE_MS,
                    timeout_ms: int = 120_000) -> dict:
    """→ {verdict: INDUCTIVE_EQUIV | NOT_INDUCTIVE | UNSUPPORTED,
         obligations, invariant, elapsed_s}. NOT_INDUCTIVE is not a defect
    verdict — it means "fall back to the bounded window"."""
    t0 = _time.perf_counter()
    keys, ti = collect_keys_and_types([m_a, m_b], {})
    sorts_a = _vars_of(m_a, {}, ti)
    sorts_b = _vars_of(m_b, {}, ti)
    shared: Set[str] = set(sorts_a) & set(sorts_b)

    out = {"shared_vars": sorted(shared)}
    per: dict = {}
    inv_ok = True

    for phase in ("base", "step"):
        im = InputModel(keys, ti)
        if phase == "base":
            t_expr = z3.IntVal(0)
            seed_a = seed_b = None
        else:
            k = z3.Int("tick_k")
            t_expr = k * period
            seed_shared = {v: _seed(v, sorts_a[v], "s") for v in shared}
            seed_a = dict(seed_shared)
            seed_a.update({v: _seed(v, sorts_a[v], "a")
                           for v in sorts_a if v not in shared})
            seed_b = dict(seed_shared)
            seed_b.update({v: _seed(v, sorts_b[v], "b")
                           for v in sorts_b if v not in shared})
        try:
            ex_a = _run_tick(m_a, im, ti, catalog, f"old{phase}",
                             phase == "base", t_expr, seed_a)
            ex_b = _run_tick(m_b, im, ti, catalog, f"new{phase}",
                             phase == "base", t_expr, seed_b)
        except Unsupported as e:
            return {"verdict": "UNSUPPORTED", "reason": str(e),
                    "elapsed_s": _time.perf_counter() - t0}

        s = z3.Solver()
        s.set("timeout", timeout_ms)
        for c in im.constraints + ex_a.constraints + ex_b.constraints:
            s.add(c)
        if phase == "step":
            s.add(k >= 1)
            s.add(t_expr <= HORIZON_MS)

        inst = _tick_obligations(ex_a, ex_b, preserve, tolerance_ms).install(
            s, tag=f"ind_{phase}")
        for lbl, b in inst.switches.items():
            r = s.check(b)
            v = ("EQUIV" if r == z3.unsat else
                 "SAT" if r == z3.sat else "TIMEOUT")
            prev = per.get(lbl)
            per[lbl] = v if prev in (None, "EQUIV") else prev

        # invariant: shared vars equal after the tick
        neq = []
        for v in sorted(shared):
            va, vb = ex_a.env.get(v), ex_b.env.get(v)
            if va is None or vb is None:
                continue
            try:
                neq.append(z3.Not(ex_a.values_equal(va, vb)))
            except Exception:
                inv_ok = False
        if neq:
            r = s.check(z3.Or(*neq))
            if r != z3.unsat:
                inv_ok = False

    all_equiv = per and all(v == "EQUIV" for v in per.values())
    out.update({
        "verdict": "INDUCTIVE_EQUIV" if (all_equiv and inv_ok) else "NOT_INDUCTIVE",
        "obligations": per, "invariant": "holds" if inv_ok else "breaks",
        "elapsed_s": round(_time.perf_counter() - t0, 2),
    })
    return out


def check_inductive_v2(src_old: str, src_new: str, period: int, inv, catalog,
                       preserve=None, timeout_ms: int = 120_000) -> dict:
    from etc.smt.encode_v2 import to_micro2
    try:
        m_a = to_micro2(src_old, inv, catalog)
        m_b = to_micro2(src_new, inv, catalog)
    except Unsupported as e:
        return {"verdict": "UNSUPPORTED", "reason": str(e), "elapsed_s": 0.0}
    return check_inductive(m_a, m_b, period, catalog, preserve,
                           timeout_ms=timeout_ms)
