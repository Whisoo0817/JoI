"""M2 batch runner: SMT gate over periodic cached pairs + replay adjudication.

Same shape as run_m1, but replay comparison is limited to the encoder's
bounded window (meta.t_cmp) — beyond it the encoder made no claim.

Usage:
    python3 -m etc.smt.run_m2 [--only ...] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

from sim.catalog import load_catalog
from sim.ir_simulator import run_ir_simulation
from sim.joi_simulator import run_joi_simulation

from etc.smt.encode import TOLERANCE_MS
from etc.smt.encode2 import check_pair_m2
from etc.smt.fragment import classify_pair
from etc.smt.run_m1 import scenario_from_model

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")


def traces_match_windowed(tr_a, tr_b, t_cmp: int, tol_ms: int) -> tuple[bool, str]:
    """Ordered-index matching per (method, #args) signature within [0, t_cmp),
    with tail grace — the same semantics the M2 miter uses."""
    def sig(r):
        return (r.method, len(r.args))

    def dedup(records):
        """comparator-style: drop identical (method,args) within ±100ms."""
        out = []
        for r in records:
            if any(q.key() == r.key() and abs(q.timestamp_ms - r.timestamp_ms) <= 100
                   for q in out):
                continue
            out.append(r)
        return out

    ra = dedup([r for r in tr_a.records if r.timestamp_ms < t_cmp])
    rb = dedup([r for r in tr_b.records if r.timestamp_ms < t_cmp])
    sigs = {sig(r) for r in ra} | {sig(r) for r in rb}
    for sg in sigs:
        xs = [r for r in ra if sig(r) == sg]
        ys = [r for r in rb if sig(r) == sg]
        for i in range(max(len(xs), len(ys))):
            if i >= len(xs) or i >= len(ys):
                extra = (xs[i] if i < len(xs) else ys[i])
                if extra.timestamp_ms < t_cmp - tol_ms:
                    la = "IR" if i < len(xs) else "JoI"
                    return False, (f"{la} extra {extra.method}{extra.args}"
                                   f"@{extra.timestamp_ms} (index {i})")
                continue
            a, b = xs[i], ys[i]
            if a.args != b.args:
                return False, (f"index {i}: args {a.method}{a.args} vs "
                               f"{b.method}{b.args}")
            if abs(a.timestamp_ms - b.timestamp_ms) > tol_ms:
                return False, (f"index {i}: {a.method} t {a.timestamp_ms} vs "
                               f"{b.timestamp_ms} (tol {tol_ms})")
    return True, "match"


def replay_m2(ir: dict, joi_block: dict, model: dict, meta: dict, catalog) -> dict:
    sc = scenario_from_model(model, meta.get("alias"))
    try:
        tr_ir = run_ir_simulation(ir, sc, catalog)
        tr_joi = run_joi_simulation(joi_block, sc, catalog)
    except Exception as e:
        return {"status": "REPLAY_ERROR", "detail": f"{type(e).__name__}: {e}"}
    ok, why = traces_match_windowed(tr_ir, tr_joi, meta["t_cmp"],
                                    meta.get("tol_eff", TOLERANCE_MS))
    return {"status": "NOT_REPRODUCED" if ok else "REPRODUCED", "detail": why}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default=os.path.join(os.path.dirname(__file__),
                                                   "results", "m2.json"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    only = set(x.strip() for x in args.only.split(",") if x.strip())

    results: dict = {}
    times: list = []
    for fn in sorted(os.listdir(_CACHE)):
        if not fn.endswith(".json"):
            continue
        pid = fn[:-5]
        if only and pid not in only:
            continue
        with open(os.path.join(_CACHE, fn), encoding="utf-8") as f:
            pair = json.load(f)
        ir, joi_block = pair.get("ir") or {}, pair.get("joi_block") or {}
        try:
            cls = classify_pair(ir, joi_block)
        except Exception:
            continue
        if cls["verdict"] != "M2":
            continue

        try:
            r = check_pair_m2(ir, joi_block, catalog,
                              devices=pair.get("connected_devices"))
        except Exception as e:
            r = {"verdict": "ENCODER_ERROR", "reason": f"{type(e).__name__}: {e}"}
        if r["verdict"] == "DIVERGE":
            r["replay"] = replay_m2(ir, joi_block, r["model"], r["meta"], catalog)
        if "elapsed_s" in r:
            times.append(r["elapsed_s"])
        results[pid] = r
        if args.verbose:
            extra = ""
            if r["verdict"] == "DIVERGE":
                extra = f" replay={r['replay']['status']}"
            if r["verdict"] in ("UNSUPPORTED", "ENCODER_ERROR"):
                extra = f" ({r.get('reason','')[:90]})"
            w = r.get("meta", {}).get("w_ticks", "")
            print(f"{pid}: {r['verdict']}{extra}  [{r.get('elapsed_s', 0):.3f}s W={w}]")

    n = len(results)
    by = Counter(r["verdict"] for r in results.values())
    rep = Counter(r["replay"]["status"] for r in results.values() if r.get("replay"))
    print(f"\npairs: {n}")
    for k, v in by.most_common():
        print(f"  {k:<14} {v:>4}  ({v/max(n,1):5.1%})")
    if rep:
        print("DIVERGE replay adjudication:")
        for k, v in rep.most_common():
            print(f"  {k:<16} {v:>4}")
    if times:
        st = sorted(times)
        print(f"solve time: median {st[len(st)//2]*1000:.1f}ms  "
              f"p95 {st[int(len(st)*0.95)]*1000:.1f}ms  max {st[-1]:.2f}s")

    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    print(f"detail → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
