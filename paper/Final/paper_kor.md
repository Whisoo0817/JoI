# OVLA: On-device Verification of LLM-Generated IoT Automations via Timeline IR

> 초안 (한글 본문 + 핵심 용어 영어). flow = `paper_flow_plan.md`(+REVISIONS), locks = `outline2.md`. Figure/Table은 존재 가정(F1~F8, T1~T3). F2=idiom-multiplicity(§3 money figure).

---

## Abstract

IoT 환경은 점점 더 LLM을 사용해 자연어(NL) 요청을 실행 가능한 reactive 자동화로 변환한다. 그러나 이렇게 생성된 자동화를 edge device에 곧바로 배포하는 것은 위험하다. reactive 자동화는 시간적으로 복잡하며(지속 조건, 타이머, 반복, 다단계 상태), 생성된 코드가 시스템이 사용자에게 보여 준 동작과 silently 어긋난 채 배포될 수 있기 때문이다. 기존 검증은 사람의 코드 검사, 오프라인 전문가, 또는 무거운 cloud LLM 재검사에 의존하며, 이는 edge의 프라이버시와 지연 제약에 맞지 않는다. 게다가 검증을 LLM judge에 맡기면 게이트 자체가 불안정하다.

우리는 OVLA를 제안한다. OVLA는 LLM을 *생성*(NL→Timeline IR 제안, 그리고 IR→JoI lowering)에 한정하고, 배포 게이트를 결정론적이고 LLM-free로 만든다. 즉 IR을 평문으로 보여 주는 결정론 Rendering을 사용자가 승인하고, 생성된 코드를 그 승인된 IR에 대해 bounded trace-equivalence로 검사한다. OVLA는 IR로부터 FSM과 boundary event를 자동 합성하고, 두 시뮬레이터로 코드와 IR을 함께 실행해 동작 차이를 검출하며, counterexample로 자동 repair를 유도한다. 게이트가 거부할 때는 fail-closed로 배포를 막는다.

≤9B 4-bit 로컬 모델과 382개 자동화로 평가한 결과, OVLA는 게이트 없이는 표시된 IR과 silently 어긋난 채 배포되던 9.2%를 0으로 줄였고(11건 repair, 24건 reject), 주입된 시간적 결함의 99.3%를 검출했으며, 합성 시나리오가 목표 boundary case의 97.4%를 exercise했다. 이 모든 검증은 루프에 LLM 호출이 전혀 없이 Mac Mini급 edge device에서 동작한다.

---

## 1 서론 (Introduction)

IoT 자동화는 빠르게 LLM 기반 코드 생성으로 옮겨 가고 있다. 사용자가 자연어로 원하는 동작을 말하면, LLM이 이를 플랫폼이 실행할 수 있는 reactive 규칙으로 바꾼다. 그러나 이 워크플로의 마지막 단계, 즉 *생성된 코드를 배포해도 되는가*를 판단하는 단계는 여전히 비어 있다.

**대상 artifact의 구분.** 이 빈자리가 어려운 이유는 우리가 다루는 코드의 성격에 있다. 기존의 많은 연구는 사용자 의도를 **flat trigger-action 규칙**이나 **정적 access policy**로 표현했다. 이런 artifact는 무상태이고 순간적이다. 하나의 trigger가 한 시점에 하나의 action을 발화하며, 정확성은 시점별로 점검할 수 있다. 대중 플랫폼도 대체로 이 수준에 머문다. IFTTT는 단일 trigger에서 단일 action으로 이어지며 지속 상태가 없다. SmartThings의 Routines는 AND/OR 조건과 "stays for X", delay까지 지원하지만, loop나 지속 변수, 중첩 조건은 개발자용 Rules-API JSON으로만 표현된다. Home Assistant는 `repeat`/`while`/`for:` duration/템플릿으로 reactive-temporal 자동화를 지원하지만, 그 GUI 에디터는 코드 생성이 아니라 스키마 폼이다. 사용자가 entity와 상태, 값, duration을 일일이 선택해 YAML로 직렬화하며, loop나 지속 변수, 중첩 reactive 로직은 YAML과 Jinja2 템플릿으로 직접 내려가야 한다. 이는 비전문가에게 사실상의 벽이다.

우리가 다루는 대상은 이보다 한 단계 위, **reactive-temporal 자동화**다. 여기에는 지속 register, "N분 이상 지속되면"과 같은 sustained condition, 주기 반복(cycle), 타이머, 다단계 상태 전이가 들어간다. 이러한 표현력은 두 가지 결과를 낳는다. 첫째, 동작 공간이 시간 축으로 펼쳐지므로 *검증이 어렵다*. 둘째, 같은 이유로 LLM이 생성한 *코드가 미묘하게 틀리기 쉽다*.

**구체적 예시(이 논문의 running example).** 한 사용자가 "회의실에 사람이 10분 이상 감지되지 않으면 모든 조명을 끈다"를 요청한다고 하자. 의도된 동작은 presence-false가 *지속*된 시간이 10분에 도달했을 때 소등하는 것이다. lowering 과정에서 LLM은 지속 시간을 600초가 아니라 60초로 쓰거나(1분), 매 polling마다 타이머를 재설정해 사실상 즉시 소등하거나, 사람이 잠깐 사라졌다 나타나도 타이머를 리셋하지 못하는 코드를 만들 수 있다. 이 코드는 syntactically 정상이고, 평상시(사람이 계속 있는 시간)에는 아무 행동도 하지 않아 정상으로 보인다. 시스템은 사용자에게 "10분 지속 시 소등"이라고 표시했지만, 배포된 코드는 그와 다르게 동작한다. 이것이 우리가 제거하려는 실패 모드, 즉 **배포된 코드가 시스템이 표시한 IR과 silently 어긋나는 것**이다.

**왜 LLM judge로는 안 되는가.** 가장 뻔한 대안은 또 다른 LLM에게 "이 코드가 의도대로인가"를 묻는 것이다. 그러나 LLM judge는 배포 게이트로서 불안정하다. 배포 결정은 binary다. 동작이 완전히 같은 두 프로그램은 같은 deploy/reject 판정을 받아야 한다. 그런데 idiom만 바꾼 행동-동일 프로그램에 대해 LLM judge의 판정은 temp=0에서도 흔들린다(§3). 더 큰 모델을 써도 흔들림이 남고, 무엇보다 cloud 모델은 edge의 프라이버시와 지연 제약에 맞지 않는다. 게이트가 코드의 표면 form을 따라 판정이 바뀐다면, 그것은 배포 게이트의 자격이 없다.

