"""Check extension accounting, preserved artifacts and recorded trace comparisons.
Run from any directory with Python 3. This does not certify source interpretation.
"""
from pathlib import Path
from collections import Counter
import hashlib, json, math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
WORK = HERE.parent / 'remaining72'


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def trace_multiset_match(expected, actual):
    free = list(actual)
    for e in expected:
        match = next((i for i, a in enumerate(free) if same(e[:5], a[:5])), None)
        if match is None:
            return False
        free.pop(match)
    return not free


def main():
    cohort = json.loads((HERE / 'cohort_snapshot.json').read_text())
    snapshots = json.loads((HERE / 'preserved_artifacts_sha256.json').read_text())
    changed = [p for p, digest in snapshots.items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest]
    rows, files = [], []
    for p in sorted(WORK.glob('batch_*/runs/results.json')):
        data = json.loads(p.read_text())
        rows.extend(data)
        files.append(str(p.relative_to(HERE.parent)))
    counts = Counter(r['id'] for r in rows)
    expected_ids = set(cohort['remaining_ids'])
    discrepancies, unordered_only, no_actions, missing_histories = [], [], [], []
    histories = exact = 0
    for r in rows:
        hs = r.get('histories', [])
        if not hs:
            missing_histories.append({'id': r['id'], 'error': r.get('error'), 'label': r.get('label')})
        good = 0
        for h in hs:
            histories += 1
            if 'actual' not in h or 'expected' not in h:
                if h.get('exact'):
                    discrepancies.append([r['id'], h['name'], 'success without raw traces'])
                continue
            eq = trace_multiset_match(h['expected'], h['actual'])
            good += int(eq)
            exact += int(eq)
            if eq != h.get('exact'):
                discrepancies.append([r['id'], h['name'], 'recorded exact mismatch'])
            if eq and not same(sorted(h['expected'], key=lambda a: a[0]), [a[:5] for a in h['actual']]):
                unordered_only.append([r['id'], h['name']])
        if hs and r.get('exact') != f'{good}/{len(hs)}':
            discrepancies.append([r['id'], 'case aggregate differs from raw traces'])
        if hs and not any(h.get('expected') for h in hs):
            no_actions.append(r['id'])
    report = {'case_count': len(rows), 'expected_case_count': len(expected_ids),
              'missing_ids': sorted(expected_ids-set(counts)), 'unexpected_ids': sorted(set(counts)-expected_ids),
              'duplicate_ids': sorted(k for k,v in counts.items() if v != 1),
              'original_artifacts_changed': changed, 'raw_trace_comparison_discrepancies': discrepancies,
              'histories': histories, 'exact_histories_recomputed': exact,
              'cases_without_histories': missing_histories, 'cases_with_only_empty_expected_traces': no_actions,
              'histories_matching_only_if_equal_time_order_ignored': unordered_only,
              'inputs': files, 'scope':'Mechanical accounting and recomputation only; source interpretation reviewed separately.'}
    supplemental = []
    for relative in ['batch_er/sensitivity/runs/results.json', 'batch_community/runs/sensitivity_results.json']:
        path = WORK / relative
        if not path.exists():
            supplemental.append({'file': relative, 'missing': True})
            continue
        data = json.loads(path.read_text())
        total = good = 0
        mismatch = []
        for row in data:
            for h in row.get('histories', []):
                total += 1
                eq = 'actual' in h and 'expected' in h and trace_multiset_match(h['expected'], h['actual'])
                good += int(eq)
                if eq != h.get('exact'):
                    mismatch.append([row['id'], h['name']])
        supplemental.append({'file': relative, 'histories': total, 'exact_recomputed': good, 'discrepancies': mismatch})
    report['separate_supplemental_checks'] = supplemental
    (HERE/'artifact_audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return int(bool(report['missing_ids'] or report['unexpected_ids'] or report['duplicate_ids'] or changed or discrepancies))

if __name__ == '__main__':
    raise SystemExit(main())
