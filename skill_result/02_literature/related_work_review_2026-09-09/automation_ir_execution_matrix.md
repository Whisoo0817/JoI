# TAP·자동화의 자체 IR / FSM 비교: 실행 가능성과 최종 산출물

2026-09-09. 사용자 요청에 따른 집중 문헌 정리. **Introduction의 Timeline 선택 이유와 Related Work의 직접 비교**에 사용한다.
기존 corpus의 원문·카드를 재검토하고 ThingML을 추가했다. 체계적 전수 검색이나 도구 재현 실험은 아니다.
‘논문에 확인되지 않음’은 ‘원리적으로 불가능’과 다르다.

## 1. 판정 기준

- **직접 규칙 실행:** grounding된 표현을 해당 automation manager/runtime가 해석하여 동작하도록 제시한다.
- **모델 실행:** 정의된 상태 전이 또는 규칙 실행 절차로 행동을 전개·재생·탐색한다. 실제 기기 배포와 다르며 비결정적 모델일 수도 있다.
- **변환 후 실행:** 해당 표현을 다른 실행 표현/코드로 변환해 실행하는 경로를 제시한다. 독립 IR interpreter의 존재는 별도 확인한다.
- **미확인:** 읽은 원문에 해당 표현을 독립 실행하는 절차가 확인되지 않는다. 문법·의도 설명 자체를 부정하지 않는다.

‘최종 DSL’은 언어 이름과 파일 확장자만으로 판정하지 않는다. TAP 규칙, HA automation 설정, 자체 JSON 규칙도
도메인 실행 언어/설정에 해당할 수 있다. DSL과 일반 코드, 분석 전용 언어를 분리하여 실제 산출물을 기재한다.
Promela/Maude는 실행 가능한 언어이지만 아래 연구에서 쓰는 **검증 모델**이 곧 배포용 자동화인 것은 아니다.

## 2. 자연어·사용자 행동에서 자동화를 작성하는 연구

| 연구 | 표현 및 pipeline 위치 | IR 자체 실행 여부 | 최종 산출물 / DSL 목표 | 검사와 비교 기준 |
|---|---|---|---|---|
| **AwareAuto**, arXiv 2024 | NL 규칙 → grounded TA-pair JSON. event/state mode, state(duration), action sequence와 timer, 분기 분해 | **직접 규칙 실행 경로:** grounded tuple을 automation manager에 전달. 독립 formal reference interpreter는 미확인 | **자동화 규칙이 목표.** TA-pair JSON이 실행 측에 전달되며, 별도 JoI 같은 후단 DSL 생성은 확인되지 않음 | 의도·환경 grounding/실행 가능성. reference–별도 code의 timed ACTION 보존 검사는 확인되지 않음 |
| **ChatIoT**, IMWUT 2024 | NL → ChatIoT-TAP → runtime TAP. trigger/condition/action 및 Boolean 조합·action assignment | **변환 후 실행.** ChatIoT-TAP 독립 실행기는 미확인 | **예:** Home Assistant가 실행하는 자동화 형식으로 변환·배포 | LLM evaluator의 요청/context 적합성 점검. 별도 formal reference 실행과의 동등 인증은 제시하지 않음 |
| **CASPER**, Behaviour & Information Technology 2026 | 대화 → Event–Condition(s)–Action(s)의 structured NL → Automation Generator → HA 자동화 | **변환 후 실행.** structured NL 독립 실행 의미/실행기는 미확인 | **예:** Home Assistant 자동화 생성·승인·배포 | entity 적합성, conflict, activation chain, goal consistency. 검사 없음으로 분류하지 않음 |
| **Trace2TAP**, IMWUT 2020 | 센서·수동 행동 trace → symbolic TAP template → concrete TAP 후보 | **모델 실행 확인:** `executeTrace`로 규칙을 입력 trace에 적용 | **예, TAP 프로그램 합성.** 별도 범용 순차 DSL lowering 연구는 아님 | 관측 trace의 action episode 설명, SAT 합성·후보 분류. 전 입력 reference–code 동등성 아님 |
| **TAP-Debug**, IMWUT 2022 | 기존 TAP + 잘못되거나 누락된 행동 피드백 → symbolic patch → 수정 TAP | **모델 실행 확인:** 기록 이력에 수정 규칙을 재실행·기호 평가 | **예, TAP 수정 프로그램/patch.** NL에서 새로운 후단 DSL을 만드는 흐름은 아님 | 사용자 피드백을 만족하는 수정안 합성·ranking 및 counterfactual history |
| **AutoIoT**, Cheng et al., arXiv 2024 | device/rule JSON → 제한된 Python modeling calls → Maude rewriting model; 검출 후 규칙 수정 | **Maude 모델 실행 확인.** JSON 규칙 자체와 Maude 분석 모델은 구별 | **코드 목표도 있음:** Mi Home에 수동 등록할 NL 규칙 또는 `python-miio` Python 스크립트. 별도 target DSL은 아님 | 4종 conflict의 도달 가능성. 생성 Python과 Maude 모델의 관측 동등 검사는 확인되지 않음 |

