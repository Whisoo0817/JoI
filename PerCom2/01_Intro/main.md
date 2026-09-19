# Introduction

> SenSys 원문을 기반으로 수정한 VETS 초안. Why this is hard 문단은 원문 흐름을 유지하되 명령형 코드와 요청별 검증 기준에 관한 설명을 수정했다. Running example과 기존 검사 설명을 축약하되 논리 연결을 유지하고, LLM judge 설명은 기존 검사 문단에 통합했다. 분량보다 흐름을 우선한다. `overleaf-paper/main.tex`의 Introduction과 내용이 동일하며, 그림 경로는 LaTeX 프로젝트 기준이다.

Internet of Things (IoT) automation is moving toward code generation with large language models (LLMs)~\cite{gpiot,awareauto}. A user states the desired behavior in natural language, and an LLM turns it into a reactive rule the platform can execute. Yet the final step of this workflow, deciding *whether the generated code is correct to deploy*, has no deterministic gate. The missing piece is a reference to check the code against; the natural-language request contains the intent, but not in a form that can serve as a rigorous baseline for automated testing.

**Why this is hard:** The core challenge stems from the absence of a verifiable reference baseline. The target automations are inherently *reactive-temporal*. They are *reactive* because their execution is driven by asynchronous events and conditional triggers,
and *temporal* because their behavior unfolds over time through schedules, periodic executions, and sustained state durations (e.g. ``if it persists for more than N minutes'').
Driven by timers, counters, and multi-step state, the correct behavior of an automation must be evaluated across an entire timeline rather than a single discrete instant. Furthermore, in our setting, these temporal behaviors are deployed as imperative code implemented through variable updates and conditionals.
Validating their correctness presents two key challenges. First, no request-specific test oracle is provided in advance.
Unlike text-to-SQL (Structured Query Language) or traditional programming benchmarks that supply gold denotations or input-output test suites~\cite{spider,humaneval}, a reactive automation's output is a future sequence of environment interactions. Therefore, a behavioral reference for verification must be constructed from the request.
Second, syntactic divergence complicates evaluation. The same user intent can be expressed through many syntactically different yet behaviorally equivalent implementations. Therefore, checking a generated program by matching it against any single reference text is neither sound nor complete. Determining correctness fundamentally requires reasoning about the program’s semantic behavior over time, rather than analyzing its static syntax or a single snapshot of its output.

**Running example:** Suppose a user requests ``whenever the temperature rises above 25°C, turn on the air conditioner.'' We read ``rises above'' as an edge-triggered intent: the air conditioner should be switched on once per upward crossing, not continuously while it stays hot. Figure~\ref{fig:idiom} shows three lowerings, sketched in JOI, the automation domain-specific language (DSL) of our target platform. All three implementations execute with a one-second tick period. Implementation (a) detects the crossing by comparing previous and current readings, while (b) uses a flag that is set on firing and reset below the threshold. They share almost nothing syntactically yet behave identically. Implementation (c) textually mirrors the request, but under periodic execution it falsely re-fires on every tick while the temperature stays above the threshold. Because repeated On() commands leave the air conditioner in the same visible state, the user may see nothing wrong. This is a crucial failure mode our system targets: **deployed code that silently diverges from the user's intended behavioral specification**.

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/percom/figure1_a.pdf}\par
  {\small (a) Previous/current comparison}\par\smallskip
  \includegraphics[width=\linewidth]{figures/percom/figure1_b.pdf}\par
  {\small (b) Triggered flag}\par\smallskip
  \includegraphics[width=\linewidth]{figures/percom/figure1_c.pdf}\par
  {\small (c) Re-fires while the level holds}\par\smallskip
  \includegraphics[width=\linewidth]{figures/percom/figure1_d.pdf}\par
  {\small (d) Timed action traces}
  \caption{Three lowering sketches of one intent and their timed action traces. (a)
  and (b) produce identical traces; (c) fires on every tick while the threshold
  is exceeded. Platform boilerplate is omitted.}
  \label{fig:idiom}
\end{figure}
```

**Why existing checks fall short.** Prior verification frameworks of IoT automations target fixed, predefined criteria, such as safety properties, inter-rule conflicts, or security policies~\cite{autotap,iotsan,iotguard}. These checks establish whether an automation satisfies the selected properties, but do not by themselves establish whether it implements the particular behavior requested by the user. Another LLM could judge whether the code matches the request, but in our experiments, verdicts changed even under behavior-preserving temporal rewrites (§3). Therefore, a verification reference specifying the requested behavior and a method for consistently checking the code against it are needed.

**VETS.** To address these challenges, we present VETS. Its key idea is to *derive the missing reference specification* at authoring time and subsequently utilize it as a deterministic verification baseline. VETS represents the requested automation in an intermediate representation (IR) called Timeline IR. This representation specifies the behavioral structure for the LLM to implement in code and provides an executable reference for checking the generated JOI code.

Timeline IR makes an automation's temporal control flow explicit by specifying execution order and timing conditions (§5). It can thus clearly express automations that wait for an event, perform an action, and repeat with a delay until a termination condition is met. Given an initial state and a timed input sequence, which specifies input values and when they change, its execution semantics determine the expected timed action trace, consisting of device commands and their occurrence times.

Behavioral Explorer checks whether the IR and generated JOI code produce the same timed action trace for every allowed initial state and timed input sequence (§6). It certifies equivalence only when checking completes within the specified input ranges and execution rules and provides an executable counterexample for confirmed divergence. Unsupported or unfinished checks remain uncertified.

**Scope and assumptions.** During authoring, the user confirms the IR as the specification, and we assume that it captures the intended automation. We do not evaluate users' ability to identify IR errors. VETS checks for state, timer, and boundary errors introduced during subsequent code generation, and its guarantee is limited to conformance of the generated code to the confirmed IR.

**Local generation and verification.** We assume a setting in which automation requests and device information are not disclosed to external services during generation or verification. To meet this requirement, VETS uses a local language model to generate both Timeline IR and JOI code and performs behavioral verification locally without additional LLM calls.

**Contributions.** Our contributions are:

- **C1. Timeline IR:** We introduce an executable intermediate representation that specifies an automation's execution order and timing conditions. Its execution semantics define the expected behavior for a given initial state and timed input sequence, providing a behavioral reference for verifying generated JOI code.
- **C2. Behavioral Explorer:** We propose a deterministic checker that jointly explores Timeline IR and generated JOI code under the same timed input sequences and compares their timed action traces. It reports executable counterexamples for confirmed divergence and certifies equivalence only when exploration completes within the specified input ranges and execution rules.
- **C3. Local implementation:** We implement a pipeline that combines local LLM-based authoring with deterministic behavioral verification requiring no LLM calls. Across 379 attempted checks in the generated-code evaluation, verification process time had a median of 62 ms and a 95th percentile of 158 ms, including process startup and preparation.

<!-- Latency source: ../../explorer/eval/results/e3_single_binding_382_20260915_run/case_outcomes.jsonl (relative to this file). process_wall_seconds; 379 attempted checks include 2 UNKNOWN; 3 preparation refusals excluded. Median 61.843 ms, nearest-rank p95 158.126 ms. Generation time excluded. Outcome SHA-256 verified against summary.json. -->
