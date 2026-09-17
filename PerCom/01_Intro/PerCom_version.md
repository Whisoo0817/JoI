# Introduction — PerCom working draft

> 2026-09-18: 축약본을 유지하고 LLM judge 문단의 연결 문장을 보완했다. Overleaf 본문은 변경 표시를 제거한 최종 텍스트다.

Large language models (LLMs) enable users to create smart-home automations tailored to their needs. A user states the desired behavior in natural language, and an LLM turns it into automation code the platform can execute. Before deployment, the generated code must be checked against the requested behavior. The natural-language request expresses the user's intent, but an automated behavioral check requires an explicit reference for the expected actions and their timing.

**Why this is hard.** The target automations are inherently *reactive-temporal*. Their actions depend on changing inputs, execution history, and elapsed time. In our setting, generated imperative code implements these relationships through persistent variables, conditions, and timers. A condition that holds now may require a different action depending on whether it has just become true or has remained true for several minutes. Correctness therefore concerns the sequence and timing of device actions across an input history.

**Running example.** Suppose a user requests ``whenever the temperature rises above 25°C, turn on the air conditioner.'' We read ``rises above'' as an edge-triggered intent: the AC should be switched on once per upward crossing, not continuously while it stays hot. Figure~\ref{fig:idiom} shows three lowerings, sketched in JoI, the automation DSL of our target platform (§4). All three implementations execute once per second. Implementation (a) detects the crossing by comparing the previous and current temperature readings while (b) keeps a flag that is set on firing and reset when the temperature falls back below the threshold. Both produce the same action trace, whereas (c) incorrectly fires on every tick while the temperature remains above the threshold. Because repeated `On()` commands leave the AC in the same visible state, the user may see nothing wrong.

**Existing checks.** Existing automation tools check properties such as safety and inter-rule conflicts~\cite{autotap,iotsan}, while generation systems assess output validity or present proposed behavior for user confirmation~\cite{chatiot,awareauto}. In a workflow that generates code, confirming that behavior leaves a further check: whether the implementation preserves it. An executable reference makes the expected actions and timing available for this comparison.

Another option is to ask an LLM to judge whether the code matches the request. Our experiments show that LLM judges can produce inconsistent verdicts both across behaviorally equivalent implementations and across repeated evaluations of the same code (§3). These results motivate a behavioral check whose verdict follows from the confirmed specification and the code's execution.

**VETS.** To address these challenges, we present VETS. It places Timeline IR between the natural-language request and the generated code, making the intended event, state, and temporal relationships explicit through composable operators. The user confirms the IR and device binding before the LLM generates JoI code. Given an initial state and timed input history, the IR's deterministic operational semantics produce the expected timed action trace. Behavioral Explorer jointly explores the IR and code under shared inputs and compares their actions and timing without LLM calls. A mismatch yields a counterexample for code revision, while unsupported cases and incomplete exploration remain uncertified.

**Scope and assumptions.** VETS targets natural-language commands specifying reactive-temporal behaviors supported by Timeline IR. We assume that the user-confirmed IR and binding accurately capture the intended behavior and targets. Under this assumption, successful verification certifies that the generated code preserves the specification's timed action traces within the declared execution model.

**Contributions.**

- **C1. Timeline IR:** We introduce an executable formal specification that makes the event, state, and temporal relationships implicit in natural-language requests explicit. It defines temporal operators and their composition with deterministic operational semantics.
- **C2. Behavioral Explorer:** We propose a checker that jointly explores IR and code execution states, using input partitioning, state reuse, and timer abstractions to reduce exploration overhead. A completed equivalence check certifies trace preservation under the declared model, and a detected mismatch yields an executable counterexample.

In our evaluation, Explorer identified 68 behavioral mismatches among 382 generated JoI candidates, all confirmed by its concrete replay. In a separate scale experiment, it completed checks for 28 of 30 parameterized programs, compared with 12 for explicit-state exploration (§7).

---

## 이전 편집 기록 (2026-09-18 축약 전, 논문 본문 아님)

- S7의 IR 설명 두 문장은 temporal operators의 조합으로 행동 발생 시점과 시간에 따른 행동 전개를 명시하고, 결정론적 실행 의미로 기대 timed action traces를 산출하는 흐름으로 보강했다. `per-automation`은 삭제하고 `a behavioral oracle`로 표현했다.

- C1은 의도 명시화 → temporal operators와 그 조합의 결정론적 실행 의미 → 주어진 초기 상태·timed input trace에 대한 유일한 기대 timed action trace의 순서로 구체화했다. 제어 흐름 종류를 나열하는 대신 `temporal operators and their composition`으로 표현했다.

