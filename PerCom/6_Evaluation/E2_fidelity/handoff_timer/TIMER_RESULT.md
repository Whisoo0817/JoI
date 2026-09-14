# 타이머 작업 결과 — 2026-09-14

이 문서는 timer-v2 당시 기록이다. 후속 전체 142쌍 평가와 두 유형의 한계
분류는 [EXTENSION_RESULT.md](EXTENSION_RESULT.md), E2 담당 인계는
[EXTENSION_HANDOFF.md](EXTENSION_HANDOFF.md)를 따른다.

별도 worktree `/home/gnltnwjstk/joi-timer-regions`, 브랜치 `timer-regions-20260914`.
상속한 Explorer 변경의 기준 커밋은 `580053a`다. 원래 작업 폴더를 수정하지 않았다.
타이머 구현·테스트·증명 문서는 커밋 `552e4ba`로 분리했다.

## 결과

- 대상 19쌍 중 5쌍에서 판정을 완료했다.
- 기존에 판정된 104쌍의 판정 변화: 0쌍.
- 동결 정답기에서 차이가 발견된 쌍을 새 EQUIV로 판정한 경우: 0쌍.
- 지정된 기존 회귀 10개 모듈과 새 테스트 15개 통과. `results/checks-v2.jsonl` 참조.
- 정답기 구현은 읽거나 실행하지 않았다. 위 정답기 비교는 동결 실행 결과의 판정 필드와 비교한 것이며,
  새 반례를 독립 정답기에서 다시 실행한 결과는 아니다. DIVERGE는 Explorer의 구체 실행·재생으로 확인했다.

전체 검사는 E1 파일과 별도 표본 파일의 기존 104쌍, 미결정 대상 19쌍을 합친 123쌍이다.
쌍당 120초, 상태 400,000, 전이 2,000,000, worker 4개다. 동결 결과와 비교하기 위해
`E2_BINDING_DECISION` 기본값(false)을 사용했다. 해당 설정을 바꾼 독립 E2 평가는 별도다.

| 쌍 | 이전 판정 | 새 판정 | 새 상태 수 | 초 | 설명 |
|---|---|---|---:|---:|---|
| C01/fault2 | TIMEOUT | TIMEOUT | — | 120 | 타이머 적용 조건 통과; 전체 실행 한도 |
| C05/fault2 | REFUSED | DIVERGE | 2 | 0.54 | 구체 반례 재생 확인 |
| C05/fault3 | REFUSED | TIMEOUT | — | 120 | 타이머 적용 조건 통과; 전체 실행 한도 |
| C07/correct | TIMEOUT | TIMEOUT | — | 120 | 실제 Clock 읽기: 새 적용 범위 밖; 전체 실행 한도 |
| C07/fault1 | TIMEOUT | TIMEOUT | — | 120 | 실제 Clock 읽기: 새 적용 범위 밖; 전체 실행 한도 |
| C07/fault2 | TIMEOUT | TIMEOUT | — | 120 | 실제 Clock 읽기: 새 적용 범위 밖; 전체 실행 한도 |
| C07/fault3 | TIMEOUT | TIMEOUT | — | 120 | 실제 Clock 읽기: 새 적용 범위 밖; 전체 실행 한도 |
| C07/fault4 | TIMEOUT | TIMEOUT | — | 120 | 실제 Clock 읽기: 새 적용 범위 밖; 전체 실행 한도 |
| C15/correct | REFUSED | TIMEOUT | — | 120 | 실제 Clock 읽기: 새 적용 범위 밖; 전체 실행 한도 |
| C15/fault1 | REFUSED | TIMEOUT | — | 120 | 실제 Clock 읽기: 새 적용 범위 밖; 전체 실행 한도 |
| C18/correct | REFUSED | TIMEOUT | — | 120 | 실제 Clock 읽기: 새 적용 범위 밖; 전체 실행 한도 |
| C19/correct | REFUSED | REFUSED | 400000 | 96.24 | 실행기 형태가 새 적용 범위 밖; 상태 400,000개 한도 |
| C20-O/correct | TIMEOUT | EQUIV | 10 | 0.16 | 타이머 관계 그래프 폐쇄 |
| C20-O/fault1 | TIMEOUT | DIVERGE | 9 | 18.11 | 구체 반례 재생 확인 |
| E1-034/correct | TIMEOUT | EQUIV | 3 | 0.14 | 타이머 관계 그래프 폐쇄 |
| E1-034/fault1 | TIMEOUT | TIMEOUT | — | 120 | 타이머 적용 조건 통과; 전체 실행 한도 |
| E1-034/fault2 | TIMEOUT | TIMEOUT | — | 120 | 타이머 적용 조건 통과; 전체 실행 한도 |
| E1-034/fault3 | TIMEOUT | DIVERGE | 2 | 77.38 | 구체 반례 재생 확인 |
| E1-034/fault4 | TIMEOUT | TIMEOUT | — | 120 | 타이머 적용 조건 통과; 전체 실행 한도 |

