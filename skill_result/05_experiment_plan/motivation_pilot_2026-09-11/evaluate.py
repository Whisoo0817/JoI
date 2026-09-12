"""Evaluate generated candidates and print the funnel.

python evaluate.py [--models qwen9b gpt51]
Writes runs/results_<model>.jsonl and runs/summary.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import TASK_BY_ID, evaluate_block  # noqa: E402

GEN = HERE / "runs" / "generations"
PRE_BEHAVIOR = ["format", "syntax", "modeled_fragment", "api_binding", "runtime"]


def evaluate_model(model: str) -> list[dict]:
    rows = []
    for path in sorted((GEN / model).glob("*/*.json")):
        rec = json.loads(path.read_text())
        task = TASK_BY_ID[rec["task"]]
        if rec.get("raw") is None:
            r = {"stage_failed": "format", "failure": rec.get("error", "no output")}
            res = {"task": rec["task"], **r, "histories": [], "block": None}
        else:
            res = evaluate_block(task, raw=rec["raw"]).to_json()
            if rec.get("finish_reason") == "length" and res["stage_failed"] == "format":
                res["failure"] = "truncated at max tokens; " + res["failure"]
        res.update(model=model, condition=rec["condition"], sample=rec["sample"],
                   family=task["family"], level=task["level"], finish_reason=rec.get("finish_reason"))
        rows.append(res)
    out = HERE / "runs" / f"results_{model}.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows) + "\n")
    return rows


def funnel(rows: list[dict]) -> dict:
    n = len(rows)
    failed = defaultdict(int)
    for r in rows:
        failed[r["stage_failed"]] += 1
    executable = sum(1 for r in rows if r["stage_failed"] not in PRE_BEHAVIOR)
    nominal_pass = sum(1 for r in rows if r["stage_failed"] in (None, "boundary"))
    silent = sum(1 for r in rows if r["stage_failed"] == "boundary")
    silent_nl = sum(1 for r in rows if r["stage_failed"] == "boundary" and r.get("boundary_pass_nl_determined") is False)
    correct = sum(1 for r in rows if r["stage_failed"] is None)
    return {
        "generated": n,
        "failed_format": failed["format"], "failed_syntax": failed["syntax"],
        "failed_modeled_fragment": failed["modeled_fragment"], "failed_api_binding": failed["api_binding"],
        "failed_runtime": failed["runtime"],
        "executable": executable,
        "visible_divergence": failed["nominal"],
        "nominal_pass": nominal_pass,
        "silent_divergence": silent,
        "silent_divergence_nl_determined_histories": silent_nl,
        "correct_on_all_histories": correct,
        "silent_rate_of_executable": round(silent / executable, 3) if executable else None,
        "silent_share_of_nominal_pass": round(silent / nominal_pass, 3) if nominal_pass else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=[p.name for p in sorted(GEN.iterdir()) if p.is_dir()])
    args = ap.parse_args()
    summary = {}
    for model in args.models:
        rows = evaluate_model(model)
        by = defaultdict(list)
        for r in rows:
            by[("condition", r["condition"])].append(r)
            by[("condition_level", f"{r['condition']}/L{r['level']}")].append(r)
            by[("condition_family", f"{r['condition']}/{r['family']}")].append(r)
            by[("condition_task", f"{r['condition']}/{r['task']}")].append(r)
        summary[model] = {"all": funnel(rows)}
        for (kind, key), rs in sorted(by.items()):
            summary[model].setdefault(kind, {})[key] = funnel(rs)
        print(f"\n=== {model}: {len(rows)} candidates")
        hdr = ["cond", "gen", "fmt", "syn", "frag", "api", "rt", "exec", "visible", "nomPass", "silent", "correct"]
        print(" ".join(f"{h:>7}" for h in hdr))
        for cond in ["NL", "SPEC", "IR"]:
            f = summary[model]["condition"].get(cond)
            if not f:
                continue
            vals = [cond, f["generated"], f["failed_format"], f["failed_syntax"], f["failed_modeled_fragment"],
                    f["failed_api_binding"], f["failed_runtime"], f["executable"], f["visible_divergence"],
                    f["nominal_pass"], f["silent_divergence"], f["correct_on_all_histories"]]
            print(" ".join(f"{v:>7}" for v in vals))
        print("per level (silent / executable, correct / executable):")
        for key, f in summary[model]["condition_level"].items():
            print(f"  {key:10s} exec={f['executable']:>2} silent={f['silent_divergence']:>2} "
                  f"visible={f['visible_divergence']:>2} correct={f['correct_on_all_histories']:>2}")
    (HERE / "runs" / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
