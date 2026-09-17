# Related Work 문단 흐름 — SenSys 보존 중심 수정 계획

상태: **R1–R8 보존 수정본에 NL → IR → DSL 생성·검증 관점 반영 완료, 문장별 검토 전 (2026-09-17)**. [SenSys 원문](SenSys_version.md)의 순서와 연구 소개를 기준으로 [PerCom 본문](PerCom_version.md)에 아래 계획을 반영했다. 오른쪽 열은 적용한 수정 방향을 기록한다.

기준: [Intro](../01_Intro/PerCom_version.md), [HANDOFF](HANDOFF.md), [Writing Style](../WRITING_STYLE.md), [Guardrails](../WRITING_GUARDRAILS.md). 이번 계획은 기존의 네 비교 축 재구성안을 대체한다.

## 편집 원칙

- **R2–R7의 순서, 문단 역할, 연구 소개를 유지한다.** 잘못된 결론을 고치기 위해 문단 전체를 재작성하거나 논문들을 다른 문단으로 이동하지 않는다.
- 주로 문단의 첫 주장·연결 문장과 마지막 해석·결론을 바꾼다. 개별 연구 설명의 사실 오류는 해당 절만 수정한다.
- R1은 분류 기준 한 문장으로 축약하고, R8은 현재 VETS의 위치에 맞춰 다시 쓴다.
- SenSys에 없던 논문은 이번 수정에 넣지 않는다. nl2spec, ARTEMIS, Moon et al., IoTSan, translation validation, VeriSafe 등의 조사 기록은 남기되 본문에는 사용하지 않는다.
- 전체 과업은 **NL → Timeline IR → imperative DSL의 생성·검증 파이프라인**이다. 확정 IR은 LLM 코드 생성의 기준이자 생성 결과를 검사하는 실행 가능한 명세다. 생성 정확도·성공률 향상이나 NL→IR 정확도를 입증했다는 주장은 하지 않는다. 단순한 생성·검증 결합 자체도 novelty로 삼지 않는다.
- `fixed vs. non-fixed` 대신 **해당 연구가 어떤 대상에 어떤 검증 질문을 적용하는지** 비교한다. 검증 시점의 Timeline IR도 확정된 reference다.
- 아래 계획을 본문에 반영했다. 대응 SenSys 문단에서 수정·추가한 단어·구절을 굵게 표시하고, 새로 쓴 문장은 전체를 굵게 표시했다. 삭제만 한 부분은 이 비교표와 본문 편집 메모에 기록한다.

## 문단별 Flow Comparison

