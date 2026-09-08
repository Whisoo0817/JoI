"""Append-only descriptive comparison of a frozen existing-candidate recheck.

This report is post-outcome analysis, not a new generation or an isolated ablation.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    with Path(path).open('x') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def verdict(row):
    return row.get('explorer', {}).get('claim', row.get('explorer', {}).get('status', row['status']))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prefix', required=True)
    ap.add_argument('--parent-prefix', required=True)
    args = ap.parse_args()
    prefix, parent = args.prefix, args.parent_prefix
    audit_id = 'E3-CONTRACT-RECHECK-V4-' + Path(prefix).name.rsplit('_', 1)[-1].upper()
    out = Path(prefix)
    p, m, s = [read(prefix + suffix) for suffix in ('_protocol.json', '_manifest.json', '/summary.json')]
    op, om = [read(parent + suffix) for suffix in ('_protocol.json', '_manifest.json')]
    rows = [json.loads(line) for line in (out / 'case_outcomes.jsonl').read_text().splitlines()]
    oldrows = [json.loads(line) for line in Path(parent + '/case_outcomes.jsonl').read_text().splitlines()]
    assert m['protocol_sha256'] == s['protocol_sha256'] == digest(prefix + '_protocol.json')
    assert s['manifest_sha256'] == digest(prefix + '_manifest.json')
    assert s['outcomes_sha256'] == digest(out / 'case_outcomes.jsonl')
    assert [r['id'] for r in rows] == [c['id'] for c in m['cases']] == p['case_ids'] == op['case_ids']
    assert len(rows) == len({r['id'] for r in rows}) == 388
    assert s['statuses'] == dict(Counter(r['status'] for r in rows))
    assert s['snapshot_continuity']
    assert digest(p['source_archive']['path']) == p['source_archive']['sha256']
    with zipfile.ZipFile(p['source_archive']['path']) as z:
        for path, sha in p['sources'].items():
            assert hashlib.sha256(z.read(path.lstrip('/'))).hexdigest() == sha, path
    oldcases = {c['id']: c for c in om['cases']}
    old = {r['id']: r for r in oldrows}
    cases = {c['id']: c for c in m['cases']}
    present = 0
    for c in m['cases']:
        assert c.get('candidate_sha256') == oldcases[c['id']].get('candidate_sha256'), c['id']
        if 'candidate_sha256' in c:
            assert digest(c['candidate_path']) == c['candidate_sha256']
            present += 1
    assert not p['generation']['performed_in_this_run']
    prepared = [r for r in rows if 'explorer' in r]
    comparable = [r for r in rows if r['status'] in ('AGREE', 'DISAGREEMENT')]
    symbolic = [r['id'] for r in rows if r['status'] == 'SYMBOLIC_CERTIFIED']
    for key in symbolic:
        r = next(r for r in rows if r['id'] == key)
        assert r['exact']['status'] == 'NOT_APPLICABLE'
        assert r['explorer']['result']['symbolic_certificate']
    disagreements = [r['id'] for r in rows if r['status'] == 'DISAGREEMENT']
    unconfirmed = [r['id'] for r in prepared if r['explorer']['status'] == 'REPLAY_UNCONFIRMED'
                   or (r['explorer']['status'] == 'DIVERGE' and
                       not any(v['confirmed'] for v in r['explorer'].get('replays', [])))]
    changed = [{'id': r['id'], 'before': verdict(old[r['id']]), 'after': verdict(r),
                'previous_reason': oldcases[r['id']].get('reason'),
                'current_reason': cases[r['id']].get('reason'),
                'reference_payload_changed': cases[r['id']].get('payload', {}).get('ir') !=
                    oldcases[r['id']].get('payload', {}).get('ir')}
               for r in rows if verdict(r) != verdict(old[r['id']])]
    reason_changes = [{'id': c['id'], 'before': oldcases[c['id']].get('reason'),
                       'after': c.get('reason'), 'status': c['status']}
                      for c in m['cases'] if c.get('reason') != oldcases[c['id']].get('reason')]
    method_cases = [{'id': c['id'], 'method': c['verification_method'],
                     'status': next(r for r in rows if r['id'] == c['id'])['explorer']['status'],
                     'reason': next(r for r in rows if r['id'] == c['id'])['explorer'].get('reason')}
                    for c in m['cases'] if c.get('verification_method')]
    unresolved = [{'id': r['id'], 'verdict': verdict(r),
                   'reason': r.get('explorer', {}).get('reason', cases[r['id']].get('reason')),
                   'notes': r.get('explorer', {}).get('result', {}).get('notes', [])}
                  for r in rows if verdict(r) not in ('EQUIV-BOUNDED', 'EQUIV', 'DIVERGE')]
    counts = dict(Counter(verdict(r) for r in rows))
    metrics = {
        'evidence_class': p['evidence_class'], 'selected': len(rows), 'prepared': len(prepared),
        'existing_candidate_artifacts_verified': present, 'new_generation_calls': 0,
        'before': dict(Counter(verdict(r) for r in oldrows)), 'after': counts,
        'changed_verdicts': changed, 'preparation_reason_changes': reason_changes,
        'comparable': len(comparable), 'agreement': sum(r['status'] == 'AGREE' for r in rows),
        'disagreements': disagreements, 'unconfirmed_replays': unconfirmed,
        'symbolic_certified_ids': symbolic, 'unresolved': unresolved,
        'symbolic_method_cases': method_cases,
        'reference_payload_changed_ids': [c['id'] for c in m['cases'] if c.get('payload') and
            any(c['payload'].get(k) != oldcases[c['id']].get('payload', {}).get(k)
                for k in ('ir', 'binding', 'devices'))],
        'changed_source_paths': [path for path, sha in p['sources'].items() if op['sources'].get(path) != sha],
        'completion_fraction_all_388': sum(v for k, v in counts.items() if k in ('EQUIV-BOUNDED', 'EQUIV', 'DIVERGE')) / len(rows),
        'wall_seconds': s['wall_seconds'], 'horizon_ms': p['model_policy']['horizon_ms'],
        'engine_statuses': {e: dict(Counter(r[e]['status'] for r in prepared)) for e in ('explorer', 'exact')},
        'limitations': p['limitations'] + ['Agreement is conditional on both finite searches completing; symbolic certificates are separate.',
            'Refusal does not establish a wrong generated program. EQUIV is relative to supplied IR, bindings, input contract and horizon.',
            'No accuracy, generalization, independent proof or causal speedup claim is inferred from these descriptive counts.'],
    }
    write(out / 'metrics.json', metrics)
    lines = ['# 기존 Gemma4 후보 재검증 — 2026-09-07', '',
             '기존 388개 ID 전체를 현재 계약으로 재검증했다. LLM 호출은 0회이며 기존 후보 SHA는 모두 일치한다.', '',
             '| Explorer 판정 | 이전 | 현재 |', '| --- | ---: | ---: |']
    for key in sorted(set(metrics['before']) | set(counts)):
        lines.append(f"| {key} | {metrics['before'].get(key, 0)} | {counts.get(key, 0)} |")
    lines += ['', f"실행 시간 {s['wall_seconds']:.1f}초. 검증 시간 범위는 3.2초, 외부 입력100ms/타이머1ms, 기존 자원 제한 유지.", '',
              f"유한 탐색 비교: 양쪽 완료 {len(comparable)}건, 불일치 {len(disagreements)}건. 기호 인증 {len(symbolic)}건은 이 비교에 포함하지 않는다.", '',
              '## 판정 변경', '']
    lines += [f"- {c['id']}: {c['before']} → {c['after']}. 이전 이유: {c['previous_reason']}" for c in changed]
    if not changed:
        lines += ['최종 Explorer 판정 변경 없음: 388건 모두 이전과 같다.']
    lines += ['', '## 기호 검증 경로', '']
    lines += [f"- {c['id']}: `{c['method']}` → {c['status']}" +
              (f". 이유: {c['reason']}" if c['reason'] else '') for c in method_cases]
    lines += ['', '## 해석과 다음 작업', '',
              '기호 인증은 지원하는 전체 입력 도메인을 대상으로 하며 유한 대표값 열거기와의 판정 일치 수치에서 분리한다. 새 경로 진입과 최종 판정 개선은 구분한다.',
              f"이전 실행 대비 reference payload 변경은 {len(metrics['reference_payload_changed_ids'])}건이다. 모델·소스 변경 내역은 protocol과 metrics에 기록했다. 기존 사례를 본 뒤 수행한 개발 재평가이며 독립 표본이나 통제된 성능 실험이 아니다.",
              '남은 REFUSED에는 의도적인 지원 범위 제한과 생성 코드의 계약 위반이 함께 있다. 생성 실패·준비 오류·자원 한계는 모두 전체388건에 남겼다.',
              '다음은 이 동결 결과·지원 범위·증명 근거를 논문의 bounded formal verification 설명에 연결하는 것이다. 미완료 또는 새 불일치가 있으면 먼저 원인을 조사한다.',
              '새 후보 생성/미관측 held-out 평가가 아니며, 기존 사례에 대한 개발 재평가다. 평가 일치만으로 전체 실행기의 형식적 정확성을 증명하지 않는다.', '',
              '상세 이유·케이스별 변화: [metrics.json](metrics.json). 원시 판정: [case_outcomes.jsonl](case_outcomes.jsonl).', '']
    with (out / 'report.md').open('x') as f:
        f.write('\n'.join(lines))
    paths = [prefix + '_protocol.json', prefix + '_manifest.json', str(out / 'summary.json'),
             str(out / 'case_outcomes.jsonl'), str(out / 'metrics.json'), prefix + '_sources.zip',
             prefix + '_evaluation.log', parent + '_protocol.json', parent + '_manifest.json',
             parent + '/case_outcomes.jsonl', str(Path(__file__).resolve())]
    bad = bool(disagreements or unconfirmed)
    bounded = 'does_not_support_claim' if bad else 'supports_exploratory_follow_up'
    checks = [
        ('protocol_integrity', 'pass', 'All same 388 IDs and model/caps frozen before rerun. Prior outcomes informed development; no holdout claim.'),
        ('metric_validity', 'fail' if bad else 'pass', 'Unconditional outcomes, conditional finite-search agreement, and universal symbolic certificates are reported separately. Confirmed replay checked.'),
        ('baseline_fairness', 'pass', 'Finite searches receive identical prepared payloads, domains, horizon and caps. Symbolic cases are not compared to finite enumeration.'),
        ('outcome_accounting', 'pass', 'All 388 IDs included exactly once; generation errors, preparation errors, refusals and incomplete cases retained; no scientific retries.'),
        ('inferential_support', 'inconclusive', 'Descriptive finite-corpus rerun; no independent sample, confidence interval or confirmatory generalization claim.'),
        ('confound_control', 'inconclusive', 'Source/model/reference differences are recorded, but this outcome-visible development follow-up has no independent samples or controlled performance experiment.'),
        ('provenance', 'pass', 'Protocol/manifest/outcome/archive digests checked. All existing candidate hashes match original manifest; no generation in this run.'),
        ('snapshot_continuity', 'pass', 'Harness verifies source/candidate digests before and after searches. Archived bytes match protocol; repository-local continuity, not filesystem isolation.'),
        ('independence', 'inconclusive', 'Self-audit; finite engines share interpreters/adapters/observation. No external evaluator or advancement-authority separation.'),
    ]
    claim = 'On all 388 existing fresh-v4 candidate IDs, the current frozen 3200ms contract yields descriptive verification outcomes and agreement on jointly completed finite searches; symbolic certificates are counted separately.'
    audit = {'audit_id': audit_id, 'claim_id': 'E3-CURRENT-CONTRACT-RECHECK',
             'claim_text': claim, 'scope': 'Same familiar 388-task corpus and original candidate artifacts; user-approved strict BOOL and non-null GetMenu, corrected references, current symbolic/concrete engines; 3200ms.',
             'source_mode': 'standalone', 'requested_assurance_class': 'exploratory',
             'attained_assurance_class': 'exploratory', 'verdict': bounded,
             'audited_claim_effect': 'weaken' if bad else 'strengthen', 'source_runs': [],
             'run_selection': {'selection_rule': 'Include full current rerun and the explicitly bound parent rerun as before/after lineage; no ID exclusions or retries. Earlier corpus runs and development fixtures are not pooled.',
                 'excluded_runs': [{'run_id': 'historical-v1-v2-v3-and-pilot', 'rationale': 'Different candidate/model scope; not same 388 unchanged fresh-v4 artifact rerun.'},
                     {'run_id': 'earlier-fresh-v4-and-rechecks-excluding-bound-parent', 'rationale': 'Preserved predecessor evidence with earlier verifier/model versions; immediate parent is the comparison baseline, older runs are not independent replications or pooled samples.'},
                     {'run_id': 'symbolic-menu-input-cap-and-smt-development-fixtures', 'rationale': 'Outcome-visible regression/mutation fixtures are supporting implementation checks, not extra corpus samples; initial SMT v1 fixtures predate two soundness fixes and are superseded by v2.'}]},
             'evidence_artifacts': [{'path': v, 'kind': 'reporter' if v == paths[-1] else 'evaluation-artifact',
                 'source': 'audit' if v == paths[-1] else 'experiment', 'digest': digest(v)} for v in paths],
             'check_results': [{'check_id': k, 'status': status, 'rationale': why, 'evidence_paths': paths[:5]}
                 for k, status, why in checks],
             'independence': {'self_review': True, 'dimensions': [], 'evidence': 'Same agent; separate traversal with shared runtime semantics; no external verifier.'},
             'limitations': metrics['limitations'],
             'predecessor_failures': [
                 {'failure_id': 'SMT-TEXT-GUARD-BOOL-ARITHMETIC', 'status': 'accepted_with_narrowing', 'rationale': 'Initial SMT development falsely certified two unsupported symbolic operations. Explicit Unsupported dispatch and final v2 regression artifacts fix these cases by refusal; this corpus rerun does not independently prove SMT soundness.'},
                 {'failure_id': 'RECHECK-REPORT-ZIP-PATH', 'status': 'resolved', 'rationale': 'Post-run reporter initially looked up an absolute catalog path verbatim in ZIP; ZIP strips its leading slash. Fixed lookup before any metrics/audit output. Evaluation artifacts unchanged; no engine rerun.'},
                 {'failure_id': 'C01-OBSERVABLE-DOMAINS', 'status': 'resolved', 'rationale': 'C01_009/C01_017/C01_018 now certified by symbolic value flow under current explicit input contract.'},
                 {'failure_id': 'REFERENCE-CATALOG-SIX', 'status': 'accepted_with_narrowing', 'rationale': 'Reference/catalog repairs included; secondary D7 or generated group-call issues can still cause refusal.'},
                 {'failure_id': 'C01_014-INPUT-CAP',
                  'status': 'open' if any(r['id'] == 'C01_014' for r in unresolved) else 'resolved',
                  'rationale': 'Current frozen outcome and certificate, including remaining resource limits, are recorded per case; no prior incomplete outcome is retroactively relabeled.'}],
             'minimum_corrective_action': 'Investigate any disagreement in a new version.' if bad else 'Use these bounded descriptive counts with explicit model assumptions; account for any remaining limits and map proof obligations/support boundaries to the manuscript. Stronger generalization requires independent evidence.',
             'narrative_anchor': audit_id}
    auditdir = Path(prefix + '_audit')
    draft = read(auditdir / 'results-audit.json')
    assert draft['status'] == 'draft', 'Do not overwrite completed audit'
    draft.update(status='complete', audits=[audit])
    (auditdir / 'results-audit.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2) + '\n')
    (auditdir / 'results-audit.md').write_text('\n'.join([
        '# Existing-candidate recheck self-audit', '', '## Audit ' + audit_id, '',
        '- Bounded verdict: ' + bounded, '- Assurance: exploratory; self-review.', '', claim, '',
        'Before: ' + json.dumps(metrics['before']), 'After: ' + json.dumps(counts), '',
        f'Jointly completed finite searches: {len(comparable)}; disagreements: {len(disagreements)}. Symbolic certificates: {len(symbolic)}, separate from that denominator.',
        'All errors/refusals/incomplete outcomes retained. Existing candidate digests preserved; no new LLM call. Source/model/reference differences are recorded in protocols and metrics.',
        'No independent replication, causal ablation, holdout generalization, full-language formal proof or speedup is established.', '',
        'Canonical support: results-audit.json. Detailed counts and transitions: ../' + out.name + '/metrics.json.', '',
        'Next: ' + audit['minimum_corrective_action'], '']))
    print(json.dumps({'before': metrics['before'], 'after': counts, 'changed': changed,
                      'comparable': len(comparable), 'symbolic': symbolic, 'verdict': bounded}, ensure_ascii=False))


if __name__ == '__main__':
    main()
