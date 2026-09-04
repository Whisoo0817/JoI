# Advice Change Register

사용자 지시에 따라 S3의 문제, contribution order, guarantee boundary, 7단계 flow는 승인된 것으로 간주하며 재확인을 요구하지 않는다. `optional-extension`은 모두 비활성 상태다.

| Advice ID | 분류 | S3 영향 section | 권고 | 범위 변화 | 상태 |
|---|---|---|---|---|---|
| A01 | clarification | §6, §11, §15.6 | `verification`을 IR semantic theorem과 bounded code-equivalence check로 나누어 명명 | 없음 | active |
| A02 | clarification | §1.1, §15.2 | confirmation은 intent correctness evidence가 아니라 specification-fixing operation이라고 반복 명시 | 없음 | active |
| A03 | evidence-needed | §9, §12.2 | production interpreter와 독립된 small-step evaluator 또는 semantics-derived oracle로 순환 검증 방지 | 없음 | active |
| A04 | evidence-needed | §12.3 | target behavior space를 corpus 판정 전에 동결하고 unsupported examples도 포함 | 없음 | active |
| A05 | evidence-needed | §12.2, §15.7 | E3에 natural LLM failures와 non-IR-derived held-out faults를 포함 | 없음 | active |
| A06 | clarification | §11, §18 | exact state equality 기반 BFS를 기본 Explorer로 두고 abstraction/POR은 기본 claim에서 제외 | 없음 | active |
| A07 | clarification | §13.4, §18 | LLM lowering을 사용하되 deterministic compiler가 불가능하다고 주장하지 않음 | 없음 | active |
| A08 | evidence-needed | §15.7 | PerCom systems-evidence 경향에 맞춰 real workloads, target hardware, tails/failures/provenance를 E1~E4 안에서 보고 | 없음 | active |
| A09 | optional-extension | §13.4 | deterministic compiler와 LLM lowering의 비교 | 있음: 새 비교 질문 | inactive |
| A10 | optional-extension | §14.6 | second backend portability study | 있음: backend-independence empirical claim | inactive |
| A11 | optional-extension | §1.3 | usability/human-subject study | 있음: 명시적 non-goal 회수 | inactive |
| A12 | optional-extension | §11 | partial-order reduction 또는 sound abstraction | 있음: 새 Explorer optimization | inactive |

## Gate G0

- 세 로컬 source가 식별되고 역할이 분리됨: PASS.
- legacy evidence가 predecessor evidence로 라벨됨: PASS.
- 네 가지 핵심 제외 범위가 기록됨: PASS.
- S3 §0, §1, §15, §16, §19의 순서와 범위를 유지함: PASS.
- 모든 후속 권고의 분류·영향 section·활성 상태를 기록할 register가 생성됨: PASS.
