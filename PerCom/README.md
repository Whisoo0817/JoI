# PerCom 최종 집필 작업 공간

작성일: 2026-09-12.

이 폴더는 사용자가 지정한 PerCom 최종 집필 작업 공간이다. 기존 `skill_result/`의 자료는 원래 위치에서 참고한다. 기존 문서의 `skill_result/` 내부 저장 규칙에 대한 이번 사용자 지정 경로이며, 자료를 이동하거나 기존 계획·코드·그림을 변경하지 않는다.

## 먼저 읽을 문서

1. [최종 집필 참고·준수사항](WRITING_GUARDRAILS.md): 연구 범위, FSM·시간·LTL/TAP 비교, lowering, 향후 연구, 사용할 표현과 근거 한계.
2. [Introduction Figure 1·2 및 Table 1 체크리스트](1_Intro/Figures/FIGURE_REQUIREMENTS.md): Introduction에 들어갈 동기 도표의 역할, 시각 편집 요구와 판정 불변성 실험의 재현성 조건.

`WRITING_GUARDRAILS.md`의 **최신 최우선 결정**이 PerCom 원고 전체에 우선한다. 핵심은 스마트홈 자동화 전체에 대한 generality를 주장하지 않는 것, JoI를 현재 유일한 backend로 두는 것, Home Assistant 실험을 계획하지 않는 것, deterministic compiler를 비교하지 않은 Future Work로 두는 것이다. openHAB은 시간이 남고 imperative-code backend로 실제 adapter와 평가를 완료할 때만 선택적으로 검토한다.

## 원고 섹션 구조

각 섹션 폴더에는 정확히 다음 세 파일이 있다.

- `SenSys_version.md`: `docs/ovla0606.tex`에 제출되었던 구성과 주장을 보존한 비교 기준.
- `PerCom_version.md`: 최신 VETS framing과 검증 계약을 적용한 실제 영문 원고 초안.
- `HANDOFF.md`: 채택·폐기·미확정 사항, 근거 경로와 다음 수정 작업.

| 순서 | 섹션 폴더 |
| ---: | --- |
| 0 | [Abstract](0_Abstract/) |
| 1 | [Introduction](1_Intro/) |
| 2 | [System Overview and Scope](2_System_Overview_and_Scope/) |
| 3 | [Timeline IR](3_Timeline_IR/) |
| 4 | [Code Generation and Behavioral Validation](4_Code_Generation_and_Behavioral_Validation/) |
| 5 | [Implementation](5_Implementation/) |
| 6 | [Evaluation](6_Evaluation/) |
| 7 | [Related Work](7_Related_Work/) |
| 8 | [Limitations and Future Work](8_Limitations_and_Future_Work/) |
| 9 | [Conclusion](9_Conclusion/) |

`PerCom_version.md`는 계획 메모가 아니라 본문에 들어갈 문장으로 작성한다. 미완성 근거는 대괄호 placeholder로 남기며, `HANDOFF.md`의 제한을 해소하기 전에는 결과처럼 단정하지 않는다. 섹션 폴더의 직접 파일은 위 세 개를 유지하고, 그림·표 작업 자료는 해당 섹션의 `Figures/` 같은 하위 폴더에 둔다. **실험의 방식·코드·데이터·결과는 2026-09-12부터 `6_Evaluation/` 아래 실험별 하위 폴더(`E1_adequacy/`, 이후 `E2_*/`, `E3_*/`, `E4_*/`)에 둔다.** `skill_result/`에는 새 실험 자료를 만들지 않는다.

두 문서는 2026-09-12 사용자 메모를 정리한 **집필 준비 자료**다. 새 구현, 실험 실행, 그림 수정, 완성 원고 또는 결과 감사가 아니다. 사용자 결정과 구현으로 확인된 사실, 증거가 필요한 해석을 구별한다. 체크박스는 앞으로 수행할 작업이며 완료를 뜻하지 않는다.

## 기존 근거로 돌아가는 경로

| 용도 | 기준 자료 |
| --- | --- |
| 최신 논문 논의와 이전 결정 | [skill_result 진입점](../skill_result/README.md) |
| 문제 정의·연구 경계 | [2026-09-11 framing](../skill_result/06_manuscript/problem_framing_codegen_validation_2026-09-11.md) |
| 본문 절 구성 | [Paper flow](../skill_result/06_manuscript/paper_flow_ir_contract_2026-09-10.md) |
| 현재 E1–E4 골격 | [평가 계획](../skill_result/05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md) |
| E1 실험 코드·데이터·결과 | [E1_adequacy](6_Evaluation/E1_adequacy/README.md) (2026-09-12 Stage A 12건, 감사 반영) |
| 실제 시간·입력·관찰·인증 계약 | [Explorer 검증 계약](../explorer/docs/model/VERIFICATION_CONTRACT.md) |
| 증명과 신뢰 기반 | [증명 의무](../explorer/docs/proof/PROOF_OBLIGATIONS.md) |
| 기존 평가와 한계 | [평가 요약](../explorer/docs/paper/EVALUATION.md) |
| 최근 동기 검증 파일럿 | [파일럿 기록](../skill_result/05_experiment_plan/motivation_pilot_2026-09-11/README.md) |

사용자 메모는 이후 집필 방향에 반영하되, 메모만으로 구현 지원이나 실험 결과가 생긴 것으로 취급하지 않는다. 특히 이전 문서의 E1/E2 번호, bounded-only 표현, 시스템 이름·초록은 최신 결정과 대조한다. 이 문서에서는 현 framing의 작업명인 VETS를 사용하며 최종 제목 선정은 별도다.
