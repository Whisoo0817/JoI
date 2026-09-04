"""M3 batch runner: SMT gate over cron cached pairs + replay adjudication.

Usage:
    python3 -m etc.smt.run_m3 [--only ...] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

from sim.catalog import load_catalog

from etc.smt.encode3 import check_pair_m3
from etc.smt.fragment import classify_pair
from etc.smt.run_m2 import replay_m2

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default=os.path.join(os.path.dirname(__file__),
                                                   "results", "m3.json"))
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
        if cls["verdict"] != "M3":
            continue

        try:
            r = check_pair_m3(ir, joi_block, catalog,
                              devices=pair.get("connected_devices"))
        except Exception as e:
            r = {"verdict": "ENCODER_ERROR", "reason": f"{type(e).__name__}: {e}"}
        if r["verdict"] == "DIVERGE":
            if r.get("reason") == "cron occurrence sets differ":
                r["replay"] = {"status": "DETERMINISTIC", "detail": str(r["meta"])}
            else:
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
            print(f"{pid}: {r['verdict']}{extra}  [{r.get('elapsed_s', 0):.3f}s]")

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