**OVLA.** 우리는 OVLA를 제안한다. OVLA의 한 가지 설계 결정은 LLM을 *생성*에만 쓰는 것이다. LLM은 NL로부터 후보 Timeline IR을 제안하고, 승인된 IR을 JoI 코드로 lowering한다. 두 단계 모두 LLM이다. 그러나 배포 게이트는 결정론적이고 LLM 호출이 없다. 게이트는 두 부분으로 이루어진다. (1) IR을 평문으로 보여 주는 결정론 Rendering을 사용자가 승인하고, (2) 생성된 코드를 그 승인된 IR에 대해 bounded trace-equivalence로 검사한다. lowering이 LLM 단계이기 때문에 *바로 그래서* 결정론 검사기가 필요하다.

**확인 대상의 범위(2층).** OVLA가 검증하는 reference는 사용자가 승인한 IR이다. 이 oracle은 지나치게 까다로운 가정이 아니다. reactive-temporal 자동화에서 사용자가 실제로 제어하는 차원은 한정적이고 열거 가능하다. 시작 시점, 주기, 트리거와 조건, 동작과 그 인자, 지속·지연 시간이다. Timeline IR은 이 닫힌 슬롯 집합만 표현하며, 그 내용은 결정론 Rendering을 통해 사용자에게 그대로 드러난다(RQ3). 따라서 IR 승인은 임의의 형식 property를 작성하는 일이 아니라, 사용자가 말한 명령의 유한한 제어 슬롯을 시간선으로 확인하는 닫힌 판단이다. 그럼에도 보장 범위는 정직하게 두 층으로 구분한다. **Layer A (NL→IR)**: 시스템은 의도를 IR로 포착해 평문으로 제시하지만, 비전문가의 confirm 성공률 *자체*는 이 라운드에서 측정하지 않는다(사람 대상 연구 없음, §9). **Layer B (IR→code)**: IR이 승인된 뒤, OVLA는 생성된 코드가 그 표시된 IR과 silently 어긋나는 것을 bounded 동작 영역 안에서 막는다. OVLA의 보장은 Layer B에 있다.

**배포 환경.** 우리는 cloud가 아니라 가정용 edge device를 가정한다. 프라이버시(센서 데이터가 집을 떠나지 않음)와 지연 때문이다. 이 제약은 cloud LLM judge를 게이트에서 배제하며, 따라서 게이트는 LLM 없는 결정론 검사여야 한다. 같은 설계 결정 하나가 신뢰(확률적 judge 없음)와 배포 가능성(model 호출 없이 ms 단위)을 동시에 낳는다.

**기여.**
- **C1. Timeline IR.** 하나의 표현이 동시에 두 역할을 한다. (a) 사용자가 승인하도록 결정론적으로 평문 Rendering되는 surface이자, (b) reactive-temporal 코드를 검사하기 위한 기계검증 가능한 behavioral reference다. 승인된 NL 문장은 (a)만, 형식 property는 (b)만 할 수 있다. 둘을 겸하는 표현이 기여다. (선행 연구가 이미 confirmable temporal IR을 생성하므로, 우리의 주장은 *그 IR을 결정론 LLM-free로 검증하고 렌더하며 on-device로 돌리는 조합*에 있다. §2.)
- **C2. 결정론 배포 게이트.** IR→FSM→boundary event→bounded trace-equivalence를 LLM 없이 수행하며 fail-closed다(pass=deploy / fail=repair 또는 reject). 플래그가 뜨면 그것은 실제 동작 divergence다(rejection-sound).
- **C3. On-device 실현.** ≤9B 4-bit 모델을 fine-tuning 없이 사용하고, 게이트에 LLM 호출이 없어 ms 단위로 cloud 없이 동작한다.
- **C4. 평가.** 시스템 안전(silent IR-code divergence 9.2%→0, RQ1), verifier detection(RQ2), rendering faithfulness(RQ3), on-device feasibility와 실배포(RQ4)를 component별로 입증한다.

**기여의 초점.** OVLA가 제거하는 것은 *승인 이후에도 남는* 배포 실패 모드, 즉 생성된 실행 코드가 시스템이 표시하고 승인받은 동작과 silently 어긋나는 모드다. 이 모드가 실재하는 이유는, 표시된 IR이 받아들일 만하더라도 reactive-temporal lowering이 상태, 타이머, 경계 조건 오류를 끌어들이기 때문이다.


---

## 2 관련 연구와 포지셔닝 (Related Work & Positioning)

OVLA의 출력은 **non-canonical reactive-temporal** 프로그램이다. 같은 동작을 여러 다른 표현으로 쓸 수 있고, 도메인이 제공하는 정답 oracle도 없다. 따라서 구문 비교나 주어진 oracle 검사로는 충분하지 않고, 동작 자체를 검증해야 한다. 우리는 선행 연구를 "NL 의도를 다루는가"가 아니라 *생성 이후 무엇을 검사하는가*라는 세 단계 깔때기로 정리한다. 거의 모든 시스템이 NL 의도를 입력으로 받기 때문에, 변별점은 입력이 아니라 검사다.

**2.1 생성된 자동화를 (동작) 검증하는가?** 대다수는 하지 않는다. Giudici et al.(2025)은 NL을 Home Assistant 루틴으로 만들지만 정확성을 "프레임워크가 JSON을 수락함"까지로 본다. IoTGPT는 SmartThings 규칙을 생성하고 LLM self-correction으로 API 오류만 잡는다. ChatIoT는 LLM "Evaluator"로 형식과 값 적정성만 점검한다. Sasha와 SAGE는 지속 자동화 artifact 없이 일시적 device 설정이나 tool-call을 낸다. 이 단계에서 가장 가까운 generator는 **AwareAuto**다. AwareAuto는 NL로부터 confirmable한 reactive-temporal 규칙(event/state mode, delay, 분기, 순서)을 만들어 사용자에게 보여 주고 실행 JSON으로 내린다. 그러나 생성된 코드를 그 규칙에 대해 *동작 검증하지 않는다*. 유일한 자동 검사는 device 인터페이스로의 grounding feasibility이고, intent consistency는 연구자가 수작업으로 맞춘 것이며, 사용자에게 보여 주는 것은 LLM의 산문 그 자체다.

