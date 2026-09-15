"""Repository-local, append-only contract evaluation; no candidate selection by outcome.

Run from repository root. Protocol precedes generation; preparation freezes domains
before either search. Each engine gets its own process and identical model/caps.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')


def snapshot():
    from timeline_ir.catalog import load_service_specs
    paths = set(Path('explorer').rglob('*.py'))
    for base in ('lowering', 'timeline_ir'):
        paths.update(p for p in Path(base).rglob('*') if p.is_file()
                     and p.suffix in ('.py', '.json', '.md', '.txt', '.g4'))
    paths.update(Path('explorer/docs').rglob('*.md'))
    paths.update(Path('files').glob('joi*.md'))
    paths.add(Path('explorer/README.md'))
    paths.add(Path('explorer/requirements.txt'))
    paths.update((Path(__file__).resolve().relative_to(ROOT), Path('dataset.csv'),
                  Path(load_service_specs()['path'])))
    return {str(p): sha(p) for p in sorted(paths)}


def verify(sources):
    bad = [p for p, digest in sources.items() if not Path(p).exists() or sha(p) != digest]
    if bad:
        raise RuntimeError('snapshot mismatch: ' + ', '.join(bad))


def protocol(args):
    from explorer.eval.e3 import load_rows, key_of, payload_sha256, row_payload, E3_SELECTION_RULE
    rows = sorted(load_rows(), key=key_of)
    if args.pilot:
        selected = {}
        for r in rows:
            selected.setdefault(r['category_v2'], r)
        rows = list(selected.values())[:5]
    record = {
        'schema_version': 1, 'semantics': 'contract-v1',
        'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'evidence_class': 'development-pilot' if args.pilot else 'fresh-generation-on-familiar-tasks',
        'selection_rule': 'first case of first five categories, sorted IDs' if args.pilot else
                          E3_SELECTION_RULE,
        'case_ids': [key_of(r) for r in rows],
        'payload_sha256': {key_of(r): payload_sha256(row_payload(r)) for r in rows},
        'candidates': args.candidates,
        'generation': {'model': args.model_id or 'cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit',
                       'base_url': args.base_url or None,
                       'workers': args.generation_workers,
                       'timeout_seconds': args.generation_timeout, 'seed': None,
                       'pipeline': ('explorer.eval.e3 gen; confirmed ir_gt and binding_gt '
                                    'injected; NL mapping/selector inference bypassed; one lowering call'),
                       'sampling': ('temperature=0.1, max_tokens=512, streaming, '
                                    'enable_thinking=false; source hashes are normative')},
        'extractor_policy': {
            'timeline_ir': ('not invoked: each selected dataset ir_gt is the confirmed '
                            'Timeline supplied to lowering'),
            'mapping': ('not invoked: confirmed binding_gt deterministically supplies '
                        'selectors and occurrence slots'),
        },
        'model_policy': {'horizon_ms': 3200, 'input_step_ms': 100, 't0_ms': 2419200000,
                         'service_catalog': True,
                         'input_basis': 'catalog-backed joint certified representatives/exact observable domains; symbolic value-flow fallback on automatic domain materialization failure or cap; smt-linear-trace-v1 for eligible one-shot arithmetic; BOOL strictly false/true; MenuProvider.GetMenu non-null STRING (menu-string-return-v1); other non-BOOL None included; DOUBLE lattice 0.1',
                         'gv_basis': 'normative predicate-family initial/external GV domains; no measured store claim; required explicit domains unavailable => REFUSED',
                         'bindings': ('dataset binding_gt and fixed connected_devices; B1 selector '
                                      'denotes bound devices, B2 split calls in one slot stay grouped, '
                                      'B5 selector occurrences are assigned to binding slots; '
                                      'selector_binding=True; no post-outcome rebinding')},
        'caps': {'max_states': 200000, 'max_transitions': 500000, 'max_input_combinations': 100000,
                 'smt_timeout_ms': 1000, 'smt_total_timeout_ms': 10000, 'smt_max_queries': 10000},
        'engine_limits': {'wall_seconds': 20, 'address_space_mib': 768},
        'evaluation_workers': 1, 'engine_order': ['explorer', 'exact'],
        'stop_rule': 'run every selected case once per engine; no initial-pass scientific retries; retain refusal, invalid, timeout, memory failure and disagreement',
        'sources': snapshot(), 'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'environment': {'python': sys.version, 'platform': platform.platform(),
                        'cpu': next((x.split(':', 1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')), 'unknown')},
        'limitations': ['repository digest continuity is not filesystem isolation',
                        'familiar tasks are not unseen-task heldout',
                        'search engines share adapters and observation; no independent ground truth labels',
                        '3.2 seconds is a bounded evaluation horizon, not a completeness bound']}
    if args.fresh:
        record['evidence_class'] = 'fresh Qwen generation on outcome-visible familiar tasks; exploratory'
        record['limitations'].append(
            'Reference and predecessor outcomes informed contract remediation; this run is exploratory, not confirmatory.')
    if args.unbounded:
        record['evidence_class'] = ('unbounded recheck of fixed, outcome-visible familiar-task '
                                    'candidates; exploratory')
        if not args.fresh:
            record['generation']['pipeline'] = 'reuse existing candidate bytes; no LLM calls'
        if args.candidate_provenance:
            provenance = Path(args.candidate_provenance)
            record['generation']['candidate_provenance_manifest'] = str(provenance)
            record['generation']['candidate_provenance_sha256'] = sha(provenance)
        record['model_policy']['horizon_ms'] = None
        record['model_policy']['verification_mode'] = 'auto'
        record['model_policy']['closure_policy'] = ('exact relative-timer graph closure; eligible INTEGER '
            'relational invariants; symbolic/SMT one-shot completion; no bounded fallback')
        record['engine_order'] = ['explorer']
        record['limitations'][-1] = ('No horizon; resource exhaustion remains inconclusive. '
            'No independent unbounded oracle; old bounded positives are not relabeled.')
        record['limitations'].append(
            'Candidate outcomes were inspected in predecessor runs; this is not a confirmatory sample.')
    write(args.output, record)


def prepare(args):
    from explorer.eval.e3 import candidate_matches_row, load_rows, key_of
    from explorer.verification.gate import prepare_pair, pair_input_domains
    from explorer.verification.product import check_supported_pair
    from explorer.verification.input_coverage import initial_domains
    from explorer.runtime.interp import Unsupported
    p = json.loads(Path(args.protocol).read_text())
    verify(p['sources'])
    rows = {key_of(r): r for r in load_rows()}
    cases = []
    for key in p['case_ids']:
        row = rows[key]
        path = Path(p['candidates']) / (key + '.json')
        c = {'id': key, 'candidate_path': str(path), 'status': 'GENERATION_ERROR'}
        cases.append(c)
        if not path.exists():
            c['reason'] = 'missing candidate artifact (generation timeout/crash or not attempted; see generation log)'
            continue
        c['candidate_sha256'] = sha(path)
        try:
            candidate = json.loads(path.read_text())
            if not candidate_matches_row(candidate, row):
                c.update(status='PREPARATION_ERROR',
                         reason='candidate payload does not match current dataset row')
                continue
            if candidate.get('status') != 'ok' or not isinstance(candidate.get('joi_block'), dict):
                c['reason'] = candidate.get('error_code', 'missing joi_block')
                continue
            c['payload'] = {'ir': json.loads(row['ir_gt']), 'binding': json.loads(row.get('binding_gt') or '{}'),
                            'devices': json.loads(row['connected_devices']), 'joi_block': candidate['joi_block']}
            payload = c['payload']
            pair = prepare_pair(payload['ir'], payload['binding'], payload['devices'], payload['joi_block'])
            relational = p['model_policy'].get('verification_mode') == 'relational'
            if not relational and p['model_policy']['horizon_ms'] is None:
                from explorer.verification.relational_analysis import analyze
                try:
                    analyze(pair.ir_runner, pair.code_runner)
                    relational = True
                except Unsupported:
                    pass
            if relational:
                from explorer.verification.relational_analysis import analyze
                analyze(pair.ir_runner, pair.code_runner)
                c['model'] = {k: p['model_policy'][k] for k in ('horizon_ms', 'input_step_ms', 't0_ms')}
                c['model'].update(verification_mode='relational', input_domains=None)
                c.update(status='READY', verification_method='relational-state-v1',
                         domain_basis='catalog-backed joint guard domains; integer relational invariant',
                         service_model=pair.service_model.evidence(), preparation_notes=pair.notes)
                continue
            try:
                from explorer.verification.smt import smt_specs
                if smt_specs(pair.ir_runner, pair.code_runner) is not None:
                    raise Unsupported('arithmetic fragment: select SMT trace verification')
                domains = pair_input_domains(pair)
                from explorer.verification.symbolic import symbolic_input_cap_fallback
                if symbolic_input_cap_fallback(pair.ir_runner, pair.code_runner, domains,
                        max_input_combinations=p['caps']['max_input_combinations'],
                        max_transitions=p['caps']['max_transitions']):
                    raise Unsupported('automatic input combination cap: select symbolic value flow')
            except Unsupported:
                from explorer.verification.symbolic import symbolic_specs
                method = 'smt-linear-trace-v1' if smt_specs(pair.ir_runner, pair.code_runner) is not None else 'symbolic-value-flow-v1'
                if method == 'symbolic-value-flow-v1' and symbolic_specs(pair.ir_runner, pair.code_runner) is None:
                    raise
                c['model'] = {k: p['model_policy'][k] for k in ('horizon_ms', 'input_step_ms', 't0_ms')}
                c['model'].update(input_domains=None, initial_gv_domains={})
                c.update(status='READY', verification_method=method,
                         domain_basis='universal catalog symbolic inputs; no finite-domain oracle',
                         service_model=pair.service_model.evidence(), preparation_notes=pair.notes)
                continue
            axes = check_supported_pair(pair.ir_runner, pair.code_runner, input_domains=domains)
            c['model'] = {k: p['model_policy'][k] for k in ('horizon_ms', 'input_step_ms', 't0_ms')}
            c['model'].update(input_domains=domains, initial_gv_domains=initial_domains(axes))
            c.update(status='READY', input_families=axes.input_families,
                     domain_basis=p['model_policy']['input_basis'], gv_basis=p['model_policy']['gv_basis'],
                     service_model=pair.service_model.evidence(), preparation_notes=pair.notes)
        except Unsupported as e:
            c.update(status='REFUSED', reason=str(e))
        except Exception as e:
            c.update(status='PREPARATION_ERROR', reason=type(e).__name__ + ': ' + str(e))
    verify(p['sources'])
    write(args.output, {'protocol_path': args.protocol, 'protocol_sha256': sha(args.protocol), 'cases': cases})
    print(json.dumps(dict(Counter(c['status'] for c in cases)), ensure_ascii=False), flush=True)


def worker(args):
    job = json.load(sys.stdin)
    limit = job['limits']['address_space_mib'] * 1024**2
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    started = time.perf_counter()
    result = {'status': 'ERROR'}
    try:
        from explorer.verification.gate import prepare_pair
        from explorer.runtime.interp import Unsupported
        from explorer.tests.oracles.exact_timed import exact_timed_product
        from explorer.verification.timed import timed_product
        from explorer.verification.product import replay_divergence
        payload = job['case']['payload']
        if args.engine != 'explorer' and job['case'].get('verification_method') in ('symbolic-value-flow-v1', 'smt-linear-trace-v1', 'relational-state-v1'):
            print(json.dumps({'status': 'NOT_APPLICABLE',
                'reason': 'finite enumeration oracle does not certify symbolic domains',
                'worker_seconds': time.perf_counter() - started}), flush=True)
            return
        pair = prepare_pair(payload['ir'], payload['binding'], payload['devices'], payload['joi_block'])
        engine = timed_product if args.engine == 'explorer' else exact_timed_product
        caps = job['caps'] if args.engine == 'explorer' else {k: v for k, v in job['caps'].items() if not k.startswith('smt_')}
        r = engine(pair.ir_runner, pair.code_runner, **job['case']['model'], **caps)
        result = {'status': r.verdict, 'result': asdict(r)}
        if args.engine == 'explorer':
            result['claim'] = r.claim
            result['replays'] = [asdict(replay_divergence(pair.ir_runner, pair.code_runner, d)) for d in r.divergences]
            if r.verdict == 'DIVERGE' and not any(x['confirmed'] for x in result['replays']):
                result['status'] = 'REPLAY_UNCONFIRMED'
    except MemoryError:
        result = {'status': 'MEMORY_LIMIT'}
    except Unsupported as e:
        result = {'status': 'REFUSED', 'reason': str(e)}
    except Exception as e:
        result = {'status': 'ERROR', 'reason': type(e).__name__ + ': ' + str(e)}
    result.update(worker_seconds=time.perf_counter() - started,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    print(json.dumps(result, ensure_ascii=False, default=repr), flush=True)


def run(args):
    p = json.loads(Path(args.protocol).read_text())
    m = json.loads(Path(args.manifest).read_text())
    if m['protocol_sha256'] != sha(args.protocol):
        raise RuntimeError('protocol mismatch')
    verify(p['sources'])
    for c in m['cases']:
        if 'candidate_sha256' in c and sha(c['candidate_path']) != c['candidate_sha256']:
            raise RuntimeError('candidate mismatch: ' + c['id'])
    dest = Path(args.output)
    dest.mkdir(parents=True, exist_ok=False)
    outcomes = []
    started = time.perf_counter()
    with (dest / 'case_outcomes.jsonl').open('x') as log:
        for c in m['cases']:
            row = {'id': c['id'], 'status': c['status']}
            if c['status'] == 'READY':
                for engine in p['engine_order']:
                    tick = time.perf_counter()
                    job = {'case': c, 'caps': p['caps'], 'limits': p['engine_limits']}
                    try:
                        proc = subprocess.run([sys.executable, __file__, 'worker', '--engine', engine],
                                              input=json.dumps(job), text=True, capture_output=True,
                                              timeout=p['engine_limits']['wall_seconds'])
                        row[engine] = json.loads(proc.stdout) if proc.returncode == 0 else {
                            'status': 'CRASH', 'returncode': proc.returncode, 'stderr': proc.stderr[-2000:]}
                    except subprocess.TimeoutExpired:
                        row[engine] = {'status': 'TIMEOUT', 'peak_rss_kib': None}
                    except Exception as e:
                        row[engine] = {'status': 'HARNESS_ERROR', 'reason': str(e)}
                    row[engine]['process_wall_seconds'] = time.perf_counter() - tick
                a, b = row['explorer']['status'], row.get('exact', {}).get('status')
                complete = a in ('EQUIV', 'DIVERGE') and b in ('EQUIV_BOUNDED', 'DIVERGE')
                row['status'] = ('AGREE' if (a == 'DIVERGE') == (b == 'DIVERGE') else 'DISAGREEMENT') if complete else 'NOT_COMPARABLE'
                if c.get('verification_method') in ('symbolic-value-flow-v1', 'smt-linear-trace-v1'):
                    if a == 'EQUIV' and row['explorer'].get('result', {}).get('symbolic_certificate'):
                        row['status'] = 'SYMBOLIC_CERTIFIED'
                    elif a == 'DIVERGE' and any(r['confirmed'] for r in row['explorer'].get('replays', [])):
                        row['status'] = 'DIVERGE_CONFIRMED'
                if c.get('verification_method') == 'relational-state-v1' and a == 'EQUIV':
                    certificate = row['explorer']['result'].get('symbolic_certificate') or {}
                    if row['explorer'].get('claim') == 'EQUIV-FIXPOINT' and certificate.get('complete'):
                        row['status'] = 'RELATIONAL_CERTIFIED'
                if p['engine_order'] == ['explorer'] and p['model_policy']['horizon_ms'] is None:
                    if a == 'EQUIV' and row['explorer'].get('claim') == 'EQUIV-FIXPOINT':
                        row['status'] = 'EQUIV-FIXPOINT'
                    elif a == 'DIVERGE' and any(r['confirmed'] for r in row['explorer'].get('replays', [])):
                        row['status'] = 'DIVERGE_CONFIRMED'
                    else:
                        row['status'] = a if a != 'EQUIV' else 'INVALID_UNBOUNDED_CLAIM'
            else:
                row['reason'] = c.get('reason')
            outcomes.append(row)
            log.write(json.dumps(row, ensure_ascii=False, default=repr) + '\n')
            log.flush()
            print(f"[{len(outcomes)}/{len(m['cases'])}] {c['id']} {row['status']} " +
                  ' '.join(e + '=' + row[e]['status'] for e in p['engine_order'] if e in row), flush=True)
    verify(p['sources'])
    for c in m['cases']:
        if 'candidate_sha256' in c and sha(c['candidate_path']) != c['candidate_sha256']:
            raise RuntimeError('candidate changed during evaluation: ' + c['id'])
    summary = {'protocol_sha256': sha(args.protocol), 'manifest_sha256': sha(args.manifest),
               'outcomes_sha256': sha(dest / 'case_outcomes.jsonl'), 'snapshot_continuity': True,
               'total_cases': len(outcomes), 'statuses': dict(Counter(r['status'] for r in outcomes)),
               'wall_seconds': time.perf_counter() - started, 'engines': {},
               'evidence_class': p['evidence_class'], 'model_policy': p['model_policy']}
    for engine in p['engine_order']:
        values = [r[engine] for r in outcomes if engine in r]
        times = sorted(r['result']['seconds'] for r in values if 'result' in r)
        summary['engines'][engine] = {'statuses': dict(Counter(r['status'] for r in values)),
                                     'returned_search_seconds_n': len(times),
                                     'returned_search_seconds_median': statistics.median(times) if times else None,
                                     'returned_search_seconds_max': max(times) if times else None,
                                     'note': 'conditional on returned search results; not all-case latency; per-case process wall and peak RSS in JSONL'}
    write(dest / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def main():
    os.chdir(ROOT)
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('protocol')
    p.add_argument('--candidates', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--pilot', action='store_true')
    p.add_argument('--fresh', action='store_true', help='fresh candidate generation under this protocol')
    p.add_argument('--unbounded', action='store_true', help='reuse candidates; H=None; Explorer only')
    p.add_argument('--model-id', default='')
    p.add_argument('--base-url', default='')
    p.add_argument('--generation-workers', type=int, default=2)
    p.add_argument('--generation-timeout', type=int, default=300)
    p.add_argument('--candidate-provenance', default='',
                   help='optional frozen manifest that hashes the reused candidate bytes')
    p = sub.add_parser('prepare')
    p.add_argument('--protocol', required=True)
    p.add_argument('--output', required=True)
    p = sub.add_parser('run')
    p.add_argument('--protocol', required=True)
    p.add_argument('--manifest', required=True)
    p.add_argument('--output', required=True)
    p = sub.add_parser('worker')
    p.add_argument('--engine', choices=('explorer', 'exact'), required=True)
    args = ap.parse_args()
    globals()[args.cmd](args)


if __name__ == '__main__':
    main()
