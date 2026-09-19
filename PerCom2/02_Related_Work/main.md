# Related Work and Positioning

> SenSys 원문의 검증 기준에 따른 논리 순서를 유지한 축약본. 개별 연구 비교는 표로 정리했다. `overleaf-paper/main.tex`의 해당 절과 대응한다.

Prior automation verification has checked rules against specified safety and liveness properties, while code-generation evaluations have used test cases or gold execution results as references. When automations are generated from natural-language requests, checking these properties must be accompanied by checking whether the code implements the particular behavior requested. The request itself, however, is not a reference that can be executed for comparison, making it important to examine how each system represents the requested behavior and what it checks against. We organize prior work from this perspective. Table 1 compares representative systems by the artifact analyzed, checking reference, and method.

**When a verification reference already exists.** A rich body of work verifies trigger-action programming (TAP) rules with formal techniques. AutoTap~\cite{autotap} synthesizes or repairs TAP rules so that they satisfy user-specified safety properties expressed in linear temporal logic (LTL). TAPInspector~\cite{tapinspector} model-checks timing-aware rule sets for safety and liveness violations, and TAPFixer~\cite{tapfixer} repairs such violations. Related analyses uncover inter-rule and security vulnerabilities~\cite{iruler,soteria}, while HAWatcher~\cite{hawatcher} monitors deployed automations against mined invariants. These systems check properties of automation behavior, including temporal behavior and rule interactions.

A reference is also available for generation targets whose domain supplies an executable oracle. GPIoT~\cite{gpiot} generates signal-processing and machine-learning algorithm code from natural-language requirements and evaluates generated code with execution tests. Outside IoT, text-to-SQL evaluates generated queries against the denotations of gold queries~\cite{spider}. In these evaluations, the test cases or gold results provide the reference.

**LLM-generated reactive automations.** Systems that generate automations from natural-language requests use different criteria and procedures to check their outputs. AutoIoT~\cite{autoiot_maude} checks generated rules against four inter-rule conflict types using Maude rewriting logic. ChatIoT~\cite{chatiot} translates natural language into Home Assistant automations and uses an LLM Evaluator to assess format compliance and request satisfaction.

AwareAuto~\cite{awareauto} constructs automation rules that users can review and revise, grounds them in device interfaces as trigger-action pairs in JSON, and passes them to an automation manager. This rule representation includes event/state modes and timing conditions. VETS targets JOI scripts that implement temporal behaviors such as edge detection and sustained conditions through variables and conditionals. VETS therefore checks whether the generated implementation's state updates and action timing preserve the behavior specified by the confirmed Timeline IR.

Outside automation, other approaches also compare generated artifacts against the original request. LACE~\cite{lace} back-translates a generated access-control policy into natural language and judges semantic equivalence against the original request with a natural language inference (NLI) model; it separately checks policy conflicts with a satisfiability modulo theories (SMT) solver. Its request-conformance judgment thus concerns policy meaning, while its formal check concerns policy conflicts.

Building on these studies, we ask whether specified automation behavior is preserved in separately generated reactive-temporal code. VETS constructs Timeline IR from the natural-language request and uses the confirmed IR as both the basis for code generation and an executable reference for verification. Within the specified input ranges and execution rules, Behavioral Explorer checks whether the generated code produces the same timed action trace as the IR for every allowed initial state and timed input sequence. This guarantee assumes that the confirmed IR captures the user's intended automation.

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
