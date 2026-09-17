"""Run a frozen remaining72 batch on the unchanged reference IR runner.
Usage: ~/temp/bin/python run_batch.py batch_community [E1-078 ...]
"""
from pathlib import Path
import sys, json, hashlib, importlib.util, traceback, time, shutil, datetime
HERE=Path(__file__).resolve().parent
DEPTH=HERE.parent/'depth'
E1=HERE.parents[1]
ROOT=HERE.parents[4]
for p in (ROOT,E1,DEPTH): sys.path.insert(0,str(p))
import run_depth as R
import fixture_v2
from timeline_ir.timeline_ir import validate_ir, validate_ir_against_catalog
from timeline_ir.catalog import load_catalog
from grammar_check import check_ir

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
 batch=Path(sys.argv[1]); batch=batch if batch.is_absolute() else HERE/batch
 sys.path.insert(0,str(batch))
 # Check whichever manifest convention a batch used before executing.
 manifests=list(batch.glob('FREEZE*.json'))
 assert manifests, 'missing pre-encoding freeze manifest'
 hashes=[]
 for mf in manifests:
  record=json.loads(mf.read_text())
  if 'cases_sha256' in record:hashes.append(record['cases_sha256'])
  if isinstance(record.get('files'),dict):
   v=record['files'].get('cases.py')
   if isinstance(v,str):hashes.append(v)
  if isinstance(record.get('sha256'),dict):
   v=record['sha256'].get('cases.py')
   if isinstance(v,str):hashes.append(v)
 if hashes:assert hashlib.sha256((batch/'cases.py').read_bytes()).hexdigest() in hashes, 'frozen cases.py changed'
 c=load('batch_cases',batch/'cases.py'); a=load('batch_attempts',batch/'attempts.py')
 base=json.loads(fixture_v2.fixture.BASE.read_text())
 stubs=fixture_v2.STUBS_V2+getattr(c,'STUBS',[])
 catalog_obj={'skills':base['skills']+stubs}
 ids=[s['id'].lower() for s in catalog_obj['skills']]
 assert len(ids)==len(set(ids)), 'duplicate fixture skill ID'
 out=batch/'runs';out.mkdir(exist_ok=True)
 artifacts=out/'artifacts';artifacts.mkdir(exist_ok=True)
 for src in [batch/'cases.py',batch/'attempts.py',Path(__file__),DEPTH/'run_depth.py']:
  sha=hashlib.sha256(src.read_bytes()).hexdigest()
  target=artifacts/(src.stem+'_'+sha+src.suffix)
  if not target.exists():shutil.copy2(src,target)
 cp=out/'catalog.json';cp.write_text(json.dumps(catalog_obj,indent=1))
 cat=load_catalog(str(cp)); rows=[]; selected=set(sys.argv[2:])
 result_path=out/'results.json'
 if result_path.exists():
  stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%f')
  archive=out/'archive'/stamp;archive.mkdir(parents=True)
  shutil.copy2(result_path,archive/'results.json');shutil.copy2(batch/'attempts.py',archive/'attempts_at_rerun.py')
  if selected:rows=json.loads(result_path.read_text())
 for case in c.CASES:
  cid=case['id']
  if selected and cid not in selected:continue
  entry=a.ATTEMPTS[cid];t0=time.monotonic()
  row={'id':cid,'label':entry['label'],'label_reason':entry['label_reason'],'interpretation_origin':'agent-derived from source and prior20 conventions','automations':[],'explorer':'not run (separate from E1)','joi_fallback':entry.get('joi_fallback','not required for complete encoding')}
  try:
   lowered=[]
   for auto in entry['automations']:
    ir,binding=R.lower(auto['ir']);info={'name':auto['name'],'ir':ir,'binding':binding,'extractor_grammar_outside':check_ir(ir)}
    validate_ir(ir);validate_ir_against_catalog(ir,cat);info['frontend']='accepted'
    _,erased=R.compile_pair(ir,binding,case['devices'],str(cp));info['cron_anchor_erased']=erased;info['runner']='compiled';lowered.append((ir,binding));row['automations'].append(info)
   def factory():return [R.compile_pair(ir,b,case['devices'],str(cp))[0].ir_runner for ir,b in lowered]
   hist=[]
   for h in case['histories']:
    one=dict(case,histories=[h],t_start_ms=h.get('t_start_ms',case['t_start_ms']))
    hr,_,_=R.run_histories(one,factory);hist.extend(hr)
   row['histories']=hist
   row['match']=f"{sum(h['match'] for h in hist)}/{len(hist)}"
   row['exact']=f"{sum(h['exact'] for h in hist)}/{len(hist)}"
   for h in hist:
    if 'actual' in h:
     h['ordered_exact']=len(h['expected'])==len(h['actual']) and all(e==a[:5] for e,a in zip(h['expected'],h['actual']))
   row['realized_outcome']=entry['label'] if all(h['exact'] for h in hist) else 'not fully reproduced; inspect failures' 
  except Exception:row['error']=traceback.format_exc()
  row['elapsed_seconds']=round(time.monotonic()-t0,3)
  row['cases_sha256']=hashlib.sha256((batch/'cases.py').read_bytes()).hexdigest()
  row['attempts_sha256']=hashlib.sha256((batch/'attempts.py').read_bytes()).hexdigest()
  row['runner_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
  row['reference_replay_sha256']=hashlib.sha256((DEPTH/'run_depth.py').read_bytes()).hexdigest()
  rows=[r for r in rows if r['id']!=cid]+[row];rows.sort(key=lambda r:r['id'])
  result_path.write_text(json.dumps(rows,indent=1,ensure_ascii=False,default=str))
  print(cid,row.get('match','ERROR'),row.get('exact','ERROR'),row['elapsed_seconds'],flush=True)
  if row.get('error'):print(row['error'],flush=True)
  for h in row.get('histories',[]):
   if not h['exact']:print('MISMATCH',h,flush=True)
 if not selected:
  print('TOTAL',len(rows),'cases',sum(len(r.get('histories',[])) for r in rows),'histories',flush=True)
if __name__=='__main__':main()
