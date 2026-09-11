# VETS PerCom Flow 논의 기록 — 2026-09-09

현재 대화의 결정과 다음 논의 위치를 보존한다. 최신 검증 계약·증명·평가를 대체하지 않는다.
기본 구성은 [전체 구성안](../../docs/VETS_PAPER_STRUCTURE_AND_CLAIMS.md)을 따른다.
이 문서에서는 사용자 확정, 사용자 문제 제기, assistant 제안을 구분한다.

**최신 사용자 제공 방향은 §10을 따른다:** 반복·이벤트·타이머에 걸친 시간·제어·상태 전달을
Timeline의 실행 의미로 정하고, 여기서 얻는 기준 행동을 DSL 생성과 Explorer 검증에 연결한다.
§7–8의 Explorer 중심 제안만으로 전체 서사를 축소하지 않는다.
**property 비교의 최신 보완은 §12:** 입력 탐색 범위와 오류 판정 기준을 분리하고,
무한 trace 열거가 아닌 선언 모델 아래 전 이력에 대한 조건부 인증으로 표현한다.
**표현 선택의 최신 보완은 §15:** 시간·상태를 가진 structured control flow를 생성용 명세로 선택하는 이유를 중심에 둔다.
**현재 검토할 서론 초안:** [motivation·Introduction v2](motivation_intro_timeline_2026-09-09.md). 사용자 요청으로 작성했으며 최종 문구 확정은 아니다.

## 1. 다음 대화에서 반드시 지킬 설명 방식 — 사용자 요청

- 추상적으로 다음 작업만 나열하지 말고, 구체적으로 설명하거나 비교할 후보를 제시한다.
- 매번 **전체 논문 흐름에서 지금 위치 → 구체적인 설명·후보 → 선택이 뒤에 미치는 영향**을 짚는다.
- 사용자가 지금 논문의 어느 부분을 위해 결정/논의하는지 항상 상기시킨다.
- 전체 흐름을 머릿속에 유지할 수 있도록 부분 논의를 상위 서사와 연결한다.
- 현재는 방법 절의 세부 배치보다 **Introduction의 motivation tone을 먼저 논의**한다.

## 2. 현재 전체 흐름 지도

| 위치 | 독자가 이해할 내용 |
| --- | --- |
| ① Introduction·문제 정의 | 반복 자동화의 조건 평가·저장값·이벤트 기억·타이머·회차 간 전달을 명세하고, 생성 DSL까지 보존해야 함 |
| ② System Overview | 자연어 → Timeline IR → 사용자 확인 → LLM 코드 생성 → Explorer 인증 |
| ③ Timeline IR | 연산자와 조합의 시간·제어·상태 전달 의미로 반복 실행을 정하고, 입력 이력별 기대 ACTION을 어떻게 계산하는가? |
| ④ Explorer | 생성 코드가 그 행동을 모든 허용 이력에서 보존하는지 어떻게 인증하는가? |
| ⑤ Evaluation | 실제 요청·생성 코드에 대한 적용 범위, 오류, 인증 비용 |
| ⑥ Discussion·Related Work | 확인 오류·지원 범위·신뢰 기반·기존 접근과의 차이 |

위 번호는 대화용 지도이며 최종 원고의 절 번호를 새로 확정한 것이 아니다.
확정된 IR 이후의 보장은 선언 모델과 지원/인증 완료 조건에 한정된다.

## 3. 확정한 진행 순서와 예시 배치

### A로 문제를 열고 B로 방법을 확장 — 사용자 동의

assistant가 A를 서론 대표 사례, B를 방법 절 추가 사례로 제안했고,
사용자는 “네 말에 전적으로 동의해. 그런데 motivation tone을 먼저 정하고 싶어”라고 답했다.

**A — 방이 연속으로 5분 비어 있으면 플러그를 끈다.**

| 입력 | 지속 조건을 지키는 구현 | 5분 delay 뒤 현재 부재만 재검사하는 구현 |
| --- | --- | --- |
| 0분부터 계속 부재 | 5분에 끔 | 5분에 끔 |
| 4분에 재실, 4분 30초에 다시 부재 | 9분 30초에 끔 | 5분에 끔 |

첫 부재 전에는 재실이고, 두 번째 구현은 대기 중 새 trigger를 무시하는 설명 조건이다.
①에서 선택한 실행과 최종 상태만으로 부족함을, ③에서 sustain/delay 의미 차이를,
④에서 중단·재개 입력 이력과 정확한 ACTION 시각의 필요성을 보여준다.

**B — 현재 온도를 기록하고, 1분 뒤 그 값을 알려준다.**

설명용 명세: `READ(온도 → x) → DELAY(1분) → NOTIFY(x)`.
처음 20도, 30초에 25도로 바뀌면 기준은 1분에 20도를 알린다.
지연 뒤 다시 읽는 잘못된 구현은 25도를 알린다. 온도가 일정하면 차이가 드러나지 않는다.
③에서 operator 사이의 값 전달 의미를, ④에서 저장값의 출처·수명 보존을,
⑤에서 ACTION 인자 오류 평가의 필요성을 설명한다.

두 예시는 설명용 구성 사례이며 실제 관측된 생성 오류나 실험 결과가 아니다.
각 operator가 정상이어도 조합의 시간·값 관계가 잘못 구현될 수 있음을 설명한다.
현재 Explorer를 operator별 증명을 결합하는 compositional verifier로 부르지 않는다.

## 4. Motivation tone — 사용자 문제 제기

사용자가 제시한 두 방향:

1. **사용자 중심:** 사용자는 생성 코드를 보고 구체적으로 어떻게 실행될지 잘 모른다.
   어떤 행동 후보가 있고 무엇을 선택할 수 있는지도 모른다. A/B는 그 구체 사례다.
2. **검증 중심:** 1번을 전면에 내세우면 user study 필요성을 부각할 수 있다.
   behavior specification이 명확하지 않다는 문제에서 시작하여,
   모호한 NL로부터 temporal 정보를 제공하는 구체적인 behavior spec을 이끌어내는 필요성을 강조할 수 있다.

사용자는 다른 tone 제안도 요청했다. 두 방향 중 하나를 최종 선택한 것은 아니다.

## 5. Assistant의 연결 제안 — 최종 문구는 미확정

권고: **사용자의 곤란에서 시작하되, 해결 목표를 시간 행동의 명시화와 구현 보존으로 구체화한다.**

중심 문장 후보:

> 자연어 요청이 코드로 바뀌는 과정에서 구체적인 시간 행동이 결정되지만,
> 그 결정이 명시적인 명세로 드러나고 구현까지 보존되는지는 별도의 문제다.

논리 연결:

