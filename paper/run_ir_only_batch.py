#!/usr/bin/env python3
"""Batch IR-only runner.

Walks all rows in dataset.csv and, for each row, spawns a subprocess
running the JoI pipeline with JOI_IR_ONLY=1. The subprocess writes a per-row
dump JSON to JOI_IR_DUMP_DIR. After all rows finish, this script writes a
master `_index.json` summarizing status per row + per category.

Subprocess (rather than threads) is used so each row gets its own env (the
dump filename is set via env var read at import-time of run_local_ir, which
would race with threads).

Usage:
    python3 paper/run_ir_only_batch.py                 # all rows
    JOI_IR_DUMP_DIR=/tmp/run_x python3 ...             # override out dir
    BATCH_WORKERS=8 python3 ...                        # parallel workers
    BATCH_CATEGORIES=C01,C20 python3 ...               # subset
    BATCH_LIMIT=10 python3 ...                         # cap total rows (smoke)
"""
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "dataset.csv")
OUT_DIR = os.environ.get("JOI_IR_DUMP_DIR", "/tmp/joi_ir_dump_batch")
WORKERS = int(os.environ.get("BATCH_WORKERS", "4"))
CAT_FILTER = {c.strip() for c in os.environ.get("BATCH_CATEGORIES", "").split(",") if c.strip()}
LIMIT = int(os.environ.get("BATCH_LIMIT", "0"))
TIMEOUT_SEC = int(os.environ.get("BATCH_TIMEOUT", "180"))

WORKER_SCRIPT = """
import os, sys, json
sys.path.insert(0, os.environ['JOI_ROOT'])
from paper.run_local_ir import generate_joi_code, JoiGenerationError
cmd, devs = sys.argv[1], sys.argv[2]
try:
    r = generate_joi_code(cmd, devs, {})
    print('OK', r.get('ir_dump_path'))
except JoiGenerationError as e:
    print('ERR', getattr(e, 'error_code', 'unknown'), str(e)[:300].replace('\\n',' '))
except Exception as e:
    print('EXC', type(e).__name__, str(e)[:300].replace('\\n',' '))
"""


def load_rows():
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            cat = (r.get("category_v2") or "").strip()
            if not cat:
                continue
            if CAT_FILTER and cat not in CAT_FILTER:
                continue
            rows.append({
                "index": (r.get("index") or "").strip(),
                "category": cat,
                "command_eng": r.get("command_eng", ""),
                "connected_devices": r.get("connected_devices", ""),
            })
    if LIMIT:
        rows = rows[:LIMIT]
    return rows


def call_subproc(r):
    name = f"{r['category']}_{r['index']}"
    env = os.environ.copy()
    env["JOI_IR_ONLY"] = "1"
    env["JOI_IR_DUMP_DIR"] = OUT_DIR
    env["JOI_IR_DUMP_NAME"] = name
    env["JOI_ROOT"] = ROOT
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [sys.executable, "-c", WORKER_SCRIPT, r["command_eng"], r["connected_devices"]],
            env=env, capture_output=True, text=True, timeout=TIMEOUT_SEC,
        )
        elapsed = time.perf_counter() - t0
        last = ((p.stdout or "").strip().splitlines() or [""])[-1]
        if last.startswith("OK "):
            return {"name": name, "category": r["category"], "index": r["index"],
                    "status": "ok", "dump_path": last[3:].strip(), "elapsed": elapsed}
        return {"name": name, "category": r["category"], "index": r["index"],
                "status": "error",
                "error_msg": last or (p.stderr or "")[:400],
                "elapsed": elapsed}
    except subprocess.TimeoutExpired:
        return {"name": name, "category": r["category"], "index": r["index"],
                "status": "error", "error_msg": f"timeout-{TIMEOUT_SEC}s",
                "elapsed": float(TIMEOUT_SEC)}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = load_rows()
    print(f"[batch] loaded {len(rows)} rows; out_dir={OUT_DIR}; workers={WORKERS}")
    t0 = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(call_subproc, r): r for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            results.append(res)
            if i % 10 == 0 or res["status"] != "ok":
                msg = f"  [{i}/{len(rows)}] [{res['status']}] {res['name']}  ({res['elapsed']:.1f}s)"
                if res["status"] != "ok":
                    msg += f"  {res.get('error_msg','')[:100]}"
                print(msg)

    total = time.perf_counter() - t0
    ok = sum(1 for r in results if r["status"] == "ok")
    err = len(results) - ok
    by_cat = {}
    for r in results:
        c = r["category"]
        by_cat.setdefault(c, {"ok": 0, "err": 0})
        by_cat[c]["ok" if r["status"] == "ok" else "err"] += 1

    index_path = os.path.join(OUT_DIR, "_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(results),
            "ok": ok,
            "error": err,
            "elapsed_total_seconds": total,
            "by_category": by_cat,
            "rows": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[batch] done: {ok}/{len(results)} OK, {err} errors in {total:.1f}s")
    print(f"[batch] index: {index_path}")


if __name__ == "__main__":
    main()
