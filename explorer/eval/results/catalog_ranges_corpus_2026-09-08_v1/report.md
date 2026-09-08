# Catalog 범위 연결 후 H 없는 전체 평가

2026-09-08. 같은 388개 후보, LLM 호출 0회. H=None, 입력 격자 100ms, 정확한 만료 1ms,
상태 200000/전이 500000/입력 조합 100000, 사례별 process 20초/768MiB 등 기존 상한 유지.
프로토콜·manifest·122개 소스 ZIP을 실행 전에 동결했다. 전체 실행 약 24.64초.

| 최종 판정 | 기존 unbounded v2 | 이번 catalog-range v1 |
| --- | ---: | ---: |
| EQUIV-FIXPOINT | 187 | **189** |
| 재생 확인 DIVERGE | 95 | **95** |
| TIMEOUT/미완료 | 2 | **0** |
| REFUSED | 43 | **43** |
| 기존 GENERATION_ERROR | 59 | **59** |
| PREPARATION_ERROR | 2 | **2** |
| 합계 | 388 | 388 |

189개 인증은 concrete event BFS 폐쇄 185개와 기존 symbolic-value-flow 완료 4개다.
새 relational/SMT corpus 인증이 생긴 것은 아니다. 43개 거절은 준비 42개와 실행 1개다.
모든 긍정 결과에 H=None과 closed가 있고, 모든 불일치에 실제 재생 확인이 있다.
동등 인증은 준비된 IR–코드의 모델 내 ACTION trace에 대한 것이며 자연어 정답률이 아니다.

## 바뀐 두 사례

- **C15_005:** “평일 오전 8시부터 자정까지 한 시간마다 카메라로 사진을 찍어줘.”
- **C18_003:** “밤10시부터 자정까지 10분마다 긴급 사이렌을 울려줘.”

둘 다 IR 종료 조건은 `clock.time >= 2400`, 코드 종료 조건은 `clock_hour >= 24`다.
정정한 catalog의 Hour 0~23/Minute 0~59에서 둘 다 항상 거짓이다. 시간 의존성이 없다는
증명 후 원래 프로그램을 계속 실행하여 각각 **상태 1개 / 양쪽 step 합계 4회**로 폐쇄했다.
두 TIMEOUT만 EQUIV-FIXPOINT로 바뀌었고 나머지 386건은 판정이 같다.

**원문 품질 이슈는 남는다:** 이 IR과 코드는 둘 다 자정을 지나 계속 행동한다.
두 프로그램이 같다는 판정은 맞지만 자연어의 “자정까지”를 만족한다는 뜻은 아니다.
dataset, IR, 후보를 편집하거나 이 사례를 분모에서 제외하지 않았다. 의도를 바로잡는
reference 교정은 별도 데이터 버전에서 해야 한다. 새 자정 경계 테스트는 `hour == 0`으로
실제로 중단하는 코드와 기존 계속 실행 IR 사이의 ACTION 반례를 확인한다.

## 변경의 근거와 검증

- catalog 기존 `bound` 필드 사용: Hour 0~24→0~23, Minute/Second 0~60→0~59와 설명문만 수정.
  Clock.Delay 인자 및 모든 서비스 함수/설명문은 이전 소스 ZIP과 완전히 동일하다.
  read-role review hash는 그 비교를 근거로 갱신하고 stale hash 거절은 유지했다.
- [범위 판별·시간 의존성 제거의 충분조건](../../../CATALOG_RANGE_ANALYSIS.md).
  원래 AST를 고치지 않고 읽기 전용 비교 결과의 상수성만 시간 상태 병합에 이용한다.
  일반 clock 관찰, 저장된 시각, 실제 경계 조건은 유지한다. 선언이 없거나 유효하지 않으면
  새 증명을 사용하지 않는다. 일반 무한 반복의 판정 가능성을 주장하지 않는다.
- **289개 regression 통과**: 기존 274 + 신규 15. 구간 비교 전수 대조, 경계/자정 반례 재생,
  catalog 범위 변경, 잘못된 선언, unknown wrapper, snapshot, H/cap, 원본 보존 검사 포함.
  E1은 실행기 변경이 없어 이전 563이력 근거를 유지하며 이번에 새 측정한 것으로 세지 않는다.
- 후보 hash, 준비 payload와 input/GV/time model은 388개 모두 이전과 같다. catalog 및
  분석 구현의 명시적인 변경이 있으므로 무변경 반복 실험이라고 부르지 않는다.

개발 중 즉시 종료 테스트가 내부 상태 수 0을 기대했으나 DoneLatch가 흡수 상태 1개를
저장했다. 무행동·다음 wake 없음으로 검사를 고쳤으며 engine 변화 없이 통과했다.
준비 helper에 Path를 넘겨 JSON 직렬화가 실패한 부분 manifest도 별도 보존하고 동일
프로토콜에서 문자열 경로로 다시 준비했다. 전체 평가 실행은 1회이며 실패 사례 재시도나
결과 선택은 없다. 나머지 초기 진단 호출/ZIP 경로 오류는 후속 검증 JSON에 기록했다.
검증 뒤 timed.py 모듈 설명문만 갱신했으며 정확히 되돌리면 검증 당시 SHA와 같음을 확인했다.

## 증거 파일과 해석 범위

- [전체 결과](case_outcomes.jsonl), [집계](summary.json), [비교·무H/폐쇄·재생·SHA 검사](followup_verification.json).
- [프로토콜](../catalog_ranges_corpus_2026-09-08_v1_protocol.json),
  [manifest](../catalog_ranges_corpus_2026-09-08_v1_manifest.json),
  [동결 소스](../catalog_ranges_corpus_2026-09-08_v1_sources.zip),
  [실행 로그](../catalog_ranges_corpus_2026-09-08_v1_eval.log).
- [289개 회귀 기록](../catalog_ranges_validation_2026-09-08_v1.json),
  [catalog 전체 diff·함수 명세 동일성](../catalog_ranges_catalog_change_2026-09-08_v1.json).

기존 결과를 보고 만든 개선 및 익숙한 후보의 재평가이므로 exploratory evidence다.
독립 held-out, 외부 oracle, 자연어 의도 적합성 검증, 전체 구현의 기계 증명으로 해석하지 않는다.
이전 시간 생략/SMT 개발 결함과 해결 기록은 이전 감사에 보존하며 이번 통과로 숨기지 않는다.
