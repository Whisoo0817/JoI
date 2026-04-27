# JoI-LLM 논문 정리 (중간 스냅샷)

자연어 → JoI(반응형 IoT DSL) 변환 파이프라인에서, 9B급 local LLM(Qwen3-9B-AWQ)으로 **정확하고 검증 가능한 코드 생성**을 달성하기 위한 방법론 정리.

> **Thesis**: Reactive temporal DSLs encode trigger and time-window semantics through **idioms** rather than primitives. This single property couples two otherwise-separate hard problems — small-LLM generation and specification-free verification — and **the same executable intermediate representation resolves both**.

---

## 0. JoI 언어 개요

**JoI = service-level reactive IoT DSL.**

- 표면적으로 Python과 유사한 imperative syntax. 디바이스 service 추상화 위에서 다중 브랜드 IoT를 통합 제어.
- 모듈: `if`, `wait until`, `cron`, `period`, 디바이스 service 호출.
- **컴파일러 없음, return value 없음, 결정론적 출력 없음.** 실세계 디바이스에 발생하는 side effect가 곧 "실행 결과".

표현 가능한 시나리오 스펙트럼:

| 난이도 | 예시 | 핵심 구조 |
|---|---|---|
| Trivial | "오후 5시에 섹터 A 조명 켜줘" | cron 1회 |
| Simple | "비가 오면 창문 닫아" | 단일 조건 1회 |
| **Bounded** | "오후 1~3시 동안 5분마다 온도 체크" | 시간 창 + 주기 |
| **Persistent** | "문이 열릴 때마다 조명 켜줘" | rising-edge 반복 (≠ 1회) |
| **Trigger→Periodic** | "움직임 감지되면 5분마다 사이렌" | 이벤트 후 주기 |

**핵심 사실:** Bounded / Persistent / Trigger→Periodic 시나리오는 JoI 언어에 **first-class primitive가 없다**. 개발자가 일반 변수(`triggered`, `phase`, `start_time`)와 일반 control flow로 **idiom**을 짜서 구현해야 한다. 즉 reactive temporal semantics가 **idiomatic encoding** 레벨에 산다.

---

## 1. 문제 정의 (Problem Statement)

### 1.1 Motivating Example

세 명령어를 보자:

```
(a) "문이 열리면 조명을 켜줘"
(b) "문이 열릴 때마다 조명을 켜줘"
(c) "If the door opens, turn on the light."
```

(a)와 (c)는 **자연어 자체가 모호**하다 — 1회성(`if`)인지 매 발생(`whenever`)인지 텍스트만으로 결정 불가. (b)는 한국어 형태소 "마다"로 disambiguate되지만, 동일한 의미를 영어로 옮기면 "when/whenever/every time" 중 무엇이 정확한지가 다시 흐려진다.

이 의미 차이가 JoI에서는 **전혀 다른 idiom**으로 나타난다:

```python
# (a) 1회 — if idiom
if (Door.value == 'open') { Light.on() }

# (b) 매 발생 — rising-edge idiom (언어 primitive 없음, 관용구로 인코딩)
triggered := false
cycle {
    if (Door.value == 'open') {
        if (triggered == false) { Light.on(); triggered = true }
    } else { triggered = false }
}
```

**End-to-end 9B baseline의 실패 양상** *(placeholder 숫자 — 실험으로 채울 자리)*:
- (a)/(b) 의미 구분 정확도: 9B 단일 단계 38%, GPT-4 71%
- (b)의 idiom 정확 구현률: 9B 12%, GPT-4 54%

→ **모델 규모를 키워도 문제가 사라지지 않는다.** Idiom 선택은 단순 scaling으로 해결되지 않는 systematic error class.

### 1.2 Problem Setting

**Input:**
- $u$: natural language utterance (Korean or English)
- $D = \{(d_i, S_i, A_i)\}$: device catalog (device id, callable services, observable attributes)

**Output:**
- $P \in \mathcal{L}_{\text{JoI}}$: an executable JoI program

**Requirement:**
$$
\text{behavior}(P, E) = \text{intent}(u, D, E) \quad \forall E \in \mathcal{E}_{\text{cover}}(u)
$$

