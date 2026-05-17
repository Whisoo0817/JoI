# SenSys 타겟 전략 정리

본 논문(NL→JoI, on-device SLLM, Timeline IR 분해, transition-obligation coverage)을 SenSys 라인에 제출하기 위한 venue 분석·관련 작 정리·acceptance 패턴·문제 framing·reviewer rebuttal.

---

## 1. Venue 정보 (SenSys 2027 R1)

- **마감**: Abstract **May 29, 2026** / Full paper **Jun 5, 2026** (AoE)
- **분량**: Full ≤12 pages 본문, references·appendix 무제한
- **포맷**: ACM `acmart.cls` sigconf, 2-column, 9pt
- **익명화**: 완전 익명, 위반 시 desk-reject
- **R2**: TBD (R1 rejected 시 substantive revision + reviewer response 동반 재제출 가능)

준비 가용 기간 약 3주. 빡빡하지만 R2 옵션 있음.

---

## 2. 가까운 SenSys 2025/2026 논문 5선

| 순위 | 논문 | 무엇 | 본 논문과의 거리 |
|---|---|---|---|
| 1 | **GPIoT** (SenSys 2025) | SLM fine-tune + IoT 코드 합성 + IoTBench | **★ 가장 가까움.** 세팅 동일(SLM+IoT+local). 솔루션 다름(data-centric fine-tune). reactive 의미·verification 없음 |
| 2 | **TaskSense** (SenSys 2025) | NL→센서 태스크 plan, 'sensor language' 번역, dependency check | NL→IR 분해 framing 사상적으로 유사. 그러나 one-shot tasking + plan dependency 검증이라 reactive program / behavioral equivalence 아님 |
| 3 | **Toward Sensor-In-the-Loop LLM Agent** (SenSys 2025) | LLM agent에 sensor hint 주입, WellMax 프로토타입 | LLM-IoT paradigm 제안. 코드 합성 아님, 다른 문제 |
| 4 | **ADLGen** (SenSys 2026) | smart home HAR용 symbolic event-triggered sensor sequence 합성 | "symbolic event-triggered" 키워드 공통. data synthesis라 NL→DSL과 직교 |
| 5 | **EdgeTune** (SenSys 2026) | On-device LLM personalization at edge | C3(on-device) motivation 인용용. 직교 |

---

## 3. SenSys accept 공식 — 공통 패턴 6요소

위 5편 + Sasha·SAGE·HomeBench·SimuHome을 가로지르는 acceptance 요인:

1. **System motivation 명료화**: 프라이버시·latency·offline·비용. abstract 첫 paragraph에 박힘.
2. **두 자릿수 % 정량 효과**: GPIoT +64.7%, TaskSense ×2 planning / +75% answer, HomeBench가 GPT-4o의 0% 약점 폭로.
3. **재현 가능한 벤치마크 부산물**: IoTBench, SensorQA, 170-task TaskSense set, SmartHome-Bench, SimuHome 600 episode.
4. **실제 deployment 또는 high-fidelity simulation**: TaskSense는 real smart home, EdgeTune은 실제 edge HW. 단순 prompt 실험은 거의 reject.
5. **단일 hero abstraction**: GPIoT="SLM fine-tune", TaskSense="sensor language", ADLGen="symbolic event-triggered seq". 평가 전체가 hero 정당화로 정렬됨.
6. **case study + ablation 풍부**, failure 정직: Sensor-In-the-Loop는 명시적 "pitfalls" 섹션. SenSys reviewer가 좋아함.

추가로 거의 필수:
- **token cost / latency 표** (SenSys는 시스템 학회).
- **GPT-4 / GPT-4o와의 비교** (local·특화 모델 paper의 default).

---

## 4. "우리 문제 이미 풀린 거 아닌가?" — 답: 아니. 인접 문제만.

| 논문 | 푼 문제 | 본 논문과의 차이 |
|---|---|---|
| GPIoT | 일반 IoT 코드 합성 정확도 ↑ via SLM fine-tune | data-centric. reactive idiom 인코딩 문제·검증·사용자 확인 안 다룸 |
| TaskSense | NL→센서 태스크 plan + dependency check | one-shot tasking. plan well-formedness 검증이지 behavioral equivalence 아님 |
| Sensor-in-the-Loop | LLM agent + sensor grounding | 런타임 agent. 코드/DSL 생성 아님 |
| ADLGen | HAR용 센서 시퀀스 데이터 합성 | data synthesis. NL→DSL generation 아님 |
| EdgeTune | edge LLM fine-tune 효율화 | HW·시스템 최적화 |

**5편 어디에도 없는 본 논문의 novelty 5가지**:
1. Reactive DSL의 idiom-encoded 시맨틱을 문제 클래스로 정식화.
2. NL→DSL behavioral verification의 anchor 부재 문제.
3. User-confirmed IR을 spec으로 쓰는 구조적 발상 (UX가 아닌 verification 가능성을 만드는 구조).
4. IR-FSM transition-obligation coverage — lightweight MBT를 NL-derived 스마트홈 DSL lowering에 적용한 첫 사례.
5. IR-feature 라벨 기반 self-correction — 결정적 알고리즘이 위반을 IR op에 localize.

---

## 5. IoT-LLM 라인 공통 자산 (인용·데이터셋·디바이스)

### 공통 인용 baseline (빠지면 즉시 reject signal)

| 분류 | 대표작 |
|---|---|
| LLM 스마트홈 agent 1세대 | **Sasha** (IMWUT 2024) — NL 스마트홈 LLM의 정전 |
| LLM 스마트홈 agent 2세대 | **SAGE** (arXiv 2023) — grounded execution tree |
| NL→trigger-action 생성 | **TARGE / "Generating HomeAssistant Automations"** (arXiv 2025) |
| NL→code semantic parsing 원조 | **Quirk et al. "Language to Code: If-This-Then-That"** (ACL 2015) |
| IoT 코드 SLM 라인 | **GPIoT** (SenSys 2025) |
| 시스템 플랫폼 | **Home Assistant**, **openHAB**, **SmartThings** |
| TAP 사용자 행동 분석 | **Ur et al., "Trigger-Action Programming in the Wild"** (CHI 2016) |
| TAP + LLM rule generation | **AutoIoT** (IEEE IoT-J 2024), **ChatIoT**, **AutoIOT2** (arXiv 2025) |

