# Code Generation and Behavioral Validation handoff

## 최신 사용자 검토 반영 (2026-09-17, §5·6 커밋 요청)

- 영문·한글·LaTeX의 최신 본문은 검증 목적을 먼저 밝히고, 공통 실행·timed action 비교·입력과 시간·Algorithm 1·완료 조건·명제 S 및 짧은 증명으로 구성한다.
- 특정 timer–counter/DBM 탐색 문단과 사용되지 않는 product-state 수식을 삭제했다. DBM 상세는 `DRAFT_NOTES.md`의 편집 이력으로 보존하며, timestamp idiom 지원 범위를 새로 주장하지 않는다.
- Algorithm 1은 유지하되 내부 용어와 중복 설명을 줄였다. 명제 S 수식, 후속 실행 포괄, 정상 실행·시간 진행 조건, 미확정 처리와 신뢰 범위는 유지했다.
- 최신 PDF 빌드와 diff 공백 검사 통과. 아래 분량·문단 배치 및 push 여부 기록은 각 편집 시점의 이력이다. 사용자 요청에 따라 이번에 §5·6 변경을 JoI `paper`와 Overleaf GitHub `master`에 커밋·푸시한다.

## 최신 원고 상태 (2026-09-17, 압축 초안)

- 사용자 합의에 따라 candidate generation은 Fig. 2를 참조하는 2문장, counterexample/repair는 2문장으로 작성했다. 별도 소절·예시·그림을 추가하지 않았다.
- `PerCom_version.md`: 공동 탐색, 입력·시간 처리, IR timer–JoI counter 관계, 개념 알고리즘 1개, 명제 S와 증명 개요. Implementation은 마지막 짧은 문단에 통합했다.
- Overleaf: `sections/behavioral-validation.tex`, `main.tex`에서 §5 다음에 포함. 기존 figure·§1–5·결정론성 부록은 보존했다. 새 본문은 검정색.
- 아래의 “algorithm and theorem pending” 및 “상세 증명을 부록으로”는 이전 계획이다. 현재는 본문에 명제/증명 개요를 넣고, 상세 경로별 증명은 기존 로컬 proof 문서에 유지한다. 새 proof appendix를 추가하지 않았으며, 본문이 모든 보조정리의 완전한 증명이라고 주장하지 않는다.
- `DRAFT_NOTES.md`에 근거 매핑, Fig. 2 라벨 권고, citation 검증 및 조판 점검을 기록한다. 명제 S를 결정론성 D만으로 도출하지 않는다.

## 독자 안내 및 중복 축소 (2026-09-17)

- 도입부에 검증 대상(생성 코드의 액션·시각 보존)과 명제 S의 필요성(완료된 동등 판정의 근거)을 명시했다.
- 사용되지 않는 product-state 수식과 상태 필드 나열을 삭제하고, 입력·시간 처리와 알고리즘 뒤 설명 및 증명 개요를 압축했다. 영문 공백 기준 1,093 → 993단어.
- 경로별 적용 제약, 후속 상태 포괄·확장 후 재검사, 완료 조건, 미확정 처리, 보장의 신뢰 경계는 유지했다.
- 영문 MD, 한글 MD, 로컬 Overleaf TeX에 반영했다. 이번 변경은 push하지 않았다.

## 이전 인계 (이력)

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
