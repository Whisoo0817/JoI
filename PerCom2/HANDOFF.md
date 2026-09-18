# PerCom2 집필 인계

갱신일: 2026-09-18. 사용자가 대화에서 확정한 작성 지침과 현재 반영 상태를 기록한다. 이후 사용자 지시가 이 문서보다 우선한다. 아래 내용은 새 실험 결과나 모든 절의 수정 완료를 뜻하지 않는다.

## 1. 최우선: SenSys 원문 보존

- **SenSys의 문장 흐름·주장·문체·단어 선택은 교수님이 검토한 결과이므로 최대한 보존한다.**
- 변경된 방법·실험·포지셔닝 때문에 필요한 부분과 사용자가 요청한 압축 부분만 수정한다.
- 단순한 문체 개선, 더 자연스럽게 보이기 위한 재표현, 동의어 교체를 하지 않는다. 원문을 유지할 수 있으면 유지한다.
- 분량보다 논리 흐름이 우선이다. 중복 설명과 긴 예시부터 줄인다.
- 삭제·압축 후 앞뒤 연결, 지시어, First·Second 등의 열거 구조를 확인한다. 새 개념을 갑자기 넣거나 설명 없이 결론으로 건너뛰지 않는다.
- Intro의 초기 분량 목표는 2페이지 첫 번째 column까지였으나, 사용자가 흐름을 위해 이를 넘어도 된다고 명시했다.

## 2. 원고 기반과 수정 범위

- PerCom2는 SenSys 기반에서 필요한 부분을 조금씩 바꾸는 작업 공간이다. 기존 PerCom의 서술 전체로 돌아가지 않는다.
- 각 절의 현재 영문은 `main.md`, 한글 검토본은 `main_ko.md`에 둔다. `SenSys_version.md`와 `PerCom_version.md`를 다시 병렬로 만들지 않는다.
- Overleaf 원고는 [main.tex](../../overleaf-paper/main.tex)이다. 해당 절을 수정하면 PerCom2 영문·한글과 동기화한다.
- 검증·구현과 Evaluation은 기존 PerCom의 Behavioral Explorer 버전으로 교체했다. 본문에서는 검증·구현이 §6, Evaluation이 §7이다. 기존 폴더명 `08_Evaluation`은 유지한다.
- 제목·Abstract·Figure 1은 VETS 버전이다. **별도 요청 없이 Abstract를 수정하지 않는다.**
- 원본 SenSys와 기존 PerCom 자료는 참고용으로 보존한다.

## 3. Timeline IR의 포지셔닝

- 핵심 표현: **explicit temporal control flow**, **control flow along a time axis**.
- 스케줄, wait, delay, timer는 언제 실행이 진행되는지를, 순서·분기·반복·종료는 어떻게 진행되는지를 명시한다. 단순한 문장 나열이나 실행 순서만을 뜻하는 time axis가 아니다.
- Timeline IR은 **실행 가능한 중간 표현**이며, 생성된 JOI 코드의 **timed action trace**를 검사할 정확한 행동 기준을 제공한다.
- IR이 주어진 초기 상태와 timed input sequence에서 기대 timed action trace를 정한다. IR 자체를 하나의 raw trace 또는 low-level trace라고 부르지 않는다.
- 코드의 구문이나 제어 흐름 그래프가 IR과 구조적으로 같은지를 검사한다고 쓰지 않는다. 비교 대상은 관찰되는 동작과 발생 시각이다.

## 4. Authoring·렌더링·사용자 가정

- Authoring에서 사용자가 IR을 명세로 확정하는 단계는 유지한다.
- 렌더링을 핵심 stage, IR의 최종 목적, 주요 contribution처럼 쓰지 않는다.
- JSON, 결정론적 자연어 렌더링, 향후 LLM 설명은 IR의 흐름을 표현·활용하는 방식이다. Intro에서는 Scope and assumptions에서 확장 가능성으로 다룬다.
- 렌더링의 readability·faithfulness, 사용자의 오류 식별 정확도, LLM의 이해 향상을 입증했다고 주장하지 않는다. 렌더링 텍스트 차이를 근거로 내세우지 않는다.
- **확정된 IR이 사용자 의도를 올바르게 담는다고 가정한다. 사용자 연구로 이 가정을 검증하지 않았다.** 잘못된 IR을 승인하면 그 잘못된 명세를 검증한다는 한계를 유지한다.
- 우리의 보장은 정해진 입력 범위와 실행 규칙 아래의 IR–코드 부합성이다. 자연어 의도부터 코드까지의 무조건적 정확성을 주장하지 않는다.
- C1의 중심은 시간적 제어 흐름과 실행 가능한 행동 기준이다. 렌더링·여러 표현 방식에 관한 추가 문장으로 되돌리지 않는다.

