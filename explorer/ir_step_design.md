# W1 설계 — IR 한-걸음 실행기 (ir_step.py)

> 목표: 확인받은 Timeline IR을 "나란히 비교"(product.py)의 한쪽으로 넣어,
> **IR ↔ 생성 코드**를 지도 전체에서 비교할 수 있게 한다. 이게 되어야
> "확인받은 IR이 기준"이라는 논문의 정체성이 새 탐색기에서 성립한다.
> (2026-08-13 설계.)

## 지금 구조의 사실

`product_explore(src_a, src_b, period_ms)`는 양쪽 모두 JoI 코드를 전제한다
— parse → classify_vars(변수 성격) → derive_axes(입력 칸 나누기) →
finiteness_check(다룰 수 있는 형태인지) → step(한-걸음 실행) →
normalize(상태 키)를 직접 호출. 상태 키 = (A쪽 키, B쪽 키) 쌍.

## 설계 1 — 실행기 묶음(Runner)으로 벽 허물기

프로그램 하나를 다루는 데 필요한 것은 딱 4가지다. 이걸 작은 묶음으로 정의:

```python
class Runner:
    vars_info            # 상태 변수 목록 + 성격(래치/시각/카운터) — VarInfo dict
    axes                 # 이 프로그램이 구분하는 입력 칸·시간 임계 — Axes
    def check_finite()   # 못 다루는 변수 이름 목록 (비면 통과)
    def step(vars, gv, inputs, now_ms, first_tick) -> StepResult
```

- **JoiRunner**: 기존 함수 호출을 그대로 감싼다. 동작 변화 0.
- **IrRunner**: 이번에 새로 만든다 (ir_step.py).
- product_explore는 Runner 두 개를 받도록 고치고, 기존 시그니처는 얇은
  래퍼로 유지 → **기존 회귀(자기동치 6/6, 고장 4/4, e1 표)가 그대로
  통과해야 리팩터 성공.** 나중에 W4의 HA 실행기도 세 번째 Runner로 들어온다.

## 설계 2 — IR의 실행 상태는 딱 5종

IR(json)을 op 목록으로 읽고, 아래 상태만 둔다. 전부 탐색기가 이미 아는
정규화 클래스라 normalize()를 재사용할 수 있고, 유한성이 그냥 성립한다:

| 상태 | 뜻 | 정규화 클래스 |
|---|---|---|
| `pc` | 지금 어느 op에서 기다리는 중 | 유한 enum |
| `since_<i>` | wait 지속·제한시간·delay의 시작 시각 | 시각 레지스터(zone) |
| `cnt` | cycle 반복 횟수 | 포화 카운터(cap=count 상수) |
| `prev_<i>` | edge 감지용 직전 값 | bool 래치 |
| `done` | 타임라인 종료 | bool 래치 |

IR의 비교 상수·시간 상수는 IrRunner.axes로 내놓아 기존 규칙대로 양쪽
합집합으로 칸을 나눈다.

## 설계 3 — 시간 해석 규칙 (JoI 타깃, 여기서 명문화)

IR의 시간은 JoI와 같은 tick 격자 위에서 읽는다:

- `delay N` — 경과 ≥ N이 되는 **첫 tick**에 다음 op로.
- `wait ... for N` (지속) — 조건이 끊기지 않고 유지 + 경과 ≥ N이 되는 첫 tick에 발화.
- `wait ... timeout N` — 조건이 먼저 참이 되면 성공 길(다음 op),
  경과 ≥ N이 먼저 오면 `on_timeout` 블록 실행 후 이번 회차 종료.
- `cycle period P` — 회차가 끝나면 다음 P 경계 tick에서 처음부터. count/until 도달 시 done.

이 규칙이 IR의 공식 의미가 되면, 구 검증기의 tolerance가 눈감아 주던
"한 tick 늦는 lowering"(comparator `>=`→`>` 생존자 8건)이 이제 원리상
DIVERGE로 잡힌다 — E2 재검출 표의 근거가 이 문단이다.

## 설계 4 — 액션 이름 맞추기 (예상되는 최대 잡일)

비교가 성립하려면 IR의 `call target: "Switch.Off"`와 JoI 액션 키
`switch#Office.off(...)`가 같은 이름으로 떨어져야 한다:

- IR 쪽에도 같은 grounding(셀렉터→기기 바인딩)을 태운다 (ground.py 재사용).
- target → (service, method) 변환 표는 카탈로그에서 도출.
- IR cond 문자열("MotionSensor.Motion == false")은 JoI 표현식 문법과 거의
  같으므로 expr 파서 재사용 + 이름 변환만 얹는 방향으로 시도.
- 실제 불일치 목록은 M3에서 전부 드러난다 — 거기서 표를 채운다.

## 구현 순서와 완료 기준

- **M0 (반나절)**: product.py를 Runner 2개 받게 리팩터.
  완료 = 기존 JoI 회귀 전부 불변 통과.
- **M1 (2~3일)**: ir_step.py를 op 쉬운 것부터:
  call/start_at → if → wait(레벨/엣지) → delay → wait for(지속) →
  cycle(count/until/break) → **wait timeout(동결된 신규 문법)** → read.
  단계마다 손 tick 테스트.
- **M2 (반나절)**: 382 데이터셋에서 대표 10행(엣지/지속/지연/횟수/분기/cron)
  선정 → IR×IR 자기 비교 전부 EQUIV.
- **M3 (1일)**: 같은 10행에서 IR×정답 JoI 전부 EQUIV,
  IR×고장 JoI(기존 고장 주입 유형) 전부 DIVERGE.
  이름 불일치·시간 해석 어긋남이 전부 여기서 드러난다 — W1의 진짜 시험대.
- cron IR은 cron.py의 달력 가드 방식 재사용. ForEach·quantifier는
  ground.py 경유로 M3 이후.

## 위험 요소

1. **액션·조건의 이름 정합** — 기술적으로 어렵진 않지만 양이 많음. M3에서
   불일치 목록을 한 번에 뽑아 변환 표로 해결.
2. **시간 해석 한 끗 차이** — 정답 JoI가 M3에서 가짜 DIVERGE를 내면
   설계 3의 규칙과 lowering 관행이 어긋난 것. 규칙을 고칠지 lowering
   교본(exemplar)을 고칠지 그때 결정하고, 결정을 이 문서에 기록.
3. **382 레퍼런스 IR의 품질** — 카탈로그 재감사(§5.2)와 맞물림. M2 표본은
   재감사가 끝난 행에서 뽑는다.