| SenSys — 원래 역할과 흐름 | 그대로 살릴 부분 | PerCom — 주장 문장 수정 계획 |
| --- | --- | --- |
| **R1. 분류 도입.** 기존 검증에는 reference가 있었으나 author→prompter 전환으로 사라졌다는 설명. 마지막에 reference 중심 분류 선언. | 마지막 분류 문장의 골격. | **대폭 축약.** 자동화를 생성하는 방식과 검사 reference를 기준으로 비교한다는 한 문장만 둔다. 사용자 authoring의 어려움과 reference가 사라졌다는 전면적 주장은 반복하지 않는다. |
| **R2. 자동화의 형식 검증.** AutoTap → TAPInspector/TAPFixer → iRuler/Soteria → HAWatcher. fixed reference 덕분에 검증 가능하며 별도 intent reference는 불필요하다는 결론. | 연구 순서와 기능 설명. LTL 합성·수정, 시간·안전성·활성 검사, 보안 분석, runtime monitoring 사례. | **첫 범위와 끝 두 문장을 국소 수정.** 모두 hand-authored TAP만 분석한다는 범위를 넓힌다. 끝은 properties·conflicts·invariants에 대한 합성·검사라는 검증 질문으로 정리한다. Soteria의 기존 인용에 코드에서 얻은 모델을 검사한다는 짧은 설명을 붙여 R8 비교를 준비할 수 있다. |
| **R3. 다른 생성 도메인의 실행 검사.** GPIoT → SQL → CodeT/Self-Debug. 이미 주어진 oracle 덕분에 검증 가능하다는 결론. | 실행 테스트·gold query·실행 피드백 사례와 순서. 다른 생성 도메인의 검사 기준을 소개하는 연결 역할. | **첫 연결과 마지막 일반화 수정.** 모두 미리 제공된 reference라는 설명을 바꾼다. CodeT의 생성 테스트와 Self-Debug의 테스트 없는 설정 때문에 해당 소개 절도 최소 수정한다. R3를 삭제하거나 다른 문단에 합치지 않는다. |
| **R4. 생성 reactive-temporal 코드의 문제.** 미래 행동 reference → TAP primitive → JoI의 변수·조건·tick idiom → lowering 오류. | primitive를 플랫폼이 구현하는 경우와 생성 코드가 구현하는 경우의 차이. persistent variables, conditions, per-tick execution과 lowering 오류로의 연결. | **생성 과정과 행동 명세를 연결.** 자연어의 행동을 시간·입력에 따라 작동하는 코드로 옮기는 과정을 소개하고, 명시적 행동 명세가 생성의 기준과 결과 검사의 reference를 제공할 수 있음을 설명한다. slot 오류는 보이고 mechanism 오류는 안 보인다는 단정은 오류가 slot 값 또는 분산된 상태·제어 로직에 위치한다는 차이로 고친다. JoI의 지원 설정으로 범위를 제한한다. |
| **R5. 생성 결과의 결정적 검사.** AutoIoT → DS-IA → TaskSense → AgentSpec. fixed/hand-written criteria만 검사하고 사용자 행동은 reference가 아니라는 결론. | 네 연구와 순서. conflict·grounding·plan structure·runtime enforcement의 사례. | **첫 문장과 마지막 결론 수정.** 각 검사의 기준을 구체적으로 묶는다. 요청별 실행 명세와 생성 구현의 timed action 보존과 검사 질문이 다르다는 방향. AgentSpec의 fixed/hand-written 절과 TaskSense의 두 검사를 모두 structural well-formedness로 묶은 절은 사실에 맞게 수정한다. |
| **R6. 자동화 생성 시스템.** ChatIoT → Giudici et al. → IoTGPT → AwareAuto. format/API 수준에서 멈춘다는 일반화와 rendering 비교. | 각 시스템 소개와 순서. ChatIoT evaluator의 request satisfaction, AwareAuto의 event/state, delay, branch, sequencing 및 실행 가능한 규칙 생성. AwareAuto 자체의 panel 설명은 기능 소개로 유지 가능. | **연구 소개 뒤 결론 교체.** 의도 평가와 행동 표현을 인정하고, 실행 가능한 행동 명세로부터 생성한 imperative 구현이 그 명세의 timed action을 보존하는지라는 비교 지점을 남긴다. researcher annotation vs. deterministic rendering 비교는 삭제한다. `weaker`, `goes furthest` 같은 총체적 서열 표현도 고친다. |
| **R7. 의도와 실행을 직접 평가하는 사례.** LACE 요청–정책 비교 → SimuHome 시뮬레이션 → 모델의 자기 인증 비판. | LACE의 deterministic back-translation + NLI 설명. SimuHome의 시간 가속 시뮬레이션과 agent 평가라는 역할. | **마지막 비판을 검사 관계의 차이로 변경.** LACE의 NLI 판정과 별도 SMT conflict 검사를 구별한다. SimuHome은 benchmark 실행 평가라는 차이를 남긴다. 사용자 확인 부재, 자기 인증, 100% correctness 비판은 뺀다. 기존 18 agents/실패 양상 및 §3 참조는 현재 버전·Motivation과 대조 전 재사용하지 않는다. |
| **R8. 가까운 연구와 OVLA의 위치.** LACE + AwareAuto → authoring/user confirmation → IR oracle → on-device/독점성 주장. | 가까운 연구의 기능을 짚고 우리 검증 질문으로 닫는 구조. | **내용 재작성.** AwareAuto의 행동 표현과 TAPInspector/Soteria의 모델 기반 검증을 두 인접 방향으로 받는다. NL → imperative DSL 과정에서 Timeline IR이 행동을 명시하고, 확정된 동일 IR을 코드 생성의 기준과 timed action 보존 검사의 executable reference로 사용하는 관계로 마무리한다. LACE는 R7에 남긴다. 최적·최초·독점성, authoring UI, on-device는 차별점으로 쓰지 않는다. |

