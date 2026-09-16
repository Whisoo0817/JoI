# Problem and Motivation — SenSys source

> 비교용 원문: `docs/ovla0606.tex`의 해당 절. LaTeX 표기와 옛 결과를 보존하며 현재 PerCom의 주장이나 수치로 사용하지 않는다.

\section{Problem and Motivation}

Together, \S1 and \S2 leave a clear task: a gate is needed that decides, before deployment, whether LLM-generated reactive-temporal code behaves as the user intended. This section first establishes the requirements such a gate must meet in our setting. Next it weighs alternative candidate checking approaches against them, and finally measures the one remaining candidate, an LLM judge, motivating our proposed solution.

\textbf{Three requirements for a deployment gate.}
\begin{itemize}
\item \textbf{R1 (Reference).} No prior reference exists. The intended behavior is determined solely by the user’s recent request, meaning it is not provided as a checkable artifact.
Algorithmic code carries an executable oracle in the form of input-output pairs and is checked by running tests (GPIoT~\cite{gpiot}, \S2). For reactive-temporal code, the ``right output'' is a future sequence of device actions that no external source labels. The reference must be constructed, not looked up.
\item \textbf{R2 (Stability).} A deployment decision is binary: two programs with the same behavior must receive the same deploy/reject verdict. A checker whose verdict wavers under behavior-preserving rewrites is unsuitable as a gate, regardless of the quality of its individual judgments.
\item \textbf{R3 (On-device).} Sensor data must not leave the home (privacy) and the verdict must be immediate (latency), so the gate must run on the edge without a cloud round-trip.
\end{itemize}

\textbf{Candidate 1: syntactic or structural comparison.} The most straightforward verification method is to match the generated code directly against a reference text. However, as demonstrated by the temperature control example in \S1 (Figure~\ref{fig:idiom}), identical user intent can be realized through syntactically disparate idioms (a prev/curr comparison vs.\ a triggered flag), while the buggy implementation is the one that most resembles the request. Indeed, near-miss bugs differing by only a single execution tick or a single comparison can appear identical to valid code variants. Because syntactic or structural matching can neither validate diverse correct variants nor isolate subtle bugs, it satisfies neither soundness nor completeness.
Equivalence must be decided on execution behavior, not on syntax.

\textbf{Candidate 2: self-checking by the generating model.} One could ask the model that produced the code to inspect and repair it. SimuHome~\cite{simuhome} evaluated this method with 18 models; the self-correction recovery rate was 8.0\% for time-based errors, 18.5\% for event-based errors, and 0.0\% for coordinated scheduling. Notably, the success rate remained at or below 67\% even when an oracle was provided. Based on these findings, the authors concluded that agents fail to detect flaws in their own plans. A post-hoc self-check entrusted to the same stochastic process that generated the code cannot serve as a reliable quality gate.

\textbf{Candidate 3: human inspection of the code.} One could show the generated code to the user for approval. However, prior research in TAP-Debug~\cite{tapdebug} demonstrated that non-experts frequently misread even the basic IF (event) and WHILE (state) conditions of raw rules; specifically, misreadings occurred in 21 out of 50 control-condition sessions, all of which subsequently failed the task. Given that such errors occur even with a simple, two-slot TAP rule, it is untenable to expect users to successfully inspect complex reactive-temporal code, which realizes its mechanism through persistent variables and per-tick execution. What is shown to the user must be a readable representation rather than the raw code; this also motivates the deterministic rendering detailed in \S5.

\textbf{The remaining candidate: an LLM judge.} What remains is to hand the request and the code to a separate LLM to verify whether they align. This approach appears plausible at first glance and is indeed used in practice (ChatIoT's Evaluator, \S2), and existing literature does not rule it out. We therefore evaluate whether this candidate meets R2 independent of OVLA's IR and verifier.

We presented pairs of programs exhibiting identical behavior (trace-exact) but differing in idiom, and measured how often the judge's accept/reject verdict flipped. Even under a deterministic setting at temperature 0, a 9B model flipped on 27\% of pairs and a strong cloud-based model (GPT-5.1~\cite{gpt51}) flipped on 10.6\%. The rewrite types are categorized into surface rewrites (SEL = selector order, AND = $A{\wedge}B{\leftrightarrow}B{\wedge}A$, VAR = variable renaming) and logic/arithmetic rewrites (ADD = $x{+}n{\leftrightarrow}n{+}x$, BR = branch swap, DN = double negation, DM = De Morgan, IDM = idiom replacement). As shown in Figure~\ref{fig:instability}, purely surface rewrites flipped up to 9\% of the 9B judge's verdicts (14\% for the cloud judge), while logic and arithmetic rewrites caused flips up to 81\%. No ground-truth label is required to demonstrate this; the flip itself evidences instability.

The core is not the miss rate; on cleanly injected bugs, strong models are indeed competent detectors. The point is that \emph{any} probabilistic judge yields an unstable deployment policy under behavior-preserving rewrites. This instability persists in larger models, and majority voting fails to reduce it below the temperature-0 baseline, because voting mitigates sampling noise but cannot counteract the systematic dependence on surface form (Table~\ref{tab:instab}). This violates R2, disqualifying the final candidate. In contrast, OVLA's verdict depends only on behavior over a bounded set of traces, so under the same rewrites its flip rate is 0 by construction.

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figs/instability.pdf}
\caption{LLM judge verdict flip rate by rewrite type on behavior-identical programs (temperature 0).}
\label{fig:instability}
\end{figure}

\begin{table}[t]
\centering
\caption{Overall flip rate by judge configuration; OVLA's trace check flips on none of the same rewrites.}
\label{tab:instab}
\begin{tabular}{lcc}
\toprule
Judge configuration & 9B & GPT-5.1 \\
\midrule
deterministic (temp=0) & 27.0\% & 10.6\% \\
+ sampling (temp=0.7) & 34.4\% & 12.8\% \\
+ majority vote (K=5) & 31.2\% & 13.5\% \\
\bottomrule
\end{tabular}
\end{table}

\textbf{The surviving design.} With every candidate eliminated, rereading the requirements reveals the shape of the answer. By R1, the reference must be \emph{derived} from intent the user has confirmed; by R2, the check must be deterministic over behavior (traces), not syntax; by R3, it must be lightweight on the edge, with no LLM call. The artifact that satisfies all three at once is the Timeline IR (\S5), and the deterministic trace-equivalence check over it is the verifier (\S6). The judge in this motivating experiment compares NL against code.

\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{figs/system.pdf}
\caption{OVLA system overview. ①{--}⑤ Generation phase and ⑥{--}⑦ verification phase; the dashed arrow is the counterexample-guided repair loop.}
\label{fig:arch}
\end{figure*}