where $E$ is an event sequence (sensor readings, clock ticks) and $\mathcal{E}_{\text{cover}}$ is a coverage-complete event distribution. Behavioral equality is taken **modulo idiom-quotient** (formalized in §6).

### 1.3 Three Constraints That Define the Problem Class

**(C1) Idiomatically-encoded reactive semantics.**
$\mathcal{L}_{\text{JoI}}$ lacks first-class primitives for rising/falling edges, bounded time windows, phase transitions, and trigger-then-periodic structures. These semantics are expressible only through a finite idiom set $\mathcal{I} = \{i_1, \ldots, i_k\}$ over ordinary variables and control flow.

**(C2) No verification anchor.**
There is no compiler, no canonical NL→DSL ground-truth mapping, and no deterministic execution result against which a generated program $P$ can be checked. Side effects on physical devices cannot be replayed.

**(C3) Local-only deployment.**
Production targets run on on-premise hardware (≤9B parameter LLMs) due to (i) privacy of device state and behavioral data, (ii) sub-second latency for reactive triggers, (iii) offline operation. C3 is not a self-imposed limitation — it is the actual deployment constraint of consumer/industrial IoT hubs. Our findings (§1.1) further show the difficulty under C1+C2 does **not** vanish with model scale; C3 makes the difficulty visible, but the underlying problem class is scale-independent.

### 1.4 The Coupled Challenge

C1 alone does not make the problem unique — many DSLs use idioms. C2 alone is a verification problem solvable by testing, given a spec. **The novelty of this problem class is their coupling**:

```
                  ┌──────────────── C1 (idiom encoding) ────────────────┐
                  │                                                      │
   NL ──────► generation needs                          verification needs
              idiom-selection                           idiom-aware equivalence
              knowledge                                 (bisimulation breaks)
                  │                                                      │
                  └──── shared root cause: no idiom-free representation ──┘
```

**Claim:** Any solution to *only* generation leaves verification open and unfalsifiable. Any solution to *only* verification requires the spec we don't have. **The two must be solved together, and they are solvable together because they share the same missing artifact: a representation in which idiomatic semantics are first-class.** That artifact is the **Timeline IR**.

### 1.5 Research Questions

- **RQ1.** Can natural language utterances with idiom-encoded reactive temporal semantics be reliably mapped to an intermediate representation by a 9B-scale LLM?
- **RQ2.** Given such an IR, can a target-language program be lowered such that its behavior is *verifiably* equivalent to the IR — without a compiler, formal specification, or ground-truth program?
- **RQ3.** Does the same artifact (Timeline IR) that enables RQ1's generation also enable RQ2's verification, and at what cost?

### 1.6 Scope and Non-goals

**In scope.**
- Korean and English single-utterance commands
- Temporal triggers, time windows, periodic and edge-driven semantics
- Behavioral verification of generated programs against an executable IR
- 9B-scale local LLM as primary generator; cloud models as comparison

**Out of scope.**
- Multi-utterance dialogue (each command treated independently)
- Spatial reasoning over room geometry (catalog gives device IDs, not positions)
- Device authentication, access control, security
- Conflict resolution between concurrent automations
- Synthesis of new device service abstractions; $D$ is fixed
- Energy-aware or QoS-aware scheduling
- Continuous-time / hybrid-system semantics; IR is discretization-bounded (§6)

---

## 2. 문제 해결 필요성 (Why it matters)

1. **Local 배포 요구**: 프라이버시·지연·비용 제약으로 on-device LLM 수요가 크다. 9B급은 복합 reactive semantics에 약하고, 큰 모델 또한 idiom 정확성에서 systematic error를 보인다.
2. **IoT 도메인의 안전성**: 잘못된 시제 해석(예: one-shot을 cycle로) → 계속 동작 / 동작 누락 같은 실제 물리적 오류.
3. **검증 공백**: NL→DSL 연구 대부분은 BLEU/exec-accuracy에 의존 — reactive semantics 정확성을 실제로 검사하지 못한다.
4. **일반화 가능성**: 동일한 "IR + idiom-quotient trace 동치" 프레임워크는 idiomatic-encoded reactive language의 광범위한 클래스로 이식 가능:

