# SUPPORTED_FRAGMENT — 검증기가 EQUIV를 주장할 수 있는 프로그램 조각

2026-09-14 추가: `timer-zones-v2`는 반복 JoI period=입력 격자이고 모든 IR 마감이
그 격자에 놓이는 경우, 비교 전용 정수 증가 카운터와 내부 타이머의 차이
관계를 확대·재검사한다. 전역 미사용 plain Clock READ는 상태 관계에서
제외한다. 격자 위 blocking, 유한 회차 카운터, Hour와 비교 전용 timestamp
snapshot은 아래 2026-09-14 확장 조건에서 받는다. JoI loop, 무한 IR 카운터,
GV, IR 질의/매개변수 질의, 타이머 값의 ACTION 유출은 새 경로에서 거절한다.
미결정이면 기존 경로를 유지한다. 적용 조건과 증명은
[TIMER_ZONES.md](../proof/TIMER_ZONES.md)를 따른다.

작성 2026-09-02 (P1). 이 문서는 **코드가 실제로 검사하는 것**과 1:1로
맞춘 계약이다. 조각 밖 프로그램은 탐색 전에 `Unsupported`로 거절되고
게이트에서 REFUSED가 된다 — 허위 EQUIV(놓친 차이)는 금지, 허위
REFUSED(과한 거절)는 허용이 기본 방향(fail-closed)이다.

**후속 승인 — 산술 SMT 경로:** [smt-linear-trace-v1](../proof/SMT_VERIFICATION.md)은
`joint-guard`/`derived-guard`/`arith-arg`만 갖는 catalog 숫자 one-shot에 별도 전칭
기호 검증을 적용한다. 기존 축 분할 엔진의 D7 거절은 제거하지 않는다. 자동 입력·
유한 숫자 catalog bounds·acyclic 실행 등 새 경로의 모든 사전조건을 충족해야
한다. `+/-/상수 곱/상수 나눗셈`, 산술 조건·숫자/문자열 ACTION을 다루며, float
형식과 None 규칙을 보존한다. 제한·caps·UNKNOWN 의미는 연결 문서가 기준이다.
아래 D7 표는 기존 concrete/value-flow 경로의 거절 이유이며 **이 새 경로까지
모든 산술이 무조건 REFUSED라는 뜻은 아니다**.

**H 없는 시간 탐색 추가 (2026-09-08):** [silent-time-v1](../proof/UNBOUNDED_TIME.md)은 알려진
실행기/래퍼의 양쪽 비관찰 대기만 생략하며 최신 입력과 정확한 만료를 보존한다.
타이머 상대값·입력 위상·전체 저장소의 폐쇄를 사용한다. 고정 입력 가속은 반례만
발견하고 반드시 재생한다. H=None auto는 자격을 갖춘 INTEGER 관계 경로도 선택한다.
SMT의 H 요구는 제거했으나 무제한 긍정 인증에는 모든 기호 경로의 종료가 필요하다.
미지원/미완료를 인증하지 않으며, 일반 비동기 타이머 유한 추상화는 추가하지 않았다.

**추가 인증 경로 (2026-09-07):** [symbolic-value-flow-v1](../proof/SYMBOLIC_VALUE_FLOW.md)은
자동 exact 입력 구성이 불가능하거나 입력 조합 상한을 넘는 순차 one-shot의
read/대입/문자열 변환/call/고정
delay를 보편 기호로 검사한다. 출처·조회 인자·입력 epoch와 ACTION 순서를 보존한다.
정규형 일치만 동등 인증, 불일치는 구체 재생된 반례만 DIVERGE, 미결은 UNKNOWN이다.
분기/주기/GV/산술 지원은 확장하지 않으며 기존 경로는 유지한다. 비BOOL None을
필수 ACTION 인자에 직접 넘기는 경우도 여전히 거절한다.

강제 지점: `features.analyze_stmts`/`analyze_ir`(무늬 검사, product·
explore 사전 점검에서 호출) + `explore.finiteness_check`(유한성) +
`derive_axes`의 `param_reads`(해석 불가 질의 인자). 분류 보고는
`predicates.FRAGMENT`(CAL·ENUM·THRESH·TIMER·LATCH·COUNT 등)가 하지만,
새 product/gate 경로는 위 검사에 더해 `input_coverage`의 출처·입력 사용
인증, 필요한 외부/초기 도메인 검사를 강제한다.

