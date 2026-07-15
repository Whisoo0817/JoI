"""Verifier replay over the cached pipeline outputs.

Reads `paper/simulators/cache/*.json` (one per dataset row), feeds the cached
(ir, joi_block) pair through L1 static + L2 runtime checks, and summarizes
how many violations the verifier would surface — *without* re-invoking the
LLM. This is the LLM-free upper bound on what verifier-on retry could catch.

Usage:
    cd /home/gnltnwjstk/joi
    python3 -m paper.eval.verifier_replay              # all 307 rows
    python3 -m paper.eval.verifier_replay --cat C01    # one category
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "simulators", "cache",
)

from paper.verifier.l1_static import analyze as l1_analyze
from paper.verifier.l2_runtime import check as l2_check
from paper.simulators.catalog import load_catalog


def replay_one(catalog, row: dict) -> dict:
    ir = row.get("ir") or {}
    joi_block = row.get("joi_block") or {}
    connected = row.get("connected_devices") or {}

    l1 = l1_analyze(joi_block, connected_devices=connected, catalog=catalog)
    l2_list = []
    l2_error = None
    if not l1:
        try:
            report = l2_check(ir, joi_block, catalog=catalog)
            l2_list = report.violations
        except Exception as e:
            l2_error = f"{type(e).__name__}: {e}"

    return {
        "l1_count": len(l1),
        "l1_kinds": [v.kind for v in l1],
        "l2_count": len(l2_list),
        "l2_kinds": [v.kind for v in l2_list],
        "l2_error": l2_error,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default=None, help="filter by category prefix (e.g. C01)")
    ap.add_argument("--show-rows", action="store_true",
                    help="print every flagged row, not just summary")
    args = ap.parse_args()

    catalog = load_catalog()

    files = sorted(os.listdir(_CACHE_DIR))
    if args.cat:
        files = [f for f in files if f.startswith(args.cat + "_")]
    if not files:
        print("(no cache files matched)", file=sys.stderr)
        return 1

    per_cat_total = Counter()
    per_cat_l1 = Counter()
    per_cat_l2 = Counter()
    per_cat_l2err = Counter()
    kind_counter_l1 = Counter()
    kind_counter_l2 = Counter()
    flagged_rows = []

    for fname in files:
        path = os.path.join(_CACHE_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            row = json.load(f)
        cat = fname.split("_")[0]
        per_cat_total[cat] += 1

        res = replay_one(catalog, row)
        if res["l1_count"]:
            per_cat_l1[cat] += 1
            kind_counter_l1.update(res["l1_kinds"])
        if res["l2_count"]:
            per_cat_l2[cat] += 1
            kind_counter_l2.update(res["l2_kinds"])
        if res["l2_error"]:
            per_cat_l2err[cat] += 1

        if res["l1_count"] or res["l2_count"] or res["l2_error"]:
            flagged_rows.append((fname, res, row.get("command_eng", "")[:60]))

    # ── Output ──
    print(f"Verifier replay over {len(files)} cached rows\n")
    print(f"{'cat':<6} {'total':>6} {'L1':>6} {'L2':>6} {'L2err':>6}")
    print("-" * 36)
    for cat in sorted(per_cat_total):
        print(f"{cat:<6} {per_cat_total[cat]:>6} "
              f"{per_cat_l1[cat]:>6} {per_cat_l2[cat]:>6} {per_cat_l2err[cat]:>6}")
    print("-" * 36)
    print(f"{'TOTAL':<6} {sum(per_cat_total.values()):>6} "
          f"{sum(per_cat_l1.values()):>6} {sum(per_cat_l2.values()):>6} "
          f"{sum(per_cat_l2err.values()):>6}")

    print("\nL1 violation kinds:")
    for k, n in kind_counter_l1.most_common():
        print(f"  {k:<22} {n}")
    print("\nL2 violation kinds:")
    for k, n in kind_counter_l2.most_common():
        print(f"  {k:<22} {n}")

    if args.show_rows:
        print("\n── Flagged rows ──")
        for fname, res, cmd in flagged_rows:
            tag = []
            if res["l1_count"]:
                tag.append(f"L1×{res['l1_count']}({','.join(res['l1_kinds'])})")
            if res["l2_count"]:
                tag.append(f"L2×{res['l2_count']}({','.join(res['l2_kinds'])})")
            if res["l2_error"]:
                tag.append(f"L2ERR({res['l2_error']})")
            print(f"  {fname:<14} {' '.join(tag):<50} {cmd}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
