"""Derive descriptive metrics and a bounded self-audit from a finished frozen run."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def distribution(values):
    x = sorted(values)
    return {'n': len(x), 'median': statistics.median(x) if x else None,
            'p95_nearest_rank': x[max(0, (95 * len(x) + 99) // 100 - 1)] if x else None,
            'max': max(x) if x else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prefix', required=True)
    args = ap.parse_args()
    prefix = args.prefix
    out = Path(prefix)
    paths = {'protocol': prefix + '_protocol.json', 'manifest': prefix + '_manifest.json',
             'summary': str(out / 'summary.json'), 'outcomes': str(out / 'case_outcomes.jsonl'),
             'generation': prefix + '_generation.log', 'source_archive': prefix + '_sources.zip',
             'reporter': __file__}
    protocol = json.loads(Path(paths['protocol']).read_text())
    manifest = json.loads(Path(paths['manifest']).read_text())
    summary = json.loads(Path(paths['summary']).read_text())
    rows = [json.loads(line) for line in Path(paths['outcomes']).read_text().splitlines()]
    assert summary['outcomes_sha256'] == digest(paths['outcomes'])
    assert summary['manifest_sha256'] == digest(paths['manifest'])
    assert manifest['protocol_sha256'] == summary['protocol_sha256'] == digest(paths['protocol'])
    assert [r['id'] for r in rows] == protocol['case_ids'] == [c['id'] for c in manifest['cases']]
    assert summary['statuses'] == dict(Counter(r['status'] for r in rows))
    prepared = [r for r in rows if 'explorer' in r]
    comparable = [r for r in rows if r['status'] in ('AGREE', 'DISAGREEMENT')]
    equiv = [r for r in comparable if r['explorer']['status'] == 'EQUIV' and r['exact']['status'] == 'EQUIV_BOUNDED']
    disagree = [r['id'] for r in rows if r['status'] == 'DISAGREEMENT']
    unconfirmed = [r['id'] for r in prepared if r['explorer']['status'] == 'REPLAY_UNCONFIRMED']
    counters = {e: dict(Counter(r[e]['status'] for r in prepared)) for e in ('explorer', 'exact')}
    metrics = {'selected': len(rows), 'prepared': len(prepared), 'comparable': len(comparable),
               'statuses': summary['statuses'], 'engine_statuses': counters,
               'disagreements': disagree, 'unconfirmed_replays': unconfirmed,
               'preparation_reasons': dict(Counter(c.get('reason', '') for c in manifest['cases'] if c['status'] != 'READY')),
               'engines': {}, 'equivalent_only_comparison': {},
               'limits': protocol['engine_limits'], 'horizon_ms': protocol['model_policy']['horizon_ms'],
               'limitations': protocol['limitations']}
    generated, same_script, wrong_model = 0, 0, []
    for case in manifest['cases']:
        candidate_path = Path(case['candidate_path'])
        if not candidate_path.exists():
            continue
        assert digest(candidate_path) == case['candidate_sha256']
        candidate = json.loads(candidate_path.read_text())
        if candidate.get('model') != protocol['generation']['model']:
            wrong_model.append(case['id'])
        block = candidate.get('joi_block')
        if candidate.get('status') == 'ok' and isinstance(block, dict):
            generated += 1
            old_path = Path('explorer/candidates/gemma4-26b-heldout-v3') / candidate_path.name
            if old_path.exists():
                old = json.loads(old_path.read_text()).get('joi_block')
                same_script += isinstance(old, dict) and old.get('script') == block.get('script')
    assert not wrong_model, ('unexpected generator model', wrong_model)
    metrics['generation_provenance'] = {
        'valid_joi_blocks': generated, 'model_mismatches': wrong_model,
        'identical_script_to_same_task_old_v3': same_script,
        'note': 'fresh invocation does not guarantee a new program; duplicates retained, no outcome-based exclusion'}
    for e in ('explorer', 'exact'):
        engine = [r[e] for r in prepared]
        metrics['engines'][e] = {
            'process_wall_seconds_all_attempts': distribution([r['process_wall_seconds'] for r in engine]),
            'search_seconds_returned_results': distribution([r['result']['seconds'] for r in engine if 'result' in r]),
            'process_peak_rss_kib_observed': distribution([r['peak_rss_kib'] for r in engine if r.get('peak_rss_kib') is not None]),
            'peak_rss_missing': sum(r.get('peak_rss_kib') is None for r in engine)}
    for e in ('explorer', 'exact'):
        metrics['equivalent_only_comparison'][e] = {
            'search_seconds': distribution([r[e]['result']['seconds'] for r in equiv]),
            'pair_transitions': distribution([r[e]['result']['n_steps'] // 2 if e == 'explorer' else
                                              r[e]['result']['n_transitions'] for r in equiv])}
    metrics['equivalent_only_comparison']['note'] = 'same completed bounded-equivalent pairs only; no speedup claim from early-stopping counterexamples'
    metric_path = out / 'metrics.json'
    if metric_path.exists():
        assert json.loads(metric_path.read_text()) == metrics, 'derived metrics changed; preserve the previous report and use a new version'
    else:
        with metric_path.open('x') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
            f.write('\n')
    paths['metrics'] = str(out / 'metrics.json')
    bad = bool(disagree or unconfirmed)
    verdict = 'does_not_support_claim' if bad else 'supports_exploratory_follow_up'
    claim = ('Under the frozen contract-v1 model and 3200ms horizon, timed Explorer agrees '
             'with dense 1ms search on jointly completed new generated samples from the familiar 388-task corpus.')
    checks = [
        ('protocol_integrity', 'pass', 'All 388 case IDs, generator sources, model/domain derivation and caps frozen before fresh generation; domains serialized before searches. Task corpus remains familiar.'),
        ('metric_validity', 'fail' if bad else 'pass', 'Completed-pair agreement is separated from all-case coverage; refusals and incomplete results are retained. Dense search is a comparator, not independently established ground truth.'),
        ('baseline_fairness', 'pass', 'Both engines use identical serialized domains, horizon, start time and caps in separate sequential processes; transition ratios use paired completed equivalent cases.'),
        ('outcome_accounting', 'pass', 'Every selected ID occurs once in manifest and outcomes, including missing/failed generation, preparation refusal and resource failures.'),
        ('inferential_support', 'inconclusive', 'Descriptive finite-corpus results only; familiar tasks, one generation sample per task, no task-independent test split or independent ground truth. No population accuracy confidence claim.'),
        ('confound_control', 'inconclusive', 'Source and model frozen. Shared interpreters, catalog, input inference and observation can share bugs; internal E1 evidence does not remove all common-mode failures.'),
        ('provenance', 'pass', 'Protocol, candidate and model manifest, complete outcomes, logs and source hashes retained; generation seed unspecified by existing helper.'),
        ('snapshot_continuity', 'pass', 'Evaluation checked recorded source and candidate hashes before and after execution. This is local continuity, not sandbox isolation or external timestamp authentication.'),
        ('independence', 'fail', f'This is self-review. Search traversal differs but semantic adapters and observation are shared; tasks were used in development. {same_script}/{generated} valid generated scripts are identical to the same-task old-v3 script; fresh generation is weak code-level holdout evidence.')]
    audit = {'schema_version': '1.0', 'paper_id': 'VETS', 'identity_version': 1, 'status': 'complete',
             'audits': [{'audit_id': 'E3-CONTRACT-FRESH-V4', 'claim_id': 'E3-SEARCH-AGREEMENT',
                         'claim_text': claim, 'scope': 'All 388 prespecified generation attempts on familiar dataset tasks; catalog-backed inputs and predicate-family GV model; 3200ms only; conditional comparison and unconditional outcomes reported separately.',
                         'source_mode': 'standalone', 'requested_assurance_class': 'exploratory',
                         'attained_assurance_class': 'exploratory', 'verdict': verdict,
                         'audited_claim_effect': 'weaken' if bad else 'strengthen', 'source_runs': [],
                         'run_selection': {'selection_rule': 'Include complete fresh-v4 attempt; five-case old-v3 development pilot is retained separately. No fresh-v4 row excluded or retried.',
                                           'excluded_runs': [{'run_id': 'contract-pilot-2026-09-07', 'rationale': 'Prespecified five-case old-candidate development smoke check, not a fresh-generation sample.'},
                                                             {'run_id': 'historical-v1-v2-v3', 'rationale': 'Historical model and outcome-visible development data, not current-contract fresh-generation evidence.'}]},
                         'evidence_artifacts': [{'path': v, 'kind': k, 'source': 'experiment' if k != 'reporter' else 'audit', 'digest': digest(v)} for k, v in paths.items()],
                         'check_results': [{'check_id': k, 'status': s, 'rationale': why,
                                            'evidence_paths': list(paths.values())[:4]} for k, s, why in checks],
                         'independence': {'self_review': True, 'dimensions': [],
                                          'evidence': 'Same agent prepares evaluation and audit; dense search uses separate traversal but shares production semantics.'},
                         'limitations': protocol['limitations'] + [f'{same_script}/{generated} valid generated scripts match the old-v3 script exactly; only {generated-same_script} differ. Do not present all fresh invocations as unseen code.',
                                                                  'Peak RSS includes interpreter/preparation overhead; timeout RSS is missing, not zero.',
                                                                  'Declared GV families are normative model domains, not measured deployed GV stores.',
                                                                  'No formal proof or full-language accuracy established by benchmark agreement.'],
                         'predecessor_failures': [{'failure_id': 'HARNESS-PREFREEZE-PATH', 'status': 'resolved',
                                                   'rationale': 'Initial protocol construction failed because __file__ was relative; fixed before any protocol/candidate freeze or search. Dependent missing-file commands produced no evaluation artifacts.'},
                                                  {'failure_id': 'HISTORICAL-INPUT-MODEL', 'status': 'accepted_with_narrowing',
                                                   'rationale': 'Historical v3 numbers are not carried forward after semantics/input repairs; this run uses current catalog-backed model and bounded scope.'}],
                         'minimum_corrective_action': 'Investigate disagreements without rewriting this frozen run; new implementation requires a new version and generation sample.' if bad else
                                                      'Use only bounded descriptive results; obtain task-independent samples and stronger independent semantic coverage before stronger generalization/accuracy claims.',
                         'narrative_anchor': 'E3-CONTRACT-FRESH-V4'}]}
    audit_dir = Path(prefix + '_audit')
    (audit_dir / 'results-audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False) + '\n')
    lines = ['# Current contract fresh-generation evaluation', '', '## Audit E3-CONTRACT-FRESH-V4', '',
             '- Bounded verdict: ' + verdict, '- Assurance: exploratory; self-review.', '',
             claim, '', f'Selected {len(rows)}; prepared {len(prepared)}; jointly completed {len(comparable)}.',
             'Full outcomes: ' + json.dumps(summary['statuses']),
             'Explorer: ' + json.dumps(counters['explorer']), 'Dense search: ' + json.dumps(counters['exact']), '',
             f'Code overlap: {same_script}/{generated} valid generated scripts exactly match old-v3 for the same task; only {generated-same_script} differ. Every duplicate stays in the denominator. New invocation is not new unseen code.', '',
             'Fresh generated code on familiar tasks is not an unseen-task test set. Agreement is conditional on both searches completing.',
             'Refusal means the checker made no equivalence decision; it does not automatically mean generated code is wrong.',
             'Shared adapters/observation remain a common source of error. This run does not establish full-language correctness or unbounded equivalence.', '',
             'Detailed results and timings: `' + paths['metrics'] + '`.',
             'Canonical support record: `results-audit.json`. Historical results and development pilot are not pooled.', '',
             'Next: ' + audit['audits'][0]['minimum_corrective_action'], '']
    (audit_dir / 'results-audit.md').write_text('\n'.join(lines))
    print(json.dumps({'statuses': metrics['statuses'], 'engines': counters, 'verdict': verdict}, ensure_ascii=False))


if __name__ == '__main__':
    main()