행별 원문과 상세 근거는 §5의 같은 이름 카드를 따른다. AwareAuto는 NL 단계와 grounded JSON 단계를 하나로 뭉치지 않는다.

## 3. 상태 전이 모델로 분석·합성하는 연구

| 연구 | IR / 모델의 위치와 형태 | 실행 가능 여부 | 최종 DSL / 산출물 | 의미 있는 역할 차이 |
|---|---|---|---|---|
| **AutoTap**, ICSE 2019 | device + TAP의 transition system, timer; LTL 위반 실행의 Büchi automaton | **모델 실행 가능.** 시간 진행·timer reset 전이 정의. LTL 자체가 interpreter는 아님 | **예, TAP 규칙 합성·수정.** automaton 자체를 기기에 배포하는 방식은 아님 | 속성 만족을 위해 모델의 bad execution을 제거할 TAP를 찾음 |
| **TAPInspector**, TIFS 2022 | 앱 → TAP 추출 → concurrency/latency/physical interaction을 포함한 hybrid FSM → NuSMV | **모델 실행 가능.** 상태 전이 탐색과 반례 생성; 실제 기기 실행용 IR는 아님 | **아니오:** safety/liveness 위반과 반례 | 생성 전에 의도를 고정하는 IR보다 기존 앱을 분석하는 모델 |
| **TAPFixer**, USENIX Security 2024 | HA profile/rule → property-specific finite automaton, latency·physical abstraction → nuXmv | **모델 실행 가능.** 반례와 추상화/정제 기반 탐색 | **규칙 문법 patch까지.** 플랫폼 프로그램 수정은 수작업 | LTL correctness 위반을 제거하는 repair; target code까지 자동 변환·보존하는 의무와 구별 |
| **Soteria**, USENIX ATC 2018 | 앱 source → 자체 component IR(permissions, events/actions, call graph) → state model → NuSMV | **후단 state model에서 가능.** 처음 추출한 component IR 자체의 독립 실행기는 미확인 | **아니오:** property 검사 결과·반례 | IR와 FSM이 같은 한 단계가 아님. 실제 코드를 읽고 모델을 추출함 |
| **IoTSan**, CoNEXT 2018 | Groovy event handlers/configuration → Promela system model → Spin | **모델 실행 가능.** Promela의 전이/실행 탐색 | **아니오:** safety 검사·반례 및 원인 분석. Promela는 검증용 출력 | 배포 코드 생성보다 기존 앱 조합의 분석. 논문의 BITSTATE 경로는 approximate |

FSM이 있다는 사실은 그 자체로 unique reference behavior나 전 입력 인증을 뜻하지 않는다.
입력, 비결정성, 관측 대상, 추상화 및 탐색 완료 조건을 각각 비교해야 한다.

## 4. FSM을 생성용 행동 표현으로 쓰는 직접 인접 연구

