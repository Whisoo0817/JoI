#!/usr/bin/env python3
"""Stage-B batch: lowering eval given GT IR (paper §7.3).

For each row: write GT IR to a tmp file, set JOI_GT_IR_PATH, run
generate_joi_code. extract_ir is bypassed; lowering operates on GT IR.
Run twice (JOI_VERIFY=0 / =1). Grade by l2_runtime.check(gt_ir, joi).

Output dir layout:
  JOI_LOWER_GT_DUMP_DIR/off/<cat>_<idx>.json
  JOI_LOWER_GT_DUMP_DIR/on/<cat>_<idx>.json
  JOI_LOWER_GT_DUMP_DIR/gt_ir/<cat>_<idx>.json
  JOI_LOWER_GT_DUMP_DIR/_summary.json
"""
import csv, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "paper"))
CSV_PATH = os.path.join(ROOT, "dataset_migration/local_dataset2.csv")
OUT_DIR = os.environ.get("JOI_LOWER_GT_DUMP_DIR", "/tmp/joi_lower_gt_batch")
WORKERS = int(os.environ.get("BATCH_WORKERS", "4"))
CAT_FILTER = {c.strip() for c in os.environ.get("BATCH_CATEGORIES","").split(",") if c.strip()}
LIMIT = int(os.environ.get("BATCH_LIMIT","0"))
TIMEOUT_SEC = int(os.environ.get("BATCH_TIMEOUT","240"))

WORKER_SCRIPT = r"""
import os, sys, json, re
sys.path.insert(0, os.environ['JOI_ROOT'])
sys.path.insert(0, os.path.join(os.environ['JOI_ROOT'], 'paper'))
from paper.run_local_ir import generate_joi_code, JoiGenerationError
cmd, devs, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    r = generate_joi_code(cmd, devs, {})
    code = r.get('code') or ''
    try:
        code_packed = re.sub(
            r'("script"\s*:\s*")(.*?)(")',
            lambda m: m.group(1) + m.group(2).replace('\n','\\n').replace('"','\\"') + m.group(3),
            code, count=1, flags=re.DOTALL,
        )
        joi_block = json.loads(code_packed)
    except Exception:
        joi_block = None
    out = {'status':'ok','ir':r.get('ir'),'joi_block':joi_block,'code_raw':code,
           'precision':r.get('precision')}
except JoiGenerationError as e:
    out = {'status':'error','error_code':getattr(e,'error_code','unknown'),
           'error_msg':str(e)[:600]}
except Exception as e:
    out = {'status':'error','error_code':'exception',
           'error_msg':f'{type(e).__name__}: {str(e)[:600]}'}
with open(out_path,'w',encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('OK' if out['status']=='ok' else 'ERR', out_path)
"""


def load_rows():
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cat=(r.get("category_v2") or "").strip()
            if not cat: continue
            if CAT_FILTER and cat not in CAT_FILTER: continue
            if not (r.get("ir_gt") or "").strip(): continue
            rows.append({
                "index":(r.get("index") or "").strip(),
                "category":cat,
                "command_eng":r.get("command_eng",""),
                "connected_devices":r.get("connected_devices",""),
                "ir_gt":r.get("ir_gt",""),
            })
    if LIMIT: rows=rows[:LIMIT]
    return rows


def call_one(row, mode, gt_path):
    name = f"{row['category']}_{row['index']}"
    mode_dir = os.path.join(OUT_DIR, mode)
    os.makedirs(mode_dir, exist_ok=True)
    out_path = os.path.join(mode_dir, f"{name}.json")
    env = os.environ.copy()
    env["JOI_ROOT"] = ROOT
    env["JOI_VERIFY"] = "1" if mode=="on" else "0"
    env["JOI_GT_IR_PATH"] = gt_path
    env.pop("JOI_IR_ONLY", None)
    t0=time.perf_counter()
    try:
        p = subprocess.run(
            [sys.executable, "-c", WORKER_SCRIPT,
             row["command_eng"], row["connected_devices"], out_path],
            env=env, capture_output=True, text=True, timeout=TIMEOUT_SEC,
        )
        elapsed = time.perf_counter()-t0
        return {"name":name,"mode":mode,"path":out_path,
                "ok":os.path.exists(out_path),"elapsed":elapsed,
                "stderr_tail":(p.stderr or "")[-300:] if not os.path.exists(out_path) else ""}
    except subprocess.TimeoutExpired:
        return {"name":name,"mode":mode,"path":out_path,"ok":False,
                "elapsed":float(TIMEOUT_SEC),"stderr_tail":f"timeout-{TIMEOUT_SEC}s"}


