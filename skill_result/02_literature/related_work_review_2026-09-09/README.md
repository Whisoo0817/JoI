# VETS Related Work 검토: motivation의 겹침과 남는 검증 문제

2026-09-09. **현재 논문 내 위치: ① Introduction의 motivation을 정하기 위한 Related Work 대조.**
전체 흐름은 `문제 → NL/Timeline IR/확인/생성 개요 → IR 실행 의미 → Explorer → 평가 → 한계·관련연구`다. 여기서의 결정은 Introduction의 문제 문장, IR의 기여 설명, Explorer가 필요한 이유에 영향을 준다. Related Work의 최종 절 위치는 아직 정하지 않았다.

## 1. 판단

**“행동 명세를 위한 IR을 만든다”, “NL의 시간 관계를 명확하게 한다”, “사용자가 확인한다”, “LLM 출력에 검증을 붙인다”는 각각 기존 연구가 이미 다룬다.** 이들을 단독 motivation 또는 novelty로 쓰면 “이미 해결했잖아”라는 반박을 받는다. 기존 문헌을 “명세 없음/검증 없음”으로 분류한 OVLA의 일부 설명은 수정해야 한다.

이번 검토에서 방어 가능한 문제 후보는 다음이다.

> 사용자가 채택한 스마트홈 자동화의 시간·값 행동을 실행 가능한 기준으로 확정한 뒤,
> 별도로 생성된 플랫폼 구현이 그 행동을 허용된 모든 입력 이력에서 보존하는지 확인한다.

그러나 **이 문장 자체가 새로운 verification 원리는 아니다.** Translation validation과 synchronous compiler 검증은 source–implementation 보존을 이미 다뤘다. VETS의 실질 기여는 스마트홈의 입력·서비스 값·타이머와 JoI 구현을 같은 관측 계약에 연결하고, 어떤 축소·탐색 조건에서 그 관계를 인증할 수 있는지에 있어야 한다. ‘LLM이 생성했다’거나 ‘IoT에 적용했다’는 것만으로 충분한 기술적 차이를 입증하지 못한다. [formal 근거 F1–F5](formal_prior.md)

이것은 현 문헌에서 도출한 **차별성 제안**이다. 사용자와 최종 motivation을 확정한 것은 아니며, 문헌 전체의 ‘최초’를 확정한 결과도 아니다.

## 2. 자료 구성과 읽는 순서

| 자료 | 내용 |
| --- | --- |
| [자동화 IR·실행·최종 산출물 비교](automation_ir_execution_matrix.md) | TAP/자동화 12개 연구의 자체 IR·FSM, 직접/모델/변환 후 실행 구분, DSL·코드·검사 결과 분류; ThingML 신규 검토 |
| [통합 inventory](inventory.md) | OVLA Related Work 20개 인용 전부 + 다른 절/기존 corpus/최근·신규 논문 + 미확인 후보 |
| [formal 비교](formal_prior.md) | Murphy, TSL, AutoTap, translation validation, synchronous compiler, ARTEMIS, Req2LTL, NLForge |
| [Translation validation 정밀 분석](translation_validation_deep.md) | TACAS 1998 전문·SCOPES 2015와 상세 manuscript 구별, refinement 방법과 Explorer 비교 |
| [ARTEMIS 정밀 분석](artemis_deep.md) | proxy·balanced traces·의미 중복 제거, 평가 조건과 본체 기여 범위 |
| [authoring 비교](authoring_prior.md) | AwareAuto, CASPER, TAP-Debug, Trace2TAP, SENSATION |
| [생성·검사 비교](generation_prior.md) | ChatIoT, 두 AutoIoT, GPIoT, TaskSense, LACE, IoTGPT, Giudici, DS-IA, SimuHome, CodeT/Self-Debug |
| [safety/runtime 비교](safety_prior.md) | TAPInspector, TAPFixer, IoTSan, Soteria, iRuler, HAWatcher, AgentSpec, VIGIL |

