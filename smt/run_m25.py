"""M2.5 batch: accelerated engine over periodic pairs + unroll differential.

For every M2-class pair (and the two window-capped UNSUPPORTED ones):
    1. try the accelerated engine (accel.check_pair_accel)
    2. NOT_ACCELERABLE → fall back to the unroll engine verdict
    3. differential: where BOTH engines produce a verdict, they must agree
       (accelerated horizon is 7 days vs unroll's W window — an accel-only
       DIVERGE found beyond W is reported as scope-extra, not disagreement:
       adjudicated by replay)

Usage:
    python3 -m smt.run_m25 [--only ...] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

from sim.catalog import load_catalog

from smt.accel import check_pair_accel
from smt.encode2 import check_pair_m2
from smt.fragment import classify_pair
from smt.run_m2 import replay_m2

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default=os.path.join(os.path.dirname(__file__),
                                                   "results", "m25.json"))
    ap.add_argument("--skip-unroll", action="store_true",
                    help="skip the unroll differential (fast run)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    only = set(x.strip() for x in args.only.split(",") if x.strip())
    prior = {}
    prior_path = os.path.join(os.path.dirname(__file__), "results", "m2.json")
    if os.path.exists(prior_path):
        prior = json.load(open(prior_path, encoding="utf-8"))

    results: dict = {}
    if os.path.exists(args.json):   # resume: keep pairs already judged
        done = json.load(open(args.json, encoding="utf-8"))
        results.update({p: r for p, r in done.items()
                        if r.get("accel", {}).get("verdict")
                        in ("EQUIV", "DIVERGE", "NOT_ACCELERABLE")})
    for fn in sorted(os.listdir(_CACHE)):
        if not fn.endswith(".json"):
            continue
        pid = fn[:-5]
        if only and pid not in only:
            continue
        if pid in results:
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

        devs = pair.get("connected_devices")
        try:
            ra = check_pair_accel(ir, joi_block, catalog, devices=devs)
        except Exception as e:
            ra = {"verdict": "ENCODER_ERROR", "reason": f"{type(e).__name__}: {e}"}
        if ra["verdict"] == "DIVERGE":
            ra["replay"] = replay_m2(ir, joi_block, ra["model"], ra["meta"], catalog)

        entry = {"accel": {k: v for k, v in ra.items() if k != "model"}}
        # unroll comparison verdict (prior run or fresh)
        uv = None
        if pid in prior and prior[pid].get("verdict") in ("EQUIV", "DIVERGE"):
            uv = prior[pid]["verdict"]
            entry["unroll"] = {"verdict": uv, "source": "m2.json",
                               "elapsed_s": prior[pid].get("elapsed_s")}
        elif not args.skip_unroll and ra["verdict"] in ("EQUIV", "DIVERGE"):
            try:
                ru = check_pair_m2(ir, joi_block, catalog, devices=devs)
                uv = ru["verdict"]
                entry["unroll"] = {"verdict": uv, "source": "fresh",
                                   "elapsed_s": ru.get("elapsed_s")}
            except Exception as e:
                entry["unroll"] = {"verdict": "ERROR", "reason": str(e)}

        av = ra["verdict"]
        if av in ("EQUIV", "DIVERGE") and uv in ("EQUIV", "DIVERGE"):
            if av == uv:
                entry["differential"] = "AGREE"
            elif av == "DIVERGE" and uv == "EQUIV":
                # possibly beyond-W scope extra — replay decides
                entry["differential"] = ("SCOPE_EXTRA_REPRODUCED"
                                         if ra.get("replay", {}).get("status") == "REPRODUCED"
                                         else "DISAGREE_ACCEL_FP")
            else:
                entry["differential"] = "DISAGREE_ACCEL_MISS"
        results[pid] = entry
        if args.verbose:
            d = entry.get("differential", "-")
            extra = ""
            if av == "DIVERGE":
                extra = f" replay={ra['replay']['status']}"
            if av in ("NOT_ACCELERABLE", "UNSUPPORTED", "ENCODER_ERROR"):
                extra = f" ({ra.get('reason','')[:70]})"
            print(f"{pid}: accel={av}{extra} unroll={uv or '-'} diff={d} "
                  f"[{ra.get('elapsed_s', 0):.2f}s]")

    n = len(results)
    by_a = Counter(r["accel"]["verdict"] for r in results.values())
    by_d = Counter(r.get("differential", "-") for r in results.values())
    times = sorted(r["accel"]["elapsed_s"] for r in results.values()
                   if r["accel"]["verdict"] in ("EQUIV", "DIVERGE"))
    print(f"\npairs: {n}")
    print("accel verdicts:")
    for k, v in by_a.most_common():
        print(f"  {k:<16} {v:>4}  ({v/max(n,1):5.1%})")
    print("differential vs unroll:")
    for k, v in by_d.most_common():
        print(f"  {k:<24} {v:>4}")
    if times:
        print(f"accel solve: median {times[len(times)//2]*1000:.1f}ms  "
              f"p95 {times[int(len(times)*0.95)]*1000:.1f}ms  max {times[-1]:.2f}s")

    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    print(f"detail → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
