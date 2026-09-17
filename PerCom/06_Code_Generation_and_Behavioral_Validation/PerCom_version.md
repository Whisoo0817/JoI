# Code Generation and Behavioral Validation

As shown in Figure 2, the LLM generates candidate JoI code from the confirmed Timeline IR and device binding. Because generated code may implement a condition or delay incorrectly, Behavioral Explorer checks whether it preserves the actions and timing specified by the IR for every input history allowed by the execution model. The following exploration procedure compares the two executions, and Proposition S establishes why a completed equivalence check justifies this guarantee.

## Joint Behavioral Exploration

**Shared execution model.** The Explorer runs the IR and generated code through their interpreters with the same input values and logical time. After checking that both programs are supported, it constructs a common input model from the values they read, their types, and the execution rules. It starts both programs under each allowed initial setting and tracks their execution states separately, since equivalent behavior may use different variables and control flow.

**Timed action comparison.** The Explorer compares the actions produced by the IR and generated code at each execution time, checking their targets, methods, arguments, number of occurrences, and order. When a single call sends an action to multiple independent devices, the order among those devices may differ. Numeric arguments compare by value, while Boolean and string arguments remain distinct. This trace comparison detects both commission and omission. An action on one side while the other remains silent is a mismatch, even if both eventually reach the same device state. A terminated program remains silent while the other side continues to be checked.

**Inputs and time.** To cover possible input histories, the Explorer checks individual values or represents sets of values symbolically. Grouping inputs must preserve later actions and their timing, including any stored values used by later computations. Under the timing rules of Section 5, concrete exploration advances to the next possible input change, timer expiry, or relevant clock change. It skips intermediate input updates only when neither program can observe them or change state that affects later behavior, and includes every possible input value at resumption.

**Algorithm 1. Behavioral exploration (schematic).**

```text
Prepare the IR–code pair and model, or return UNCERTIFIED
For each applicable checking method within the resource limit:
    Initialize states to explore from all allowed initial settings
    While states remain and resources permit:
        Select states and possible inputs
        Advance both programs under the shared input and time rules
        Compare actions and their times for every case considered
        If a possible mismatch is found:
            Return DIVERGENT if replay with concrete inputs confirms it
            Otherwise stop this method without an equivalence verdict
        Add all continuations that still need checking
    Return EQUIVALENT only if the completion conditions are met
Return UNCERTIFIED
```

## Completion and Soundness

To justify using the Explorer as a deployment check, we establish what a completed equivalence check guarantees. Completion requires including all allowed initial settings and inputs, checking that actions agree, and covering every continuation of the explored states. For supported programs that run once and terminate, a symbolic check can instead complete all feasible execution paths. Reaching a resource limit or checking only a fixed duration is insufficient.

Let \(I,C\) be the prepared IR and code under the model \(M\) of Section 5, \(G_0\) the allowed initial global-variable settings, and \(\mathcal U_M\) the allowed input histories. We write \(\operatorname{Accept}_{\infty}(I,C,M)\) when an applicable checking method meets these completion conditions and returns EQUIVALENT without limiting the execution duration.

**Proposition S (soundness).** For a supported prepared pair under the declared execution and observation rules,

\[
\begin{aligned}
&\operatorname{Accept}_{\infty}(I,C,M)\\
&\quad\Longrightarrow\ \forall g_0\in G_0,\ \forall u\in\mathcal U_M:\\
&\qquad\operatorname{Tr}_M(I;g_0,u)
 =_O \operatorname{Tr}_M(C;g_0,u).
\end{aligned}
\]

Here \(=_O\) denotes equality of actions and their times under the comparison rules above. The guarantee uses the normal-execution and time-progress conditions of Section 5. Errors and execution limits are never treated as normal termination.

**Proof sketch.** Fix an allowed initial setting \(g_0\) and input history \(u\). Exploration includes their initial state. Each comparison checks the actions and times of every execution considered, while grouping inputs, reusing states, and skipping time preserve all possible continuations and their observations. Completion ensures that every continuation is covered. Thus agreement extends from the start to each later comparison point, so every finite trace prefix agrees by induction. The normal-execution and time-progress conditions extend this equality to the full traces. Proposition D supplies the unique IR reference.

The guarantee applies to the declared model and assumes correct parsing, semantic interpretation, and solver results. It does not establish that the confirmed IR matches the user's intent or that physical devices behave as modeled.

**Counterexample feedback.** A confirmed mismatch returns its initial environment, timed input history, and expected and actual actions. The LLM may use this evidence to revise the code, which is then checked again against the unchanged IR and binding.

**Implementation.** VETS is implemented in Python for JoI, with Z3 supporting arithmetic reasoning. Verification uses the IR and JoI semantic interpreters without LLM calls or physical device execution. The soundness argument is a manual proof, and the implementation has not been machine-verified.
