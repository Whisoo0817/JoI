# E2 개발 재평가와 한계 분류 — 2026-09-14

전체 동결 142쌍을 같은 120초 예산으로 재검사했다. 행동 비교 대상 140쌍 중
125쌍(89.3%)에서 판정을 완료했다. 나머지는 아래 두 유형에만 남았다.
원래 142쌍을 분모로 유지하면 판정 완료율은 88.0%다.

| 구분 | 쌍 수 | 의미 |
|---|---:|---|
| 판정 완료 | 125 | EQUIV 또는 구체 재생으로 확인한 DIVERGE |
| 계산된 수치 상태의 관계 추론 | 10 | 누적·평균 또는 증가 카운터로 계산한 값이 출력이나 기한을 결정함 |
| 유한 곱 상태의 폭증 | 5 | 저장값·여러 타이머·반복 제어의 조합이 현재 탐색 예산을 초과함 |
| 입력 검증에서 제외 | 2 | 구문 부적합 1, service mapping 오류 1 |

## 설명에 사용할 분류

“평가한 유효 프로그램에서는 대부분의 행동 동등성/차이를 판정했다.
미결정 사례는 **계산된 수치 상태의 관계 추론이 필요한 프로그램**과 **복합 제어로 상태가
폭증하는 프로그램**에 한정됐다.”

첫 유형은 시간 비교 구간만으로 동작을 보존할 수 없는 수치 계산이다.
센서값의 누적·평균을 출력하거나, 계속 증가하는 카운터로 기한을 계산하므로
추가 수치 관계 추론이 필요하다. 평균 계산은 매일 초기화되므로 모든 사례의
값이 끝없이 증가한다는 뜻은 아니다. 두 번째는 유한한 값과
제어 상태의 조합이 너무 큰 경우다. 추상화를 더 결합하거나 탐색을 개선할
여지가 있으므로 둘 모두 원리적으로 해결 불가능하다고 표현하지 않는다.

이 두 유형은 **이 E2 평가에서 남은 실패 원인**이다. 임의의 모든 JoI
프로그램이 이 두 유형 외에는 지원된다는 주장은 아니다. 기존 지원 단편의
query/GV/입력 모델/비동기 시간 등의 전제는 계속 적용된다.

## 대상 정리

`e2_population.json`이 새 행동 평가 대상의 규칙과 제외 기록이다.
C03_008/llm의 ACTION 위치 any는 사용자 언어 결정에 따른 파싱 오류다.
C20_011/llm은 TV에 선언되지 않은 Charger를 사용한 LLM service mapping
오류다. 이 두 쌍은 행동 비교 실패율의 분모에서 제외하고 입력 검증 단계에
별도 보고한다. 동결 pairs/histories/runs는 보존했다. 기존 142쌍 결과를
몰래 140쌍 결과로 바꾸지 않고, 이 수정된 모집단을 별도 버전으로 기록한다.

## 개선과 검증

원래 판정 완료 104쌍의 판정 변화: 0. 동결 정답기가 차이를
찾은 쌍에 대해 새 EQUIV를 낸 경우: 0.
원래 미결정에서 판정 완료로 바뀐 쌍: 21.

타이머 관계 v1의 5쌍에 더해, 입력 변경 시점을 보존하는 다단계 반례 생성,
나머지 카운터의 정확한 몫 상태, Hour 공통 변화의 과근사, 저장 timestamp의
경과 시간 관계를 구현했다. 양쪽 ACTION이 모든 포함 상태에서 같고 그래프가
닫힌 경우만 EQUIV다. 반례 후보의 인위적인 clock 입력은 제거하고 원래
시작 시각에서 구체 재생한 경우만 DIVERGE다.

지정된 기존 회귀와 timer-zones 회귀는 `results/checks-v4.jsonl`,
추가 use-site/시각/경계/반례 회귀는 `results/checks-extensions-v4.jsonl`에 기록한다.
새 증명 전제와 논증은 `explorer/docs/proof/TIMER_ZONES.md`에 있다.

## 독립 정답기와의 경계

