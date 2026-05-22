#!/usr/bin/env python3
"""Batch end-to-end JoI evaluation with/without self-correction.

For each row in dataset_migration/local_dataset2.csv:
  1. Run `generate_joi_code(NL, devices)` under both JOI_VERIFY=0 (off) and
     JOI_VERIFY=1 (on). Save the resulting (ir, joi_block, log) per row per
     mode in JOI_EVAL_DUMP_DIR/<mode>/<cat>_<idx>.json.
  2. Post-hoc grade by calling l2_runtime.check(ir_gt_from_csv, joi_block).
     L2 trace equivalence is the gating signal; we treat l2.equivalent as
     PASS, else FAIL.
  3. Write a master `_summary.json` with per-mode pass rates + per-cat
     breakdown.

Each row runs in a subprocess so the JOI_VERIFY env is isolated per call.

Usage:
    python3 paper/run_joi_eval_batch.py
    BATCH_WORKERS=4 ...                # parallel
    BATCH_CATEGORIES=C19,C20 ...       # subset
    BATCH_LIMIT=10 ...                 # cap rows (smoke)
"""
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "paper"))
CSV_PATH = os.path.join(ROOT, "dataset_migration/local_dataset2.csv")
OUT_DIR = os.environ.get("JOI_EVAL_DUMP_DIR", "/tmp/joi_eval_batch")
WORKERS = int(os.environ.get("BATCH_WORKERS", "4"))
CAT_FILTER = {c.strip() for c in os.environ.get("BATCH_CATEGORIES", "").split(",") if c.strip()}
LIMIT = int(os.environ.get("BATCH_LIMIT", "0"))
TIMEOUT_SEC = int(os.environ.get("BATCH_TIMEOUT", "240"))

# Worker spawns a subprocess that runs the full pipeline once.
WORKER_SCRIPT = r"""
import os, sys, json, re
sys.path.insert(0, os.environ['JOI_ROOT'])
sys.path.insert(0, os.path.join(os.environ['JOI_ROOT'], 'paper'))
from paper.run_local_ir import generate_joi_code, JoiGenerationError
cmd, devs, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    r = generate_joi_code(cmd, devs, {})
    code = r.get('code') or ''
    # The code is a JSON object pretty-printed with literal newlines in
    # the script field — re-pack to a parseable JSON dict.
    try:
        code_packed = re.sub(
            r'("script"\s*:\s*")(.*?)(")',
            lambda m: m.group(1) + m.group(2).replace('\n', '\\n').replace('"', '\\"') + m.group(3),
            code, count=1, flags=re.DOTALL,
        )
        joi_block = json.loads(code_packed)
    except Exception:
        joi_block = None
    out = {
        'status': 'ok',
        'ir': r.get('ir'),
        'joi_block': joi_block,
        'code_raw': code,
        'precision': r.get('precision'),
    }
except JoiGenerationError as e:
    out = {'status':'error','error_code':getattr(e,'error_code','unknown'),
           'error_msg':str(e)[:600]}
except Exception as e:
    out = {'status':'error','error_code':'exception',
           'error_msg':f'{type(e).__name__}: {str(e)[:600]}'}

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('OK' if out['status']=='ok' else 'ERR', out_path)
"""


def load_rows():
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cat = (r.get("category_v2") or "").strip()
            if not cat: continue
            if CAT_FILTER and cat not in CAT_FILTER: continue
            rows.append({
                "index": (r.get("index") or "").strip(),
                "category": cat,
                "command_eng": r.get("command_eng",""),
                "connected_devices": r.get("connected_devices",""),
                "ir_gt": r.get("ir_gt","").strip(),
            })
    if LIMIT: rows = rows[:LIMIT]
    return rows


def call_one(row, mode):
    """mode: 'off' (JOI_VERIFY=0) or 'on' (JOI_VERIFY=1)."""
    name = f"{row['category']}_{row['index']}"
    mode_dir = os.path.join(OUT_DIR, mode)
    os.makedirs(mode_dir, exist_ok=True)
    out_path = os.path.join(mode_dir, f"{name}.json")
    env = os.environ.copy()
    env["JOI_ROOT"] = ROOT
    env["JOI_VERIFY"] = "1" if mode == "on" else "0"
    env.pop("JOI_IR_ONLY", None)
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [sys.executable, "-c", WORKER_SCRIPT,
             row["command_eng"], row["connected_devices"], out_path],
            env=env, capture_output=True, text=True, timeout=TIMEOUT_SEC,
        )
        elapsed = time.perf_counter() - t0
        ok = os.path.exists(out_path)
        return {"name": name, "mode": mode, "path": out_path,
                "ok": ok, "elapsed": elapsed,
                "stderr_tail": (p.stderr or "")[-300:] if not ok else ""}
    except subprocess.TimeoutExpired:
        return {"name": name, "mode": mode, "path": out_path,
                "ok": False, "elapsed": float(TIMEOUT_SEC),
                "stderr_tail": f"timeout-{TIMEOUT_SEC}s"}


