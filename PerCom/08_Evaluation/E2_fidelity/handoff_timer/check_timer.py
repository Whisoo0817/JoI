"""Record the requested regression modules without importing E2 reference code."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

MODULES = [f'explorer.tests.{name}' for name in (
    'test_contract', 'test_input_coverage', 'test_service_model', 'test_soundness',
    'test_exact_tick', 'test_time_elision', 'test_relational_fixpoint', 'test_search_correctness')]
MODULES += ['explorer.analysis.features', 'explorer.runtime.ir_step', 'explorer.tests.test_timer_zones']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[4]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with args.out.open('x') as output:
        for module in MODULES:
            start = time.perf_counter()
            p = subprocess.run([sys.executable, '-m', module], cwd=root,
                               text=True, capture_output=True)
            row = {'module': module, 'returncode': p.returncode,
                   'seconds': time.perf_counter() - start, 'stdout': p.stdout, 'stderr': p.stderr}
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
            output.flush()
            results.append(row)
            print(module, 'PASS' if p.returncode == 0 else 'FAIL', flush=True)
    if any(r['returncode'] for r in results): raise SystemExit(1)


if __name__ == '__main__': main()