| 도메인 | 예시 시스템 | 대표 idiom |
|---|---|---|
| Smart Home / IoT | JoI, Home Assistant, openHAB | `triggered` flag for edge |
| Workflow automation | n8n, Zapier code, IFTTT JS | state-tracking variables |
| Robotics | ROS scripts, behavior tree DSLs | `phase` enum |
| Game scripting | Roblox Luau, Unity events | tick-based polling |
| Build / CI | GitHub Actions inline, GitLab CI | implicit step ordering |
| Stream processing | KSQL, Flink with windows | window via aggregation |

---

## 3. 문제 해결 방법 (Approach)

### 3.0 설계 진화와 User-in-the-Loop 통찰

**초기 시도 (실패):** End-to-end NL → JoI 생성 후, 생성된 JoI를 다시 자연어로 **재번역(JoI→NL)** 해서 원 명령과 의미적으로 비교하려 했다. 재번역 프롬프트(`re_translate.md`)는 사실상 **1:1 암기식 매핑** — JoI 패턴마다 자연어 표현을 사람이 손으로 적어둔 lookup table이다. 결과:
- 익숙한 패턴은 잘 번역하지만 **4건 중 1건 꼴로 잘못 해석**
- 새롭거나 idiom이 조금만 복잡해지면 표현 범위 밖으로 떨어짐
- 근본적으로 §4에서 분석할 **JoI→NL 비대칭 손실**이라는 한계

**핵심 통찰:** **IR → NL은 본질적으로 쉽다, JoI → NL은 본질적으로 어렵다.**

| 방향 | 난이도 | 이유 |
|---|---|---|
| JoI → NL | 어려움 | reactive semantics가 idiom으로 인코딩됨 → `triggered`-flag 패턴이 일반 변수와 syntactic하게 구별 안 됨 → decompilation 수준의 분석 필요 |
| IR → NL | 쉬움 | IR의 9 ops는 시간 의미론의 first-class primitive — `wait(edge:rising)`은 한국어 "~할 때마다"로 결정론적 1:1 매핑 |

**검증 문제의 분할 (Crucial Reframing):**

```
원래 verification 문제:    NL ────────?──────── JoI    (자동화 불가능)
                              │
              ┌───────────────┴───────────────┐
              │                               │
분할 후:    NL ──[user-confirm]── IR ──[trace eq]── JoI
              │                               │
        human-in-the-loop                automatic
        (NL→IR readable 보고             (IR이 reference로
         사용자가 OK)                      존재 → trace 비교)
```

사용자가 IR-readable을 확인하고 OK를 주면, 그 시점부터 **NL→IR의 의도 매핑은 grounded**된다. 사용자가 IoT 비개발자라도 "이 시스템이 내 명령을 이런 로직으로 수행하려 한다"는 step-by-step 한국어 설명은 읽을 수 있다 (§7.4의 trigger 매핑 룰 + IR의 9 ops가 일상어와 거의 1:1). 이는 **단순 사용성 향상이 아니라 verification 가능성의 전제**다:

- **사용자 OK 이전:** verification 대상은 "NL → JoI 전체"이며 spec이 없음 → 자동 검증 불가능 (§5의 model checking 한계).
- **사용자 OK 이후:** verification 대상은 "IR → JoI"로 축소되며 IR이 reference 역할 → §6의 trace equivalence가 sufficient discriminator가 됨.

즉 user-in-the-loop은 **자동화의 결함을 사람이 메우는 우회로가 아니라, 검증 가능성을 만드는 구조적 요소**다. 이 구조가 없으면 §6 theorem은 "무엇과 비교할 것인가"라는 질문에 답하지 못한다.

### 3.1 파이프라인 전체 구조

```
[NL(KO)]
   │  Stage 1: K→E 번역 (morphology → trigger 결정론적 매핑)
   ▼
[NL(EN)]
   │  Stage 2: NL → Timeline IR (9B, schema validated)
   ▼
[IR] ──▶ readable NL ──▶ 사용자 confirm/feedback ──(수정)──▶ [IR']
   │
   │  Stage 3: IR → JoI (lowering)
   ▼
[JoI code]
   │
   │  Self-correction: 동일 event 시퀀스를 IR simulator와 JoI simulator에 주입
   ▼
trace(IR) ≟_π trace(JoI)  ── 불일치 시 Stage 3 재시도

※ 동일 메커니즘으로 ground-truth IR/JoI와 trace 비교 → evaluation으로 전용 가능
```

