# Motivation 문단 흐름 — SenSys ↔ PerCom

기준: [SenSys 원문](SenSys_version.md), [PerCom 초안](PerCom_version.md), [최종 실험 결과](motivation_judge/RESULTS_2026-09-16.md). M1–M7은 PerCom 초안의 본문 문단 순서다. 현재 내용은 검토할 초안이며 확정 원고가 아니다.

| SenSys — 원문 순서와 역할 | PerCom — 수정 및 대응 |
| --- | --- |
| 도입: 배포 전 gate 필요, 요구사항·후보·실험 예고 | **M1 통합.** 첫 문장을 보존하고 reference와 판정 일관성을 바로 설명한다. 유일하게 남은 후보라는 예고는 삭제한다. |
| R1 Reference: 요청의 의도가 검사 가능한 artifact로 주어지지 않음 | **M1 유지·수정.** 자연어를 실행 가능한 명세로 명시해야 한다는 문제로 한정한다. 모든 oracle이 불가능하거나 사용자 확인의 용이성을 보장한다는 뜻으로 쓰지 않는다. |
| R2 Stability: 동등 구현에는 같은 verdict | **M1 유지·보강.** 동일 코드 반복 평가도 같은 판정을 해야 한다는 조건을 추가한다. |
| R3 On-device: privacy·즉시 판정·edge 필수 | **현재 초안에서 보류.** On-device·SLM은 전체 초안 완성 후 통합한다. SenSys의 강한 privacy·즉시 판정 요구는 그대로 복원하지 않는다. |
| Candidate 1: 구문·구조 비교 | **M2 앞부분.** 원문의 reference text 비교와 Fig. 1 idiom 예시 연결을 보존하고 Intro와 중복되는 상세는 압축한다. |
| Candidate 2: 생성 모델 self-checking | **M2 중간.** 원문의 후보 소개 문장을 보존한다. SimuHome의 workflow self-correction 한계를 인용하되 JoI 검사 또는 모든 모델의 불가능성으로 확대하지 않는다. |
| Candidate 3: human inspection | **M2 뒷부분.** 후보 소개와 TAP-Debug의 event/state 오독 근거를 보존한다. readable rendering이 필요하다는 결론은 삭제한다. |
| Remaining candidate: 별도 LLM judge | **M3 도입.** 요청과 코드를 judge에게 제공하는 설명은 보존한다. reactive-temporal 코드의 판정 일관성을 평가하는 자체 실험으로 직접 연결한다. Moon 인용 문장은 압축 과정에서 제외했다. |
| 예전 재작성 실험 설정·Fig. 2 | **M3 및 Table 1로 교체.** 본문은 원본 217개의 반복 평가와 세 모델 공통 통과 원본 52개의 재작성 168쌍을 설명한다. 전체 검증 후보 471쌍은 실험 상세에 남긴다. None과 rewrite의 분모·정의를 구분한다. |
| 모델별 재작성 flip·voting 분석 | **M4–M5로 교체.** Qwen 시간 구조 재작성 31/48, loop unroll 10/11, period halve 16/17. GPT·Claude는 동일 코드 반복 평가에서 각각 36/217·21/217 불일치. 옛 수치와 voting 결론은 삭제한다. |
| 모든 probabilistic judge가 unstable, 마지막 후보 탈락 | **M6 수정.** 검사한 조건의 일관성 한계가 독립 행동 검사를 동기화한다. 버그 탐지 평가가 아니며 rewrite 결과는 선택된 공통집합에 조건부임을 밝힌다. |
| Surviving design: R1–R3를 만족하는 유일한 artifact·verifier | **M7 수정.** reference 요구와 일관성 관찰을 함께 받아, NL → Timeline IR → imperative code로 연결한다. 확정 IR에서 코드를 생성하고 같은 실행 명세의 timed action trace 보존을 검증한다. IR 정확성은 가정으로 둔다. 유일성·on-device·렌더링·bounded-only 표현은 사용하지 않는다. |
| 시스템 그림 | **§4로 이동할 역할.** Motivation 끝에 복제하지 않고 다음 절의 workflow 설명으로 연결한다. |

## 작성·검토 기준

- 원문과 동일한 구절은 일반체, 수정·추가 구절은 굵게 표시한다. 표·캡션은 신규 실험 자료이므로 차분 표시를 생략한다.
- 본문에서는 실험이 보이는 두 종류의 불일치를 설명한다. None과 rewrite 비율을 직접 차감하거나 cloud 결과를 재작성 민감성으로 단정하지 않는다.
- 동등성 확인에는 VETS Explorer를 사용했음을 공개한다. 본 실험은 Explorer 정확도의 독립 검증이 아니다.
- 자세한 재현 조건과 사후 추가 변환의 경위는 편집 메모에 추적하고 최종 실험 상세/부록에 공개한다. 현재 문서가 부록 작성을 완료한 것은 아니다.
