# Problem and Motivation

\section{Problem and Motivation}
\label{sec:motivation}

Together, \S1 and \S2 leave a clear task: a gate is needed that decides, before deployment, whether generated code preserves the user's intended behavioral specification. This section first establishes the requirements such a gate must meet in our setting. Next it considers alternative checking approaches and evaluates the consistency of an LLM judge, motivating our proposed design.

\textbf{Three requirements for a deployment gate.}
\begin{itemize}
\item \textbf{R1 (Reference).} No prior reference exists. The intended behavior is determined by the user's request, but is not provided as a checkable artifact. Algorithmic code can be checked against input-output test cases (GPIoT, \S2). For reactive-temporal code, the ``right output'' is a future sequence of device actions that no external source labels. The reference must be constructed, not looked up.
\item \textbf{R2 (Stability).} A deployment decision is binary: two programs with the same behavior must receive the same deploy/reject verdict against the same specification. Repeated evaluations of the same program should likewise agree. A checker whose verdict wavers under behavior-preserving rewrites is unsuitable as the sole gate, regardless of the quality of its individual judgments.
\item \textbf{R3 (On-device).} In our deployment setting, automation requests and sensor data must remain within the home, so the gate must run on the edge without a cloud round-trip.
\end{itemize}

\textbf{Candidate checking approaches.} The most straightforward verification method is to match the generated code directly against a reference text. However, as the temperature example in \S1 illustrates, identical behavior can be realized through syntactically disparate idioms, while a buggy implementation can closely resemble the request. One could instead ask the generating model to inspect and repair its code, but SimuHome~\cite{simuhome} reports limited recovery from scheduling errors through self-correction. Showing the code to the user also requires inspection of its implementation details; TAP-Debug~\cite{tapdebug} found that non-experts frequently misread even the basic IF (event) and WHILE (state) conditions of raw rules. These limitations motivate a behavioral check that does not rely solely on textual similarity, model self-assessment, or users' inspection of code.

\textbf{An LLM judge.} Another approach is to hand the request and the code to a separate LLM to verify whether they align. This approach appears plausible at first glance and is used in practice (ChatIoT's Evaluator, \S2). We therefore evaluate whether the judges satisfy R2, both on repeated submissions of unchanged code and across behavior-preserving rewrites.

We submitted each of 217 JOI programs three times to Qwen3.5-9B, GPT-5.4-mini, and Claude-Sonnet-5. Each call contained the natural-language request, language documentation, and one program; the judge did not receive Timeline IR. We then evaluated 168 behavior-preserving rewrites of the 52 originals accepted by every judge in at least two of three evaluations. These rewrites change how the code is written while preserving what device actions occur and when. Each original and its rewrites were checked against the same confirmed IR by Behavioral Explorer (\S6), comparing their timed action traces under the same timed input sequences. This establishes the behavioral relation used in the experiment, rather than independently evaluating Explorer's correctness. Appendix~\ref{app:judge-protocol} records the judge settings and experiment construction.

\begin{table}[t]
\color{black}
\centering
\caption{Verdict disagreement on unchanged code: the percentage of 217 programs whose three evaluations did not all agree.}
\label{tab:instab}
\footnotesize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lccc@{}}
\toprule
 & Qwen3.5-9B & GPT-5.4-mini & Claude-Sonnet-5 \\
\midrule
Disagreement (\%) & 0.0 & 16.6 & 9.7 \\
\bottomrule
\end{tabular}
\end{table}

As Table~\ref{tab:instab} shows, Qwen's three evaluations agreed for every unchanged original, whereas GPT and Claude disagreed on 36 and 21 of the 217 programs (16.6\% and 9.7\%). Repeatability on identical code, however, did not ensure consistent verdicts across implementations that produce the same timed action traces. Qwen rejected 31 of 48 temporal rewrites (64.6\%), compared with 3.8\% of notation rewrites and 2.4\% of logic rewrites. Figure~\ref{fig:instability} separates the individual transformations: Qwen rejected 10 of 11 loop-unrolling variants and 16 of 17 variants that halved the execution period while using a flag to execute the body on alternate iterations.

\begin{figure}[t]
\color{black}
\centering
\includegraphics[width=\linewidth]{figures/judge_rewrites.pdf}
\caption{Rejection of behavior-preserving rewrites of the 52 commonly accepted originals. Counts appear below each type. VAR: variable renaming; CMP: comparison reversal; UNIT: time-unit conversion; GRP: group-condition respelling; BR: branch swap; ELS: else splitting; DLY: delay splitting; UNR: loop unrolling; PHS: phase-to-flag conversion; WPC: wait precheck; PHV: period halving with alternate execution.}
\label{fig:instability}
\end{figure}

These results concern verdict consistency, not bug-detection accuracy. The rewrite results are conditional on the common accepted set. Because GPT and Claude already varied on unchanged code, and the table and figure use different populations and measures, their rates do not isolate an additional effect of rewriting. Under the tested conditions, the observations undermine reliance on these judges alone for a stable deployment decision; they do not rule out every possible LLM-based checker.

\textbf{Design direction.} The requirements and observations point to an explicit behavioral reference and a separate execution-based check. By R1, the reference must be constructed during authoring; by R2, the check must compare behavior rather than depend on code presentation; by R3, it must run locally. VETS uses Timeline IR (\S5) to make the automation's temporal control flow explicit and Behavioral Explorer (\S6) to check the generated code against it. As stated in \S1, the guarantee assumes that the confirmed IR captures the intended automation.

## 실험 상세 부록

\section{LLM Judge Experiment Details}
\label{app:judge-protocol}

The originals came from the equivalent programs in the generated-code evaluation (Section~\ref{sec:eval-generated}); 217 had at least one verified rewrite. The judges were \texttt{Hyper-AI/Qwen3.5-9B-fp8} (temperature 0, seed 0, thinking disabled), \texttt{gpt-5.4-mini-2026-03-17} (low reasoning effort, seed 42), and \texttt{claude-sonnet-5} (adaptive thinking, low effort). The hosted APIs did not permit the same temperature control. Qwen used a 1,500-token initial budget and, when needed, a continuation of up to 300 tokens to complete the verdict; this occurred in 200 of its 1,122 evaluations. All three judges returned valid verdicts for every evaluated input.

PHV was added after inspecting preliminary results. Its transformation rule was fixed before its judge results were inspected and applied uniformly to eligible seeds. Rewrite results are conditional on the 52 originals accepted by every judge in at least two of three evaluations; this selection does not establish agreement between the IR and natural-language intent. The figure reports descriptive proportions for 3--39 variants per type, rather than a general ranking of transformation difficulty. Table~\ref{tab:instab} measures disagreement across three unchanged submissions, whereas Figure~\ref{fig:instability} measures rejection of a rewritten program. Their difference does not estimate a rewrite effect.
