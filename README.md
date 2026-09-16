# VETS / JoI — PerCom 논문 작업

2026-09-11 갱신. 이 문서는 프로젝트 배경과 논문 방향의 진입점이다.
**Explorer의 현재 상태·다음 작업은 [Explorer README](explorer/README.md) 한 곳에서 관리한다.**
검증 범위와 평가 수치를 이 파일에 복제하지 않는다.

## 논문의 문제와 범위

SenSys 2027에 제출했던 OVLA의 reject 리뷰를 바탕으로 PerCom 2027 논문을 준비한다.
현재 초록의 시스템 이름은 VETS이며 OVLA/VESTA는 이전 이름이다.
중심 질문은 **LLM이 생성한 스마트홈 자동화 코드가 기준 행동을 구현하는가**이다.
Timeline IR 자체를 독립적인 언어 연구로 전면에 내세우지는 않는다.

2026-09-11 framing 결정에 따라 Timeline을 모든 IoT automation을 위한 범용 공용 IR로
정당화하지 않는다. Timeline은 **NL→JoI 생성에서 표현력 높은 구현 언어의 여러 코드 idiom과
미세한 시간·상태·제어 흐름 오류를 syntax만으로 판별할 수 없기 때문에 필요한,
지원 JoI 범위의 per-automation executable behavioral specification**이다.
논문의 대비 축은 primitive/declarative 플랫폼과 code-based 플랫폼의 이분법이 아니라,
닫히고 명시적인 검증 기준과 표현력 높은 구현 언어의 역할 차이다.
현재 구현·평가 backend는 JoI 하나이며 openHAB/Home Assistant/SmartThings는 현재의
platform-general guarantee가 아니다. 상세 결정은
[2026-09-11 problem framing](skill_result/06_manuscript/problem_framing_codegen_validation_2026-09-11.md)을 따른다.

2026-09-09 교수님과 논의한 결정에 따라 **LLM-generated와 기존 생성·검증 흐름을 유지**한다.
결정론적 IR→JoI compiler는 **future work**로 두며, 현재 논문의 구현·실험 범위에 포함하지 않는다.

```text
자연어 → Timeline IR 후보 → 사용자 확인 → 기준 명세
                                         ├→ 코드 생성
                                         └→ IR 실행
같은 초기 환경·입력 이력에서 IR과 코드의 timed ACTION trace 비교
```

- 확인된 IR을 검증 기준으로 삼는다. IR 확인이 자연어 의도 정확성이나 사용자 확인 성공률을 보장하지 않는다.
- 정확한 검증 기준은 selector-free IR과 확정 binding plan의 쌍이다. 현재는
  `Service.Method`당 서로 다른 selector 하나만 허용하며, 한 `all(...)` selector의
  multi-device fan-out은 지원한다.
- 고정된 프로그램·초기 상태·시간별 입력에 대한 실행 결과의 유일성이 결정론성이다. LLM 생성의 재현성과 다르다.
- 결정론성과 검증 soundness는 정리·증명으로, 구현 적합성은 코드 대응·실험으로 뒷받침한다.
- 표현 범위는 문법·연산자·합성·제외 사례로 설명한다. 유한 corpus를 전체 자동화의 모집단으로 보지 않는다.
- 스마트홈/JoI가 현재 범위다. 다른 플랫폼·물리 시스템의 정확성이나 일반화를 이미 입증했다고 쓰지 않는다.
- on-device와 특정 LLM 크기는 핵심 전제가 아니다. IR→코드는 LLM lowering을 사용한다.
- user study는 진행하지 않는 방향이다. 논문의 중심은 확인된 명세에 대한 코드 행동 검증이다.

## 처음 읽을 자료

현재 논문 Flow 대화는 [2026-09-11 problem framing](skill_result/06_manuscript/problem_framing_codegen_validation_2026-09-11.md)과
[canonical paper flow](skill_result/06_manuscript/paper_flow_ir_contract_2026-09-10.md)에서 이어간다.
현재 위치는 **NL→JoI 생성 결과 검증을 중심으로 절별 flow와 contribution wording을 동결하는 단계**이며,
구체적 실험 설계는 본체 Flow 완성 뒤다.
[Related Work 원문 대조와 통합 목록](skill_result/02_literature/related_work_review_2026-09-09/README.md)에
OVLA 인용·최근 문헌·예상 반박·차별성 후보를 정리했다. 기존의 넓은 novelty 설명보다 이 대조를 우선 참고한다.
매 논의에서 전체 논문 내 위치를 먼저 짚고 구체적인 설명·후보를 제시한다.

