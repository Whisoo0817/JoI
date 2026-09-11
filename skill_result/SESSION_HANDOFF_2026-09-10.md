# PerCom 논문 논의 세션 인계

최종 갱신: 2026-09-11

새 세션에서는 아래 파일을 순서대로 읽는다.

1. `06_manuscript/problem_framing_codegen_validation_2026-09-11.md`
   - **최우선 framing 결정.** 범용 IoT IR/HA generality가 아니라 NL→JoI 생성 결과의
     행동 검증에서 Timeline의 필요성을 도출한다.
2. `06_manuscript/paper_flow_ir_contract_2026-09-10.md`
   - 교수님 의견을 반영한 최신 paper flow와 Timeline IR의 역할·필수 특징.
3. `05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md`
   - 확정 Timeline을 출발점으로 한 최신 E1–E4 평가 골격.
4. `05_experiment_plan/e1_ir_adequacy_design_2026-09-10.md`
   - E1 표현 범위 평가의 구체 설계와 현재 논의된 실패 후보.
5. `06_manuscript/flow_discussion_2026-09-09.md`의 §21–§22
   - 교수님 의견으로 방향이 바뀐 배경과 사용자 결정 이력.

## 현재 확정된 방향

- Timeline을 모든 IoT automation을 위한 범용 공용 IR로 주장하지 않는다.
- Timeline의 필요성은 **NL→JoI 생성에서 표현력 높은 구현 언어의 여러 idiom과
  timer/state/control-flow 오류를 syntax만으로 검증할 수 없다**는 원래 문제에서 도출한다.
- 대비 축은 `primitive/declarative vs. code-based`가 아니라
  `closed executable behavioral reference vs. expressive implementation language`다.
- JoI가 현재 유일한 구현·평가 backend다. openHAB은 broader relevance/future adapter 사례이며,
  Home Assistant와 SmartThings를 단순 primitive 대조군으로 사용하지 않는다.
- Timeline은 사용성·가독성을 입증하려는 표현이 아니라 LLVM IR/FSM과 같은 기술적 중간 표현으로 본다.
- 사용자가 올바른 Timeline을 이해하고 확정하며, 확정 Timeline이 의도한 행동을 담는다고 가정한다.
- 핵심 연구 범위는 `confirmed Timeline → JoI 생성 → Explorer의 timed ACTION 보존 검증`이다.
- NL→IR 정확도와 사용자 이해도는 현재 필수 평가에서 제외한다.
- Timeline은 시간·제어·상태 행동을 정의하는 executable behavioral specification이다. 각 operator의 의미뿐 아니라 순서·분기·반복에서 제어와 상태가 전달되는 compositional semantics가 필요하다.
- 결정성은 고정 프로그램·모델·초기 상태·입력 이력에서 정상 실행의 timed ACTION trace가 유일하다는 의미론적 성질이다. Timeline만의 독점 성질이나 E1 성공률 지표로 주장하지 않는다.
- 개별 operator의 novelty나 범용성보다, confirmed intermediate specification을 lowering의 source이자
  executable reference로 사용하여 생성 DSL의 행동 보존을 검사하는 baseline framework를 기여로 둔다.
- 검증 기준 명세는 selector-free Timeline 단독이 아니라 **confirmed Timeline + binding plan**이다.
  현재 범위는 `Service.Method`당 서로 다른 selector 하나이며, selector 하나의 multi-device
  `all(...)` fan-out은 지원한다. 복수 selector가 필요한 동일 service 요청은 mapping에서
  fail-closed로 거절하고 E1/E3에서 지원 경계/refusal로 보고한다.

## 최신 평가 골격

- E1: IR 표현 범위. 외부 자동화 사례에서 행동 요구를 먼저 확정한 뒤, Timeline operator의 조합이 요구를 생략·변경하지 않고 표현하는지 평가한다.
- E2: 의미 실행기와 Explorer의 validation fidelity.
- E3: 확정 Timeline에서 실제 LLM 생성 JoI를 검사했을 때의 EQUIV/DIVERGE/거절/미완료 등 적용 결과.
- E4: 탐색 완료 범위, 시간·메모리 비용과 실제 축소 기법 효과.

E1에서 LTL/TAP/FSM과의 직접 비교는 현재 보류했다. E1은 여러 실제 사례에서 완전 표현/부분 표현/지원 밖/자료 불충분과 실패 이유를 보고한다. IR 문법·의미상 표현 가능, 참조 실행기 지원, Explorer 지원을 서로 구분한다.

명세 후보를 여러 개 생성해 trace로 사용자에게 선택시키는 확장 계획은 폐기했다. 논문 계획·평가·향후 연구에 포함하지 않는다.

E1의 대표 실패 후보는 독립 병렬 실행이다. 추가 조사 후보는 실행 중 즉시 취소·재시작, 다른 대기 중 발생한 이벤트의 버퍼링, 이동 시간창의 사건 횟수·집계, 독립 반복 일정과 실행 인스턴스 중첩이다. 이들은 아직 모두 불가능하다고 확정한 목록이 아니다. 기존 operator 조합으로 정확히 표현 가능한지 먼저 검사해야 한다.

Operator의 개별·조합 의미 정의는 E1 결과 자체가 아니라 Timeline IR/semantics 절의 기술 내용이다. E1은 그렇게 정의된 언어가 실제 요구를 어디까지 담는지 평가하고, E2는 실행기와 검증기가 그 정의를 구현하는지 확인한다.

## 문서 충돌 주의

- `05_experiment_plan/experiment-plan.md`, `run-blocks.json`, `decision-gates.md` 등 2026-09-04 파일의 E1은 **interpreter conformance**라는 옛 번호를 사용한다.
- 최신 논의에서 E1은 **IR 표현 범위**, E2는 validation fidelity다.
- 최신 안은 아직 최종 동결된 실행 protocol이 아니다. 외부 corpus 출처·수량, annotator 판정 절차, 모델과 자원 한도는 미확정이다.
- 교수님 의견 이전의 prose/flat/full Timeline 생성 비교안은 폐기했으며 현재 실험에 포함하지 않는다.

## 다음 논의 지점

새 problem framing을 기준으로 paper flow의 절별 문장과 contribution wording을 최종 동결한다.
그 다음 E1 corpus의 출처와 선정 규칙, 행동 요구를 확정하는 annotation sheet,
완전 표현/부분 표현/지원 밖의 판정 기준을 구체화하고 operator 조합 taxonomy와 대표 boundary case를 정한다.
