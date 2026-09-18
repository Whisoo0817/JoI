"""Reproduce descriptive counts from the existing E1 corpus and final E3 manifest.

Run from any directory. No evaluation is rerun and no source data are modified.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
E1 = ROOT / "PerCom/08_Evaluation/E1_adequacy/breadth/corpus_100.csv"
DATA = ROOT / "dataset.csv"
PROTOCOL = ROOT / "explorer/eval/results/e3_single_binding_382_20260915_protocol.json"
MANIFEST = ROOT / "explorer/eval/results/e3_single_binding_382_20260915_manifest.json"


def nodes(value):
    if isinstance(value, dict):
        if "op" in value:
            yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def control_depth(value, level=0):
    if isinstance(value, dict):
        level += value.get("op") in ("if", "cycle")
        return max([level] + [control_depth(v, level) for v in value.values()])
    if isinstance(value, list):
        return max([level] + [control_depth(v, level) for v in value])
    return level


def counts(values):
    return dict(sorted(Counter(values).items()))


def main():
    with E1.open(encoding="utf-8-sig", newline="") as handle:
        corpus = list(csv.DictReader(handle))
    with DATA.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    protocol = json.loads(PROTOCOL.read_text())
    manifest = json.loads(MANIFEST.read_text())
    cases = manifest["cases"]
    assert len(corpus) == 100 and len(cases) == 382
    assert {c["id"] for c in cases} == set(protocol["case_ids"])
    assert len({c["id"] for c in cases}) == 382
    digest = hashlib.sha256(DATA.read_bytes()).hexdigest()
    assert digest == protocol["sources"]["dataset.csv"]
    present, occurrences, features, combinations = Counter(), Counter(), Counter(), Counter()
    sizes, depths, call_counts = [], [], []
    for case in cases:
        ir = case["payload"]["ir"]
        ns = list(nodes(ir))
        ops = {n["op"] for n in ns}
        present.update(ops)
        occurrences.update(n["op"] for n in ns)
        combinations.update([" + ".join(sorted(ops - {"start_at", "call"})) or "start_at/call only"])
        sizes.append(len(ns))
        depths.append(control_depth(ir))
        call_counts.append(sum(n["op"] == "call" for n in ns))
        flags = {
            "wait_for_duration": any(n["op"] == "wait" and n.get("for") for n in ns),
            "wait_rising": any(n["op"] == "wait" and n.get("edge") == "rising" for n in ns),
            "cron_anchor": any(n["op"] == "start_at" and n.get("anchor") == "cron" for n in ns),
            "wait_and_cycle": "wait" in ops and "cycle" in ops,
            "delay_and_cycle": "delay" in ops and "cycle" in ops,
        }
        features.update(k for k, flag in flags.items() if flag)
    eligible = [r for r in corpus if r["screen_status"] == "IN_SCOPE"]
    result = {
        "definitions": {
            "E1": "R/B labels use rb_adjudicated only, over the 92 IN_SCOPE rows. Other descriptive class columns are not treated as audited final labels.",
            "E3": "IRs come from the final evaluation manifest. Presence counts each case once; occurrences count syntactic nodes. Control depth counts nested if/cycle nodes, excluding the root timeline. Static call nodes are not executed action counts or physical device counts.",
            "limits": "These are structural descriptions, not empirical difficulty scores, population estimates, or a new independent semantic audit.",
        },
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [E1, DATA, PROTOCOL, MANIFEST]},
        "dataset_csv_matches_E3_protocol": True,
        "E1": {
            "n": len(corpus), "in_scope_n": len(eligible),
            "strata": counts(r["source_stratum"] for r in corpus),
            "screen_status": counts(r["screen_status"] for r in corpus),
            "provenance_types": counts(r["provenance_type"] for r in corpus),
            "text_forms": counts(r["text_form"] for r in corpus),
            "source_urls_by_stratum": {s: counts(r["source_url"] for r in corpus if r["source_stratum"] == s) for s in sorted({r["source_stratum"] for r in corpus})},
            "final_RB_presence": counts(t.strip() for r in eligible for t in r["rb_adjudicated"].split(",")),
        },
        "E3": {
            "source_csv_n": len(rows), "evaluated_n": len(cases),
            "categories": counts(c["id"].split("_")[0] for c in cases),
            "operator_presence": dict(sorted(present.items())),
            "operator_occurrences": dict(sorted(occurrences.items())),
            "features": dict(sorted(features.items())),
            "operator_sets_without_start_call": dict(sorted(combinations.items())),
            "IR_node_count": {"min": min(sizes), "median": median(sizes), "max": max(sizes), "histogram": counts(sizes)},
            "control_depth_histogram": counts(depths),
            "static_call_count_histogram": counts(call_counts),
        },
    }
    target = OUT / "dataset_structure.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Saved {target}: E1={len(corpus)} ({len(eligible)} in scope), E3={len(cases)}; dataset hash matches final protocol.")


if __name__ == "__main__":
    main()
