# SMT ACTION trace verification (`smt-linear-trace-v1`)

2026-09-07. User approved extending the old arithmetic REFUSED policy after
discussing joint guards and sensor-average Speaker arguments. This is an
implemented additional path; the concrete BFS and `symbolic-value-flow-v1`
remain available. No IR, catalog, dataset, numeric formatting or binding
contract was changed to obtain equivalence.

## Claim and actual support

2026-09-08 update: H is optional. With `H=None`, a positive result requires all
symbolic paths to terminate (`closure_kind=all-paths-terminated`). Nonterminating
wait paths exhaust a resource cap and remain UNKNOWN. Fixed silent sleeps skip
irrelevant input events while preserving the actual input epoch; see
[unbounded time obligations](UNBOUNDED_TIME.md). No loop invariant inference or
general periodic SMT support was added. The existing bounded claim below remains
available for explicitly bounded calls.

For a fixed prepared IR/code pair, inventory, binding, catalog and time origin,
an **EQUIV-BOUNDED** result with `complete=true` establishes equal D1 ACTION
traces through the inclusive horizon H for every allowed catalog input history.
Inputs change independently on the 100 ms grid and are held between grid
points. Interpreter deadlines remain exact integer milliseconds. Reading a
stored variable retains its original source/epoch; a fresh read uses the
current epoch. Both programs receive the same history.

This path admits catalog-backed, acyclic one-shot pairs with numeric
inputs, arithmetic conditions, reads, assignments, conditional actions, fixed
delays, and top-level JoI waits. IR wait edge/sustain/timeout behavior continues
to use its existing runner. Numeric input types are INTEGER or DOUBLE with
finite declared bounds of magnitude at most 1e12 and no enumerated members.
The supported arithmetic is `+`, `-`, constant multiplication and constant
division. IR `abs` and the existing expression evaluator's absolute-value term
are lifted; **the JoI source parser has not gained an `abs(...)` builtin**.
The three-sensor average fixture uses `(A+B+C)/3`.

The fallback is selected only for pairs whose detected unsupported features
are `joint-guard`, `derived-guard`, or `arith-arg`. It does not remove these
flags from the old engines. Its own grammar/domain checks replace their
one-dimensional partition precondition. Existing coverage errors, dynamic
query arguments, other feature refusals, clock/GV use, periodic runners,
loops/cycles and nonnumeric input mixtures do not enter this path. Explicit
finite input domains and initial GV domains retain their existing scope and
are never expanded to full catalog symbolism. Finite H requests stay bounded;
unbounded requests certify only completed symbolic path exploration.

Symbolic text is supported only as ACTION output, not as a guard operand.
Arithmetic on symbolic Boolean values is also refused. All unsupported typed
operations raise `Unsupported` explicitly; Python object-identity equality and
TypeError-to-None handling must never substitute for symbolic DSL semantics.
Missing internal registers use the existing interpreter initialization rule;
this path does not introduce arbitrary initial local stores or internal GVs.

## Algorithm and why numeric values are not enumerated

1. `timed.timed_product` selects `smt.smt_product` before constructing numeric
   representative lists when its eligibility checks succeed.
2. A lazy input identifies `(grounded key, input epoch)`. Reading it splits
   only the representation alternatives permitted by the catalog: None,
   integer, or binary64. Unread inputs cause no representation branching.
   A symbolic integer encodes the complete numeric domain; numeric values
   themselves are not enumerated. DOUBLE n represents n/10 on the agreed grid,
   with integer representations when n is divisible by ten and signed zero.
3. Both ordinary pure runners execute typed symbolic numbers. At a symbolic
   Boolean decision, execution pauses and queues both outcomes with their path
   constraints. The event is re-executed from its unchanged incoming state.
   Captured values and constraints survive waits/delays and subsequent reads.
4. **Branch feasibility is deferred.** Both branches may include infeasible
   paths; this overapproximation avoids expensive float feasibility queries
   when both traces are structurally equal. Every mismatch/domain query
   includes the full path constraints and input-domain constraints. No branch
   is discarded because a representative input missed it.
5. D1 observations retain call order, fanout boundaries, target chains,
   arguments and multiplicity. Equality is simplified first. Otherwise Z3
   checks `input_domain AND path AND observations_differ`.
6. UNSAT discharges that event/path. SAT is materialized as a concrete history
   and run through both ordinary catalog-checked runners and divergence replay.
   Only a confirmed ACTION mismatch produces DIVERGE. All queued bounded paths
   must be discharged for EQUIV; terminal states have no future ACTIONs.

Exact memoization includes typed symbolic stores, time, the entire ordered
path constraint list and known branch choices. It does not merge based on
predicate truth vectors, numeric samples or source names alone. SMT queries
are cached only with their complete constraint key. This conservative policy
does not promise a small state graph for long waits or many branches.

## Numeric and string correspondence

INTEGER operations use exact integers. DOUBLE input n/10 is rounded to binary64
with round-to-nearest/ties-to-even, matching conversion of the exact decimal
grid value. Addition/subtraction/multiplication involving floats use binary64
operations; integer true division rounds the exact rational quotient once.
Division by a constant zero follows the existing `0` result rule. Negative
zero is retained, including zero divided by a negative integer.

Mixed int/float comparisons use exact numeric values, matching Python's
comparison behavior without first rounding the integer to float. A conservative
outward magnitude bound rejects potentially overflowing or excessively large
intermediates (>1e100); it is a support restriction, not an extra constraint
silently imposed on the sensor domain. Existing None arithmetic/guard behavior
is executed on the concrete None branch.

