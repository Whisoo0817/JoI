"""E-B — mutation replay: the SMT gate as its own test suite.

Seeds = cached pairs the SMT gate certified EQUIV (M1/M2/M3 results).
For each seed, apply the v1 mutation operators to the JoI script; filter
equivalent mutants with the v1 sim-signature filter (ground truth is the
simulator, independent of the gate). Every remaining GENUINE mutant must
NOT come back EQUIV from the gate:

    DIVERGE                    → caught (the expected outcome)
    UNSUPPORTED / parse error  → fail-closed (rejected, counted separately)
    TIMEOUT                    → unresolved (separately reported)
    EQUIV                      → candidate encoder miss → adjudicated with a
                                 tolerance-aware sim comparison: if IR-sim vs
                                 mutant-sim actually match within the gate's
                                 tol_eff on every synthesized scenario, the
                                 mutant is φ-equivalent (the exact-timestamp
                                 v1 filter is stricter than φ) — otherwise
                                 it is a real ENCODER_MISS.

Usage:
    python3 -m smt.run_eb [--classes M1,M2,M3] [--limit N] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

from sim.catalog import load_catalog
from sim.event_synth import synthesize_scenarios
from sim.ir_simulator import run_ir_simulation
from sim.joi_simulator import run_joi_simulation
from sim.run_mutation_test import OPERATORS, _trace_signature

from smt.accel import check_pair_accel
from smt.encode import check_pair
from smt.encode2 import check_pair_m2
from smt.encode3 import check_pair_m3
from smt.fragment import classify_pair
from smt.run_m2 import traces_match_windowed

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")
_RESULTS = os.path.join(os.path.dirname(__file__), "results")
SITE_CAP = int(os.environ.get("MUT_SITE_CAP", "6"))
TIMEOUT_MS = 60_000
ACCEL_TIMEOUT_MS = 300_000   # fallback only fires on large-W pairs = accel's regime


def load_seed_verdicts() -> dict:
    out = {}
    for fn, cls in (("m1.json", "M1"), ("m2.json", "M2"), ("m3.json", "M3")):
        p = os.path.join(_RESULTS, fn)
        if os.path.exists(p):
            for pid, r in json.load(open(p, encoding="utf-8")).items():
                out[pid] = (cls, r.get("verdict"))
    return out


def gate_verdict(cls: str, ir: dict, jb: dict, catalog, devices=None) -> dict:
    if cls == "M1":
        return check_pair(ir, jb, catalog, devices=devices)
    if cls == "M2":
        r = check_pair_m2(ir, jb, catalog, timeout_ms=TIMEOUT_MS, devices=devices)
        if r["verdict"] == "TIMEOUT":
            # unroll timed out ⟹ W is large ⟹ the accelerated engine's
            # regime; NOT_ACCELERABLE/TIMEOUT there keeps the TIMEOUT verdict
            ra = check_pair_accel(ir, jb, catalog,
                                  timeout_ms=ACCEL_TIMEOUT_MS, devices=devices)
            if ra["verdict"] in ("EQUIV", "DIVERGE"):
                ra["engine"] = "accel-fallback"
                return ra
        return r
    return check_pair_m3(ir, jb, catalog, timeout_ms=TIMEOUT_MS, devices=devices)


def adjudicate_miss(ir: dict, mut: dict, catalog, tol_eff: int, t_cmp: int) -> str:
    """SMT said EQUIV on a sim-genuine mutant — φ-equivalent or real miss?"""
    try:
        scns = synthesize_scenarios(ir)
    except Exception:
        return "NO_SCENARIO"
    for sc in scns:
        try:
            tr_ir = run_ir_simulation(ir, sc, catalog)
            tr_mut = run_joi_simulation(mut, sc, catalog)
        except Exception:
            return "SIM_ERROR"
        ok, why = traces_match_windowed(tr_ir, tr_mut, t_cmp, tol_eff)
        if not ok:
            return f"ENCODER_MISS ({why[:80]})"
    return "WITHIN_TOLERANCE"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classes", default="M1,M2,M3")
    ap.add_argument("--limit", type=int, default=0, help="cap seeds (smoke)")
    ap.add_argument("--json", default=os.path.join(_RESULTS, "eb.json"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    classes = {c.strip() for c in args.classes.split(",") if c.strip()}

    catalog = load_catalog()
    seeds = load_seed_verdicts()

    gen = Counter(); equiv_f = Counter(); genuine = Counter()
    caught = Counter(); fail_closed = Counter(); timeout = Counter()
    within_tol = Counter()
    misses = []
    timeouts = []
    n_seeds = 0

    for fn in sorted(os.listdir(_CACHE)):
        if not fn.endswith(".json"):
            continue
        pid = fn[:-5]
        cls_verdict = seeds.get(pid)
        if not cls_verdict or cls_verdict[1] != "EQUIV" or cls_verdict[0] not in classes:
            continue
        with open(os.path.join(_CACHE, fn), encoding="utf-8") as f:
            pair = json.load(f)
        ir, jb = pair.get("ir") or {}, pair.get("joi_block") or {}
        cls = cls_verdict[0]
        if args.limit and n_seeds >= args.limit:
            break
        n_seeds += 1

        try:
            seed_sig = _trace_signature(jb, ir, catalog)
        except Exception:
            seed_sig = None

        # tolerance parameters mirror the gate's per-class semantics
        period = int(jb.get("period", 0) or 0)
        tol_eff = max(1000, period + 1000)
        t_cmp = 10 ** 12   # adjudication over the sims' full run

        for op_name, op in OPERATORS.items():
            seen = set()
            try:
                variants = op(jb.get("script", "") or "")[:SITE_CAP]
            except Exception:
                continue
            for new_script, desc in variants:
                if new_script == jb.get("script") or new_script in seen:
                    continue
                seen.add(new_script)
                gen[op_name] += 1
                mut = dict(jb)
                mut["script"] = new_script

                try:
                    mut_sig = _trace_signature(mut, ir, catalog)
                except Exception:
                    mut_sig = None
                if mut_sig is not None and seed_sig is not None and mut_sig == seed_sig:
                    equiv_f[op_name] += 1
                    continue
                genuine[op_name] += 1

                try:
                    r = gate_verdict(cls, ir, mut, catalog,
                                     devices=pair.get("connected_devices"))
                except Exception as e:
                    r = {"verdict": "GATE_ERROR", "reason": f"{type(e).__name__}: {e}"}
                v = r["verdict"]
                if v == "DIVERGE":
                    caught[op_name] += 1
                elif v in ("UNSUPPORTED", "GATE_ERROR"):
                    fail_closed[op_name] += 1
                elif v == "TIMEOUT":
                    timeout[op_name] += 1
                    timeouts.append({"seed": pid, "cls": cls, "op": op_name,
                                     "mutation": desc})
                elif v == "EQUIV":
                    adj = adjudicate_miss(ir, mut, catalog, tol_eff, t_cmp)
                    if adj == "WITHIN_TOLERANCE":
                        within_tol[op_name] += 1
                    else:
                        misses.append({"seed": pid, "cls": cls, "op": op_name,
                                       "mutation": desc, "adj": adj,
                                       "script": new_script})
                        if args.verbose:
                            print(f"  !! MISS {pid} {op_name}: {desc} — {adj}")
                else:
                    fail_closed[op_name] += 1
        if args.verbose:
            print(f"{pid} ({cls}): done")

    # ── report ──
    print("\n" + "=" * 78)
    print(f"seeds (SMT-EQUIV): {n_seeds}")
    print(f"{'operator':<14} {'gen':>5} {'equiv':>6} {'genuine':>8} "
          f"{'DIVERGE':>8} {'φ-tol':>6} {'closed':>7} {'t/o':>4} {'miss':>5}")
    tg = tgen = tc = tw = tf = tt = 0
    miss_by_op = Counter(m["op"] for m in misses)
    for op_name in OPERATORS:
        g, e, gu = gen[op_name], equiv_f[op_name], genuine[op_name]
        c, w, f_, t = caught[op_name], within_tol[op_name], fail_closed[op_name], timeout[op_name]
        m = miss_by_op[op_name]
        tg += g; tgen += gu; tc += c; tw += w; tf += f_; tt += t
        print(f"{op_name:<14} {g:>5} {e:>6} {gu:>8} {c:>8} {w:>6} {f_:>7} {t:>4} {m:>5}")
    n_miss = len(misses)
    print("-" * 78)
    print(f"{'TOTAL':<14} {tg:>5} {'':>6} {tgen:>8} {tc:>8} {tw:>6} {tf:>7} {tt:>4} {n_miss:>5}")
    denom = tgen - tw   # φ-tolerance-equivalent mutants leave the denominator
    if denom > 0:
        print(f"\nkill rate (DIVERGE + fail-closed over φ-genuine): "
              f"{(tc + tf)}/{denom} = {(tc + tf)/denom:.1%}   "
              f"(timeouts {tt}, encoder misses {n_miss})")

    os.makedirs(_RESULTS, exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump({"seeds": n_seeds,
                   "per_op": {op: {"gen": gen[op], "equiv": equiv_f[op],
                                   "genuine": genuine[op], "caught": caught[op],
                                   "within_tol": within_tol[op],
                                   "fail_closed": fail_closed[op],
                                   "timeout": timeout[op],
                                   "miss": miss_by_op[op]} for op in OPERATORS},
                   "misses": misses, "timeouts": timeouts},
                  f, ensure_ascii=False, indent=1)
    print(f"detail → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
