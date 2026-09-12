# 확정 Timeline을 출발점으로 하는 Evaluation 재설계

2026-09-10 작성, 2026-09-12 E1 절 갱신. standalone 토론용 설계안. E2–E4는 아직 frozen pack이 아니다.
사용자 결정: 올바른 Timeline 확인을 가정하고, 기술적 IR와 플랫폼 구현 보존에 초점을 둔다.
[최신 paper flow](../06_manuscript/paper_flow_ir_contract_2026-09-10.md)의 C1/C2를 평가한다.
이전 두 단계 평가안에서 NL→IR/이해도/표현별 생성 정확도를 필수로 삼던 제안은 대체한다.

## 1. 평가 질문과 증거 분담

- C1: 지원하는 복합 시간·상태 자동화를 Timeline의 조합적 실행 의미로 명세할 수 있다.
- C2: 선언 모델의 확정 Timeline에 대해 JoI의 행동 보존을 검사하며, 실사용 후보에서도 의미 있는 범위를 판정할 수 있다.

문법과 operational rules, 모델 결정성 및 성공 인증 soundness는 이론/구현 대응 근거다.
실험은 지원 사례의 범위, 구현 적합성, 구체 오류 검출 및 완료/비용을 측정한다. 무오류 실험을 보편적 soundness 증명으로 쓰지 않는다.
현 증거는 개발/탐색 단계다. 새 독립 corpus/라벨/설정 동결과 독립성 점검 전 confirmatory로 부르지 않는다.

## 2. 핵심 네 실험 묶음

### E1 — IR adequacy: 경계 표 중심의 외부 요구 표현 적합성 사례 연구 (2026-09-12 갱신)

- 질문: 사용자 행동으로 정의한 범위(단일 자동화, 입력 이력이 주어지면 호출의 시각·대상·인자·횟수·순서가 정해지는 요구)의 외부 요구를 Timeline이 의미 손실 없이 표현하는가, 경계(B1–B5)는 어디인가?
- 지표는 "완전 표현 비율"이 **아니다**. 요소 R1–R10과 경계 B1–B5의 표에 사례별 판정(완전/부분/불가/보류)을 놓는다. 선정 건수 중의 건수이며 coverage 비율로 해석하지 않는다.
- 절차: 출처·원문 고정 → 해석·가정·기대 trace를 IR 작성 **전에** 고정(해시) → IR 작성(A) → 독립 의미 감사(B, whisoo) → 참조 실행기 재생 비교(C, 1초 허용·정확 일치 별도) → 실행기 지원(D)·Explorer 자기 product(E, 참고)·binding(F)·JoI 가능성(G, 불가/부분만).
- 완전 = A 완전 ∧ B 보존 ∧ C 전 이력 일치. D·E는 A를 바꾸지 못한다. 결과에 맞춰 허용 오차·실행기·계약을 바꾸지 않는다(버전 고정).
- 선례: AutoTap ICSE'19 §III–IV·VI, Dwyer ICSE'99 §3. 두 연구의 수집 자료는 표현 체계 설계에 쓰였으므로 held-out 선례로 과장하지 않는다. AutoTap 속성→자동화 변환은 `[연구자 변환]`으로 표시.
- 상태: Stage A 12건 완료·감사 반영(완전 12/12, exact 41/41). B3(look-back)·B4(가변 간격)는 Stage A 미평가, Stage B 후보 8건 미착수. 세부: `../../PerCom/6_Evaluation/E1_adequacy/README.md`, 결과 `results.md`.
- E1에서 드러난 계약 사실은 Timeline 절에 반영한다: period는 회차 종료 후 대기, 초기 참인 edge 발화, 다른 대기 중 edge는 latch 미반영, 실행기의 cron 앵커 거절(소거 후 한 창), `wait.timeout`이 extractor 문법에 없음, frontend 검사는 구조만.
- 보류: 타 표현(TAP/LTL/FSM)과의 동일 행동 encoding 비교(구 E1b). 본문 결과: 경계 표 + 복합 사례 2개 정도의 의미 전개.

