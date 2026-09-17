# Code Generation and Behavioral Validation

As shown in Figure 2, the LLM generates candidate JoI code from the confirmed Timeline IR and device binding. Behavioral Explorer checks whether the candidate preserves the IR's actions and their timing for every input history allowed by the execution model. Certification requires a completed check without an execution-time horizon; exhausting the exploration budget leaves the pair uncertified.

## Execution Contract

The model \(M\) fixes the binding, service catalog and return policies, start time \(t_0\), input domains, allowed initial global-variable environments \(G_0\), and the following execution rules. Time fields such as hour and timestamp follow logical time; the holiday indicator is an external Boolean input. The two interpreters receive the same external inputs and logical time, but retain separate control locations and stores.

| Component | Declared model |
| --- | --- |
| External inputs | At \(t_0+n\Delta\), each input may take any value in its declared domain; it remains constant until the next update. The default \(\Delta\) is 100 ms. Reads of the same device/member/query-argument key within an update interval share a value. |
| Values and initialization | Catalog types and ranges constrain inputs; INTEGER uses mathematical integers, and DOUBLE inputs follow the declared 0.1 grid and representation policy. Explicit domain subsets restrict the guarantee to those subsets. Program-written globals start in \(G_0\) and then evolve separately; local variables follow each program's initialization. |
| Time | Internal deadlines have 1 ms resolution and are not rounded to input updates. New inputs take effect before coincident deadlines. A period starts after the preceding iteration completes. |
| Invocation | Preparation checks matching start anchors, including `cron`. The check covers one scenario instance; overlapping scheduled instances and concurrent scenarios are outside the model. |

**Observed behavior.** At each comparison time, the Explorer compares action targets, methods, arguments, multiplicity, and order. Only the order among independent devices within a single fanout call may differ. Numeric arguments compare by value; Boolean and string arguments remain distinct. This trace comparison detects both commission and omission. An action on one side while the other is silent is a mismatch, even if their eventual device states agree. Termination makes that side permanently silent while the other continues to be checked.

## Joint Inputs and Stored Values

For an input used only through supported scalar predicates, the Explorer collects predicates from both programs, including uses reached through assignments. Values belong to the same cell only when every collected predicate has the same truth value. One representative per nonempty cell then covers all such outcomes. For example, IR guard \(T>22\) and code guard \(T>25\) require cells \(T\le22\), \(22<T\le25\), and \(T>25\) within the declared numeric domain. The middle cell exposes the disagreement. The Explorer combines predicates before partitioning, rather than merely combining separately chosen representatives.

This reduction requires a check of the value's later uses. If `saved = T` is followed by an action carrying `saved`, values 23 and 24 cannot be merged just because both currently satisfy the same guards. The analysis follows all definitions, branches, and copies to identify values used in outputs, conversions, or computations not preserved by the partition. Such inputs require full value enumeration or a supported symbolic method. Stored values retain their types and original read intervals; a saved input is never replaced by the latest input. For example, numeric action equality between `1` and `1.0` does not justify merging stores if a later string conversion distinguishes them.

Concrete exploration retains both control states, relevant stores, active timers, edge and termination flags, and the current input where needed. It advances to the next input update, deadline, or relevant clock boundary. Intermediate updates may be skipped only when both programs are suspended without observing those inputs or changing relevant state. Resumption includes every possible latest input and preserves earlier stored values.

## Timer Relations and Exploration

The Explorer uses different methods for different supported program forms. Each has its own eligibility checks and completion obligation; support by one method does not imply support by another.

| Method | Supported form and certification condition |
| --- | --- |
| Concrete exploration | Joint predicate cells or full input values; exact states or justified time-relative keys. Certify only when all successors are covered. |
| Symbolic value flow | Sequential one-shot reads, copies, strings, and fixed delays. Preserve typed read symbols and certify matching observations through termination. |
| SMT arithmetic | Eligible acyclic numeric one-shot programs with catalog bounds and linear arithmetic (addition, subtraction, constant multiplication/division), excluding general loops, globals, and clock reads. Require identical observations or UNSAT action-difference queries under path/input constraints, and termination of all paths. |
| Integer relations | Restricted top-level counter repetitions. Check actual initialization, output/update order, and preservation of integer relations until the graph closes. |
| Timer relations | Supported synchronous programs with grid-aligned deadlines and restricted counter uses. Explore timer/counter sets and recheck every enlarged set until closure. |

**Relating different time representations.** An IR sustained wait can correspond to a JoI tick counter. The core timer method requires the JoI repetition period to equal \(\Delta\), and IR periods, delays, sustained waits, and timeouts to be integer multiples of \(\Delta\). Selected counters allow integer constant initialization/reset, unit increments, and direct comparisons with integer constants; copying them to ordinary variables or action/query arguments is rejected. These restrictions are checked over their assignments and uses. This core case excludes JoI loops, globals, queries, and clock reads; Hour and timestamp-snapshot extensions require additional usage checks. Other timing forms require separately supported analysis or concrete exploration.

A node \((q,Z)\) keeps the paired control locations, relevant ordinary stores, active-timer pattern, and edge/termination flags in \(q\). The set \(Z\) is represented by an integer difference-bound matrix (DBM) [@bengtsson2004timed], representing constraints \(x_i-x_j\le c\), with a zero coordinate \(x_0=0\). Counter coordinates retain their integer values; a timer coordinate is \((t-r)/\Delta\), where \(r\) is its stored start or deadline. A future deadline therefore has a negative coordinate. For example, a relation \(a-k=0\) can connect an IR elapsed-time coordinate \(a\) to a JoI counter \(k\), provided initialization and subsequent reactions establish it. Under that relation, guards \(a\ge d\) and \(k\ge d+1\) disagree at \(a=k=d\), exposing a one-tick timing error.

