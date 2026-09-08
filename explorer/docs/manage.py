#!/usr/bin/env python3
"""Render the selected evaluation and check documentation/evidence continuity.

Uses only the standard library; does not import or execute Explorer or rerun evaluations.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / 'explorer/docs/index.json'


def read_json(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_references(text, layout):
    moves = {old[:-3].replace('/', '.'): new[:-3].replace('/', '.')
             for old, new in layout['moves'].items() if old.endswith('.py')}
    if not moves:
        return text
    pattern = r'\b(' + '|'.join(re.escape(k) for k in sorted(moves, key=len, reverse=True)) + r')\b'
    return re.sub(pattern, lambda m: moves[m[0]], text)


def relocated_source(name, original, layout):
    """Replay import, CLI and source-inventory edits; never waive body differences."""
    import ast
    from importlib.util import resolve_name
    if not name.endswith('.py'):
        return original
    text = original.decode('utf-8')
    module_moves = {old[:-3].replace('/', '.'): new[:-3].replace('/', '.')
                    for old, new in layout['moves'].items() if old.endswith('.py')}
    package = name[:-3].replace('/', '.').rpartition('.')[0]
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.ImportFrom):
            continue
        origin = resolve_name('.' * node.level + (node.module or ''), package) if node.level else node.module
        if not origin or not origin.startswith('explorer'):
            continue
        groups = {}
        for alias in node.names:
            child = origin + '.' + alias.name
            if child in module_moves:
                target, _, leaf = module_moves[child].rpartition('.')
                mapped = ast.alias(name=leaf, asname=alias.asname)
            else:
                target, mapped = module_moves.get(origin, origin), alias
            groups.setdefault(target, []).append(mapped)
        replacement = ('\n' + ' ' * node.col_offset).join(
            'from ' + target + ' import ' + ', '.join(a.name + (' as ' + a.asname if a.asname else '') for a in aliases)
            for target, aliases in groups.items())
        edits.append((offsets[node.lineno-1]+node.col_offset,
                      offsets[node.end_lineno-1]+node.end_col_offset, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    text = module_references(text, layout)
    # These changes only repair repository roots and source evidence collection.
    if name == 'explorer/e3.py':
        text = text.replace('os.path.dirname(os.path.dirname(os.path.abspath(__file__)))',
                            'os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))')
    if name == 'explorer/contract_eval.py':
        text = text.replace('Path(__file__).parent.glob("*.py")', 'Path(__file__).parents[1].rglob("*.py")')
        text = text.replace('path.name.encode()', 'str(path.relative_to(Path(__file__).parents[1])).encode()')
        text = text.replace("Path(__file__).parent.parent / 'timeline_ir'", "Path(__file__).parents[2] / 'timeline_ir'")
    if name == 'explorer/relational.py':
        text = text.replace("p.relative_to(Path(__file__).parent)", "p.relative_to(Path(__file__).parents[1])")
        text = text.replace("Path(__file__).parent.glob('*.py')", "Path(__file__).parents[1].rglob('*.py')")
    if name == 'explorer/eval/frozen_contract.py':
        text = text.replace("Path('explorer').glob('*.py')", "Path('explorer').rglob('*.py')")
        text = text.replace("paths.update(Path('explorer').glob('*.md'))",
                            "paths.update(Path('explorer/docs').rglob('*.md'))\n    paths.add(Path('explorer/README.md'))")
    if name in ('explorer/tests/e1_internal_conformance.py',
                'explorer/tests/e1_runtime_probe.py', 'explorer/eval/triage_refusals.py'):
        for old, new in layout.get('document_moves', {}).items():
            text = text.replace(old, new)
        text = text.replace("(ROOT / 'explorer').glob('*.py')",
                            "(ROOT / 'explorer').rglob('*.py')")
    return text.encode('utf-8')


def relocated_document(name, original, layout):
    """Rebase links without rewriting the historical document's claims or results."""
    import posixpath
    moves = {**layout['moves'], **layout.get('document_moves', {})}
    target_name = moves.get(name, name)
    def rebase(match):
        target = match[2]
        url = urlsplit(target)
        if url.scheme or url.netloc or target.startswith('/'):
            return match[0]
        old = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path))) if url.path else name
        new = moves.get(old, old)
        relative = posixpath.relpath(new, posixpath.dirname(target_name)) if url.path else ''
        return match[1] + relative + ('#' + url.fragment if url.fragment else '') + ')'
    text = re.sub(r'(\[[^\]\n]*\]\()([^\s)]+)\)', rebase, original.decode('utf-8'))
    text = module_references(text, layout)
    # Repository-qualified references in code examples and prose.
    if moves:
        pattern = r'(?<![\w/])(' + '|'.join(re.escape(k) for k in sorted(moves,key=len,reverse=True)) + r')(?![\w.])'
        text = re.sub(pattern, lambda m: moves[m[0]], text)
    return text.encode('utf-8')