### E2 — Validation fidelity: 검증 결과를 신뢰할 수 있는가?

- 질문: IR/JoI 실행 모델과 탐색이 올바른 구현/실제 불일치를 구별하는가?
- 먼저 interpreter 적합성을 확인한다. 독립 semantics evaluator와 boundary 예상 결과를 사용하며 production one-step runner 공유 여부를 공개한다.
- positive pairs: 문법/제어 표현이 다른 독립 올바른 구현. negative pairs: 실제 LLM 오류, 별도 작성한 오류, stratified mutations. 전부 mutant로 대체하지 않는다.
- 오류 축: 누락/추가 호출, 시간, 인자 snapshot, 순서, sustain reset, edge 재무장, period/회차 갱신. 모델 밖 오류는 따로 표시한다.
- 정답: 독립 small-model bounded exhaustive evaluator 또는 검토된 전체 finite-state 모델을 사용한다. 유한 H의 정답은 그 범위 안에서만 사용한다.
- 지표: 잘못된 EQUIV, 잘못된 DIVERGE, 지원 거절, 미완료, runtime error를 분리; 반례 replay 및 과거 입력/기대·실제 ACTION.
- 비교: 단순 exhaustive exploration을 같은 모델/관측 계약의 기준으로 사용한다. 공유 runner를 쓰는 경우 탐색 알고리즘의 대조이며 frontend 독립 검증과 구별한다.
- 판단: 독립 정답과의 설명되지 않은 불일치는 강한 검증 주장을 막는다. 미완료는 false DIVERGE로 집계하지 않는다.
- 본문 결과: 유형별 검출/판정 표, 하나의 history-dependent 반례. shortest/earliest를 구현 보장 없이 주장하지 않는다.

### E3 — Application: 실제 LLM 생성 JoI에 얼마나 적용되는가?

- 입력: 검수해 확정한 Timeline + binding plan + 동일 JoI syntax/API/runtime 설명.
- 포함 계약: `Service.Method`당 서로 다른 selector 하나. selector 하나의 multi-device
  `all(...)` fan-out은 포함한다. 복수 selector가 필요한 요청은 조용히 제거하지 않고
  generation/preparation refusal로 전체 분모에 남긴다.
- NL→IR 품질은 가정 밖이다. 모델은 명세/문서를 받되 정답 코드, 시험 이력, fault labels, 탐색기 결과는 최초 생성 시 받지 않는다.
- 후보: 새로 동결한 과제에서 코드 생성. 생성 실패/준비 실패도 요청 전체 분모에 남긴다. 현 familiar-task 후보는 별도 개발 결과다.
- 기본 결과: 요청 전체 중 EQUIV 인증, DIVERGE, 지원 거절, 미완료, generation/preparation errors의 비율 + 단계별 비용.
- 이것은 NL 의도 정확도가 아니라 확정 명세에 대한 인증/불일치/적용률이다. 최종 코드의 독립 행동 정확도는 가능한 gold subset에서 별도로 평가한다.
- 오류 탐지 비교 후보: 동일한 code pairs에 (a) 고정 budget의 random/boundary input replay, (b) 전체 Explorer. LLM reviewer는 선택적 세 번째 family다. 두 comparator 모두 같은 확정 명세와 문서를 사용할 수 있어야 한다.
- replay에서 불일치를 못 찾은 결과는 test-pass로 표기한다. 이를 EQUIV 인증으로 혼동하지 않고 오류 검출/시간만 공통 비교한다.
- 외부 논문 방법: 동일 IR–code 계약을 다루는 기존 validator/실행 검사 방법의 적용 가능성을 우선 조사한다. ChatIoT/ARTEMIS의 NL authoring 정확도 경쟁을 필수로 강제하지 않는다. 타 논문 구현/semantic adaptation의 적합성은 아직 미확정이다.
- 실제 플랫폼: 선정한 복합 사례에서 JoI runtime의 service call log와 모델 trace를 대조한다. 물리 장치 응답/네트워크 보장을 제시하는 것은 아니다. 실제 runtime 접근이 없으면 해당 근거를 미확보로 표시한다.
- 판단: 실용 적용률이 낮으면 지원/준비/탐색 실패 원인과 실용 범위를 좁힌다. 검증만으로 코드가 수정되거나 생성 성공률이 올라갔다고 쓰지 않는다.
- 본문 결과: 전체 결과 분포, syntax-valid semantic fault 예, 대표 JoI 실행 사례.

