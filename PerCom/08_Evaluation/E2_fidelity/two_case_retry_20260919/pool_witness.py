"""Concrete counterexample search; does not claim an exhaustive Explorer verdict."""
import os,sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;E2=HERE.parent;ROOT=E2.parents[2]
os.environ.update(E2_BINDING_DECISION='1',E2_BINDING_ASSIGN='1',E2_REF_DIR=str(E2/'reference'))
sys.path[:0]=[str(E2),str(ROOT),str(E2.parent/'E1_adequacy/breadth/depth')]
import run_e2
from run_depth import lower
from explorer.verification.gate import prepare_pair
from explorer.verification.observation import observation_scope,actions_observation
p=next(p for p in json.loads((HERE/'inputs.json').read_text()) if p['pair_id']=='E1-095/ext60-fault2')
ir,binding=lower(p['ir'])
prepared=prepare_pair(ir,binding,p['devices'],p['joi'],service_catalog=str(ROOT/p['catalog']),selector_binding=True)
a,b=prepared.ir_runner,prepared.code_runner
av,ag,bv,bg={},{},{},{}
world={'Pool_PH.value':7.0,'Pool_Chlorine.value':2.0}
t0=run_e2.T0_EXPLORER+p['t_start_ms'];trace=[];t=time.time();found=None
with observation_scope(a,b):
 for elapsed in range(0,18002001,100):
  ra=a.step(av,ag,world,t0+elapsed,first_tick=elapsed==0)
  rb=b.step(bv,bg,world,t0+elapsed,first_tick=elapsed==0)
  oa,ob=actions_observation(ra.actions),actions_observation(rb.actions)
  if ra.actions or rb.actions:print('ACTION',elapsed,repr(oa),repr(ob),flush=True)
  if oa!=ob:
   found={'elapsed_ms':elapsed,'actions_ir':repr(oa),'actions_joi':repr(ob)};break
  av,ag,bv,bg=ra.vars,ra.gv,rb.vars,rb.gv
assert found is not None,'No difference on chosen finite history'
# A constant input held from start through the differing action; independent reference replay.
witness={'path':[[world,0],[world,found['elapsed_ms']]],'t0_ms':t0}
reference=run_e2.witness_on_reference(p,witness)
result=dict(pair_id=p['pair_id'],method='Concrete execution on the original 100 ms input grid using Explorer internal interpreters; not exhaustive timed_product exploration',witness=witness,difference=found,independent_reference=reference,wall_seconds=time.time()-t)
(HERE/'pool_concrete_witness.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False),flush=True)
