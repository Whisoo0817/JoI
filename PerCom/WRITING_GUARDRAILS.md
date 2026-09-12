# PerCom 최종 집필 참고·준수사항

작성일: 2026-09-12. 마지막 확인: 2026-09-12. 입력: 같은 날 사용자가 전달한 최종 집필 메모와 후속 최우선 결정.

이 문서는 기존 논문과 코드를 수정하는 지시서가 아니라 이후 집필·도표·실험에서 참조할 기준이다. `유지`는 사용자 방향, `현재 계약`은 구현 문서의 범위, `근거 필요`는 아직 결과처럼 쓸 수 없는 주장, `향후 연구`는 현재 기여 밖의 구상이다.

## 0. 최신 최우선 결정

아래 결정은 PerCom의 Abstract, Introduction, Method, Evaluation, Related Work, Limitations, Conclusion에 공통으로 적용한다. 이전 문서가 충돌하면 이 절을 따른다.

1. **스마트홈 자동화 전체에 대한 generality를 주장하지 않는다.** Timeline의 coverage, VETS의 검증 보장, 실험 결과를 전체 스마트홈 자동화·전체 IoT automation·임의 imperative program으로 일반화하지 않는다. 논문의 대상은 아래에서 정의하는 지원 범위의 reactive-temporal automation과 선언된 JoI 실행 모델이다.
2. **Home Assistant 실험은 하지 않는다.** HA를 두 번째 backend, baseline, portability 평가 또는 generality 근거로 계획하지 않는다. 필요하면 Related Work에서 정확한 authoring/execution model을 설명하는 정도로만 사용한다.
3. **JoI가 현재 유일한 구현·평가 backend다.** 다른 플랫폼을 구현·평가하지 않은 상태에서 backend independence 또는 platform generality를 주장하지 않는다.
4. **openHAB은 시간적 여유가 있을 때만 검토하는 선택적 확장이다.** 추가한다면 Rules DSL 또는 scripting처럼 imperative code로 temporal/state/control-flow idiom을 구현하는 경로를 대상으로 한다. 실제 semantics adapter, binding, 실행 계약, 평가가 모두 있어야 논문 실험에 포함한다. 단순 예시나 소규모 데모만으로 multi-platform generality를 주장하지 않는다. 시간이 부족하면 broader relevance/Future Work 한 문장으로 남긴다.
5. **deterministic compiler는 비교하지 않은 대안이자 Future Work다.** 현재 파이프라인은 LLM lowering의 생성 다양성과 의미 보존 실패를 독립적으로 검증한다. compiler가 불가능하거나 LLM lowering보다 열등하다고 주장하지 않는다.

이 다섯 항목은 아직 수행하지 않은 HA/openHAB/compiler 실험을 평가 계획에 자동으로 추가하라는 뜻이 아니다.

## 1. 논문의 중심과 용어 — 유지

대상은 **imperative code로 구현되는 reactive-temporal automation**이다. 처음 범위를 설명한 뒤에는 `reactive-temporal code`로 줄여 쓴다.

핵심 문제는 사용자 수준의 시간적 의미와 구현 수준의 상태·제어 로직 사이의 간극이다. 일부 시간 의미는 전용 operator 하나에 직접 나타나지 않고 상태 변수, 조건문, 반복, timer 갱신 등의 구현 idiom에 분산된다. 동일 행동을 구현하는 코드가 여러 형태일 수 있으며, 그럴듯한 코드도 특정 입력 이력에서만 잘못된 ACTION을 낼 수 있다.

- `expressive` 여부로 imperative/declarative 플랫폼을 나누지 않는다. 선언형 언어도 충분한 표현력을 가질 수 있다.
- Timeline을 모든 스마트홈/IoT 자동화의 범용 IR 또는 operator 자체가 새로운 언어라고 주장하지 않는다.
- 검증 기준은 **사용자가 확정한 Timeline + binding plan**이다. selector-free IR만으로 concrete target까지 정해지는 것은 아니다.
- Timeline의 두 역할을 연결한다: 사용자 확인을 위한 명세, 생성 구현의 행동을 검사하는 executable reference.
- 사용자 확인은 의도에 맞는 명세가 확정되었다는 가정이다. 현재 연구에서 NL→IR 정확도나 사용자 이해도·가독성을 입증한 것은 아니다.
- 현재 구현·평가 backend는 JoI다. `Service.Method`당 서로 다른 selector 하나를 허용하며, 한 selector의 multi-device fan-out은 지원한다. 복수 selector 요구는 현 binding 계약 밖으로 보고한다.