def link(path, label):
    target = os.path.relpath(ROOT / path, ROOT / 'explorer/docs/paper')
    return f'[{label}]({target})'


def evaluation_text(index):
    e = index['latest_evaluation']
    run = ROOT / e['run']
    summary = read_json(run / 'summary.json')
    protocol = read_json(ROOT / e['protocol'])
    validation = read_json(ROOT / e['validation'])
    followup = read_json(run / 'followup_verification.json')
    statuses = dict(summary['statuses'])
    for status in ('EQUIV-FIXPOINT', 'DIVERGE_CONFIRMED', 'INCONCLUSIVE',
                   'REFUSED', 'GENERATION_ERROR', 'PREPARATION_ERROR'):
        statuses.setdefault(status, 0)
    rows = '\n'.join(f'| {status} | {n} |' for status, n in statuses.items())
    methods = '\n'.join(f'- `{method}`: {n}건.'
                        for method, n in followup['positive_methods'].items())
    model, caps, limits = protocol['model_policy'], protocol['caps'], protocol['engine_limits']
    audit = read_json(ROOT / e['audit'])
    audit_rows = '\n'.join(f'- `{a["audit_id"]}`: `{a["verdict"]}`.' for a in audit['audits'])
    return f'''# Explorer 평가 요약

<!-- Generated by docs/manage.py from docs/index.json. Do not edit by hand. -->
현재 선택된 결과의 요약이다. 원본을 수정하지 않고 `docs/index.json`의 평가 경로에서 생성한다.
현재 TODO는 [README](../../README.md), 보장 범위는 [검증 계약](../model/VERIFICATION_CONTRACT.md),
증명 상태는 [증명 의무](../proof/PROOF_OBLIGATIONS.md)를 따른다.

## 선택된 평가와 조건

- Run: `{Path(e['run']).name}`.
- 성격: **기존 후보의 개발 재평가** (`{summary['evidence_class']}`). 새 독립 held-out이 아니다.
- 후보: `{protocol['candidates']}`. 기존 바이트를 재사용하며 LLM 재생성은 없다.
- 시간 범위: `H={model['horizon_ms']}`. 외부 입력 간격 {model['input_step_ms']}ms,
  시작 시각 {model['t0_ms']}ms. 정확한 내부 deadline의 의미는 검증 계약을 따른다.
- 상한: 상태 {caps['max_states']}, 전이 {caps['max_transitions']}, 입력 조합 {caps['max_input_combinations']}.
- 사례별 프로세스: {limits['wall_seconds']}초 / {limits['address_space_mib']}MiB.
  SMT 질의 {caps['smt_timeout_ms']}ms, 총 {caps['smt_total_timeout_ms']}ms, 최대 {caps['smt_max_queries']}회.
- 전체 실행 wall time: **{summary['wall_seconds']:.2f}초**. 개별 검증 지연시간이나 일반 성능 보장과 다르다.

## 결과

| 결과 | 건수 |
| --- | ---: |
{rows}
| 합계 | {summary['total_cases']} |

H 없는 인증의 경로별 구성:

{methods}

이번 corpus에서 새 SMT/관계 경로의 인증이 나왔다는 근거로 사용하지 않는다.
그 경로의 지원 근거는 별도 개발 사례와 증명 의무다.
미결정이 관측되지 않았다는 결과를 모든 프로그램의 판정 완료 보장으로 확대하지 않는다.
동등 건수는 자연어 정답률이나 검증기 정확도 100%의 분모가 아니다.

## 구현 근거와 한계

- 선택된 회귀 기록: **{validation['total_tests']}개**, 전체 통과 `{validation['all_passed']}`.
  suite별 명령·출력·소스 hash는 아래 validation에 있다. 이 문서를 생성하면서 다시 실행한 수치가 아니다.
- 모든 긍정 결과의 폐쇄/H 없음 확인: `{followup['all_positive_closed_and_H_none']}`.
  모든 불일치의 구체 재생 확인: `{followup['all_divergences_replay_confirmed']}`.
- 작은 직접 열거 대조는 탐색 축소 검사의 근거다. 공유 실행기 오류를 전부 배제하지 않는다.
  독립 의미론 kernel도 검사한 언어 조각과 입력 이력에 대한 근거이며, 전체 구현의 기계 증명이 아니다.
- C15_005/C18_003은 IR과 코드가 함께 자정 종료 의도를 놓친 기준 데이터 품질 이슈다.
  동등 인증은 두 행동이 같다는 뜻이며 원문의 의도 충족을 뜻하지 않는다. 분모에서 제외하지 않았다.
- 같은 과제·개발 중 수정된 구현의 재평가다. 독립 반복 실험, unseen-task 일반화,
  물리 런타임 적합성 또는 새 최적화의 독립적인 속도 향상을 이 결과만으로 주장하지 않는다.

기존 감사의 판단(이번 문서 정리는 새 감사가 아님):

{audit_rows}

## 원본 근거

- {link(e['run'] + '/report.md', '동결 보고서')}, {link(e['run'] + '/summary.json', '원본 집계')}, {link(e['run'] + '/case_outcomes.jsonl', '전체 행별 결과')}.
- {link(e['protocol'], '실행 전 프로토콜')}, {link(e['manifest'], '준비 manifest')}, {link(e['run'] + '_sources.zip', '평가 소스 ZIP')}.
- {link(e['validation'], '회귀 validation')}, {link(e['run'] + '/followup_verification.json', '경로·반례·직전 결과 비교')}.
- {link(e['audit'], '기존 결과 감사 JSON')}, {link(str(Path(e['audit']).with_suffix('.md')), '기존 감사 설명')}.

원본 보고서·감사는 당시 버전의 고정 근거다. 그 안의 TODO를 현재 지시로 사용하지 않는다.
문서 링크/집계/소스 변경 검사는 `python3 explorer/docs/manage.py check`로 수행한다.
'''