**ThingML: A Language and Code Generation Framework for Heterogeneous Targets**, MODELS 2016.

| 항목 | 확인한 내용 |
|---|---|
| 표현 | 자체 textual DSL; component, message/port, statechart, imperative action language, configuration |
| 위치 | 개발자가 작성한 행동 모델 → 코드 생성기 → 배포 가능한 플랫폼 코드 |
| 실행 | **코드 생성 후 실행이 확인된 경로.** 원문에서 독립 모델 interpreter를 확인하지 않았으므로 ‘IR를 그대로 직접 실행’이라고 표시하지 않음 |
| 최종 목표 | C/C++, Java, JavaScript 코드. DSL은 중간/작성 언어이며 최종 산출물은 일반 프로그램 코드 |
| 도메인 | IoT·분산 reactive systems; home/building automation, Safe@Home 사례도 포함 |
| VETS에 대한 함의 | FSM/statechart는 단지 검증 모델만이 아니라 행동 작성과 코드 생성에도 쓰인다. ‘스마트홈 + 상태 있는 자체 언어 + 실행 코드’라는 넓은 조합의 최초성은 주장할 수 없음 |

우리가 비교할 표현상의 후보 차이는, 사용자가 직접 펼쳐야 할 제어 상태·전이 대신 반복·대기·지속·상태 갱신을
지원 도메인 연산과 structured control flow로 표현하는지다. 그러나 statechart도 계층 구조·변수·action을 제공하므로
‘FSM은 모두 평면이고 Timeline만 구조화됨’이라고 쓰지 않는다. 실제 문법 매핑과 생성 평가가 필요하다.