1. 사용자가 자동화를 요청한다.
2. 코드 생성 과정에서 조건 평가 시점·대기 취소·값 읽기 시점 등의 행동이 결정된다.
3. 그 결정을 실행 가능한 명세로 드러내고 사용자 확인으로 기준을 확정한다.
4. 생성 코드가 그 기준을 모든 허용 이력에서 보존하는지 인증한다.

표현 후보는 “사용자는 행동을 알 수 없다”는 일반적 능력 단정보다
“생성된 시간 행동을 확인하려면 사용자가 코드에 분산된 조건·타이머·상태 관계를 해석해야 한다”다.
이는 확인에 필요한 작업을 설명하는 것이며, VETS로 이해·선택 정확성이 개선되었다는 실증 주장이 아니다.
사용자 관점으로 motivation을 여는 것만으로 usability 개선이 증명되지는 않으며,
“비전문가가 정확하게 이해·선택한다”는 결론에는 별도 근거가 필요하다.
기존 리뷰의 사용자 확인 능력 우려가 해결된 것으로 쓰지 않는다.

A의 “연속으로”, B의 “기록한 그 값”은 이미 명확한 요구다.
따라서 A/B를 NL의 모호함 자체에 대한 증거로 쓰지 않는다.
**생략된 시간 관계는 구체화하고, 이미 명시된 관계는 명세와 코드에 보존한다**는 두 경우를 함께 다룬다.
NL 모호성만 강조하여 논문 전체가 의도 해석 연구로 읽히거나 Explorer의 필요성이 사라지지 않도록 한다.

### 서론 문단 후보

자연어 기반 스마트홈 자동화는 사용자가 원하는 동작을 요청하면 실행 코드를 생성한다.
그러나 생성된 코드는 단순한 기기 호출 목록 이상의 결정을 포함한다. 조건을 언제 평가하는지,
대기 중 조건이 깨지면 어떻게 처리하는지, 어떤 시점의 센서값을 사용하는지에 따라 서로 다른 행동이 발생한다.
이러한 결정은 조건문·타이머·변수에 나뉘어 구현되므로, 사용자가 결과를 확인하려면 그 관계를 코드에서 해석해야 한다.

필요한 것은 요청의 시간 행동을 명시적인 기준으로 정하고, 생성된 구현이 그 기준을 보존하는지 확인하는 것이다.
자연어 요청에서 생략된 관계는 구체화하고, 명시된 관계는 실행 의미로 옮겨야 한다.
VETS는 이를 실행 가능한 Timeline IR로 표현하고 사용자 확인을 거쳐 기준으로 확정한다.
이후 Behavioral Explorer는 선언된 실행 모델에서 생성 코드가 그 기준과 동일한 시간별 ACTION을 내는지 인증한다.

## 6. 다음 논의를 재개할 위치

**현재 위치: ① Introduction의 motivation tone. 아래 §7의 Related Work 대조를 먼저 반영한다.**
사용자의 두 방향과 위 연결 제안을 놓고 출발점·강조 비중·문구를 구체화한다.
사용자가 tone 확정 전에 방법 절 상세 배치를 서둘러 진행하지 않는다.
그 뒤 A/B의 실제 제시 방식 → ③ IR·④ Explorer의 소절 흐름 → ⑤ 평가 질문·그림을 정한다.

## 7. 후속 Related Work 검토 — 2026-09-09

사용자는 motivation에 대해 “A 논문이 해결했잖아/B와 같은데”라는 반박 가능성을 확인하고,
OVLA의 related works와 최근 발견한 문헌을 통합해 달라고 요청했다.
검토 결과와 원문 근거는 [Related Work 대조](../02_literature/related_work_review_2026-09-09/README.md),
전체 인용 목록은 [inventory](../02_literature/related_work_review_2026-09-09/inventory.md)에 기록했다.

- 기존 IR/temporal 명세/사용자 확인/검증은 각각 선행연구가 있다. “명세 없음/검증 없음”으로 묶지 않는다.
- AwareAuto/CASPER 외에 Req2LTL(ASE 2025), ARTEMIS(ICSE 2026)가 motivation과 직접 겹친다.
- AutoTap/Trace2TAP의 sustain과 TSL cells의 저장값 관계 때문에 A/B를 새로운 표현력의 증거로 쓰지 않는다.
- Murphy의 reactive synthesis와 synchronous translation validation 때문에 “시간·값을 가진 생성 코드 검증” 자체도 최초가 아니다.
- Assistant 권고는 **확정한 실행 기준에 대한 생성 JoI의 timed ACTION 보존**을 중심 질문으로 두고,
  도메인 의미 연결·관찰 보존 축소·인증 조건을 기술 기여로 설명하는 것이다. 사용자 최종 확정은 아직 아니다.
- ARTEMIS는 distinguishing traces로 명세 후보를 확인하고, Trace2TAP도 후보 clustering/선택/예상 trace를 제공한다.
- A의 Intro/B의 Method 배치는 유지한다. 새 구현·실험은 시작하지 않았다.

다음 대화 위치: **Related Work 반박을 반영하여 Introduction의 중심 질문/문구를 정하기.**
자세한 후보·차이·미해결 근거는 새 검토 문서 §6/§9를 따른다.

## 8. Translation validation·ARTEMIS 정밀 대조 — 2026-09-09

사용자는 translation validation의 출판 상태와 ARTEMIS(ICSE 2026)의 방법을 자세히 확인해 달라고 요청했다.
현재 논문 위치는 **Introduction의 차별성 근거 → Related Work의 직접 선행 → Explorer의 기여 범위**다.

근거: [TV 정밀 카드](../02_literature/related_work_review_2026-09-09/translation_validation_deep.md),
[ARTEMIS 정밀 카드](../02_literature/related_work_review_2026-09-09/artemis_deep.md).

- 원조 *Translation Validation*은 TACAS 1998 정식 논문이다. 전문을 새로 확보했다.
  Ngo의 `jar15.pdf`는 정식 journal/arXiv 상태 미확인 저자 manuscript이며,
  같은 제목의 SCOPES 2015 4p 정식 abstract와 구별한다.
- ARTEMIS는 **후보 생성 → 의미 동등성 중복 제거 → 구별 trace → 사용자 답으로 후보 제거**를 수행한다.
  중복 제거는 공개 구현에서도 확인했다. 이 기능을 VETS의 독립 novelty로 쓰지 않는다.
- ARTEMIS의 구체 기술은 국소 proxy로 표시 변수를 줄이고 balanced trace로 후보를 많이 제거하는 것이다.
  로그 질문 수는 모든 후보 집합에 대한 무조건 보장이 아니다.
- ARTEMIS는 채택할 명세의 semantic validation, Explorer는 채택된 명세의 생성 코드 보존에 대응한다.
  하지만 코드 보존 원리도 TV 선행이 있으므로 “ARTEMIS+기존 TV 아닌가?”에 대한 기술적 답이 필요하다.