**오차 흡수 구조:**
- **NL ↔ IR 오차**: 사용자 피드백(IR readable)으로 보정. 100% 보장은 아니나 사람이 개입할 수 있는 루프 제공.
- **IR ↔ JoI 오차**: idiom-quotient trace 동치 비교로 자동 보정. Stage 3의 의미 보존 여부를 기계적으로 판정.

### 3.2 방법론적 기여 (Contributions)

- **C1 (Timeline IR)**: Reactive-IoT 도메인에 특화된 9-op fixed grammar IR. 9B 추출 용이성 + 시간 semantics 표현력 + first-class temporal primitives.
- **C2 (Idiom-Quotient Trace Equivalence)**: IR과 JoI 코드가 같은 의미인지 구조 동일성이 아닌 **observable trace의 π-동치**로 판정. Bisimulation을 idiom-quotient 위에서 정의해 self-correction과 evaluation 모두에 사용. **본 논문의 핵심 이론 contribution.**
- **C3 (Reactive MC/DC Coverage Synthesis)**: IR의 분기·edge·cycle.until 구조를 dependency-guided로 분석해 polynomial-size의 coverage-complete 이벤트 시퀀스를 자동 생성.
- **C4 (Multi-stage pipeline + IR-mediated user-in-the-loop)**: 검증 문제를 NL↔JoI에서 **NL↔IR (human-confirmed) + IR↔JoI (auto-verified)** 로 분할. IR-readable 렌더링이 결정론적으로 가능한 이유는 IR이 first-class primitive를 갖기 때문이며, 이는 단순 UX가 아니라 §6 theorem의 reference anchor를 만드는 구조적 요소다. Korean morphology → trigger 결정론 매핑, Stage 2/3 분리 포함.
- **C5 (Temporal-Branching Entropy)**: 문제 난이도 지표. IR 내 cycle/if/edge-wait 분포로 입력 명령의 시간 분기 복잡도를 정량화.

---

## 4. 왜 자연어 역변환(NL round-trip)이 검증 수단이 될 수 없는가

### 4.1 초기 접근 — JoI → NL → 자연어 유사도 비교
초기 설계는 "JoI 코드를 자연어로 되돌려 원래 명령어와 비교한다"는 round-trip 방식이었다. 이 방식의 핵심 문제는 **NL과 JoI 코드의 표현 범위가 비대칭**이라는 점이다.

### 4.2 NL → JoI: 의도를 커버할 수 있다
자연어 명령이 담은 의도는 JoI 코드로 표현 가능하다. "문이 열릴 때마다 조명을 켜줘" → `cycle { wait(rising); Light.on() }` 처럼 자연어의 의도를 JoI의 구조로 충분히 담아낼 수 있다.

### 4.3 JoI → NL: 의도를 복원할 수 없다

**이유 1 — Idiom 인코딩의 불투명성**:
JoI는 `rising edge`, `phase lifecycle` 같은 reactive primitive를 언어 레벨에서 제공하지 않는다. 대신 개발자가 `triggered`, `phase`, `duration` 같은 **일반 변수로 직접 인코딩**하는 idiom을 사용한다. 이 idiom의 의미는 JoI를 아는 개발자에게는 읽히지만, **형식적으로는 일반 변수와 구별이 없다**. 자동 복원은 단순 parsing이 아니라 **프로그램 분석(decompilation) 수준**의 작업이다.

**이유 2 — 다대다 관계 (non-canonical)**:
- 자연어 하나가 여러 JoI 코드로 표현될 수 있고 (코딩 방식의 다양성),
- JoI 코드 하나가 표현하는 의미를 자연어 하나로 특정할 수 없다.

JoI 코드가 내포한 reactive 의미(주기, edge, 조건 타이밍)를 자연어로 표현하면 **단어 몇 개로 압축**되며, 이 압축 과정에서 timing 정보가 뭉개진다.

**이유 3 — 평가 기준 부재**:
역변환된 자연어가 맞는지 판정할 canonical 정답이 없다. BLEU, 의미 유사도 같은 지표는 reactive 의미의 차이(one-shot vs cycle)를 포착하지 못한다.

