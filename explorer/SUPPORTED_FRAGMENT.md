# SUPPORTED_FRAGMENT — 검증기가 EQUIV를 주장할 수 있는 프로그램 조각

작성 2026-09-02 (P1). 이 문서는 **코드가 실제로 검사하는 것**과 1:1로
맞춘 계약이다. 조각 밖 프로그램은 탐색 전에 `Unsupported`로 거절되고
게이트에서 REFUSED가 된다 — 허위 EQUIV(놓친 차이)는 금지, 허위
REFUSED(과한 거절)는 허용이 기본 방향(fail-closed)이다.

강제 지점: `features.analyze_stmts`/`analyze_ir`(무늬 검사, product·
explore 사전 점검에서 호출) + `explore.finiteness_check`(유한성) +
`derive_axes`의 `param_reads`(해석 불가 질의 인자). 분류 보고는
`predicates.FRAGMENT`(CAL·ENUM·THRESH·TIMER·LATCH·COUNT 등)가 하지만,
**강제의 원천은 위 세 검사**다.

## 판정 계약

내부 4-way → 외부 3-way (`gate.fold_verdict`, §9.16):

| 내부 | 외부 | 뜻 |
|---|---|---|
| EQUIV (닫힌 그래프에서만) | EQUIV | 탐색한 전 상태에서 행동 동일 |
| DIVERGE + 재생 확인 | DIVERGE | 구체 입력 시퀀스로 재현된 차이 |
| DIVERGE + 재생 미확인 | REFUSED | 허위 반례 의심 — 배포 거절 |
| UNKNOWN (cap·미완) | REFUSED | 탐색 미완 — 배포 거절 |

관찰값 = tick별 **액션 시퀀스(순서·중복·인자 포함)**. tick 안의 순서도
행동이다(§9.16 ①).

## 지원하는 것

- **조건(guard)**: `and`/`or`/`not` 트리 + 아래 원자들
  - 맨 읽기(기기·GV·질의) vs 상수(리터럴, param, 상수-wire의 값 후보들)
  - 산술 안 거친 변수 vs 상수 (counter 비교 포함)
  - bool 값끼리의 비교 (`desired != armed`) — bool 도메인은 전량 열거
  - 타이머: `now − reg (op) 상수`, 지속시간 변수, `reg == 0` 센티널
  - 달력: `clock.hour/minute/weekday/isholiday` + `clock.time`(HHMM
    합성 — 자유 입력이 아니라 분 경계 `tod_ops`로 모델, §9.18 ①)
  - 맨 truthy 읽기/bool 변수
- **상태 변수**: bool 래치, 리터럴 유한 enum, counter(갱신이 `= 상수`
  또는 `자기 ± 상수`뿐이고 **비교 전용**일 때 — 최대 비교 상수에서 포화),
  타임스탬프 레지스터(zone 정규화)
- **타이머 여러 개**: 쌍별 마감 차이 구간(deadline region, §9.18 ②) —
  임계값이 달라도 교차 순서가 상태 키에 보존된다. 개수 제한 없음
  (상태 폭발은 STATE_CAP → UNKNOWN → REFUSED가 받침)
- **질의 읽기**: 인자가 전부 리터럴, 또는 정적 범위가 잡히는 루프
  카운터 하나 (`forecast(h)`, h ∈ 1..6)
- **관찰 인자(액션·GV 쓰기·질의 인자)**: 리터럴, 맨 읽기/변수(항등
  전달), 문자열 이어붙이기·템플릿. 콤보가 원값을 곱집합으로 돌리므로
  항등 전달은 정확하다
- **주기/시작**: 주기형 tick 실행, 원샷(OneShot/Pause 경로), cron 쌍은
  같은 앵커임을 확인한 뒤 소거하고 창 안 행동만 비교 (불일치 → REFUSED)

## 거절하는 것 (features.py의 무늬)

| kind | 무엇 | 왜 위험한가 |
|---|---|---|
| `joint-guard` | 한 비교식에 입력 ≥2 혼합 (`x+y>10`, `x>y`, `abs(t2−t1)≥1`) | 축은 키별 1차원 분할 — 대표값 조합이 결합 경계를 놓칠 수 있음 |
| `derived-guard` | 항등 아닌 변형을 거친 비교 (`x/2>10`, `avg>임계wire`) | k=1이어도 실경계(20)가 술어 상수(10)와 달라 대표값이 못 덮음 |
| `opaque-guard` | 지원 밖 guard 모양(함수 호출 조건, 미모델 clock 필드 `clock.date` 등) | 축이 아예 없어 진리 전환을 탐색이 못 봄 |
| `arith-arg` | 산술 거친 값의 관찰 지점 유출 (`speak(t*2)`, `max(...)` 인자) | 두 프로그램이 대표값에서만 우연히 일치할 수 있음 |
| `observable-counter` | 포화 counter 값의 관찰 지점 유출 (`speak(n)`) | 포화는 비교 전용일 때만 정당 — cap 위 5회/6회가 접히는데 출력은 다름 |

그 외 강제: `parameterized reads`(해석 불가 질의 인자),
`unbounded carried vars`(유한 모양이 안 잡히는 상태 변수),
`ForEach needs grounding`(접지 전 ForEach), cron 앵커 불일치.

## 알려진 잔여 갭 (문서화된 한계, §9.18)

- **product 교차-쌍 타이머**: IR 쪽 타이머 × JoI 쪽 타이머의 마감
  경쟁은 상태 키 밖. 같은 입력 경로에서 대응 캡처가 일치하므로 실질
  영향은 없다고 보나, 형식적으로는 갭.
- **③ 미지원 무늬의 실존 2행**: C11_001(결합 산술), C14_002(인자
  산술) — REFUSED 유지, 논문 제한사항. 지원하려면 input-pure affine
  한정 predicate abstraction + SMT(all-SAT 대표값)가 표준 경로.
- 달력×타이머 교차 순서(시각 경계 vs 타이머 마감의 선후)는 상태 키
  밖 — 기존 설계 범위(P0 이전부터 동일).

## 검증 명령

```
python3 -m explorer.features               # 탐지기 자가 점검
python3 -m explorer.tests.test_soundness   # 회귀 33건
python3 -m explorer.product                # 자기동치 6/6 + 고장 4/4
python3 -m explorer.gate                   # 정답쌍 178: D79/E97/R2
python3 -m explorer.prevalence             # 무늬 빈도(걸린 행 2, 오탐 0)
```