도메인 배경이 필요할 때 아래 순서로 읽고, 구현 작업 재개는 Explorer README에서 시작한다.

| 순서 | 자료 | 역할 |
| --- | --- | --- |
| 1 | [JOI_SPEC](docs/JOI_SPEC.md) | JoI DSL과 파이프라인 배경. 오래된 경로·의미는 현 구현/검증 계약과 대조 |
| 2 | [이전 제출본](docs/OVLA_SenSys2027.pdf) | 문제 설정·이전 시스템과 평가 |
| 3 | [원래 리뷰](docs/review.txt) | 사용자 확인 경계, compiler 대안, 검증 보장, 일반화·재현성 지적 |
| 4 | [Timeline IR 재설계](docs/New_OVLA_Timeline_IR_Design_and_Verification.md) | 설계 배경. 제안과 구현 완료를 구별 |
| 5 | [현재 초록 초안](docs/abstract_draft.txt) | 확정본이 아닌 서사의 출발점 |

## 제출 계획과 원고

사용자 확인: 논문은 아직 미등록이며 **9월 11일까지 등록할 계획**이다.
그때까지 `formally verifies`를 뒷받침하도록 보강하고, 미달하면 초록을 수정한다.
이를 등록 완료로 바꾸거나 합의한 판단 시점 전에 초록을 선제 수정하지 않는다.

기존 기록에서 2026-09-07 확인한 일정은 registration 9월 11일 AoE,
최종 제출 9월 18일 AoE다. 공식 요건을 새로 확인한 기록은 아니며 실제 제출 때
[공식 CFP](https://percom.org/call-for-papers/)와 [HotCRP](https://percom2027.hotcrp.com/)를 확인한다.
당시 기록상 기술 내용 9쪽과 참고문헌 전용 최대 1쪽, IEEE 2단·double-blind다.

초록은 위 초안이 기준이다. [이전 LaTeX](docs/ovla0606.tex)와
[참고문헌](docs/refs.bib)은 PerCom 완성 원고가 아니다.
[리뷰 대응](skill_result/01_intake/reviewer_objection_register.md),
[주장 범위·집필 준수사항](PerCom/WRITING_GUARDRAILS.md),
[관련연구](skill_result/02_literature/related_work_review_2026-09-09/README.md)는 필요할 때 참조한다.
`skill_result/`는 2026-09-12에 압축 정리했다(옛 번호 계획서·advisor 요약·형식 설계 초안 삭제, git 이력에 보존).
실험 작업 공간은 `PerCom/08_Evaluation/`이다.

## 작업 위치와 관리

| 위치 | 역할 |
| --- | --- |
| [timeline_ir/](timeline_ir) | IR 파싱·검사·렌더링·mapping |
| [files/](files) | 서비스 명세·생성 prompt·장치 hints |
| [lowering/run_local_ir.py](lowering/run_local_ir.py) | IR 기반 후보 생성 |
| [explorer/README.md](explorer/README.md) | 검증 구현·문서·현재 TODO의 진입점 |
| [dataset.csv](dataset.csv), [candidates/](explorer/candidates) | 기준 IR/binding과 생성 후보 |
| [sensys/](sensys) | 이전 논문 근거. 현재 결과와 혼용하지 않음 |
| [PerCom/](PerCom/README.md) | 최종 집필 작업 공간. 절별 초안과 E1–E4 실험 코드·데이터·결과(`08_Evaluation/`) |

현재 작업 브랜치는 `paper`다. 먼저 `git status --short`로 사용자 작업을 확인한다.
미커밋·untracked 파일을 임시 파일로 간주하지 않고, 과거 평가를 덮어쓰지 않는다.
[문서 관리 규칙](explorer/README.md#기록-보존과-경로-변경)을 따른다. 정리 전 README·계획·실험 메모는
[압축 기록](explorer/docs/archive/pre-consolidation-2026-09-08.zip)에 원문 그대로 보존했다.