## 실제로 교체할 주장 문장의 경계

아래는 실제로 교체한 주장 문장의 경계다. 소개 문장에 사실 문제가 없는 한 앞부분을 유지했다.

| 위치 | SenSys의 교체 대상 | 대체할 의미 |
| --- | --- | --- |
| R1 | 처음 다섯 문장 | 삭제. 마지막 `We therefore organize prior work ...`를 생성 방식·검사 reference를 기준으로 하는 한 문장으로 수정. |
| R2 끝 | `Deterministic verification is possible ... because the reference is fixed in advance ...` 및 `a separate per-task intent reference is never required.` | 앞의 연구는 properties, conflicts, invariants를 기준으로 분석·합성·감시한다. 사용자 맞춤 property도 존재하며 fixed 여부는 VETS와의 차이가 아니다. |
| R3 처음·끝 | `whose domain supplies an executable oracle` 및 `a checkable target that was already available` | 실행 결과를 테스트·gold 결과·실행 피드백으로 검사한다. 기준이 외부 제공인지 생성된 것인지는 논문별로 구별한다. |
| R4 처음 | `no ready-made reference` 및 `LLM-generated reactive automations have no such target` | 자연어의 기대 행동을 구현으로 옮기는 과정에서 명시적 행동 명세가 생성과 결과 검사 모두의 기준이 될 수 있다. 기존 행동 명세의 존재를 부정하지 않는다. |
| R4 중간·끝 | `so slot errors are visible on the face of the rule` 및 `Mechanism errors are silent` | primitive를 실행하는 엔진과 그 메커니즘을 변수·조건·반복으로 다시 구현하는 생성 코드의 역할을 구별한다. 오류 가시성의 절대적 대비는 하지 않는다. |
| R5 처음·끝 | `but still against fixed criteria` 및 `the behavior the user actually asked for is still never the reference` | conflict freedom, grounding feasibility, plan structure, runtime constraints라는 구체적 기준으로 묶는다. 실행 명세–생성 코드 간 행동 보존과 검사 관계를 구별한다. |
| R6 끝 세 문장 | `Across this line, automatic checking stops ...`부터 `none of these systems verifies ...`까지 | 의도 확인과 실행 가능한 자동화 생성을 인정하면서, 행동 명세로부터 생성된 imperative 구현이 그 명세의 시간에 따른 행동을 보존하는지라는 비교 지점을 남긴다. rendering 비교는 제거한다. |
| R7 끝 | `intent has no ground truth other than the user ... a model-judged verdict certifies itself ...` | 요청–정책 의미 판정과 benchmark 실행 평가가 각각 무엇을 판정하는지 정리한다. 분야 전체의 불가능성이나 기존 시스템의 오류를 주장하지 않는다. |
| R8 전체 | `Two systems come nearest ...` 이후 | 아래 세 문장 역할에 맞춰 현재 positioning으로 교체한다. |

## 마지막 문단 — 세 문장의 연결

1. **인접 연구를 한 문장으로 연결:** AwareAuto의 reactive-temporal 표현을 통한 자동화 생성과 TAPInspector/Soteria의 규칙·앱 모델에 대한 속성 검사를 소개한다. 각각을 다시 길게 설명하지 않는다.
2. **VETS의 전체 과업과 IR의 위치:** NL → imperative reactive-temporal DSL에서 Timeline IR이 요청의 event/state/temporal 관계를 명시하는 중간 표현임을 설명한다.
3. **생성과 검증의 공통 기준으로 마무리:** 확정 IR을 바탕으로 LLM이 코드를 생성하고, 같은 IR의 결정적 실행 의미가 선언된 실행 모델 내 timed action 보존 검사의 reference를 제공한다. 생성 성능의 우수성이 아니라 명세와 생성 구현의 관계를 설명한다. IR이 의도에 맞게 확정되었다는 것은 전제이며 확인 UI는 기여가 아니다.

이는 기존 연구의 보고된 검사 대상·관계와 VETS를 비교하는 계획이다. **Model checker도 reference–code product에서 action 일치를 검사할 수 있다.** 따라서 model checking과 behavioral comparison을 상호 배타적인 선택지로 만들거나, interpreter 실행이 일반적으로 더 쉽고 빠르다고 결론 내리지 않는다. 결정적 실행 명세 자체의 최초성도 주장하지 않는다.

