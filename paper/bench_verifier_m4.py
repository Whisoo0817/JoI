#!/usr/bin/env python3
"""RQ4: on-device verifier latency benchmark (run ON the Mac Mini M4).

Times the deterministic LLM-free verifier (paper.verifier.l2_runtime.check)
over all rows of a Stage-B run dir, the same call run_lower_gt_batch.py uses
for grading. No LLM, no network: copy the repo to the M4 and run.

Per row: l2_check(gt_ir, joi_block) x (1 warm-up discarded + REPS timed).
Reports per-row p50 and aggregate p50/p95/worst, plus IR complexity features
(op counts) so latency can be stratified by structure, and peak RSS.

Usage (on the M4):
  PYTHONPATH=/path/to/joi python3 paper/bench_verifier_m4.py \
      --run-dir experiments/stageB_382_8B/<ts>__qwen3-8b-awq/intermediate \
      --arm on --reps 10 \
      --out paper/Final/evaluation/results/m4_verifier_latency.json
"""
import argparse
import csv
import json
import os
import platform
import resource
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "paper"))

CSV_PATH = os.path.join(ROOT, "dataset.csv")


def ir_features(ir):
    """Count IR ops per kind (complexity axes for stratification)."""
    counts = {"wait": 0, "delay": 0, "cycle": 0, "if": 0, "call": 0,
              "read": 0, "break": 0, "start_at": 0, "total": 0}

    def walk(node):
        if isinstance(node, dict):
            op = node.get("op")
            if op in counts:
                counts[op] += 1
                counts["total"] += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(ir)
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True,
                    help="Stage-B intermediate dir containing off/ and on/")
    ap.add_argument("--arm", default="on", choices=["off", "on"],
                    help="which generated JoI set to check against gt_ir")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--out", default="/tmp/m4_verifier_latency.json")
    a = ap.parse_args()

    from paper.verifier.l2_runtime import check as l2_check

    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            c, i = (r.get("category_v2") or "").strip(), (r.get("index") or "").strip()
            if c and i:
                rows.append((f"{c}_{i}", r))

    results, skipped = [], []
    t_all0 = time.perf_counter()
    for name, r in rows:
        p = os.path.join(a.run_dir, a.arm, f"{name}.json")
        if not os.path.exists(p):
            skipped.append((name, "no joi file"))
            continue
        d = json.load(open(p, encoding="utf-8"))
        joi = d.get("joi_block")
        if d.get("status") != "ok" or not isinstance(joi, dict):
            skipped.append((name, "no usable joi_block"))
            continue
        try:
            ir = json.loads(r["ir_gt"])
        except Exception:
            skipped.append((name, "no gt_ir"))
            continue

        try:
            l2_check(ir, joi)                      # warm-up (discarded)
            times = []
            for _ in range(a.reps):
                t0 = time.perf_counter()
                rep = l2_check(ir, joi)
                times.append((time.perf_counter() - t0) * 1000.0)  # ms
            results.append({
                "name": name,
                "ms_p50": statistics.median(times),
                "ms_min": min(times), "ms_max": max(times),
                "equivalent": bool(rep.equivalent),
                "features": ir_features(ir),
            })
        except Exception as e:
            skipped.append((name, f"{type(e).__name__}: {str(e)[:120]}"))
        sys.stdout.write(f"\r{len(results)+len(skipped)}/{len(rows)}")
        sys.stdout.flush()
    wall = time.perf_counter() - t_all0
    print()

    p50s = sorted(x["ms_p50"] for x in results)
    n = len(p50s)
    agg = {
        "n_rows": n, "reps": a.reps, "arm": a.arm,
        "ms_p50": p50s[n // 2] if n else None,
        "ms_p95": p50s[int(n * 0.95)] if n else None,
        "ms_worst": max(x["ms_max"] for x in results) if results else None,
        "ms_mean_of_p50": statistics.mean(p50s) if p50s else None,
        "wall_clock_s": round(wall, 1),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                             / (1024 * 1024 if platform.system() == "Darwin" else 1024), 1),
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "python": platform.python_version()},
        "skipped": skipped,
    }
    print(json.dumps({k: v for k, v in agg.items() if k != "skipped"},
                     ensure_ascii=False, indent=1))
    if skipped:
        print(f"skipped {len(skipped)}: {[s[0] for s in skipped][:10]} ...")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"aggregate": agg, "per_row": results}, f, ensure_ascii=False, indent=1)
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