**2.2 검증한다면, 무엇에 대해서인가(reference)?** 대개 의도된 동작이 아니라 고정된 property다. (a) **고정 property**: AutoTap은 사용자가 작성한 부정 LTL 안전 invariant를 만족하도록 TAP을 합성한다. TAPFixer와 TAPInspector는 부정 안전/활성 property를 model-checking한다. AutoIoT는 Maude로 규칙 간 충돌 4종을 검사한다. HAWatcher는 마이닝한 invariant로 런타임 이상을 탐지한다. DS-IA는 결정론 cascade로 명령의 grounding feasibility를 점검하고 실행 전 fail-closed로 거부한다. iRuler/Soteria는 규칙 간 취약점/안전 property를 본다. 이들은 모두 안전/충돌/feasibility를 보며, *의도 부합*은 비어 있다. (b) **주어진 oracle(비-IoT 비유, 짧게)**: text-to-SQL은 gold 질의에 대한 denotation 동치로 검증할 수 있고, CodeT/Self-Debug는 unit test로, GPIoT는 algorithmic 코드에 pass@k 같은 executable oracle이 있어 검증이 쉽다. 핵심은, 실행 검사는 oracle이 도메인에서 *주어질 때만* 가능하다는 것이다. reactive 자동화에는 그것이 없으므로 OVLA는 oracle을 승인된 IR에서 *유도*한다. trace-equivalence는 reactive 영역에서의 execution-accuracy에 해당한다.

**2.3 의도를 검사한다면, 무엇으로 하는가(mechanism)?** 학습/확률 모델 judge다. 이 단계에서 가장 가까운 verifier는 **LACE**다. LACE는 생성된 정적 access policy를 결정론 템플릿으로 back-translate해 fine-tuned NLI 모델로 의도 동치를 판정하고, Z3 충돌 검사와 OPA 재검증을 더한다. 우리 문제를 거의 그대로 진술하지만, 검증 대상이 *시간이 없는 정적 policy*이고 판정이 *확률적*이며 *사용자가 루프에 없다*. ChatIoT의 Evaluator, IoTGPT/SAGE의 self-correction도 같은 부류다. SimuHome은 reactive-temporal 동작을 모델이 스스로 점검하는 것이 실패함을 실측으로 보인다(§3). 이들은 의도를 다루지만 모델 기반이라 불안정하고 edge에 부적합하다.

**OVLA의 위치.** OVLA는 깔때기의 끝점에 있다. *동작*을, *승인된 IR*에 대해, *결정론적으로*, *배포 전에*, *on-device*에서 검사한다.

**가장 가까운 두 이웃.** *LACE*: LACE와 OVLA는 모두 생성물을 back-translate해 의도에 비추지만, LACE는 시간이 없는 정적 policy를 확률적 NLI로, 사용자 없이 검사한다. 그 결과 "100% 정확"은 NLI가 스스로 인증한 수치다. OVLA는 reactive-temporal *trace* 동작을, 사용자가 승인한 reference에 대해, 결정론 LLM-free로 검사한다. (LACE의 back-translation도 결정론 템플릿이므로, "결정론 rendering" 자체를 차별점으로 앞세우지 않는다. wedge는 reactive-temporal trace + LLM-free equivalence + user-approved reference다.) *AwareAuto*: AwareAuto는 이미 confirmable한 reactive-temporal 표현을 NL로부터 만들어 보여 주고 배포한다. 따라서 우리는 "최초의 NL→temporal IR"이나 "최초로 규칙을 비전문가에게 보여 줌"을 novelty로 주장하지 않는다. 그러나 AwareAuto는 동작 검증을 하지 않는다. OVLA는 AwareAuto가 멈추는 지점에서 시작한다. 승인된 표현을 behavioral reference로 삼아 생성 자동화를 결정론 LLM-free verifier로 검사하고 on-device로 돌린다. 기여는 temporal IR의 *존재*가 아니라 그 *조합*이다.

**포지셔닝.** 우리는 "생성+검증 결합" 자체를 novelty로 주장하지 않는다. 그것은 이 분야의 표준이다(Table 1). novelty는 *user-approved 결정론 behavioral 검증(reactive-temporal·on-device)* + IR의 다목적성에 있다. (Table 1: 조합 행렬. arXiv preprint는 인용·차별화용이며 정량 head-to-head baseline로 쓰지 않는다.)

**Table 1.** Positioning. 단일 칸이 아니라 *행 조합*이 OVLA를 유일하게 한다.

