#!/usr/bin/env python3
"""Aggregate transition-boundary coverage of the scenario suite over the dataset.

Reports, per category and overall: the number of IR-FSM coverage obligations, how
many the synthesized suite exercises, the coverage rate, and a breakdown of
uncovered obligations by reason — the RQ3 coverage metric backing the Rung-1 claim.

Usage:
    python3 paper/run_coverage_report.py
    BATCH_CATEGORIES=C03,C20 python3 paper/run_coverage_report.py   # subset
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "paper"))

from paper.simulators.coverage import coverage_report, joi_branch_coverage

CSV_PATH = os.path.join(ROOT, "dataset.csv")
CAT_FILTER = {c.strip() for c in os.environ.get("BATCH_CATEGORIES", "").split(",") if c.strip()}
# Optional: a Stage-B dump dir of joi_block JSONs (cat_idx.json with key 'joi_block')
# enables the IMPLEMENTATION-side (JoI branch) coverage column (§8.6 two-sided).
JOI_DUMP_DIR = os.environ.get("JOI_DUMP_DIR", "")


def main():
    per_cat_tot = defaultdict(int)
    per_cat_cov = defaultdict(int)
    per_cat_scn = defaultdict(int)
    per_cat_rows = defaultdict(int)
    uncovered_reasons = Counter()
    n_rows = n_with_obligations = 0
    worst = []  # (pct, name, n_uncovered)
    impl_tot = impl_cov = impl_rows = 0  # JoI-side branch coverage (if dump dir given)

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cat = (r.get("category_v2") or "").strip()
            idx = (r.get("index") or "").strip()
            if not cat or (CAT_FILTER and cat not in CAT_FILTER):
                continue
            try:
                ir = json.loads(r.get("ir_gt", "") or "null")
            except Exception:
                ir = None
            if not isinstance(ir, dict) or "timeline" not in ir:
                continue
            n_rows += 1
            rep = coverage_report(ir)
            per_cat_rows[cat] += 1
            per_cat_scn[cat] += rep["n_scenarios"]
            per_cat_tot[cat] += rep["total"]
            per_cat_cov[cat] += rep["n_covered"]
            if rep["total"]:
                n_with_obligations += 1
            for _ob, reason in rep["uncovered"]:
                uncovered_reasons[reason] += 1
            if rep["total"] and rep["pct"] < 100:
                worst.append((rep["pct"], f"{cat}_{idx}", len(rep["uncovered"])))

            if JOI_DUMP_DIR:
                p = os.path.join(JOI_DUMP_DIR, f"{cat}_{idx}.json")
                if os.path.exists(p):
                    try:
                        jb = json.load(open(p, encoding="utf-8")).get("joi_block")
                    except Exception:
                        jb = None
                    if isinstance(jb, dict):
                        jrep = joi_branch_coverage(jb, ir)
                        if jrep and jrep["total"]:
                            impl_tot += jrep["total"]
                            impl_cov += jrep["covered"]
                            impl_rows += 1

    print("=" * 74)
    print(f"Transition-boundary coverage of the scenario suite ({n_rows} IRs; "
          f"{n_with_obligations} have ≥1 branch/wait obligation)")
    print("=" * 74)
    print(f"  {'cat':<6} {'rows':>5} {'avg|S|':>7} {'obligations':>12} {'covered':>8} {'cov%':>6}")
    tot_o = tot_c = tot_s = 0
    for cat in sorted(per_cat_tot):
        o, c = per_cat_tot[cat], per_cat_cov[cat]
        rows = per_cat_rows[cat]
        avg_s = per_cat_scn[cat] / rows if rows else 0
        tot_o += o; tot_c += c; tot_s += per_cat_scn[cat]
        pct = 100 * c / o if o else 100.0
        print(f"  {cat:<6} {rows:>5} {avg_s:>7.1f} {o:>12} {c:>8} {pct:>5.1f}%")
    print("-" * 74)
    pct = 100 * tot_c / tot_o if tot_o else 100.0
    print(f"  {'TOTAL':<6} {n_rows:>5} {tot_s/n_rows if n_rows else 0:>7.1f} "
          f"{tot_o:>12} {tot_c:>8} {pct:>5.1f}%")

    if JOI_DUMP_DIR and impl_rows:
        ipct = 100 * impl_cov / impl_tot if impl_tot else 100.0
        print(f"\nIMPL-side JoI branch coverage ({impl_rows} JoI programs, dump={JOI_DUMP_DIR}):")
        print(f"  {impl_cov}/{impl_tot} branches exercised = {ipct:.1f}%")

    if uncovered_reasons:
        print("\nUncovered obligations by reason:")
        for reason, n in uncovered_reasons.most_common():
            print(f"  {n:>4}  {reason}")
    if worst:
        print("\nLowest-coverage IRs:")
        for p, name, nu in sorted(worst)[:15]:
            print(f"  {p:>5.1f}%  {name}  ({nu} uncovered)")


if __name__ == "__main__":
    main()
