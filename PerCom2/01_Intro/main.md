# Introduction

> SenSys 원문을 기반으로 수정한 VETS 초안. Why this is hard 문단은 원문을 보존했다. Running example과 기존 검사 설명을 축약하되 논리 연결을 유지하고, LLM judge 설명은 기존 검사 문단에 통합했다. 분량보다 흐름을 우선한다. `overleaf-paper/main.tex`의 Introduction과 내용이 동일하며, 그림 경로는 LaTeX 프로젝트 기준이다.

IoT automation is moving toward LLM-based code generation~\cite{gpiot,awareauto}. A user states the desired behavior in natural language, and an LLM turns it into a reactive rule the platform can execute. Yet the final step of this workflow, deciding *whether the generated code is correct to deploy*, has no deterministic gate. The missing piece is a reference to check the code against; the natural-language request contains the intent, but not in a form that can serve as a rigorous baseline for automated testing.

**Why this is hard:** The core challenge stems from the absence of a verifiable reference baseline. The target automations are inherently *reactive-temporal*. They are *reactive* because their execution is driven by asynchronous events and conditional triggers,
and *temporal* because their behavior unfolds over time through schedules, periodic executions, and sustained state durations (e.g. ``if it persists for more than N minutes'').
Driven by timers, counters, and multi-step state, the correct behavior of an automation must be evaluated across an entire timeline rather than a single discrete instant. Furthermore, in our setting, this logic is deployed as arbitrary code rather than a restricted, fixed-rule template.
Validating their correctness presents two key challenges. First, no test oracle is available.
Unlike text-to-SQL or traditional programming benchmarks that supply gold denotations or input-output test suites~\cite{spider,humaneval}, a reactive automation's output is a future sequence of environment interactions. Because no external source can pre-label this sequence, the verification reference must be actively constructed on the fly.
Second, syntactic divergence complicates evaluation. The same user intent can be expressed through many syntactically different yet behaviorally equivalent implementations. Therefore, checking a generated program by matching it against any single reference text is neither sound nor complete. Determining correctness fundamentally requires reasoning about the program’s semantic behavior over time, rather than analyzing its static syntax or a single snapshot of its output.

**Running example:** Suppose a user requests ``whenever the temperature rises above 25°C, turn on the air conditioner.'' We read ``rises above'' as an edge-triggered intent: the AC should be switched on once per upward crossing, not continuously while it stays hot. Figure~\ref{fig:idiom} shows three lowerings, sketched in JOI, the automation DSL of our target platform. All three implementations execute with a one-second tick period; this setting is omitted from the sketches. Implementation (a) detects the crossing by comparing previous and current readings, while (b) uses a flag that is set on firing and reset below the threshold. They share almost nothing syntactically yet behave identically. Implementation (c) textually mirrors the request, but under periodic execution it falsely re-fires on every tick while the temperature stays above the threshold. Because repeated On() commands leave the AC in the same visible state, the user may see nothing wrong. This is a crucial failure mode our system targets: **deployed code that silently diverges from the user's intended behavioral specification**.

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

**Why existing checks fall short.** Prior verification frameworks of IoT automations target fixed, predefined criteria, such as safety properties, inter-rule conflicts, or security policies~\cite{autotap,iotsan,iotguard}. These checks establish whether an automation satisfies the selected properties, but do not by themselves establish whether it implements the particular behavior requested by the user. As the user transitions from author to prompter, this distinction becomes critical. Once an LLM synthesizes code from a natural-language request, the user's original statement and the generated artifact become distinct, decoupled entities that can silently diverge. Asking another LLM whether the code matches the request addresses this question directly, but a deployment decision also requires consistency: two behaviorally identical programs should receive the same deploy/reject verdict. Yet we find that an LLM judge's verdict can flip even at temperature 0 under behavior-preserving temporal rewrites (§3). Deterministically checking this per-automation intent-conformance remains less explored. The fundamental missing piece is a verifiable reference specification.

**VETS.** To address these challenges, we present VETS. Its key idea is to *derive the missing reference specification* at authoring time and subsequently utilize it as a deterministic verification baseline. VETS represents the requested automation in Timeline IR, an executable intermediate representation that serves as the behavioral reference for checking the generated JOI code.

Timeline IR makes an automation's temporal control flow explicit along a time axis: schedules, waits, delays, and timers specify when execution proceeds, while sequences, branches, and cycles specify how it proceeds. An automation can thus describe waiting for an event, performing an action, delaying, and repeating until a condition ends the cycle. Given an initial state and a timed input sequence, which specifies input values and when they change, its execution semantics determine the expected timed action trace. This trace records device actions and their occurrence times and provides the reference for checking the generated JOI code.

Behavioral verification compares the generated JOI code against this IR. Behavioral Explorer checks whether the IR and generated code produce the same timed action trace for every allowed initial state and timed input sequence (§6). Equivalence requires a completed check within the specified input ranges and execution rules; confirmed divergence yields an executable counterexample. Unsupported or unfinished checks remain uncertified.

**Scope and assumptions.** Our focus is on making an automation's temporal control flow explicit and using it as an executable reference for code verification. This structure can support different forms of presentation, including JSON, deterministic natural-language rendering, and potentially LLM-generated explanations. We leave the evaluation of these approaches for helping users understand and distinguish automation behaviors to future work. During authoring, the user confirms the IR as the specification; we assume that it captures the intended automation and do not evaluate users' ability to identify IR errors. If the user approves an incorrect IR, the verifier checks against that incorrect specification. VETS's technical guarantee lies in IR-to-code conformance within these input ranges and execution rules. Even when the approved IR is acceptable, the subsequent lowering phase can introduce subtle state, timer, and boundary errors; VETS checks for precisely these divergences.

**Deployment setting.** We assume a home edge device rather than the cloud, to keep automation requests and sensor data within the home and avoid cloud round-trips. A local language model generates both Timeline IR and JOI code, while the verification gate runs on the same device without LLM calls.

**Contributions.** Our contributions are:

- **C1. Timeline IR:** We introduce an executable intermediate representation that makes an automation's temporal control flow explicit along a time axis. Its execution semantics provide a precise behavioral reference for verifying generated JOI code.
- **C2. Behavioral Explorer:** We propose a deterministic checker that jointly explores Timeline IR and generated JOI code under the same timed input sequences and compares their timed action traces. It reports executable counterexamples for confirmed divergence and certifies equivalence only when exploration completes within the specified input ranges and execution rules.
- **C3. On-device realization:** We realize local LLM-based authoring and deterministic behavioral verification on a home edge device. Across 379 attempted checks in the generated-code evaluation, verification process time had a median of 62 ms and a 95th percentile of 158 ms, including process startup and preparation. The verification gate bypasses LLM execution entirely, and its guarantee does not depend on the size or quality of the generation model.

<!-- Latency source: ../../explorer/eval/results/e3_single_binding_382_20260915_run/case_outcomes.jsonl (relative to this file). process_wall_seconds; 379 attempted checks include 2 UNKNOWN; 3 preparation refusals excluded. Median 61.843 ms, nearest-rank p95 158.126 ms. Generation time excluded. Outcome SHA-256 verified against summary.json. -->