**실제 서비스 연결 (2026-09-07):** 기본 prepare_pair/gate는
[SERVICE_MODEL.md](SERVICE_MODEL.md)의 catalog 검사를 강제한다. 알 수 없는
서비스/member, 이름 충돌, capability 불일치, 인자 누락/타입/범위 오류를
거절한다. named args는 binding 접지 후 정식 순서로 재정렬한다. 검토된 읽기
함수만 반환 대입으로 허용하며 effectful/unreviewed 반환 대입과 결과를 버리는
읽기 문장 호출은 REFUSED한다. 자동 입력은 catalog 타입·범위에서 재분할하며
관찰값은 전체 유한 도메인을 요구한다. 동적 ACTION 인자 검사 실패는 실행 중
REFUSED할 수 있다. synthetic model은 service_catalog=False로 명시하며
실제 catalog 적합성 결과와 구별한다. 기존 D7 정책은 바꾸지 않았다.

**BOOL 계약 후속 확정:** catalog BOOL/BOOLEAN 입력은 true/false만 지원한다.
기본 도메인은 두 값 전체이며 명시 입력 및 직접 재생에서 누락·None·0/1은
거절한다. 비BOOL의 결측 정책은 유지한다. bool 입력 모델 ID는
`strict-two-valued-v1`; 이전 nullable BOOL 평가 수치는 역사적 결과다.

**생성·평가 binding 범위 확정 (2026-09-11):** 하나의 `Service.Method`에는
서로 다른 selector를 최대 하나만 허용한다. `all(#...)` 하나가 여러 concrete
device에 fan-out하는 것은 지원한다. 같은 service에 서로 다른 selector가 필요하면
mapping 단계에서 fail-closed로 거절하며 E1에서는 지원 경계, E3에서는 generation/
preparation refusal로 분리한다. 이 제한은 임의 후보 JoI를 읽는 gate parser의 문법
제한이 아니라, 논문에서 다루는 confirmed binding과 lowering 입력의 범위다.

**파서·실행기 검토 갱신 (2026-09-07):**
[FRONTEND_CORRECTNESS.md](../proof/FRONTEND_CORRECTNESS.md)에 모델 내부의 의미 보존·결정론성
논증과 서비스 명세에 남은 전제를 구분했다. any 비교는 전체 매칭 장치를
OR로 검사하고, query 입력도 기기 ID와 인자 타입을 보존한다. unused query를
ACTION으로 바꾸지 않는다. 중첩 cycle은 진입마다 내부 카운터를 초기화한다.
gate는 missing/offline/floating binding과 사용 중인 자리 수 불일치를 거절한다.
숫자 slot suffix 순서를 사용하며 완전히 쓰이지 않는 여분 서비스는 메모만 남긴다.
문자열 escape, 표현식 안 GV 쓰기, 다중 장치 query 결과, edge+sustain 조합,
foreach 내부 break/blocking/nesting/iterator 쓰기는 미인증 의미로 거절한다.
이 변경으로 IR/binding 스키마나 기존 D7 결정을 바꾸지 않았다.


**2026-09-07 갱신:** 현재 `gate_pair`는 `timed.timed_product`를 사용한다.
[VERIFICATION_CONTRACT.md](VERIFICATION_CONTRACT.md)가 새 시간·입력·상태 계약이다.
[SEARCH_CORRECTNESS.md](../proof/SEARCH_CORRECTNESS.md)는 탐색 정리의 전제와 남은
입력 모델·런타임 적합성 의무를 구분한다. [INPUT_COVERAGE.md](../proof/INPUT_COVERAGE.md)에
인증된 AST에서 입력 대표값의 포괄성과 ACTION 보존을 논증했다.
기존 `product_runners`/`exact_tick_product`는 명시적 tick 모델의 개발·과거 평가 경로로
남겨 두며, 새 시간 계약의 성능·정확도 근거로 혼용하지 않는다.

## 판정 계약

`gate.fold_verdict`: 기존 배포 3-way에 bounded 결과를 별도로 표시한다.

