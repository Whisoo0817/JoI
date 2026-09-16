# E2 고정 집계 자동 unroll 추가 결과 — 2026-09-14

이 결과는 기존 timer `extension-v4` 전체 실행을 덮어쓰거나 섞지 않은 별도
개선판이다. 최종 전체 실행은 `results/fixed-aggregation-v1-full.jsonl.gz`,
메타데이터와 분류는 같은 이름의 `.meta.json`, `-classified.json`이다.
`fixed-aggregation-v1.jsonl`은 E1-095 다섯 쌍만 먼저 확인한 부분 실행이다.
독립 정답기 코드는 읽거나 실행하지 않았고 기존 결과 파일에 기록된 동결
판정 필드만 대조했다.

전체 142쌍 결과는 EQUIV 44, DIVERGE 86, REFUSED 7, TIMEOUT 5다. 입력 검증
제외 2쌍을 분리한 유효 140쌍에서는 **130쌍(92.9%)**을 판정했다. 기존에
판정했던 104쌍의 변화는 0이며, 동결 `REF-DIVERGE`에 새 EQUIV를 낸 경우도 0이다.

| pair | 이전 | 새 판정 | 상태 | 시간 |
|---|---|---|---:|---:|
| E1-095/correct | REFUSED | EQUIV-FIXPOINT | 7 | 0.01 s |
| E1-095/fault1 | REFUSED | DIVERGE | 7 | 2.17 s |
| E1-095/fault2 | REFUSED | DIVERGE | 7 | 2.18 s |
| E1-095/fault3 | REFUSED | DIVERGE | 7 | 2.16 s |
| E1-095/fault4 | REFUSED | DIVERGE | 7 | 2.18 s |

네 DIVERGE는 모두 원래 IR/JoI 실행기의 구체 재생으로 확인됐다. 동결 판정과
비교하면 correct는 `REF-EQUIV-CHECKED`, fault1--4는 모두 `REF-DIVERGE`와
일치한다.

## 자동 unroll

컴파일러 전처리 `fixed-aggregation-unroll-v1`은 고정된 연속 Hour 구간,
시간당 한 번의 표본, 고정 증가 count, 보고 후 완전 reset을 구조적으로
확인한다. E1-095에서는 10--14시의 다섯 센서 읽기를 서로 다른 기호
snapshot으로 펼친 뒤 15시 ACTION의 산술식 트리를 Timeline과 비교한다.
따라서 연속적인 DOUBLE 입력을 대표값으로 샘플링하여 EQUIV를 주장하지 않는다.

동적 반복 한도, 입력 의존 count, timestamp 산술, 부작용이 있는 else,
불완전 reset 등은 적용하지 않고 기존 경로로 넘긴다. 전체 적용 조건과 귀납
논증은 `explorer/docs/proof/FIXED_AGGREGATION_UNROLL.md`에 있다.

## 갱신된 한계 분류

유효 모집단 140쌍 기준 판정 완료는 125에서 **130쌍(92.9%)**으로 증가했다.
이는 부분 결과의 산술 합산이 아니라 현재 소스로 142쌍을 다시 실행한
`fixed-aggregation-v1-full`의 단일-run 집계다. 미결정 10쌍은 다음 두 유형이다.

| 한계 유형 | 쌍 수 | 코호트 |
|---|---:|---|
| 동적 산술 시한 관계 | 5 | E1-099 correct/fault1--4 |
| 유한 상태곱 폭발 | 5 | C07 correct/fault1--4 |

논문 설명은 “고정 개수 집계는 자동 unroll로 처리하며, 남은 미결정은 동작
횟수에 따라 변하는 시한 관계와 깊게 중첩된 반복·타이머의 상태곱 폭발 두
유형”으로 정리할 수 있다. C07과 E1-099는 이번 구현 범위에서 한계로
유지한다. 새 전체판에서도 E1-099는 REFUSED 5쌍, C07은 TIMEOUT 5쌍이다.

## 재현

```sh
~/temp/bin/python PerCom/08_Evaluation/E2_fidelity/handoff_timer/evaluate_timer.py \
  --only E1-095/correct E1-095/fault1 E1-095/fault2 E1-095/fault3 E1-095/fault4 \
  --out PerCom/08_Evaluation/E2_fidelity/handoff_timer/results/fixed-aggregation-v1.jsonl \
  --workers 4
~/temp/bin/python -m explorer.tests.test_fixed_aggregation
~/temp/bin/python PerCom/08_Evaluation/E2_fidelity/handoff_timer/evaluate_timer.py \
  --all-pairs \
  --out PerCom/08_Evaluation/E2_fidelity/handoff_timer/results/fixed-aggregation-v1-full.jsonl \
  --workers 4
~/temp/bin/python PerCom/08_Evaluation/E2_fidelity/handoff_timer/report_fixed_aggregation.py
```