## 수정 뒤 전체 흐름

R1 생성 방식·검사 기준으로 분류 → R2 자동화의 속성 검사 → R3 다른 생성 도메인의 실행 검사 → R4 행동 명세를 통한 reactive-temporal 코드 생성·검사와 구현 간극 → R5 생성 결과의 결정적 검사 → R6 자동화 생성·의도 확인 → R7 요청/실행을 직접 평가하는 인접 사례 → R8 NL → IR → DSL 파이프라인에서 동일 명세를 생성·검증 기준으로 사용하는 VETS의 역할.

R3 끝의 `already available`을 고치면 R4 첫머리의 `no such target`도 함께 고친다. R5–R7에서는 각 계열의 검사 기준을 설명하고, VETS의 전체 검증 계약은 R8에서 한 번 정리한다. 이 연결 수정으로 기존 문단 구조를 유지한다.

분량은 먼저 R1과 R8, R2–R7의 중복 결론에서 줄인다. 현 단계에서 연구 소개 문단을 병합하거나 인용 사례를 대거 삭제하지 않는다. 본문 작성 후 실제 분량을 보고 추가 압축한다.

## 근거와 후속 확인

- [자동화 IR·실행 경로 비교 카드](../../skill_result/02_literature/related_work_review_2026-09-09/automation_ir_execution_matrix.md): AwareAuto, AutoTap, TAPInspector, Soteria의 표현·실행·검사 역할.
- [생성 시스템 카드](../../skill_result/02_literature/related_work_review_2026-09-09/generation_prior.md): CodeT/Self-Debug, ChatIoT, TaskSense, LACE, SimuHome의 국소 사실 수정.
- [검증 연구 카드](../../skill_result/02_literature/related_work_review_2026-09-09/safety_prior.md): AgentSpec의 LLM 규칙 생성과 runtime enforcement, 기존 모델 검사 범위.
- 마지막 문단의 인접 연구는 [AwareAuto §§4.3–4.4](https://arxiv.org/html/2408.12687v1), [TAPInspector](https://arxiv.org/html/2102.01468v2), [Soteria 공식 소개](https://www.usenix.org/conference/atc18/presentation/celik)를 재확인했다. 이들 연구의 보고된 경로에 근거한 비교이며 확장 불가능성이나 모든 선행연구에 대한 부재 증명이 아니다.
- GPIoT는 execution tests를 이용한 평가로 표현하고 pass@k를 test 종류처럼 쓰지 않았다. TaskSense는 solvability와 structure를 구별했으며, SimuHome의 agent 수·실패 결과·과거 §3 참조는 삭제하고 goal states와 required tool calls의 benchmark 평가를 남겼다.
- R3의 [CodeT](https://arxiv.org/abs/2207.10397) 생성 테스트와 [Self-Debug](https://arxiv.org/abs/2304.05128)의 테스트 없는 설정, R7의 [SimuHome v3](https://arxiv.org/html/2509.24282v3) 평가 기준을 작성 시 원문과 재대조했다.
- 계획표 외 국소 수정: Giudici et al.의 설명을 JSON parsing만으로 수용한다는 문장에서 framework acceptance에 기반한 JSON validity 평가로 바꿨다. IoTGPT가 intent mismatch를 다루지 않는다는 넓은 단정은 삭제했다. 연구 소개 순서는 유지했다.
- R5 마지막은 각 검사의 구체적 기준으로 마무리했다. R6 마지막은 행동 명세로부터 생성한 imperative 구현의 행동 보존과 구별하고, R7은 SimuHome의 benchmark 평가와 deployment gate의 차이로 닫았다. 문단마다 VETS의 전체 계약을 반복하지 않는다.
- 본문 작성과 변경 표시를 완료했다. bibliography와 다른 절은 수정하지 않았다.

- 후속 논의 반영: R1·R4·R6의 연결 문장과 R8만 수정했다. R2·R3·R5·R7 및 개별 연구 소개는 유지했다. `separately generated`는 IR과 무관한 생성이라는 오해를 피하도록 제거했다. 생성과 검증을 함께 제공하는 파이프라인이라는 기능 설명을 생성 정확도의 실험적 주장과 구분한다.