### 공통 데이터셋

- **IFTTT recipes (200K+)** — NL ↔ trigger-action 쌍, semantic parsing 표준
- **HomeBench** (ACL 2025) — valid/invalid × single/multi-device LLM 평가 표준
- **SmartBench / SmartHome-Bench** — 비정상 상태 / video anomaly
- **IoTBench** (GPIoT) — IoT 코드 합성 평가
- **CASAS (Aruba/Milan/Kyoto)** — 31 motion + door + temp 센서, HAR 표준
- **HomeAssistant YAML automation corpus** — GitHub scrape, TARGE 류가 사용
- **SimuHome** (arXiv 2025) — **temporal·environment-aware** 600 episode 시뮬레이션 벤치마크

### 공통 디바이스 / 센서 modality

| 모달리티 | 어디서 |
|---|---|
| Binary motion / door / window contact | CASAS-기반 HAR |
| Temperature / Humidity / Light sensor | smart home automation 표준 |
| Switch / Light / Speaker / Camera | Home Assistant entity와 1:1, NL→DSL paper의 default device pool |
| IMU / 웨어러블 (wrist, glasses) | Sensor-In-the-Loop, WristSense, mmET (SenSys '25 핫) |
| mmWave radar | SenSys 2025 절반 가까이 (sensing modality 핫) |
| Camera + multimodal vision | SmartHome-Bench, ADLGen 일부 |

---

## 6. baseline 구성법 — 라인별 패턴

| 논문 | baseline | 평가셋 | 메트릭 |
|---|---|---|---|
| **GPIoT** | GPT-4o, DeepSeek-Coder, CodeLlama-34b, WizardCoder-33b, CodeQwen-7b, Copilot, MapCoder (RAG) | IoTBench 100 samples | BLEU, format, embedding sim, pass rate, +64.7% |
| **TaskSense** | 6 LLM × {direct prompt vs TaskSense framework} | 4 scenarios × 9 sensor types × 170 tasks × 5 modalities | planning acc ×2, answer acc +75%, token cost |
| **Sasha** | GPT-4 / GPT-3.5 / Llama 2 (7B,13B), 외부 system 없음 | 자체 home template + commands | accuracy, FP, FN, relevance, latency, token, JSON validity |
| **SAGE** | GPT-4 direct, Sasha, ReAct | 자체 SmartThings task set | end-to-end success rate (75% w/ GPT-4) |
| **HomeBench** | 13 LLM | valid/invalid × single/multi (자체 데이터셋) | success rate (GPT-4o 0% on invalid+multi) |

### 본 논문에 적용 시 권장 baseline

- **A.** 9B direct few-shot (NL→JoI one-shot)
- **B.** 9B CoT (NL→step-by-step reasoning→JoI)
- **C.** Ours (NL→IR→JoI)
- **D.** GPT-4 direct (upper bound)
- **E.** (선택) GPIoT 변형 + 우리 데이터셋 — "fine-tune으로 reactive idiom 못 푼다" 메시지용
- **F.** (선택) Sasha-style JSON plan + cron 후처리 — TAP 라인과의 차별 입증용

E·F를 reactive cat 4–9에서 무너뜨리는 게 SenSys reviewer 디펜스에 결정적.

---

## 7. Sasha가 모호한 명령어를 해결한 방법

> 예: "make it cozy", "help me sleep better" — 디바이스·동작 명시 안 됨

**핵심 발상**: 한 번에 plan 만들지 말고, LLM을 5단계로 호출해 단계별로 좁힘.

### 5-stage 파이프라인

```
모호한 NL + Home Template (방·디바이스·센서 JSON)
   ↓
[1] Clarifying : 가용 디바이스로 달성 가능한가? 불가능 시 사용자에게 되묻기 (할루시네이션 plan 방지)
[2] Filtering  : 의미적으로 관련된 minimal 디바이스 집합만 추리기
[3] Planning   : 추려진 디바이스로 action plan / trigger-action pair 생성
[4] Execution  : JSON → 스마트홈 API 호출
[5] Feedback   : 사용자가 NL로 refine, 다시 [3]
```

### 모호성 종류별 stage

| 모호성 | 처리 stage |
|---|---|
| "cozy"가 뭘 켤지 모름 | Filtering — LLM 상식("cozy ≈ 따뜻한 조명·낮은 볼륨")으로 의미적 매핑 |
| 그걸 할 디바이스 없음 | Clarifying — 무리한 plan 안 만들고 사용자에 재질문 |
| 여러 해석 가능 | Feedback — 일단 한 plan 실행 후 NL refine |
| 출력 JSON 깨짐 / 디바이스 환각 | Clarifying + ablation으로 FP 감소 |

### Sasha의 한계 (본 논문 차별 포인트)

- Reactive 시간 의미(rising edge, 시간 윈도우, phase)는 깊게 안 다룸. trigger-action pair는 단순 if-then.
- 영구 deploy되는 reactive 프로그램 생성 아님.
- Plan의 behavioral 정확성 검증 없음 — 사용자 feedback이 유일한 검증.

---

## 8. 디바이스 제어 방식 — 라인별 5가지 패턴

| 패턴 | 대표작 | 영구 deploy? | reactive 시간 1급? | Verification | LLM 호출 빈도 |
|---|---|---|---|---|---|
| **A. JSON action plan (one-shot)** | Sasha | △ (trigger-action pair 한정) | ❌ | 사용자 feedback만 | 명령마다 |
| **B. Agent / tool-call tree** | SAGE | ❌ | n/a (런타임) | 없음 | **매 디바이스 호출** |
| **C. Subtask + 메모리 캐시** | IoTGPT | ❌ | n/a | 없음 | 명령마다 (캐시) |
| **D. Platform DSL 생성** | TARGE, AutoIoT, ChatIoT, home-llm | ✅ | ✅ (플랫폼이 제공) | 스키마/충돌 검출 | 자동화 생성 1회 |
| **E. 함수형 코드 생성** | GPIoT / **JoI = 본 논문** | ✅ | **❌ (idiom 인코딩)** | **IR-FSM coverage** | 자동화 생성 1회 |

**본 논문의 자리**: (영구 deploy) × (DSL이 reactive temporal primitive를 1급으로 안 가짐) × (behavioral verification 있음) — 셋의 교집합이 비어 있었음.

---

## 9. cron / 시간 스케줄 / temporal automation 관련 논문

| 논문 | 시간 처리 | 본 논문과의 거리 |
|---|---|---|
| **TARGE** (arXiv 2025) | HA YAML 직접 생성, time/numeric_state/sun trigger 1급 활용 | YAML이 풍부해 idiom 문제 없음 |
| **AutoIoT** (IEEE IoT-J 2024) | LLM TAP rule + 충돌 검출 + formal verification | 시간 조건 1급, **충돌 검출** angle |
| **ChatIoT** | zero-code TAP 규칙, 토큰 감소 | TAP 수준 |
| **AutoIOT2** (arXiv 2503.05346) | NL→TAP | 유사 |
| **GreenIFTTT** | IFTTT의 multi-device + time condition 확장 | TAP 수준 |
| **Nandi et al.** (PLAS 2016) | NL → trigger 규칙 + **formal verification** | 시간 트리거 다룸, LLM 없이 formal. verification angle 가까움 |
| **SimuHome** (arXiv 2025/2026) ★ | **Temporal·environment-aware** 스마트홈 LLM agent 벤치마크, 600 episode, 시간 가속 시뮬레이션 | evaluation infra 사상 매우 유사. 단 agent setting이지 영구 reactive 프로그램 합성 아님 |

**핵심 관찰**: HA YAML / IFTTT / SmartThings는 **타깃 언어가 시간 트리거를 1급으로 제공** → idiom 문제 발생 안 함. JoI는 1급 없음 → idiom 강제. 본 논문이 차지하는 빈 칸은 **"DSL이 reactive temporal primitive를 1급으로 안 가질 때"** 의 NL→DSL 합성·검증.

---

## 10. 문제 framing

> trigger / duration / phase 같은 reactive·temporal 의미가 복잡하게 얽혀 1급 primitive로 표현 어려움 → idiom 인코딩 → 단계 간 간극 큼 → (a) LLM 생성 불안정, (b) verification anchor 부재, (c) 사용자 코드 의미 못 읽음.

이 세 결과가 하나의 구조적 원인(idiom 인코딩)에서 나오고, 분해(NL→IR→JoI) + user-confirmed IR을 spec으로 사용하는 단일 구조가 세 문제를 동시에 해결.

---

## 11. Reviewer pushback: "primitive 풍부한 플랫폼 쓰면 되잖아?"

가장 흔한 reject 사유. §1.6 scope + §10 rebuttal checklist에 5중 방어 박아두기.

### 방어 1: JoI는 산업 배포된 주어진 DSL — 바꿀 수 없음

- 본 연구는 "어떤 DSL 설계할까"가 아니라 "이미 배포된 JoI 환경에서 NL→DSL을 어떻게 신뢰 가능하게 만들까".
- 멀티 브랜드 abstraction·vendor neutrality 같은 엔지니어링 이유로 JoI 채택됨.
- "다른 플랫폼으로 가자"는 product 선택이지 research contribution 아님.

### 방어 2: Primitive 풍부한 플랫폼도 같은 문제를 숨겨놓을 뿐

HA YAML로 "오후 1–3시 사이 5분마다 lab 온도 측정, 직전 대비 5℃ 이상 오르면 에어컨 켜고, 3시에 상태 리셋"을 표현하면:
- `input_number`로 직전 값 저장 (= **변수 idiom**)
- `template trigger`로 차이 계산 (= **expression idiom**)
- `time_pattern: /5` + `condition: time` (= **윈도우 idiom**)
- 3시 reset용 별도 automation (= **lifecycle idiom**)

→ HA에서도 idiom 사용. template/helper 레이어에 숨겨져 있을 뿐. 사용자 요구의 long tail은 어느 플랫폼에서나 idiom으로 떨어짐.

### 방어 3: Primitive 추가는 product roadmap이지 연구 답이 아님

- rising-edge primitive 추가 → falling-edge·both·hysteresis·debounce 무한 요구.
- 모든 reactive 의미 primitive를 다 넣으면 DSL 폭발.
- 언어 설계 trade-off: 작은 코어 + idiom 합성 (JoI 선택) vs 큰 primitive 집합. 산업 사례 다수(Forth, Lisp, behavior tree 4-node, BPMN)가 전자.

### 방어 4: 문제 클래스가 smart home에 국한되지 않음

같은 idiom-encoded reactive 문제가 발생하는 곳:
- Behavior tree (ROS robotics) — phase enum idiom
- n8n / Zapier code node — state-tracking variable idiom
- Roblox Luau / Unity events — tick-based polling idiom
- KSQL / Flink stream — aggregation으로 window 흉내내는 idiom

JoI는 instantiation 1개. 문제 클래스가 더 넓음.

### 방어 5: JoI 자체의 디자인 가치 — selector·service 추상화

- **`(#Tag #Cat)`, `all()`, `any()` selector**: 멀티 브랜드 디바이스 tag 묶어 일괄 제어. HA는 group/area/template으로 흩어짐.
- **서비스 추상화**: 동일 NL이 다른 벤더(LG TV / Samsung TV / Roku)에서 동일 service로 lowering. HA는 entity별 service domain이 달라 매핑이 LLM 부담.
- **service catalog 기반 lowering**: 형식화된 시그니처 → 검증 출발점 명확. HA service registry는 더 ad-hoc.

→ JoI는 reactive primitive 풍부함을 포기한 대신 selector/service 추상화를 얻은 의도된 trade-off. 우리 연구는 약점을 보완.

### 한 문장 rebuttal

> "Primitive를 추가하면 된다"는 답은 (a) JoI는 산업 배포된 주어진 DSL이라 바꿀 수 없고, (b) primitive 풍부한 플랫폼도 결국 long-tail 요구를 helper/template idiom으로 떠넘기며, (c) idiom 인코딩은 reactive DSL 전반의 구조적 문제라 platform 교체로 사라지지 않고, (d) JoI는 reactive primitive 풍부함을 포기한 대신 selector·service 추상화를 얻은 의도된 설계 선택이라는 4가지 이유로 본 연구를 무효화하지 않는다.

---

## 12. 한 달 안에 채워야 할 acceptance 결정 요소

paper_summary §9 baseline 기준, 1개월 윈도우에서 SenSys-grade를 만들기 위해 반드시 채울 항목:

1. **E1 정량 결과** (idiom-correct 정확도, 9B+IR vs 9B direct vs CoT vs GPT-4) — cat 4–9에서 두 자릿수 격차.
2. **E2 mutation testing** — semantics-preserving 50 + semantics-changing 50, detection ≥95% / FP ≤5%, BLEU·AST·LLM-judge·NL re-translation 비교.
3. **GPIoT를 우리 데이터셋에 직접 돌려 reactive cat에서 무너지는 결과** — novelty 디펜스 결정적.
4. **HomeBench 2축 답습** (valid/invalid × single/multi) + 추가 축 (reactive cat 1–3 vs 4–9).
5. **on-device cost 표** — 9B inference latency, KV-cache reuse 이득, L1/L2/L3 단계별 ms.
6. **데이터셋 600 commands 확장** (cat 4–9 가중) + 공개 artifact 약속.
7. **case study 2–3개**: D-3 rising-edge, D-4 phase lifecycle, time window — 정성 + IR-FSM 사용 vs 미사용 ablation.

---

---

## 13. Codex 평가 — Hero framing별 SenSys 확률

2026-05-15 codex 2회 round adversarial review 결과.

### Round 1 — verification 단독 vs 분해+IR

| Framing | SenSys 확률 |
|---|---|
| Verification mechanism (IR-FSM coverage)를 hero로 단독 | **10–15%** |
| Decomposition + user-confirmed IR as spec를 hero로 | **25–35%** |

→ verification mechanism은 표준 MBT/runtime verification 라인으로 인식. application 도메인이 새롭다 해도 method 자체는 off-the-shelf. **Hero를 분해+IR-as-contract로 잡고 verification은 mechanism으로 종속 배치 권장.**

### Round 2 — Hero 업그레이드 후보 (A·B·C·D)

| Hero | SenSys 확률 |
|---|---|
| A 단독 (behavioral scenario confirmation) | IMWUT 영역, SenSys 15–25% |
| B 단독 (continuous edge hub runtime monitor) | 25–35% |
| **A + B + 실제 배포 증거** | **40–55%** ★ |
| A + B + C-lite (실 센서 trace 보강) | 45–60% |
| D 위주 (multi-device 동적 태그) | 위험 20–30% |

### Round 3 — Hub 권한 없음 제약 추가 후 재평가

저자가 hub 접근 권한 없고 LLM side(NL→JoI 생성)까지가 역할이라는 제약 들어가면:

| Framing | SenSys 확률 |
|---|---|
| Verification 단독 hero | 8–12% |
| Decomposition + IR | 10–15% |
| User-confirm + lowering-time verification | 15–22% |
| Edge-deployable SLLM + latency/memory 강조 | 18–25% |
| **"Pre-deployment safety gate"** framing | **20–28%** (이 경로의 천장) |

→ Hub 권한 없으면 SenSys 본선은 어떤 framing이든 코인 토스 미만. **codex 권고: ICSE/FSE 회전 또는 IMWUT Nov 1로 재배치.**

### Round 4 — 데이터를 method에 박는 경우

Hub trace를 받을 수 있다면, evaluation evidence가 아니라 **method 구성 요소**로 끌어들여야 SenSys-grade.

업그레이드 옵션:
- **옵션 1**: Distribution-aware scenario synthesis (실 hub trace 분포를 IR-FSM 합성 시나리오에 inject)
- **옵션 2**: Failure-pattern-guided obligation prioritization
- **옵션 3 ★**: **Sensor-noise-aware obligation verification** — debounce τ, temporal tolerance ε, concurrent δ, inconclusive 3-valued verdict 4 파라미터를 실 hub trace에서 자동 측정

옵션 3 채택 시 method 한 줄: **"Tolerance-aware transition obligation verification with sensor-noise-derived parameters."** "센서 noise"가 SenSys 정체성 단어와 직결 → 40–50%로 회복 가능.

---

## 14. Hub 데이터 — 형식·항목·규모

### 형식 (이벤트 trace JSON Lines)

```json
{
  "ts_ms": 1715740123456,
  "hub_id": "hub_anon_017",
  "automation_id": "auto_042",
  "device_id": "dev_anon_LR_Light_01",
  "device_category": "Light",
  "service": "Switch.On",
  "method_type": "call|read|event",
  "args": {},
  "result": "ok|timeout|error_<code>",
  "trigger_source": "automation|manual|voice|app"
}
```

선택 필드: `confidence`, `latency_ms`.

### 자동화 메타데이터

```json
{
  "automation_id": "auto_042",
  "nl_command": "...",
  "generated_joi": "...",
  "confirmed_ir": {...},
  "deploy_ts_ms": ...,
  "devices_referenced": [...]
}
```

### Fault 어노테이션

```json
{
  "automation_id": "auto_042",
  "fault_window_start_ms": ...,
  "fault_window_end_ms": ...,
  "fault_type": "sensor_offline|flap|dropped|...",
  "expected_behavior_violation": "rising_edge_missed|...",
  "source": "operator_logged|user_reported"
}
```

### 규모

| 항목 | 최소 | 권장 |
|---|---|---|
| Hub 수 | 3 | 10–20 |
| 자동화 수 | 30 | 100–200 |
| 관측 기간 | 2주 | 4–12주 |
| Reactive idiom 카테고리 커버 | 각 ≥3개 | 각 ≥10개 |
| Fault 케이스 | 10 | 50–100 |

### 데이터 용도 (검증용 일회성, runtime loop 아님)

1. **시뮬레이터 vs 실 hub fidelity 비교** — §6.9 T2 디펜스
2. **검증이 잡는 fault 사례** — §6 hero 입증
3. **합성 시나리오 + 실 분포 coverage** — §6.6 adequacy 보강

3가지 다 **이벤트 trace 한 종류**로 가능. hub 팀 요청 부담 적음.

---

## 15. 문제 framing 정확화 — Idiom 문제 3 요소

본인 직관 정리: idiom 문제는 단일이 아니라 **3가지 복합**.

| 요소 | 설명 | 결과 |
|---|---|---|
| **(a)** DSL primitive 없어 idiom 강제 | rising edge·phase·시간 윈도우를 변수+제어흐름으로 인코딩 | **생성 P1** — LLM이 어떤 idiom 패턴 쓸지 선택 실패 |
| **(b)** 같은 NL이 여러 valid idiom으로 lowering 가능 | `triggered` flag / `prev/curr` / `phase` enum 다 옳음 | **GT 다중성** — BLEU/exact match 무력 |
| **(c)** Idiom은 평범한 코드와 syntactically 구분 불가 | `triggered := false` 줄만 봐선 의미 모름 | **JoI→NL decompilation 수준 난이도** — verification anchor 부재 (P2), user confirm 불가 (P3) |

세 요소가 합쳐져 P1·P2·P3 동시 발생. (b)+(c)가 verification 어려움의 본질 (단순 GT 다중성만이 아님).

---

## 16. Reactive 자체는 unique 아님 — 빈 칸 정확화

기존 SenSys/IoT-LLM 라인 비교:

| Paper | 타깃 플랫폼 | 그들이 푼 문제 | reactive primitive 1급? | idiom 문제? |
|---|---|---|---|---|
| TARGE / HA YAML 생성기 | HA YAML | NL→YAML 매핑 정확도 | ✅ | ❌ |
| AutoIoT | TAP rule | 자동화 사이 conflict 검출 | ✅ | ❌ |
| ChatIoT | TAP rule | token 비용 감소 | ✅ | ❌ |
| Sasha | JSON action plan | 모호한 명령 의도 추론 | ❌ (영구 reactive 아님) | ❌ |
| SAGE | SmartThings API | agent grounding (runtime 결정) | n/a | ❌ |
| HomeBench | API call | valid/invalid × single/multi | ✅ | ❌ |
| GPIoT | Python/C IoT 코드 | 일반 code LLM 도메인 지식 부족 | n/a | ❌ |
| TaskSense | Sensor system API | 태스크 plan + dependency 검증 | n/a | ❌ |
| SimuHome ★ | Matter API | 시간 진화·환경 변수 인식 | ✅ | △ 평가 인프라 |
| Nandi (PLAS '16) | TAP rule | formal verification | ✅ | △ formal angle |
| Brackenbury (CHI '19) | TAP rule | 사용자가 자기 TAP 못 읽음 | ✅ | △ HCI |
| **본 연구** | **JoI (minimal-core reactive)** | **idiom 인코딩 + 검증 + 사용자 확인 동시** | **❌ primitive 빈약** | **✅** |

**핵심**: reactive automation 자체는 모든 라인 공통(보편). **JoI가 특이한 건 reactive primitive가 빈약해서 idiom 강제되는 것**. 이게 §1.4·§2의 motivation 핵심 — "Reactive 설정이 unique한 게 아니라 primitive-poor DSL이 unique".

---

## 17. Temporal evaluation 라인 — 빈 자리

| 평가 패턴 | 누가 | 시간 의미 진짜 검증? |
|---|---|---|
| Syntax/structural (BLEU·AST·embedding) | TARGE·ChatIoT·GPIoT | ❌ "1회성 if"와 "rising-edge cycle"이 같은 점수 |
| Single-step task success | Sasha·SAGE·HomeBench | ❌ 명령 끝나면 평가 끝, "5분 후" 의 5분 안 봄 |
| 시뮬레이터 기반 시간 진화 | SimuHome ★ | ✅ — 단 agent runtime 평가지 lowering 검증 아님 |
| Formal verification | Nandi | ✅ symbolic — execution 안 함 |
| **본 연구** | 시뮬레이터 trace + IR-FSM transition obligation | ✅ **lowering 검증용 시간 trace 단위** ← 빈 자리 |

본 연구의 evaluation 자체가 contribution.

---

## 18. Spurious action 잡힘 메커니즘 — 케이스 스터디

**예시 NL**: "평일 오전에 재실 감지가 10분 이상 안 되면 조명 다 꺼줘. 정오에는 중단."

**GT JoI (multi-GT 중 하나 — `:=` start_time 변형)**:
```
cron: "0 0 * * 1,2,3,4,5"
period: 100ms
code:
start_time := -1
if ((#Clock).time == "1200") { break }
if ((#PresenceSensor).presence == false) {
  if (start_time == -1) { start_time = (#Clock).now }
  if ((#Clock).now - start_time >= 600000) { (#Light).switch_off(); break }
} else {
  start_time = -1
}
```

### Plausible lowering 버그 6종

| 버그 | 설명 | 증상 |
|---|---|---|
| **A** Reset 누락 | `else { start_time = -1 }` 빠짐 | 연속 아닌 누적 10분에 spurious fire |
| **B** 부등호 뒤집힘 | `>= → <=` | 첫 absence 즉시 fire |
| **C** Init guard 누락 | 매 iter `start_time = now` 덮어쓰기 | 영원히 fire 안 함 (missing) |
| **D ★** Spurious action 추가 | `Heater.off` 끼워 넣음 | 시키지 않은 동작 발화 |
| **E** break 누락 | fire 후 break 빠짐 | 100ms마다 반복 fire |
| **F** 단위 실수 | `600000 → 600` | 0.6초에 fire |

### IR-FSM이 자동 합성하는 시나리오 set (transition cover)

| ID | 시나리오 | 기대 동작 |
|---|---|---|
| S1 | presence 시종 true | 발화 없음, 정오 break |
| S2 | presence false 5분 → true | 발화 없음 |
| S3 | presence false 11분 연속 | 10분 시점 Light.off, break |
| S4 | false 5분 → true 1분 → false 11분 | 두 번째 false 구간 10분에 발화 |
| S5 | 정오 도달 mid-absence | break |
| S6 | false/true 짧게 alternating 누적 10분+ | 발화 없음 |

### 잡힘 결과

6/6 버그 모두 검출 (S1–S6 cover 가정).

**Spurious action (D) 잡는 메커니즘**: IR이 `call Light.Off`만 명시 → IR-FSM negative obligation: "이 state에서 허용된 emit 집합 = {Light.Off}. 그 외는 모두 위반." → `Heater.Off` 발화 순간 `SPURIOUS_CALL_NOT_IN_IR (target=Heater.Off)` 라벨. self-correction에 직결.

**반복 발화 (E) 잡는 메커니즘**: 첫 발화 후 state가 "cycle exit"로 진입했어야 함. 두 번째 발화는 그 state에 transition 정의 없음 → `EXTRA_FIRE_AFTER_BREAK`.

→ **Spurious action도 trace equivalence로 잡힘**. 단 IR-FSM coverage가 해당 state에 시나리오 도달 보장해야 함.

---

## 19. Model checking 갭 — IR-FSM이 못 잡는 5종

정직히 인정. paper §6.5 가정 + §6.9 threats에 명시.

| 갭 카테고리 | 예시 | IR-FSM 결과 | 우리 처리 |
|---|---|---|---|
| **(1) Latent JoI 변수** | lowering이 IR에 없는 누적 카운터 추가 | 못 잡음 (IR이 변수 자체 모름) | L3 fallback + mutation testing |
| **(2) 수치 boundary** | `>= 600000` vs `> 600000` | 부분 잡음 (boundary sampling 가능) | scenario에 boundary 추가 |
| **(3) Concurrency race** | 두 자동화 동시 trigger, hub 큐 순서 | 못 잡음 (단일 deterministic sim) | §1.6 out of scope |
| **(4) Long-horizon emergence** | 2.5달 후 32-bit overflow | 못 잡음 (실용 시간 한계) | 시간 scope 명시 |
| **(5) Universal "never" claim** | "Heater 절대 발화 안 함"의 전 입력 공간 보장 | 도달 범위 내 한정 | scope-conditional 표기 |

### 정직한 contribution 위치

> Model checking이 가능하면 그게 더 강하다. 우리 setting (JoI formal semantics 없음 + idiom 다중성 + ≤2s edge budget)에서 그게 불가능한 게 motivation. 우리는 그 빈자리에 MBT를 IR-FSM 구조로 가져와 defensible coverage 제공 — **model checking보다 약하지만 ad-hoc 테스트보다 강한 지점**.

§6.5 transition-obligation completeness (A1–A6) 가 정확히 이 trade-off의 정식화.

---

## 20. 다른 라인의 user confirm 처리 비교

| Paper | user 개입 방식 | 본 연구와 다른 점 |
|---|---|---|
| **Sasha** | (1) Clarifying 가능성 확인, (5) Feedback 사후 NL refine | 영구 reactive 의미 사전 확인 아님 |
| **SAGE** | tool-call tree 중간 clarification 가능 | 대부분 자동, 영구 deploy 없음 |
| **TARGE / HA 생성기** | 생성 YAML 보여주고 적용 동의 | trivial trigger엔 읽힘, idiom 인코딩 region은 못 읽음 |
| **AutoIoT** | 시스템 자동 conflict 검출 | 사용자 의도 확인 아님 |
| **ChatIoT** | dialog로 사용자 반복 refine | 생성 룰 reactive 의미 가독성은 별개 |
| **HCI 라인 (Ur 2014, Brackenbury 2019)** | TAP 사용성 실증 (사용자가 TAP 의미 못 읽음) | 우리 motivation 인용 |
| **본 연구** | IR readable rendering + IR-FSM 시나리오 walk-through | **사전 행동 단위 확인 + verification spec 자격** |

본 연구가 빈 칸: **HCI (읽기 어려움 실증) + 시스템 (verification anchor 부재)** 의 교집합. real-world critical 환경 정서에 직접 호소.

---

## 21. 결정 흐름 — 2026-05-15 기준

| 데이터 확보 | hero framing | 권장 venue | 확률 |
|---|---|---|---|
| Hub trace 받음 + method에 박음 (옵션 3) | "Tolerance-aware obligation + decomposition + IR-contract" | SenSys R1 | 40–50% |
| Hub trace 받음 + 평가에만 사용 | "Decomposition + IR + offline replay" | SenSys R1 (borderline) | 25–35% |
| Hub trace 못 받음 | "User-confirmed IR + lowering-time verification" | **ICSE 2027 / IMWUT Nov 1** | ICSE 15–25%, IMWUT 35–50% |
| Hub trace 못 받음 + 1개월 sprint만 | "NL→IR→JoI 안전 publication" | **IEEE IoT-J SI (6/15) + IMWUT Nov 1 동시** | 저널 60%+, IMWUT 35–50% |

**다음 결정 포인트**:
1. Hub 팀에 anonymized trace dump 5–10 자동화 × 2–4주 요청 가능한가?
2. Method에 옵션 3 (sensor-noise-aware obligation) 박을 분석 capacity 있는가?
3. 1개월 vs 6개월 timeline 선호?

---

---

## 22. Self-correction 강화 — VCSC (Verifier-Coupled Self-Correction)

현재 paper의 C5 self-correction은 1문단 hero + §6.8 mutation diagnostic(optional)만 있어 sparse. 강화 layer 정리.

### 22.1 6 mechanism 후보

| # | 메커니즘 | 설명 |
|---|---|---|
| **M1 ★** | Typed Repair Operator (TRO) 카탈로그 | IR op × violation type 교차 → 15–25개 typed operator. 자유 retry 대신 typed operator + location hint + repair template 전달 |
| **M2 ★** | Minimal counterexample synthesis | Delta debugging 1-pass — 60-event 위반 trace를 3–5 event로 shrink. LLM 프롬프트 노이즈 감소 |
| M3 | Cumulative failure clustering | N회 같은 라벨 반복 실패 시 escalate (hint → 직접 template → 구체 idiom skeleton) |
| M4 | In-loop verifier (tight coupling) | LLM single generation call 내 inner loop revision. CoT-with-verifier 패턴 |
| M5 | Confidence-weighted feedback | L2 high-confidence, L3 lower. LLM이 신호 강도 인지 |
| **M6 ★** | Bounded retry budget | N_max attempts × B_max ms. remaining budget에 따라 feedback depth 적응 |

### 22.2 Codex 평가 (2026-05-15)

- **VCSC 단독 hero ❌**: Self-Refine·Reflexion 등 verifier-guided retry 선행 라인이 두꺼움. 6 mechanism 묶음은 익숙한 packaging.
- **유일한 novelty**: "small reactive IR이 verifier 실패를 finite repair space로 분류 가능" — 도메인 특화 instantiation. evidence로 받쳐야.
- **권장 sprint subset**: **M1 + M2 + M6**. M3은 cheap addition. M4·M5는 측정 못 하면 cut.
- **Hero 위치**: VCSC는 sub-system. "Decomposition + user-confirmed IR as contract"가 hero, VCSC는 contract를 exploit하는 메커니즘.
- **SenSys 확률 (M1+M2+M6 추가, hub 없음)**: 15–25%. 외부 타당성 갭(단일 디바이스·실 hub 없음)은 VCSC로 메꿔지지 않음.

### 22.3 정직한 한 문장 contribution

> **"작은 reactive IR이 verifier 실패를 finite repair space로 분류할 수 있게 만들어, ≤9B 로컬 모델이 bounded edge budget 안에서 DSL lowering을 복구할 수 있게 한다."**

### 22.4 M1 TRO 카탈로그 — 초기 15개

| TRO 라벨 | Detection (IR-FSM state + pattern) | Repair template |
|---|---|---|
| `MISSING_REARM` | `wait(rising)` armed→fired 후 cond false 거치지 않고 또 fire | "add `<var> = <sentinel>` in else branch of `if(cond)`" |
| `SPURIOUS_CALL_NOT_IN_IR` | IR vocab 밖 service emit | "remove call to `<target>`" |
| `EXTRA_FIRE_AFTER_BREAK` | exit state에서 추가 발화 | "add `break` after `call <X>`" |
| `EARLY_FIRE_BOUNDARY` | threshold 만족 전 발화 | "verify comparison direction `>=` vs `>`" |
| `MISSING_INIT_GUARD` | persistent var가 매 iter 덮어쓰기 | "wrap with `if (<var> == <sentinel>)`" |
| `WRONG_DELAY_UNIT` | delay arg 잘못된 단위 | "convert `<n>` to ms" |
| `DEAD_BRANCH` | 분기 안 도달 | "remove `<branch>`" |
| `BAD_QUANTIFIER` | all/any 잘못 | "swap `all` ↔ `any`" |
| `MISSING_DELAY_IN_CYCLE` | cycle 무한 폴링 | "insert `delay <ms>` in cycle body" |
| `WRONG_EDGE_TYPE` | rising↔falling↔level 혼동 | "change `edge:<X>` to `<Y>`" |
| `MISSING_BREAK_ON_COND` | exit cond 만족했는데 cycle 지속 | "add `break` inside cond block" |
| `EXTRA_INIT_RESET` | sentinel 잘못된 시점 reset | "remove premature reset" |
| `BAD_SELECTOR_SCOPE` | `(#Tag)` vs `all(#Tag #Cat)` 혼동 | "qualify selector with category" |
| `WRONG_TARGET_SERVICE` | 같은 카테고리 다른 method | "change `<X>` to `<Y>` based on IR `call`" |
| `MISSING_CRON_FIELD` | cron 5-field 부족 | "extend cron to 5 fields" |

### 22.5 3주 sprint 분할

| Phase | 작업 | 기간 |
|---|---|---|
| 1 | M1 TRO 카탈로그 정의 + IR-FSM 위반→TRO 매핑 | 5–7일 |
| 2 | M2 minimal counterexample (delta debug 1-pass) | 3–5일 |
| 3 | M6 bounded budget controller | 2–3일 |
| 4 | 평가 (ablation ladder + retry stats + cost) | 5–7일 |

### 22.6 평가 필수 (codex 명시)

**Must-have** — 빠지면 contribution claim 깨짐:
1. **Ablation ladder**: no-feedback → raw trace mismatch → IR feature label → +TRO → +minimal counterexample → +budget
2. **Retry success rate** + **retry count distribution** (mean + p50 + p95)
3. **End-to-end accuracy**: 9B direct vs 9B+decomposition vs 9B+VCSC vs GPT-4 direct
4. **Cost**: per-attempt latency, total budget consumed, verifier overhead
5. **Failure mode analysis**: 어디서 VCSC가 포기하는가? (wrong IR, ambiguous intent, capability mismatch, simulator gap, multi-device)

**Sink-the-claim omissions**: raw → TRO ablation 빠지면, edge cost 숫자 빠지면, end-to-end lift 안 보이면, failure 분석 없으면 → reviewer가 cherry-picking 의심.

### 22.7 결정 — Hub trace 확보 가정 시 SenSys 정공법

Hub trace 받아오는 시나리오로 가정 (5–20 hub × 4–12주 anonymized dump):

### 22.8 통합 Hero (Hub data 가정)

> **"User-confirmed temporal IR을 executable contract로 두어, sensor-noise-aware verification + verifier-guided SLLM repair를 실제 hub trace로 검증한 NL→reactive-DSL 합성 시스템"**

| Contribution | 무엇 | 데이터 활용 |
|---|---|---|
| **C1** Timeline IR | 9-op 고정 문법, reactive primitive 1급 | — |
| **C2** NL→IR→JoI decomposition | SLLM 부담 분해 | — |
| **C3** User-confirmed IR as spec | 행동 시나리오 walk-through (옵션) | — |
| **C4** Sensor-noise-aware IR-FSM coverage | tolerance 의무 (τ, ε, δ, 3-valued verdict) | τ·ε·δ를 **hub trace에서 추출** |
| **C5** VCSC self-correction | M1 TRO + M2 minimal CE + M6 budget | **실 fault 케이스로 ablation** |
| **Eval** | Sim + hub replay + lowering bug + cost | hub trace로 **sim fidelity gap 측정** |

### 22.9 확률 재평가 — Hub data 가정

| 구성 | SenSys 확률 |
|---|---|
| 기존 (verification + IR + sim only, no hub) | 25–35% |
| + 실 hub trace evaluation | 35–45% |
| + Sensor-noise-aware obligation (C4 강화) | 40–50% |
| **+ VCSC (M1+M2+M6)** | **45–55%** ★ |
| + 행동 시나리오 user study | 50–60% |

Hub trace + VCSC + noise-aware 묶음으로 SenSys main-track 가시권.

### 22.10 3주 sprint plan (Hub data 가정)

#### Week 1 — Hub data ingest + M1 TRO

- D1–2: Hub team으로부터 데이터 receipt + 파싱·정규화
- D3–4: 센서별 flap 통계 → τ, latency 분포 → ε, jitter → δ 추출
- D5–7: M1 TRO 카탈로그 15–25개 정의 + IR-FSM 위반→TRO 매핑

#### Week 2 — M2 + M6 + tolerance 통합

- D8–10: M2 minimal counterexample (delta debug 1-pass)
- D11–12: M6 bounded retry budget controller
- D13–14: IR-FSM 의무를 tolerance-aware로 확장 (binary → 3-valued)

#### Week 3 — 평가 + 작성

- D15–17: E1 generation accuracy ladder
- D18–19: E2 mutation testing + E3 VCSC ablation
- D20–21: E4 sim vs hub fidelity + E5 edge cost
- D22–25: 12쪽 draft

### 22.11 핵심 평가 표 (12쪽 안에 필수)

**Table 1 — Generation accuracy ladder (cat 4–9)**
9B direct / +CoT / +decomp / +VCSC partial / +VCSC full / GPT-4 direct

**Table 2 — VCSC ablation**
no-feedback / raw mismatch / IR feature label / +M1 TRO / +M2 minimal CE / +M6 budget — retry success rate, mean retries, p95 retries

**Table 3 — Sim vs Hub fidelity**
평균 timing drift, IR-FSM verdict 동일률, tolerance 적용 후 FP 감소

**Table 4 — Edge cost**
9B inference latency, IR-FSM monitor 오버헤드, M2 합성 시간, end-to-end p50/p95

**Table 5 — Sensor-noise-aware obligation 효과**
Binary 대비 FP rate, τ·ε·δ 추출 정확도

### 22.12 Hub 팀 요청 메시지 (template)

> "평가용으로 anonymized 이벤트 로그 한 번만 dump 부탁드립니다. 시스템에 살아 붙는 거 아니고, paper 측정 끝나면 끝입니다.
> 형식: JSONL, 한 줄당 `{ts_ms, hub_id(해시), automation_id, device_id(해시), device_category, service, method_type, args, result}`.
> 규모: 5–10개 자동화 × 2–4주. fault 케이스(센서 끊김, 지연 등)가 자연 발생한 구간 표시해주시면 더 좋습니다."

---

## Sources

- [SenSys 2027 CFP](https://sensys.acm.org/2027/cfp.html)
- [SenSys 2025 proceedings (DBLP)](https://dblp.org/db/conf/sensys/sensys2025.html)
- [SenSys 2026 accepted papers](https://sensys.acm.org/2026/main_program.html)
- [GPIoT (arXiv)](https://arxiv.org/abs/2503.00686)
- [TaskSense (ACM DL)](https://dl.acm.org/doi/10.1145/3715014.3722070)
- [Toward Sensor-In-the-Loop LLM Agent](https://dl.acm.org/doi/10.1145/3715014.3722082)
- [Sasha (arXiv)](https://arxiv.org/abs/2305.09802)
- [SAGE](https://arxiv.org/abs/2311.00772)
- [TARGE / HomeAssistant LLM Chatbot](https://arxiv.org/abs/2505.02802)
- [AutoIoT (IEEE IoT-J)](https://arxiv.org/abs/2411.10665)
- [SimuHome](https://arxiv.org/abs/2509.24282)
- [HomeBench (ACL 2025)](https://arxiv.org/abs/2505.19628)
- [Nandi — Automatic Trigger Generation for Rule-based Smart Homes (PLAS 2016)](https://cnandi.com/docs/plas16-cr.pdf)
- [Quirk et al. — Language to Code (ACL 2015)](https://aclanthology.org/P15-1085.pdf)
- [CASAS Smart Home Dataset](https://zenodo.org/records/15708568)
- [LLM Agents for IoT Applications](https://openreview.net/pdf?id=BikB3f8ByV)
