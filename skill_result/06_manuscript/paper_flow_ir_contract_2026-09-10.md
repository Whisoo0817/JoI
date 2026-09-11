# Paper flow: 확정 행동 명세에서 플랫폼 구현 보존까지

2026-09-10 작성, 2026-09-11 problem framing 갱신.
사용자 요청에 따른 최신 논문 흐름 및 설계 특징 정리.
범위 가정은 사용자가 결정한 사항이며, 아래 문단 구성·특징 분류·실험 묶음은 검토용 제안이다.
이 문서는 이전 사용자/LLM 이해도 중심 제안보다 우선한다. 구현 또는 검증 계약을 변경하지 않는다.

## 0. 2026-09-11 framing update: 범용 IR 주장을 버리고 원래 문제로 돌아간다

상세 결정은 [`problem_framing_codegen_validation_2026-09-11.md`](problem_framing_codegen_validation_2026-09-11.md)를 따른다.
이 갱신은 이 문서의 confirmed-Timeline 경계와 검증 계약을 바꾸지 않고, Timeline의 필요성을
정당화하는 논리를 다음과 같이 고정한다.

> Timeline은 모든 IoT automation을 위한 범용 공용 IR이기 때문에 필요한 것이 아니다.
> 자연어에서 JoI처럼 표현력 높은 구현 언어로 생성할 때, 같은 행동의 여러 구현 idiom과
> 미세한 timer/state/control-flow 오류를 syntax만으로 구별할 수 없으므로 필요하다.
> Confirmed Timeline은 지원 JoI 범위의 기대 행동을 lowering 전에 고정하는
> per-automation executable behavioral specification이며, Explorer의 reference다.

논문의 대비 축은 `primitive/declarative platform vs. code-based platform`이 아니다.
`closed and explicit behavioral reference vs. implementation-facing expressive language`다.
Home Assistant와 SmartThings도 구조화된 control 기능을 제공하므로 단순 primitive 대조군으로
사용하지 않는다. openHAB은 broader relevance 또는 future backend의 사례일 뿐, adapter와 실험 없이
현재 기여·지원 범위에 넣지 않는다. 현재 구현·평가 backend는 JoI 하나다.

Timeline operator는 IoT 전체에서 보편적이거나 타 IR보다 우월해서 선택한 것이 아니다.
선언한 reactive-temporal JoI 문제 범위에서 시간·제어·상태 행동을 명시하고 실행하기 위해
필요한 surface로 정당화한다. 따라서 E1도 범용성 경쟁이 아니라 이 범위에 대한 adequacy와
unsupported boundary를 평가한다.

## 1. 연구 경계와 중심 주장

사용자는 Timeline과 binding plan을 올바르게 이해·확정할 수 있고, 확정된 두 산출물은 의도한 행동과 대상을 담는다고 가정한다.
NL→LLM→Timeline→user confirmation은 명세 작성 frontend로 시스템에 남지만, NL 번역 정확도나 인간 확인의 효과가 논문 보장에 포함되지는 않는다.

핵심 문제:

> 확정한 reactive-temporal 자동화의 시간·제어·상태 행동을 JoI 코드로 구현하고,
> 생성된 구현이 그 timed observable ACTION을 보존하는지 확인한다.

두 중심 주장 후보:

- C1: Timeline은 지원하는 JoI 자동화 범위의 reactive-temporal 행동을 명시적 시간 연산,
  구조화된 제어 흐름, 상태 전달 규칙으로 표현하는 per-automation 실행 가능 행동 명세다.
- C2: Explorer는 선언 모델에서 확정 Timeline·binding plan과 생성 JoI의 timed ACTION 보존을 검사하며, 완료한 인증과 재생 가능한 반례 및 미인증 결과를 구별한다.

Timeline의 가독성, NL 번역 정확도 우위, 모든 사용자 의도의 자동 확정, 범용 IoT IR,
다중 플랫폼 성과는 이 두 주장에 포함하지 않는다.
자동 repair의 포함 여부는 별도 미확정 사항이다.

정의 후보:

> Timeline IR is an executable behavioral specification that represents smart-home automation through composable temporal primitives, structured control flow, and defined state propagation, providing a common reference for platform-code generation and behavioral validation.

## 2. Introduction의 문단별 논리

