# System Overview 문단 대응

기준: `../../docs/ovla0606.tex`의 System Overview. 이 폴더의 `SenSys_version.md`는 이전 개요의 요약이다. 본문 O1–O5는 `PerCom_version.md`의 다섯 문단이며 figure 환경은 문단 수에서 제외한다.

| SenSys 원문 | PerCom 배치와 처리 |
| --- | --- |
| `OVLA implements the aforementioned design as a two-phase pipeline.` 및 authoring/verification 소개 | **O1.** 첫 문장 골격과 `the system checks the generated code against the confirmed IR before deployment`를 유지했다. 두 phase 대신 reference 확정 → 코드 생성·검사의 흐름을 썼다. IR의 두 역할을 이 문단에 통합했다. |
| `Execution target.`의 JoI 플랫폼, cron/period/code, persistent variables 설명 | **O2.** 원문 문장을 최대한 유지했다. 플랫폼 배치를 과장하지 않도록 edge hub 강조를 제외했다. `on each tick`은 현재 계약에 맞게 회차 종료 후 period만큼 기다리는 것으로 수정했다. |
| `Figure ... shows the complete pipeline.` 및 두 phase 재설명 | **O1에 통합.** 그림 참조 하나를 남기고 중복 설명을 삭제했다. 기존 그림 자체는 사용자 요청으로 임시 유지한다. |
| Phase 1의 Command Analysis, Candidate IR Extraction, feasibility gate, IR Rendering, User Confirmation, Lowering | **O3.** candidate의 의미, `Once confirmed ...`, `Only after this reference is fixed ...`를 유지했다. 사용자 검토·직접 수정·LLM-assisted revision과 확정 IR/binding 가정을 추가했다. Semantic parsing·rendering·상세 gate 열거는 삭제했다. |
| Phase 2의 `The verifier receives two artifacts ...` 및 static syntax check | **O4 앞부분.** 원문 두 문장을 유지하고 지원 실행 모델 검사로 연결했다. |
| FSM 도출 → Event Synthesis → 두 simulator → Trace-Equivalence | **O4 중간.** 현재 Explorer의 IR–code 공동 상태 탐색으로 교체했다. 같은 timed input·초기 상태 조건 아래 의미 실행기에서 나오는 timed action traces를 비교한다. LLM-free 검사는 유지한다. |
| passing program 배포, 실패 시 counterexample을 lowering에 반환, IR 고정, repair budget | **O4 끝과 O5.** 동등 인증·반례·미완료를 구분한다. 원문의 실패 코드 처리와 code-only 수정·IR 유지 문장을 재사용하되 선택적 수정 경로로 한정했다. 수정 후 재검증을 명시하고 자동 배포·budget 정책을 삭제했다. |
| `Three checks, three places.` | **O4에 통합.** 정적 검사와 행동 검사의 연결만 남기고 별도 반복 문단은 삭제했다. |
| `Roles of the IR.`의 네 역할 | **O1·O3에 통합.** 확정 reference와 코드 생성 입력 역할을 남긴다. rendering과 exemplar routing을 Overview의 별도 역할로 열거하지 않는다. |

## 그림과 본문의 임시 차이

- 원본 그림: `../../docs/figs/system.pdf`. 재작성·이미지 편집 없이 그대로 참조한다.
- 본문은 기존 그림의 ①–⑦ 번호, Authoring Phase, IR Rendering, Event Synthesis라는 단계 구분을 설명하지 않는다.
- 최종 그림에서는 IR 후보 제안과 사용자 확인을 간결하게 유지하고, confirmed IR에서 generation과 reference execution으로 갈라지는 경로를 강조한다.
- Explorer의 최종 결과는 동등성 확인·반례가 있는 불일치·미완료를 구분한다. 기존 그림의 Deploy/Reject만으로 이 구분을 표현했다고 보지 않는다.
- repair는 counterexample → LLM code generation 점선이며, 확정 IR을 바꾸는 화살표를 두지 않는다.
