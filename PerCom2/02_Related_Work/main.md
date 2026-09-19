# Related Work and Positioning

> SenSys 원문의 검증 기준에 따른 논리 순서를 유지한 축약본. 개별 연구 비교는 표로 정리했다. `overleaf-paper/main.tex`의 해당 절과 대응한다.

Verifying automations generated from natural language requires checking not only whether selected properties hold but also whether the code behaves as the user requested. However, the natural-language request itself is not an executable reference for comparison. We therefore compare prior work by the artifact analyzed, checking reference, and method (Table 1).

**When a verification reference already exists.** A rich body of work verifies trigger-action programming (TAP) rules with formal techniques. AutoTap~\cite{autotap} synthesizes or repairs TAP rules so that they satisfy user-specified safety properties expressed in linear temporal logic (LTL). TAPInspector~\cite{tapinspector} model-checks timing-aware rule sets for safety and liveness violations, and TAPFixer~\cite{tapfixer} repairs such violations. Related analyses uncover inter-rule and security vulnerabilities~\cite{iruler,soteria}, while HAWatcher~\cite{hawatcher} monitors deployed automations against mined invariants. These systems check properties of automation behavior, including temporal behavior and rule interactions.

Executable references are also available for some code-generation tasks. GPIoT~\cite{gpiot} evaluates generated signal-processing and machine-learning algorithm code with execution tests, while text-to-SQL evaluates generated queries against the execution results of gold queries~\cite{spider}.

**LLM-generated reactive automations.** Systems that generate automations from natural-language requests use different criteria and procedures to check their outputs. AutoIoT~\cite{autoiot_maude} checks generated rules against four inter-rule conflict types using Maude rewriting logic. ChatIoT~\cite{chatiot} translates natural language into Home Assistant automations and uses an LLM Evaluator to assess format compliance and request satisfaction.

AwareAuto~\cite{awareauto} constructs automation rules with event/state modes and timing conditions and supports user review, revision, and grounding in device interfaces. VETS differs in checking whether the state updates and action timing of JOI code, which implements such temporal behavior through variables and conditionals, preserve the behavior specified by the confirmed Timeline IR.

Outside automation, LACE~\cite{lace} back-translates generated access-control policies into natural language and uses a natural language inference (NLI) model to judge semantic equivalence with the original request, while separately checking policy conflicts with a satisfiability modulo theories (SMT) solver.

We ask whether specified automation behavior is preserved in separately generated reactive-temporal code. VETS uses user-confirmed Timeline IR as a common reference for code generation and verification and checks whether the generated code's timed action trace matches this reference.

**Table 1. Representative systems by artifact, checking reference, and method.** Entries summarize the indicated checks, not every system component or evaluation metric. TAP: trigger-action programming; LTL: linear temporal logic; NLI: natural language inference; SMT: satisfiability modulo theories.

| System | Artifact analyzed | Checking reference | Method |
|---|---|---|---|
| AutoTap~\cite{autotap} | TAP programs | User-specified LTL safety properties | Automata-based synthesis and repair |
| TAPInspector~\cite{tapinspector} | Timing-aware TAP rules | Safety and liveness properties | Model checking (NuSMV) |
| GPIoT~\cite{gpiot} | Generated IoT algorithm code | Manually authored test cases | Execution tests (offline evaluation) |
| AutoIoT~\cite{autoiot_maude} | Models of generated TAP rules | Four conflict definitions | State-space search in Maude |
| ChatIoT~\cite{chatiot} | Generated TAP representation | User request, context, and format requirements | LLM Evaluator |
| AwareAuto~\cite{awareauto} | Reactive-temporal rules and grounded JSON | User intent and device interfaces | User revision and deployment checks |
| LACE~\cite{lace} | Generated access-control policies | User request and policy-conflict definitions | NLI for meaning; SMT for conflicts |
| **VETS** | **Reactive-temporal JOI code** | **User's intended behavior specified in Timeline IR** | **Timed action-trace equivalence checking** |
