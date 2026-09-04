"""Obligation-split differential: split verdicts must equal monolithic.

For every cached pair, pick its engine (M1 → path miter, M2 → accelerated
run miter, M3 → cron miter) and run the divergence query BOTH ways:

    mono    one plain check()            — the pre-refactor gate query
    split   one check(b_k) per obligation — the assumption-switch queries

Asserts, per pair:
  * mono verdict == split verdict;
  * mono verdict == the prior batch verdict (results/m1.json, m25.json,
    m3.json) where one exists — the refactor changed the query's FORM, not
    its meaning;
and prints, for every DIVERGE pair, the per-obligation localization: which
output contracts are violable and which are individually proved preserved.

    python3 -m etc.smt.run_obligations [--only C01_006,...] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

from sim.catalog import load_catalog

from etc.smt.accel import check_pair_accel
from etc.smt.encode import check_pair
from etc.smt.encode3 import check_pair_m3
from etc.smt.fragment import classify_pair

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")
_RESULTS = os.path.join(os.path.dirname(__file__), "results")


def _prior() -> dict:
    out: dict = {}
    for fn, get in (("m1.json", lambda r: r.get("verdict")),
                    ("m25.json", lambda r: (r.get("accel") or {}).get("verdict")),
                    ("m3.json", lambda r: r.get("verdict"))):
        path = os.path.join(_RESULTS, fn)
        if not os.path.exists(path):
            continue
        for pid, r in json.load(open(path, encoding="utf-8")).items():
            v = get(r)
            if v:
                out.setdefault(pid, v)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default=os.path.join(_RESULTS, "obligations.json"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    only = set(x.strip() for x in args.only.split(",") if x.strip())
    prior = _prior()

    engines = {"M1": check_pair,
               "M2": check_pair_accel,
               "M3": check_pair_m3}
    results: dict = {}
    disagree: list = []
    prior_flips: list = []
    t_mono: list = []
    t_split: list = []

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
            cls = classify_pair(ir, joi_block)["verdict"]
        except Exception:
            continue
        engine = engines.get(cls)
        if engine is None:
            continue
        devs = pair.get("connected_devices")

        try:
            r0 = engine(ir, joi_block, catalog, devices=devs)
        except Exception as e:
            r0 = {"verdict": "ENCODER_ERROR", "reason": f"{type(e).__name__}: {e}"}
        entry = {"class": cls, "mono": r0["verdict"]}
        if r0["verdict"] in ("EQUIV", "DIVERGE"):
            t_mono.append(r0.get("elapsed_s", 0.0))
            try:
                r1 = engine(ir, joi_block, catalog, devices=devs, split=True)
            except Exception as e:
                r1 = {"verdict": "ENCODER_ERROR",
                      "reason": f"{type(e).__name__}: {e}"}
            entry["split"] = r1["verdict"]
            entry["obligations"] = r1.get("obligations")
            entry["violated_mono"] = r0.get("violated")
            t_split.append(r1.get("elapsed_s", 0.0))
            if r0["verdict"] != r1["verdict"]:
                disagree.append(pid)
        pv = prior.get(pid)
        if pv is not None and pv != r0["verdict"]:
            prior_flips.append((pid, pv, r0["verdict"]))
        entry["prior"] = pv
        results[pid] = entry
        if args.verbose or r0["verdict"] == "DIVERGE" or pid in disagree:
            print(f"{pid} [{cls}] mono={r0['verdict']} "
                  f"split={entry.get('split', '-')} prior={pv}")
            if entry.get("obligations"):
                for lbl, v in entry["obligations"].items():
                    mark = "×" if v == "DIVERGE" else "✓"
                    print(f"    {mark} {lbl:<40} {v}")

    n = len(results)
    by_cls = Counter(e["class"] for e in results.values())
    by_v = Counter(e["mono"] for e in results.values())
    n_obl = sum(len(e.get("obligations") or {}) for e in results.values())
    print(f"\npairs: {n}  {dict(by_cls)}")
    for k, v in by_v.most_common():
        print(f"  {k:<16} {v:>4}")
    print(f"obligations checked individually: {n_obl}")
    print(f"mono↔split verdict disagreements: {len(disagree)} {disagree}")
    print(f"prior-verdict flips: {len(prior_flips)} {prior_flips}")
    if t_mono:
        print(f"solve time  mono total {sum(t_mono):.1f}s  "
              f"split total {sum(t_split):.1f}s")
    print("PASS" if not disagree and not prior_flips else "FAIL")

    os.makedirs(_RESULTS, exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    print(f"detail → {args.json}")
    return 1 if (disagree or prior_flips) else 0


if __name__ == "__main__":
    sys.exit(main())
