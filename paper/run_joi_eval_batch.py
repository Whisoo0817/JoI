#!/usr/bin/env python3
"""Batch end-to-end JoI evaluation with/without self-correction.

For each row in dataset.csv:
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
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "paper"))
CSV_PATH = os.path.join(ROOT, "dataset.csv")
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
        'verifier_trace': r.get('verifier_trace'),
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


def _grade_block(ir_gt, joi_block):
    """Grade a single joi_block dict against ir_gt → 'pass' | 'fail'.

    Unlike grade_one (which scores the *dumped final* block), this scores an
    arbitrary block — used to score attempt-1 vs final from verifier_trace so
    the confusion matrix can separate detection from recovery.
    """
    if not isinstance(joi_block, dict):
        return "fail"
    try:
        from paper.verifier.l2_runtime import check as l2_check
        rep = l2_check(ir_gt, joi_block)
        return "pass" if rep.equivalent else "fail"
    except Exception:
        return "fail"


def build_confusion(rows, out_dir=None):
    """Verifier-intrinsic confusion matrix + recovery breakdown, computed from
    the on-mode dump's verifier_trace. All scoring is against ir_gt.
    `out_dir` defaults to this module's OUT_DIR; the Stage-B runner passes its
    own dump dir so the same aggregation serves both batches.

    Detector matrix (prediction = internal verifier flagged attempt-1;
    truth = attempt-1 block is actually wrong vs ir_gt):
      TP flagged & wrong | FP flagged & correct | FN missed & wrong | TN clean & correct
    Recovery (attempt-1 → final, on-mode internal retry):
      helped wrong→correct | hurt correct→wrong | both_correct | both_wrong
    """
    cm = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
    rec = {"helped": 0, "hurt": 0, "both_correct": 0, "both_wrong": 0}
    kind_flagged = Counter()       # attempt-1 violation kinds, all rows
    kind_helped = Counter()        # attempt-1 kinds on rows that recovered
    kind_hurt = Counter()          # attempt-1 kinds on rows that regressed
    # Wrong-but-unflagged (FN) split: the verifier judges the JoI against the
    # *internal* (pipeline-extracted) IR, but grading is vs ir_gt. So a wrong
    # row the verifier didn't flag is one of two very different things:
    #   upstream_ir : JoI faithfully matches the internal IR, but the internal
    #                 IR itself diverged from ir_gt → an IR-extraction error,
    #                 NOT a verifier/lowering miss. The verifier is correct to
    #                 stay silent (IR is its spec).
    #   verifier_miss: JoI diverges even from its own internal IR yet L2 stayed
    #                 silent → a true verifier insensitivity (the cell that LLM
    #                 diagnose / L2 hardening should target).
    fn_split = {"upstream_ir": 0, "verifier_miss": 0}
    n_scored = 0
    detail = []
    base = out_dir or OUT_DIR
    for r in rows:
        name = f"{r['category']}_{r['index']}"
        path = os.path.join(base, "on", f"{name}.json")
        if not os.path.exists(path):
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if d.get("status") != "ok" or not r["ir_gt"]:
            continue
        try:
            ir_gt = json.loads(r["ir_gt"])
        except Exception:
            continue
        vt = d.get("verifier_trace") or {}
        atts = vt.get("attempts") or []
        if not vt.get("enabled") or not atts:
            continue
        n_scored += 1

        a1 = atts[0]
        a1_kinds = list(a1.get("l1_kinds", [])) + list(a1.get("l2_kinds", []))
        flagged = (a1.get("l1_count", 0) + a1.get("l2_count", 0)) > 0
        a1_correct = _grade_block(ir_gt, a1.get("joi_block")) == "pass"
        final_correct = _grade_block(ir_gt, atts[-1].get("joi_block")) == "pass"

        for k in a1_kinds:
            kind_flagged[k] += 1

        fn_kind = None
        if flagged and not a1_correct:
            cm["TP"] += 1
        elif flagged and a1_correct:
            cm["FP"] += 1
        elif not flagged and not a1_correct:
            cm["FN"] += 1
            # Split FN: did attempt-1 JoI match its OWN internal IR?
            internal_ir = d.get("ir") or {}
            a1_vs_internal = _grade_block(internal_ir, a1.get("joi_block")) == "pass"
            fn_kind = "upstream_ir" if a1_vs_internal else "verifier_miss"
            fn_split[fn_kind] += 1
        else:
            cm["TN"] += 1

        if not a1_correct and final_correct:
            rec["helped"] += 1
            for k in a1_kinds:
                kind_helped[k] += 1
        elif a1_correct and not final_correct:
            rec["hurt"] += 1
            for k in a1_kinds:
                kind_hurt[k] += 1
        elif a1_correct and final_correct:
            rec["both_correct"] += 1
        else:
            rec["both_wrong"] += 1

        detail.append({
            "name": name, "flagged": flagged, "a1_kinds": a1_kinds,
            "a1_correct": a1_correct, "final_correct": final_correct,
            "fn_kind": fn_kind, "n_attempts": len(atts),
        })
    return {
        "n_scored": n_scored,
        "matrix": cm,
        "fn_split": fn_split,
        "recovery": rec,
        "kind_flagged": dict(kind_flagged),
        "kind_helped": dict(kind_helped),
        "kind_hurt": dict(kind_hurt),
        "detail": detail,
    }


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

    # Verifier-intrinsic confusion matrix + recovery (on-mode, vs ir_gt).
    conf = build_confusion(rows)
    cm, rc = conf["matrix"], conf["recovery"]
    tp, fp, fn, tn = cm["TP"], cm["FP"], cm["FN"], cm["TN"]
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    print("\n" + "="*72)
    print(f"Verifier detector matrix (on-mode, attempt-1 vs ir_gt; n={conf['n_scored']})")
    print("="*72)
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}   precision={prec:.2f} recall={recall:.2f}")
    fs = conf["fn_split"]
    print(f"  FN split: upstream_ir(JoI matches a wrong internal IR)={fs['upstream_ir']}  "
          f"verifier_miss(JoI diverges from own IR, L2 silent)={fs['verifier_miss']}")
    print(f"  recovery: helped(wrong→correct)={rc['helped']}  hurt(correct→wrong)={rc['hurt']}  "
          f"both_correct={rc['both_correct']}  both_wrong={rc['both_wrong']}")
    if conf["kind_flagged"]:
        print("  attempt-1 flagged kinds:", dict(sorted(conf["kind_flagged"].items(),
                                                        key=lambda kv: -kv[1])))
        print("    of which helped:", conf["kind_helped"] or "{}")
        print("    of which hurt:  ", conf["kind_hurt"] or "{}")

    summary_path = os.path.join(OUT_DIR, "_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "n_rows": n,
            "off_totals": off_total, "off_per_cat": off_cat,
            "on_totals": on_total,   "on_per_cat": on_cat,
            "confusion": conf,
            "grades": grades,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[joi-eval] summary -> {summary_path}")


if __name__ == "__main__":
    main()