### 4.4 결론과 Pivot
NL round-trip은 "JoI가 원래 의도를 담았는가"를 검증하는 수단으로 부적합하다 — **JoI ↔ NL** 방향에서. 그러나 이 비대칭은 한쪽으로만 성립한다: **IR ↔ NL은 다르다**. IR의 9 ops는 시간 의미론의 first-class primitive이므로 IR→NL 렌더링은 결정론적·손실 없이 가능하며 (§3.0, §7.4 trigger 매핑), 이것이 사용자 confirm 루프를 구조적으로 가능하게 만든다. **본 논문이 round-trip을 폐기한 것이 아니라, round-trip의 위치를 NL↔JoI에서 NL↔IR로 옮긴 것**이다 — 그리고 그 이동이 §6의 자동 검증을 가능케 한다.

---

## 5. 왜 Model Checking / FSM이 검증 수단이 될 수 없는가

### 5.1 Model Checking이란
Model checking은 **형식 명세 $\varphi$가 주어졌을 때**, 프로그램이 그 명세를 만족하는지($M \vDash \varphi$)를 모든 가능한 상태를 열거해 자동으로 판정하는 방법이다. 보통 명세는 LTL(선형 시제 논리)이나 CTL로 표현한다.

### 5.2 왜 이 문제에 맞지 않는가

**불일치 1 — Property checking이 아니라 equivalence checking**.
Model checking은 $M \vDash \varphi$ — 프로그램이 형식 명세를 만족하는가를 본다. 우리에게는 $\varphi$가 없다. "자연어를 LTL로 번역"은 원래 문제(NL→의미표현)를 다시 푸는 **순환논증**이다.

**불일치 2 — 상태 폭발 (State Explosion)**.
- `period:100ms` polling → 시나리오 1시간 = 36,000 틱
- 센서 변수(temperature: 실수값), flag 변수(`triggered`, `phase`), 지역 변수가 조합되면 상태 공간이 **기하급수적으로 폭발**

**불일치 3 — Idiom bisimulation 문제**.
IR의 `wait(edge:rising)` 과 JoI의 `triggered` idiom은 **내부 상태공간이 다르다**. 두 FSM은 문자 그대로는 bisimilar하지 않으며, "외부 trace만 같다"는 사실을 model checker로 판정하려면 **custom equivalence relation**을 수동 정의해야 한다. → 이게 §6 idiom-quotient theorem의 출발점.

**불일치 4 — 도구 입력 언어 장벽**.
SPIN(Promela), NuSMV(SMV), UPPAAL(timed automata) — 이들 중 어느 것도 JoI를 직접 받지 않는다. JoI → 해당 언어 번역 자체가 semantics-preserving transformation 문제다.

**불일치 5 — 출력 형태가 evaluation에 부적합**.
Model checker의 출력은 `✓/✗ + counterexample`. 우리가 필요한 것은 정량 지표(trace 일치율, 탐지율, 난이도별 커브)와 Stage 3 재시도 학습 신호다.

### 5.3 비교 요약

| 차원 | FSM / Model Checking | Trace Equivalence (본 제안) |
|---|---|---|
| 목표 | $M \vDash \varphi$ (property satisfaction) | $\text{trace}(IR) \equiv_\pi \text{trace}(JoI)$ (behavioral equivalence) |
| 명세 | LTL/CTL 필요 — 자연어 입력에서 없음 | reference IR이 명세 역할 |
| 실수 값·연속 시간 | 추상화 수동, decidability 위험 | discrete simulator로 직접 실행 |
| Idiom (phase/triggered) | FSM 상태가 달라 bisimilar 아님 | quotient automaton 위에서 자동 흡수 |
| 상태 폭발 | 센서·period·변수 조합으로 폭발 | dependency-guided 표본 커버리지 |
| 입력 언어 | Promela/SMV로 재번역 필요 | JoI 그대로 (parser + simulator) |
| 출력 | ✓/✗ + counterexample | 정량 trace-match rate |

### 5.4 한계 인정 (리뷰어 선제 대응)
Trace 동치는 **표본 기반**이므로 모든 가능한 이벤트에 대한 완전성을 증명하지 못한다. 그러나 Reactive MC/DC coverage(§6.3)가 polynomial-size로 idiom-quotient bisimulation의 sufficient discriminator를 제공한다 — 즉 **표본 기반이지만 이론적 보증이 있다**.

