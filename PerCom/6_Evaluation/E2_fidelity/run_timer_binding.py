"""Explorer-only E2 rerun: timer/unroll Explorer (timer worktree) + binding decision B1/B2/B5.
Reference outcomes are reused from runs/e2_run.binding-final.jsonl (reference code unchanged); new DIVERGE witnesses
are replayed on the paper-branch reference. Output runs/e2_run.timer-binding.jsonl (+ .meta.json)."""
import json, os, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
PAPER_E2 = '/home/gnltnwjstk/joi/PerCom/6_Evaluation/E2_fidelity'
TIMER_ROOT = '/home/gnltnwjstk/joi-timer-regions'
TIMER_E2 = TIMER_ROOT + '/PerCom/6_Evaluation/E2_fidelity'
os.environ['E2_BINDING_DECISION'] = '1'
os.environ['E2_BINDING_ASSIGN'] = '1'
os.environ['E2_REF_DIR'] = PAPER_E2 + '/reference'
sys.path[:0] = [TIMER_E2, TIMER_ROOT]

def work(pair_id):
    import run_e2
    pairs, _ = run_e2.load_inputs()
    pair = next(p for p in pairs if p['pair_id'] == pair_id)
    started = time.time()
    exp = run_e2.explorer_side(pair)
    if exp.get('witness'):
        exp['witness_on_reference'] = run_e2.witness_on_reference(pair, exp['witness'])
    exp['wall_seconds'] = round(time.time() - started, 2)
    return pair_id, exp

if __name__ == '__main__':
    import run_e2
    assert run_e2.BINDING_DECISION and run_e2.BINDING_ASSIGN and str(run_e2.REF).startswith(PAPER_E2), run_e2.REF
    assert run_e2.__file__.startswith(TIMER_E2), run_e2.__file__
    base = {json.loads(l)['pair_id']: json.loads(l) for l in open(PAPER_E2 + '/runs/e2_run.binding-final.jsonl')}
    out = PAPER_E2 + '/runs/e2_run.timer-binding.jsonl'
    head = subprocess.run(['git', '-C', TIMER_ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    json.dump({'explorer_worktree': TIMER_ROOT, 'explorer_head': head, 'reference_dir': os.environ['E2_REF_DIR'],
               'reference_outcomes_from': 'runs/e2_run.binding-final.jsonl', 'binding_decision': True, 'binding_assign': True,
               'budget_s': run_e2.BUDGET_S, 'workers': 8, 'started': time.strftime('%Y-%m-%d %H:%M:%S'),
               'load_at_start': os.getloadavg()}, open(out.replace('.jsonl', '.meta.json'), 'w'), indent=1)
    rows = {}
    with ProcessPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(work, p) for p in sorted(base)]
        for f in as_completed(futs):
            pid, exp = f.result()
            row = dict(base[pid])
            row['explorer_binding_final'] = base[pid]['explorer']
            row['explorer'] = exp
            row['agreement'] = run_e2.agreement(exp, row['reference'])
            rows[pid] = row
            print(len(rows), pid, base[pid]['explorer'].get('verdict'), '->', exp.get('verdict'), row['agreement'], exp.get('wall_seconds'), flush=True)
    open(out, 'w').write(''.join(json.dumps(rows[p], ensure_ascii=False) + '\n' for p in sorted(rows)))
    from collections import Counter
    print('explorer', Counter(r['explorer'].get('verdict') for r in rows.values()))
    print('agreement', Counter(r['agreement'] for r in rows.values()))
