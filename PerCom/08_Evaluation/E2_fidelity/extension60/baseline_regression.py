"""Re-evaluate original140 Explorer decisions, retaining original separate-reference evidence.
Reference runtime sources are identical to post-R14 commit436039a (see compatibility file).
Only historical catalog directory paths are relocated; catalogue bytes verified unchanged.
"""
import argparse,copy,gzip,hashlib,json,os,sys,time,subprocess,traceback
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
HERE=Path(__file__).resolve().parent
E2=HERE.parent
ROOT=E2.parents[2]
os.environ['E2_BINDING_DECISION']='1';os.environ['E2_BINDING_ASSIGN']='1';os.environ['E2_REF_DIR']=str(E2/'reference')
sys.path[:0]=[str(E2),str(ROOT)]
import run_e2

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshots():
 paths=list((ROOT/'explorer').rglob('*.py'))+list((E2/'reference').rglob('*.py'))+[E2/'run_e2.py',Path(__file__),ROOT/'files/service_list_ver2.0.7.json',ROOT/'PerCom/08_Evaluation/E1_adequacy/breadth/depth/runs/fixture_catalog_v2.json']
 return {str(p.relative_to(ROOT)):digest(p) for p in paths if '__pycache__' not in str(p)}
def worker(pair,old):
 t=time.monotonic();row=copy.deepcopy(old);row['historical_explorer']=row.pop('explorer');row['historical_agreement']=row['agreement']
 try:
  exp=run_e2.explorer_side(pair)
  if exp.get('witness'):exp['witness_on_reference']=run_e2.witness_on_reference(pair,exp['witness'])
  row['explorer']=exp;row['agreement']=run_e2.agreement(exp,row['reference'])
 except Exception as e:
  row['explorer']={'verdict':'ERROR','reason':repr(e),'trace':traceback.format_exc()};row['agreement']='REGRESSION-HARNESS-ERROR'
 row['regression_seconds']=round(time.monotonic()-t,3);row['verdict_changed']=row['historical_explorer']['verdict']!=row['explorer']['verdict'];return row

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=8);ap.add_argument('--out',type=Path,default=HERE/'runs/baseline140_current.jsonl');a=ap.parse_args()
 oldfile=E2/'runs/e2_run.timer-binding.jsonl.gz'
 with gzip.open(oldfile,'rt')as f:old={r['pair_id']:r for r in map(json.loads,f) if r['pair_id']not in ['C03_008/llm','C20_011/llm']}
 pairs={p['pair_id']:p for name in ['e1_pairs.json','sample_388_pairs.json'] for p in json.loads((E2/'pairs'/name).read_text())['pairs'] if p['pair_id']in old}
 assert len(pairs)==len(old)==140
 for p in pairs.values():
  p['catalog']=p['catalog'].replace('PerCom/6_Evaluation','PerCom/08_Evaluation');assert (ROOT/p['catalog']).exists()
 compat=json.loads((HERE/'reference_compatibility.json').read_text())
 assert all(r['exact']for r in compat['files']if Path(r['path']).name in ['common.py','ir_ref.py','joi_ref.py','run.py','JOILangLexer.py','JOILangParser.py','JOILangListener.py'])
 a.out.parent.mkdir(exist_ok=True,parents=True);meta=a.out.with_suffix('.meta.json');snap=snapshots()
 if meta.exists():assert json.loads(meta.read_text())['source_sha256']==snap,'Runtime changed'
 else:meta.write_text(json.dumps(dict(started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),workers=a.workers,load=os.getloadavg(),source_sha256=snap,original_results_sha256=digest(oldfile),reference_reuse='Runtime source exact post-R14 commit436039a; preserve original history+supplement outcomes; replay all new witnesses.',selection='All140 admitted originalpairs; no outcome selection.',catalog_relocation='6_Evaluation -> 08_Evaluation'),indent=2)+'\n')
 done={json.loads(l)['pair_id']for l in a.out.read_text().splitlines()}if a.out.exists()else set()
 with ProcessPoolExecutor(max_workers=a.workers)as pool,a.out.open('a')as f:
  futs={pool.submit(worker,p,old[pid]):pid for pid,p in pairs.items()if pid not in done}
  for fu in as_completed(futs):
   row=fu.result();f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();print(row['pair_id'],row['explorer']['verdict'],row['agreement'],'changed',row['verdict_changed'],row['regression_seconds'],flush=True)
 assert snapshots()==snap,'Runtime mutated duringregression'
if __name__=='__main__':main()