- ARTEMIS의 사용자 부담 평가는 전문가 명세로 답을 시뮬레이션했고, 후보 집합에 expert spec을 추가했다.
  실제 사람의 이해·선택 정확도 검증이 아니다. trace 길이 20은 lasso의 prefix+cycle 길이다.
- Assistant 권고는 본체를 구현 보존 중심으로 유지하고, ACTION 관측을 보존하는 모델·축소·탐색의 기술 기여를 구체화하는 것이다.

다음 논의 후보: **Explorer의 어떤 기술 작업이 단순한 기존 검증기 적용을 넘어서는지**, 실제 관측·축소 예로 한 문장 기여를 만들기.
이 문장이 성립하는지 확인한 뒤 Introduction motivation의 최종 표현을 정한다.

## 9. 사용자 보완: 스마트홈에서 실행할 DSL이 최종 목표

사용자는 근본적인 차이를 **스마트홈 자동화라는 문제와 실행할 DSL을 최종 산출물로 삼는 것**에서 찾아야 한다고 강조했다.
또 LTL의 부분적인 규칙 성격과 비실행성이 그 차이를 설명할 수 있는지 질문했다.
이는 **Introduction의 문제·산출물 정의와 Timeline IR 절의 설계 근거**에 관한 논의다.
직전 assistant가 차별성 논의를 Explorer 알고리즘의 novelty로 지나치게 좁힌 설명을 보완한다.

### 유지할 구분

- VETS의 최종 산출물은 현재 플랫폼에서 실행하는 JoI DSL 프로그램이다. Timeline IR는 그것을 생성·검사하기 위한 실행 가능한 행동 기준이다. IR와 최종 DSL을 혼용하지 않는다.
- ARTEMIS의 제시 산출물은 structured NL/TL 명세다. 그 명세의 의미를 검토하는 것과 스마트홈 런타임의 센서 읽기·값 저장·시간 제어·서비스 호출로 구현하는 것은 별도의 작업이다.
- 따라서 문제 차이는 단순히 application 이름이 다른 것이 아니라 **요구의 실행상 결정을 확정하고 플랫폼 프로그램까지 전달해야 한다는 산출물 의무**다.

### LTL에 대해 쓸 수 있는 말과 피할 말

