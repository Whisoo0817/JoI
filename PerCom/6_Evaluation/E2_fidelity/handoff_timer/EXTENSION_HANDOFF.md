# E2 담당에게 넘길 변경 — 2026-09-14

> 후속 개선: E1-095 고정 집계 5쌍은 자동 unroll로 모두 판정됐다. 기존
> `extension-v4`는 그대로 보존하며 새 결과와 갱신된 130/140 집계는
> `FIXED_AGGREGATION_RESULT.md`를 사용한다. 현재 남은 한계는 E1-099 5쌍과
> C07 5쌍이다.

브랜치 `timer-regions-20260914`, worktree `/home/gnltnwjstk/joi-timer-regions`.
기존 인계 기준 `580053a`에 상속된 수정과 후속 Explorer 변경을 분리했다.
이번 구현·증명·회귀의 커밋은 `003d863`이다.
보호된 ground.py, observation.py, gate.py, run_e2.py는 수정하지 않았다.

## 결과와 모집단

새 전체 Explorer 실행: `results/extension-v4.jsonl.gz`와 `.meta.json`.
142쌍 전부 실행했고 43 EQUIV, 82 DIVERGE, 5 TIMEOUT, 12 REFUSED다.
기존 판정 104쌍은 그대로이며 새 판정 완료는 21쌍이다.
기존 timer v2 대비로는 16쌍을 추가 해결했다.

사용자 결정에 따라 행동 평가 모집단은 `e2_population.json`의 140쌍이다.
ACTION 위치 any 1쌍은 구문 부적합, C20_011/llm 1쌍은 LLM service mapping
오류로 입력 검증에 별도 집계한다. 동결 142쌍 원자료를 삭제하거나 수정하지
않는다. 기존 142쌍 실험을 소급 변경하지 않고 모집단 수정 근거를 같이 싣는다.

유효 140쌍 중 125쌍 판정 완료(89.3%). 남은 15쌍의 설명은 두 유형으로 충분하다.

| 한계 유형 | 쌍 수 | 코호트 |
|---|---:|---|
| 계산된 수치 상태의 관계 추론 | 10 | E1-095, E1-099의 correct/fault1–4 |
| 유한 곱 상태의 폭증 | 5 | C07의 correct/fault1–4 |

첫 유형은 누적·평균값 또는 증가 카운터가 출력/기한을 결정해 추가 수치 관계
추론이 필요한 경우다. E1-095의 합계는 매일 초기화되므로 모든 사례가
무한히 증가한다고 설명하지 않는다. 두 번째는 brightness 값 1,104개 × 접촉 입력 ×
Hour × 중첩 타이머/회차가 결합된 경우로, 현재 120초 예산 내 미완료다.
이번에 쉬운 시간·나머지 카운터·timestamp 모양은 해결했고 이 두 확장은 보류했다.
“이 평가에서 미결정 사례가 두 유형에 집중된다”로 한정한다.

## 독립 확인이 남은 부분

이 세션은 reference/를 읽거나 실행하지 않았다. 새 결과의 DIVERGE는
Explorer의 원래 실행기와 실제 clock으로 재생 확인했다. 독립 정답기 판정
필드와 비교했을 때 REF-DIVERGE → EQUIV는 0이지만, 이것이 새 전체 결과의
독립 검증 완료를 뜻하지는 않는다.

새 DIVERGE witness를 독립 정답기에 넣어 확인해야 한다. 특히 아래 두 쌍은
동결 REF-EQUIV-CHECKED와 새 DIVERGE가 다르다. 이력 기반 무차이는 동등성
증명이 아니므로 곧바로 Explorer 오판 또는 정답기 버그로 결론내리지 않는다.

- C15/fault1: 실제 6시 경계에서 `< 6`과 `<= 6`의 차이.
- C14_003/llm: 버튼 이력에 따른 IR 회차와 JoI 주기 회차/샘플링이 다름.

전체 원시 결과에 device-key 입력·dwell·t₀가 있어 run_e2의 기존 witness
변환 경로로 넘길 수 있다. 최종 E2 판정 일치율은 이 재검사를 마친 뒤 확정한다.
E2_BINDING_DECISION=false를 사용했으므로 바인딩 결정이 바뀐 실행과 혼합하지 않는다.

## 구현과 회귀

- ACTION any의 parser 거절; any 읽기는 유지.
- 조이 나머지 카운터의 최소공배수 몫; 원값 유출은 거절.
- Hour 공통 입력 및 timestamp age 관계의 포괄 상태 집합.
- 긴 입력 유지의 경계 반례 생성, 입력 변경 시작 시점을 보존하는 압축.

지정 회귀 10모듈과 timer zones 15테스트, 추가 extension 10테스트 통과.
로그는 `results/checks-v4.jsonl`, `results/checks-extensions-v4.jsonl`.
상세 논증은 `explorer/docs/proof/TIMER_ZONES.md`, 집계와 142쌍 표는
`EXTENSION_RESULT.md`, 연구 주장 범위 감사는 `results-audit/`에 있다.

v3 전체 실행 후, timestamp 별칭이 blocking continuation을 넘는 모양을
보수적으로 거절하도록 적용 조건을 좁혔다. v4는 그 최종 소스로 전체
142쌍을 다시 실행한 결과다. v3 및 모든 개발 프로브 기록은 보존했다.
