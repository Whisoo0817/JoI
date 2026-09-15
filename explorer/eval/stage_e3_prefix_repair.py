"""Stage 57 regenerations and 325 byte-identical reuses (timeout overlap removed)."""
import hashlib
import json
from pathlib import Path
import shutil

from explorer.eval.e3 import load_rows, key_of, candidate_matches_row

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'explorer/candidates/qwen3_5-9b-fp8-e3-remediated-v1'
NEW = ROOT / 'explorer/candidates/qwen3_5-9b-fp8-e3-prefix-fixed-v2'
RESULTS = ROOT / 'explorer/eval/results'
PREFIX = RESULTS / 'e3_prefix_fixed_382_20260915'


def main():
    outcomes = [json.loads(s) for s in (RESULTS / 'e3_qwen35_9b_fp8_remediated_20260915_run_complete/case_outcomes.jsonl').read_text().splitlines()]
    affected = {r['id'] for r in outcomes if 'does not declare capability' in r.get('reason', '')}
    assert len(affected) == 57, affected
    rows = {key_of(r): r for r in load_rows()}
    regenerate = (affected & rows.keys()) | {'C05_015'}
    assert len(rows) == 382 and regenerate <= rows.keys()
    reused = []
    for key in sorted(rows.keys() - regenerate):
        src = OLD / (key + '.json')
        assert candidate_matches_row(json.loads(src.read_text()), rows[key]), key
        reused.append({'id': key, 'source': str(src.relative_to(ROOT)),
                       'sha256': hashlib.sha256(src.read_bytes()).hexdigest()})
    assert len(reused) == 325 and len(regenerate) == 57
    NEW.mkdir(exist_ok=False)
    for record in reused:
        shutil.copy2(ROOT / record['source'], NEW / (record['id'] + '.json'))
    with Path(str(PREFIX) + '_lineage.json').open('x') as f:
        json.dump({'regenerated_ids': sorted(regenerate), 'reused': reused,
                   'excluded_ids': [f'C26_{i:03d}' for i in range(1, 7)],
                   'reason': 'prefix postprocessor repair and C05_015 corrected drying IR',
                   'candidate_tag': NEW.name}, f, indent=2)
    print('Staged 325 unchanged candidates; 57 pending generation; 6 excluded.')


if __name__ == '__main__':
    main()
