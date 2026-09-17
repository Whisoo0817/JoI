# Timeline IR syntax and determinism (appendix draft)

> 보존용 상세 명세. 제출 원고에는 이 전체 문서 대신 `DETERMINISM_APPENDIX_COMPACT.md`를 사용한다. 전체 grammar와 상세 증명은 여기 그대로 보존한다. 별도 supplementary의 제출·심사 허용을 전제하지 않는다.

This companion to §5 specifies the operator structure and the argument for Proposition D. It describes the declared execution model, with a trusted correspondence to the frontend and interpreter. It is a manual mathematical argument, not a machine-checked proof of the Python implementation.

## A. Operator syntax

The following EBNF describes an abstract notation for the JSON representation. Brackets denote optional parts and braces denote repetition. A sequence `seq` contains zero or more steps. This notation covers the operator forms discussed in §5, rather than every legacy spelling accepted by the parser.

```text
program ::= start_at seq
start_at ::= "start_at" "(" ("now" | "cron" cron-string) ")"
seq     ::= "[" { step } "]"
step    ::= wait | delay | read | call | branch | cycle | break
wait    ::= "wait" "(" expr ["," "edge=" edge]
            ["," "for=" duration] ["," "timeout=" duration]
            ["," "on_timeout=" seq] ")"
delay   ::= "delay" "(" duration ")"
read    ::= "read" "(" ident "," service-member ")"
call    ::= "call" "(" service-method ["," args]
            ["," "var=" ident] ")"
branch  ::= "if" "(" expr "," seq ["," seq] ")"
cycle   ::= "cycle" "(" "period=" duration
            ["," "count=" (ident | positive-integer)]
            ["," "until=" expr] "," seq ")"
break   ::= "break"
edge    ::= "none" | "rising" | "falling"
duration ::= nonnegative-integer ("MSEC" | "SEC" | "MIN" | "HOUR")
args    ::= named, typed argument values in catalog-declared order
```

In JSON, `program` is an object with a `timeline` array, `seq` is an array, and each step is an object with an `op` field. `wait`'s expression is `cond`, `delay`'s duration is `duration`, and `read`'s operands are `var` and `src`. A call uses `target`, `args`, and optional `var`. Branch sequences are `then` and `else`, and a cycle sequence is `body`. Omitted `edge` means `none`. Omitted or null `until` supplies no stop condition. The durations above are the canonical manuscript notation. The execution parser additionally accepts certain exact millisecond-representable aliases, which do not add an operator or alter its semantics.

Expression precedence is specified from weakest to strongest below. Repetitions in `sum` and `product` associate to the left.

```text
expr    ::= disj
disj    ::= conj { "or" conj }
conj    ::= neg { "and" neg }
neg     ::= "not" neg | compare
compare ::= sum [ cmp sum ]
sum     ::= product { ("+" | "-") product }
product ::= unary { ("*" | "/" | "%") unary }
unary   ::= "-" unary | atom
atom    ::= literal | service-member | "$" ident | ident
          | "(" expr ")" | "abs" "(" expr ")"
          | ("min" | "max") "(" expr "," expr ")"
cmp     ::= "==" | "!=" | "<" | "<=" | ">" | ">="
literal ::= number | string | "true" | "false" | "null"
```

The canonical spelling for a stored variable is `$x`. Bare names are also used for cycle counters in existing programs. Expressions occupy strings in JSON condition fields. ACTION argument values follow the typed argument decoder: ordinary strings are literal data, while `$`-marked expressions or supported interpolation refer to stored or service values. Expression syntax alone does not authorize every type combination or arithmetic verification path. Typed operations, missing-value handling, and accepted argument encodings follow the fixed model and preparation checks.

\textbf{Well-formedness and support.} A program has one leading `start_at`, with no nested start anchor. Each service/member and argument must agree with the catalog and confirmed binding. Query-result calls require an approved read-only operation and an unambiguous result. A `break` requires an enclosing cycle, a cycle has a period, and names cannot collide with reserved interpreter state. An edge mode other than `none` cannot be combined with a positive `for` duration. A cron-bearing pair is prepared by checking the common anchor and analyzing one invocation with that anchor fixed. These conditions precede, but do not guarantee completion of, the code-equivalence check. In particular, nested cycles have execution semantics even when a particular certification path does not support them. There is no parallel-branch construct.

## B. State, input, and reaction

Fix a prepared program $I$ and model $M$. The model fixes the binding and service interpretation, typed input domains, initial global-variable domain $G_0$, start time $t_0$, input interval $\Delta>0$, and time and observation rules. For each external input key $k$, let $U_k$ be its allowed concrete values. Then

\[
\mathcal U_M=\left\{u:\mathbb N\to\prod_k U_k\right\},
\qquad \bar u(t)=u\left(\left\lfloor\frac{t-t_0}{\Delta}\right\rfloor\right).
\]

