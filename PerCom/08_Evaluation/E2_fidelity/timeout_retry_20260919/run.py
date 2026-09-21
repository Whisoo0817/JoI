"""Separate extended-budget retry of all eight E2 timeouts; original results unchanged."""
import concurrent.futures, hashlib, json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
E2 = HERE.parent
ROOT = E2.parents[2]
os.environ.update(E2_BINDING_DECISION='1', E2_BINDING_ASSIGN='1', E2_REF_DIR=str(E2/'reference'))
sys.path[:0] = [str(E2), str(ROOT), str(E2/'extension60')]
import run_e2
import runner
BUDGET = 3600

def worker(pair, previous):
    run_e2.BUDGET_S = BUDGET
    started = time.time()
    print('START', pair['pair_id'], 'pid', os.getpid(), flush=True)
    try:
        result = run_e2.explorer_side(pair)
        if result.get('witness'):
            result['witness_on_reference'] = run_e2.witness_on_reference(pair, result['witness'])
        agreement = run_e2.agreement(result, previous['reference'])
    except BaseException:
        result = {'verdict':'ERROR', 'traceback':traceback.format_exc()}
        agreement = 'RETRY-HARNESS-ERROR'
    return dict(pair_id=pair['pair_id'], explorer=result, agreement=agreement,
                previous_explorer=previous['explorer'], reference=previous['reference'],
                reference_supplement=previous.get('reference_supplement'),
                elapsed_s=time.time()-started)

def main():
    source = E2/'extension60/results200.jsonl'
    prior = {r['pair_id']:r for r in map(json.loads, source.read_text().splitlines()) if r['explorer']['verdict']=='TIMEOUT'}
    pairs = {}
    for p in [E2/'pairs/e1_pairs.json', E2/'extension60/e1/pairs.json']:
        for pair in json.loads(p.read_text())['pairs']:
            if pair['pair_id'] in prior:
                pair['catalog'] = pair['catalog'].replace('PerCom/6_Evaluation','PerCom/08_Evaluation')
                pairs[pair['pair_id']] = pair
    assert len(pairs)==len(prior)==8
    snapshots = runner.runtime_files()
    frozen = json.loads((E2/'extension60/runtime_freeze.json').read_text())['files']
    changed = [p for p,h in frozen.items() if snapshots.get(p)!=h]
    assert not changed, ('Runtime changed since previous experiment', changed)
    (HERE/'inputs.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2))
    meta = dict(started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                budget_s=BUDGET, workers=8, max_states=400000, max_transitions=2000000,
                selection='All eight TIMEOUT pairs in extension60/results200.jsonl',
                change='Only external wall-time budget increased from 120 to 3600 seconds per search; semantics and structural limits unchanged.',
                previous_results_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                runtime_sha256=snapshots, reference_policy='Reuse existing reference evidence with identical runtime hashes; independently replay any new witness.')
    (HERE/'metadata.json').write_text(json.dumps(meta,indent=2))
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool, (HERE/'results.jsonl').open('x') as out:
        futures = [pool.submit(worker,pair,prior[pid]) for pid,pair in pairs.items()]
        for f in concurrent.futures.as_completed(futures):
            row=f.result();out.write(json.dumps(row,ensure_ascii=False)+'\n');out.flush();os.fsync(out.fileno())
            print('DONE',row['pair_id'],row['explorer']['verdict'],row['agreement'],round(row['elapsed_s'],2),flush=True)
    unchanged=runner.runtime_files()==snapshots
    (HERE/'completion.json').write_text(json.dumps(dict(runtime_unchanged=unchanged,finished_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))))
    print('COMPLETE runtime_unchanged=',unchanged,flush=True)
if __name__=='__main__': main()
