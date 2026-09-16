# E2 latest-binding rerun — 2026-09-15

실행 당시 기준 HEAD `0e76584`의 timer-zone 및 fixed-aggregation 개선과 2026-09-14
바인딩 결정 B1/B2/B5를 합친 E2 재실행 결과다. 동결된 142쌍, 이력, pair당
Explorer 예산 120초는 유지했다. B1/B2는 전체 142쌍을 실행했고, B5가
적용되는 22쌍을 별도 재실행하여 해당 행만 교체했다.

최종 원자료는 `runs/e2_run.binding-final.jsonl`이며 SHA-256은
`8e3cb15d9046c174121bc6ef7a8b0b1a65b90e501a38d3c0e58c586a01b900a1`이다.
B1/B2 전체판은 `runs/e2_run.binding-v1.jsonl`
(`214e9e2323e52f972e0406711297f091739e1068198a845cb9a5e58d52269eaf`),
B5 교체 행은 `runs/e2_run.binding-b5.partial.jsonl`
(`2f34d7cd351978cef0643d172dfa7e7ede93e72930c4dcbc2438631b323f0b9a`)에
보존했다.

## 최종 분포

| Explorer 판정 | 쌍 수 |
|---|---:|
| EQUIV | 56 |
| DIVERGE | 75 |
| REFUSED | 6 |
| TIMEOUT | 5 |
| 합계 | 142 |

독립 reference와의 관계는 다음과 같다.

| 관계 | 쌍 수 |
|---|---:|
| AGREE-EQUIV-ON-CHECKED | 56 |
| AGREE-DIVERGE | 66 |
| Explorer witness를 reference로 재생해 DIVERGE 확인 | 8 |
| Explorer DIVERGE, reference JoI 실행 미지원 | 1 |
| Explorer REFUSED | 6 |
| Explorer TIMEOUT | 5 |
| 합계 | 142 |

Explorer가 EQUIV를 낸 56쌍은 모두 reference에서도 checked-equivalent였다.
DIVERGE 75쌍 중 74쌍은 reference의 전체 이력 또는 Explorer witness의
reference 재생으로 차이가 확인됐다. C24_003/llm 한 쌍은 Explorer가
구체 반례를 냈지만 reference JoI 실행기가 해당 구성을 지원하지 않았다.
따라서 이 문서 시점에는 이 한 쌍을 독립 확인된 DIVERGE로 세지 않았다.

**추가 (2026-09-16):** 미초기화 변수 산술을 runtime error로 정하는 R14
(whisoo 결정, `RUNTIME_CONTRACT.md`)를 두 도구에 넣으면서 C24_003/llm 은
reference 전체 이력에서 REF-DIVERGE가 됐고 AGREE-DIVERGE로 옮겼다. 그래서
현재 수치는 DIVERGE 75쌍 전부가 독립 확인이다. 이 문서의 위 숫자는
2026-09-14 시점의 기록으로 그대로 둔다.

입력 검증 오류 C20_011/llm 한 쌍을 행동 비교 모집단에서 분리하면 유효
141쌍 중 131쌍이 EQUIV 또는 DIVERGE로 판정됐다(92.9%). 남은 행동 미판정
10쌍은 E1-099의 동적 산술 시한 관계 5쌍(REFUSED)과 C07의 유한 상태곱
폭발 5쌍(TIMEOUT)이다. 이 비율은 정확도가 아니라 이 평가 모집단에서의
판정 완료율이다.

## B5 영향

B5 적용 대상은 22쌍이었고, B1/B2 전체판과 최종 판정 조합이 달라진 것은
7쌍이다.

- 바인딩 차이로 EQUIV 전환: C16/fault1, C21_003/llm,
  E1-062/fault3, E1-086/fault3.
- Explorer의 DIVERGE는 유지되지만 reference 전체 이력 판정이
  `REF-UNSUPPORTED-JOI`로 바뀌고 witness 재생으로 차이를 확인:
  C16/fault2, C16/fault3, C16/fault4.

Fault cohort에서 EQUIV인 네 쌍 가운데 위 세 fault는 바인딩 범위 밖으로
재분류한다. 나머지 C09/fault4는 기존 감사와 같이 구성상 관측 불가능한
변형으로 양쪽 모두 EQUIV다. 이를 false accept로 세지 않는다.

## 실행 이력과 제한

첫 시도는 `run_binding_v1.py`가 저장소에 없는 비압축
`supplement_histories.json`만 찾는 문제로 initializer에서 즉시 실패했다.
계산된 pair는 없었고 142행 모두 HARNESS-ERROR였다. 실패 산출물은
`runs/e2_run.binding-v1.failed-missing-supp.*`로 보존했다. harness가 기존
`supplement_histories.json.gz`를 읽도록 고친 뒤 관련 회귀 23개를 통과시키고
재실행했다.

B1/B2 전체판은 16 workers로 2026-09-14 23:55:10부터 2026-09-15
02:16:21까지 실행됐다. B5 22쌍 재실행과 최종 결합은 02:34:50에 끝났다.
동등성 후보에서 reference가 모든 history와 selector assignment를 소진하므로
일부 pair wall time이 30분을 넘었다. 이 결과는 동일한 동결 pair에 대한
개발 후속 실행이며 독립 표본의 confirmatory replication은 아니다.
