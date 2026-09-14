"""Explorer-only evaluation; never imports or executes the independent reference.

Read frozen judgments only for the final comparison. Write a NEW output path.
Run from repository root with ~/temp/bin/python .../evaluate_timer.py --out PATH.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

E2 = Path(__file__).resolve().parents[1]
ROOT = E2.parents[2]
sys.path[:0] = [str(ROOT), str(E2)]

TARGETS = {'C20-O/correct', 'C20-O/fault1', 'C01/fault2',
           'C05/fault2', 'C05/fault3', 'C15/correct', 'C15/fault1', 'C18/correct', 'C19/correct'}
TARGETS |= {f'{base}/{kind}' for base in ('C07', 'E1-034')
            for kind in ('correct', 'fault1', 'fault2', 'fault3', 'fault4')}


def evaluate(pair):
    import run_e2
    result = run_e2.explorer_side(pair)
    result['timer_eligibility'] = eligibility(pair)
    return result


def eligibility(pair):
    import run_e2
    from explorer.verification.timer_analysis import analyze
    from explorer.verification.gate import prepare_pair
    try:
        ir, binding = pair['ir'], pair['binding']
        if binding is None:
            sys.path.insert(0, str(run_e2.DEPTH))
            from run_depth import lower
            ir, binding = lower(ir)
        catalog = True if pair['catalog'].endswith('service_list_ver2.0.7.json') else str(ROOT / pair['catalog'])
        p = prepare_pair(ir, binding, pair['devices'], pair['joi'],
                         service_catalog=catalog, selector_binding=run_e2.BINDING_DECISION)
        plan = analyze(p.ir_runner, p.code_runner, 100)
        return {'counters': plan.counters, 'dead': sorted(plan.dead)}
    except Exception as exc:
        return {'reason': f'{type(exc).__name__}: {exc}'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--targets-only', action='store_true')
    parser.add_argument('--all-pairs', action='store_true')
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    baseline_path = E2 / 'runs/e2_run.ref-current-supp.jsonl.gz'
    with gzip.open(baseline_path, 'rt') as f:
        baseline = {r['pair_id']: r for line in f if (r := json.loads(line))}
    pairs = json.loads((E2 / 'pairs/e1_pairs.json').read_text())['pairs']
    pairs += json.loads((E2 / 'pairs/sample_388_pairs.json').read_text())['pairs']
    selected = [p for p in pairs if p['pair_id'] in TARGETS or (
        not args.targets_only and baseline[p['pair_id']]['explorer']['verdict'] in ('EQUIV', 'DIVERGE'))]
    assert TARGETS <= {p['pair_id'] for p in selected}
    expected = TARGETS | (set() if args.targets_only else {
        ident for ident, r in baseline.items() if r['explorer']['verdict'] in ('EQUIV', 'DIVERGE')})
    assert {p['pair_id'] for p in selected} == expected
    assert len(selected) == len(expected)
    if args.all_pairs: selected = pairs
    if args.only: selected = [p for p in pairs if p['pair_id'] in args.only]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with args.out.open('x') as output:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(evaluate, p): p for p in selected}
            for future in as_completed(jobs):
                p = jobs[future]
                old = baseline[p['pair_id']]
                result = future.result()
                row = {'pair_id': p['pair_id'], 'target': p['pair_id'] in TARGETS,
                       'previous': old['explorer'], 'explorer': result,
                       'frozen_reference_outcome': old['reference']['outcome']}
                output.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')
                output.flush()
                print(p['pair_id'], old['explorer']['verdict'], '->', result['verdict'],
                      result.get('n_states'), result.get('seconds'), flush=True)
    metadata = {'pairs': len(selected), 'workers': args.workers, 'budget_seconds_per_pair': 120,
                'wall_seconds': time.time() - started, 'reference_executed': False,
                'binding_decision': __import__('run_e2').BINDING_DECISION,
                'baseline_sha256': hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
                'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted((ROOT / 'explorer').rglob('*.py'))}}
    args.out.with_suffix('.meta.json').write_text(json.dumps(metadata, indent=2))


if __name__ == '__main__': main()
