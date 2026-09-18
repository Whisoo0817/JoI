"""Summarize a new assistant review of all 92 requirements; not an IR run.

Annotations in e1_behavior_review.tsv are explicit judgments based on source
requests and recorded interpretations. They are not inferred from IR node counts
and do not replace the historical author-coded R/B labels.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CORPUS = ROOT / 'PerCom/08_Evaluation/E1_adequacy/breadth/corpus_100.csv'
FEATURES = {
    'G': '추가 상태·시간대 가드',
    'B': '여러 트리거·일정 규칙 또는 동작 대안',
    'A': '여러 종류의 출력 동작',
    'Q': '순서가 있는 실행 단계·사건',
    'D': '경과 시간·지연·응답 제한',
    'U': '조건의 연속 지속',
    'R': '동작 반복·점멸 효과',
    'H': '과거 사건·값·횟수·누적량 이용',
    'X': '취소·재시작·억제·복원·복구·실패 처리',
    'P': '독립 흐름의 동시 진행',
}
GROUPS = {
    'direct': '단일 사건·조건에서 한 종류의 동작',
    'conditional': '추가 가드·여러 규칙·여러 출력 동작',
    'temporal': '시간 진행·이력·실행 관리·독립 흐름',
}
NATIVE_EFFECT = {'E1-038', 'E1-041'}


def group(cid, features):
    # The recorded evaluation boundary supplies Blink as one native operation
    # for these two cases. Do not treat device-internal blinking as a loop that
    # the automation controller must manage. Preserve R in the descriptive tags.
    effective = features - ({'R'} if cid in NATIVE_EFFECT else set())
    if effective & set('QDURHXP'):
        return 'temporal'
    return 'conditional' if effective else 'direct'


def main():
    with CORPUS.open(encoding='utf-8-sig') as stream:
        corpus = {r['corpus_id']: r for r in csv.DictReader(stream) if r['screen_status'] == 'IN_SCOPE'}
    with (HERE / 'e1_behavior_review.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    assert len(rows) == 92 and {r['id'] for r in rows} == set(corpus)
    stats = {mode: {'groups': Counter(), 'features': Counter()} for mode in ('source', 'evaluation')}
    for row in rows:
        source = set(row['source_features'].split(',')) - {'-'}
        extra = set(row['evaluation_extra_features'].split(',')) - {''}
        assert (source | extra) <= set(FEATURES)
        assert not source & extra
        row['source_features'] = sorted(source)
        row['evaluation_extra_features'] = sorted(extra)
        row['source_text'] = corpus[row['id']]['original_text']
        row['source_url'] = corpus[row['id']]['source_url']
        row['source_locator'] = corpus[row['id']]['source_locator']
        for mode, tags in [('source', source), ('evaluation', source | extra)]:
            row[mode + '_group'] = group(row['id'], tags)
            stats[mode]['groups'].update([row[mode + '_group']])
            stats[mode]['features'].update(tags)
    summary = {
        'status': 'New assistant semantic review, not yet author-validated. Descriptive overlapping features and presentation groups, not difficulty scores or a claim about collection quotas.',
        'author_collection_intent': 'User stated in this conversation that complex requests were prioritized in collection. This states intent; it does not establish that every collected item is complex or that probability/popularity sampling was used.',
        'definitions': FEATURES,
        'groups': GROUPS,
        'native_blink_boundary_cases': sorted(NATIVE_EFFECT),
        'statistics': stats,
        'input_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (CORPUS, HERE / 'e1_behavior_review.tsv')},
        'cases': rows,
    }
    (HERE / 'e1_behavior_review.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    lines = [
        '# E1 요청 92건의 행동 요구 재분류', '',
        '작성: 2026-09-19. 기존 R/B 태그 개수 해석을 정정하기 위한 **새 assistant 검토안**이다. 저자 확정 분류라고 주장하지 않으며, 기존 corpus 태그나 논문은 변경하지 않았다.', '',
        '## 수집 의도와 분석 결과', '',
        '저자는 이번 대화에서 복잡한 요청을 우선 찾아 수집했다고 설명했다. 이는 수집 의도로 기술할 수 있다. 수집된 모든 사례가 복잡하다거나 특정 난이도 할당량을 충족했다는 뜻은 아니다. 출처는 무작위 추출·사용 빈도순 수집으로 설명하지 않는다.', '',
        '원문의 요청과 기록된 평가 해석을 따로 읽어 분류했다. IR에 감시 반복문이 있다는 이유로 요청에 반복 행동을 붙이지 않았으며, native Blink 호출 두 건의 내부 효과를 자동화 자체의 반복 제어로 세지 않았다. 단일 매일/매주 일정, 기본 사건 검출, 단일 설정 동작, 같은 동작의 여러 대상 바인딩만으로 복잡도를 높이지 않았다.', '',
        '세 그룹은 지면상 요약을 위한 구분이며 난이도 등급이 아니다. 시간·이력·실행 관리·독립 흐름 요소가 하나라도 있으면 세 번째 그룹, 나머지 중 추가 가드/여러 규칙/여러 출력이 있으면 두 번째, 그 외는 첫 번째로 구분한다.', '',
        '| 그룹 | 원문 기준 | 확정 평가 해석까지 포함 |', '| --- | ---: | ---: |',
    ]
    for code, label in GROUPS.items():
        lines.append('| {} | {} | {} |'.format(label, stats['source']['groups'][code], stats['evaluation']['groups'][code]))
    lines += ['', '원문 기준 분포는 공개 요청에 명시된 구조를, 평가 해석 기준 분포는 연구자가 고정한 실행 정책까지 포함한 실험 대상을 설명한다. 둘을 바꿔 쓰지 않는다. 원문에서 점멸을 요구하지만 평가에서 native Blink 한 번으로 다룬 E1-038·041은 첫 그룹에 들어간다. 원문에 같은 종류의 동작이 반복되는 효과가 있어도 실행 제어를 플랫폼에 맡긴 경우를 밝히기 위해서다.', '',
              '## 행동 요소의 정의와 중복 집계', '',
              '| 코드 | 의미 | 원문 포함 | 평가 해석 포함 |', '| --- | --- | ---: | ---: |']
    for code, label in FEATURES.items():
        lines.append('| {} | {} | {} | {} |'.format(code, label, stats['source']['features'][code], stats['evaluation']['features'][code]))
    lines += ['', '한 사례에 여러 요소를 함께 붙인다. 예를 들어 오븐의 지속 조건·확인 요청·응답 대기·타임아웃 종료를 하나의 즉시 반응 유형으로 축약하지 않는다. 특징 수가 1–10점 난이도를 뜻하지도 않는다. 반복/시간 의미가 기기 서비스에 포함되는지, 자동화가 직접 유지하는지도 구분한다.', '',
              '## 92건 전수 검토', '',
              '| ID | 요청 동작 요약 | 원문 요소 | 해석에서 추가 구체화 | 원문 그룹 / 평가 그룹 | 해석·범위 메모 |',
              '| --- | --- | --- | --- | --- | --- |']
    short = {'direct': '단일 동작', 'conditional': '조건·동작 확장', 'temporal': '시간·이력·실행 관리'}
    for row in rows:
        lines.append('| {} | {} | {} | {} | {} / {} | {} |'.format(
            row['id'], row['behavior_ko'], ', '.join(row['source_features']) or '기본 trigger–action',
            ', '.join(row['evaluation_extra_features']) or '—', short[row['source_group']], short[row['evaluation_group']], row['interpretation_note']))
    lines += ['', '## 본문 문안 제안', '',
              '> 시간 조건과 여러 실행 단계가 결합된 복잡한 자동화 요구를 우선적으로 찾고자, 공식 플랫폼 예제, 선행 연구 자료, 공개 참가자 응답, 커뮤니티 게시물에서 요청 100건을 수집했다. 연구 범위와 동작 해석을 검토한 뒤 92건을 평가 대상으로 확정했다. 이들 요청은 단일 사건에 동작을 수행하는 규칙부터 여러 조건과 기기 동작의 조합, 지속 조건과 반복, 응답 타임아웃, 실행 중 취소·재시작, 과거 이력에 따른 실행 제한, 독립 흐름의 동시 실행까지 포함한다.', '',
              '구체적인 빈도는 이번 전수 검토안의 정의를 저자가 검토한 뒤 본문 또는 부록에 사용할 수 있다. 현재 문안은 분류 숫자를 확정된 연구 결과처럼 추가하지 않는다. 수집 의도는 이번 저자 설명에, 유형 사례는 원문 및 확정 해석에 각각 근거한다.', '',
              '## 재현 및 원문 추적', '',
              '`e1_behavior_review.tsv`에 92건의 수동 검토 판단을 보존했다. `python summarize_e1_behavior_review.py`는 membership·태그 일관성을 검사하고 JSON과 이 보고서를 만든다. 원문·URL·locator는 JSON의 각 사례에 포함된다. 원문의 모든 행과 평가 spec을 읽어 만든 검토안이며, IR을 재실행하거나 원출처 웹페이지를 새로 감사한 것은 아니다. 새 분류는 기존 저자 확정 R/B 라벨을 대체하지 않는다.']
    (HERE / 'E1_BEHAVIOR_REVIEW_KO.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
