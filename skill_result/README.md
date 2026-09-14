# skill_result — VETS(PerCom 2027) 연구 기록

2026-09-12 압축 정리. 이 폴더는 **논문 방향·문헌·계획의 기록**이다. 실험의 방식·코드·데이터·결과는
[`../PerCom/6_Evaluation/`](../PerCom/6_Evaluation/)에 두고, 원고는 [`../PerCom/`](../PerCom/README.md)에서 쓴다.
삭제한 옛 파일(2026-09-04 계획서, advisor 요약, 형식 설계 초안, 문헌 카드, 구 E3 v1/v2 실행)은 git 이력에만 남는다.

## 읽는 순서

1. [`06_manuscript/problem_framing_codegen_validation_2026-09-11.md`](06_manuscript/problem_framing_codegen_validation_2026-09-11.md) — **최우선 framing.** Timeline은 범용 IoT IR이 아니라 NL→JoI 생성 결과의 행동 검증에 필요한 per-automation executable behavioral specification.
2. [`06_manuscript/paper_flow_ir_contract_2026-09-10.md`](06_manuscript/paper_flow_ir_contract_2026-09-10.md) — 절별 flow와 Timeline IR 계약.
3. [`05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md`](05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md) — E1–E4 골격. E1 절은 2026-09-12 경계 표 설계로 갱신.
4. [`../PerCom/WRITING_GUARDRAILS.md`](../PerCom/WRITING_GUARDRAILS.md) — 집필 시 우선 결정(generality 미주장, JoI 단일 backend, HA 실험 없음, compiler는 future work).

## 확정된 방향 (요약)

- 검증 기준 = **확정 Timeline + binding plan**(`Service.Method`당 selector 하나, `all(...)` fan-out 지원, 복수 selector는 fail-closed 거절).
- 대비 축은 "닫힌 명시적 검증 기준 vs 표현력 높은 구현 언어". primitive/declarative 대 code-based 이분법이 아니다.
- NL→IR 정확도·사용자 이해도·user study는 필수 평가에서 제외. deterministic compiler는 비교하지 않은 future work.
- 결정성은 고정 프로그램·초기 상태·입력 이력에서 timed ACTION trace가 유일하다는 의미론적 성질이며 실험 지표가 아니다.
- E1 = IR 표현 적합성(경계 표 사례 연구), E2 = validation fidelity(독립 oracle), E3 = 실제 LLM 생성 JoI 적용, E4 = 비용·축소 효과.
  2026-09-04 이전 문서의 E1=interpreter conformance 번호는 폐기.
- 명세 후보 여러 개를 trace로 고르게 하는 확장, prose/flat/full 생성 비교, E1의 타 표현(TAP/LTL/FSM) 직접 비교는 폐기 또는 보류.

## 현재 상태 (2026-09-14)

| 실험 | 상태 | 위치 |
|---|---|---|
| E1 | 종료(2026-09-13). corpus 100(IN_SCOPE 92), depth 20건 이력 53/53 정확(선정 건수, coverage 아님), 경계 probe 3건. 원고 초안 검토 대기 | `../PerCom/6_Evaluation/E1_adequacy/E1_SUMMARY.md` |
| E2 | 완료(2026-09-14). 독립 정답기, 140쌍 중 판정 130·어긋남 0. 원고 초안 검토 대기 | `../PerCom/6_Evaluation/E2_fidelity/E2_SUMMARY.md` |
| E3 | 개발 단계 H=32 감사 결과만 존재(`05_experiment_plan/results/E3/heldout-gemma-v3-h32/`). 동결 protocol 재실행 필요 | — |
| E4 | 미착수 | — |
| Fig2 동기 파일럿 | 기록 있음 | `05_experiment_plan/motivation_pilot_2026-09-11/` |

## 폴더

- `01_intake/`: 리뷰 반박 목록, 이전 논문 주장·근거 목록.
- `02_literature/`: `related_work_review_2026-09-09/`(원문 대조, 우선 참고), `percom/`(venue 요건·exemplar), `references.bib`.
- `05_experiment_plan/`: E1–E4 골격, 선행 파이프라인 평가 비교, 동기 파일럿, 구 E3 결과·manifest(provenance).
- `06_manuscript/`: framing·flow 결정, 제목 후보·초록, `flow_discussion_2026-09-09.md`(결정 이력, 근거 참조용).