def check(index):
    errors = []

    def require(ok, message):
        if not ok:
            errors.append(message)

    e = index['latest_evaluation']
    run = ROOT / e['run']
    summary = read_json(run / 'summary.json')
    protocol = read_json(ROOT / e['protocol'])
    manifest = read_json(ROOT / e['manifest'])
    outcomes = [json.loads(line) for line in (run / 'case_outcomes.jsonl').read_text().splitlines() if line]
    require(Counter(r['status'] for r in outcomes) == summary['statuses'], 'Outcome counts differ from summary')
    require(len(outcomes) == summary['total_cases'], 'Total denominator differs')
    require(len({r['id'] for r in outcomes}) == len(outcomes), 'Duplicate case IDs')
    require({r['id'] for r in outcomes} == set(protocol['case_ids']), 'Selected case IDs differ')
    require(summary['model_policy'] == protocol['model_policy'], 'Model policy differs from protocol')
    for path, expected in [(ROOT / e['protocol'], summary['protocol_sha256']),
                           (ROOT / e['manifest'], summary['manifest_sha256']),
                           (run / 'case_outcomes.jsonl', summary['outcomes_sha256'])]:
        require(digest(path) == expected, f'Evaluation digest changed: {path.relative_to(ROOT)}')
    require(manifest['protocol_sha256'] == digest(ROOT / e['protocol']), 'Manifest protocol changed')
    for r in outcomes:
        engine = r.get('explorer', {})
        if r['status'] == 'EQUIV-FIXPOINT':
            result = engine.get('result', {})
            require(result.get('closed') is True and
                    result.get('bounded_horizon_ms') is None and
                    result.get('bounded_horizon_ticks') is None and
                    engine.get('claim') == 'EQUIV-FIXPOINT', f'Positive is not H-free/closed: {r["id"]}')
        if r['status'] == 'DIVERGE_CONFIRMED':
            require(any(x.get('confirmed') for x in engine.get('replays', [])), f'No replay: {r["id"]}')

    layout = index.get('source_layout')
    audit_seen, evidence_count = set(), 0

    def audit_evidence(path):
        nonlocal evidence_count
        if path in audit_seen:
            return
        audit_seen.add(path)
        for a in read_json(path)['audits']:
            for artifact in a.get('evidence_artifacts', []):
                name = artifact['path']
                p = ROOT / name
                evidence_count += 1
                if layout and name in layout.get('document_moves', {}):
                    with zipfile.ZipFile(ROOT / index['archive']['path']) as z:
                        original = z.read(name)
                    target = ROOT / layout['document_moves'][name]
                    require(hashlib.sha256(original).hexdigest() == artifact['digest'] and
                            target.is_file() and target.read_bytes() == relocated_document(name, original, layout),
                            f'Relocated audit document changed beyond references: {name}')
                else:
                    require(p.is_file() and digest(p) == artifact['digest'],
                            f'Frozen audit evidence changed: {name}')
                if p.name == 'results-audit.json' and p.is_file():
                    audit_evidence(p)

    audit_evidence(ROOT / e['audit'])
    source_count = 0
    layout = index.get('source_layout')
    layout_names = set()
    layout_sources = {}
    if layout:
        require(layout['baseline_protocol_sha256'] == digest(ROOT / e['protocol']),
                'Source layout belongs to a different evaluation; review or retire the layout mapping')
        for name, expected in layout.get('package_files', {}).items():
            path = ROOT / name
            require(path.is_file() and digest(path) == expected,
                    f'Diagnostic package initializer changed: {name}')
        layout_names = set(layout['moves']) | set(layout['import_updates'])
        require(layout_names <= set(protocol['sources']), 'Layout lists unknown evaluated sources')
        with zipfile.ZipFile(ROOT / (e['run'] + '_sources.zip')) as z:
            layout_sources = {name: z.read(name) for name in layout_names}
    for name, expected in protocol['sources'].items():
        p = ROOT / name
        if p.suffix == '.md':  # Explanatory docs may evolve; frozen ZIP retains the evaluated version.
            continue
        source_count += 1
        if name in layout_names:
            original = layout_sources[name]
            require(hashlib.sha256(original).hexdigest() == expected,
                    f'Layout baseline differs from frozen source: {name}')
            target = ROOT / layout['moves'].get(name, name)
            require(target.is_file() and target.read_bytes() == relocated_source(name, original, layout),
                    f'Source differs beyond recorded layout/import edits: {name}')
            if name in layout['moves']:
                require(not p.exists(), f'Obsolete duplicate source remains: {name}')
            continue
        require(p.is_file() and digest(p) == expected,
                f'Evaluator/model differs from selected run; retain historical result or reevaluate: {name}')

    archive = ROOT / index['archive']['path']
    require(digest(archive) == index['archive']['sha256'], 'Historical archive changed')
    with zipfile.ZipFile(archive) as z:
        old = json.loads(z.read('ARCHIVE_INDEX.json'))['files']
        require(len(old) == index['archive']['files'], 'Archive file count differs')
        for name, meta in old.items():
            require(hashlib.sha256(z.read(name)).hexdigest() == meta['sha256'], f'Archive member changed: {name}')
        for item in index['appendices']:
            member = item.get('archive_member', item['path'])
            original = z.read(member)
            target = ROOT / item['path']
            expected = relocated_document(member, original, layout) if layout else original
            require(target.is_file() and target.read_bytes() == expected,
                    f'Versioned appendix changed beyond reference relocation: {item["path"]}')

    for item in index.get('additional_archives', []):
        path = ROOT / item['path']
        require(path.is_file(), f'Missing archive: {item["path"]}')
        if not path.is_file():
            continue
        require(digest(path) == item['sha256'], f'Archive changed: {item["path"]}')
        with zipfile.ZipFile(path) as z:
            members = json.loads(z.read('ARCHIVE_INDEX.json'))['files']
            require(len(members) == item['files'], f'Archive count differs: {item["path"]}')
            require(set(z.namelist()) == set(members) | {'ARCHIVE_INDEX.json'},
                    f'Archive inventory differs: {item["path"]}')
            for name, meta in members.items():
                data = z.read(name)
                require(len(data) == meta['bytes'] and
                        hashlib.sha256(data).hexdigest() == meta['sha256'],
                        f'Archive member changed: {name}')

    managed = list(index['canonical'].values()) + index['redirects'] + index.get('guides', [])
    link_count = 0
    for name in managed:
        p = ROOT / name
        require(p.is_file(), f'Missing managed document: {name}')
        if not p.is_file():
            continue
        # This project uses inline Markdown links. Ignore code examples and external URLs.
        text = re.sub(r'```.*?```', '', p.read_text(), flags=re.S)
        for target in re.findall(r'\[[^\]\n]*\]\(([^)\s]+)\)', text):
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            path = p.parent / unquote(url.path) if url.path else p
            require(path.exists(), f'Broken link in {name}: {target}')
            link_count += 1
            if url.fragment and path.is_file() and path.suffix == '.md':
                slugs = set()
                for heading in re.findall(r'^#+\s+(.+)$', path.read_text(), flags=re.M):
                    slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
                    slugs.add(slug)
                require(unquote(url.fragment) in slugs, f'Broken heading link in {name}: {target}')
    for item in index['appendices']:
        require((ROOT / item['path']).is_file(), f'Missing appendix: {item["path"]}')
    rendered = ROOT / index['canonical']['evaluation']
    require(rendered.is_file() and rendered.read_text() == evaluation_text(index),
            'Generated evaluation is stale: run python3 explorer/docs/manage.py render')
    if errors:
        raise SystemExit('\n'.join('FAIL ' + x for x in errors))
    print(f'PASS: {len(managed)} managed documents, {link_count} local links; '
          f'{len(outcomes)} outcomes; {evidence_count} frozen audit references; '
          f'{source_count} evaluator/model sources; '
          f'{1 + len(index.get("additional_archives", []))} archives and reference-rebased appendices; generated summary.')
    print('Scope: structural/numeric/hash consistency. Semantic prose/proof review remains manual.')
    if layout:
        print(f'Layout: {len(layout["moves"])} relocated modules; '
              'exact imports/CLI, repository-root and snapshot-inventory edits checked against frozen source ZIP. '
              'Historical evaluation was not rerun.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['render', 'check'])
    args = parser.parse_args()
    index = read_json(INDEX)
    if args.command == 'render':
        (ROOT / index['canonical']['evaluation']).write_text(evaluation_text(index))
        print('Rendered ' + index['canonical']['evaluation'])
    else:
        check(index)


if __name__ == '__main__':
    main()