중심 문장:

> VETS는 사용자가 확정한 Timeline과 binding plan을 실행 가능한 행동 명세로 삼고, 생성된 imperative JoI 코드가 선언된 실행 모델에서 그 명세의 timed ACTION trace를 보존하는지 검사한다.

근거: [최신 framing](../skill_result/06_manuscript/problem_framing_codegen_validation_2026-09-11.md).

## 2. FSM과의 관계 — 사용 여부가 아닌 구성·탐색 방식

**FSM을 안 쓰는 것이 아니다.** Explorer는 IR과 코드의 실행 의미에서 유도되는 상태 전이 시스템의 reachable product state를 탐색한다. 값·시간에 무한 영역이 있으면 원래 의미 모델 전체를 유한 FSM이라고 부르지 않고, 유한 추상화 또는 해당 기호·관계 검증 경로의 조건을 설명한다.

| 비교 항목 | 완전한 명시적 상태 그래프를 먼저 만드는 방식 | Explorer의 on-the-fly product 탐색 |
| --- | --- | --- |
| 상태 생성 | 변수·센서·timer·제어 위치의 조합을 미리 구체화하면 크기가 급증할 수 있음 | 허용 초기 상태에서 필요한 후속 상태를 생성 |
| 상태 재사용 | 변환된 그래프 위에서 도구의 축소·탐색 적용 | 미래 관찰 보존이 정당화된 상태 키·관계로 병합 |
| 입력과 시간 | 변환 모델에 해당 의미를 보존해야 함 | 지원하는 입력 분할, 정확한 만료 사건, 조건부 대기 생략·상대 시간 병합 사용 |
| 의미 대응 의무 | code→model 변환이 변수·시간·실행 순서를 보존하는지 확인 | 파서·접지·IR/JoI 실행기 및 탐색 축소가 선언 의미를 보존하는지 확인 |

