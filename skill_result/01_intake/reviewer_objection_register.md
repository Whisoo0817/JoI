# Reviewer Objection Register

상태 값은 `resolved-by-scope`, `requires-design`, `requires-evidence`, `optional-extension`, `retired-claim`이다.

| ID | 실제 reviewer objection | 출처 | 새 flow에서의 처리 | 상태 | 후속 artifact |
|---|---|---|---|---|---|
| R1 | 사용자가 잘못된 IR을 승인하면 잘못된 명세를 충실히 검증할 뿐이다 | S2 #453A, #453B, #453C | user confirmation을 correctness proof가 아닌 specification boundary와 명시적 assumption으로 한정 | resolved-by-scope | `new_direction_scope.md`, C1/C2 anti-claims |
| R2 | usability와 non-expert confirmation ability가 검증되지 않았다 | S2 #453A/B/C | readability/usability 주장을 철회하고 평가 범위에서 제외 | retired-claim | S3 §1.3, E1~E4 범위 |
| R3 | bounded verification이 full equivalence처럼 보인다 | S2 #453A/C | finite environment model과 명시적 bounds 안의 reachable equivalence로 정확히 한정 | requires-design | Explorer model, observation model, E3/E4 |
| R4 | 왜 deterministic IR→JoI compiler를 만들지 않는가 | S2 #453B | LLM lowering의 불가피성을 주장하지 않으며 checker가 lowering mechanism과 직교함을 명시. 비교 실험은 현재 optional | requires-design | `lowering_decision.md` |
| R5 | `verification` 용어가 formal proof를 과도하게 암시할 수 있다 | S2 #453B/C | IR semantics의 theorem과 bounded code-equivalence verdict를 분리하여 정확히 명명 | requires-design | proof obligations, claim register |
| R6 | 단일 platform/DSL에 비해 generalization 주장이 과도하다 | S2 #453A | backend-independent observation vocabulary는 설계 목표로 두되, single backend에서는 portability를 주장하지 않음 | requires-evidence | E2/E3 limitations; second backend optional |
| R7 | on-device 필요성이 약하다 | S2 #453A | 새 논문의 중심을 on-device에서 behavioral verification으로 이동. edge 실행은 pervasive deployment context와 cost measurement로만 다룸 | retired-claim | PerCom alignment, E4 |
| R8 | related work 대비 차이와 성능 비교가 불명확하다 | S2 #453B | reference specification, execution model, explored space, equivalence criterion, guarantee boundary의 5축으로 비교 | requires-evidence | `sota_gap_map.md` |
| R9 | benchmark, prompts, seeds, quantization, algorithms, simulators가 불충분하게 공개됐다 | S2 #453B | 새 실험 pack은 inputs, evaluator, 실패/skip/timeout, revision, seeds와 artifact paths를 고정 | requires-evidence | `execution-bridge.md`, artifact plan |
| R10 | 놓친 faults가 어떤 현실적 오류인지 분석이 부족하다 | S2 #453A/C | false accepts와 false rejects를 fault family별로 완전 보고하고 counterexample/failure taxonomy를 유지 | requires-evidence | E3, decision gates |
| R11 | mutation operators와 checker checkpoints가 같은 IR construct에서 나와 99.3%가 낙관적일 수 있다 | S1 §8.2 자체 limitation | independent failures, held-out transformations, non-IR-derived faults를 포함 | requires-evidence | E3 controls |

## 우선순위

1. R3/R5: 보장의 정확한 의미를 semantics, observation, Explorer bound로 고정한다.
2. R4: lowering choice를 숨기지 않고, verifier 필요성을 compiler infeasibility에 의존시키지 않는다.
3. R8/R11/R10: novelty 및 checker evidence의 순환성을 제거한다.
4. R6/R9: single-backend와 reproducibility 경계를 명시한다.
5. R1/R2/R7: 되살리지 않을 주장을 유지한다.