## 5. 용어와 Intro 편집 지침

- `JOI`는 모두 대문자로 표기한다.
- `user's intended behavioral specification`은 유지한다.
- Intro에서 확정 전 IR을 `candidate`라고 부르지 않는다. 이는 Motivation의 검사 대안 제목이나 검증 대상 코드의 일반적 명칭을 모두 금지한다는 뜻은 아니다.
- Intro에 binding·compiler 설명을 넣지 않는다.
- 불명확한 `declared model` 대신 `specified input ranges and execution rules`처럼 뜻이 드러나는 표현을 쓴다.
- `no existing system` 같은 단정은 완화한다. 기존 연구가 다루는 시간·검증 기능을 부정하여 차별화하지 않는다.
- 삭제한 `LLM calls are confined ...`부터 `LLM-free`까지의 두 문장은 다시 넣지 않는다. 로컬 생성·검증 설명을 모두 금지한 것은 아니다.
- Figure 1 예시에는 그림에서 생략된 1초 tick period를 본문 한 줄로 설명한다.
- Deployment setting과 C3 On-device contribution은 유지한다. C3를 evaluation 결과 나열 중심의 기여로 되돌리지 않는다.

## 6. 로컬 모델과 성능 주장

- 로컬 모델이 Timeline IR과 JOI 코드를 모두 생성한다는 범위를 명확히 한다. Authoring만 로컬인 것처럼 쓰지 않는다.
- 배포된 자동화가 로컬에서 실행된다는 문장은 삭제한 상태로 유지한다.
- **“로컬 모델이므로 검증이 더 필요하다”는 추가 논리는 넣지 않는다.** 사용자가 논의 후 넣지 않기로 결정했다.
- 모델 생성 비용과 검증 비용을 구분한다. 검증 지연으로 9B 모델의 엣지 실행 가능성을 입증했다고 쓰지 않는다.
- 현재 Intro의 검증 시간은 379회 attempted checks의 프로세스 시간 중앙값 62 ms, p95 158 ms이다. 프로세스 시작·준비를 포함하지만 LLM 생성 시간은 포함하지 않는다. 이를 다른 실험 조건의 지연으로 일반화하지 않는다.
- E3의 `Qwen3.5-9B-fp8` 생성 기록만으로 가정용 엣지 기기에서의 모델 실행 가능성이 입증되는 것은 아니다. 구체적인 기기·양자화·최대 메모리·생성 지연 근거와 구분한다.

## 7. Related Work

- SenSys의 논리 순서를 유지하며 줄인다. 기존 연구를 바로 나열하지 않고, 검증 기준이 왜 중요한지 설명하는 첫 문단을 유지한다.
- 마지막 문단 앞에 `Positioning VETS.` 같은 굵은 소제목을 붙이지 않는다.
- 비교 표는 `System / Artifact analyzed / Checking reference / Method`의 네 열이다. 중복이 많던 `Checked behavior / scope` 열은 삭제했다.
- VETS의 Checking reference는 **User's intended behavior specified in Timeline IR**이다. `Confirmed IR`만 적어 사용자 의도와의 관계를 가리지 않는다.
- VETS의 Method는 **Timed action-trace equivalence checking**이다. 세부 보장 조건은 본문에서 설명한다.
- 각 셀은 가능한 짧게 쓰되 비교 대상의 의미나 검증 범위를 왜곡하지 않는다.

## 8. Motivation과 judge 실험 표시

