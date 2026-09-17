"""Replay frozen core and rolling-expiry cases using the unchanged reference runtime."""
from pathlib import Path
import sys,json,hashlib,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import run_batch as B
CASE=B.load('rolling_cases',HERE/'cases.py').CASE
from build_ir import build

def budget_audit(trace):
    """Independent continuous interval integration at every slope breakpoint.
    Checks actual On/Off intervals, rather than the candidate's timestamp slots.
    """
    intervals=[]; start=None
    for a in trace:
        t,_,method=a[:3]; t=t/1000
        if method=='on':
            assert start is None, ('duplicate on',a)
            start=t
        elif method=='off':
            assert start is not None and t>start, ('off without positive interval',a)
            intervals.append((start,t)); start=None
    assert start is None,'test should finish off'
    points={x+d for interval in intervals for x in interval for d in (0,172800)}
    usage=[(t,sum(max(0,min(b,t)-max(a,t-172800)) for a,b in intervals)) for t in points]
    maximum=max((used for _,used in usage),default=0)
    return {'max_rolling_on_seconds':maximum,'within_600_seconds':maximum<=600,'sessions':len(intervals)}

def main():
    frozen=json.loads((HERE/'FREEZE.json').read_text())
    for name,digest in frozen['files'].items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest,name
    ir=build();(HERE/'timeline_ir.json').write_text(json.dumps(ir,indent=2)+'\n')
    lowered,binding=B.R.lower(ir)
    catalog=str(HERE.parent/'batch_er/runs/catalog.json');cat=B.load_catalog(catalog)
    B.validate_ir(lowered);B.validate_ir_against_catalog(lowered,cat)
    print('frontend accepted; compiling',flush=True)
    t0=time.monotonic();pair,erased=B.R.compile_pair(lowered,binding,CASE['devices'],catalog)
    print('compiled',len(pair.ir_runner.prog.ins),'instructions in',round(time.monotonic()-t0,2),'s',flush=True)
    # The compiled runner is immutable; replay state is supplied separately per history.
    selected=set(sys.argv[1:]);rows=[]
    for h in CASE['histories']:
        if selected and h['name'] not in selected:continue
        t0=time.monotonic();res,_,_=B.R.run_histories(dict(CASE,histories=[h]),lambda:[pair.ir_runner]);row=res[0]
        row['elapsed_seconds']=round(time.monotonic()-t0,3)
        if 'actual' in row:row['rolling_budget_audit']=budget_audit(row['actual'])
        rows.append(row)
        print(h['name'],row.get('exact'),row['elapsed_seconds'],row.get('error',''),flush=True)
        if not row.get('exact'):print(json.dumps(row),flush=True)
        result={'id':'E1-024','revision':'rolling600_second_slots','scope':'integer-second execution; empty prehistory; single controlled actuator; finite empirical tests',
                'frontend':'accepted','runner':'compiled','cron_erased':erased,'timestamp_slots':600,'instructions':len(pair.ir_runner.prog.ins),
                'exact':f"{sum(r.get('exact',False) for r in rows)}/{len(rows)}",'histories':rows,
                'files_sha256':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('cases.py','build_ir.py','timeline_ir.json','run.py')}}
        (HERE/('results_selected.json' if selected else 'results.json')).write_text(json.dumps(result,indent=2)+'\n')
    assert all(r.get('exact') and r['rolling_budget_audit']['within_600_seconds'] for r in rows)
if __name__=='__main__':main()