정답기 코드를 읽거나 실행하지 않았다. 결과 비교에는 동결 판정 필드만
사용했다. 새 판정 완료 수치는 Explorer 개발 재평가이며, 새 반례 모두가
독립 정답기에 의해 확인됐다는 뜻은 아니다. 특히 C15/fault1, C14_003/llm은
동결 이력에서 차이를 못 찾았지만 새 구체 이력에서 차이를 찾았다.
정답기 담당자가 새 witness를 재실행한 뒤 최종 E2 정확도 수치를 확정해야 한다.

실패 사례를 보고 개선했고 제외 규칙도 이번에 명시했으므로 일반화 성능이나
확증 실험으로 포장하지 않는다. 군별 fault 쌍은 서로 독립 표본이 아니므로
쌍 수의 비율에 독립 표본을 가정한 통계적 신뢰구간을 붙이지 않는다.

## 실행 조건과 재현

별도 worktree `joi-timer-regions`, branch `timer-regions-20260914`.
입력 간격 100ms, 쌍당 120초, 상태 400,000, 전이 2,000,000, worker 4.
동결 비교와 동일하게 E2_BINDING_DECISION=false. 보호된 네 파일은 기준
`580053a`에서 그대로 유지했다. source digest와 실행 설정은
`results/extension-v4.meta.json`, 전체 분류는 `results/extension-v4-classified.json`.

```sh
~/temp/bin/python PerCom/08_Evaluation/E2_fidelity/handoff_timer/evaluate_timer.py --all-pairs --out /tmp/e2-new-full.jsonl --workers 4
~/temp/bin/python -m explorer.tests.test_timer_extensions
```

## 쌍별 원자료