def grade_one(row, mode):
    name=f"{row['category']}_{row['index']}"
    out_path=os.path.join(OUT_DIR, mode, f"{name}.json")
    if not os.path.exists(out_path): return {"verdict":"missing"}
    try: d=json.load(open(out_path,encoding="utf-8"))
    except Exception as e: return {"verdict":"missing","msg":str(e)}
    if d.get("status")!="ok":
        return {"verdict":"error","error_code":d.get("error_code",""),
                "msg":d.get("error_msg","")[:200]}
    joi_block=d.get("joi_block")
    if not isinstance(joi_block,dict):
        return {"verdict":"fail","msg":"joi_block missing"}
    try: ir_gt=json.loads(row["ir_gt"])
    except Exception: return {"verdict":"no_gt"}
    try:
        from paper.verifier.l2_runtime import check as l2_check
        rep=l2_check(ir_gt, joi_block)
        return {"verdict":"pass" if rep.equivalent else "fail",
                "msg":"; ".join(v.kind for v in rep.violations)[:200] if not rep.equivalent else ""}
    except Exception as e:
        return {"verdict":"fail","msg":f"l2 exception: {type(e).__name__}: {str(e)[:200]}"}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    gt_dir = os.path.join(OUT_DIR, "gt_ir")
    os.makedirs(gt_dir, exist_ok=True)
    rows = load_rows()
    print(f"[lower-gt] {len(rows)} rows; workers={WORKERS}; out={OUT_DIR}")

    # Write GT IR files
    for r in rows:
        name=f"{r['category']}_{r['index']}"
        json.dump(json.loads(r["ir_gt"]),
                  open(os.path.join(gt_dir, f"{name}.json"),"w",encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    t0=time.perf_counter()
    runs=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={}
        for r in rows:
            name=f"{r['category']}_{r['index']}"
            gt_path=os.path.join(gt_dir, f"{name}.json")
            for mode in ("off","on"):
                futs[ex.submit(call_one, r, mode, gt_path)]=(r, mode)
        for i, fut in enumerate(as_completed(futs), 1):
            res=fut.result(); runs.append(res)
            if i%20==0 or not res["ok"]:
                msg=f"  [{i}/{len(futs)}] [{res['mode']:3}] {res['name']} ({res['elapsed']:.1f}s)"
                if not res["ok"]: msg+=f"  {res['stderr_tail'][:80]}"
                print(msg)

    print(f"\n[lower-gt] all subprocess runs done in {time.perf_counter()-t0:.1f}s; grading...")

    grades={"off":{},"on":{}}
    for mode in ("off","on"):
        for r in rows:
            grades[mode][f"{r['category']}_{r['index']}"] = grade_one(r, mode)

    def tally(mg):
        c={"pass":0,"fail":0,"error":0,"no_gt":0,"missing":0}
        pc={}
        for name,g in mg.items():
            cat=name.rsplit("_",1)[0]
            pc.setdefault(cat,{"pass":0,"fail":0,"error":0,"no_gt":0,"missing":0})
            v=g["verdict"]; c[v]=c.get(v,0)+1; pc[cat][v]=pc[cat].get(v,0)+1
        return c, pc

    ot,oc=tally(grades["off"]); nt,nc=tally(grades["on"])
    n=len(rows)
    print("\n"+"="*72)
    print("Stage B: lowering w/ GT IR (verifier off vs on)")
    print("="*72)
    print(f"{'mode':<5} {'PASS':>6} {'FAIL':>6} {'ERR':>6} {'NoGT':>6} {'MISS':>6}  PASS%")
    for mode,t in (("off",ot),("on",nt)):
        p=t.get("pass",0); pct=100*p/n if n else 0
        print(f"{mode:<5} {p:>6} {t.get('fail',0):>6} {t.get('error',0):>6} {t.get('no_gt',0):>6} {t.get('missing',0):>6}  {pct:>5.1f}%")
    print("\nPer-category:")
    cats=sorted(set(oc)|set(nc))
    print(f"  {'cat':<5} {'off':>5} {'on':>5} {'Δ':>4}  /tot")
    for c in cats:
        op=oc.get(c,{}).get("pass",0); np_=nc.get(c,{}).get("pass",0)
        tot=sum(oc.get(c,{}).values())
        print(f"  {c:<5} {op:>5} {np_:>5} {np_-op:>+4}  /{tot}")

    sp=os.path.join(OUT_DIR,"_summary.json")
    json.dump({"n_rows":n,"off":ot,"on":nt,"off_per_cat":oc,"on_per_cat":nc,
              "grades":grades},open(sp,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(f"\n[lower-gt] summary -> {sp}")

if __name__=="__main__":
    main()