def grade_one(row, mode):
    """Run l2.check(ir_gt, joi_block) → equivalent? Returns dict."""
    name = f"{row['category']}_{row['index']}"
    out_path = os.path.join(OUT_DIR, mode, f"{name}.json")
    if not os.path.exists(out_path):
        return {"verdict": "missing"}
    try:
        d = json.load(open(out_path, encoding="utf-8"))
    except Exception as e:
        return {"verdict": "missing", "msg": f"unread: {e}"}
    if d.get("status") != "ok":
        return {"verdict": "error",
                "error_code": d.get("error_code",""),
                "msg": d.get("error_msg","")[:200]}
    joi_block = d.get("joi_block")
    if not isinstance(joi_block, dict):
        return {"verdict": "fail", "msg": "joi_block missing/unparseable"}
    if not row["ir_gt"]:
        return {"verdict": "no_gt"}
    try:
        ir_gt = json.loads(row["ir_gt"])
    except Exception:
        return {"verdict": "no_gt", "msg": "ir_gt parse error"}
    try:
        from paper.verifier.l2_runtime import check as l2_check
        rep = l2_check(ir_gt, joi_block)
        if rep.equivalent:
            return {"verdict": "pass"}
        return {"verdict": "fail",
                "msg": "; ".join(v.kind for v in rep.violations)[:200]}
    except Exception as e:
        return {"verdict": "fail", "msg": f"l2 exception: {type(e).__name__}: {str(e)[:200]}"}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = load_rows()
    print(f"[joi-eval] {len(rows)} rows; workers={WORKERS}; out={OUT_DIR}")
    t0 = time.perf_counter()

    runs = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {}
        for r in rows:
            for mode in ("off", "on"):
                futures[ex.submit(call_one, r, mode)] = (r, mode)
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            runs.append(res)
            if i % 20 == 0 or not res["ok"]:
                print(f"  [{i}/{len(futures)}] [{res['mode']:3}] {res['name']}  ({res['elapsed']:.1f}s)"
                      + ("" if res["ok"] else f"  {res['stderr_tail'][:80]}"))

    print(f"\n[joi-eval] all subprocess runs done in {time.perf_counter()-t0:.1f}s; grading...")

    # Grade
    by_row = {f"{r['category']}_{r['index']}": r for r in rows}
    grades = {"off": {}, "on": {}}
    for mode in ("off", "on"):
        for r in rows:
            name = f"{r['category']}_{r['index']}"
            grades[mode][name] = grade_one(r, mode)

    # Tally
    def tally(mode_grades):
        c = {"pass":0,"fail":0,"error":0,"no_gt":0,"missing":0}
        per_cat = {}
        for name, g in mode_grades.items():
            cat = name.rsplit("_",1)[0]
            per_cat.setdefault(cat, {"pass":0,"fail":0,"error":0,"no_gt":0,"missing":0})
            v = g["verdict"]
            c[v] = c.get(v,0)+1
            per_cat[cat][v] = per_cat[cat].get(v,0)+1
        return c, per_cat

    off_total, off_cat = tally(grades["off"])
    on_total,  on_cat  = tally(grades["on"])

    print("\n" + "="*72)
    print("Mode comparison (350 rows, l2 trace-equivalence as PASS signal)")
    print("="*72)
    n = len(rows)
    print(f"{'mode':<5} {'PASS':>6} {'FAIL':>6} {'ERR':>6} {'NoGT':>6} {'MISS':>6}  PASS%")
    for mode, t in (("off", off_total), ("on", on_total)):
        p = t.get("pass",0); pct = 100*p/n if n else 0
        print(f"{mode:<5} {p:>6} {t.get('fail',0):>6} {t.get('error',0):>6} {t.get('no_gt',0):>6} {t.get('missing',0):>6}  {pct:>5.1f}%")

    print("\nPer-category:")
    cats = sorted(set(off_cat) | set(on_cat))
    print(f"  {'cat':<5} {'off_PASS':>9} {'on_PASS':>9} {'Δ':>5}  total")
    for c in cats:
        op = off_cat.get(c,{}).get("pass",0)
        np_ = on_cat.get(c,{}).get("pass",0)
        tot = sum(off_cat.get(c,{}).values())
        print(f"  {c:<5} {op:>9} {np_:>9} {np_-op:>+5}  /{tot}")

    summary_path = os.path.join(OUT_DIR, "_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "n_rows": n,
            "off_totals": off_total, "off_per_cat": off_cat,
            "on_totals": on_total,   "on_per_cat": on_cat,
            "grades": grades,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[joi-eval] summary -> {summary_path}")


if __name__ == "__main__":
    main()
