import json,hashlib,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE=ROOT/'explorer/eval/results'
p=json.loads((BASE/'e3_single_binding_382_20260915_protocol.json').read_text())
m=json.loads((BASE/'e3_single_binding_382_20260915_manifest.json').read_text())
snapshot=HERE/'snapshot';snapshot.mkdir(exist_ok=False)
checks={}
for s,h in p['sources'].items():
    rel=s if not s.startswith('/') else 'files/'+Path(s).name
    if not (s.endswith('.py') or s.endswith('.json')):continue
    current=ROOT/rel
    data=current.read_bytes() if current.exists() else b''
    if hashlib.sha256(data).hexdigest()!=h:
        data=subprocess.check_output(['git','-C',str(ROOT),'show',p['git_head']+':'+rel])
    assert hashlib.sha256(data).hexdigest()==h,rel
    dest=snapshot/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);checks[rel]=h
cases=[c for c in m['cases'] if c['id'] in ['C11_001','C11_005']]
for c in cases:
    assert hashlib.sha256((ROOT/c['candidate_path']).read_bytes()).hexdigest()==c['candidate_sha256']
caps=dict(p['caps'],smt_timeout_ms=120000,smt_total_timeout_ms=120000)
limits=dict(p['engine_limits'],wall_seconds=120)
protocol=dict(parent_protocol=str(BASE/'e3_single_binding_382_20260915_protocol.json'),parent_manifest=str(BASE/'e3_single_binding_382_20260915_manifest.json'),caps=caps,limits=limits,source_hashes=checks,policy='Exploratory retry of exactly two UNKNOWN outcomes. Frozen original payload and source hashes; only time limits changed. Sequential subprocesses; hard 120 seconds wall limit per case. Original table is unchanged.')
(HERE/'protocol.json').write_text(json.dumps(protocol,indent=2))
(HERE/'inputs.json').write_text(json.dumps(cases,indent=2,ensure_ascii=False))
with (HERE/'results.jsonl').open('x') as log:
 for c in cases:
    job=dict(case=c,caps=caps,limits=limits)
    (HERE/(c['id']+'_job.json')).write_text(json.dumps(job,indent=2,ensure_ascii=False))
    print('START',c['id'],flush=True);start=time.monotonic()
    try:
        proc=subprocess.run([sys.executable,str(snapshot/'explorer/eval/frozen_contract.py'),'worker','--engine','explorer'],input=json.dumps(job),capture_output=True,text=True,cwd=snapshot,timeout=120)
        (HERE/(c['id']+'_stderr.txt')).write_text(proc.stderr)
        result=json.loads(proc.stdout) if proc.returncode==0 else dict(status='ERROR',returncode=proc.returncode,stderr=proc.stderr)
    except subprocess.TimeoutExpired:
        result=dict(status='TIMEOUT',reason='Whole-case wall-clock limit: 120 seconds')
    row=dict(id=c['id'],elapsed_s=time.monotonic()-start,explorer=result)
    log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
    print('DONE',c['id'],result['status'],round(row['elapsed_s'],3),result.get('result',{}).get('notes'),flush=True)