- **SenSys의 요구사항 → 검사 대안 → LLM judge → 설계 방향 흐름을 유지한다.**
- 구문·구조 비교, 생성 모델의 자체 점검, 사용자 코드 검사를 한 Candidate 문단으로 압축하고 바로 별도 LLM judge로 연결한다.
- 렌더링 가독성을 정당화하는 논리로 연결하지 않는다. `the remaining candidate`, `every candidate eliminated`처럼 모든 대안을 배제했다고 쓰지 않는다.
- 옛 SenSys judge 수치와 voting 실험 대신 현재 PerCom 실험을 사용한다.
- **작은 표:** 동일 원본 217개를 각각 세 번 평가했을 때 판정이 모두 같지 않은 프로그램 비율. Qwen 0.0%, GPT 16.6%, Claude 9.7%. 데이터 행이 하나여도 유지한다.
- **막대그래프:** 모든 judge가 세 번 중 두 번 이상 승인한 원본 52개의 재작성 168개에 대한 거부율. 현재 실험의 11개 세부 변환을 사용한다. 옛 AND·DM 유형을 가져오지 않는다.
- 유형: VAR, CMP, UNIT, GRP / BR, ELS / DLY, UNR, PHS, WPC, PHV. Notation·Logic·Temporal 범주 사이를 구분하고 유형별 표본 수를 표시한다.
- 그래프 세로축은 **Rewrite rejection rate (%)**이다. 표와 그래프의 모집단·측정 정의가 다르므로 두 비율의 차이를 재작성 효과로 해석하지 않는다.
- 0%인 유형도 남긴다. 모든 모델이 0%인 DLY도 삭제하지 않는다. 개별 0 숫자는 생략 가능하다. `Zero-height bars indicate no rejected variants.`라는 캡션 추가 문장은 제안만 했으며 현재 원고에는 넣지 않았다.
- Qwen의 높은 Temporal 거부율을 모든 모델이나 모든 시간 변환에 일반화하지 않는다. 개별 유형은 3~39개로 표본이 작으며 일반적인 난이도 순위를 주장하지 않는다.
- 동등성의 근거가 Explorer라는 점, 공통집합 조건, 반복 판정 변동과 재작성 효과의 구분을 유지한다. 이 실험을 Explorer 정확도의 독립 검증으로 쓰지 않는다.
- 원본의 E3 출처, 모델 설정, Qwen 판정 완성용 추가 호출, PHV의 초기 결과 확인 후 추가 경위는 현재 실험 상세 부록에 기록했다.

## 9. 파일·그림·검토 표시·푸시

- Overleaf 그림은 `figures/sensys/`와 `figures/percom/`으로 분리하여 모두 보존한다. 버전 교체 시 실제 경로를 확인한다.
- 현재 **§1–§3은 검정**, §4 이후 본문과 표·그림 캡션은 연한 회색이다. 미수정 절의 회색 표시를 임의로 없애지 않는다.
- 스타일만 변경할 때 본문 문장을 함께 바꾸지 않는다.
- 푸시 요청에는 필요한 확인만 하고 빠르게 처리한다. 커밋 내역을 길게 설명하지 않는다.
- 현재 원격은 GitHub이며 직접 Overleaf Git 원격이 아니다. 푸시 후에는 “Overleaf에서 GitHub → Pull하면 반영됩니다”라고 안내한다.

## 현재 상태와 후속 작업 주의

- 2026-09-18 마지막 Overleaf 연동 GitHub 저장소 푸시: `bd3b0ef` — §1–§3 용어 통일과 §6 행동 검증 설명 개편. 직접 Overleaf Git 원격은 없으며, Overleaf에서 GitHub → Pull해야 웹 프로젝트에 반영된다.
- §1–§3의 편집 및 §6–§7 교체를 반영했다. §4–§5와 후반부에는 SenSys의 옛 검증·렌더링 설명이 남아 있다. 전체 원고가 Explorer 계약에 맞춰 정리된 상태는 아니다.
- 다음 절 수정 시 사용자가 지정한 범위에서 이 불일치를 해결하되, 원고 전체를 일괄 재작성하지 않는다.
- 이 `HANDOFF.md`는 PerCom2의 로컬 집필 지침이다. Overleaf 저장소 밖에 있으므로 Overleaf 푸시 대상과 구분한다.

### §6 사용자 피드백 반영 초안 (2026-09-18)

