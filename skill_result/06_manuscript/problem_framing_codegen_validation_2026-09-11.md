# Problem framing: 범용 IoT IR이 아니라 NL→JoI 생성 결과의 행동 검증

작성: 2026-09-11. 교수님 조언과 사용자 결정을 반영한 canonical framing update.
이 문서는 Timeline을 범용 IoT 공용 IR로 정당화하거나 Home Assistant/openHAB 확장을
논문의 중심 근거로 삼던 이전 논의보다 우선한다. 기존
[`paper_flow_ir_contract_2026-09-10.md`](paper_flow_ir_contract_2026-09-10.md)의
연구 경계·검증 계약을 유지하면서, **왜 Timeline이 필요한가**에 대한 논증을 좁히고 선명하게 한다.

## 1. 최종 결정

논문은 Timeline을 모든 IoT automation을 위한 범용 IR로 주장하지 않는다.
Timeline의 필요성은 우리가 처음 설정한 다음 문제에서 직접 도출한다.

> 자연어로 요청한 reactive-temporal 자동화를 JoI와 같은 표현력 높은 실행 언어로
> 생성할 때, 생성 코드가 확정된 행동을 실제로 보존하는지 어떻게 검사할 것인가?

JoI에서는 변수, 조건문, 반복 실행, persistent state와 시간 관련 idiom을 조합하여
행동을 구현한다. 그 결과 하나의 행동을 서로 다른 코드 구조로 구현할 수 있고,
작은 timer/state/control-flow 차이가 특정 입력 이력에서만 다른 ACTION을 만들 수 있다.
따라서 문법 적합성, 코드 모양, 하나의 정답 코드, 실행 성공 여부 또는 한 번의 simulation은
행동 보존의 기준이 될 수 없다.

검증하려면 lowering 전에 기대 행동을 별도의 실행 가능한 형태로 고정해야 한다.
Timeline과 확정 binding plan은 지원하는 JoI 자동화 범위의 시간·제어·상태 행동을 명시하는
**per-automation executable behavioral specification**을 이룬다. Timeline은
selector-free reference IR이고 binding plan은 service를 concrete device 집합에 접지한다.
Explorer는 이 확정 명세와 생성 JoI를 같은 input/time/ACTION contract 아래 실행하여
timed observable ACTION의 보존을 검사한다.

현재 논문 범위에서는 `Service.Method`당 서로 다른 selector를 하나만 허용한다.
`all(#...)` selector 하나가 여러 concrete device를 선택하는 fan-out은 지원한다.
같은 service에 서로 다른 selector가 둘 이상 필요한 자동화는 표현 불가능하다고 일반화하지 않고,
현 binding/lowering contract 밖으로 분류한다. 이 제한은 selector 분할에서 생기는 call-group
provenance 문제를 본 논문의 중심 기여로 확대하지 않기 위한 의도적인 범위 선택이다.

## 2. 논문의 중심 한 문장

한국어:

> VETS는 사용자가 확정한 Timeline과 binding plan을 실행 가능한 행동 명세로 삼고, 그 명세에서 생성된
> JoI 코드가 선언된 실행 모델에서 시간·제어·상태에 따른 observable ACTION을 보존하는지 검사한다.

영문 작업문:

> VETS uses a user-confirmed Timeline and binding plan as an executable behavioral specification and checks whether
> the generated JoI program preserves its timed observable actions under a declared execution model.

framework 관점의 보조 문장:

> VETS provides a reference-centered baseline framework for connecting natural-language authoring,
> a confirmed intermediate behavioral specification, platform-code generation, and behavioral
> preservation checking.

## 3. Motivation의 필수 논리

