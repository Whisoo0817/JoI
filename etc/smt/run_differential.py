"""E-A — differential: SMT gate vs old sim-based verifier on cached pairs.

Old verifier verdict (per pair): synthesize boundary scenarios from the IR,
run both simulators on each, compare traces (comparator, ±100ms). PASS iff
every scenario is equivalent.

Cross-tab against etc/smt/results/m1.json verdicts.

Usage:
    python3 -m etc.smt.run_differential
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

from sim.catalog import load_catalog
from sim.event_synth import synthesize_scenarios
from sim.ir_simulator import run_ir_simulation
from sim.joi_simulator import run_joi_simulation
from sim.comparator import compare_traces

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")
_M1_JSON = os.path.join(os.path.dirname(__file__), "results", "m1.json")


def old_verifier_verdict(ir: dict, joi_block: dict, catalog) -> tuple[str, str]:
    try:
        scenarios = synthesize_scenarios(ir)
    except Exception as e:
        return "SYNTH_ERROR", f"{type(e).__name__}: {e}"
    for sc in scenarios:
        try:
            tr_ir = run_ir_simulation(ir, sc, catalog)
            tr_joi = run_joi_simulation(joi_block, sc, catalog)
        except Exception as e:
            return "SIM_ERROR", f"{type(e).__name__}: {e}"
        res = compare_traces(tr_ir, tr_joi)
        if not res.equivalent:
            return "FAIL", f"[{sc.label}] {res.diff_summary.splitlines()[0]}"
    return "PASS", f"{len(scenarios)} scenarios"


def main() -> int:
    catalog = load_catalog()
    smt_res = json.load(open(_M1_JSON, encoding="utf-8"))

    tab = Counter()
    rows = {}
    for pid, sr in sorted(smt_res.items()):
        with open(os.path.join(_CACHE, pid + ".json"), encoding="utf-8") as f:
            pair = json.load(f)
        ov, detail = old_verifier_verdict(pair["ir"], pair["joi_block"], catalog)
        sv = sr["verdict"]
        tab[(sv, ov)] += 1
        rows[pid] = {"smt": sv, "old": ov, "old_detail": detail}

    print(f"pairs: {len(rows)}\n")
    print(f"{'SMT':<12} {'old-verifier':<14} count")
    for (sv, ov), n in sorted(tab.items()):
        print(f"{sv:<12} {ov:<14} {n:>4}")

    print("\ndisagreements:")
    for pid, r in rows.items():
        agree = (r["smt"] == "EQUIV") == (r["old"] == "PASS")
        if not agree and r["old"] not in ("SYNTH_ERROR", "SIM_ERROR"):
            print(f"  {pid}: SMT={r['smt']} old={r['old']} — {r['old_detail'][:110]}")
    print("\nerrors (old verifier could not run):")
    for pid, r in rows.items():
        if r["old"] in ("SYNTH_ERROR", "SIM_ERROR"):
            print(f"  {pid}: {r['old']} — {r['old_detail'][:110]}")

    out = os.path.join(os.path.dirname(__file__), "results", "differential_m1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"\ndetail → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