원문 URL·절/페이지·판본·접근 수준은 각 카드에 기록했다. 전문을 확보해 방법 절을 읽은 자료와 공식 초록만 확인한 자료를 구분한다. 저자들이 제시한 보장을 이 검토에서 독립 재증명하거나 구현 재현한 것은 아니다. 기존 source 문서의 오류는 아래 §7에 명시하며 원본을 덮어쓰지 않는다.

## 3. 가장 직접적인 반박과 답할 수 있는 범위

| 논문 | 예상 반박 | 인정해야 할 선행 기여 | VETS에서 비교할 지점 |
| --- | --- | --- | --- |
| **AwareAuto** | “복잡한 행동을 temporal IR로 만들고 확인하는 건 이미 했잖아.” | event/state, duration, timer, sequence/branch와 사용자 수정 | 확인한 규칙의 의미와 최종 lowering 결과 사이에 어떤 실행 보존 검사를 하는가? [AP-01](authoring_prior.md) |
| **CASPER** | “NL을 명확히 하고 코드 생성·검사·승인까지 이미 한다.” | structured NL, clarification, HA 생성, entity/conflict/chain/goal 검사 | 검사 대상이 그 요청별 reference의 정확한 ACTION trace인가? 생성 후 검사 유무로 차별화하지 않음. [AP-02](authoring_prior.md) |
| **Req2LTL / OnionL (ASE 2025)** | “NL에 숨어 있는 temporal 정보를 IR로 드러내는 게 우리 연구다.” | temporal scope/relation IR, optional human inspection, deterministic LTL 변환 | 최종 산출물이 논리 명세인 연구와, 실행 기준→실제 생성 구현의 보존까지 다루는 연구를 구분. [F8](formal_prior.md) |
| **ARTEMIS (ICSE 2026)** | “사용자가 명세를 이해·검증하도록 구분되는 trace를 보여준다.” | structured NL/TL, distinguishing traces를 통한 semantic validation | 확정할 해석을 고르는 단계와 확정된 해석의 코드 구현 보존 단계를 구분. [F7](formal_prior.md) |
| **AutoTap / TAPFixer** | “사용자 temporal requirement를 형식화하고 검증·합성·수정한다.” | duration/timer, 사용자 속성, 모델 검사, 합성/repair | 선택한 속성을 만족하는 구현 집합과 선택된 실행명세의 timed ACTION을 보존하는 관계의 차이. [F3](formal_prior.md), [TAPFixer](safety_prior.md) |
| **Murphy + TSL** | “NL→temporal spec→reactive code에 이미 형식 보장이 있다.” | 시간·상태·cell/data flow, formal reactive controller synthesis | 합성 제어 관계의 보장과 LLM이 작성한 최종 JoI의 서비스 인자·시각을 포함하는 관측 보존의 차이. [F1–F2](formal_prior.md) |
| **Translation validation / synchronous compiler** | “IR 의미와 실제 생성 코드의 시간·값 보존도 이미 검증한다.” | source/target 공통 의미, refinement/equivalence, 생성 C의 값 보존 | 가장 강한 방법론 선행. 도메인 의미 연결과 관측 보존 abstraction/인증 의무의 구체성이 필요. [F4–F5](formal_prior.md) |
| **ChatIoT / LACE** | “요청대로 생성됐는지 이미 확인한다.” | LLM/NLI semantic checks; LACE에는 SMT/OPA도 있음 | NL 판정, policy 분석, executable-reference equivalence 각각의 관계를 구분. [generation](generation_prior.md) |
| **TAP-Debug / Trace2TAP** | “사용자 의도·실행 trace·후보 선택·formal reasoning도 이미 결합했다.” | 관측 trace/feedback에서 SAT 합성·repair, 후보 ranking/clustering와 예상 실행 | 관측 trace의 제한된 수정/유사성 계약과 선언 모델의 전 이력 관계. [AP-04–05](authoring_prior.md) |
| **VIGIL (2026)** | “NL 행동 명세, temporal dependency, 값 binding과 SMT verification까지 있다.” | finite tool trace에서 policy satisfaction, cross-call value binding | 현재 관측 실행/prefix의 정책 검사와 생성 프로그램의 모든 허용 미래 입력 이력 인증을 구분. [VIGIL](safety_prior.md) |

