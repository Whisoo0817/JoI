# Compact appendix: Timeline IR input-determinism

We prove Proposition D under the model and progress assumptions of Section 5. An internal configuration consists of state $s$ and the ACTION sequence emitted so far. A normal reaction takes internal steps until blocking or termination.

\textbf{Expression and step uniqueness.} At fixed state, input, and time, literals and lookups have unique values. Structural induction extends uniqueness to expressions because $M$ fixes each typed operation and evaluation order. The continuation then selects one operator:
\begin{itemize}
\item \texttt{start\_at} uses the fixed anchor. A sequence advances in order, and \texttt{if} selects the branch fixed by its condition. A blocked branch retains its continuation.
\item \texttt{read} and query-result \texttt{call} save the value of a fixed input key. An ACTION \texttt{call} evaluates arguments in fixed order and applies the prescribed observation and store updates.
\item \texttt{delay} stores its entry time and advances at expiry. A level \texttt{wait} tests its condition. An edge wait compares it with stored history, initially false for rising and true for falling, then updates that history.
\item A sustained wait starts its timer at the first true evaluation, resets it on false, and succeeds when the elapsed duration reaches its threshold. Success clears its timers and takes priority over timeout. Otherwise, timeout advances to the next step, or runs a nonempty \texttt{on\_timeout} handler and ends the current iteration (the program outside a cycle).
\item \texttt{cycle} resets its counter and completion timer on entry, checks a numeric count bound at the loop head, and tests \texttt{until} after the post-completion interval. Body completion increments the counter and records its time. \texttt{break} exits the nearest enclosing cycle. Program termination is permanently silent.
\end{itemize}
The fixed values and timers select at most one normal successor in each case. Input-first processing resolves coincident input and deadline events. Unsupported operations and errors supply no alternative normal successor.

\textbf{Reaction uniqueness.} Consider two finite normal reactions from the same configuration. Step uniqueness implies, by induction, identical states and ACTION accumulators after every common prefix. Neither reaction can finish before the other, because a blocking or terminated configuration has no enabled internal step at that time. Their final states and ACTION sequences therefore coincide.

\textbf{Trace uniqueness.} Fixed $I,M,g_0$ determine the initial state. After each reaction, the event policy selects the least subsequent input-grid point, active deadline, or required clock boundary. Equal states and the same input history determine the same next time and snapshot. Tied events form one input-first reaction, with zero-duration steps executed within that reaction. Induction using reaction uniqueness gives identical timed ACTION prefixes. Under the stated progress assumption, every finite time interval contains finitely many reactions, so any difference between complete traces would occur in a finite prefix. Terminated executions remain silent. Thus the complete traces are equal. $\square$

This argument concerns the declared semantics and retains the implementation trust boundary stated in Section 5. Preservation by optimized event skipping is a separate obligation.