1. **도메인 문제.** 복합 스마트홈 자동화는 호출할 기기와 조건 외에도 관측 시점, 지속 조건, 순서, 반복, 저장값과 타이머의 수명을 정의해야 한다.
2. **구현 간극.** 확정 행동을 플랫폼 코드로 옮기는 과정에서 문법적으로 유효해도 그 시간·상태 관계를 잘못 구현할 수 있다. DSL 문법/API/실행 설명을 제공한 LLM 생성도 의미 보존 자체를 보장하지 않는다.
3. **행동 IR.** Timeline은 이런 의미를 지원 연산과 조합 규칙으로 명시하는 기술적 IR이다. 플랫폼의 구체 제어 변수/구문과 별개로 기준 행동을 정의하되, 실제 service binding/model과 연결한다.
4. **실행 가능성의 역할.** 초기 구성과 입력 이력을 주면 기준 timed ACTION을 계산한다. IR은 하나의 고정 일정표가 아니라 입력별 가능한 실행을 정의한다.
5. **구현 검증.** 같은 모델/입력에서 JoI와 Timeline의 관측을 비교한다. 누락·추가·시각·인자·명시 순서의 차이를 반례로 제시하며 완료하지 못한 검사를 성공으로 취급하지 않는다.
6. **기여와 평가 예고.** IR 설계/의미론, IR–JoI 검증 방법, 실제 복합 자동화에서의 적용·검출·비용 평가를 제시한다. 생성 모델이 더 똑똑해졌다는 주장을 강제하지 않는다.

대표 사례:
“방이 연속 5분 비어 있으면 플러그를 한 번 끈다.”
Timeline은 `wait(absent, for=5min); call(off)`라는 확정 의미를 갖는다.
오구현 `wait(absent); delay(5min); if(absent) off`는 중간 재실을 놓칠 수 있다.
0분 부재 → 4분 재실 → 4분30초 부재에서, 오구현은 5분 off, 기준은 계속 부재일 때 9분30초 off다.
이 사례는 원문 모호성이나 사용자 이해 연구가 아니라 **확정된 지속 조건의 구현 오류**를 보여준다.

## 3. Timeline의 필요한 특징

| 특징 | 정확한 역할 | 구체적으로 명시할 사항 | 증거 형태 |
| --- | --- | --- | --- |
| Domain-level closed surface | 지원 자동화를 한정된 구문과 catalog/type 계약으로 표현하여 해석 범위를 정함 | start_at/wait/delay/read/call/if/cycle/break; 유효 조합·인자·미지원 경계 | 문법, typing/well-formedness, 모델 연결 |
| Temporal explicitness | 시간/이벤트 관련 행동 결정을 고정 | 조건 평가 시점, delay vs sustained wait, edge 기억, period 재개, 입력/만료 동시 처리 | 연산 의미 규칙과 boundary 사례 |
| Structured control flow and compositional semantics | 여러 시간 연산의 순서·분기·반복을 규칙적으로 결합 | 중단 후 복귀, cycle exit/reentry, 결합 시 state/control 전달 | 구문별 operational rules; 부분 의미 + 결합 규칙 |
| Defined state propagation and lifetime | 이전 입력/회차가 미래 ACTION에 미치는 영향을 결정 | snapshot, 지역 저장값, 초기 GV와 이후 갱신, 반복 count, timer/latch 수명 | 상태 구성, store 갱신·읽기 규칙 |
| Input-deterministic semantics | 고정 프로그램/모델/초기 상태/입력에서 기준 행동을 유일하게 정함 | 외부 입력과 내부 상태 구별, 같은 시각 처리 순서, 정상 실행/오류/진행 조건 | 모델 결정론성 논증 |
| Executable semantics | 기준 행동을 계산하여 코드와 비교하고 반례를 재현 | step/reaction, blocking/resume, timed trace 구성 | reference interpreter 적합성 및 실행 사례 |

composable은 허용된 조합 아래의 성질이다. 임의 연산의 무제한 중첩/병렬 결합을 허용한다는 뜻이 아니다.
compositional semantics를 compositional verification으로 확대하지 않는다. 국소 ACTION만 같은 조각은 후속 상태가 달라 문맥 내 치환이 안전하지 않을 수 있다.
연산자 각각이 스스로 완전한 명세인 것도 아니다. 전체 구성과 언어/환경 의미가 함께 기준 행동을 결정한다.
이 특징들이 언어 일반의 유일한 필요조건이거나 다른 IR에서는 불가능하다고 주장하지 않는다.