---

## 6. 이론적 핵심 (Idiom-Quotient Trace Equivalence)

### 6.1 Definitions

**Definition 6.1 (Idiom).** An idiom $i \in \mathcal{I}$ for target language $\mathcal{L}_{\text{JoI}}$ is a triple $(\sigma_i, G_i, r_i)$ where:
- $\sigma_i$: syntactic pattern (AST template)
- $G_i$: ghost variable set (e.g., `triggered`, `phase`)
- $r_i$: semantic role label (e.g., `rising_edge`, `phase_transition`)

**Definition 6.2 (Idiom-Quotient Automaton).** Given JoI program $J$ and idiom set $\mathcal{I}$, the quotient automaton $Q(J, \mathcal{I})$ is the LTS obtained by:
1. Identifying $\sigma_i$-matching subtrees in $J$
2. Absorbing $G_i$ ghost variables into internal state
3. Exposing $r_i$ as transition labels

**Definition 6.3 (π-Trace Equivalence).** Programs $P_1, P_2$ are π-equivalent under event sequence $E$, written $P_1 \equiv_\pi^E P_2$, iff
$$\pi(\text{exec}(P_1, E)) = \pi(\text{exec}(P_2, E))$$
where $\pi$ projects onto observable device API calls (target, args, timestamp).

### 6.2 Main Theorem

**Theorem 6.1 (Idiom-Soundness of Trace Equivalence).** Let $\mathcal{E}_{\text{cover}}$ denote the reactive-coverage-complete event family (§6.3). Then:
$$Q(J, \mathcal{I}) \sim_{\text{bisim}} \text{IR} \;\;\iff\;\; \forall E \in \mathcal{E}_{\text{cover}}(\text{IR}). \; J \equiv_\pi^E \text{IR}$$

좌변은 **검증 불가** (state explosion). 우변은 **검증 가능** (polynomial simulation). 좌우의 동치성이 본 논문의 핵심 결과 — **state-explosion-prone한 검증 문제를 polynomial-time simulation으로 환원**시킨다.

### 6.3 Coverage Theorem (Auxiliary)

**Definition 6.4 (Reactive Coverage).** $E$ is *reactive-coverage-complete* for IR if it exercises:
- 모든 `if` 노드의 then/else
- 모든 `wait(edge:rising)` 노드의 (false→true) transition
- 모든 `wait(edge:falling)` 노드의 (true→false) transition
- 모든 `cycle.until=φ` 노드의 (φ false 유지) and (φ true 도달)

**Theorem 6.2 (Coverage Sufficiency).** Let $B$ = branching points in IR, $D$ = max nesting depth. There exists $E^*$ with $|E^*| \leq O(|B| \cdot 2^D)$ such that
$$\forall J \not\equiv_\pi \text{IR}. \; \text{exec}(J, E^*) \neq \text{exec}(\text{IR}, E^*)$$
(modulo idiom-quotient).

**Algorithm.** IR을 AST로 traverse하면서 각 branching point에 대해 (조건 만족 / 불만족) 이벤트를 결정론적으로 생성. `devices_referenced`로 어떤 센서값을 조작할지 결정.

### 6.4 Proof Obligations (작성 시)
- IR operational semantics를 LTS로 명시 (small-step inference rules)
- JoI operational semantics를 tick-based execution layer로 명시
- 각 idiom $i \in \mathcal{I}$에 대해 quotient construction이 well-defined임을 증명 (한 idiom당 1쪽 분량)
- Coverage theorem은 IR structure에 대한 induction

---

## 7. Timeline IR을 써야 하는 이유 (Why Timeline IR?)

### 7.1 대안과의 비교
| 접근 | 문제점 |
|---|---|
| **End-to-end NL→JoI** | 9B가 시제+시간+구문을 동시에 맞추지 못함. 오류 귀속·검증 불가. |
| **Phase-graph IR** (초기 설계) | Case B(지연 후 diff), Case C(점진적 업데이트+break) 같은 순차 로직이 한 phase 안에 길게 들어가 JSON이 비대·복잡해지고 9B 추출 정확도 급락. |
| **AST 수준 IR** | JoI 문법에 너무 가까워, 번역·동치 체크의 추상화 이득이 사라짐. |