| 내부 | 외부 | 뜻 |
|---|---|---|
| EQUIV (닫힌 그래프에서만) | EQUIV | 탐색한 전 상태에서 행동 동일 |
| EQUIV + 유한 horizon | EQUIV-BOUNDED | 선언한 밀리초 범위의 모든 입력 이력; 무제한 배포 승인과 구분 |
| DIVERGE + 재생 확인 | DIVERGE | 구체 입력 시퀀스로 재현된 차이 |
| DIVERGE + 재생 미확인 | REFUSED | 허위 반례 의심 — 배포 거절 |
| UNKNOWN (cap·미완) | REFUSED | 탐색 미완 — 배포 거절 |

관찰값은 시각별 호출 순서와 각 호출의 ACTION이다. 한 호출이 독립 장치로
펼쳐진 부분만 장치 나열 순서를 무시한다. 명시적 순서, 동일 장치 순서,
중복 횟수, 대상, 인자 값·타입은 보존한다. 종료 자체는 ACTION이 아니다.

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
  또는 `자기 ± 상수`뿐이고 **비교 전용**일 때), 타임스탬프 레지스터.
  기본 timed BFS는 구체 값을 보존한다. 위 조건에서는 timer-zones-v2의
  과근사 관계 증명을 먼저 시도한다. 단순 counter 포화는 구 경로의 방식이다.
- **타이머 여러 개**: 기본 timed BFS는 양쪽 timer의 정확한 시각을 보존한다.
  timer-zones-v2는 위 적용 범위 안에서 여러 좌표의 쌍별 차이를 함께 보존한다.
  구 경로는 쌍별 마감 차이 구간(deadline region, §9.18 ②)을 사용한다.
  상태 폭발 시 cap → UNKNOWN → REFUSED.
- **질의 읽기**: 인자가 전부 리터럴인 경우. 이전 루프 범위 휴리스틱은
  전체 인자 포괄성이 인증되지 않아 현재 product/gate에서 추가 거절한다.
  `forecast(1)`과 `forecast(1.0)`의 인자 타입 및 입력 키를 보존한다.
- **관찰 인자(액션·GV 쓰기·질의 인자)**: 리터럴, 맨 읽기/변수(항등
  전달), 문자열 이어붙이기·템플릿. **관찰값으로 흐르는 모든 외부 입력은
  명시된 유한 도메인이 필요하다.** 임계값 대표값만 있으면 REFUSED.
  주어진 도메인의 원값을 모두 열거하며 인자를 임의 반올림하지 않는다.
- **주기/시작**: 회차 종료 후 period 대기, delay는 정확한 만료에 재개.
  외부 입력은 기본 100ms 간격에 변화하고 그 사이에는 유지한다.
  원샷(OneShot/Pause 경로), cron 쌍은
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

아래 zone·교차 순서 갭은 구 `product_runners` 정규화 경로에 해당한다.
새 timed 경로는 구체 상태/시각을 보존하고, 사용자 clock 읽기가 없을 때만
실행기 내부 timer의 정확한 상대 시각을 사용한다. clock 사용 프로그램의
무제한 탐색은 시간이 계속 구별되어 cap에 걸릴 수 있다. 전체 지원 단편의
입력 추론은 `INPUT_COVERAGE.md`의 모델 계열과 인증된 출처 사용 범위에서
논증했다. 그 모델이 실제 센서 도메인과 일치하는지와 실제 런타임 적합성은 남아 있다.

- **product 교차-쌍 타이머**: IR 쪽 타이머 × JoI 쪽 타이머의 마감
  경쟁은 상태 키 밖. 같은 입력 경로에서 대응 캡처가 일치하므로 실질
  영향은 없다고 보나, 형식적으로는 갭.
- **③ 미지원 무늬의 실존 2행**: C11_001(결합 산술), C14_002(인자
  산술) — REFUSED 유지, 논문 제한사항. 지원하려면 input-pure affine
  한정 predicate abstraction + SMT(all-SAT 대표값)가 표준 경로.
- 달력×타이머 교차 순서(시각 경계 vs 타이머 마감의 선후)는 상태 키
  밖 — 기존 설계 범위(P0 이전부터 동일).

## 검증 명령