별도 **공통 관측 계약**도 필수다. IR과 JoI가 호출 시각, 기기, method, typed arguments, multiplicity 및 명시 순서를 동일한 기준으로 비교해야 한다. 이는 IR operator 하나의 성질이 아니라 양쪽을 연결하는 시스템 계약이다. 현재 binding/lowering 범위는 `Service.Method`당 서로 다른 selector 하나이며, 그 selector의 `all(...)` fan-out은 여러 concrete device를 포함할 수 있다. 복수 selector가 필요한 동일 service 사례는 지원 경계로 보고한다.

## 4. System Overview와 본문 절 순서

```text
명세 작성 frontend: NL → LLM → Timeline + binding plan → user confirmation
                                      │ 확정된 행동을 담는다는 가정
                                      ▼
                         Confirmed Timeline + binding
                                  │          │
                        DSL 설명+LLM       IR interpreter
                                  │          │
                                JoI      기준 실행 의미
                                  └────┬─────┘
                                Explorer: 공통 모델/입력
                                  │
                 EQUIV / DIVERGE+witness / 미인증
```

1. Introduction: 도메인 행동과 구현 보존 문제, 사례, 접근/기여.
2. System Overview and Scope: 위 pipeline, 명세 가정, platform/runtime 범위.
3. Timeline IR: 문법, 조합, 상태, 시간, 실행 의미와 모델 결정성.
4. Platform Code Generation and Behavioral Validation: JoI 생성 인터페이스, 구현 의미 모델, 관측 계약, 탐색/축소, 성공 정당성, 반례와 미완료.
5. Evaluation: 지원 범위, 구현 적합성·검출, 실제 후보 적용, 비용.
6. Related Work: 자동화 표현·명세 작성·코드 생성·검증과의 역할 비교. 기존 방법 대비 새로운 기술 난제는 별도 구체화 의무로 유지.
7. Limitations and Conclusion: 선언 모델, 지원 코드/환경, 신뢰 기반, frontend 가정.

Related Work 배치는 템플릿/페이지 수에 따라 조정 가능하다. 논증상 내용은 Introduction의 위치 설명과 연결한다.

## 5. 현 구현과 논문 범위를 맞출 사항

기준: `explorer/docs/model/VERIFICATION_CONTRACT.md`, `explorer/docs/proof/PROOF_OBLIGATIONS.md`.

- 현 period는 **회차 종료 후 period만큼 대기**다. 고정 시각 cadence와 혼용하지 않는다.
- cron은 준비 단계에서 동일 anchor를 확인하며 여러 실행 인스턴스 중첩을 검증하지 않는다.
- 단일 시나리오 쌍이며 병렬 시나리오/IR 병렬 분기는 지원 범위에 포함되지 않는다.
- cycle.count는 회차 번호다. “온도가 3번 넘었다” 같은 사건 누적 counter와 동일시하지 않는다. 해당 동작의 실제 상태 갱신 표현/검증 지원을 별도 확인해야 한다.
- 입력 grid, 정확한 내부 deadline, 입력 우선 동시 처리 및 보존되는 값/호출 의미는 계약을 따른다.
- H 없는 인증과 명시 H 안의 동등은 구별한다. 자원 상한/미지원/unknown은 동등 인증이 아니다.
- formal 문서의 수작업 증명 완료 진술은 전체 Python/실제 기기의 기계 검증을 의미하지 않는다.
- binding은 `Service.Method`당 서로 다른 selector 하나만 허용한다. 하나의 `all(...)`
  selector가 여러 기기에 fan-out하는 것은 포함하며, 복수 selector가 필요한 요청은
  mapping에서 fail-closed로 거절하고 평가 분모에서 별도 보고한다.

기존 넓은 operational_semantics.md의 병렬 merge 규칙이나 extractor의 허용/표현 설명을 현 검증기의 지원 보장으로 가져오지 않는다. 이번 정리는 코드 또는 frontend 정책 변경 작업이 아니다.

## 6. 이 흐름에 맞는 새 실험 논리

상세 설계는 [새 평가 제안](../05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md)을 따른다.
가독성/의도 확인/NL→IR 정확도는 필수 실험에서 제외한다. 의미 규칙·정당성 논증을 실험 수치로 대신하지 않는다.

E1 지원 범위 → E2 검증 구현의 신뢰성 → E3 실제 JoI 후보 적용 → E4 탐색 비용/축소 효과.
이 네 묶음은 현 단계의 권고안이며 데이터 수, 모델, 외부 baseline, 최종 자원 상한은 아직 미확정이다.