- 사용자가 §1–§3의 이야기와 연결하여 §6을 쉽게, 짧게 다시 쓰도록 요청했다. 현재 초안은 **같은 입력과 시각 → 각자의 의미로 실행 → timed action 비교 → 가능한 실행 탐색 → 판정과 피드백** 순서다.
- §6 영문 본문은 공백 기준 제목 포함 1,924 → 755단어로 축소했다. 소절은 `Comparing Behavior under Shared Inputs`, `Exploring Possible Executions`, `Verdicts and Feedback`이다.
- 본문에서 reaction 정의, 수식, 방법별 표, DBM 및 widening 상세, Algorithm 1, 명제 S와 증명 개요를 분리했다. 타이머–카운터 관계는 반복을 모두 펼치지 않고 검사하는 이유를 설명하는 한 문단으로 남겼다.
- 기존 기술 내용은 §6 폴더의 `appendix.md` / `appendix_ko.md`와 Overleaf의 `Behavioral Validation: Execution Rules and Soundness` 부록에 보존했다. 전체 논문 분량까지 줄었다는 뜻은 아니며, 부록 분량은 추후 조정 대상이다.
- PerCom2 §5에는 명제 D와 진행 가정이 아직 없으므로, 옮긴 부록은 존재하지 않는 §5 명제를 참조하지 않고 필요한 결정성·유한 실행·시간 진행 가정을 직접 명시한다. 새로운 구현 증명을 완료했다고 주장하지 않는다.
- PerCom2 영문·한글과 Overleaf `main.tex`에 동기화했다. 현재 시스템 개요 그림 번호는 3으로 맞췄다. §4 이후 회색 표시는 유지한다. 원본 PerCom 파일은 수정하지 않았다.
- Tectonic PDF 빌드와 diff 공백 검사 통과. 미정의 상호참조·중복 label·overfull box가 없음을 확인하고 §6 조판을 검토했다. 기존 font 대체 및 PDF 버전 경고는 남아 있다.
- §4–§5와 기존 후반부의 bounded horizon 등 옛 설명은 여전히 후속 수정 대상이다. 이번 작업은 §6 및 그 기술 부록에 한정한다.

### §6 한글 인라인 피드백 반영 (2026-09-18)

- 합의한 여섯 의견을 한글·영문·Overleaf에 동기화했다. 본문에서 그룹 명령 순서 예외, 공통 시간 규칙의 중복 문장, 단일 인스턴스 범위 문장을 삭제했다. 상세 조건은 부록에 유지한다.
- 검사 환경을 “설정한다”로 표현하고, 외부 입력을 “센서값과 기기 상태 등의 입력”으로 풀었다. 입력 전체를 이벤트라고 바꾸지 않는다.
- 시간 진행은 “실행에 영향을 줄 수 있는 다음 시점으로 논리 시각을 이동하고 두 실행을 이어 간다”로 설명한다. 저장값 보존은 유지한다.

### §6 입력값 묶기 설명 수정 및 빌드 지침 (2026-09-18)

- 입력값 묶기는 “조건 판단에만 사용하는 값 중 양쪽 프로그램의 모든 조건에서 판단 결과가 같은 값끼리 묶는다”로 풀어 쓴다. 액션 인자나 다른 계산에 쓰이는 값은 실제 값의 차이까지 검사한다고 설명한다. 기호 방법의 이름과 세부 지원 조건은 부록에 둔다.
- 한쪽 종료 후 다른 쪽을 계속 검사한다는 문장은 본문에서 삭제하고 부록에 유지했다. 한글·영문·Overleaf에 동기화했다.
- **문장 검토·수정 단계에서는 PDF를 자동 빌드하지 않는다. 사용자가 요청할 때 빌드한다.** 이번 변경은 소스만 검사했다.

### §6 시간 구현과 부록 제외 (2026-09-18)

- JOI는 같은 대기를 실행 횟수 카운터 또는 저장한 시작 시각과 현재 시각의 차이로 구현할 수 있다고 설명한다. 지원되는 각 구현의 액션·시각을 검사한다는 범위를 유지하며, 임의의 시각 연산 전체를 지원한다고 확대하지 않는다.
- 카운터의 시작값·증가·초기화 시점을 IR 경과 시간과 연결하고, 이 관계로 여러 상태를 함께 검사하여 개별 값의 열거를 줄인다는 효과를 설명한다. 집합 확대의 개별 문장은 삭제했다.
- 입력값 차이로 명령 인자나 이후 동작이 달라질 수 있다는 이유를 추가했다. 판정 문단에는 입력·상태를 묶더라도 가능한 행동과 표현된 상태 전체를 검사한다는 조건을 남겼다.
- **부록까지 포함한 9페이지 제한을 고려하여 행동 검증 부록을 논문에서 제외했다.** Overleaf 해당 부록과 §6의 부록 참조를 제거했다. `appendix.md` / `appendix_ko.md`는 로컬 기술 참고자료이며 논문에 포함하지 않는다. 앞선 부록 이동 기록보다 이 결정이 우선한다.
- 영어는 §1–§3과 §6의 기존 `IR interpreter`, `periodic executions`, `action arguments`, `elapsed time`, `actions and timing`에 맞췄다. 관련 없는 문장은 재표현하지 않았다. 한글·영문·Overleaf 동기화 후 소스만 검사했으며 PDF는 빌드하지 않았다.