### 7.2 Timeline IR이 해결하는 것
1. **선형 시간 순서**가 자연어의 서술 순서와 1:1 대응 → 9B가 좌→우 pattern-matching만으로 추출 가능.
2. **9개 op의 고정 문법** → hallucination 공간 최소화, 스키마 검증으로 형식 오류 기계적 제거.
3. **`cycle.until` / `read` / `delay` 분리** → Case A/B/C 같은 복합 명령을 평탄한 step 리스트로 표현.
4. **Edge annotation**(`edge:"none|rising|falling"`) → trigger 의미를 IR 레벨에서 명시 (first-class primitive화).
5. **Trace 의미 정의 가능** → IR 자체에서 실행 시맨틱스가 정의되므로 IR과 JoI의 동치를 trace로 판정 가능. **검증 가능성의 핵심.**
6. **Convention β** (args 문자열에 `.`/`$`/연산자 있으면 표현식, 아니면 리터럴) → 리터럴/표현식 구분을 추가 태깅 없이 추론 가능.

---

## 8. Timeline IR 규칙과 스키마

### 8.1 최상위 스키마
```json
{
  "devices_referenced": ["<Device_id>", ...],
  "timeline": [ <step>, <step>, ... ]
}
```

### 8.2 Step Grammar (9 ops)
| Op | 의미 | 주요 필드 |
|---|---|---|
| `start_at` | 시나리오 시작 앵커 | `anchor: "now"` 또는 `anchor:"cron", cron:"<5-field>"` |
| `wait` | 조건 충족까지 블록 | `cond`, `edge: none\|rising\|falling` |
| `delay` | N ms 정지 | `ms:<int>` |
| `read` | 값 스냅샷을 지역변수에 bind | `var`, `src:"<Device.attr>"` |
| `call` | 디바이스 메소드 호출 | `target:"<Device.method>"`, `args:{...}` |
| `if` | 1회성 분기 | `cond`, `then:[...]`, `else:[...]` |
| `cycle` | 반복 루프 | `until:"<expr>\|null"`, `body:[...]` |
| `break` | 최근접 cycle 탈출 | — |

### 8.3 Expression Grammar
- 리터럴: 숫자, 문자열, 불린.
- 속성 참조: `Device_id.attr` (예: `TempSensor_1.temperature`).
- 지역 변수: `$varname` (prior `read` 결과).
- Clock: `clock.time` (`"HH:MM"`), `clock.date` (`"MM-DD"` or `"YYYY-MM-DD"`), `clock.dayOfWeek`(`"MON".."SUN"`).
- 연산자: `+ - * / ( )`, `== != < > <= >=`, `&& || !`, `abs(x)`.
- **Convention β**: args 문자열에 `.`, `$`, 또는 연산자 포함 → 표현식; 아니면 리터럴.

### 8.4 Trigger 매핑 (핵심 규칙)
| 영어 | IR 패턴 |
|---|---|
| `if X, do Y` | `if` 1회성 분기 (wait/cycle 없음) |
| `when X, do Y` | `wait(edge:"none") + Y` — 1회, cycle 없음, rising 없음 |
| `whenever / every time X, do Y` | `cycle { wait(edge:"rising"); Y }` |

### 8.5 Validator 규칙 (`validate_ir`)
- 최상위: `devices_referenced`(list of str) + `timeline`(non-empty list).
- 첫 step은 `start_at`이어야 함.
- `cycle.body`는 **delay 또는 edge-triggered wait** 중 하나 이상을 포함해야 함 (cadence 보장).
- `wait.edge`는 `none|rising|falling` 중 하나.
- 모든 `Device.attr`/`Device.method`는 제공된 Service 카탈로그에 존재해야 함.
- 중첩 루프(nested cycle) 금지.

### 8.6 Reject 조건
- cycle 요청되었으나 주기 명시 안 됨 (예: "번갈아 ~" without period).
- 정의되지 않은 device/attr 참조.
- Nested loop 요구.

---

## 9. 앞으로의 계획 (Roadmap)

### 9.1 단기 (구현 완료 검증)
- **Stage 3 (IR → JoI) 구현**: 17개 few-shot IR 케이스에 대해 lowering 템플릿 확정 → 컴파일 가능성·실행 정확도 측정.
- **Reject case 튜닝**: "번갈아 without period" 같은 케이스에서 silent failure 존재 → 프롬프트에 명시적 reject 예제 추가.