| 쌍 | 이전 | 새 판정 | 상태 | 초 | 분류 |
|---|---|---|---:|---:|---|
| C01/correct | EQUIV | EQUIV | 6 | 0.02 | decided |
| C01/fault1 | DIVERGE | DIVERGE | 4 | 0.12 | decided |
| C01/fault2 | TIMEOUT | DIVERGE | 4 | 0.25 | decided |
| C01/fault3 | DIVERGE | DIVERGE | 7 | 0.25 | decided |
| C01/fault4 | DIVERGE | DIVERGE | 3 | 0.01 | decided |
| C01_014/llm | EQUIV | EQUIV | 1 | 0.21 | decided |
| C01_020/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C02_020/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C02_022/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C02_028/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C02_030/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C03/correct | EQUIV | EQUIV | 9 | 0.01 | decided |
| C03/fault1 | DIVERGE | DIVERGE | 5 | 0.01 | decided |
| C03/fault2 | DIVERGE | DIVERGE | 5 | 0.01 | decided |
| C03/fault3 | DIVERGE | DIVERGE | 11 | 0.01 | decided |
| C03/fault4 | DIVERGE | DIVERGE | 4 | 0.01 | decided |
| C03_008/llm | REFUSED | REFUSED | — | 0.0 | invalid_syntax |
| C03_027/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C04/correct | EQUIV | EQUIV | 1 | 0.0 | decided |
| C04/fault1 | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| C04/fault2 | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| C04/fault3 | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C04/fault4 | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| C05/correct | EQUIV | EQUIV | 4 | 0.04 | decided |
| C05/fault1 | DIVERGE | DIVERGE | 2 | 0.12 | decided |
| C05/fault2 | REFUSED | DIVERGE | 2 | 0.19 | decided |
| C05/fault3 | REFUSED | DIVERGE | 4 | 0.38 | decided |
| C05/fault4 | DIVERGE | DIVERGE | 4 | 0.28 | decided |
| C05_014/llm | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C05_021/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C05_028/llm | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C06_007/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C07/correct | TIMEOUT | TIMEOUT | — | 120 | finite_product_state_explosion |
| C07/fault1 | TIMEOUT | TIMEOUT | — | 120 | finite_product_state_explosion |
| C07/fault2 | TIMEOUT | TIMEOUT | — | 120 | finite_product_state_explosion |
| C07/fault3 | TIMEOUT | TIMEOUT | — | 120 | finite_product_state_explosion |
| C07/fault4 | TIMEOUT | TIMEOUT | — | 120 | finite_product_state_explosion |
| C07_018/llm | EQUIV | EQUIV | 1 | 0.0 | decided |
| C07_027/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C07_029/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C08_001/llm | EQUIV | EQUIV | 1 | 0.0 | decided |
| C08_032/llm | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C09/correct | EQUIV | EQUIV | 4 | 0.0 | decided |
| C09/fault1 | DIVERGE | DIVERGE | 5 | 0.0 | decided |
| C09/fault2 | DIVERGE | DIVERGE | 3 | 0.0 | decided |
| C09/fault3 | DIVERGE | DIVERGE | 2 | 0.0 | decided |
| C09/fault4 | EQUIV | EQUIV | 4 | 0.0 | decided |
| C09_004/llm | EQUIV | EQUIV | 1 | 0.0 | decided |
| C09_015/llm | EQUIV | EQUIV | 1 | 0.0 | decided |
| C10_007/llm | EQUIV | EQUIV | 4 | 0.0 | decided |
| C11/correct | EQUIV | EQUIV | 6 | 0.01 | decided |
| C11/fault1 | DIVERGE | DIVERGE | 6 | 0.01 | decided |
| C11/fault2 | DIVERGE | DIVERGE | 18 | 0.01 | decided |
| C11/fault3 | DIVERGE | DIVERGE | 6 | 0.01 | decided |
| C11/fault4 | DIVERGE | DIVERGE | 6 | 0.01 | decided |
| C12_012/llm | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| C12_013/llm | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| C13_006/llm | REFUSED | EQUIV | 2 | 0.0 | decided |
| C14_003/llm | REFUSED | DIVERGE | 3 | 0.01 | decided |
| C15/correct | REFUSED | EQUIV | 19 | 0.09 | decided |
| C15/fault1 | REFUSED | DIVERGE | 7 | 29.15 | decided |
| C15/fault2 | DIVERGE | DIVERGE | 72002 | 10.83 | decided |
| C15/fault3 | DIVERGE | DIVERGE | 18 | 8.61 | decided |
| C15/fault4 | DIVERGE | DIVERGE | 18 | 8.54 | decided |
| C15_013/llm | EQUIV | EQUIV | 0 | 0.0 | decided |
| C15_019/llm | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C16/correct | EQUIV | EQUIV | 0 | 0.0 | decided |
| C16/fault1 | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C16/fault2 | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C16/fault3 | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C16/fault4 | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C16_003/llm | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| C16_007/llm | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C16_011/llm | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| C17_005/llm | EQUIV | EQUIV | 9 | 0.01 | decided |
| C18/correct | REFUSED | EQUIV | 5 | 0.13 | decided |
| C18/fault1 | DIVERGE | DIVERGE | 5 | 0.2 | decided |
| C18/fault2 | DIVERGE | DIVERGE | 5 | 0.2 | decided |
| C18/fault3 | DIVERGE | DIVERGE | 4802 | 0.73 | decided |
| C18/fault4 | DIVERGE | DIVERGE | 3 | 3.49 | decided |
| C18_001/llm | EQUIV | EQUIV | 25 | 0.0 | decided |
| C18_004/llm | EQUIV | EQUIV | 37 | 0.01 | decided |
| C18_009/llm | EQUIV | EQUIV | 6 | 0.0 | decided |
| C19/correct | REFUSED | EQUIV | 2 | 0.01 | decided |
| C19/fault1 | DIVERGE | DIVERGE | 1 | 6.51 | decided |
| C19/fault2 | DIVERGE | DIVERGE | 216003 | 32.16 | decided |
| C19/fault3 | DIVERGE | DIVERGE | 1 | 6.69 | decided |
| C19_005/llm | EQUIV | EQUIV | 3 | 0.0 | decided |
| C20-O/correct | TIMEOUT | EQUIV | 10 | 0.04 | decided |
| C20-O/fault1 | TIMEOUT | DIVERGE | 9 | 5.48 | decided |
| C20-O/fault2 | DIVERGE | DIVERGE | 9 | 0.04 | decided |
| C20-O/fault3 | DIVERGE | DIVERGE | 7 | 0.02 | decided |
| C20-O/fault4 | DIVERGE | DIVERGE | 9 | 0.03 | decided |
| C20_003/llm | DIVERGE | DIVERGE | 4 | 0.01 | decided |
| C20_011/llm | REFUSED | REFUSED | — | 0.0 | invalid_service_mapping |
| C21_003/llm | DIVERGE | DIVERGE | 0 | 0.0 | decided |
| C22_003/llm | EQUIV | EQUIV | 4 | 0.0 | decided |
| C24_003/llm | DIVERGE | DIVERGE | 4 | 0.13 | decided |
| C26_003/llm | DIVERGE | DIVERGE | 5 | 0.0 | decided |
| E1-028/correct | REFUSED | EQUIV | 7 | 0.08 | decided |
| E1-028/fault1 | REFUSED | DIVERGE | 5 | 4.21 | decided |
| E1-028/fault2 | REFUSED | DIVERGE | 5 | 0.06 | decided |
| E1-028/fault3 | REFUSED | DIVERGE | 3 | 0.01 | decided |
| E1-028/fault4 | REFUSED | DIVERGE | 5 | 16.3 | decided |
| E1-034/correct | TIMEOUT | EQUIV | 3 | 0.04 | decided |
| E1-034/fault1 | TIMEOUT | DIVERGE | 5 | 36.02 | decided |
| E1-034/fault2 | TIMEOUT | DIVERGE | 3 | 19.52 | decided |
| E1-034/fault3 | TIMEOUT | DIVERGE | 2 | 19.41 | decided |
| E1-034/fault4 | TIMEOUT | DIVERGE | 3 | 19.36 | decided |
| E1-062/correct | EQUIV | EQUIV | 4 | 0.01 | decided |
| E1-062/fault1 | DIVERGE | DIVERGE | 4 | 0.01 | decided |
| E1-062/fault2 | DIVERGE | DIVERGE | 8 | 0.01 | decided |
| E1-062/fault3 | DIVERGE | DIVERGE | 4 | 0.01 | decided |
| E1-062/fault4 | DIVERGE | DIVERGE | 4 | 0.01 | decided |
| E1-072/correct | EQUIV | EQUIV | 4 | 0.01 | decided |
| E1-072/fault1 | DIVERGE | DIVERGE | 4 | 0.01 | decided |
| E1-072/fault2 | DIVERGE | DIVERGE | 4 | 0.01 | decided |
| E1-072/fault3 | DIVERGE | DIVERGE | 8 | 0.01 | decided |
| E1-072/fault4 | DIVERGE | DIVERGE | 2 | 34.89 | decided |
| E1-086/correct | EQUIV | EQUIV | 8 | 0.02 | decided |
| E1-086/fault1 | DIVERGE | DIVERGE | 2 | 0.01 | decided |
| E1-086/fault2 | DIVERGE | DIVERGE | 5 | 0.9 | decided |
| E1-086/fault3 | DIVERGE | DIVERGE | 6 | 0.86 | decided |
| E1-086/fault4 | DIVERGE | DIVERGE | 4 | 0.79 | decided |
| E1-092-A/correct | EQUIV | EQUIV | 4 | 0.0 | decided |
| E1-092-A/fault1 | DIVERGE | DIVERGE | 2 | 0.0 | decided |
| E1-092-A/fault2 | DIVERGE | DIVERGE | 4 | 0.0 | decided |
| E1-092-A/fault3 | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| E1-092-B/correct | EQUIV | EQUIV | 4 | 0.0 | decided |
| E1-092-B/fault1 | DIVERGE | DIVERGE | 4 | 0.0 | decided |
| E1-092-B/fault2 | DIVERGE | DIVERGE | 1 | 0.0 | decided |
| E1-092-B/fault3 | DIVERGE | DIVERGE | 4 | 0.0 | decided |
| E1-095/correct | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-095/fault1 | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-095/fault2 | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-095/fault3 | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-095/fault4 | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-099/correct | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-099/fault1 | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-099/fault2 | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-099/fault3 | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
| E1-099/fault4 | REFUSED | REFUSED | — | 0.0 | arithmetic_state_relations |