이 표의 왼쪽은 특정한 **사전 명시적 전개 방식**이다. 모든 FSM/model-checking 도구를 이 방식으로 묶지 않는다. NuSMV는 전이 관계를 기호적으로 기술하고 BDD/SAT 기반 검사를 제공한다. 따라서 “FSM은 전체 상태를 만들지만 우리는 reachable state만 만든다”를 일반적인 선행기술 대비로 쓰지 않는다. [NuSMV 공식 tutorial](https://nusmv.fbk.eu/userman/v21/nusmv_2.html)

유지할 설계 근거:

> Explorer는 공통 timed input 아래에서 IR과 코드의 실행 상태를 함께 전개하므로, 요청별 행동 보존 검사에 직접 연결된다.

다음 표현은 근거가 추가로 필요하다.

- “FSM보다 효율적이다”, “NuSMV보다 빠르다”: 같은 의미·입력·완료 조건·자원 상한의 비교 없이는 쓰지 않는다.
- “같은 미래 행동이면 모두 merge한다”: 구현이 임의 행동 동등성을 판정하는 것은 아니다. 보존이 입증된 키·관계가 허용하는 병합이라고 쓴다.
- “조건 경계의 대표값만 있으면 충분하다”: ACTION 인자로 원값이 흐르거나 snapshot에 저장되면 guard만 보존해서는 부족하다. typed 값·출처 및 지원 분석 경로를 함께 설명한다.
- “on-the-fly면 상태 폭발을 해결한다”: reachable product 자체도 커질 수 있다. 완료·거절·미완료와 비용을 보고한다.

근거: [검증 계약](../explorer/docs/model/VERIFICATION_CONTRACT.md), [증명 의무 O2–O5](../explorer/docs/proof/PROOF_OBLIGATIONS.md).

## 3. Product state와 시간 — 현재 계약에 맞춰 설명

논문에서 설명용 product state는 `q = (s_IR, s_code, input_snapshot, time_context)`로 둘 수 있다. 실제 클래스의 필드 나열이 아니라 개념 표기다. 각 실행 상태에는 제어 위치, 저장 변수/GV, 활성 timer, edge 이력, 종료 상태 등이 필요하다.

시작 앵커를 `t₀`, 경과 시간을 `τ`라 하면 실행 시각은 `t = t₀ + τ`다. Clock/calendar를 읽지 않는 예제는 `τ`로 설명해도 되지만, 구현 계약의 trace는 공통 절대 시각 위에 정의된다. “time은 언제나 경과 시간뿐”이라고 일반화하지 않는다. Clock 값은 논리 시각으로부터 계산되고, 시간 이동 병합에는 clock 의존성 등의 전제가 있다.

예: `temperature > 22`이면 `AC.on()`을 호출하는 코드를 생각한다.

```text
t₀:       temperature = 20 → ACTION 없음
t₀+100ms: temperature = 23 → 이 시점에 평가하면 AC.on()
```

| 구분 | 설명할 시각 | 주의점 |
| --- | --- | --- |
| 외부 입력 | 기본 `t₀ + k×100ms`에서 변경 가능 | 사이에는 유지. 100ms보다 짧은 격자 사이 펄스는 모델 밖 |
| 즉시 반응 가능한 실행 | 위 변화에서 `t₀+100ms` | 해당 시점에 실제로 조건을 평가하는 실행 상태여야 함 |
| 1초 period 예 | 다음 평가가 `t₀+1s`인 예라면 그때 ACTION | 조건이 그때까지 유지되어야 함. 입력 변화 간격과 실행 주기는 다름 |
| delay | 진입 시각 + 정확한 duration | 만료를 100ms 격자로 반올림하지 않음 |
| wait.for | 연속 조건의 시작·취소·정확한 만료 | 단순 delay 후 재검사와 다름 |
| Clock/cron | 앵커 및 필요한 calendar 시각 | 현재 cron은 동일 시작 앵커 확인 후 소거. 다중 cron 인스턴스의 중첩 실행은 미지원 |

현재 period는 **회차 종료 후 대기 시간**이다. 회차가 1500ms에 끝나고 period가 1000ms이면 다음 시작은 2500ms다. 일반적으로 정각마다 시작하는 fixed-rate schedule로 설명하지 않는다.

같은 시각에 입력 변경과 timer 만료가 있으면 새 입력을 먼저 반영한다. 긴 대기 중 시간 이동은 양쪽 실행기가 생략 구간에서 입력을 관찰하거나 상태를 바꾸지 않는 등의 조건 아래에서만 가능하다. 입력을 읽는 wait나 필요한 Clock 경계를 무조건 건너뛰지 않는다.

근거: [검증 계약의 시간·반응 절](../explorer/docs/model/VERIFICATION_CONTRACT.md#시간반응).

## 4. LLM lowering과 compiler — 유지할 선택과 인정할 대안

현재 경로는 **LLM lowering + idiom 예시 + Explorer**다. 이번 정리는 deterministic compiler로의 변경을 뜻하지 않는다.

- 생성 과정에는 구현 선택의 다양성과 의미 보존 실패 가능성이 있다.
- 생성 과정의 비결정성과, 고정된 프로그램·모델·초기 상태·입력 이력에 대한 실행 의미의 결정성을 구분한다.
- 독립적인 reference로 생성 결과를 검증하는 역할을 연구한다. idiom 예시 자체를 의미 보존 보장으로 제시하지 않는다.
- deterministic compiler는 비교하지 않은 대안으로 인정한다. 불가능하거나 LLM보다 열등하다고 쓰지 않는다.
- 검증 후 수정은 확정 명세를 기준으로 한다. 자동 repair의 구현·평가가 정리되지 않은 상태에서 검증만으로 생성 성공률·수정 성능이 향상됐다고 쓰지 않는다.

범위 문장:

> This study evaluates independent behavioral validation in a pipeline that includes LLM-based lowering. A deterministic compiler is an alternative that we do not compare in this work.

원고의 Limitations/Future Work에서는 다음 뜻을 유지한다.

> A deterministic compiler from Timeline to JoI could remove one source of generation variability and is an important alternative for future work. This paper does not compare such a compiler with LLM-based lowering.

독립성은 생성 코드와 분리된 명세·검사 역할을 뜻한다. 실행기·프런트엔드·시험 oracle 간 구현 공유 여부는 별도로 공개해야 하며, 역할 분리만으로 독립 검증 정확도가 확보되는 것은 아니다.

## 5. LTL·model checking과의 비교 — 검증 질문을 중심으로

`nl2spec`은 자연어에서 temporal-logic 명세를 만들고, 자연어 조각과 부분 수식의 대응을 사용자가 반복적으로 수정하는 workflow다. 사용자 개입 자체 또는 자연어 시간 의도의 명세화 자체를 우리만의 기여로 쓰지 않는다. [nl2spec 원문](https://arxiv.org/abs/2303.04864)

| 항목 | Property 기반 검증 | 현재 Timeline 기반 검증 |
| --- | --- | --- |
| 기준 | 선택한 temporal properties | 확정 Timeline + binding의 실행 의미 |
| 기본 질문 | 구현 모델이 해당 속성을 만족하는가? | 같은 입력 이력에서 구현과 reference의 timed ACTION이 같은가? |
| 기대 행동 | 속성이 제약하는 행동 집합 | 지원하는 결정적 reference에서 직접 계산한 trace |
| 구현 연결 | code/runtime의 충실한 전이 모델 또는 대응 인터페이스 필요 | JoI 의미 실행기와 공통 input/time/ACTION 계약 필요 |

**일반 model checking에 완전한 property 집합이 필수인 것은 아니다.** 일부 안전성·활성 속성만 검사할 수도 있다. 다만 우리와 같은 완전한 관측 행동 보존을 주장하려면 필요한 행동뿐 아니라 불필요한 추가 행동, 시각·순서·인자도 충분히 제약하거나, reference와의 product에 관계적 속성을 두는 등 동등한 검증 질문을 구성해야 한다.

지켜야 할 비교 경계:

1. “복잡한 시간 행동의 LTL 식이 복잡할 수 있다”는 동기다. 구체 encoding 없이 표현 불가능·가독성 열등·사용성 우위를 단정하지 않는다.
2. code→NuSMV 변환에는 제어 흐름·persistent state·timer·입력/실행 순서·ACTION의 의미 대응이 필요하다. 변환 비용이 `cheap` 또는 `expensive`라는 메모는 모두 **미측정**으로 남긴다.
3. TAPInspector는 시간·지연·상호작용을 모델링하고 안전성·활성을 검사하며 모델 축소도 사용한다. “기존 방법은 시간을 다루지 못한다”는 대비는 금지한다. 다만 이 사례만으로 JoI 전체의 NuSMV 변환이 구현·검증됐다고 결론 내리지 않는다. [TAPInspector 원문](https://arxiv.org/html/2102.01468v2)
4. 기존 model checker도 상태 폭발 완화·기호 탐색을 제공한다. 우리 역시 최악의 비용 문제에서 면제되지 않는다.
5. “직접 실행”은 현재 **선언된 모델의 IR/JoI 의미 실행기**를 구동한다는 뜻이다. 실제 JoI 서버를 매 탐색 상태에서 실행하거나 code 의미 모델이 불필요하다는 뜻이 아니다.
6. 별도 NuSMV용 변환기를 사용하지 않는다는 구현 선택을 설명하되, 파싱·내부 표현·실행기 의미 대응 의무가 사라진다고 쓰지 않는다.
7. LTL/model checking으로 같은 행동 보존 문제를 표현·검사할 수 없다고 주장하지 않는다. 차이는 reference의 작성·실행 방식과 현재 구현 경로에 둔다.

근거: [기존 원문 비교 카드](../skill_result/02_literature/related_work_review_2026-09-09/safety_prior.md), [NuSMV tutorial](https://nusmv.fbk.eu/userman/v21/nusmv_2.html).

## 6. TAP의 위치 — executable semantics라는 공통점을 인정

TAP는 자동화 행동을 trigger/action 등의 구조로 작성하고 그 실행 의미로 행동을 정하는 접근이다. 특정 TAP 언어와 runtime을 지정해야 하며, 모든 TAP가 하나의 동일한 의미론을 가진다고 가정하지 않는다.

Operational semantics로 기대 실행을 정할 수 있다는 이점은 Timeline만의 독점 성질이 아니다. 개별 positive/negative property를 모두 수작업 작성하지 않고 행동을 나타낸다는 점도 공통될 수 있다. 또한 TAP 시스템에 별도 안전성·활성 속성 검사가 필요 없어지는 것은 아니다.

전형적인 역할 비교는 “TAP 표현 자체를 실행할 자동화로 사용하는 경우”와 “확정된 실행 명세를 별도로 생성한 imperative DSL 코드의 검증 reference로 사용하는 본 연구”다. 모든 기존 TAP 시스템에 후단 코드 생성·검증이 없다고 일반화하지 않는다.

## 7. Fig1·Fig2의 역할 — 별도 체크리스트 적용

- Fig1: 같은 시간 행동의 다른 구현 idiom과 잘못된 level/wait 구현을 독자가 읽을 수 있게 한다.
- Fig2: 의미를 보존하는 코드 변환에 대한 judge 판정 불변성을 조사한다. 일반적 surface bias 발견 자체를 novelty로 삼지 않는다.
- Fig2는 동기 근거이며 E2/E3의 검증기 정확도·적용률 평가를 대체하지 않는다.
- 요구사항 및 재현성 항목은 [Introduction Figure 요구사항](1_Intro/Figures/FIGURE_REQUIREMENTS.md)에 기록했다. 아직 실행·수정하지 않았다.

## 8. 향후 연구 — 저장된 IR의 수정과 다중 자동화 충돌 검사

이 방향은 사용자가 제시한 **향후 연구 구상**으로 보존한다. 현재의 단일 IR–code 쌍 인증 기능이나 이번 논문의 실험 결과로 제시하지 않는다.

### IR을 통한 수정

지원 범위의 행동 수정은 Timeline operator·파라미터·구조를 편집하는 방식으로 표현할 수 있다. 실제 배포 코드가 자동으로 바뀌는 것은 아니므로 `IR/binding 수정 → 사용자 재확정 → 코드 재생성/수정 → 재검증 → 배포 버전 연결`이 필요하다. operator 하나의 수정만으로 모든 변경 요구를 처리할 수 있다고 약속하지 않는다.

### Multi-automation Explorer 구상

배포된 코드와 동등성이 확인되고 버전이 연결된 IR들을, 공통 시간·센서·상태 아래에서 함께 실행하여 ACTION 간 충돌을 찾는 방향이다. 그 전제가 유지되면 매번 코드 분석과 개별 의미 모델 재구성부터 시작하지 않고 저장된 IR을 재사용할 수 있다. 공동 product와 환경 모델 구성·탐색 자체는 여전히 필요하다.

| 충돌 후보 | 요구되는 관찰·모델 |
| --- | --- |
| 동시 반대 명령 | 같은 대상의 on/off 등 상충 관계와 동시 실행 순서 |
| 중복 실행 | 동일 호출의 중복 정책·idempotence |
| 짧은 시간 내 덮어쓰기 | 충돌 시간창과 마지막 호출의 효과 |
| 주기적 충돌: 15분마다 + 10분마다 | 시작 위상, cadence/period 의미, 공통 시간 경계 |
| 반복 진동: on 반복 + off 반복 | 상태 변화와 반복 판정 기준 |
| 연쇄 간섭: IR1 ACTION이 IR2 조건 활성화 | ACTION→장치/환경 상태→센서·조건의 인과 모델 |

cron, period, delay, wait.for의 시간 경계를 함께 고려하는 탐색은 계획의 핵심이다. 다만 현재 cron의 앵커 처리만으로 다중 반복 스케줄 지원을 주장하지 않는다. “최초 충돌 시각”은 시간순 탐색과 최소성 조건이 확보된 뒤 주장하며, 현재 Explorer가 내는 반례가 언제나 가장 이른 반례라고 쓰지 않는다.

상태 곱 폭발을 줄이기 위해 새 IR 등록 시 binding이 겹치는 기존 IR을 우선 고르는 **점진적 탐색**을 구상한다. 직접 대상 중복만으로는 shared GV, 읽기/쓰기 의존성, 간접 물리 영향·연쇄 간섭을 놓칠 수 있으므로, 관련성 필터의 완전성 또는 누락 범위를 정의해야 한다. 공통 입력을 주는 것만으로 ACTION의 물리적 효과가 모델링되는 것은 아니다.

추가 전제: 배포 후 코드·binding·runtime 변경 감지, IR–code 버전 대응, 공동 실행의 간섭·스케줄링 의미, 단일 실행에서 얻은 보장이 공동 환경에서도 유지되는 조건. 실제 충돌 완화 효과나 성능 우위는 향후 측정 대상이다.

## 9. 사용자 요약 문장의 집필용 정리

아래는 사용자 문장의 의도를 유지하면서 현재 보장 경계에 맞춘 **문장 후보**다. 원고에 이미 반영된 문장이 아니다.

### 통합 역할

> Timeline IR serves as a specification for user confirmation and, together with a confirmed binding plan, as an executable behavioral reference for validating generated imperative automation code.

### 기존 표현과의 관계

사용자가 확정한 비교 문장 후보:

> Existing representations are not directly tailored to simultaneously support user confirmation, compositional reactive-temporal semantics, and trace-level validation of imperative automation code.

이 문장은 세 기능의 **동시 결합에 대한 비교 주장**이다. Related Work에서 실제로 비교한 representation과 계약을 특정하고 citation을 붙인 뒤 사용한다. 모든 기존 표현에 세 기능이 없다는 전 분야 부재 주장이나 `first` 주장으로 확대하지 않는다. 근거가 부족한 단계에서는 다음 긍정문을 사용한다.

> Our design connects a user-confirmed behavioral specification, compositional reactive-temporal semantics, and trace-level validation of generated imperative automation code.

선행연구 대비 novelty 문장에는 실제 비교한 표현·검증 계약의 범위를 별도로 붙인다. 사용자 확인의 용이함이나 세 요소 결합의 최초성을 이 문장만으로 주장하지 않는다.

### 한국어 핵심 설명

> 기존 연구도 자연어의 시간적 의도를 명세화할 수 있다. 본 연구는 확정된 명세를 별도로 생성된 imperative DSL 구현의 행동 검증 기준으로 사용한다. 이를 위해 공통 timed input으로부터 기대 ACTION trace를 유도할 수 있는 Timeline IR의 실행 의미를 정의하고, 확정 binding 아래에서 생성 코드와 비교한다.

### Model-checking 비교

사용자 원문의 방향:

> Conventional model checking requires a faithful transition-system model of both the imperative automation code and its event-driven runtime, as well as a complete set of temporal properties. OVLA instead directly executes the implementation and an independent operational specification under the same bounded environments, avoiding a separate code-to-model translation and detecting discrepancies through timed action-trace comparison.

이 원문은 그대로 사용하지 않는다. `OVLA`는 현재 작업명 `VETS`와 불일치하고, `same bounded environments`는 폐기된 fixed-horizon framing으로 오해될 수 있으며, “complete set of temporal properties”는 일반적인 model checking의 필수조건이 아니다. 또한 “directly executes the implementation”은 실제 JoI server가 아니라 JoI semantic interpreter를 실행한다는 신뢰 경계를 숨긴다. 현재 계약에 맞춘 문장은 다음이다.

> Property-based model checking checks a transition-system model against selected temporal requirements. VETS instead uses a confirmed operational specification as the behavioral reference and explores it jointly with the generated JoI program through their semantic interpreters under a shared execution model. This implementation avoids a separate export to a model-checker language, while retaining the obligation to justify the interpreters and exploration reductions.

`same bounded environments`는 실제 해당 실험이 유한 H 또는 제한된 환경을 사용하는 경우에만 구체 범위와 함께 쓴다. 현재 H=None 인증 전체를 bounded-only로 되돌리지 않는다. 유한 horizon 일치, H 없는 폐쇄 인증, 반례, 미완료를 구분한다.

## 10. 다음 집필 단계에서 확인할 항목

- [ ] Introduction·기여·Related Work에 같은 연구 질문과 용어를 사용한다.
- [ ] “FSM 미사용”, “모델 불필요”, “범용 model checker보다 빠름” 등의 과장을 제거한다.
- [ ] 입력 격자·period·deadline·calendar 시간과 현재 cron 범위를 일치시킨다.
- [ ] Fig1 시각 요구, Fig2 의미 보존 근거와 identity baseline을 준비한다.
- [ ] 기존 파일럿·bounded 결과·H 없는 개발 재평가를 각각 실제 범위에 맞춰 인용한다.
- [ ] 최신 E1=표현 범위, E2=validation fidelity, E3=실제 후보 적용, E4=비용·축소 효과를 유지한다.
- [ ] compiler 대안과 repair의 현재 범위를 명시한다.
- [ ] 스마트홈 전체 generality를 암시하는 `general`, `universal`, `platform-independent` 표현을 점검한다.
- [ ] HA 실험·baseline·두 번째 backend를 계획에 넣지 않는다.
- [ ] openHAB은 실제 imperative adapter와 평가를 수행하기 전에는 선택적 확장으로만 둔다.
- [ ] 다중 자동화 충돌 검사는 Future Work에 두고 현재 구현 결과와 분리한다.

작성 방식: `research-paper-plan`의 standalone 정리 원칙을 적용해 주장·근거·한계를 구별했다. 이번 산출물은 정식 claim–evidence binding pack이나 새 결과 감사가 아니며, 실험 수치의 논문 사용 승인을 추가하지 않는다.
