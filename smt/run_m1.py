"""M1 batch runner: SMT gate over the one-shot cached pairs + replay adjudication.

For every cached pair classified M1 (one-shot, linear):
    1. check_pair → EQUIV / DIVERGE / UNSUPPORTED (+ solve time)
    2. DIVERGE → decode the model into a Scenario, replay through BOTH
       simulators, and report whether the divergence reproduces
       (reproduced = genuine counterexample; not = encoder false positive).

Usage:
    python3 -m smt.run_m1 [--only C01_001,...] [--json smt/results/m1.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

from sim.catalog import load_catalog
from sim.scenario import Scenario
from sim.ir_simulator import run_ir_simulation
from sim.joi_simulator import run_joi_simulation

from smt.encode import check_pair, TOLERANCE_MS
from smt.fragment import classify_pair

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")


def scenario_from_model(model: dict, alias: dict | None = None) -> Scenario:
    sc = Scenario()
    seed = dict(model)
    # device-grounded unification: mirror each unified key's timeline onto
    # the pre-unification source keys (same physical device, so the sims —
    # which still read heuristic keys — see the same values)
    for src_k, dst_k in (alias or {}).items():
        if dst_k in model and src_k not in seed:
            seed[src_k] = model[dst_k]
    for key, spec in seed.items():
        sc.initial_world[key] = spec["initial"]
        for (t, v) in spec["events"]:
            sc.add(int(t), key, v)
    return sc


def traces_match(tr_a, tr_b, tol_ms: int = TOLERANCE_MS) -> tuple[bool, str]:
    """Index-wise ordered match on (method, args) with time tolerance."""
    ra, rb = tr_a.records, tr_b.records
    if len(ra) != len(rb):
        return False, f"record count IR={len(ra)} JoI={len(rb)}"
    for i, (a, b) in enumerate(zip(ra, rb)):
        if a.key() != b.key():
            return False, f"record {i}: {a.method}{a.args} vs {b.method}{b.args}"
        if abs(a.timestamp_ms - b.timestamp_ms) > tol_ms:
            return False, f"record {i}: t {a.timestamp_ms} vs {b.timestamp_ms}"
    return True, "match"


def replay(ir: dict, joi_block: dict, model: dict, catalog, alias=None) -> dict:
    sc = scenario_from_model(model, alias)
    try:
        tr_ir = run_ir_simulation(ir, sc, catalog)
        tr_joi = run_joi_simulation(joi_block, sc, catalog)
    except Exception as e:
        return {"status": "REPLAY_ERROR", "detail": f"{type(e).__name__}: {e}"}
    ok, why = traces_match(tr_ir, tr_joi)
    return {
        "status": "NOT_REPRODUCED" if ok else "REPRODUCED",
        "detail": why,
        "trace_ir": tr_ir.to_list(),
        "trace_joi": tr_joi.to_list(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default=os.path.join(os.path.dirname(__file__),
                                                   "results", "m1.json"))
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
        if cls["verdict"] != "M1":
            continue

        devs = pair.get("connected_devices")
        try:
            r = check_pair(ir, joi_block, catalog, devices=devs)
        except Exception as e:
            r = {"verdict": "ENCODER_ERROR", "reason": f"{type(e).__name__}: {e}"}
        if r["verdict"] == "DIVERGE":
            r["replay"] = replay(ir, joi_block, r["model"], catalog,
                                 alias=r.get("meta", {}).get("alias"))
        if "elapsed_s" in r:
            times.append(r["elapsed_s"])
        results[pid] = r
        if args.verbose:
            extra = ""
            if r["verdict"] == "DIVERGE":
                extra = f" replay={r['replay']['status']}"
            if r["verdict"] in ("UNSUPPORTED", "ENCODER_ERROR"):
                extra = f" ({r.get('reason','')[:80]})"
            print(f"{pid}: {r['verdict']}{extra}  [{r.get('elapsed_s', 0):.3f}s]")

    n = len(results)
    by = Counter(r["verdict"] for r in results.values())
    rep = Counter(r["replay"]["status"] for r in results.values()
                  if r.get("replay"))
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
              f"p95 {st[int(len(st)*0.95)]*1000:.1f}ms  max {st[-1]*1000:.1f}ms")

    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    def _clean(r):
        return {k: v for k, v in r.items()
                if k not in ("trace_ir", "trace_joi")}
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump({pid: {**r, **({"replay": _clean(r["replay"])} if r.get("replay") else {})}
                   for pid, r in results.items()}, f, ensure_ascii=False, indent=1, default=str)
    print(f"detail → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