기존 검토의 **TSL(CAV 2019)**도 논리 명세 → Control Flow Model → Haskell FRP module의 코드 생성 경로를 갖는다.
순수 TAP 목록 밖이지만 시간·상태·control-flow 표현과 코드 생성의 인접 비교로 유지한다.
[기존 formal 카드 F2](formal_prior.md#f2-finkbeiner-et-al--temporal-stream-logic-synthesis-beyond-the-bools).

## 5. 원문 근거 카드 / 접근 수준

### AwareAuto

- [원문 §§4.2–4.4](https://arxiv.org/html/2408.12687v1), 특히 §4.3.1 TA-pair; §4.3.2 JSON grounding; §4.4 Fig.8 실행 manager 전달.
- trigger quadruple `target-interface-condition-mode`, action triple `target-interface-parameter`.
- `state(10mins)`와 `timer-wait-10mins` 및 action 순서가 명시되어 있다. 따라서 시간·순서·실행 규칙이 없다고 쓰면 안 된다.
- 직접 실행 판정은 grounded rules를 automation manager로 보내 실행하는 기술에 근거한다. 독립 formal reference semantics와 의미 보존 증명을 확인했다는 뜻은 아니다.
- [기존 카드 AP-01](authoring_prior.md#ap-01--awareauto). 검토본은 arXiv v1이며 placeholder conference header를 venue로 쓰지 않는다.

### ChatIoT

- [저자 원문](https://www.emnets.cn/zh/publication/ubicomp-24-chatiot/chatiot.pdf), [DOI](https://doi.org/10.1145/3678585).
- 로컬 기존 원문 `etc/related_works/ChatIoT.pdf`의 변환본 `/tmp/vets-related-20260909/ChatIoT.txt`, §3.1.2, Fig.2–3 재확인.
- 출력 ChatIoT-TAP를 runtime 형식으로 변환한 뒤 HA에 배포한다고 명시. 자기 TAP의 독립 interpreter는 확인되지 않음.
- 이번 web PDF 직접 open은 실패했고 저자 검색 결과와 로컬 전문으로 보완했다. [기존 카드](generation_prior.md#chatiot-imwut-2024).

### CASPER

- [출판사 원문](https://doi.org/10.1080/0144929X.2026.2679590), 2026-05-28 online.
- §5.1 대화 명세화·Automation Generator·HA 배포, §§5.2–5.4 관계/goal 분석. [기존 카드 AP-02](authoring_prior.md#ap-02--casper-journal).
- 이번 publisher 직접 open은 실패했으나 publisher 검색 캐시와 기존 원문 검토를 사용했다. 미확인 파일 포맷을 YAML이라고 단정하지 않는다.
- structured NL 단계가 독립 reference 실행기로 해석된다는 근거는 확인되지 않음.

### Trace2TAP

- [저자 원문](https://hewj.info/papers/trace2tap.pdf), §§5.2.2–5.2.4, Algorithms 1–2.
- `executeTrace`는 initial state에서 external event를 적용하고 triggered rule의 action으로 상태를 갱신한다. symbolic/concrete 규칙 모두 취급한다.
- `state-duration` trigger가 있으며 정해진 시간 후보를 사용한다. 과거 trace에서 실행 결과를 계산하므로 ‘실행 불가능한 IR’ 분류는 틀림.
- [기존 카드 AP-05](authoring_prior.md#ap-05--trace2tap).

### TAP-Debug

- [저자 원문](https://www.blaseur.com/papers/imwut22-debuggingtap.pdf), §§3–4, 특히 symbolic patch·recorded trace·solver·ranking.
- IMWUT 2022와 UbiComp 2023 발표 연도를 구별한다. 출력은 수정 TAP이며 under/over-automation 피드백에 대한 합성이다.
- [기존 카드 AP-04](authoring_prior.md#ap-04--tap-debug--helping-users-debug-trigger-action-programs).

### AutoIoT (Cheng et al.)

- [원문 §§IV-D, V-C](https://arxiv.org/html/2411.10665v1).
- §IV-D.1: LLM이 `model_device`, `model_state_transition`, `define_initial_state` Python calls를 생성하고 adapter가 Maude로 변환.
- §IV-D.2: Maude rewrite/search로 reachable conflict states를 찾는다. action은 모델의 상태 전이에 내포된다.
- **이번 추가 확인:** §V-C는 NL 규칙 수동 등록과 `python-miio` Python script의 두 출력 및 Raspberry Pi 실행을 명시한다.
  따라서 ‘formal model만 만들고 실행 자동화 코드는 없다’고 쓰지 않는다. 다만 Maude–Python의 translation validation은 확인되지 않음.
- [기존 카드](generation_prior.md#autoiot-cheng-et-al-arxiv-241110665v1-2024). MobiCom 2025 AutoIOT와 다른 논문이다.

### AutoTap

- [저자 원문](https://hewj.info/papers/autotap.pdf), §§II-B, IV–V, Fig.4–7.
- transition system에 timer를 넣고 property 위반 Büchi automaton을 만든 뒤 valid TAP 변경을 찾는다.
- §V-A의 연속 지속 timer는 조건 false 시 reset된다. property 입력과 operational system model을 분리하여 표기한다.
- [기존 formal 카드 F3](formal_prior.md#f3-zhang-et-al--autotap).

### TAPInspector

- [원문](https://arxiv.org/pdf/2102.01468v2), §§III–IV; [정식 출판 DOI](https://doi.org/10.1109/TIFS.2022.3214084).
- 앱 추출 → rule model → hybrid FSM, time/latency와 concurrency, NuSMV property checking.
- 모델이 실행을 표현한다는 점은 확인. 모델을 실제 기기 제어 코드로 배포하는 경로는 해당 연구의 목표가 아님.
- [기존 카드](safety_prior.md#tapinspector--tifs-2022).

### TAPFixer

- [공식 원문](https://www.usenix.org/system/files/usenixsecurity24-yu-yinbo.pdf), §§4–5.
- **§5.4:** rule-syntax patches 생성까지만 수행하며 HA app program repair는 manual work로 남긴다고 명시한다.
- 최종 산출물을 자동 배포 가능한 플랫폼 코드로 표시하면 안 된다. [기존 카드](safety_prior.md#tapfixer--usenix-security-2024).

### Soteria

- [공식 원문](https://www.usenix.org/system/files/conference/atc18/atc18-celik.pdf), §§4.1–4.4, Fig.3–5.
- §4.1의 component IR는 permissions, events/actions, call graph. §4.2에서 state model을 추출하고 NuSMV로 검사.
- timer event/scheduled handler도 추출한다. IR와 후단 상태 모델을 하나의 직접 실행 IR로 오인하지 않는다.
- [기존 카드](safety_prior.md#soteria--usenix-atc-2018).

### IoTSan

- [저자 원문](https://arxiv.org/pdf/1810.09551), §§4,6–8.
- Groovy handlers → Promela, configuration과 합쳐 system model → Spin. 검증용 프로그램 생성과 배포용 프로그램 생성을 구분한다.
- [기존 카드](safety_prior.md#iotsan--conext-2018).

### ThingML — 신규 카드

- Nicolas Harrand, Franck Fleurey, Brice Morin, Knut Eilif Husa. *ThingML: A Language and Code Generation Framework for Heterogeneous Targets*. MODELS 2016.
- [원문 PDF](https://www.cs.toronto.edu/~chechik/courses18/csc2125/paper79.pdf), [DOI](https://doi.org/10.1145/2976767.2976812), [프로젝트](https://github.com/TelluIoT/ThingML).
- 원문 §§1–3, §5.1 및 project 문서 확인. §2.3의 component/state-machine/action language; §3 code-generation extension points; §5.1 Safe@Home.
- target은 C/C++, Java, JavaScript. state-machine 구현, message queues, scheduling/dispatch, initialization까지 코드 생성기를 구성한다.
- closed surface와 비교할 때 platform code embedding도 허용함을 고려한다. 모든 표현이 Timeline과 동일한 제한을 갖는다고 볼 수 없다.
- OpenCite DOI lookup으로 제목/저자/2016/DOI를 교차 확인했다. provider의 `JournalArticle` 분류 대신 원문과 proceedings title에 따라 MODELS conference로 기록했다.
- 표현·코드 생성 선행으로 관련성 높음. 독립 reference interpreter 및 생성된 각 구현의 timed ACTION 동등 validator는 이번 원문에서 확인하지 못함.

## 6. 이번 비교가 Introduction에 주는 결론

1. **자체 IR, FSM, 실행 가능한 규칙, 최종 코드 생성은 모두 선행이 있다.** LTL과의 비교만으로 Timeline의 선택 이유를 완성할 수 없다.
2. **생성 표면 비교:** AwareAuto/ChatIoT/CASPER의 규칙 구조, ThingML의 statechart/action 구조와 Timeline의 시간·상태 연산 및 순차/반복 블록을 비교한다.
3. **실행 의미 비교:** Trace2TAP의 rule replay, AutoTap의 timed transition system, ThingML의 행동/코드 생성 의미를 인정하고, state scope·timer lifetime·관측 계약을 구체적으로 조사한다.
4. **검증 역할 비교:** 코드에서 추출한 분석 모델인지, property를 만족할 규칙을 찾는 모델인지, 생성 전 확정한 행동 기준과 실제 생성 코드의 보존을 검사하는지 구별한다.

현재 중심 문장 후보:

> Timeline은 반복 자동화의 시간·상태 관계를 지원 연산과 구조화된 제어 흐름으로 명시하고,
> 그 실행 의미를 DSL 생성 지침과 생성 코드의 timed ACTION 보존 기준에 공통으로 사용한다.

이 표는 위 계약의 설계 차이를 정리한다. 기존 표현이 특정 시나리오를 표현할 수 없다는 증명,
Timeline의 생성 정확도 우위, 현행 모델 밖 모든 스마트홈 동작에 대한 보장을 제공하지 않는다.

우선 정밀 비교 순서: **AwareAuto → ThingML → AutoTap/Trace2TAP → AutoIoT**.
각각 복합 자동화 표현, statechart 기반 구현 생성, 실행 모델과 합성, LLM 생성+형식 검사의 가까운 선행이다.
새 구현은 이번 작업에서 시작하지 않았다.