For each joint input, both interpreters execute with the same relational constraints. Comparisons split the set into feasible branches, including the complementary cases; inconsistent branches are discarded. Each branch checks action equality. Updates of the form \(x'=y+c\), or assignment of an integer constant, produce an exact successor DBM by substitution and projection. Counter increments and timer resets follow the original statement order. Because all relevant events in this core method lie on the grid, advancing one interval omits no intermediate action.

**Inclusion, enlargement, and rechecking.** Successors with different \(q\) remain separate. If an existing \(Z\) contains a new successor set, no new work is needed. Otherwise, widening produces a set containing both: unstable bounds move to thresholds derived from program comparisons and timer lengths, or to infinity, while stable difference constraints remain. The enlarged node is put back on the worklist, even if it is the node currently being processed. Every input and feasible branch is rechecked over the enlarged set. The set may contain unreachable states; certification requires action agreement and successor coverage throughout that set. A single concrete representative would not establish these obligations.

**Algorithm 1. Timer-relation exploration.**

```text
Check the shared model and timer-method restrictions; otherwise return UNCERTIFIED
Build joint input cells, preserving any inputs requiring full values
D := initial nodes before the first reaction; Q := all initial node keys
while Q is not empty:
    if resources are exhausted: return UNCERTIFIED
    q := remove a key from Q; Z := current D[q]
    for every joint input and feasible relational branch from (q, Z):
        Execute both reactions at t0 initially, otherwise one grid interval later
        Compare actions at that time
        if a mismatch is possible:
            return DIVERGENT if concrete replay from initialization confirms it
            otherwise return UNCERTIFIED for this attempt
        Compute successor (q', Z'); omit only a jointly terminated successor
        if q' is new:
            D[q'] := Z'; add q' to Q
        else if Z' is not contained in D[q']:
            D[q'] := Widen(D[q'], Z'); add q' to Q if not already pending
return EQUIVALENT
```

Algorithm 1 describes the timer method; its initial nodes distinguish the first reaction from later resumptions. Any unsupported operation aborts its attempt without certification. An inconclusive timer attempt can fall back to concrete exploration within the resource limits. An abstract mismatch is not itself a counterexample: replay must establish a difference under the original initialization, inputs, and clock rules.

## Completion and Soundness

For a completed relation graph, let \(R\) denote the concrete paired states it represents, interpreting relative times under \(M\) and including jointly terminated states as silent absorbing states. Certification establishes

\[
\operatorname{Init}_M\subseteq R,\qquad
\operatorname{Post}_M(R)\subseteq R,
\]

and matching timed observations for every represented reaction under every allowed input. Here \(\operatorname{Post}_M\) includes all successors under the shared execution rules. Worklist exhaustion establishes these conditions only because every initial case, input, and feasible branch is covered and enlarged nodes are rechecked. A one-shot symbolic method instead completes all feasible paths with matching observations and termination. Neither a resource limit nor a finite execution horizon establishes unbounded equivalence.

Let \(I,C\) be the prepared IR and code, and \(\mathcal U_M\) the input histories allowed by the contract above. We write \(\operatorname{Accept}_{\infty}(I,C,M)\) when a supported method completes its obligations and returns EQUIVALENT without an execution-time horizon.

**Proposition S (soundness).** For a supported prepared pair under the declared execution and observation rules,

\[
\begin{aligned}
&\operatorname{Accept}_{\infty}(I,C,M)\\
&\quad\Longrightarrow\ \forall g_0\in G_0,\ \forall u\in\mathcal U_M:\\
&\qquad\operatorname{Tr}_M(I;g_0,u)
 =_O \operatorname{Tr}_M(C;g_0,u).
\end{aligned}
\]

Here \(=_O\) is equality of actions and their times under the observation rules above. The normal-execution and time-progress conditions of Section 5 apply; errors and execution limits are never normal termination.

**Proof sketch.** Joint predicate cells cover every allowed input valuation. The use analysis permits representative substitution only where it preserves predicates and subsequent observations; full values or typed symbols preserve observable stored data. Thus every concrete input history is covered, including reads saved across updates. For timer relations, feasible branch splitting covers every represented valuation, and exact successor projection followed by widening includes every successor. Rechecking enlarged nodes establishes observation agreement and closure over the final sets, including any additional unreachable states.

Concrete methods use future-preserving state keys; symbolic methods require observation identities, or discharged difference queries, over every feasible path. For the integer-relation method, actual initialization establishes the relation and output/update checks preserve it at each reaction. Supported time skips contain no observations and retain all possible inputs at resumption. Initial inclusion and successor coverage therefore extend agreement along every finite trace prefix by induction. For terminating symbolic paths, subsequent traces are silent. The normal-execution and time-progress assumptions extend prefix agreement to the full traces, and Proposition D supplies the unique IR reference.

The guarantee assumes correct parsing, semantic interpretation, and solver results. It does not establish that the confirmed IR matches the user's intent or that physical devices behave as modeled, and does not promise a verdict for every equivalent pair.

**Counterexample feedback and implementation.** A confirmed mismatch returns its initial environment, timed input history, and expected and actual actions. The LLM may revise the code using this evidence; the revision is checked against the unchanged IR and binding. VETS is implemented in Python for JoI, with Z3 supporting arithmetic reasoning. Verification uses semantic interpreters without LLM calls or physical device execution. The soundness argument is a manual proof; the implementation has not been machine-verified.