- S2는 SenSys 원문 구조를 유지한다. Furthermore 문장은 상태 갱신과 제어 흐름을 명시적으로 관리해야 하는 imperative code라는 설명으로 수정했다. First 문장은 원문을 유지하며, pre-label 문장은 `exhaustively`와 복수 시퀀스 표현을 사용한다.
- S1 첫 문장의 관련 연구 인용은 후속 선정 시 추가한다.
- S3 마지막의 `cron`, `period`, `code`, `:=`, `=` 문법 설명 괄호를 삭제했다. 1초 반복 실행 전제는 S3 본문에서, boilerplate 생략은 Figure 1 캡션에서, persistent initialization은 코드 주석에서 설명한다.
- Figure 1 최종 줄 번호가 정해지면 (a)의 이전·현재 값 비교와 (b)의 flag 설명에 해당 줄 번호를 연결한다. 현재는 번호를 임의로 넣지 않았다.
- 세 구현의 1초 반복 실행은 S3 본문의 `All three implementations execute once per second.`로 명시하며 그림·캡션에는 중복하지 않는다. Figure 1 캡션에는 `Platform boilerplate is omitted.`를 반영한다. 최종 코드에 blocking wait/delay가 있으면 1초 실행 전제의 유효성을 확인한다.
- S4는 SenSys 원문을 복원하고 `Many prior`와 `is treated as`만 반영했다. 마지막 문장의 `unaddressed`와 이에 따른 쉼표를 삭제했다.
- S5는 기존 문단 흐름을 유지한다. `the gap remains wide open`, `readily`, `effectively a solved problem`, `must settle for weaker`, `error-prone` 등의 단정을 삭제·완화했다. 사용자 확인과 실행 코드 검증의 역할을 구분하고, `no existing system` 문장은 삭제하는 대신 결정론적 검사의 필요성을 설명하는 문장으로 교체했다.
- S6는 LLM judge 대안 → 판정 일관성의 필요성 → §3 결과 예고 → 독립적인 행동 검사의 필요성 흐름으로 작성했다. 결과는 동등 구현 간·동일 코드 반복 평가의 판정 불일치를 한 문장으로 요약한다. 모델명·수치·실험 조건은 §3에 두며, 원문의 모델 크기·클라우드 프라이버시·지연 주장과 judge 전반에 대한 단정은 삭제했다.
- S7은 시스템 소개 → 자연어와 코드 사이에 놓인 Timeline IR의 두 역할 소개 → 의도에 내포된 행동 관계의 명시화 → 결정론적 실행 의미와 확정 IR을 기준으로 한 코드 검증의 순서로 수정했다. `Its key idea`와 `To this end`로 IR을 재소개하던 구조를 없애고, 참조 명세와 실행 가능한 검증 기준이라는 두 역할을 먼저 제시했다. `at authoring time`, 렌더링을 통한 사용자 검토·확인 설명, IR 경계만의 bounded 검사, 안전한 edge 배포 주장과 마지막 필요성 반복 문장은 삭제했다. 사용자 확인은 조건으로 두며, Timeline IR의 명시적 실행 의미에 근거해 `executable formal specification`과 `deterministic operational semantics`를 사용한다. Explorer의 `formally verifies`는 선언한 실행 모델 안의 trace 보존 인증을 뜻한다. 공동 상태 탐색·동일 timed input 조건의 상세는 뒤로 넘기고 S7에서는 timed action trace 비교만 설명한다. 마지막 문장은 LLM의 생성 역할과 확정 명세에 근거한 결정론적·LLM-free 검증을 대비하며 마무리한다. 근거는 `explorer/docs/model/VERIFICATION_CONTRACT.md`의 D/S와 `explorer/docs/proof/PROOF_OBLIGATIONS.md` 및 `TIMER_ZONES.md`의 경로별 논증이다. 결정론성만으로 formal을 정당화하지 않는다. 본문 흐름을 위해 device binding 삽입구는 제거하되, binding과 의도에 맞는 명세 확정 가정·지원 범위는 S8에서 설명하고, 미완료 판정과 실행 모델의 상세는 방법론에서 설명한다.
- S8은 SenSys S8·S9를 3문장으로 통합했다. Timeline IR의 지원 범위, 사용자 확정 IR·기기 binding이 의도를 정확히 표현한다는 가정, 성공한 검증의 보장이 선언된 실행 모델 내 IR→JoI timed action trace 보존에 있다는 경계를 남겼다. 렌더링·확인의 용이성·슬롯 나열·Layer A/B 구분·user study 미수행 설명과 모호한 목표의 예시·인용은 이 문단에서 제외했다. 미완료 판정은 방법론에서 별도로 설명한다. 굵게 표시는 SenSys S8·S9를 합친 원문과 비교했다.
- SenSys S10은 Intro에서 삭제한다. edge·프라이버시·클라우드 배제 주장은 현재 중심 기여가 아니며, 실행 환경·비용의 필요한 사실은 구현·평가에서 다룬다.

- Contributions는 Timeline IR과 Behavioral Explorer의 두 기술적 기여로 작성했다. C1은 렌더링 대신 실행 가능한 formal specification과 결정론적 실행 의미를, C2는 모델 내 timed action trace 검증과 입력 분할·상태 재사용·타이머 추상화를 설명한다. 도입은 SenSys의 시스템 전체 기여 요약 역할을 살려 deterministic pre-deployment behavioral check와 사용자 확정 IR 기반 형식 검증을 두 문장으로 설명한다. 최초성·자동 배포·on-device 기여는 제외했다. Repair는 독립 기여로 두지 않고, C2의 반례가 불일치를 식별하고 코드 수정을 도울 수 있다는 활용 목적을 명시했다. SenSys C4는 독립 항목 대신 기여 뒤의 실증 결과 한 문장으로 바꿨다. 근거는 E3_application/RESULTS.md의 기존 생성 코드 재검증 결과와 E4_cost/RESULTS.md의 explicit-state baseline 비교이며, 새 생성 실험·전체 시스템 안전성·탐색량 감소에 따른 동일 비율의 실행시간 개선을 주장하지 않는다. S12의 반복 마무리 문단은 이번 초안에 추가하지 않았다. 각 항목의 굵게 표시는 대응하는 SenSys 도입·C1·C2·C4와 비교했다.