### 9.2 중기 (이론 + 구현)
- **§6 Theorem 형식화**:
  - IR/JoI operational semantics 작성 (small-step LTS).
  - Idiom set $\mathcal{I}$ 명세 (5~6개 핵심 idiom: rising-edge, falling-edge, phase, bounded-window, trigger-then-periodic, cycle-until).
  - Quotient construction well-definedness 증명.
  - Theorem 6.1 / 6.2 증명.
- **C2/C3 구현 — Trace 기반 동치**:
  - IR 실행 시맨틱스 참조 구현 (Python simulator).
  - JoI simulator: parser AST 위 tick 기반 실행 레이어 (period + 변수 persistence + wait until).
  - `devices_referenced` 기반 Reactive MC/DC event synthesis.
- **C5 — Temporal-Branching Entropy**: 가중치 정당화 + 데이터셋 난이도 분포 보고.

### 9.3 평가 (Evaluation Plan)
- **데이터셋**: 기존 Korean IoT 명령 + Case A/B/C 확장 + 합성 복합 명령.
- **Baselines**:
  - (a) End-to-end NL→JoI (9B 단일 단계)
  - (b) AST-IR 경유
  - (c) GPT-4 class end-to-end (상한선 비교)
- **Metric**:
  - Stage 2 정확도 (IR structural + trace 동치 vs reference)
  - Stage 3 컴파일/실행 정확도
  - End-to-end trace 동치율
  - Temporal-Branching Entropy 구간별 성능 커브
  - Mutation 탐지율 (의미 변형 IR/JoI를 trace 검증이 잡아내는 비율)

### 9.4 장기 (논문화)
- **일반화 검증**: Timeline IR + idiom-quotient trace 동치 프레임워크를 Home Assistant automations / IFTTT-style / behavior tree DSL로 이식 실험.
- **한계 분석**: 중첩 루프, 연속 시간(analog time) 조건, 분산 트리거 등 Timeline IR로 표현 불가한 영역의 경계 명시.

---

## 10. 게재 후보 venue

- **ACM IMWUT / UbiComp** (직접 경쟁: ChatIoT'24, HomeGenii'25, Sasha'24)
- **IEEE Internet of Things Journal** (SAGE'25 게재된 곳)
- **ICSE / FSE** (DSL 합성 + verification 측면)
- **ACL / EMNLP** (NL→IR + idiom 인코딩 측면)
- **NeurIPS / ICLR** (이론 contribution이 강해질 경우)

---

## §1 작성 시 리뷰어 반박 선제 차단 체크리스트

| 예상 반박 | 차단 위치 |
|---|---|
| "GPT-4면 되지 않냐" | §1.1 숫자 + §1.3 (C3 note) — scale-independent |
| "Smart home 한정 아니냐" | §1.4 + §2 — idiomatic-encoded reactive language 일반 클래스 |
| "Model checking 쓰면 되잖아" | §1.3 (C2) + §5 — spec 부재 |
| "NL round-trip 쓰면 되잖아" | §1.1 + §4 — NL↔DSL 비대칭 |
| "왜 IR이 답이냐" | §1.4 coupling argument — IR이 공유 anchor로 자연스럽게 도출 |
| "Trace 동치는 incomplete 아니냐" | §5.4 + §6.3 — Coverage theorem이 polynomial discriminator 보증 |

---

## 부록 — 현재 구현 상태

- `joi_new/files/translation.md` — K→E 번역 프롬프트 (morphology 룰 내장).
- `joi_new/files/timeline_ir_extractor.md` — NL→IR 추출 프롬프트 (17 few-shot).
- `joi_new/timeline_ir.py` — 파이프라인 모듈 (`translate_to_english`, `extract_ir`, `validate_ir`, `ir_to_readable`, `DEFAULT_TEST_DEVICES`).
- `joi_new/ir_code_example.md` — NL-IR-JoI 매핑 예제 11개 (Stage 3 lowering 참조용).
- 11개 한국어 명령에 대해 Stage 1+2 end-to-end 검증 통과 (Stage 3 + §6 이론 미구현).