### E4 — Cost: 어느 규모까지 검사하며 축소가 왜 필요한가?

- 질문: 입력/state/time 복잡도에 따른 판정 완료율과 비용, 각 축소의 효과는 무엇인가?
- 지원 범위 내 변동: 입력 축/도메인, sequential program size/분기, 대기 길이, cycle/state memory 및 분석 경로. 현재 미지원 nested/parallel 구성을 확대성 축으로 섞지 않는다.
- 비교: 같은 계약의 단순 exact exploration 대 전체 Explorer. 고정 H인 비교와 H 없는 closure 비교를 별도 보고한다.
- 필요한 ablation만 선택: event-time elision/상대 시간 병합 등 실제 켜고 끌 수 있는 메커니즘. input abstraction 제거 때문에 범위가 무한이면 작은 유한 subset에서 비교한다. 더 좁은 semantics로 바꾸고 속도 개선이라 부르지 않는다.
- 지표: 상태/전이 수, 완료율, wall time, peak RSS, median/p95/max; timeout/OOM/unknown 전부 포함한다.
- 판단: 더 빠르다는 결과가 없으면 속도 우위를 주장하지 않고 완료 범위를 보고한다. 새로운 의미 불일치가 있으면 최적화 주장을 중단하고 수정한다.
- 본문 결과: 복잡도별 완료/비용 plot과 메커니즘별 대조 표.

## 3. 현재 결정 수준

확정된 범위: 올바른 Timeline을 출발점으로 가정; 사용자/LLM 이해도 우위는 비핵심.
이번 권고: C1/C2와 E1–E4. 최종 사용자 승인이 있는 실험 protocol로 취급하지 않는다.
미확정: corpus 수·외부 출처·분할, code-generation model과 문서 budget, 정확한 외부 baseline, 반복 횟수, timeout/RSS, runtime 접근 및 repair 포함 여부.

실행 전 pilot 제안: 24개 개발 사례를 지연/지속/edge/snapshot/반복/ACTION 관측의 6개 범주에 4개씩 배치해 후보 생성/입력 replay/Explorer의 차이와 라벨 획득 가능성을 확인한다.
이는 표본 크기 확정이나 본 실험 결과가 아니다. 쉬운 정상 구현에서 단순 replay도 성공하고, history-dependent 오류에서 차이를 낼 수 있도록 양쪽을 확인한다.
탐색 결과를 보고 채택한 pilot 사례는 confirmatory set에 포함하지 않는다. 참조 라벨을 후보 생성 prompt에 노출하지 않는다.

권장 진행 순서: 지원 의미/taxonomy 점검 → 독립 interpreter/oracle 적합성 pilot → 새 과제/후보·비교 설정 동결 → E2/E3 → E4.
정확한 외부 baseline은 pilot의 계약 적합성을 보고 선정하되, 우열 결과를 보고 유리한 baseline만 선택하지 않는다.

## 4. 이전 문서와의 연결

- 2026-09-04 계획서(`experiment-plan.md` 등)는 2026-09-12에 삭제했다(git 이력). bounded-only 및 shortest/parallel-merge 표현은 사용하지 않는다.
- 현재 `explorer/docs/paper/EVALUATION.md`의 H=None 388개 집계는 기존 후보 재평가다. 새 독립 결과나 검증기 정확도 100%로 사용하지 않는다.
- 기준 의미와 H 없는 성공 조건은 `explorer/docs/model/VERIFICATION_CONTRACT.md`; 수작업 논증 상태는 `explorer/docs/proof/PROOF_OBLIGATIONS.md`를 따른다.
