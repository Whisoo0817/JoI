# Problem and Motivation

\section{Problem and Motivation}
\label{sec:motivation}

Together, \S1 and \S2 leave a clear task: a gate is needed that decides, before deployment, whether generated code preserves the user's intended behavioral specification. This section first establishes the requirements such a gate must meet in our setting. Next it considers alternative checking approaches and evaluates the consistency of an LLM judge, motivating our proposed design.

\textbf{Three requirements for a deployment gate.}
\begin{itemize}
\item \textbf{R1 (Reference).} In our authoring setting, no request-specific verification reference is supplied in advance. Algorithmic code evaluations with input-output test cases, such as GPIoT (\S2), can use those cases to check generated code. Here, the question is whether the requested device actions occur correctly over time, but the request itself is not an executable specification. A verification reference that defines the expected behavior must therefore be constructed from the request.
\item \textbf{R2 (Stability).} A deployment decision is binary: two programs with the same behavior must receive the same deploy/reject verdict against the same specification. Repeated evaluations of the same program should likewise agree. A checker whose verdict changes with how the code is written despite unchanged behavior is unsuitable as the sole gate, regardless of the quality of its individual judgments.
\item \textbf{R3 (Local verification).} We assume a setting in which automation requests and device information are not disclosed to external services. VETS therefore uses a local language model to generate IR and code. This requirement must also hold when checking the generated outputs, so the verification gate must run locally without relying on cloud services.
\end{itemize}

\textbf{Candidate checking approaches.} The most straightforward verification method is to match the generated code directly against a reference text. However, as the temperature example in \S1 illustrates, identical behavior can be realized through syntactically disparate idioms, while a buggy implementation can closely resemble the request. One could instead ask the generating model to inspect and repair its code, but SimuHome~\cite{simuhome} reports limited recovery from scheduling errors through self-correction. Showing the code to the user also requires inspection of its implementation details; TAP-Debug~\cite{tapdebug} found that non-experts frequently misread even the basic IF (event) and WHILE (state) conditions of raw rules. These limitations motivate a behavioral check that does not rely solely on textual similarity, model self-assessment, or users' inspection of code.

\textbf{An LLM judge}~\cite{llmjudge}. Another approach is to hand the request and the code to a separate LLM to verify whether they align. This approach appears plausible at first glance and is used in practice (ChatIoT's Evaluator~\cite{chatiot}, \S2). We therefore evaluate whether the judges satisfy R2 both when the same code is submitted repeatedly and when the way it is written changes while its behavior stays the same.

To examine whether verdicts remain consistent when code presentation changes, we used 217 JOI programs from the generated-code evaluation (Section~\ref{sec:eval-generated}) that could be expressed differently while preserving their behavior. We submitted each natural-language request--program pair three times to Qwen3.5-9B~\cite{qwen35,qwen35fp8}, GPT-5.4-mini~\cite{gpt54mini}, and Claude-Sonnet-5~\cite{claudesonnet5}. Each call also included language documentation, but the judge did not receive Timeline IR. Qwen used temperature 0 and seed 0, and GPT used a fixed seed of 42. We then selected the 52 originals accepted by each judge through majority vote and evaluated 168 variants with different code presentations whose behavior preservation was checked by Behavioral Explorer (\S6). The rewrite rejection rate is the proportion of these variants that a judge marked as not correctly implementing the user's request.

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

Across all variants, the cloud judges GPT and Claude had lower rejection rates, 10.1\% and 6.0\%, respectively, than Qwen at 20.8\%. However, as Table~\ref{tab:instab} shows, GPT had a verdict disagreement rate of 16.6\% across three identical submissions despite its fixed seed, while Claude had a rate of 9.7\%. Thus, lower rejection rates on the variants in this experiment did not ensure repeatable verdicts on unchanged code.

By contrast, under the settings above, Qwen had a verdict disagreement rate of 0.0\% on unchanged code. Yet it had the highest overall rejection rate among the three judges on variants that preserved behavior. Qwen largely maintained its acceptance verdicts under notation and logic changes, but frequently rejected behaviorally equivalent code when its temporal structure changed. The rejection rate for temporal variants reached 64.6\%. The individual transformations in Figure~\ref{fig:instability} show rejection rates of 90.9\% for loop-unrolling variants (UNR) and 94.1\% for variants that halved the execution period while running the body on alternate iterations (PHV). Repeatability on identical code therefore did not extend to consistent verdicts across different implementations of the same behavior.

\begin{figure}[t]
\color{black}
\centering
\includegraphics[width=\linewidth]{figures/judge_rewrites.pdf}
\caption{Rejection of behavior-preserving rewrites of the 52 commonly accepted originals. Counts appear below each type. VAR: variable renaming; CMP: comparison reversal; UNIT: time-unit conversion; GRP: group-condition respelling; BR: branch swap; ELS: else splitting; DLY: delay splitting; UNR: loop unrolling; PHS: phase-to-flag conversion; WPC: wait precheck; PHV: period halving with alternate execution.}
\label{fig:instability}
\end{figure}

These results concern verdict consistency, not bug-detection accuracy. The rewrite results are conditional on the common accepted set. Because GPT and Claude already varied on unchanged code, and the table and figure use different populations and measures, their rates do not isolate an additional effect of rewriting. Under the tested conditions, the observations undermine reliance on these judges alone for a stable deployment decision; they do not rule out every possible LLM-based checker.

\textbf{Design direction.} The requirements and observations point to an explicit behavioral reference and a separate execution-based check. By R1, the reference must be constructed during authoring; by R2, the check must compare behavior rather than depend on code presentation; by R3, it must run locally. VETS uses Timeline IR (\S5) to make the automation's temporal control flow explicit and Behavioral Explorer (\S6) to check the generated code against it. As stated in \S1, the guarantee assumes that the confirmed IR captures the intended automation.