### §6 판정·구현 문단 피드백 (2026-09-18)

- “계속되는 실행”을 “종료 없이 반복되는 자동화”로 풀고, 이후 도달할 수 있는 상태가 검사 범위에 포함되며 액션·시각이 일치할 때 동등 판정을 내린다고 쓴다. 어려운 execution-time horizon 문장은 삭제했다.
- Z3를 산술식과 조건을 분석하는 도구로 먼저 소개한 뒤 보장의 가정을 설명한다. 정의 없이 solver부터 등장시키지 않는다.
- 사용자 요청으로 §6의 실제 기기 동작·모델 부합성 한계 설명을 삭제했다. IR이 사용자 의도에 부합하는지는 별도라는 범위는 유지한다.
- 한글·영문·Overleaf에 반영했다. PDF는 빌드하지 않는다.

### §1–§3 입력·출력 용어 정규화 (2026-09-18)

- 입력의 기술 용어는 `timed input sequence`, 출력은 `timed action trace`로 통일한다. `history`는 사용하지 않는다. 한글은 처음에 입력값과 변화 시각을 나타내는 “입력 시퀀스(timed input sequence)”로 풀고, 이후 “입력 시퀀스”로 줄인다.
- §1에서 두 용어를 풀어 설명하고, 검사 범위를 “허용된 모든 초기 상태와 입력 시퀀스”로 명시했다. `same`은 양쪽 실행의 공통 조건, `every allowed`는 검사 범위다. 초기 상태는 입력 시퀀스와 다른 개념이므로 필요한 곳에 유지한다.
- §1 그림 caption·C2, §2 VETS 비교 문단, §3 재작성 검증·결과 문장의 용어를 맞췄다. 일반적인 동작 설명, 기존 연구의 검사 방법, R1·R2 요구사항까지 일괄 치환하지 않는다.
- 사용자 답변에 따라 §3의 “어떤 기기 동작이 언제 발생하는지는 유지한다”는 쉬운 풀이를 보존하고, 뒤의 Explorer 검사 문장에서 timed action trace와 연결했다.
- **이번 편집은 §1–§3의 한글·영문과 Overleaf 해당 절만 수정했다. §4·§5는 수정하지 않는다. §6도 이번에는 변경하지 않았다.**
- 사용자의 §6 분량 질문은 현재 분량이 아니라 추가하려던 설명의 양에 관한 것이었다. 추가안은 가능한 다음 입력·상태 검사와 검사 완료를 연결하는 3–4문장 정도이며, §6을 600–650단어로 압축하라는 지시는 없었다.
- PDF는 빌드하지 않고 소스 동기화와 diff만 확인했다.

### §6 탐색 과정 보강 (2026-09-18)

- 사용자 승인에 따라 §6 도입에서 모든 허용 초기 상태·입력 시퀀스의 timed action trace를 검사한다는 범위를 명시했다.
- 탐색 문단을 “가능한 다음 입력 → 양쪽 실행 및 명령 비교 → 아직 포괄하지 않은 다음 상태·실행 추가 → 반복”의 네 문장으로 정리했다. 마지막 판정 문단은 중복을 줄이고 종료 경로의 trace 일치, 반복 실행의 후속 상태 포괄, 묶인 상태 전체의 검사 조건을 연결했다.
- §6의 input history / 입력 이력도 timed input sequence / 입력 시퀀스로 맞췄다. 반례 재생 문장에 동일 용어를 사용한다.
- 한글·영문·Overleaf §6만 반영했다. 다른 절은 변경하지 않았고 PDF도 빌드하지 않았다.

### 주요 경로

- [현재 Intro](01_Intro/main.md) / [한글](01_Intro/main_ko.md)
- [현재 Related Work](02_Related_Work/main.md) / [한글](02_Related_Work/main_ko.md)
- [현재 Motivation](03_Motivation/main.md) / [한글](03_Motivation/main_ko.md)
- [재작성 그래프 생성 코드](03_Motivation/figures/render_judge_rewrites.py)
- [judge 실험 집계 원자료](../PerCom/03_Motivation/motivation_judge/results/summary_common.json)
- [judge 실험 프로토콜](../PerCom/03_Motivation/motivation_judge/PROTOCOL_2026-09-16.md)
- [현재 검증·구현](06_Code_Generation_and_Behavioral_Validation/main.md)
- [현재 Evaluation](08_Evaluation/main.md)
- [SenSys 전체 원문](../docs/ovla0606.tex)
- [Overleaf main.tex](../../overleaf-paper/main.tex)
