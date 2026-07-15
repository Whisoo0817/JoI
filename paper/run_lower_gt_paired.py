#!/usr/bin/env python3
"""Stage-B paired re-run: gate as a pure ablation over the OFF arm's candidates.

Paired protocol (one rule for every row, decided before looking at results):
  - The gated arm's attempt-1 candidate IS the ungated arm's lowering
    (injected via JOI_SEED_JOI_PATH; see run_local_ir._lower_fn).
  - Rows whose OFF candidate passes l2_check need no LLM at all: the gate
    verifies the same candidate, passes it, and deploys it unchanged.
  - Rows whose OFF candidate fails are re-run here: verifier flags the seed,
    then the normal diagnose+retry repair loop runs (LLM needed).

Usage:
  LLM_BASE_URL=http://localhost:8002/v1 PYTHONPATH=. python3 \
      paper/run_lower_gt_paired.py \
      --off-run experiments/stageB_382_gemma4/20260604_174610__gemma-4-E4B-AWQ/intermediate \
      --out experiments/stageB_382_gemma4/paired_<ts>/intermediate \
      [--workers 4] [--timeout 240]

Outputs <out>/on_paired/<row>.json (same schema as the on/ arm) for the OFF-fail
rows only, plus <out>/_paired_summary.json with the paired-arm accounting:
  deployed_correct = off_pass + repaired_ok
  rejected         = rerun rows with verifier_trace.accepted == False
  silent_wrong     = rerun rows deployed (accepted) but l2_check fail
"""
import argparse, csv, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "paper"))
CSV_PATH = os.path.join(ROOT, "dataset.csv")

from run_lower_gt_batch import WORKER_SCRIPT, load_rows  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--off-run", required=True,
                    help="intermediate dir of the original run (off/ + _summary.json)")
    ap.add_argument("--out", required=True, help="output intermediate dir")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("BATCH_WORKERS", "4")))
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("BATCH_TIMEOUT", "240")))
    a = ap.parse_args()

    summary = json.load(open(os.path.join(a.off_run, "_summary.json"), encoding="utf-8"))
    off_grades = summary["grades"]["off"]
    fail_rows = sorted(n for n, g in off_grades.items() if g["verdict"] != "pass")
    off_pass = sum(1 for g in off_grades.values() if g["verdict"] == "pass")
    print(f"[paired] off_pass={off_pass} off_fail={len(fail_rows)} -> re-running fail rows only")

    rows = {f"{r['category']}_{r['index']}": r for r in load_rows()}
    out_on = os.path.join(a.out, "on_paired")
    gt_dir = os.path.join(a.out, "gt_ir")
    os.makedirs(out_on, exist_ok=True); os.makedirs(gt_dir, exist_ok=True)

    def call_one(name):
        r = rows[name]
        gt_path = os.path.join(gt_dir, f"{name}.json")
        json.dump(json.loads(r["ir_gt"]), open(gt_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        out_path = os.path.join(out_on, f"{name}.json")
        env = os.environ.copy()
        env["JOI_ROOT"] = ROOT
        env["JOI_VERIFY"] = "1"
        env["JOI_GT_IR_PATH"] = gt_path
        env["JOI_SEED_JOI_PATH"] = os.path.join(a.off_run, "off", f"{name}.json")
        env.pop("JOI_IR_ONLY", None)
        t0 = time.perf_counter()
        try:
            p = subprocess.run(
                [sys.executable, "-c", WORKER_SCRIPT,
                 r["command_eng"], r["connected_devices"], out_path],
                env=env, capture_output=True, text=True, timeout=a.timeout)
            return {"name": name, "ok": os.path.exists(out_path),
                    "elapsed": time.perf_counter() - t0,
                    "stderr_tail": (p.stderr or "")[-300:] if not os.path.exists(out_path) else ""}
        except subprocess.TimeoutExpired:
            return {"name": name, "ok": False, "elapsed": float(a.timeout),
                    "stderr_tail": f"timeout-{a.timeout}s"}

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(call_one, n): n for n in fail_rows}
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            tag = "" if res["ok"] else f"  !! {res['stderr_tail'][:80]}"
            print(f"  [{i}/{len(fail_rows)}] {res['name']} ({res['elapsed']:.1f}s){tag}")
    print(f"[paired] subprocess runs done in {time.perf_counter() - t0:.1f}s; grading...")

    from paper.verifier.l2_runtime import check as l2_check
    per_row, tally = {}, {"repaired_ok": 0, "rejected": 0, "silent_wrong": 0,
                          "error": 0, "missing": 0}
    for name in fail_rows:
        p = os.path.join(out_on, f"{name}.json")
        if not os.path.exists(p):
            per_row[name] = {"outcome": "missing"}; tally["missing"] += 1; continue
        d = json.load(open(p, encoding="utf-8"))
        vt = d.get("verifier_trace") or {}
        accepted = bool(vt.get("accepted"))
        if d.get("status") != "ok":
            # pipeline hard-error inside the gated run: nothing deploys
            per_row[name] = {"outcome": "rejected", "detail": d.get("error_code", "error")}
            tally["rejected"] += 1
            continue
        joi = d.get("joi_block")
        verdict = "fail"
        try:
            ir_gt = json.loads(rows[name]["ir_gt"])
            if isinstance(joi, dict):
                rep = l2_check(ir_gt, joi)
                verdict = "pass" if rep.equivalent else "fail"
        except Exception as e:
            verdict = f"l2-exc:{type(e).__name__}"
        if not accepted:
            outcome = "rejected"
            tally["rejected"] += 1
        elif verdict == "pass":
            outcome = "repaired_ok"
            tally["repaired_ok"] += 1
        else:
            outcome = "silent_wrong"
            tally["silent_wrong"] += 1
        per_row[name] = {"outcome": outcome, "graded": verdict,
                         "accepted": accepted, "n_attempts": vt.get("n_attempts")}

    n = len(off_grades)
    deployed_correct = off_pass + tally["repaired_ok"]
    agg = {
        "n_rows": n, "off_pass": off_pass, "off_fail": len(fail_rows),
        "paired": tally, "deployed_correct": deployed_correct,
        "deployed_correct_pct": round(100 * deployed_correct / n, 2),
        "rejected_total": tally["rejected"] + tally["missing"],
        "silent_wrong_total": tally["silent_wrong"],
        "off_run": a.off_run, "per_row": per_row,
    }
    sp = os.path.join(a.out, "_paired_summary.json")
    json.dump(agg, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in agg.items() if k != "per_row"}, indent=1))
    print(f"[paired] summary -> {sp}")


if __name__ == "__main__":
    main()
