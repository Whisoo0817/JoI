import os,sys,json,time,traceback,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent; E2=HERE.parent;ROOT=E2.parents[2]
os.environ.update(E2_BINDING_DECISION='1',E2_BINDING_ASSIGN='1',E2_REF_DIR=str(E2/'reference'))
sys.path[:0]=[str(E2),str(ROOT),str(E2.parent/'E1_adequacy/breadth/depth')]
import run_e2
from explorer.verification import timed
original=timed.timed_product
run_e2.BUDGET_S=0
ACTIVE={}
def concrete_search(a,b,**kwargs):
 keys=set(a.axes.cells)|set(b.axes.cells)
 domains={}
 for k in keys:
  if k.startswith('clock.'): domains[k]=list(range(24)) if k=='clock.hour' else [0]
  elif k.endswith('.channel'):domains[k]=[1]
  elif 'Pool_PH' in k:domains[k]=[7.0]
  elif 'Pool_Chlorine' in k:domains[k]=[2.0]
  else:raise ValueError(('Unexpected input',k))
 ACTIVE['domains']=domains
 kwargs.update(input_domains=domains,horizon_ms=ACTIVE['horizon_ms'])
 return original(a,b,**kwargs)
timed.timed_product=concrete_search
pairs=[]
for file,pid in [('extension60/llm/pairs.json','C01_006/llm'),('extension60/e1/pairs.json','E1-095/ext60-fault2')]:
 pairs.append(next(p for p in json.loads((E2/file).read_text())['pairs'] if p['pair_id']==pid))
(HERE/'inputs.json').write_text(json.dumps(pairs,indent=2))
(HERE/'protocol.json').write_text(json.dumps(dict(purpose='Find and independently replay concrete divergences for two previously refused pairs.',policy='No catalog or program changes. Explicit singleton sensor values are witness-search inputs, not asserted real-world bounds. A witness proves divergence; absence of a witness does not establish full-domain equivalence.',domains={'channel':[1],'pH':[7.0],'chlorine':[2.0]},horizons_ms=[1000,18002000]),indent=2))
with (HERE/'results.jsonl').open('x') as out:
 for pair in pairs:
  ACTIVE.clear();ACTIVE['horizon_ms']=1000 if pair['pair_id'].startswith('C01') else 18002000
  print('START',pair['pair_id'],flush=True);started=time.time()
  try:
   exp=run_e2.explorer_side(pair)
   if exp.get('witness'):exp['witness_on_reference']=run_e2.witness_on_reference(pair,exp['witness'])
   result=dict(pair_id=pair['pair_id'],explorer=exp,settings=dict(ACTIVE),elapsed_s=time.time()-started)
  except Exception:result=dict(pair_id=pair['pair_id'],error=traceback.format_exc(),settings=dict(ACTIVE))
  out.write(json.dumps(result,ensure_ascii=False)+'\n');out.flush();print('DONE',json.dumps(result,ensure_ascii=False)[:1800],flush=True)
