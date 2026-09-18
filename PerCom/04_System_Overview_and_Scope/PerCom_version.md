# System Overview — PerCom working draft

> 2026-09-18: 중복 축약 반영본. 아래 본문은 변경 표시를 제외한 현재 원고다. 이번 수정 직전 Overleaf 커밋 `82d4073` 대비 삭제 취소선·추가 빨간색은 `overleaf-paper/main.tex`에서 확인한다.

Figure~\ref{fig:arch} shows the VETS workflow from specification confirmation to code generation and behavioral checking. The following stages keep the confirmed IR and binding fixed while generating, checking, and optionally revising the code.

\begin{figure*}[t]
  \centering
  % User-maintained workflow figure. Label suggestions are tracked locally.
  \includegraphics[width=\textwidth]{../../docs/figs/system.pdf}
  \caption{System workflow with a confirmed Timeline IR as the reference for
  checking generated code. The dashed arrow indicates code revision using a
  counterexample.}
  \label{fig:arch}
\end{figure*}

**Execution target.** We instantiate VETS on a commercial
IoT platform whose execution DSL is JoI. A JoI automation consists of a start
schedule (`cron`), a re-execution interval (`period`), and a
script body (`code`). When the `period` parameter is positive,
the body is executed again after the previous iteration completes and
the interval elapses. Temporal behavior such as edge detection,
sustained conditions, and counting must be implemented with persistent
variables and ordinary conditionals. JoI therefore serves as the executable
artifact produced by the lowering phase as well as the primary artifact
checked by the verifier.

**Specification confirmation and code generation.** The LLM first proposes a candidate Timeline IR. The user reviews the candidate and may edit it or request an LLM-assisted revision before confirmation. Timeline IR specifies the temporal behavior (§5), while the confirmed binding identifies the target devices. We assume that the confirmed IR and binding capture the user's intended behavior and targets. Only after this reference is fixed does VETS lower the IR to JoI code.

**Behavioral verification.** The verifier receives two artifacts:
the confirmed Timeline IR, which serves as the behavioral reference, and the
generated JoI code. The verifier first performs a static syntax check on the
JoI code. It also checks that the IR--code pair falls within the
supported execution model. Behavioral Explorer then jointly explores the IR
and code execution states under shared timed input histories and allowed
initial states (§6). Their semantic interpreters produce action traces,
which the Explorer compares for matching actions and timing. This check runs
without any LLM call. Successful verification certifies trace preservation
within the declared execution model. A mismatch yields a counterexample,
while unsupported cases and incomplete exploration remain uncertified.

**Counterexample feedback.** A failing program is not deployed
directly. The counterexample can be returned to the lowering stage to
guide revision of the JoI code alone. The confirmed IR is not changed
during this repair process. It remains the user-approved reference.
The revised code is checked again against the same IR and binding.
This feedback is an optional use of the counterexample. Verification covers
one automation pair at a time under the declared model, including its device
binding and timing rules. Interactions among deployed automations and physical
device dynamics are outside this check.

---

## 이전 편집 기록 (2026-09-18 축약 전, 논문 본문 아님)

- 원문은 이 폴더의 `SenSys_version.md`에 있는 요약이 아니라 `../../docs/ovla0606.tex`의 `\section{System Overview}`다. 문장별 대응은 `OVERVIEW_FLOW_COMPARISON.md`에 기록했다.
- Authoring/Verification의 두 phase 설명과 ①–⑦ 단계별 열거를 없앴다. LLM의 IR 제안 → 사용자 검토·수정·확정은 유지하며, semantic parsing·IR rendering·확인 UI의 구현과 성능은 설명하지 않는다.
- 기존 `../../docs/figs/system.pdf`를 위 figure 환경에 임시로 배치했다. 경로는 이 Markdown 파일의 디렉터리 기준이다. Overleaf 이관 시 그림을 복사하고 경로를 바꾼다. 기존 그림의 Authoring Phase, Semantic Parsing, IR Rendering, Event Synthesis, Deploy/Reject는 현재 본문과 완전히 일치하지 않으므로 최종 그림으로 교체해야 한다. 본문은 기존 단계 번호나 Event Synthesis 상자에 의존하지 않는다.
- O2의 JoI 구성과 persistent-variable 설명은 SenSys에서 유지했다. `on each tick`은 현재 실행 계약의 회차 종료 후 period 대기 의미로 수정했고, edge hub 배치 강조는 삭제했다.
- O3는 SenSys의 candidate 설명·확정 문장·lowering 문장을 재사용했다. 사용자 수정 또는 LLM-assisted revision은 앞선 논의에 따른 workflow 설명이며, 별도 agent 모듈이나 NL→IR 정확도·확인의 용이성·사용성 평가를 주장하지 않는다.
- O4는 SenSys의 두 입력·syntax check·LLM-free 검사 구조를 유지했다. 사전 FSM 구성·고정 boundary-event suite 설명은 현재 Explorer의 공동 상태 탐색과 모델 내 trace 보존 검사로 교체했다. 검증 경로별 완료 조건과 증명은 §6에서 설명한다.
- O5의 code-only 수정과 확정 IR 유지 문장은 원문에서 보존했다. 자동 repair 성공·budget 소진 정책·자동 배포를 현재 평가 결과처럼 쓰지 않으며, 반례를 이용한 선택적 코드 수정과 재검증만 설명한다.
- `Three checks, three places`와 `Roles of the IR`는 별도 문단으로 반복하지 않는다. 확정 IR의 코드 생성 입력·검증 reference 역할은 O1에, 지원 검사·syntax check는 O4에 통합했다. 상세 binding selector 규칙은 열거하지 않는다.
- Timeline IR의 연산자·실행 의미·결정론성 명제는 §5에 유지한다. 현재 §4는 전체 흐름과 입력 가정·검증 범위만 설명한다.
- 문체 점검: SenSys의 문장 구조와 `serves as` 같은 원문 표현을 유지했다. 초안의 전체 흐름·IR 역할 반복을 합쳤고, 추가한 방어적 대비와 수사적 마무리는 넣지 않았다.