| System (venue) | 대상 artifact | 동작 검증 | 검증 기준 | 검증 방식 |
|---|---|---|---|---|
| AutoTap (ICSE'19) | flat TAP | ✓ | safety | model-check |
| ChatIoT (IMWUT'24) | flat TAP | 부분 | format | LLM judge |
| GPIoT (SenSys'25) | algorithmic | ✓ | tests | tests |
| TaskSense (SenSys'25) | sensor plan | ✓ | feasibility | structural |
| AwareAuto (preprint) | reactive-temporal | ✗ | grounding | (없음) |
| **OVLA** | **reactive-temporal** | **✓** | **behavior** | **trace (det.)** |

범례. *동작 검증*: ✓ 생성 코드를 동작으로 검사 / 부분(형식·값만) / ✗ 행동 검증 없음. *검증 기준*: safety(고정 안전 property) / format(형식·값) / tests(외부 test oracle) / feasibility(plan 실행가능성) / grounding(기기 존재) / **behavior(승인된 IR의 의도된 동작)**. *검증 방식*: model-check / LLM judge / tests / structural / **trace(결정론 LLM-free)**. flat TAP은 무상태·순간적이라 trace 없이 점검되지만, reactive-temporal은 지속 상태·duration·timer·순서를 더한 superset이라 trace로만 검사된다. AwareAuto는 reactive-temporal 표현을 만들지만 grounding feasibility만 보고 동작은 검사하지 않는다(intent는 수작업). 근접이웃 LACE는 정적 policy를 확률적 NLI로 검사하므로 reactive-temporal 코드를 대상으로 하는 본 표에서는 제외하고 본문에서 다룬다.

---

## 3 배경, 문제, 동기 (Background, Problem & Motivation)

**Reactive-temporal 자동화.** reactive 자동화는 센서 이벤트에 반응해 지속적으로 동작한다. flat trigger-action과 달리, reactive-temporal 자동화는 지속 register("문이 5분간 열려 있으면"), 주기 동작("10분마다"), 다단계 시퀀스, 타이머를 포함한다. 그 정확성은 한 시점이 아니라 *timeline 위의 동작*으로 정의된다. 우리는 정확성을 **transition-boundary conformance**로 본다. 두 프로그램은, 동작이 바뀔 수 있는 경계(임계값 교차, 조건 edge, 타이머 만료, 다음 주기 재시작)에서의 action trace가 일정 tolerance 안에서, 고정된 bounded 지평 위에서 같으면 동작이 같다고 본다. 이는 전체 입력 공간에 대한 동치 증명이 아니라 경계에 초점을 둔 동치 판정이다.

**왜 정적 oracle이 없는가.** algorithmic 코드(예: R-peak 검출)는 입출력 쌍이라는 executable oracle을 가져 pass@k로 검증된다(GPIoT, SenSys'25). reactive 자동화에는 그런 oracle이 없다. "옳은 출력"이 미래의 device action 시퀀스이기 때문이다. 이것이 OVLA가 reference를 *승인된 IR에서 유도*해야 하는 구조적 이유다.

**외부 증거.** 세 가지 선행 결과가 문제를 뒷받침한다. (1) **SimuHome (ICLR'26)**: 18개 *모델*이 workflow scheduling에서 실패하며, self-correction recovery는 시간 기반 8.0%, event 기반 18.5%, 협응 scheduling 0.0%에 그치고, oracle을 주어도 ≤67%다. 저자들은 "에이전트가 자신의 잘못된 plan을 탐지하지 못한다"고 결론짓는다. 즉 self-check/post-hoc는 안 되며 배포 전 검증이 필요하다. (SimuHome의 평가는 feasible 작업에 대한 결정론 simulator assertion과 infeasible 작업에 대한 3회 다수결 LLM-judge의 hybrid다.) (2) **TAP-Debug (IMWUT'22)**: 비전문가가 raw 규칙의 IF(event)와 WHILE(state)를 오독해 Control 조건 50세션 중 21건에서 오독했고 그 21건 모두 실패했다. 읽을 수 있는 Rendering이 필요한 이유다. (3) **GPIoT (SenSys'25)**: algorithmic 코드는 executable oracle이 있어 검증이 쉽다. reactive에는 없으므로 oracle을 confirmed IR에서 유도한다.

**동기 실험: LLM judge의 불안정성.** 우리는 LLM judge가 안정적 배포 게이트가 아님을 직접 보인다(OVLA의 IR이나 verifier는 이 실험에 등장하지 않는다). 동작이 완전히 같은(trace-exact) 프로그램을 idiom만 바꿔 제시했을 때, judge의 accept/reject 판정이 흔들리는 비율을 측정했다. temp=0의 결정론 세팅에서도 9B 모델은 27%, 강한 cloud 모델은 10.6%가 flip했다(변수명 변경 등 순수 표면 재작성에도 6~9%, deMorgan·double-negation 같은 논리 형태 재작성에는 최대 81%). OVLA의 결정론 trace 검사는 0이다. 정답 라벨 없이, flip 자체가 불안정의 증거다. 배포 결정은 binary이므로, 동작이 같은 두 프로그램이 다른 deploy/reject를 받는다면 게이트로 부적격이다. 여기서 핵심은 miss-rate가 아니다. 실제로 clean하게 주입된 버그에 대해서는 강한 모델도 유능한 검출기다(FN 5.8%). 핵심은, *어떤* 확률적 judge든 behavior-preserving rewrite 하에서 배포 정책이 불안정하다는 것이다. 이 불안정은 더 큰 모델로도 남고, 다수결 voting으로도 결정론 floor 아래로 내려가지 않는다(아래 Table 2). 반면 OVLA의 판정은 bounded trace 집합 위의 동작에만 의존하므로 0 by construction이다. (Figure 1: 모델별 flip rate 분포.)

**Table 2 (instability decomposition).** 어떤 judge 구성도 결정론 floor 아래로 못 내려간다. 다수결 voting은 샘플링 noise만 상쇄할 뿐 체계적 surface-form 의존은 제거하지 못한다.

| Judge 구성 | 9B | GPT-5.1 |
|---|---|---|
| 결정론 (temp=0) | 27.0% | 10.6% |
| + 샘플링 (temp=0.7) | 34.4% | 12.8% |
| + 다수결 (K=5) | 31.2% | 13.5% |
| **OVLA (결정론 trace)** | **0%** | **0%** |

**구문 비교만으로는 부족하다.** 같은 reactive-temporal 의도가 실행 DSL에서는 여러 idiom으로 실현된다. Figure 2은 하나의 primitive IR 의무(회의실 규칙의 `wait(presence==false, for: 10 MIN)`)가 (A) tick 카운터와 (B) ms 누적이라는 행동은 같지만 구문이 다른 두 lowering으로, 그리고 (C) 임계값이 10배 틀려 1분 만에 발화하는 거의 똑같아 보이는 버그로 표현되는 것을 보인다. 리터럴 구문이나 구조를 비교해서는 A와 B를 서로, 또 C를 A로부터 구분할 수 없다. 오직 시뮬레이션된 action trace에서만 올바른 idiom은 10분, C는 1분에 발화하며 갈린다. reactive-temporal 코드의 동등성은 구문이 아니라 행동으로 판정해야 한다는 뜻이며, 이것이 §6 verifier가 trace를 비교하는 이유다.

(Figure 2: 하나의 Timeline IR 의무의 세 lowering. 올바른 idiom A(tick 카운터)·B(ms 누적)는 구문이 달라도 trace 동일(10분에 소등), 버그 C는 A와 거의 같아 보이나 1분에 발화. 구조 비교로는 셋을 못 가리고 action trace만 C의 어긋남을 드러낸다. JoI·IR 문법은 §5에서 정의. 이 단계에선 verifier 판정 박스 없이 검증의 *필요*만 보인다.)

**IR로의 다리.** "LLM judge가 불안정하다"에서 "그러므로 Timeline IR"로 가는 논리는 다음과 같다. ⓪ 대상이 reactive-temporal 코드라 정적 oracle이 없다. ① reactive 동치성은 timeline 위의 semantic property다(텍스트 그럴듯함이 아니다). ② NL·code·trace는 동작이 같은 변형이 많다. ③ LLM judge는 그 동치 보존 변형에 불안정하다(위 실험). ④ 따라서 reference는 canonical하고 executable해야 하며, 그것이 Timeline IR이다. (이 동기 실험의 judge[NL+code]는 §8 RQ2의 judge[IR↔code]와 다른 실험이다.)

---

## 4 시스템 개요 (System Overview)

OVLA의 조직 원리는 하나다. LLM은 *생성*에 쓰고(IR 제안 + JoI lowering), feasibility 게이트·Rendering(승인용)·verifier는 결정론적이며 LLM 호출이 없다. lowering이 LLM 단계이기 때문에 *바로 그래서* 결정론 검사기가 필요하다. Figure 3가 전체 pipeline을 보인다. 두 phase로 읽는다.

**Phase 1: Generation (on-device LLM).** NL 요청 → semantic parsing(intent / service mapping / device mapping) → **Timeline IR** 추출 → **feasibility 게이트 `IR∈L(G)`**(구조적으로 불가능한 IR을 결정론적으로 거부) → 결정론 **Rendering**을 사용자가 승인 → 승인된 IR을 JoI 코드로 **lowering**.

**Phase 2: Verification (결정론, LLM-free).** **L1** 정적 검사(생성된 JoI의 well-formedness) → IR→FSM 도출 + boundary **event 합성** → IR 시뮬레이터와 JoI 시뮬레이터를 같은 event로 실행 → **trace-equivalence** 비교 → 불일치 시 **counterexample**로 JoI를 재생성(repair; IR은 승인된 reference이므로 고정) → 통과 시 deploy / repair 불가 시 **reject(fail-closed)**.

**검증 계층의 구분.** 세 검사는 서로 다른 시점·artifact에 놓인다. **feasibility = `IR∈L(G)`**는 *IR*을 typed tree로 보는 구조 게이트로, IR 추출 직후·lowering 전이다. **L1**은 *생성된 JoI 코드*의 정적 well-formedness로, lowering 후·L2 전이다. **L2**는 *behavioral trace-equivalence*로, 코어다. 셋을 한 단계로 묶지 않는다. hero는 L2이고, feasibility와 L1은 그것을 받쳐 주는 게이트다.

**IR의 역할.** 하나의 Timeline IR이 승인 대상(평문 surface), 검증 reference, 생성 scaffold, 구조 signature의 네 역할을 한다. upstream의 intent/service/device mapping은 기반 substrate이며 이 논문의 기여가 아니다. (device mapping은 IR 추출과 병렬로 동작하지만 figure에서는 순차로 그린다.)

---

## 5 Timeline IR

Timeline IR은 두 속성을 동시에 갖도록 설계됐다. 첫째, 사용자에게 승인받기 위해 결정론적으로(LLM 없이) 평문으로 Rendering된다. 둘째, 기계가 검증할 수 있는 behavioral reference다. NL→IR은 LLM이지만, IR→Rendering은 결정론이다. 따라서 사용자가 보는 평문은 IR을 정확히 반영하며 환각이 없다. 즉 표시된 것이 곧 검사되는 것이다.

**닫힌 제어 차원과 primitive op.** 이 두 속성이 가능한 이유는 IR의 표현 방식에 있다. reactive-temporal 명령이 제어하는 차원은 닫혀 있고 열거 가능하다. 시작·스케줄(`start_at`), 주기(`cycle.period`), 트리거·조건(`wait`의 cond·edge, `if`의 cond), 동작과 인자(`call`), 지속·지연(`wait.for`, `delay`), 상태·카운트(persistent 변수, `cycle.count`, `break`)다. Timeline IR은 각 차원에 primitive op를 하나씩 두어, 명령이 *지정한* 것을 더도 덜도 없이 timeline 위에 직접 인코딩한다. 이 정규성(canonical·minimal·complete)이 위 두 속성을 동시에 낳는다. (a) 결정론 Rendering이 새 정보를 더하지 않고 이 슬롯들을 그대로 평문화하므로, IR 승인은 임의의 형식 property를 작성하는 일이 아니라 명령이 지정한 유한한 슬롯을 timeline으로 확인하는 닫힌 판단이 된다. (b) 같은 표현이 누락 없는 기계검증 behavioral reference가 된다. 닫힌 op 집합은 그대로 아래의 문법 G를 이룬다.

**finite-state view.** IR은 reactive 동작을 유한한 obligation 집합으로 본다. 재귀나 무한 루프 없이 bounded 타이머·카운터·유한 제어만 허용한다. 이는 model-checking 대상이 아니라, 검사 대상을 열거 가능하게 만드는 view다(timed automata가 아니다).

**typed tree와 의존성 문법 G.** IR은 typed tree이며, 어떤 구조가 합법인지를 의존성 문법 G가 규정한다. start_at은 정확히 1개(top-level cron도 1개), `cycle.body` 안에는 `cycle`이 올 수 없고(중첩 불가), `then`·`else`는 `if`의 자식만, `break`는 `cycle` 안에서만, `cycle`은 period와 until이 필수다. 멤버십 `IR∈L(G)`는 결정론적으로 판정 가능하며, 이것이 §6의 feasibility 게이트의 근거다.

연산자는 start_at, wait(cond·edge·for), delay(duration), read, call, if(then/else), cycle(period·count·until·body), break이다. 예를 들어 §1의 회의실 자동화는 start_at(now) 아래 cycle{ wait(presence==false, for: 10min); call(Light.off) } 형태로 표현되고, 결정론 Rendering은 "사람이 10분간 감지되지 않으면 모든 회의실 조명을 끈다"가 된다. (Figure 4: IR 예시와 그 평문 Rendering.)

---

## 6 Verifier

### 6.1 왜 behavioral이고 왜 lightweight인가

생성된 JoI에는 정적 oracle이 없고 표현이 non-canonical하다. §5에서 보았듯 IR은 각 제어 차원을 primitive op 하나로 두지만, 실행 DSL에는 그 차원들의 primitive가 없어 같은 IR 행동을 idiom으로 실현해야 한다. "N분 지속"은 poll tick마다 카운터를 올려 임계값에서 발화하는 idiom으로, "edge(whenever)"는 발화 시 set하고 조건이 풀리면 reset하는 triggered 플래그(또는 prev/curr)로, "N분마다"는 period 본문 재실행으로 표현된다. 하나의 IR 행동이 이렇게 여러 valid idiom으로, 그리고 한 tick·한 비교 차이로 어긋난 무수한 near-miss로 나타나며(Figure 2), 버그가 들어오는 자리도 바로 이 idiom 실현 지점이다. 따라서 구문이나 구조 일치로는 valid 변형과 버그를 구분할 수 없고, 동치성은 구문이 아니라 동작(trace)으로 봐야 한다. 다행히 reactive 동작에는 형식적 뼈대가 있다. reactive 자동화의 동작은 (시간 랜드마크 × 센서값 구간 × edge × bounded 내부 상태)의 유한 추상 위에서 piecewise-constant다. 동작이 바뀔 수 있는 후보는 guard 임계값, 조건 edge, 시간 랜드마크(delay·duration·period·cron), 상태 전이뿐이다. IR이 재귀·무한 루프 없이 bounded 제어만 허용하고 고정 7일 지평을 두므로, 이 조합은 유한하고, 각 cell마다 대표 입력 하나로 그 cell 전체를 검사할 수 있다. 그래서 우리는 full equivalence나 model checking, SMT를 쓰지 않고 **bounded trace-equivalence**를 결정론적·solver-free·on-device로 수행한다. 이는 무거운 형식 기법의 대체가 아니라 배포 시점의 필터다. (내부 상태 축은 빠뜨릴 수 없다. hysteresis, 토글, counter, sustain은 센서값만으로 설명되지 않는다.)

### 6.2 Boundary Event Synthesis (IR-FSM → events)

핵심 기술은 IR로부터 FSM을 결정론적으로 도출하고(LLM 없음), IR의 결정점에서 대표 event를 합성하는 것이다. call/wait/delay/read/if/cycle/break는 obligation이 되고, after-edge는 순서를, branch는 guard를, cycle은 다음 주기의 재시작(re-arm) 의무를 만든다. 경계(guard 임계값, edge, 타이머, cron, 상태 전이) 주위에 지속 boundary 값을 갖는 대표 event를 하나씩 심는다. 교차의 *크기*는 무관하며(31°C든 100°C든 같은 구간) 중요한 것은 타이밍이다. 이 합성은 IR 기반이며 surface 구문이 아니다. read→센서 추적, abs/min/max+clamp, value domain 양끝(≥2점으로 affine 검출), RMW skip, 조건이 풀렸다 다시 성립하는 2차 edge를 다룬다. 합성된 같은 event 집합이 두 시뮬레이터에 동일하게 들어가므로 비교는 apples-to-apples다. (Figure 5: IR-FSM → event 합성 → 두 시뮬레이터 → trace 비교.)

### 6.3 Trace-equivalence와 누락(omission) 검출

IR 시뮬레이터와 JoI 시뮬레이터를 같은 event로 실행해 얻은 action trace를 ±tolerance(max 500ms, 10%) 윈도우로 그룹·dedup하고 순서를 보존해 비교한다. 이 비교는 commission(하지 말아야 할 행동)과 omission(해야 할 행동의 누락)을 동시에 잡는다. trace의 *침묵*도 trace의 일부이기 때문이다. IR trace의 빈 구간은 "여기서는 아무 행동도 하지 않는다"는 oracle이다. 이것이 가능한 이유는 IR이 complete behavior를 담기 때문이다. partial property나 LTL은 침묵을 고정하지 못해 누락을 못 잡는다. 예를 들어 "15분마다 확인"을 즉시 반응(react)으로 오역한 코드는, IR의 지속 boundary 시나리오에서 발화 빈도와 타이밍이 달라 IR(드물게/침묵)과 JoI(과다 발화)의 trace가 어긋나며 플래그된다.

### 6.4 주장 사다리 (Claim ladder)

verdict는 결정론적이며 LLM-free다. **T1 (determinism)**: 같은 (IR, code) 쌍은 항상 같은 verdict를 낸다. **T2 (rejection-sound)**: 플래그가 뜨면 그것은 정의된 관측 모델 아래의 실제 동작 divergence다. 우리는 "pass ⇒ correct"를 주장하지 않는다. TCB(trusted computing base)는 두 시뮬레이터, tolerance, 등가 관계이며 LLM은 제외된다. soundness는 증명이 아니라 시뮬레이터 충실성으로의 환원과 mutation 증거로 뒷받침된다.

### 6.5 Feasibility = `IR∈L(G)`

feasibility 게이트는 IR 추출 직후(lowering·L1·L2 전)에 IR이 문법 G에 속하는지를 결정론적으로 판정해, 구조적으로 불가능한 IR(중첩 cycle, 이중 cron, 잘못 놓인 then/else, cycle 밖 break)을 거부한다. correctness는 by-construction(문법 멤버십)이므로 실험 없이 메커니즘으로 성립한다. 다만 이 보장은 extractor가 사용자의 말을 *literal-transcription*한다는 가정 위에서만 성립한다. LLM이 불법 구조를 silent-flatten하면 valid IR이 G를 통과하고 의미만 틀려 confirmation에 잔여가 남는다. 따라서 extractor는 "정정하지 말고 그대로 옮겨라"로 설계되어야 한다.

### 6.6 Adequacy 증거 (실험; §8 RQ2)

construct-derived mutation을 전수 적용해 검출률을 측정한다(12개 연산자 active). 결과는 §8 RQ2에서 보인다. 요약하면 99.3%(1551/1562 genuine) 검출, spec coverage 97.4%(342/351), impl JoI-branch coverage 95.6%(566/592)이며, 살아남은 11개는 모두 특성화된다(8개 sub-tolerance comparator, 1개 fan-out 중복, 2개 C14 arithmetic-RMW).

### 6.7 한계 (정직)

연속 산술(센서의 연속 함수인 action arg)은 대표 ≥2점이 affine 발산은 잡지만 임의 고차는 미증명이며 SMT가 future다. bounded 7일 지평 너머는 검사하지 않는다. 모든 지속 입력에서는 IR과 같고 transient glitch에서만 다른 버그는 이론상 IR-only가 놓칠 수 있으나 자기모순적이라 실제로 나타나지 않는다. threshold 없는 변수-변수 산술(예: `notify($t1-$t2)`)은 노릴 경계가 없어 generic seed만 가능하므로, 부호·구조 버그는 잡지만 특정 값 관계에서만 터지는 value-specific 버그는 놓칠 수 있다. 이는 거짓 PASS(soundness)가 아니라 coverage 한계다. 두 시뮬레이터가 같은 값을 공유하므로 거짓 통과를 만들지 않는다.

---

## 7 구현 (Implementation)

OVLA는 ≤9B 4-bit 모델을 fine-tuning 없이 on-device로 사용하며, 생성은 multi-stage decomposition(intent / service / device / IR-extract / lowering)으로 나뉜다. (GPIoT가 13B SLM을 fine-tuning하고 TaskSense가 cloud를 쓰는 것과 달리, 우리는 fine-tuning 없는 ≤9B에 결정론 verifier를 더한다.)

**no-cloud 공동 설계.** no-cloud 가정은 cloud LLM judge를 게이트에서 배제하므로, 게이트는 LLM 없는 결정론 검사여야 한다. 같은 결정이 §3의 instability 관점에서도 옳은 선택이다. 하나의 결정이 신뢰와 배포 가능성을 함께 가져온다.

**구조 기반 exemplar routing(구현 디테일).** IR의 구조 클래스 τ(IR)를 공유하는 exemplar를 검색해 lowering prompt를 구성한다. 이는 generator 쪽에만 작용하며 verdict는 여전히 LLM-free다. 이 라운드에서 그 효과를 ablation으로 측정하지 않으므로, 우리는 generation 개선을 정량 주장하지 않고 메커니즘만 서술한다.

---

## 8 평가 (Evaluation)

평가의 목표는 정확도 경쟁이 아니라 워크플로의 각 고리가 성립함을 component별로 입증하는 것이다. headline은 silent IR-code divergence를 0으로 만드는 시스템 안전이다(RQ1).

**Setup.** *하드웨어*: 헤드라인 edge는 Mac Mini M4 16GB(MLX 4-bit)이고, 정확도 확립용 reference는 RTX 5090(AWQ)이다. 안전 결과는 backend에 독립이다(feasibility는 M4에서, yield는 backend별로, silent-wrong 0은 invariant). *데이터셋*: 382개 자동화, 24개 category(`category_v2`). 데이터셋은 reactive idiom 가족을 폭넓게 덮도록 구성됐으며 OVLA의 문법에 맞춰 선별된 것이 아니다(provenance를 §8 끝에 명시). *baseline*: 메인 비교는 verification 대안인 LLM judge다. 각 judge는 프롬프트, 입력 artifact(IR/code/rendering/trace 중 무엇을 보는지), temperature, retry, voting 여부를 명시해 보고한다. *metric*: 안전(silent-wrong-deployed), 검출(detection/FP/FN), faithfulness(surface 비율), feasibility(latency 분포·메모리·전력).

### RQ1: 시스템 안전 (HEADLINE)

OVLA는 배포된 코드가 *표시된 IR*과 silently 어긋나는 것을 막는가? 게이트가 없으면 382개 중 35개(9.2%)가 승인을 위해 표시한 IR과 silently 어긋난 채 배포된다. OVLA의 bounded IR↔code 검사는 이를 0으로 줄인다(11개 repair, 24개 fail-closed reject, 그리고 정확한 후보 2개를 over-reject하는 비용). deploy되는 정확한 자동화 비율은 90.84%에서 93.19%로 오른다. 이 수치는 *표시된 IR*로부터의 divergence에 관한 것이며(confirmed-IR 가정), IR이 사용자의 진짜 의도와 맞았는지에 관한 것이 아니다(Layer A는 §9).

이를 3-way ablation으로 본다(Table 3). (i) generation-only(게이트 없음): silent-wrong 9.2% 그대로 배포. (ii) LLM-judge 게이트: §3의 불안정성으로 일부만 걸러지고 일부 정확한 코드를 over-reject. (iii) OVLA 게이트: silent IR-code divergence 0, fail-closed. *repair는 안전의 증거가 아니다.* 안전 주장은 fail-closed에 있다. 어긋난 코드는 repair되거나 거부되어 배포되지 않는다. repair-loop 회계(시도 횟수, 성공률, 추가 지연, repair가 정확한 코드를 망친 사례)와 over-reject 2건은 메인 표에 함께 보고한다. reject되는 hard-core는 sustain-timing, read-modify-write, multi-step에 몰려 있어 fail-closed가 "어려운 것을 다 거부"하는 것이 아님을 보인다.

### RQ2: Verifier detection

verifier는 틀린 코드를 무조건 잡는가? 우리는 두 출처로 본다.

**독립 corpus(circularity 방어, 먼저).** verifier·gt_ir와 무관하게 구성한 실제 LLM-bug corpus로 먼저 검증한다. 여러 로컬·cloud 모델로 NL→JoI를 생성하고, 사람이 *gt_ir와 verifier 출력을 보지 않고* 기대 동작을 판정한 뒤(leakage 차단 protocol), verifier 결과를 {실제 lowering 버그 검출 / IR-error / unsupported-intent 거부 / ambiguous / escaped(silent-wrong)}로 분류한다. escaped 사례는 버킷이 아니라 예시로 보고한다.

**mutation(stress coverage).** 그다음 construct-derived mutation을 전수 적용해 메커니즘의 스트레스 한계를 본다. 99.3%(1551/1562 genuine) 검출, spec coverage 97.4%, impl JoI-branch coverage 95.6%, survivor 11개 전수 특성화(8 sub-tolerance comparator, 1 fan-out 중복, 2 C14 arith-RMW). 우리는 세 주장을 분리한다. ① 실제 lowering 버그를 잡는다(corpus). ② 인접 construct 결함을 검출한다(mutation neighbor-kill). ③ 382 파이프라인에서 silent mismatch가 0이다(RQ1). soundness 진술은 rejection-sound, bounded-incomplete, auditable이다("pass ⇒ correct" 아님).

**vs LLM judge.** 같은 IR↔code 판정을 LLM judge(9B P=0.71; cloud judge로 ChatIoT의 Evaluator 류)와 비교한다. 복잡도(코드 길이·중첩·device 수·시간 조건)가 올라갈수록 LLM judge는 급락하지만 OVLA는 평평하다(Figure 6). 또 같은 의도의 여러 valid 코드(multi-GT)에 대해 LLM judge는 over-reject하지만 OVLA는 trace-equivalence라 idiom-invariant하게 통과시킨다. (이 multi-GT는 judge가 IR을 받는 RQ2 세팅으로, §3의 NO-IR 동기 실험과 다른 실험이다.)

### RQ3: Rendering faithfulness

이 질문은 좁은 prerequisite다. *결정론 Rendering이 동작에 관련된 IR 차이를 모두 평문에 노출하는가?* 우리는 사용자가 옳은 IR을 승인하는지를 평가하지 않는다(no-IRB; Layer A는 §9). 평가하는 것은, 승인 surface가 충실한가, 즉 게이트가 소비하는 IR 필드가 표시 행동에 드러나는가이다.

주장은 precise하다. "renderer는 checker와 lowerer가 소비하는 IR 필드를 노출하므로, IR-to-code 관계의 fault가 표시 행동에 보인다. 우리 테스트셋의 모든 동작 차이가 서로 다른 Rendering을 냈다." 합성 8 class(comparator/polarity/arg/device/timing/oneshot↔waituntil/single↔cycle/and-drop)의 1504건이 모두 다른 평문으로 surface됐고 blind는 0이었다. 실제 logic-fault 56건도 모두 surface됐다. (Figure 7: 명령과 그 IR Rendering, 그리고 틀린 IR의 Rendering을 의도와 나란히.)

**surface되지 않는 것(정직).** 이 결과는 *모든* 종류의 오류가 평문에 드러난다는 뜻이 아니다. (a) device-name 모호성(같은 평문이 여러 device 결합으로 해석될 수 있음. device binding은 병렬 precision 채널이 담당). (b) 도메인 용어 오해(사용자가 평문을 다르게 읽음. 이는 사람 행동이며 우리가 평가하지 않음). (c) 빠진 intent(사용자가 말하지 않은 것은 IR에 없으므로 Rendering에도 없음). (d) rendering 전에 reject되는 unsupported construct. 우리 주장은 reactive-temporal *logic* fault가 평문에 드러난다는 것이며, prior work(TAP-Debug, 21/21 오독)는 *raw 규칙*으로는 이것조차 어려움을 보인다.

### RQ4: On-device feasibility와 deployment

**Feasibility.** latency를 평균이 아니라 분포(p50/p95/worst)로 보고하고, peak memory, 전력, model load time, repair 횟수, 그리고 *복잡도별 worst-case verifier runtime*(trigger·timer·state-var·quantifier·device·boundary-event 수 기준, LOC 아님)을 함께 본다. 핵심 그림은 시그니처 비교다(Figure 8a). LLM-free verifier는 ms·$0, 로컬 9B judge는 초·VRAM, cloud judge는 초+요금+네트워크다. 또한 unsupported-intent rate(현실 자동화 중 검증 전에 거부되는 비율)를 보고해 fail-closed가 유용성을 해치지 않음을 보인다.

**Deployment.** 우리는 상용 플랫폼(Mysmax) 위 Raspberry Pi 기반 edge device에 실제 기기 약 10대를 두고 N≈12-15개 자동화를 수동 등록해 demonstration한다(통계가 아니라 존재 증명). hero 시나리오는 §1의 회의실 sustain이다. presence-false가 10분 지속되면 회의실 조명이 모두 꺼져야 하는데, 버그 코드는 1분 만에 꺼진다. (Figure 8b: 센서/actuator 관측 trace와 IR 예측 trace를 겹쳐 OFF(오작동)와 ON(repair 후)을 대비.) verifier-value 사례는 9개다(7개 reject, 2개 repair). 물리적으로 실현 가능한 subset은 382 중 52개(온도 관련 ~73 포함)다. efficiency는 enabler이지 headline이 아니다.

**차별화 정리.** 능력 비교는 측정형 RQ가 아니라 §2의 Table 1로 갈음하며, 별도 capability 표를 두지 않는다. no-cloud·on-device 축은 표가 아니라 RQ4에서 정량으로 다룬다(cherry-pick 인상 방지).

**보조(정직).** end-to-end accuracy(Stage-B ON/OFF)와 minus-IR ablation은 IR이 generation에도 도움이 됨을 보인다. 이는 부수 효과이며 hero(safety)를 흐리지 않는다.

---

## 9 한계 (Limitations)

가장 큰 한계는 NL→IR intent correctness가 미해결이라는 점이다(Layer A). 사용자는 잘못 표시된 IR을 승인할 수 있고, 그 경우 verifier는 틀린 spec에 충실히 검증한다. 우리는 사람의 confirmation 행동을 이 라운드에서 경험적으로 연구하지 않으며, rendering이 결정론적·충실한 평문 surface임까지만 확립한다. 윤리: 사람 참가자 데이터를 수집하지 않으므로 "Not applicable: no human participants"다.

그 외에 coverage ceiling(n%2 counter 등), 경계 중심 동치 판정이 전체 입력 공간 보장이 아님, bounded 7일 지평, 연속 산술(SMT future), threshold 없는 변수-변수 산술(coverage 한계이며 soundness 아님), 같은 service의 두 read가 selector-free IR에서 한 device-key로 붕괴(precision은 본 논문 scope 밖), 일반화가 한계다.

---

## 10 결론 (Conclusion)

reactive-temporal IoT 자동화는 LLM으로 생성하기 쉬워졌지만, 배포해도 되는가를 판단하는 단계는 비어 있었다. OVLA는 LLM을 생성에 한정하고 배포 게이트를 결정론적·LLM-free로 만든다. 사용자가 IR의 평문 Rendering을 승인하고, 결정론 검사기가 생성된 코드를 그 승인된 IR에 대해 bounded trace-equivalence로 검사하며, 어긋나면 repair하거나 fail-closed로 거부한다. 382개 자동화에서 표시된 IR과 silently 어긋난 채 배포되던 9.2%가 0이 되었고, 이 모든 검증은 루프에 LLM 없이 edge device에서 동작한다. OVLA는 자연어 의도 정확성을 해결하지는 않지만, 승인 이후에도 남는 별개의 silent 실패 모드를 제거한다.
