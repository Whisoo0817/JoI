# Code Generation and Behavioral Validation handoff

상태: **full first draft; algorithm and theorem text pending**.

- 핵심 pseudo-code와 product-state 수식을 추가한다.
- `time_context`를 구현 필드라고 단정하지 말고 개념 상태로 사용한다.
- 네 verification path를 본문/부록 어디까지 설명할지 page budget에 맞춰 결정한다.
- FSM 대비는 `../../WRITING_GUARDRAILS.md`를 따른다. “FSM 미사용” 및 일반적 성능 우위는 금지한다.
- code를 “직접 실행”한다는 문장에는 supported JoI semantic interpreter라는 경계를 붙인다.
- shortest/earliest counterexample은 현재 보장으로 쓰지 않는다.
- deterministic compiler는 현재 비교 대상이 아니라 인정하는 대안이자 Future Work다.
