"""One-shot repair on the development set: verify the wrong candidate, build counterexample
feedback, ask the model once, verify the answer.

    ~/temp/bin/python joi/self_feedback/dev/run_repair.py --prompt joi/self_feedback/prompts/repair.md \
        --run-id v1 [--cases D1a,D2b] [--workers 3] [--no-think]

Results: joi/self_feedback/dev/runs/<run-id>/{cases/<id>.json,summary.json}. Prompt-tuning aid only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from cases import CASES  # noqa: E402

sys.path.insert(0, str(HERE.parent))
from repair_core import verify, feedback, ir_timing_facts, call_model, parse_block, build_payload, render_payload  # noqa: E402

def run_case(c, system, args, outdir):
    rec = {"id": c["id"], "family": c["family"]}
    base = verify(c["ir"], c["binding"], c["devices"], c["wrong"])
    rec["baseline"] = {k: v for k, v in base.items() if k != "witness"}
    if base.get("verdict") != "DIVERGE" or not base.get("confirmed"):
        rec["status"] = "BASELINE_NOT_DIVERGE"
        return rec
    fb = feedback(base["witness"], c["wrong"]["script"])
    payload = build_payload(c["ir"], c["binding"], c["devices"], c["wrong"], fb, ir_facts=args.ir_facts)
    user = render_payload(payload)
    rec["prompt_chars"] = len(system) + len(user)
    try:
        resp = call_model(system, user, not args.no_think, seed=args.seed, max_tokens=args.max_tokens, budget_force=args.budget_force, temperature=args.temperature)
    except Exception as e:
        rec.update(status="MODEL_ERROR", error=repr(e))
        return rec
    rec["model"] = {k: v for k, v in resp.items() if k not in ("content", "reasoning")}
    rec["response"] = resp["content"]
    rec["reasoning_chars"] = len(resp.get("reasoning") or "")
    parsed, err = parse_block(resp["content"], "Scenario")
    if parsed is None:
        rec.update(status="INVALID_OUTPUT", error=err)
        return rec
    rec["repaired"] = parsed["joi_block"]
    rec["diagnosis"] = parsed["diagnosis"]
    v = verify(c["ir"], c["binding"], c["devices"], parsed["joi_block"])
    rec["verification"] = {k: v[k] for k in v if k != "witness"}
    if v.get("witness"):
        rec["verification"]["mismatch_ms"] = feedback(v["witness"], "")["F2_action_mismatch"]["same_instant_ms"]
    if v.get("verdict") == "EQUIV" and v.get("claim") == "EQUIV-FIXPOINT":
        rec["status"] = "REPAIRED_EQUIV"
    elif v.get("verdict") == "DIVERGE":
        rec["status"] = "STILL_DIVERGE"
    else:
        rec["status"] = v.get("verdict", "UNKNOWN")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--cases", default="")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--no-think", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--budget-force", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--ir-facts", action="store_true", help="add IR-derived timing facts (durations in ms and 100 ms ticks) to the payload")
    args = ap.parse_args()
    system = Path(args.prompt).read_text(encoding="utf-8")
    want = {x for x in args.cases.split(",") if x}
    cases = [c for c in CASES if not want or c["id"] in want]
    outdir = HERE / "runs" / args.run_id
    (outdir / "cases").mkdir(parents=True, exist_ok=True)
    jobs = [(c, i) for c in cases for i in range(args.repeat)]

    def one(job):
        c, i = job
        rec = run_case(c, system, args, outdir)
        rec["rep"] = i
        (outdir / "cases" / f"{c['id']}.{i}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        print(f"  {c['id']}.{i:<2} {rec['status']:20s} {rec.get('verification', {}).get('claim') or ''} "
              f"{rec.get('model', {}).get('usage', {}).get('completion_tokens', '')}tok", flush=True)
        return rec

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        recs = list(ex.map(one, jobs))
    by_status = {}
    for r in recs:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    by_family = {}
    for r in recs:
        f = by_family.setdefault(r["family"], [0, 0])
        f[1] += 1
        f[0] += r["status"] == "REPAIRED_EQUIV"
    summary = {"run_id": args.run_id, "prompt": args.prompt,
               "prompt_sha256": hashlib.sha256(system.encode()).hexdigest(),
               "think": not args.no_think, "max_tokens": args.max_tokens, "budget_force": args.budget_force, "seed": args.seed, "temperature": args.temperature, "ir_facts": args.ir_facts, "n": len(recs),
               "repaired": by_status.get("REPAIRED_EQUIV", 0), "by_status": by_status,
               "by_family": {k: f"{a}/{b}" for k, (a, b) in by_family.items()},
               "wall_seconds": round(time.time() - t0, 1)}
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
