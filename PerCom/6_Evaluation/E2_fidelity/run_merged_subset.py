"""Explorer-only E2 regression after merging timer-regions-20260914 (E3 changes) into the paper line.

Scope (author decision 2026-09-15): the 53 pairs the merged changes can reach, not all 140:
- the 38 valid LLM candidates (service-prefix and confirmed-input changes act at preparation),
- the 5 E1-072 pairs (bare grouped Boolean reads now normalized to explicit comparisons),
- the 10 previously undecided pairs (C07, E1-099).
Binding decision B1/B2/B5 on, 120 s budget, same pairs/histories as runs/e2_run.timer-binding.jsonl. Reference outcomes
are reused from that file (reference code unchanged); new DIVERGE witnesses are replayed on the reference.
Output runs/e2_run.merged-subset.jsonl (+ .meta.json)."""
import json, os, subprocess, sys, time, gzip
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
os.environ['E2_BINDING_DECISION'] = '1'
os.environ['E2_BINDING_ASSIGN'] = '1'
os.environ['E2_REF_DIR'] = str(HERE / 'reference')
sys.path[:0] = [str(HERE), str(ROOT)]


def base_rows():
    rows = [json.loads(l) for l in gzip.open(HERE / 'runs/e2_run.timer-binding.jsonl.gz', 'rt') if l.strip()]
    excl = {e['pair_id'] for e in json.loads((HERE / 'handoff_timer/e2_population.json').read_text())['exclusions']}
    return {r['pair_id']: r for r in rows if r['pair_id'] not in excl}


def subset(base):
    return sorted(p for p, r in base.items() if p.endswith('/llm') or p.startswith('E1-072/')
                  or r['explorer'].get('verdict') not in ('EQUIV', 'DIVERGE'))


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
    assert run_e2.BINDING_DECISION and run_e2.BINDING_ASSIGN
    base = base_rows()
    ids = subset(base)
    out = HERE / 'runs/e2_run.merged-subset.jsonl'
    git = lambda *c: subprocess.run(['git', '-C', str(ROOT), *c], capture_output=True, text=True).stdout.strip()
    meta = {'explorer_head': git('rev-parse', 'HEAD'), 'dirty_files': git('status', '--short').splitlines(),
            'reference_outcomes_from': 'runs/e2_run.timer-binding.jsonl.gz', 'pairs': ids, 'n_pairs': len(ids),
            'binding_decision': True, 'binding_assign': True, 'budget_s': run_e2.BUDGET_S, 'workers': 8,
            'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'load_at_start': os.getloadavg()}
    with open(str(out).replace('.jsonl', '.meta.json'), 'x') as fh:
        json.dump(meta, fh, indent=1)
    print(len(ids), 'pairs', flush=True)
    rows = {}
    with ProcessPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(work, p) for p in ids]
        for f in as_completed(futs):
            pid, exp = f.result()
            row = dict(base[pid])
            row['explorer_timer_binding'] = base[pid]['explorer']
            row['explorer'] = exp
            row['agreement'] = run_e2.agreement(exp, row['reference'])
            rows[pid] = row
            print(len(rows), pid, base[pid]['explorer'].get('verdict'), '->', exp.get('verdict'), row['agreement'],
                  exp.get('wall_seconds'), flush=True)
    with open(out, 'x') as fh:
        fh.write(''.join(json.dumps(rows[p], ensure_ascii=False) + '\n' for p in sorted(rows)))
    changed = [p for p in sorted(rows) if rows[p]['explorer'].get('verdict') != base[p]['explorer'].get('verdict')]
    print('explorer', Counter(r['explorer'].get('verdict') for r in rows.values()))
    print('agreement', Counter(r['agreement'] for r in rows.values()))
    print('verdict changes vs timer-binding:', changed)