```sh
python3 -m explorer.tests.test_contract       # 새 계약 33건
python3 -m explorer.tests.test_input_coverage # 입력 포괄성 16건
python3 -m explorer.tests.test_service_model  # 실제 서비스 연결 21건
python3 -m explorer.tests.test_soundness      # 기존 회귀 38건
python3 -m explorer.tests.test_exact_tick     # tick 기준 회귀 9건
python3 -m explorer.analysis.features                 # 거절 정책 자가 점검
python3 -m explorer.runtime.ir_step                  # 기대 trace 6 / 비교 8건
```

과거 §9.18의 178행 D79/E97/R2는 변경 전 결과이며 새 gate 결과로 재사용하지 않는다.

## 2026-09-08: 명시적 관계 카운터 경로

기존 concrete/symbolic/SMT의 지원 검사는 유지한다. 별도
`verification_mode='relational', horizon_ms=None` 경로는 단일 최상위 이름 카운터 cycle와
JoI 첫 INTEGER :=를 대응시키고, 같은 양의 period에서 정수 +/−/복사/문자열 출력 및
if/delay/wait 관계를 검사한다. 모든 관계 전이와 그래프 폐쇄가 확인되면 EQUIV-FIXPOINT.
원값 관찰 카운터의 증가/modulo 의미는 컴파일러가 보존한다.
cycle until, 중첩 cycle, query/read 대입, GV, clock, modulo, 관계 float, 동적 시간,
복잡한 live snapshot은 이 경로의 지원 밖이다. 구조 실패는 불일치 증거가 아니다.
STRING 인자 계약과 내부 갱신/ACTION 순서도 확인하며 cap은 UNKNOWN이다.
[정확한 구현 범위와 보장](../proof/RELATIONAL_FIXPOINT.md). 기존388의208 bounded는 승격하지 않는다.

## 후속 확장: catalog 범위로 증명되는 상수 clock 비교 (2026-09-08)

`catalog-range-v1`은 명세의 Hour/Minute 정수 범위 및 IR HHMM 파생 범위로 항상 참/거짓인
직접 비교를 판별한다. 모든 clock 읽기가 그런 비교 내부에 있을 때 기존 clock-free 시간
관계로 H 없는 폐쇄가 가능하다. 일반 clock 루프/시간 snapshot/별도 STRING Time 속성의
해석을 확대하지 않는다. [정확한 전제와 보수적 fallback](../proof/CATALOG_RANGE_ANALYSIS.md).
C15_005/C18_003은 해결됐고 새 전체 결과의 미완료는0이다. 임의 프로그램의 완료 보장은 아니다.

## 2026-09-14: 격자 시계·snapshot·나머지 카운터 확장

`timer-zones-v2`는 격자 위 wait/delay와 반복/일회 실행, 직접 Hour 읽기,
현재 timestamp를 저장한 뒤 경과 시간을 상수와 비교하는 모양을 추가로
검사한다. 시계 경계와 입력 격자가 정렬돼야 한다. Hour의 임의 공통 변화와
timestamp의 공통 초 증가를 과근사하므로 EQUIV는 모든 포함 상태에서
폐쇄를 확인한 경우뿐이다. 실제 달력 이력에서 재생된 차이만 DIVERGE다.
JoI에서 양의 상수에 대한 나머지로만 관찰되는 정수 카운터는 최소공배수
몫으로 정규화한다. 원값 유출·동적 snapshot 가공·비동기 시간은 확대하지 않는다.
[전제·전방 포괄·반례 재생 논증](../proof/TIMER_ZONES.md).

사용자 언어 결정에 따라 ACTION 위치의 `any(selector).Method()`는
파싱 단계에서 거절한다. any 읽기의 기존 의미는 유지한다. 선언되지 않은
service capability를 쓰는 후보는 기존 모델 검사가 거절한다. 둘 모두
행동 동등성을 못 증명한 사례와 구별해서 집계한다.

E2의 새 개발 재평가에서는 계산된 수치 상태의 관계 추론과 유한 곱 상태의 자원 폭증을
서로 다른 한계로 기록한다. 이는 평가된 쌍의 원인 분류이며 모든 JoI
프로그램에 대한 완전 지원 주장이 아니다. 이전 동결 실험 수치를 대체할
때에는 새 반례의 독립 정답기 재검사를 별도로 마쳐야 한다.