Numeric ACTION arguments use existing numeric observation equality; converted
text preserves `6` versus `6.0` and `0.0` versus `-0.0`. Integer-to-text is encoded
exactly. Float-to-text uses one shared uninterpreted function of the IEEE bit
pattern. Every actual formatting function is a member of this overapproximation,
so UNSAT remains sound. SAT can be spurious and **never certifies a difference
without replay**. Raw numeric values are not automatically cast to STRING at
the service-call boundary. Numeric ACTION type/range inclusion is itself
checked universally; two programs emitting the same invalid call are refused.

`ir_step.eval_cond` was changed to execute only the selected arithmetic operator.
Its former eager dictionary evaluated unrelated operators too (including `%`
when executing `/`), which is invalid for the new typed terms. The ordinary
operator rules are preserved.

## Proof obligations and implementation correspondence

The argument is relative to the declared runner/catalog semantics and trusted
Z3 arithmetic/string theories; it is not a machine-checked proof of Python.

| Obligation | Reason / code |
| --- | --- |
| Complete input history coverage | `Input.force` represents all admitted kinds, grid indices and signed zeros; `world_at` gives equal symbols exactly within one input epoch. No values or histories are sampled for EQUIV. |
| Expression correspondence | `smt_values` preserves typed integer/IEEE operations, null branches and conversions. Constant operation order is retained; real-algebra identities cannot erase floating-point rounding. |
| Execution correspondence | The original `IrRunner`/`OneShotRunner` execute the lifted values. Each Boolean fork replays from the same incoming store; both branches cover the concrete execution choice. |
| Time coverage | Existing `next_time` visits both runners' deadlines and each input tick, including events at H. Symbolic conditions do not replace physical time by an abstract clock. |
| Safe state merging | Only complete typed store/time/path identities are merged; past input symbols and branch constraints remain in the key. |
| ACTION equivalence | Structural equality or UNSAT of the full mismatch query implies equality for every valuation of that path, including the actual float formatting function. D1 ordering is reused. |
| Result closure | EQUIV requires exhausting every queued bounded path. Solver/resource uncertainty is never treated as UNSAT. DIVERGE requires a valid concrete replay. |

Induction over expression evaluation, the decision forks within an event, and
the event sequence establishes the stated bounded trace implication. Exploring
infeasible paths may cause additional work, UNKNOWN or REFUSED; it cannot
remove a real execution from an EQUIV result. Operational errors on such paths
are conservatively refused, so the implementation is intentionally incomplete.

## Cost, evidence and remaining work

Defaults: 1000 ms per solver query, 10000 ms SMT-product budget, 10000 queries,
plus the existing state/transition caps. Concrete diagnostic/replay work can
follow a solver timeout and is transition-capped; the external evaluation
worker retains its wall/memory caps. SMT timeout/unknown gives UNKNOWN unless
a separately found concrete counterexample is replayed. The small existing
witness generator may be used after solver resource exhaustion **only to find
a counterexample**, never to certify equivalence. A SAT model that fails replay
also gives UNKNOWN. Float, real/integer and string constraints can be expensive;
the complete encoding is not merely a QF_LIA problem.

Install the optional dependency with `pip install -r explorer/requirements.txt`
(`z3-solver==4.15.4.0`). Each certificate records Z3 version, domains, bounds,
path/mismatch obligations, solver queries/results, resource caps and completion.
Certificates contain solver evidence and a manual proof correspondence, not
an independently checked proof object for the entire verifier.

Validation is in `tests/test_smt_trace.py`: average/joint-guard pairs and faults,
integer UNSAT obligations, numeric argument ranges, float rounding, conversion
types/signed zero, input history/delay/wait, D1 fanout, finite-oracle crosschecks,
caps, refusals, 405 arithmetic valuations, and 486 comparison valuations.
Production catalog values are preserved; explicitly marked integer/range unit
fixtures alter only an isolated in-memory model to test proof obligations.

Final self-review found two false-EQUIV holes in the initial development build:
string guards had inherited object-identity equality, and unsupported Boolean
subtraction could become None via the IR's TypeError handler. Independent finite
execution supplied ACTION counterexamples for both. The final implementation's
`SmtValue` rejects unimplemented operators, and two additional regressions fix
these cases as REFUSED. Development v1 artifacts precede this correction and
are superseded by v2; their passing tests were insufficient to expose the holes.

Development fixture results and final regression/E1 artifacts are linked from
`VERIFICATION_CONTRACT.md`. The full frozen 388-case **recheck v3** is now complete:
208 EQUIV-BOUNDED, 76 confirmed DIVERGE, 43 REFUSED, zero Explorer incomplete,
59 existing generation errors, and two preparation errors. All final verdicts
match the preceding v2. The 267 jointly completed finite comparisons agree;
four existing value-flow certificates are separate. C01_006 alone enters SMT,
but remains REFUSED: channel zero produces SetChannel(-1), outside the catalog
argument range. There are **zero new SMT certifications in this corpus**.
This does not negate the separate arithmetic development fixtures or establish
general SMT soundness. No new LLM generation or engine retry was performed.
[Detailed interpretation](../../eval/results/contract_recheck_v4_2026-09-07_v3/change_analysis.md).
The next paper tasks are the exact claim, its proof/evidence correspondence,
and current evaluation/limitations. Earlier v2 corpus artifacts remain intact.