```text
NL로부터 자동화 구현 코드를 생성한다
        ↓
JoI의 표현력 때문에 하나의 행동에 여러 올바른 구현 idiom이 존재한다
        ↓
작은 timer/state/control-flow 차이는 특정 입력 이력에서 시간적 divergence를 만든다
        ↓
syntax/schema/execution success나 단일 reference code로는 행동 보존을 판단할 수 없다
        ↓
lowering 전에 기대 행동을 독립적이고 실행 가능한 형태로 고정해야 한다
        ↓
Confirmed Timeline + binding plan = per-automation executable behavioral specification
        ↓
Timeline과 JoI를 동일한 input/time/ACTION contract에서 비교한다
        ↓
Explorer = EQUIV / DIVERGE + replayable witness / NON-CERTIFIED
```

기존 SenSys 원고의 Figure 1과 서술 구조는 이 논리를 설명하는 핵심 자산이다.
서로 다른 `prev/curr`와 flag idiom이 같은 trace를 만들고, 표면적으로 더 직관적인 구현이
반복 firing을 일으키는 사례처럼, **behavior가 같고 syntax가 다른 구현**과
**syntax가 그럴듯하지만 behavior가 다른 구현**을 함께 보여준다.

대표 지속 조건 사례도 유지한다.

> “방이 연속 5분 비어 있으면 플러그를 한 번 끈다.”

`wait(absent, for=5min); call(off)`와
`wait(absent); delay(5min); if(absent) off`는 계속 부재인 단순 이력에서는 같아 보이지만,
`absent@0 → present@4m → absent@4.5m`에서는 각각 `off@9.5m`와 `off@5m`를 만든다.
이 사례는 원문 모호성이나 사용자 이해가 아니라 **확정된 지속 조건을 JoI idiom으로
잘못 구현한 lowering error**를 보여준다.

## 4. 올바른 대비 축

논문은 `primitive/declarative platform`과 `code-based platform`을 엄격한 이분법으로
나누지 않는다. Home Assistant와 SmartThings의 선언형 rule도 변수, 분기, 대기, 반복,
실행 mode 또는 중첩 action을 제공할 수 있으므로, 앞쪽을 단순 primitive 체계로 묶으면
사실과 어긋나고 불필요한 반례를 만든다.

대신 다음 두 역할을 비교한다.

| 구분 | Confirmed Timeline | JoI implementation |
| --- | --- | --- |
| 목적 | 기대 행동을 고정 | 플랫폼에서 행동을 구현 |
| 의미 표현 | 제한된 operator와 정의된 조합 의미로 명시 | 변수·조건·주기 실행 등의 idiom에 분산 |
| 표현 형태 | 검증을 위한 정규화된 행동 구조 | 같은 행동에 여러 구현 구조 허용 |
| 실행 결과 | reference timed ACTION trace | implementation timed ACTION trace |
| 논문 역할 | 검증 기준 | 검증 대상 |

Timeline에 사용할 정확한 표현은 다음과 같다.

- `executable behavioral specification`
- `per-automation reference IR`
- `behavior-oriented IR`
- `closed and explicit behavioral model for the supported JoI scope`

`primitive IR`은 반드시 의미를 한정할 때만 쓴다. Timeline의 장점은 단순함 자체가 아니라
지원 surface가 닫혀 있고, 시간·제어·상태 의미가 명시되어 있으며, reference trace를
계산할 수 있다는 점이다.

## 5. Timeline operator의 정당화

operator를 선택한 이유는 IoT 전체에 보편적이기 때문이 아니다.
우리가 지원한다고 선언한 reactive-temporal JoI 자동화에서 행동을 명시하기 위해 필요하기 때문이다.

- `wait`: 조건 성립, edge, 지속시간과 resume를 명시한다.
- `delay`: 무조건적 시간 경과와 sustained condition을 구별한다.
- `read`: 현재 값 또는 snapshot이 이후 조건·ACTION 인자에 흐르는 방식을 명시한다.
- `call`: 관찰하는 외부 ACTION과 typed argument를 명시한다.
- `if`: guard 평가 시점과 선택한 control path를 명시한다.
- `cycle`: 반복 회차, period, 종료 조건과 state 전달을 명시한다.
- `break`: 반복 control의 명시적 종료를 정의한다.
- `start_at`: 시간 anchor가 있는 실행 시작을 정의한다.