1. LTL은 trace가 제약을 만족하는지 정의한다. 제약이 느슨하면 같은 입력에 여러 출력이 허용된다. 하지만 LTL이 본질적으로 부분적인 명세만 표현하는 것은 아니다. 예를 들어 입력/출력 명제 p/q에 대한 `G(q ↔ p)`는 모든 시점의 q를 p에 따라 정한다.
2. 일반 LTL 수식은 그 자체로 센서 API 호출·변수 대입·타이머 실행을 제공하는 JoI 프로그램이 아니다. 하지만 LTL에서 전략/제어기를 합성하는 도구가 있으므로 executable implementation으로 변환 불가능하다고 쓰지 않는다. [Strix 공식 구현](https://github.com/meyerphi/strix), [CAV 2018 논문](https://link.springer.com/chapter/10.1007/978-3-319-96145-3_31).
3. 보통의 명제 LTL에는 typed sensor value를 읽어 변수에 저장하고 나중에 ACTION 인자로 넘기는 연산이 기본으로 주어지지 않는다. Boolean abstraction이 그 값 차이를 지우면 해당 차이를 검증할 수 없다. 유한 값 인코딩, 상태 변수, 데이터 논리 확장으로 대응할 수 있으므로 원리적 불가능성으로 확대하지 않는다. TSL이 control/data 분리와 저장값을 다루는 직접 선행이다. [TSL CAV 2019](https://finkbeiner.groups.cispa.de/publications/2019-temporal-stream-logic-synthesis-beyond-the-bools/).
4. 일반 LTL의 next/단계 자체가 물리 시간 단위를 정하지 않는다. 60초·timer 취소·동시 input/deadline 순서에는 clock/runtime 모델을 연결해야 한다. 시간 제약 표현이 불가능하다는 뜻은 아니며 ARTEMIS/FRETish도 within N ticks를 제공한다.
5. Boolean `notified` 또는 `light_off`만 관측하면 같은 시점의 호출 횟수·인자·순서가 숨겨질 수 있다. richer trace alphabet/상태 모델로 인코딩할 수 있고, 우리 DSL/IR는 이 실행 정보를 명시하고 실제 ACTION 관측에 연결한다.

### 구체 예와 논문 문장 후보

요구 B: “지금 읽은 온도를 1분 후에 그 값으로 한 번 알린다.”
`G(request → F notified)`라는 약한 예시 속성에는 읽기 시점·저장값·정확한 1분·호출 횟수가 빠져 있다.
이 수식은 ARTEMIS가 B에 대해 생성한 결과가 아니라 부분 속성과 실행 기준을 비교하기 위한 구성 예다.
그 정보를 모두 명시하려면 LTL 쪽에도 데이터/시간/출력 사건 모델과 충분한 제약이 필요하다.
Timeline IR는 `READ(x) → DELAY(60s) → CALL(notify,x)`라는 설명용 순서와 실행 규칙으로 그 기준을 정한다.
이 표기는 실제 parser 문법을 보장하는 코드 예가 아니며, 최종 JoI lowering 뒤 기준 행동 보존을 검사한다.

중심 문장 제안:

> 우리의 목표는 자연어 요구를 시간논리 제약으로 형식화하는 데서 끝나지 않고,
> 스마트홈에서 실행할 DSL 프로그램을 생성하는 것이다. 이를 위해 조건 평가·대기·저장값·서비스 호출의
> 실행 의미를 명시적인 행동 명세로 확정하고, 그 명세를 생성 지침과 생성 결과의 검증 기준으로 함께 사용한다.

이 문장을 ARTEMIS 대비 **문제/산출물 차이**로 사용할 수 있다. LTL의 전면적인 표현 불가능성이나
새 temporal formalism의 최초성으로 쓰지 않는다. AutoTap·TSL/Murphy·translation validation까지 모두
배제하는 차별성은 아니므로 해당 선행과의 비교는 유지한다.

다음 논의 위치는 Explorer 세부로 바로 넘어가기보다 **IR가 DSL 생성 전에 반드시 확정할 실행 정보를 A/B에서 추출하여 motivation과 IR 설계 이유를 연결하기**다.
본체 흐름과 LLM lowering 유지, deterministic compiler의 future-work 배치는 변경하지 않는다.

## 10. 사용자 제공 대화 반영: Timeline은 반복 자동화의 실행 행동 명세

사용자는 별도 대화를 제공하며 다음 방향을 참고하도록 요청했다. 논문 내 위치는
**Introduction의 IR 필요성 → Timeline IR의 정의 → Explorer의 역할**이다.

### 중심 서사로 유지할 내용

- 스마트홈 DSL 생성에는 개별 trigger–action 조건에 더해, 반복 일정·조건 평가 시점·회차별/회차 간 값의 수명·edge 기억·timer 수명·동시 사건 처리 순서가 필요하다.
- Timeline IR는 연산자의 실행 규칙과 연산자 사이의 제어·상태 전달 규칙으로 이 관계를 정한다.
- 각 요청에 모든 내부 전이 규칙을 펼쳐 쓰는 것은 아니다. **IR에 적힌 구성 + 언어의 실행 의미 + 선언 모델**이 함께 행동을 결정한다.
- 초기 상태와 외부 입력 이력이 주어지면 지원 명세의 시간별 ACTION을 계산할 수 있다. 실행 가능성은 행동이 충분히 결정된 데서 나오는 성질이며, 생성 지침과 검증 기준을 연결한다.
- Explorer는 이 기준과 별도 생성 DSL 사이의 행동 보존을 검사한다. Timeline의 설계 역할을 단순 verifier 입력 형식으로 축소하지 않는다.
- “모든 관계가 명세됨”은 지원 단일 자동화의 선언 의미 안에서 읽는다. 모든 물리 동작·병렬 자동화·플랫폼 스케줄러 전체를 이미 명세/검증했다는 뜻은 아니다.
- LTL/TAP이라는 이름만으로 해당 관계를 표현할 수 없다고 분류하지 않는다. 비교 단위는 각 연구가 제공한 실행 의미와 명세→플랫폼 코드 연결이다. 기존 관련연구의 접기/가르기 선행 판단은 유지한다.

### 제공 예시의 위치와 현재 계약 대조

사용자 제공 예: “매 10분마다 온도를 읽고, 이전 측정값보다 2도 이상 높으면 2분 후에 이번에 측정한 값을 알린다.”
이는 반복 일정, 이전 회차 값, 이번 snapshot, 조건부 delay의 관계를 설명하는 **후보 예시**다.
현재 평가에서 이미 인증한 태스크라고 표시하지 않는다. 최초 측정의 처리, 반복 기준, 상태 갱신 위치를 정해야 구체 reference가 된다.
기존 A의 Intro/B의 Method 배치를 이 예시로 자동 교체하지 않는다.

현재 [규범적 런타임 계약](../../explorer/docs/model/RUNTIME_CONTRACT.md)의 구체 연결:

| 항목 | 현재 정의/한계 |
|---|---|
| period | 본문 완료 뒤 period를 기다림. 0분 시작·2분에 본문 완료·period 10분이면 다음 시작 12분 |
| cron | 같은 시작 앵커를 확인하는 준비 경로. 여러 cron 인스턴스의 중첩 실행을 인증한 것은 아님 |
| edge 기억 | 래치는 회차 사이 유지. 해당 wait/edge 코드가 관찰할 때 갱신하며 다른 대기 중의 모든 센서 edge를 누적하지 않음 |
| timer/input | 같은 논리 시각에는 새 입력을 먼저 반영한 뒤 timer/wait 처리 |
| tick | 반복 회차, 외부 입력 snapshot 시점, timer 재개 시점을 같은 뜻으로 혼용하지 않음 |

이 규칙은 현재 모델의 선언 의미이며 실제 운영 서버의 측정 결과가 아니다.
특히 “매 10분”과 `period=10분`을 자동 동의어로 쓰지 않는다. **반복 기준 자체가 명세해야 할 행동 결정**이라는 좋은 예다.

### 서론–방법 연결 문장 후보

> 스마트홈 자동화의 행동은 개별 조건과 동작뿐 아니라 반복 일정, 조건 평가 시점, 저장값의 수명과
> 이벤트·타이머 상태의 전달에 의해 결정된다. Timeline IR는 지원 연산과 그 조합의 실행 의미를 정의하여,
> 초기 상태와 입력 이력에 대한 기준 행동을 계산할 수 있게 한다. VETS는 이 명세를 바탕으로 DSL을 생성하고,
> Explorer로 생성 결과의 행동 보존을 검사한다.

다음 논의는 **Introduction에서 이 필요성을 가장 짧게 보여줄 사례 구성**이다.
후보는 기존 A를 반복 문맥에서 설명하거나, 제공한 온도 비교 예를 IR 절의 종합 예로 쓰는 것이다.
예시 변경·최종 문단은 추가 논의 대상으로 둔다.

## 12. 사용자 제공 대화 반영: 예상하지 못한 입력과 추가 행동의 구별

사용자는 property 기반 접근의 예상 밖 행동 처리와 Timeline의 전 이력 검증을 구별한 대화도
참고하도록 요청했다. 위치는 **Related Work의 비교 기준, Timeline의 기준 행동 역할, Explorer의 보장 문구**다.

### 비교에서 분리할 세 축

| 축 | 유지할 설명 |
|---|---|
| 실행·시뮬레이션 가능성 | LTL 수식, 모델 검증기의 전이 모델, 실행 가능한 TAP 프로그램을 같은 종류로 묶지 않는다. TAP나 model-checker 모델도 실행·시뮬레이션할 수 있다. |
| 입력/실행의 포괄성 | property model checking도 선언 모델에서 사람이 테스트로 예상하지 않은 입력·실행을 탐색할 수 있다. 전 이력 탐색 자체를 VETS만의 기능이라고 하지 않는다. |
| 오류 판정 기준 | 속성이 허용한 추가 행동은 그 속성의 위반이 아니다. Timeline–DSL 관측 동등성은 기준에 없는 ACTION도 차이로 판정한다. |

사용자 제공 근거 링크: [NuSMV 설명](https://nusmv.fbk.eu/userman/v21/nusmv_2.html),
[AutoTap 원문](https://hewj.info/papers/autotap.pdf). 이 절은 제공된 논의의 반영이며 이번 턴에 새 전문 검토를 수행한 기록은 아니다.
기존 AutoTap 검토는 [formal F3](../02_literature/related_work_review_2026-09-09/formal_prior.md#f3-zhang-et-al--autotap)를 따른다.

### 추가 알림 예시와 의미

- 부분 속성: 온도가 기준을 넘으면 알림이 발생해야 한다.
- 확정 Timeline: 기준을 넘는 순간 한 번 알린다.
- 잘못 생성된 코드: 해당 순간 알리고 다음 회차에도 다시 알린다.

첫 속성만 검사하면 추가 알림이 있어도 만족할 수 있다. 반면 ACTION 관측 동등성은 기준에 없는 두 번째 호출을 차이로 잡는다.
이는 **검사할 개별 오류 유형을 사전에 모두 열거하지 않아도, 실행 기준에서 추가·누락·시각·인자·횟수·명시 순서 차이를 도출한다**는 설계 장점을 설명한다.
충분한 금지/정확성 속성 또는 두 실행의 product mismatch 검사로 같은 오류를 찾을 수도 있으므로 property 기반 도구의 원리적 불가능성을 주장하지 않는다.
또한 VETS가 별도 property checker까지 구현했다는 뜻으로 “개별 속성 위반뿐 아니라”라는 문구를 사용하지 않는다.

### 우리 포괄성의 정확한 문구

“입력·변수·시간의 모든 곱집합에서 모든 trace를 뽑는다” 대신 현재 [검증 계약](../../explorer/docs/model/VERIFICATION_CONTRACT.md)에 맞춰 다음을 사용한다.

> 지원 검사와 H 없는 인증 작업을 완료한 IR–DSL 쌍에 대해,
> 선언 모델의 모든 허용 초기 상태와 입력 이력에서 timed ACTION이 같음을 보장한다.

내부 변수·timer는 실행 규칙으로 전개된다. 각 시점마다 임의 내부 값의 곱집합을 취하는 것이 아니다.
무한히 많은 trace를 하나씩 출력하지 않으며, 해당 경로의 상태 병합·기호 표현·탐색 폐쇄와 관찰 보존 근거로 이력을 포괄한다.
지원 밖·자원 상한·미완료는 동등 인증이 아니다. 시뮬레이션 가능성과 전 이력 인증은 분리한다.
관측에서 숨긴 내부 차이, 잘못 확인한 Timeline의 의도, 선언 모델 밖 물리 행동은 이 인증이 해결하지 않는다.

중심 문장 후보:

> Timeline의 실행 의미는 입력 이력별 기준 행동을 제공한다. VETS는 개별 오류 유형마다 속성을 작성하는 대신,
> 이 기준과 생성 DSL의 관측 가능한 행동 차이를 검사한다.

이는 §10의 Timeline 중심 서사를 보완한다.

## 13. 빠른 중복 실행은 직접적인 차별 사례인가?

사용자는 “기존 연구가 못 하고 우리가 할 수 있는 것”의 예로 잘못 설계되어 매우 빠르게 중복 실행되는 상황을 제시했다.
현재 위치는 **Introduction의 실제 오류 유형, Related Work의 관측/검증 대상 차이, 평가 후보**다.

### 이번 확인에서 새로 얻은 근거

- [TAPInspector 원문](https://arxiv.org/pdf/2102.01468v2) Table I T1과 §III: 두 규칙의 중복 action을 검사하며 반복 알림·거래를 직접 예로 든다. 중복 검출 자체를 VETS만의 기능이라고 쓰지 않는다.
- 같은 논문의 §IV-A Eq.(8)은 trigger 이전값을 기억해 state 조건이 계속 true일 때 발생하는 FSM의 매 step 실행을 막는다. TAP 의미론에 edge 기억이 없다는 주장은 틀리다. 잘못 생성된 DSL의 실제 제어 흐름까지 이 모델에 보존되는지는 별도 frontend 문제이며 미검증이다.
- 현재 VETS ACTION 관측은 같은 시각의 동일 호출도 개별 호출로 보존한다. [관측 계약](../../explorer/docs/model/VERIFICATION_CONTRACT.md), [중복 회귀 테스트](../../explorer/tests/test_symbolic_value_flow.py).
- 기존 테스트 `test_duplicate_calls_remain_observable`, `test_timing_difference_at_inclusive_horizon_is_observable`를 Python 3.12의 임시 uv 환경(openai import 의존성 포함)에서 실행하여 **2개 통과**했다. 전자는 IR 대비 실제 candidate에 호출을 추가한 뒤 confirmed DIVERGE, 후자는 delay 100ms→101ms 변경의 horizon 경계 불일치를 확인한다.
- 기본 Python 3.8은 타입 문법, 시스템 Python 3.12는 openai import 부재로 처음 로딩 실패했다. 의존성을 갖춘 임시 환경에서 성공했다. 소스 변경이나 LLM 호출은 하지 않았다.
- 이 실행은 기존 bounded regression 두 개다. 아래 period 반복 예, prior 도구 비교 실험, 일반 무한 반복 검출의 실증으로 확대하지 않는다.

### 구체 비교 후보

입력 온도가 계속 26도일 때, reference는 60초마다 한 번 `switch.on()`을 호출하나 잘못 생성된 DSL은 100ms마다 호출한다고 하자.
기준 호출은 0초·60초…, 후보 호출은 0초·0.1초·0.2초…다. 0.1초의 추가 ACTION이 최초 차이다.
처음 off였다가 첫 호출에서 on이 되고 이후 동일한 상태를 유지하는 장치를 가정하면 두 실행의 장치 상태 이력은 같다.

**조건부로 확실한 불가능성:** 동일 시각 기준의 기기 상태만 관측하여 두 실행이 같은 명제열로 투영되면,
그 명제들만 쓰는 어떤 LTL 속성도 둘을 구분할 수 없다. 관측에서 지워진 호출 빈도는 속성을 추가하는 것만으로 복구되지 않는다.
호출 사건·시각·횟수를 모델에 추가하면 달라진다. 이 정보 손실 주장을 모든 TAP/ARTEMIS 구현에 적용하지 않는다.

**실질 비교 후보:** 다중 규칙의 구조적 중복과, 단일 요청의 반복/edge/delay 구현 오류로 reference보다 많거나 빠른 호출이 생기는 문제를 나눠 비교한다.
ARTEMIS는 생성 DSL 입력을 실행해 이 차이를 인증하는 workflow를 제시하지 않는다. Timeline–DSL 검사에는 해당 비교 계약이 있다.
TAPInspector 등과의 같은 태스크 비교는 미실행이므로 “이 사례를 못 잡는다”는 결과를 기재하지 않는다.

### 기준 자체의 잘못과 구현 불일치

- Timeline은 60초, code는 100ms: 지원되는 비교 경로에서는 ACTION 불일치 대상.
- Timeline과 code가 모두 100ms: 동등성만으로 과도한 호출이라고 판정하지 않는다. 허용 호출률 등의 별도 요구/정책이 필요하다.
- 무행동 CPU busy loop 또는 같은 논리 시각에 무한 호출: 현재 timed ACTION 계약의 비용 관측/유한 반응 전제와 다르다. 모든 runaway 실행을 구체 불일치로 반환한다고 주장하지 않는다. 지원 거절·실행 한도·미인증을 구별한다.

추천 문장 후보:

> 기기 상태가 동일하게 유지되더라도 생성 DSL은 반복·상태 관리 오류로 기준보다 많은 서비스 호출을 발행할 수 있다.
> VETS는 Timeline의 기준 timed ACTION과 비교하여 이러한 추가 호출과 잘못된 호출 간격을 검사한다.

이 후보는 Timeline의 관측 설계 필요성을 강화한다. 독립 novelty의 확정이나 새 baseline 실험 개시 결정은 아니다.

## 14. Motivation·Introduction 초안 작성

사용자는 앞선 논의를 고려해 motivation과 Introduction을 작성하도록 요청했다.
[한국어 초안 v1](motivation_intro_timeline_2026-09-09.md)에 중심 주장, 다섯 문단의 역할, 실제 본문과 근거를 기록했다.

- 중심: **개별 동작이 맞게 생성되어도 반복 실행의 시간·상태 관계가 틀리면 자동화는 잘못 실행된다.**
- 문단 순서: 반복 실행의 명세 필요 → A의 시간 오류 → formalization/property 선행과 이번 문제 → Timeline IR → Explorer.
- A는 Intro 대표 사례로 유지하고, B는 IR 절로 연결한다. 빠른 중복 호출은 관측 설계의 보조 사례로 둔다.
- Timeline을 생성 지침과 실행 기준으로 먼저 설명한 후, Explorer의 보존 검사로 연결한다.
- 사용자 성능·새 평가 수치·검증된 compiler를 현재 기여로 넣지 않았다.
- 다음 검토 위치는 **서론의 중심 주장과 A의 설명이 ‘반복 실행의 관계’라는 motivation을 충분히 보여주는지**다. 초안 작성 요청을 최종 wording 승인으로 간주하지 않는다.

## 15. 사용자 방향: 생성용 명세로서 structured temporal control flow

현재 위치는 **Introduction의 IR 선택 이유 → Timeline IR 절의 설계 원칙 → Evaluation의 표현 가설**이다.
사용자는 “주말 오후에 1시간마다 온도를 재서 3번 이상 25도를 넘으면 메일”이라는 복합 요청을 제시했다.
LTL의 허용 trace 조건과 자동화의 순차·반복 실행 절차를 구별하고, Timeline의 형태 자체를 정당화하도록 요청했다.

### 사용자 방향과 채택할 설명

- 실행 가능·결정론·closed surface라는 성질에 앞서, 자동화의 시간 연산과 상태 갱신을 순서·반복 구조로 직접 표현하는 이유를 설명한다.
- 의미를 담는 primitive와 조합 규칙을 통해 실행을 정의한다. control flow와 함께 누적값·저장값의 수명도 중요하다.
- 최종 목표는 DSL 프로그램이며, Timeline의 실행 의미가 생성 지침과 검증 기준을 함께 제공한다.
- ARTEMIS의 structured NL 선택처럼, 우리도 생성 대상 표현의 선택 이유를 명시해야 한다.

### assistant 제안과 한계

정의 후보:

> Timeline IR is an executable behavioral specification that represents smart-home automation through structured temporal control flow and explicit state updates.

중심 문장 후보:

> 스마트홈 자동화의 행동 명세는 무엇이 성립해야 하는지와 함께,
> 시간에 따라 실행이 어떻게 진행되고 상태가 이어지는지를 직접 표현해야 한다.

표준 LTL은 시간 단위·변수 대입을 자동화 연산으로 직접 제공하지 않는다. 그러나 고정 유한 횟수는 수식으로 표현 가능하고,
시간/상태 인코딩·확장 논리·합성을 활용할 수 있으므로 “반드시 AP 추가”, “필연적 수식 폭발”, “구현 IR로 사용 불가”는 쓰지 않는다.
핵심은 **필요한 의미를 어떤 추상화에서 직접 제공하는가**이며, LLM 정확도 우위는 별도 평가 가설이다.

ARTEMIS 원문 §§1–2를 재확인했다. 논문은 NL 추론과 structured NL의 TL 매핑을 동기로 제시하고 자신들의 번역 결과를 평가한다.
그 결과를 Timeline의 실증으로 전용하지 않는다. [ARTEMIS](https://cs.stanford.edu/people/trippel/pubs/mendoza_ICSE26.pdf).
전이 모델과 속성의 구분은 [NuSMV](https://nusmv.fbk.eu/userman/v21/nusmv_3.html),
논리 기반 데이터·제어 및 구현 합성의 선행은 [TSL](https://finkbeiner.groups.cispa.de/publications/2019-temporal-stream-logic-synthesis-beyond-the-bools/)로 교차 확인했다.

AST는 저장 형식이므로 AST가 아니라는 주장을 하지 않는다. 행동 단위의 의미를 정의하는 것이 JoI 문법 복제와 다른 점이다.
현행 backend가 JoI임을 유지하며 다중 플랫폼 이식성의 실증을 주장하지 않는다. compositional semantics와 조합적 증명도 구별한다.

### 반영한 산출물

[Introduction v2](motivation_intro_timeline_2026-09-09.md)의 3·4문단과 정의를 수정하고, §6에 예시·용어·비교 근거를 추가했다.
예시는 오후 12–18시, 하루 누적, 세 번째 초과 직후 한 번이라는 **설명용 해석**이다. 사용자 확정 의도가 아니다.
개념 블록은 현행 IR 문법이나 인증된 전체 주말 scheduler가 아니며, anchored schedule과 completion-based period를 구별했다.
A의 대표 사례 배치와 B의 IR 절 배치를 변경하기로 확정하지 않았다. 새 실험·IR 구현은 시작하지 않았다.

## 16. TAP·자동화의 IR/FSM, 실행 가능성, 최종 DSL 비교

사용자는 자체 IR 또는 FSM을 쓰는 TAP·자동화 논문들을 표로 정리하고, IR의 직접 실행 여부와
최종 목표가 DSL인지 표시하도록 요청했다. 위치는 **Related Work 직접 비교와 Introduction의 IR 선택 근거**다.

[비교표와 원문 카드](../02_literature/related_work_review_2026-09-09/automation_ir_execution_matrix.md)에
AwareAuto, ChatIoT, CASPER, Trace2TAP, TAP-Debug, AutoIoT(Cheng), AutoTap, TAPInspector,
TAPFixer, Soteria, IoTSan, ThingML의 12개 연구를 정리했다. TSL은 인접 참고로 연결했다.

- 직접 규칙 실행, 모델 내 실행/탐색, 코드 변환 후 실행, 독립 실행 미확인을 구별했다. 미확인은 표현 불가능성이 아니다.
- AwareAuto는 grounded TA-pair JSON을 automation manager에 전달한다. 형식적 독립 reference interpreter까지 확인했다는 뜻은 아니다.
- Soteria는 component IR 이후 state model이 있으며 두 단계를 하나의 직접 실행 IR로 취급하지 않는다.
- TAPFixer는 §5.4에서 rule-syntax patch 이후 플랫폼 프로그램 수정은 수작업으로 남긴다고 명시한다.
- **신규 ThingML(MODELS 2016):** statechart/action language/component 기반 자체 DSL → C/C++·Java·JavaScript.
  IoT 및 Safe@Home 사례도 있어 FSM을 배포 코드 생성용으로 쓰는 직접 인접 선행이다. DOI와 원문 metadata를 OpenCite로 교차 확인했다.
- **추가 확인 AutoIoT:** §V-C는 NL 규칙뿐 아니라 Python 자동화 스크립트와 Raspberry Pi 실행을 기술한다.
  검증 모델 생성만 수행한다고 축소하지 않는다. MobiCom 2025 AutoIOT와는 다른 논문이다.

다음 정밀 비교 추천은 AwareAuto(복합 규칙 표현), ThingML(statechart→구현),
AutoTap/Trace2TAP(실행 모델·합성), AutoIoT(LLM 생성·formal model·실제 코드)다.
자체 IR 또는 실행 코드 목표 자체보다 **생성 표면의 시간·상태 조합과 reference–implementation 보존 계약**을 구체화한다.
이번 문헌 검토에서 prior 도구 실험과 기존 A/B 배치 변경을 수행하지 않았다.

## 17. 사용자 방향: 의도 확정과 플랫폼 구현 보존의 두 파트

현재 위치는 **Introduction의 전체 논리 → System Overview의 두 파트 → Timeline IR 설계 근거**다.
사용자는 첫 파트를 NL → 사용자 확정 Timeline IR, 두 번째를 Timeline IR → 플랫폼 DSL 생성 → 행동 검증으로 분리했다.
최종 목적은 상용 IoT 플랫폼에서 실행할 DSL 프로그램이며, Timeline 자체를 만드는 데서 끝나지 않는다는 점을 강조했다.
현재 구현 대상은 JoI이고, 다중 상용 플랫폼 적용의 완료를 주장하는 것은 아니다.

### 사용자 방향

- 앞 파트: 복합 시간·이벤트·타이머·상태 관계를 명시한 행동 명세를 만들고 사용자가 해석을 확정한다.
- 뒤 파트: LLM이 Timeline과 대상 DSL 설명을 받아 reactive-temporal 코드를 생성한다.
- 플랫폼 구현에서 행동 의미가 보존되었는지 행동 trace로 검사하고, 불일치 이력을 구체적인 진단 근거로 제공한다.
- Temporal explicitness, structured control flow, executable semantics를 각각 이 목적에서 도출한다.

### assistant 제안: 중심 논리와 문장

> 자연어에서 채택한 시간적 행동을 명시적으로 확정하고, 그 행동이 플랫폼 구현에서도 보존되는지 검사하기 위해 Timeline IR을 둔다.

파트 1의 질문은 “이 요청을 어떤 실행 행동으로 해석할 것인가?”이고,
파트 2의 질문은 “생성된 플랫폼 코드가 그 행동을 실제로 보존하는가?”다.
사용자의 확인은 첫 질문의 기준 채택이며, 두 번째 질문의 증명을 대신하지 않는다.

Timeline의 성질과 역할을 다음처럼 연결한다.

| 설계 성질 | 목적에서 나오는 필요 |
|---|---|
| Temporal explicitness | 평가 시점, 지속·대기, 반복 시작과 재개, 취소·초기화 정책을 드러내어 해석을 확정 |
| Structured control flow + explicit state updates | 시간 연산의 순서·반복·분기와 저장값·카운터의 수명을 조합 가능한 행동 단위로 표현 |
| Defined primitive/compositional semantics | 각 연산의 내부 동작을 매 생성 시 새로 고안하지 않도록 의미를 고정 |
| Executable, input-deterministic semantics | 선언 모델의 초기 상태와 입력 이력에서 검증 기준인 timed ACTION을 계산 |

정의 후보:

> Timeline IR is an executable behavioral specification that makes temporal control flow and state updates explicit, providing a common reference for intent confirmation and preservation in generated platform code.

### 논리를 강화하기 위한 표현 조정

- “Temporal explicitness/control flow가 필요하므로 반드시 LTL은 불가능”으로 결론 내리지 않는다.
  지원 도메인의 실행 결정을 직접 구성하는 표현을 선택한다는 설계 근거로 설명한다.
- JoI 같은 플랫폼 코드에도 명확한 실행 의미와 제어 흐름은 있다. 차이는 행동 단위의 추상화 수준이다.
  지속 조건 하나를 구현하면서 관측, 대기, 상태 기억, 취소·재시작을 여러 코드 연산으로 조율해야 하는 경우를 구체화한다.
- syntax description은 적법한 코드의 작성 정보를 주지만 그 사실만으로 행동 보존을 보장하지 않는다.
  생성에는 API/실행 의미 설명도 관련되며 검증기는 대상 DSL의 실행 의미를 알아야 한다.
- “복잡하면 자주 틀린다”는 빈도 주장은 평가가 필요하다. 서론 논리는 문법적으로 적법해도 시간·상태 관계를 잘못 구현할 수 있다는 실패 기제로 세운다.
- “명세가 있으므로 검증해야 한다”보다 “LLM lowering의 의미 보존이 보장되지 않으므로 검사하며, 실행 가능한 명세가 기준 행동을 제공한다”로 연결한다.
- counterexample은 입력 이력과 기대/실제 ACTION 차이를 제시하여 원인 분석을 돕는다. 소스 수준 근본 원인을 자동으로 확정한다고 쓰지 않는다.
- NL 입력 자체와 property 입력의 차이는 앞 파트의 입력 전제 비교다. 그것만으로 IR 설계 또는 전체 pipeline의 novelty를 결론 내리지 않는다.

### 두 파트를 연결하는 본문 후보

스마트홈 자동화의 자연어 요청을 플랫폼 프로그램으로 옮기려면, 먼저 시간과 상태에 관한 실행 결정을 확정하고,
이후 그 결정을 대상 플랫폼의 실행 방식으로 구현해야 한다. 반복 일정, 조건의 관측 시점, 타이머의 취소와
저장값의 수명은 같은 서비스 호출을 사용하는 프로그램 사이에서도 행동 차이를 만든다. 우리는 이러한 결정을
시간 연산과 구조화된 제어 흐름으로 표현하는 Timeline IR을 제시한다. 사용자가 확정한 Timeline은 LLM의
플랫폼 코드 생성에 행동 기준을 제공한다. 그러나 이 행동 단위를 플랫폼의 제어 구문과 상태 관리로 옮기는
과정에서는 문법적으로 적법한 코드도 다른 행동을 만들 수 있다. 따라서 Timeline에 실행 의미를 부여하여
각 입력 이력의 기준 ACTION을 계산하고, 생성 코드가 동일한 입력에서 그 행동을 보존하는지 검사한다.
불일치가 발견되면 입력 이력과 기대·실제 호출의 차이를 반례로 제공한다.

이 문구는 검토용 제안이며 최종 승인 문장이 아니다. 기존 Introduction v2 전체를 교체하지 않았고,
사용자 이해도 개선, 신규 오류율 결과, 자동 원인 국소화를 현재 기여로 추가하지 않았다.

## 20. 외부 baseline과 유사 파이프라인의 실제 평가 방식

사용자는 Direct/prose/Timeline만 비교하는 기준이 애매하고, 의도 확정과 구현 정확성을 함께 다루는 타 논문이 무엇을 평가하는지 질문했다.
[원문 기반 평가 검토](../05_experiment_plan/prior_pipeline_evaluations_2026-09-10.md)에 ChatIoT, AwareAuto, AutoTap, ARTEMIS의 실제 baseline/정답 기준/단계별 실험을 기록했다.

- 기존 A/B/C는 기본 비교와 표현 ablation으로, 외부 방법 비교를 완전히 대체하지 않는다.
- AwareAuto는 intent consistency/grounding/전체 성공을 나누고, grounding만 측정할 때 앞단 규칙을 사람이 교정한다.
- AutoTap은 의도 표현 사용자 비교, 확정 property에서의 합성 성공, mutation repair를 나눠 평가한다.
- ChatIoT는 Zero-shot/CoT/ReAct와 자체 ablation, 수작업 정답 대비 생성 정확도/token을 사용한다.
- ARTEMIS는 전문가 명세 대비 후보 포함 정확도와 시뮬레이션한 명세 검토 비용을 나눈다.
- VETS도 의도 일치와 확정 명세 보존을 분리하며, 사용자 확인 사실만으로 전자의 보장을 주장하지 않는다.
- 중심 성과 후보는 검증된 결과 제공률 + 잘못된 통과 + 미완료/거절 + 비용이다. 단순히 검증을 붙였다고 생성 코드가 수정된 것은 아니다.
- 외부 baseline 후보는 재현 가능성을 확인한 ChatIoT 방식 등의 JoI adaptation이며 미확정이다.

## 21. 사용자 결정: 기술적 IR 관점과 올바른 명세 확정 가정

사용자는 교수님의 의견에 맞춰 Timeline을 LLVM IR/FSM과 같은 **기술적 중간 표현의 역할**로 이해하자고 명시했다.
사용자나 LLM의 이해를 돕는 표현이라는 주장을 중심에 두지 않는다. LLVM IR/FSM과 구체 의미나 기능이 같다는 주장은 아니다.
**사용자가 Timeline을 올바르게 이해하고 확인할 수 있다고 가정한다.** 이 가정의 인간 성능을 현재 논문의 연구 질문으로 삼지 않는다.

### 논문 경계와 톤

- NL→Timeline은 명세 작성 frontend이며, LLM의 초안 정확도를 논문 핵심 보장의 전제로 삼지 않는다.
- 확정된 Timeline이 의도한 행동을 담고 있다고 가정한 뒤, 생성 플랫폼 코드가 그 행동을 보존하는지 연구한다.
- 시스템에 NL 입력과 user confirmation 단계가 있어도 “의도 정확성을 시스템이 입증/향상한다”는 성과로 표현하지 않는다.
- 동기는 스마트홈의 복합 시간·상태 행동을 명시적으로 표현하고 플랫폼 구현과 연결하는 문제다.
- Timeline의 특징은 temporal primitives, structured control flow, state scope/update, compositional/executable semantics 및 명시된 모델 아래 결정성으로 설명한다.
- “LTL은 LLM이 생성하기 어려우므로 Timeline”, “Timeline이 사용자에게 더 읽기 쉬움”을 중심 설계 근거로 쓰지 않는다.
- 핵심 문장: **확정된 스마트홈 행동 명세를 플랫폼 코드로 구현하고, 그 과정에서 시간·상태에 따른 관측 행동이 보존되는지 검증한다.**

### 이전 실험 제안의 우선순위 변경

- NL→Timeline 정확도, 사용자 이해/확인 정확도, 의도 선택 workload를 필수 실험에서 제외한다.
- 표현력/지원 범위, operational semantics, 구현 의미 적합성은 계속 필요하다. 가독성 실험을 요구하는 것은 아니다.
- 확정 Timeline에서의 JoI 생성 결과, Explorer의 오류 검출·잘못된 통과·미완료/거절·비용에 집중한다.
- prose/flat/Timeline 비교는 생성 편의성 향상을 별도로 주장할 경우의 선택적 분석이다. 기존의 headline 추천을 철회한다.
- 외부 baseline도 현 검증/구현 과제와 같은 계약에 맞춰 재검토한다. ChatIoT authoring accuracy 비교를 필수로 확정하지 않는다.
- LLM 코드 생성 결과의 오류율은 후단 검증 필요성과 검증 효과를 평가하는 자료가 될 수 있다. 앞단 NL→IR 정확도와 혼동하지 않는다.
- 자동 repair의 포함 여부도 미확정이다.

이 결정은 §18·§20의 제안 중 사용자 이해 및 NL→IR 성능을 주기여로 보는 해석보다 우선한다.
기존 두 단계 평가 문서 상단에 이 변경을 표시했으며 기존 실험 결과/구현은 변경하지 않았다.

## 22. 기술적 IR 관점의 paper flow와 평가 재설계

사용자 요청에 따라 [최신 flow/IR 특징](paper_flow_ir_contract_2026-09-10.md)과
[확정 명세 중심 평가안](../05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md)을 작성했다.
올바른 명세 확인 가정은 확정 방향이며, 문단/특징 분류와 E1–E4는 이번 검토용 권고다.

- Introduction: 복합 시간·상태 행동 → 플랫폼 구현 간극 → Timeline 실행 명세 → IR–JoI timed ACTION 보존 검사.
- IR 특징: closed domain surface, temporal explicitness, structured/compositional control flow, state propagation/lifetime, input determinism, executability.
- 공통 ACTION 관측 계약은 IR 연산자 특징과 별도로 양쪽 실행을 연결하는 필수 조건이다.
- 의미론/결정성/검증 soundness는 논증과 구현 대응으로, 지원 범위/검출/적용률/비용은 실험으로 뒷받침한다.
- 네 실험 후보: E1 표현 범위, E2 interpreter/validator 적합성, E3 실제 JoI 후보 적용, E4 비용/축소 대조.
- 기존 외부 authoring 도구와의 정확도 비교를 강제하지 않는다. 같은 검증 계약의 comparator 적용 가능성을 확인한다.
- 현 period는 회차 종료 후 대기이며 cron 중첩/병렬/임의 event count 등으로 범위를 확대하지 않는다.
- 데이터/모델/baseline/자원 조건은 미확정이며, 이번에는 실험 실행이나 구현 변경을 하지 않았다.
