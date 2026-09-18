"""Count static operator nodes in the final E1 encodings; no IR execution.

Results JSON supplies encodings for 80 requests; irs.py supplies the original
12, whose execution records omit the IR. E1-024 uses its final rolling-window
JSON, replacing the superseded batch encoding. Independent timelines are
summed per request. Loops are not unrolled by this counter.
"""
import ast
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
E1 = ROOT / 'PerCom/08_Evaluation/E1_adequacy'
OPS = ['start_at', 'call', 'wait', 'delay', 'read', 'if', 'cycle', 'break', 'timer', 'let']


def nodes(value):
    if isinstance(value, dict):
        if 'op' in value:
            yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def depth(value, operators, level=0):
    """Maximum number of selected control operators on one syntax-tree path."""
    if isinstance(value, dict):
        level += value.get('op') in operators
        return max([level] + [depth(v, operators, level) for v in value.values()])
    if isinstance(value, list):
        return max([level] + [depth(v, operators, level) for v in value])
    return level


def structure(automations):
    ns = [n for a in automations for n in nodes(a['ir'])]
    ops = {n['op'] for n in ns}
    waits = [n for n in ns if n['op'] == 'wait']
    return {
        'control_depth': max(depth(a['ir'], {'if', 'cycle'}) for a in automations),
        'cycle_depth': max(depth(a['ir'], {'cycle'}) for a in automations),
        'operator_types_without_start_call': len(ops - {'start_at', 'call'}),
        'operator_set_without_start_call': ' + '.join(sorted(ops - {'start_at', 'call'})) or '(none)',
        'features': {
            'wait_and_cycle': {'wait', 'cycle'} <= ops,
            'read_and_if': {'read', 'if'} <= ops,
            'wait_and_if_and_cycle': {'wait', 'if', 'cycle'} <= ops,
            'delay_and_cycle': {'delay', 'cycle'} <= ops,
            'sustained_wait': any(n.get('for') for n in waits),
            'edge_wait': any(n.get('edge') in ('rising', 'falling') for n in waits),
            'timeout_wait': any(n.get('timeout') for n in waits),
            'nonempty_timeout_handler': any(n.get('on_timeout') for n in waits),
            'cron_anchor': any(n['op'] == 'start_at' and n.get('anchor') == 'cron' for n in ns),
        },
    }


def summarize(rows):
    sizes = [r['total_operators'] for r in rows]
    total = Counter()
    presence = Counter()
    for row in rows:
        total.update(row['operators'])
        presence.update(k for k, v in row['operators'].items() if v)
    return {
        'requests': len(rows), 'timelines': sum(r['timelines'] for r in rows),
        'operators': sum(sizes), 'min': min(sizes), 'median': median(sizes),
        'mean': mean(sizes), 'max': max(sizes),
        'size_histogram': dict(sorted(Counter(sizes).items())),
        'operator_occurrences': {op: total[op] for op in OPS},
        'request_presence': {op: presence[op] for op in OPS},
    }