필요한 연구 질문은 “Timeline이 범용 IR보다 우수한가?”가 아니라 다음이다.

> 선언한 대상 범위의 reactive-temporal automation을 Timeline operator와 조합 의미가
> 요구 행동의 생략·변경 없이 표현하고 실행할 수 있는가?

따라서 E1은 타 언어와의 feature 수 경쟁이나 universal coverage가 아니라,
외부 사례에서의 **scope-bounded adequacy와 unsupported boundary**를 측정한다.
언어 표현 가능성, reference interpreter 지원, Explorer 지원을 따로 판정한다.

## 6. 플랫폼 범위

### JoI

JoI는 본 논문의 유일한 구현·평가 backend다. 논문은 JoI에서 시간 행동이 변수,
조건문, persistent state와 주기 실행 idiom에 분산되는 구체적 문제를 보여주고,
Timeline→JoI lowering과 Explorer 검사를 구현·평가한다.

### openHAB

openHAB의 Rules DSL과 scripting option은 이 문제가 JoI에만 개념적으로 국한되지 않는다는
배경 사례로 사용할 수 있다. 그러나 openHAB adapter와 검증 실험이 없다면 본 논문의 지원
범위나 기여로 쓰지 않는다. Introduction 또는 Discussion에서 broader relevance를 짧게 언급하고,
platform-specific semantics/adapter를 추가하는 future work로 둔다.

또한 사용량 순위는 논증에 필요하지 않다. “Home Assistant 다음으로 많이 사용된다”는 주장은
안정적이고 비교 가능한 근거가 없으면 사용하지 않는다.

### Home Assistant와 SmartThings

두 플랫폼은 `단순 primitive platform`이라는 대조군으로 사용하지 않는다. 이들은 구조화된
action과 상당한 control expressiveness를 제공한다. 필요하면 Related Work에서 각 플랫폼의
authoring/execution model을 정확히 설명하되, Timeline의 필요성을 이들의 표현력 부족으로
정당화하지 않는다.

SmartThings 공식 문서가 Service Integrations를 Rules의 대안으로 제시하는 이유는 자신의
platform에서 logic을 실행하거나 설치 후 logic을 업데이트하거나 standalone app/API interaction을
원할 때다. 이를 “복잡한 자동화에는 외부 코드를 권장한다”로 확대하지 않는다.

확인한 공식 문서:

- openHAB Rules DSL: <https://www.openhab.org/docs/configuration/rules-dsl>
- openHAB Advanced Rules: <https://www.openhab.org/docs/tutorial/rules_advanced>
- Home Assistant Automations in YAML: <https://www.home-assistant.io/docs/automation/yaml/>
- Home Assistant Script Syntax: <https://www.home-assistant.io/docs/scripts>
- SmartThings Rules: <https://developer.smartthings.com/docs/automations/rules>

## 7. novelty와 기여의 위치

개별 Timeline operator, FSM/reachability, 결정적 실행 또는 trace comparison 자체가 새로운
기술이라고 주장하지 않는다. novelty와 기여의 중심은 다음 결합과 검증 계약이다.

> NL→DSL generation에서 확인된 intermediate behavioral specification을 lowering의 source이자
> 별도의 executable reference로 고정하고, 실제 생성 구현이 그 명세의 timed observable behavior를
> 보존하는지 검사하는 reference-centered framework.

주요 기여는 다음 세 묶음으로 정리한다.

1. **Reference-centered framework and Timeline.** NL authoring과 표현력 높은 DSL 구현 사이에
   확정 가능한 per-automation executable behavioral specification을 둔다.
2. **Behavioral preservation validation.** 공통 input/time/ACTION contract에서 confirmed Timeline과 binding plan을
   JoI의 행동을 비교하고, 완료된 인증, divergence witness, non-certification을 구별한다.
