# Code Generation and Behavioral Validation handoff

상태: **full first draft; algorithm and theorem text pending**.

- 핵심 pseudo-code와 product-state 수식을 추가한다.
- `time_context`를 구현 필드라고 단정하지 말고 개념 상태로 사용한다.
- 기존 네 verification path와 추가된 timer-zones-v2 경로의 본문/부록 설명 범위를 page budget에 맞춰 결정한다. 현재 경로는 증명 문서와 대조한다.
- FSM 대비는 `../WRITING_GUARDRAILS.md`를 따른다. “FSM 미사용” 및 일반적 성능 우위는 금지한다.
- code를 “직접 실행”한다는 문장에는 supported JoI semantic interpreter라는 경계를 붙인다.
- shortest/earliest counterexample은 현재 보장으로 쓰지 않는다.
- deterministic compiler는 현재 비교 대상이 아니라 인정하는 대안이자 Future Work다.

## 검증 soundness 명제 S의 원고 배치 (2026-09-17)

- **이 절(§6)에 명제 S를 둔다.** 지원하는 준비된 IR–JoI 쌍에 대해 Explorer가 `H=None`의 완료 조건을 충족해 동등 인증에 성공하면, 선언 모델의 모든 허용 초기 상태와 timed input history에서 시간 제한 없이 timed action trace가 일치한다.
- 본문은 공통 모델·관찰 기준의 참조 → 검증 알고리즘과 성공 조건 → S의 명제와 증명 개요 → 경로별 충분조건 표로 구성한다. Timeline IR 절의 [결정론성 D](../05_Timeline_IR/HANDOFF.md)를 참조하며, 결정론성만으로 S가 따라온다고 쓰지 않는다.
- **증명 개요:** 허용 초기 상태·입력 포괄, 반응/관찰 보존, 입력·상태·시간 축소의 정당성, 탐색 폐쇄 또는 해당 경로의 완료 조건을 공통 귀납으로 연결한다. 상세 L1–L7 및 경로별 B0–B3 논증은 부록으로 보낸다.
- 기존 네 경로에 대한 수작업 통합 증명은 [PROOF_OBLIGATIONS.md](../../explorer/docs/proof/PROOF_OBLIGATIONS.md)에 완료로 기록돼 있다. 추가된 timer-zones-v2의 과근사·확대·재검사·폐쇄 논증은 [TIMER_ZONES.md](../../explorer/docs/proof/TIMER_ZONES.md)에서 별도로 연결한다. 원고용 정리와 증명 개요는 아직 편집해야 한다.
- [검증 계약](../../explorer/docs/model/VERIFICATION_CONTRACT.md)의 `Accept∞` 성공 조건을 그대로 따른다. 유한 horizon 성공, timeout·자원 상한·미지원·UNKNOWN을 무제한 동등 인증으로 올리지 않는다.
- 신뢰하는 실행기·프런트엔드·solver 범위와 수작업 증명의 수준을 명시한다. 전체 구현의 기계 검증이나 실제 기기 안전성으로 확대하지 않는다. 실험의 판정 일치는 이론 증명을 대신하지 않는다.
