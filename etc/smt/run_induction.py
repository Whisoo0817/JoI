"""Induction evidence run: upgrade the redeploy certificates to unbounded time.

Over the contingency redeploy artifacts (the certified pairs of run_certify):

    bounded verdict (w_cap window)  +  tick induction
    ─────────────────────────────────────────────────
    EQUIV      → INDUCTIVE_EQUIV upgrades the certificate from
                 "equal within 32s" to "equal at EVERY tick"
    TIMEOUT    → the 1-tick step query is far smaller than the 32-tick
                 monolith — the two undecided movetocolor obligations get a
                 second chance here
    NOT_INDUCTIVE → the bounded certificate stands (fall back, fail closed)

    python3 -m etc.smt.run_induction [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from sim.catalog import load_catalog

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from adapt.inventory import base_office                  # noqa: E402
from adapt.template import load_skeleton, load_template  # noqa: E402
from etc.smt.induction import check_inductive_v2             # noqa: E402
from etc.smt.relational import emitted_sigs_v2               # noqa: E402

_TABLES = os.path.join(_REPO, "adapt", "contingency_tables")
_RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout-ms", type=int, default=300_000)
    ap.add_argument("--json", default=os.path.join(_RESULTS, "induction.json"))
    args = ap.parse_args(argv)

    catalog = load_catalog()
    inv = base_office()
    results: dict = {}
    ups = fails = 0

    for fn in sorted(os.listdir(_TABLES)):
        if not fn.endswith(".json"):
            continue
        table = json.load(open(os.path.join(_TABLES, fn), encoding="utf-8"))
        tid = table["template"]
        skeleton = load_skeleton(load_template(tid))
        raw = json.load(open(os.path.join(_REPO, "adapt", "templates",
                                          f"{tid}.json"), encoding="utf-8"))
        period = int((raw.get("validity") or {}).get("period_ms", 1000))
        for dev_id, row in table["rows"].items():
            if row.get("action") != "redeploy":
                continue
            rid = f"{tid}/{dev_id}"
            keep = emitted_sigs_v2(row["artifact"], inv, catalog)
            r = check_inductive_v2(skeleton, row["artifact"], period, inv,
                                   catalog, preserve=keep,
                                   timeout_ms=args.timeout_ms)
            results[rid] = r
            v = r["verdict"]
            if v == "INDUCTIVE_EQUIV":
                ups += 1
            print(f"{rid}: {v} ({r.get('elapsed_s', 0)}s) "
                  f"invariant={r.get('invariant', '-')}")
            for lbl, ov in sorted((r.get("obligations") or {}).items()):
                mark = "✓" if ov == "EQUIV" else "×"
                print(f"    {mark} {lbl:<48} {ov}")

    print(f"\nunbounded certificates: {ups} rows upgraded")
    os.makedirs(_RESULTS, exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    print(f"detail → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