3. **Empirical characterization.** 대상 범위의 IR adequacy, interpreter/Explorer fidelity,
   실제 LLM-generated JoI 적용 결과와 탐색 비용·축소 효과를 평가한다.

이 논문은 완성된 범용 플랫폼이 아니라 **NL→DSL validation을 위한 baseline framework**를 제시한다.
후속 연구는 NL→Timeline 해석, 사용자 확인/설명, ambiguity clarification, richer control semantics,
결정적 compiler, 추가 backend, visualization, diagnosis/repair, physical/network effects로 자연스럽게 이어진다.

## 8. 명시적 anti-claims

다음은 주장하지 않는다.

- Timeline이 IoT automation 전체를 포괄하는 범용 또는 표준 공용 IR이다.
- Timeline operator 구성이 타 IR/DSL보다 본질적으로 더 새롭거나 우월하다.
- 선언형/primitive 플랫폼은 표현력이 부족하고 code-based 플랫폼만 복잡한 자동화를 표현한다.
- openHAB, Home Assistant, SmartThings에서도 VETS의 검증 보장이 이미 성립한다.
- JoI 한 backend의 결과가 backend independence 또는 platform generality를 입증한다.
- 서로 다른 selector가 여러 개 필요한 동일 service lowering을 현재 지원하거나 검증한다.
- 사용자가 Timeline을 항상 올바르게 이해하거나 NL 의도가 Timeline으로 정확히 변환된다.
- deterministic compiler가 불가능하거나 LLM lowering이 본질적으로 우월하다.

## 9. SenSys review 방어와의 연결

- **잘못된 IR 확인/사용성:** confirmed Timeline이 의도한 행동이라는 경계를 명시하고,
  NL→IR과 user comprehension은 후속 연구로 둔다.
- **bounded/full verification 과장:** 선언 모델, 지원 fragment, 완료 조건과
  EQUIV/DIVERGE/NON-CERTIFIED를 명시한다.
- **왜 LLM lowering인가:** 현재 NL→DSL workflow의 구현 선택이다. deterministic compiler도
  같은 검증 framework에 연결할 수 있으며 열등하거나 불가능하다고 주장하지 않는다.
- **verifier 과장:** timed ACTION preservation이라는 정확한 relational property와 모델 경계를 쓴다.
- **한 backend 일반화:** JoI에서만 구현·실증하고 다른 플랫폼은 future adapter로 제한한다.
- **circular evaluation:** IR-derived mutation만으로 Explorer를 평가하지 않고 독립 oracle,
  독립 fault family, held-out/externally sourced cases와 실제 LLM-generated candidate를 사용한다.

## 10. 이후 실험 설계에 주는 제약

실험은 이 framing을 넓히지 않고 증거를 제공해야 한다.

- E1은 Timeline의 universal expressiveness가 아니라 선언한 problem scope의 adequacy를 평가한다.
- E2는 semantics/interpreter/Explorer 구현의 fidelity를 독립 oracle과 positive/negative pair로 평가한다.
- E3는 confirmed Timeline과 binding plan에서 실제 생성한 JoI의 행동 보존 검사 결과를 보고한다.
- E1/E3는 `Service.Method`당 selector 하나라는 포함 조건을 적용하고, 위반 사례를
  조용히 제외하지 않고 unsupported/refused로 보고한다.
- E4는 완료 범위, 비용, reduction의 실효성을 평가한다.
- openHAB/HA 비교나 multi-backend 실험은 현재 필수 실험이 아니다.
- user study와 NL→Timeline accuracy도 현재 core claim의 필수 실험이 아니다.

이 결정 이후의 paper flow와 실험 설계는 모두 다음 질문에 답해야 한다.

> 이 내용이 `confirmed Timeline + binding plan → generated JoI → timed ACTION preservation check`를
> 설명하거나 뒷받침하는가? 아니라면 core flow가 아니라 Related Work, limitation 또는 future work다.