## 4. IR 특징은 어떻게 비교할 것인가

**후속 사용자 제공 비교 기준:** 실행 가능성, 입력 탐색의 포괄성, 오류 판정 기준을 구별한다.
Property model checking도 예상하지 못한 허용 입력을 탐색하고 TAP도 실행될 수 있다.
Timeline의 역할은 입력별 기준 ACTION을 계산하여 별도의 버그별 속성 없이 그 기준과의 추가·누락·시각·인자 차이를 검사 대상으로 만드는 것이다.
우리 검증은 무한 trace를 하나씩 출력하는 절차가 아니며, 내부 변수와 timer는 실행 규칙으로 전개된다.
정확한 인증 범위와 추가 알림 예는 [Flow 기록 §12](../../06_manuscript/flow_discussion_2026-09-09.md#12-사용자-제공-대화-반영-예상하지-못한-입력과-추가-행동의-구별)에 기록했다.

‘IR 있음/없음’이나 primitive 개수만 세면 다른 연구의 기여를 잘못 지운다. 다음 항목을 **표현 가능성 → 제공한 문법/의미 → 실제 검증 연결** 순서로 확인한다.

| 확인할 특징 | 이미 확인한 선행 사례 | VETS에서 설명할 역할 |
| --- | --- | --- |
| event/state, 지속, delay, sequence/branch | AutoTap, AwareAuto, Trace2TAP, SENSATION은 각기 해당 조각을 제공 | 어떤 시점에 평가하고 취소·재개하는지 명세와 구현에 같은 의미를 부여 |
| temporal scope와 논리 관계의 명시화 | OnionL, FRETish/ARTEMIS, TSL | NL 표면을 넘어 실행 기준을 확정하는 데 필요한 관계 |
| 과거 값 저장·후속 사용 | TSL cells, synchronous data-flow; VIGIL cross-call binding | sensor/query snapshot의 출처와 이후 ACTION 인자를 연결 |
| formal/executable semantics | TSL, timed/synchronous languages, AgentSpec 등 | 동일 초기 상태·입력 이력에서 기준 ACTION 계산; 결정론의 범위 명시 |
| 자동 설명·사용자 확인 | AwareAuto, CASPER, ARTEMIS 등 | 확정된 명세가 reference라는 조건. 사용자 이해 성공의 실증을 대신하지 않음 |
| 실제 구현에서 모델 추출 | Soteria, IoTSan, TAPInspector, translation validation | 생성 JoI의 독립 실행 의미와 frontend 대응 의무 |
| 구현의 시간·값 보존 | synchronous translation validation | 해당 원리를 JoI/service/input/deadline 관측에 구체화하는 의무 |

**현재 확인된 “VETS만의 단독 primitive”는 없다.** AwareAuto의 tie order나 snapshot lifetime이 미확인인 것은 이 연구가 그런 의미를 가질 수 없다는 증거가 아니다. 필요한 추가 조사 단위는 “저장값 지원?” 같은 넓은 질문보다 다음과 같아야 한다.

- `READ(x) → DELAY → ACTION(x)`의 x가 읽기 당시 값인지 실행 직전 값인지 문법/실행기가 어떻게 정하는가?
- sustain 도중 false 입력이 오면 timer가 취소되는가? 같은 시각에 input과 deadline이 오면 무엇이 먼저인가?
- 그 의미를 사용자용 표현에서 확인하고, 변환된 코드에서도 보존되는지 검사하는가?
- 검사가 value를 threshold class로 줄일 때 ACTION 인자로 흘러가는 원값도 보존하는가?

이는 선행연구가 반드시 실패한다는 질문이 아니다. 해당 연구의 문법·실행기·증명 또는 동일 태스크 이식으로 확인할 비교 항목이다. 현재 미확인 칸은 `미확인`으로 남긴다.

## 5. A/B가 논문에서 해야 할 역할

### A: 연속 5분 비어 있으면 끄기

0분부터 부재, 4분 재실, 4분30초 다시 부재라면 sustain 기준은 9분30초에 off, 잘못된 delay/current-state 구현은 5분에 off한다. 계속 비어 있는 입력에서는 둘 다 5분에 off하므로 차이가 가려진다. 자세한 전제는 [Flow 기록](../../06_manuscript/flow_discussion_2026-09-09.md)을 따른다.

AutoTap은 조건 유지시간과 false 시 timer reset을 명시한다. Trace2TAP/TAP-Debug에도 duration trigger가 있다. 따라서 A의 역할은 **“기존 IR는 이 행동을 표현하지 못한다”가 아니라 “이렇게 확정된 지속 의미를 구현이 보존해야 한다”**다. 알맞은 temporal property를 쓰면 기존 model checker가 이 오류를 찾을 가능성을 배제할 수 없다. [F3](formal_prior.md), [AP-04–05](authoring_prior.md)

### B: 지금 읽은 온도를 1분 후 알리기

처음 20도, 30초에 25도로 바뀌면 올바른 구현은 1분에 20도를, 지연 후 다시 읽는 구현은 25도를 알린다. ACTION의 종류와 시각만 같아도 인자가 다르다.

TSL의 cell과 synchronous translation validation은 저장값/현재값과 데이터 보존을 이미 다룬다. B의 역할은 **“값 흐름을 처음 표현한다”가 아니라 “우리 관찰과 입력 축소가 이 값의 출처·수명을 지워서는 안 된다”**다. [F2/F5](formal_prior.md)

두 예시는 실제 prior tool 실행 비교나 관측된 LLM 오류 통계가 아니다. A는 Introduction의 preservation 문제, B는 IR→Explorer의 data observation 의무를 설명하는 기존 배치를 유지한다.

## 6. Motivation 후보에 미치는 영향

| 출발점 | 가장 가까운 반박 | 판단 |
| --- | --- | --- |
| 1. 사용자는 코드를 보고 행동/선택지를 알기 어렵다 | AwareAuto, CASPER, SENSATION, TAP-Debug, ARTEMIS | 공통 배경으로 유효. 이 문제를 새로 발견했다거나 VETS가 이해/선택 정확성을 높였다고 주장하지 않음 |
| 2. 모호한 NL을 구체적 temporal behavior spec으로 바꿔야 한다 | Req2LTL, ARTEMIS, AutoTap, Murphy | 필요성 자체는 유효하지만 이것만으로 논문 문제를 닫으면 기존 formalization 연구와 매우 가까움 |
| **3. 행동 기준을 명시하고, 선택한 기준이 생성 구현에서도 보존되는지 확인해야 한다** | translation validation, reactive synthesis | **권고 후보.** 기존 specification/verification을 인정하면서 실제 smart-home timed ACTION 보존이라는 기술 작업으로 연결. 도메인별 의미·인증 방법의 기여가 뒤따라야 함 |

권고 문단 후보:

> 자연어 기반 스마트홈 자동화에서는 조건의 평가 시점, 지속 조건의 취소, 센서값을 읽는 시점에 따라 서로 다른 동작이 발생한다. 기존 연구는 이러한 요구를 구조화하거나 시간논리로 표현하고, 사용자 확인과 속성 검증을 지원해 왔다. 이 논문은 사용자가 채택한 행동을 실행 가능한 기준으로 정한 뒤, 별도로 생성된 플랫폼 코드가 그 기준을 보존하는 문제를 다룬다. VETS는 Timeline IR의 실행 의미로 입력 이력별 기대 ACTION을 계산하고, 지원 실행 모델에서 생성 코드가 같은 시각·대상·인자·횟수·명시 순서를 유지하는지 인증한다.

첫 문장은 A/B로 구체화한다. 두 번째 문장은 AwareAuto/Req2LTL/AutoTap 등으로 뒷받침한다. 세 번째 문장을 “그런 검증은 지금껏 없었다”로 확장하지 않는다. Method/Related Work에서 translation validation과의 관계를 직접 설명한다.

## 7. 구 OVLA 및 최근 기록에서 수정할 주장

이 표는 **새 원고에 재사용하지 않을 문장과 그 이유**다. 원본 기록의 역사적 맥락을 지우지는 않았다.

| 기존 문구/분류 | 문제 | 대체 기준 |
| --- | --- | --- |
| “T6 is empty across the field”, “None verifies user's positive intent” | 광범위한 부재 주장; 사용자 property/feedback/semantic validation을 지움 | 논문별 reference·판정 관계·입력 범위를 명시 |
| “기존 검증은 negative/fixed safety뿐” | TAPInspector liveness, TAPFixer/IoTSan 사용자 속성, Soteria functional properties 누락 | property satisfaction vs chosen-reference conformance |
| “자동 검사는 format/API/grounding에서 끝난다” | ChatIoT 요청 검사, CASPER conflict/chain/goal, AutoIoT Maude, LACE SMT/OPA 누락 | 어떤 검사가 deterministic/formal/LLM인지 단계별 표시 |
| “코드 생성 분야는 oracle가 원래 주어진다” | CodeT는 test도 생성, Self-Debug는 unit-test 없는 경우도 다룸 | generated/benchmark/user-confirmed reference의 출처를 구별 |
| “IR는 다 하나의 해석이 정해진 뒤 등장한다” | ARTEMIS는 해석 후보를 formal spec/trace로 구분, Trace2TAP도 후보 탐색/선택 지원 | 명세 후보 탐색 자체는 선행으로 인정하고 현재 VETS 기여에서 제외 |
| “후보의 행동 차이를 보여주면 user-study 반박에 답이 된다” | 보여준다는 사실은 올바른 이해·선택을 입증하지 못함 | 알고리즘 witness 보장과 사용성 evidence 분리 |
| “IR·deterministic semantics·실행 가능성 자체가 차별점” | TSL/synchronous languages/translation validation 등 선행 | domain reference와 generated implementation의 구체 계약/인증 방식 |
| “이전 jar15.pdf는 JAR 2015 논문” | 저자 공개 상세 manuscript의 정식 journal 출판 확인 못함 | publication 확정 전 author manuscript로 기록 |
| “IoTSan MobiSys 2018” | 서지 오류 | CoNEXT 2018 |
| “현재 검증은 bounded trace filter / 작은 on-device model이 전제” | 이전 OVLA와 현 VETS 혼동 | 현 [검증 계약](../../../explorer/docs/model/VERIFICATION_CONTRACT.md) 사용 |

## 8. Related Work 본문 구성안

문헌 수는 많지만 본문은 다음 네 묶음으로 압축한다. 각 묶음 마지막에서 **그 연구가 검증하는 관계**를 밝히면 반복적인 “하지만 우리와 다르다” 문장이 줄어든다.

1. **행동 명세의 작성과 확인.** AwareAuto/CASPER, Req2LTL/ARTEMIS를 중심으로 명시화·clarification·temporal IR의 선행을 인정. TAP-Debug/Trace2TAP은 실행 예와 피드백으로 요구를 구체화하는 사례로 연결. VETS의 사용자 확인은 검증 reference를 확정하는 조건임을 명시.
2. **스마트홈 자동화의 생성과 검증.** ChatIoT/두 AutoIoT, AutoTap/TAPInspector/TAPFixer를 중심으로 LLM 판단과 formal property checking을 구분. GPIoT/TaskSense/IoTGPT는 생성·실행 피드백 배경으로 짧게 묶음. 기능 요구·시간·동시성의 선행을 인정.
3. **Reactive synthesis와 구현 보존.** Murphy/TSL, Translation Validation 및 synchronous compiler를 핵심 비교로 배치. 새로운 temporal formalism을 주장하지 않고, VETS가 특정 JoI candidate의 concrete timed ACTION 관계를 검증하는 데 필요한 modeling/abstraction을 설명.
4. **실행 중 검사와 simulation.** AgentSpec/VIGIL/HAWatcher 및 SimuHome. runtime trajectory의 policy satisfaction·정상성·episode goal 검사와 프로그램의 전 허용 이력 계약을 구분. LACE는 semantic/policy checks의 보조 인용. 분량에 따라 2번과 합칠 수 있음.

Soteria/IoTSan/iRuler/IoTGuard는 2/4번의 기초 인용 후보이고, timed automata/synchronous semantics/SPIN은 해당 방법의 기초 인용이다. 하나의 related-work 표에 모든 문헌을 같은 깊이로 나열할 필요는 없다.

## 9. 아직 남는 주장 입증 의무와 다음 논의

**현재 source로 말할 수 있는 것:** 각 논문의 제시 workflow 및 계약과 현 VETS 계약의 차이. A/B가 보여주는 시간·값 관찰의 필요. 넓은 motivation 중복과 구 OVLA 과잉분류의 정정.

**아직 말할 수 없는 것:** 기존 도구로 A/B를 검증할 수 없음, VETS가 더 expressive/efficient/general, 전체 분야 최초, 사용자 확인 성공, 모든 generated candidate의 판정 완료. 논문을 읽고 계약을 비교한 것과 구현 비교 실험은 다르다.

다음 논의는 **① Introduction의 중심 질문을 6절 후보 3으로 잡을지**다. 그 선택을 하면 **③ Timeline IR**은 “새로운 temporal 표현력”보다 “확정·생성·실행 기준을 연결하는 명세”로, **④ Explorer**는 “그 의미를 보존하는 검사와 인증 조건”으로 설명한다.

그 다음 방법/평가에 남는 구체 질문은 다음과 같다. 지금 실험을 시작하라는 지시가 아니다.

- **IR의 설계 근거:** 기존 AwareAuto/OnionL/FRETish/TSL 표현을 썼을 때 time/value ACTION reference를 얻기 위해 무엇을 추가로 고정해야 하는지, 작은 동일 태스크 encoding으로 보여줄 수 있는가?
- **Explorer의 기술 근거:** 정확한 ACTION 시각·원값 인자·중복·순서를 관찰할 때 어떤 입력/상태 축소가 sound하며 언제 거절/미완료해야 하는가? 이는 기존 property-specific abstraction을 부정하는 것이 아니라 우리의 relational observation에 맞는 의무다.
- **평가의 역할:** 정상 trace/최종 상태 확인으로는 가려지는 A/B류 차이를 검사하는지, 지원 범위·비용·미인증 비율이 어떠한지 보여줘야 한다. ‘기존 연구보다 낫다’는 비교는 동일한 입력 모델·검사 목표를 맞춘 후에만 가능하다.
- **compiler 대안:** 왜 검증된 결정론적 compiler 대신 별도 LLM lowering 결과를 검증하는 설정을 유지하는지 설명해야 한다. 사용자 결정대로 compiler는 future work이며, 문헌 비교가 그 대안을 없애주지는 않는다.

증명 범위는 고정된 binding/catalog/start/input model과 알려진 실행기, 지원 검사 및 H 없는 인증 완료 조건에 한정한다. 동등성은 NL 해석 정답이나 물리 안전성을 뜻하지 않는다. Exact equality가 사용자가 허용하는 여러 행동을 과도하게 좁히는 경우에는 property satisfaction/refinement가 더 적합할 수 있다. 또한 두 프로그램의 product에서 mismatch를 속성으로 만들 수 있으므로, **property checking은 동등성 검증을 원리적으로 할 수 없다는 주장은 사용하지 않는다.**