TIMEOUT의 상태 수는 기존 실행기가 signal 중단 시 반환하지 않아 ‘—’로 표시한다.
REFUSED와 TIMEOUT의 상호 변화는 모두 미결정이며, 이전 REFUSED가 새 TIMEOUT으로
바뀐 사례를 성능 개선으로 세지 않는다. 실제 달력 읽기와 timestamp/비동기 시간은
이번 인증 범위 밖이다. 타이머 적용 조건을 통과해도 추상 불일치를 구체 반례로
만들지 못하거나 자원 한도에 걸리면 기존 탐색으로 돌아가 미결정으로 남을 수 있다.
C15/fault1의 동결 정답기 무차이 결과를 EQUIV 정답으로 단정하지 않는다.

## 구현과 검증 범위

`timer_analysis.py`가 비교 전용 정수 증가/상수 리셋과 사용되지 않는 Clock READ를
검사한다. `timer_domain.py`는 정수 차이 제약(DBM)과 정확한 유리수 식 계산을,
`timer_product.py`는 모든 입력 분기와 확대된 상태의 재검사를 담당한다.
시간이 다른 구체 상태를 같은 것으로 단정하지 않고, 그 상태들을 포함하는 집합
전체에서 양쪽 ACTION이 같은지 귀납적으로 검사한다.

새 경로는 기존 지원·입력 검사를 우회하지 않는다. 실제 시계 읽기, timestamp snapshot,
격자 밖 마감, JoI 내부 blocking/loop, 이름 있는 IR 카운터, GV/IR 질의/매개변수 질의, 카운터의
다른 변수/ACTION 유출은 제외한다. 기존 정확한 탐색 경로는 유지한다.
추상 불일치는 후보 입력의 유지 구간을 늘려 원래 실행기에서 매 격자 실행하고,
재생 확인이 된 경우에만 DIVERGE로 반환한다. 이 반례 탐색은 완전하지 않다.

`explorer/docs/proof/TIMER_ZONES.md`에 적용 조건, B0–B3, L4의 전방 포괄 관계,
입력과 만료의 동률, 타이머 차이, 확대 후 재검사를 기록했다. 기존 proof 문서
3개와 `SUPPORTED_FRAGMENT.md`도 연결했다. 논문 원고는 수정하지 않았다.

새 테스트는 긴 시간 창, 마감 직전/동시/직후, 두 타이머, 리셋 후 재시작,
짧은 입력 이력 전수, 관찰값 유출과 살아 있는 시계/예약 이름/미지 wrapper 거절,
한도 초과, 일정한 입력의 구체 반례를 포함한다.

## 재현과 인계

저장소 루트에서 `~/temp/bin/python`을 사용한다.

```sh
~/temp/bin/python PerCom/6_Evaluation/E2_fidelity/handoff_timer/probe_c20.py original --no-reference --budget 120
~/temp/bin/python -m explorer.tests.test_timer_zones
~/temp/bin/python PerCom/6_Evaluation/E2_fidelity/handoff_timer/evaluate_timer.py --out /tmp/timer-new-run.jsonl --workers 4
```

결과: `results/timer-v2.jsonl.gz`, 소스 해시와 실행 설정: `results/timer-v2.meta.json`.
동결 `runs/`, `pairs/`, `histories/`와 정답기 구현은 변경하지 않았다.
보호된 네 파일은 시작 시 복사한 버전을 그대로 유지했다. 수정 사항은 기준 커밋
`580053a` 이후의 diff로 분리되어 있어, 상속한 바인딩 작업을 다시 적용할 필요가 없다.

`timer-v1`은 첫 E1 파일 87쌍만 검사한 개발 기록이므로 기존 104쌍 회귀의 근거로
사용하지 않는다. 최종 `timer-v2`는 별도 표본 파일까지 포함하는지 assert로 검사한다.
원시 JSONL은 로컬에 남겼고 저장소에는 동일 내용의 gzip 사본을 기록한다.
독립 정답기의 새 반례 재평가는 이 결과를 E2 담당에게 넘겨 별도로 진행할 수 있다.