def main():
    hashes = {}

    def read(path):
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path.read_text(encoding='utf-8-sig')

    def read_json(relative):
        return json.loads(read(E1 / relative))

    corpus = list(csv.DictReader(read(E1 / 'breadth/corpus_100.csv').splitlines()))
    eligible = {r['corpus_id']: r for r in corpus if r['screen_status'] == 'IN_SCOPE'}
    seed_ids = {r['prior_case_id']: r['corpus_id'] for r in corpus if r['stage_a'] == 'yes'}
    entries = {}

    def add(cid, automations, source):
        assert cid not in entries and cid in eligible, cid
        assert automations and all('timeline' in a['ir'] for a in automations)
        entries[cid] = {'automations': automations, 'source': source}

    # The seed source is solely literal assignments and dict(...) constructors.
    seed_source = read(E1 / 'irs.py')
    tree = ast.parse(seed_source)
    assert all(isinstance(n, (ast.Assign, ast.Expr)) for n in tree.body)
    assert all(isinstance(n.func, ast.Name) and n.func.id == 'dict'
               for n in ast.walk(tree) if isinstance(n, ast.Call))
    namespace = {'__builtins__': {'dict': dict}}
    exec(compile(tree, 'irs.py', 'exec'), namespace)
    for row in read_json('runs/e1_stageA.json'):
        add(seed_ids[row['id']], [{'name': row['id'], 'ir': namespace['IRS'][row['id']]['ir']}],
            'irs.py (seed IR; not embedded in execution result)')

    for relative in ['breadth/depth/runs/e1_depth_v2.json'] + [
        'breadth/remaining72/{}/runs/results.json'.format(b)
        for b in ('batch_er', 'batch_official', 'batch_community')
    ]:
        for row in read_json(relative):
            add(row['id'], row['automations'], relative)

    relative = 'breadth/remaining72/e1_024_rolling/timeline_ir.json'
    ir = read_json(relative)
    record = read_json('breadth/remaining72/e1_024_rolling/results.json')
    assert hashes[str((E1 / relative).relative_to(ROOT))] == record['files_sha256']['timeline_ir.json']
    entries['E1-024'] = {'automations': [{'name': 'rolling600_second_slots', 'ir': ir}], 'source': relative}
    assert len(entries) == 92 and set(entries) == set(eligible)

    rows = []
    for cid, entry in sorted(entries.items()):
        per_timeline = []
        counts = Counter()
        for auto in entry['automations']:
            c = Counter(n['op'] for n in nodes(auto['ir']))
            assert not set(c) - set(OPS), set(c) - set(OPS)
            counts.update(c)
            per_timeline.append({'name': auto['name'], 'total_operators': sum(c.values()), 'operators': dict(c)})
        row = {
            'id': cid, 'source_stratum': eligible[cid]['source_stratum'],
            'request': eligible[cid]['original_text'], 'timelines': len(per_timeline),
            'total_operators': sum(counts.values()),
            'operator_types': len(counts), 'operators': {op: counts[op] for op in OPS},
            'per_timeline': per_timeline, 'ir_source': entry['source'],
            'structure': structure(entry['automations']),
            'request_behavior_labels': [v.strip() for v in eligible[cid]['rb_adjudicated'].split(',')],
        }
        rows.append(row)

    summary = summarize(rows)
    without = summarize([r for r in rows if r['id'] != 'E1-024'])
    other89 = summarize([r for r in rows if r['id'] not in ('E1-024', 'E1-066', 'E1-070')])
    structural_summary = {
        'control_depth_histogram': dict(sorted(Counter(r['structure']['control_depth'] for r in rows).items())),
        'cycle_depth_histogram': dict(sorted(Counter(r['structure']['cycle_depth'] for r in rows).items())),
        'operator_types_histogram': dict(sorted(Counter(r['operator_types'] for r in rows).items())),
        'operator_types_without_start_call_histogram': dict(sorted(Counter(r['structure']['operator_types_without_start_call'] for r in rows).items())),
        'operator_sets_without_start_call': dict(sorted(Counter(r['structure']['operator_set_without_start_call'] for r in rows).items())),
        'feature_presence': dict(sorted(Counter(k for r in rows for k, v in r['structure']['features'].items() if v).items())),
        'request_behavior_label_presence': dict(sorted(Counter(k for r in rows for k in r['request_behavior_labels']).items())),
        'legacy_R_label_count_histogram': dict(sorted(Counter(sum(k.startswith('R') for k in r['request_behavior_labels']) for r in rows).items())),
        'requests_with_two_or_more_legacy_R_labels': sum(sum(k.startswith('R') for k in r['request_behavior_labels']) >= 2 for r in rows),
        'requests_with_boundary_labels': sum(any(k.startswith('B') for k in r['request_behavior_labels']) for r in rows),
    }
    result = {
        'definition': 'Static JSON nodes with op, including start_at, loop bodies, both branches and on_timeout. Each syntactic occurrence counts once, even when reusing a Python object. Condition expressions, arguments and attributes (for/timeout/until/count/period) are not additional operators. Independent timelines are summed per request; this is not executed action count or compiled instruction count.',
        'provenance_note': 'Original 12 encodings are read from current irs.py because legacy result files do not embed them; remaining 80 are taken from recorded result JSON, except E1-024 whose replacement JSON matches the final run hash. No renderer, runner, or verifier is executed.',
        'summary_all_92': summary,
        'sensitivity_excluding_E1_024_only': without,
        'sensitivity_excluding_three_expanded_encodings': other89,
        'structural_summary': structural_summary,
        'structural_definitions': 'Control depth counts nested if/cycle operators on one path, including outer polling/rearming cycles; cycle depth counts cycle operators alone. Max depth is taken across independent timelines per request. Co-occurrence means features appear somewhere in the same request, not necessarily on the same path. R/B labels describe the source requests using existing rb_adjudicated labels; operator statistics describe the chosen final encodings. Neither is a calibrated difficulty score.',
        'source_sha256': hashes, 'cases': rows,
    }
    (OUT / 'e1_operator_counts.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    fields = ['id', 'source_stratum', 'timelines', 'total_operators', 'operator_types', 'control_depth', 'cycle_depth', 'operator_types_without_start_call'] + OPS + ['request', 'ir_source']
    with (OUT / 'e1_operator_counts.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            values = {**r, **r['structure'], **r['operators']}
            writer.writerow({k: values[k] for k in fields})
    lines = [
        '# E1 요청 92건의 최종 Timeline IR 연산자 집계', '',
        '집계 단위: IR에 작성된 정적 `op` 노드. `start_at` 포함. 반복 본문·조건 분기·timeout 처리 내부까지 세되, 반복 실행 횟수는 곱하지 않는다. 조건식과 `for`, `timeout`, `until`, `period` 등의 속성은 별도 연산자가 아니다. 여러 Timeline으로 나눈 요청은 요청 단위로 합산한다.', '',
        '## 전체 요약', '',
        '- 요청 {}건, Timeline {}개, 연산자 총 {:,}개.'.format(summary['requests'], summary['timelines'], summary['operators']),
        '- 요청당 최솟값 {}, 중앙값 {}, 평균 {:.2f}, 최댓값 {:,}.'.format(summary['min'], summary['median'], summary['mean'], summary['max']),
        '- E1-024는 600개 시간 슬롯을 펼친 최종 스프링클러 IR이다. 전체 집계에 포함했다. 이 한 건을 제외한 보조 집계: 91건, 총 {:,}개, 중앙값 {}, 평균 {:.2f}, 범위 {}–{}개.'.format(without['operators'], without['median'], without['mean'], without['min'], without['max']), '',
        '- E1-066(일산화탄소 감지 후 점멸) 905개와 E1-070(초인종 후 점멸) 606개도 150회 점멸을 명시적으로 펼친 IR이다. 이 두 건과 E1-024를 제외한 89건은 {}–{}개, 중앙값 {}, 평균 {:.2f}개이다. 이는 인코딩 방식이 정적 크기에 미치는 영향을 보여주는 보조 설명이며, 전체 92건 집계를 대체하지 않는다.'.format(other89['min'], other89['max'], other89['median'], other89['mean']), '',
        '| 연산자 | 전체 등장 횟수 | 포함 요청 수 / 92 |', '| --- | ---: | ---: |',
    ]
    for op in OPS:
        lines.append('| `{}` | {} | {} |'.format(op, summary['operator_occurrences'][op], summary['request_presence'][op]))
    lines += ['', '## 구조 특성', '',
              '중첩 깊이는 한 경로에 놓인 `if`/`cycle`의 수이며 외부 감시 반복도 포함한다. 독립 Timeline 사이에서는 최댓값을 취한다. 종류 조합은 요청 단위의 동시 포함이며 같은 실행 경로에서 반드시 함께 실행된다는 뜻은 아니다.', '',
              '| 지표 | 값 또는 분포 |', '| --- | --- |',
              '| 제어 중첩 깊이 → 요청 수 | {} |'.format(structural_summary['control_depth_histogram']),
              '| 반복 중첩 깊이 → 요청 수 | {} |'.format(structural_summary['cycle_depth_histogram']),
              '| start_at/call 제외 종류 수 → 요청 수 | {} |'.format(structural_summary['operator_types_without_start_call_histogram']),
              '| start_at/call 제외 서로 다른 종류 조합 | {} |'.format(len(structural_summary['operator_sets_without_start_call'])),
              '| 기존 R 태그가 2개 이상 (행동 요소 수 아님) | {} / 92 |'.format(structural_summary['requests_with_two_or_more_legacy_R_labels']),
              '| 기존 요청 분류에서 경계 요소 포함 | {} / 92 |'.format(structural_summary['requests_with_boundary_labels']), '',
              '기존 R/B 태그는 복합 동작을 누락하거나 하나로 축약한 경우가 있어, 태그 수를 행동 요소 수 또는 복잡도로 해석하지 않는다. 새 92건 전수 검토는 E1_BEHAVIOR_REVIEW_KO.md를 참조한다. 요청의 R/B 태그와 최종 IR의 구조는 별개 지표다. 이벤트 감시나 재무장을 구현하려고 추가한 `cycle`도 구조 집계에 들어가므로, `cycle` 포함 빈도를 반복 행동을 요청한 비율로 해석하지 않는다.']
    lines += ['', '## 요청별 집계', '', '| 요청 | Timeline 수 | 총 연산자 | 종류 수 | 종류별 개수 |', '| --- | ---: | ---: | ---: | --- |']
    for r in rows:
        detail = ', '.join('{} {}'.format(op, n) for op, n in r['operators'].items() if n)
        lines.append('| {} | {} | {} | {} | {} |'.format(r['id'], r['timelines'], r['total_operators'], r['operator_types'], detail))
    lines += ['', '## 근거와 재현', '',
              '실험을 재실행하지 않고 저장된 IR만 읽었다. 기존 12건은 결과 JSON에 IR이 없어 현재 `irs.py`의 정의를 사용했다. 나머지 80건은 실행 결과에 저장된 IR을 사용하되, E1-024는 최종 실행 기록의 SHA-256과 일치하는 교체 IR을 사용했다. 초기 실패 IR, 별도 진단용 변형, JOI 대체 구현은 중복 집계하지 않았다.', '',
              '입력 파일 해시·Timeline별 세부 수치는 `e1_operator_counts.json`, 92건의 열별 수치는 `e1_operator_counts.csv`에 저장했다.', '',
              '재현: `python count_e1_operators.py` (이 파일과 같은 폴더).']
    (OUT / 'E1_OPERATOR_COUNTS_KO.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'all_92': summary, 'excluding_E1_024': without,
                      'largest_five': [(r['id'], r['total_operators']) for r in sorted(rows, key=lambda r: r['total_operators'], reverse=True)[:5]],
                      'multi_timeline': [(r['id'], r['timelines']) for r in rows if r['timelines'] > 1]}, indent=2))


if __name__ == '__main__':
    main()