Input values remain fixed between updates. Derived clock values are functions of logical time, rather than freely chosen input values. Program-owned global variables evolve in the store after initialization and are not overwritten by external input. All time values used for event scheduling are exact integer milliseconds. The default external grid is 100 ms, which is separate from deadline precision.

Write an execution state as

\[
s=(\kappa,\rho,g,\theta,\eta,\chi,z),
\]

where $\kappa$ is the continuation, $\rho$ the local store, $g$ the relevant global-variable store, $\theta$ the timer origins/deadlines, $\eta$ the per-wait edge history, $\chi$ the cycle state, and $z$ the termination flag. The initial state $\operatorname{Init}_{I,M}(g_0)$ has the entry continuation, empty local store, initial globals $g_0$, inactive timers, the specified edge defaults, and an unset termination flag. Cycle counters are initialized when their cycle is entered. This is a conceptual state decomposition, not a claim that the implementation uses seven separate containers.

For fixed $I,M,\bar u(t),t$, an internal transition is

\[
\langle s,A\rangle\longrightarrow_{I,M,\bar u(t),t}\langle s',A\mathbin{\cdot}a\rangle,
\]

where $a$ is the possibly empty sequence of ACTIONs produced by that step. The snapshot is installed before the first internal transition. A reaction $\langle I,M,s,\bar u(t),t\rangle\Downarrow(s',A)$ is a finite sequence of internal transitions starting with an empty ACTION accumulator and ending at a blocking or terminated configuration. Errors are separate outcomes. A transition limit being exhausted is not a normal blocking or terminated configuration.

## C. Operator cases

The cases below make the choices used by the reaction relation explicit. They concern concrete execution, not Explorer's symbolic branches or state merging.

| Case | State update and continuation |
| --- | --- |
| Value or expression | Literals, stored values, external inputs, and derived clock reads each have one value. Composite expressions apply the fixed typed operations in the parser's order. Conditions have no hidden store writes. |
| `read` / result-bearing `call` | Copy the value of the fixed input key into the named variable and advance. A query key preserves the device, method, and literal query arguments. Subsequent input changes do not alter the saved value. |
| ACTION `call` | Evaluate arguments in fixed order, validate them, and append the prescribed call observation. Binding is fixed throughout execution. Approved global-variable writes follow the model's store and ACTION policy. |
| Sequence / `if` | Execute the next step, or choose the single branch determined by the condition. A blocked branch retains its continuation, including the continuation after the branch. |
| `delay(d)` | Store its entry time once. Block before entry time plus $d$ and advance at expiry. A zero duration advances within the current reaction. |
| Level `wait` | Advance exactly when its condition evaluates true, subject to the priority over timeout stated below. Otherwise remain at that wait. |
| Edge `wait` | Test the current condition against that node's stored previous value, then update the previous value. A rising edge defaults to previous=false, a falling edge to previous=true. History persists across cycle iterations and updates only when this wait executes. |
| Sustained `wait` | Start the sustain timer at the first true evaluation. Clear it at a false evaluation. Advance once the continuously true interval reaches the required duration. Clear the sustain and timeout timers upon success. |
| Timeout | If the wait has not succeeded, initialize/check its timeout timer. Success takes priority if success and timeout coincide. On timeout, a nonempty `on_timeout` block runs and then ends the current iteration, or ends the program outside a cycle. Without that block, timeout advances to the next step. |
| Cycle entry / iteration | Entry resets that cycle's counter and completion timer. A numeric count bound is checked at the loop head. Once the post-completion period has elapsed, evaluate `until` and either exit or enter the body. Completion increments the counter and records the new completion time. Re-entering a nested cycle initializes that inner cycle again. |
| `break` / termination | Jump to the nearest enclosing cycle's exit. Reaching the program end enters an absorbing, permanently silent state. |

For a sustained wait with duration $d>0$, let $b$ be the condition value at time $t$, and let $a$ be its stored start time or $\bot$ if inactive. The update used before the completion test is

\[
a^+=\begin{cases}
\bot & \text{if }\neg b,\\
t & \text{if }b\land a=\bot,\\
a & \text{otherwise},
\end{cases}
\qquad
\mathit{fire}=b\land(a^+\ne\bot)\land(t-a^+\ge d).
\]

The difference in the last expression is evaluated only when $a^+\ne\bot$. Because $b$ uses the newly installed input, an input becoming false exactly at the deadline cancels completion. By contrast, `delay` has no condition to cancel. This ordering is part of the semantics, rather than a runtime race left unspecified.

## D. Input-determinism

\textbf{Lemma D1 (expression uniqueness).} Fix the model, store, snapshot, and time. Each supported expression has at most one normal value and a uniquely determined modeled error, if evaluation fails.

\emph{Proof.} By structural induction. Literal and lookup cases are fixed by the environment. For a compound expression, the induction hypothesis fixes its operand values or error. Its typed operator and evaluation order are fixed by $M$, so its result is unique. Unsupported operations do not acquire an arbitrary value. $\square$

\textbf{Lemma D2 (internal-step uniqueness).} From a fixed internal configuration, there is at most one enabled normal successor, with a uniquely determined emitted ACTION sequence.

\emph{Proof.} The continuation selects one of the cases in §C. Lemma D1 fixes every evaluated condition and argument. For branches, the true and false cases are disjoint. For delay and wait, the stored times, current time, and edge/sustain state fix the outcome. The explicit success-before-timeout priority removes overlap at a coincident boundary. Cycle entry, completion, exit, and resumption each have fixed control targets and updates. Sequential execution supplies the ACTION order. Blocking and terminated configurations have no further enabled internal step at that reaction time. $\square$

\textbf{Lemma D3 (reaction uniqueness).} If two normal finite reactions start from identical $I,M,s,\bar u(t),t$, they end in identical states and ACTION sequences.

\emph{Proof.} Both begin with the same state and empty accumulator. Apply Lemma D2 inductively to each internal transition. Their states and accumulators coincide after every common prefix. One cannot finish earlier while the other takes another internal step, since a normal reaction ends only at a blocking or terminated configuration. Thus their final states and ACTION sequences coincide. An infinite instantaneous loop supplies no finite normal derivation of this relation. $\square$

\textbf{Proposition D (unique timed trace).} Fix $I,M,g_0\in G_0,u\in\mathcal U_M$. Suppose execution follows the specified event policy, each reached reaction terminates normally in finitely many internal steps, and an infinite execution advances logical time without a finite accumulation point. A terminated run is extended by silence. Then any two such runs produce the same timed ACTION trace:

\[
\frac{r_1,r_2\in\operatorname{Runs}_M(I,g_0,u)\quad
      \operatorname{NormalProgress}(r_1)\land\operatorname{NormalProgress}(r_2)}
     {\operatorname{Trace}(r_1)=\operatorname{Trace}(r_2)}.
\]

\emph{Proof.} Both runs begin at $t_0$ in $\operatorname{Init}_{I,M}(g_0)$. Lemma D3 fixes their first post-reaction state and ACTIONs. After a reaction, the canonical event policy takes the least subsequent external grid point, active deadline, or required derived-clock boundary. The same state, model, and input history determine that time and its held snapshot. At tied events, both runs install the new snapshot first and execute a single reaction to quiescence. Lemma D3 then fixes the next result. Induction over reactions yields identical states, times, and ACTIONs at every finite reaction index.

Normal reactions contain finitely many internal steps. Distinct reaction times increase by at least one millisecond under the model, so only finitely many reactions occur in any finite time interval. Zero-duration steps are exhausted within their current reaction, rather than scheduled as infinitely many same-time reactions. Consequently, every finite timed ACTION prefix is unique. After termination, both runs remain silent. For a nonterminating time-progressing execution, any unequal ACTION or occurrence time would appear in a finite prefix, contradicting prefix uniqueness. $\square$

The canonical policy can include silent input ticks. Skipping ticks in an optimized interpreter/explorer additionally requires the event-omission preservation argument, rather than following from determinism alone. Likewise, D establishes uniqueness for a fixed input history, not equivalence of two different programs, universal termination, or termination of the exploration algorithm. Section 6's soundness statement is a separate claim.

## E. Provenance and implementation boundary (editing record)

- Claim and model: [VERIFICATION_CONTRACT.md](../../explorer/docs/model/VERIFICATION_CONTRACT.md), D and the input/time definitions.
- Reaction and continuation argument: [FRONTEND_CORRECTNESS.md](../../explorer/docs/proof/FRONTEND_CORRECTNESS.md), §§2, 4, 5.
- Operator cases and time progress: [PROOF_OBLIGATIONS.md](../../explorer/docs/proof/PROOF_OBLIGATIONS.md), common induction and L3–L4.
- Executable checks: [ir_step.py](../../explorer/runtime/ir_step.py), `parse_cond`, `compile_ir`, `ir_step`, and `IrRunner.next_wakeup_ms`; [gate.py](../../explorer/verification/gate.py), `prepare_pair`.
- Typed primitive operations and the frontend/interpreter correspondence remain trusted implementation assumptions. This appendix does not turn source review or tests into proof-assistant verification, and does not establish physical-device behavior or NL-to-IR correctness.
- SenSys's bounded-horizon argument and prohibition on nested cycles were not imported. The old extractor prompt is not the semantic authority for the current executable model.
- D1–D3 are local lemma identifiers in this appendix. They are not new Explorer claims or replacements for the existing L1–L7 identifiers.
