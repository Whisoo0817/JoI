# A/B Evaluation Protocol and Status

## Status

- **Stage:** v3 held-out search-layer evaluation completed and audited
- **Last updated:** 2026-09-04
- **Immediate objective:** obtain defensible false-accept (`A`) and
  false-reject (`B`) counts for Behavioral Explorer on a frozen, finite,
  bounded gold set.
- **Abstract use:** the narrowly scoped H=32 search-layer result may be used;
  do not describe it as independent end-to-end semantic accuracy.

## Decision contract

For a pair with an independently frozen gold label:

| Gold | Explorer `EQUIV` | Explorer `DIVERGE` |
| --- | --- | --- |
| equivalent | correct | false reject (`B`) |
| divergent | false accept (`A`) | correct |

`UNKNOWN`, `REFUSED`, timeout, invalid input, crash, and retry are not folded
into A or B. They remain visible in total-case accounting and determine the
completion rate. This prevents a fail-closed checker from obtaining `A=B=0`
by refusing difficult cases.

The primary gate is zero false accepts on every completed exact case. Zero
false rejects is the target for the frozen supported fragment. Counts must be
reported with separate equivalent/divergent denominators and binomial
confidence intervals; zero observed errors is not presented as proof of zero
population error.

## Two evidence layers

1. **Search-layer differential oracle.** `explorer/exact_tick.py` enumerates
   every sequence over an explicit finite input model, tick by tick, through a
   declared horizon. It does not use Explorer state normalization, time jumps,
   predicate-derived input cells, or combination deduplication. It shares the
   concrete IR/code one-step runners, so it tests Explorer's search reductions
   rather than independently validating runner semantics.
2. **Interpreter conformance.** E1 separately compares the one-step runners
   with frozen operational rules and an independently implemented evaluator
   or hand-audited boundary oracle. A/B results cannot be promoted to an
   end-to-end verifier-correctness claim until this gate passes.

## Finite model contract

Every gold case must declare, before its result is observed:

- exact sensor/event/GV keys and their finite values;
- initial persistent-variable domains, including absent/unseeded where valid;
- logical tick size and horizon;
- expected gold class and its provenance;
- supported-fragment version;
- state/transition/time caps;
- all terminal outcomes, including refusal and incomplete exploration.

The confirmatory set may contain only cases selected by this syntactic/model
contract. A case cannot be moved out of scope after its outcome is known.

## Dataset separation

- **Development:** current 35 soundness regressions, 10 complex scenarios,
  existing mutations, and any new counterexample found while implementing the
  oracle. Explorer may be changed using these cases.
- **Confirmatory:** held-out, balanced equivalent/divergent pairs frozen after
  development. Equivalent pairs must include syntax-different implementations;
  divergent pairs must cover predeclared event, state, time, repetition,
  cancellation/reentry, action-argument, ordering, and binding faults.
- **Application corpus:** the existing 388 generated-code candidates remain a
  separate system-use evaluation. They are not accuracy gold merely because
  Explorer already classified them.

The abstract's `N` is the number of frozen gold pairs on which both the exact
oracle and Explorer complete. The total selected count and every excluded,
unsupported, or incomplete outcome must appear beside it.

## Implementation progress

- [x] Add a separate bounded tick-by-tick oracle.
- [x] Preserve action order, duplicates, arguments, targets, termination, and
  concrete counterexample paths.
- [x] Fail explicitly on state/transition caps.
- [x] Add seven oracle/bounded-mode regressions; retain all 35 existing
  soundness regressions.
- [x] Add an equal-horizon mode to Behavioral Explorer.
- [x] Add a manifest-driven paired evaluation runner and raw JSONL accounting.
- [ ] Construct and review the full development gold set (six-case
  non-vacuity pilot currently passes; it is not confirmatory evidence).
- [x] Run outcome-visible differential development sweeps at 4, 8, and 32
  ticks over all 388 existing generated candidates.
- [x] Fix the first Explorer discrepancy found in development and add a
  permanent regression.
- [x] Classify five malformed generated programs as preparation errors; keep
  27 fail-closed unsupported outcomes visible.
- [x] Add boundary-neighborhood stress domains for the separate `R` metric.
- [x] Add outcome-blind input-domain manifest generation with per-case source
  digests, explicit values/initial states/horizon, and run-time drift checks.
- [x] Rerun all 388 development candidates from a serialized manifest; all
  outcomes and unsupported/preparation failures remain visible.
- [x] Audit every READY case's behavior-relevant reads without consulting
  `runner.axes` or `derive_axes`; v3 passes 311/311. The audit still shares
  parsing, grounding, and IR compilation and is not a fully independent
  frontend.
- [x] Freeze a new-model held-out generation plan, retain its failed first
  attempt, and freeze the successful retry's candidate/input manifests.
- [x] Execute the source-drift-checked held-out A/B candidate run at H=32.
- [x] Version the evaluator source, generate a new v3 held-out sample, freeze
  its input manifest before A/B inspection, and complete a result audit.
- [ ] Expand E1 beyond the six-case common-subset pilot before making a broad
  end-to-end semantic-correctness claim.

## Next implementation step

Expand E1 and structured gold construction across the predeclared event,
state, time, repetition, cancellation/reentry, action-argument, ordering, and
binding strata. The current v3 result supports a bounded search-layer claim;
broader verifier-correctness wording still depends on those semantic tests.

## Development pilot result (not paper evidence)

The first executable pilot contains three equivalent and three divergent
IR–code pairs. All six completed with `A=0` and `B=0`; maximum Explorer latency
was below 0.004 seconds on this trivial suite. An initial 28.3% transition
reduction calculation was invalidated because it mixed full equivalent-space
exploration with traversal-order-dependent early counterexamples. The harness
now computes reduction only over equivalent pairs for which both methods
complete the entire bounded space. No pilot number may be copied into the
abstract.

## Development differential sweep

The first four-tick sweep exposed one false-accept candidate, C10_002. At the
same logical time, bounded Explorer merged two concrete timer ages that fell
in the same threshold zone. A newly started timer then displaced an older
timer that would fire inside the horizon. The unbounded Explorer happened to
find the fault through a time jump, but bounded evaluation missed it.

Evaluation-only bounded mode now preserves concrete stores and logical depth
and advances one tick at a time. It therefore evaluates input-boundary
discretization without relying on state-zone merging or time jumps. A targeted
regression reproduces C10_002.

After the fix, development sweeps at horizons 4, 8, and 32 agreed on all 356
comparable cases. At horizon 32 the two searches each evaluated 764,396 pair
transitions. The remaining outcomes were 27 fail-closed unsupported cases and
five preparation/parser errors. These are outcome-visible development results,
not confirmatory A/B evidence.

A boundary-neighborhood stress model was then used only on the exact side. It
adds multiple raw values immediately below, at, and above every numeric
threshold and multiple distinct values in categorical catch-all cells. At an
eight-tick horizon, all 356 comparable cases still agreed. For the 213 pairs
that both methods exhaustively classified as equivalent, exact tick search
evaluated 169,158 transitions and bounded Explorer evaluated 16,372, a 90.3%
reduction. This is a promising development measurement, not the final `R`:
the current sweep obtains its input keys and threshold constants from Explorer
analysis and must be converted to a frozen, auditable manifest first.

The next development run serialized those boundary-neighborhood values before
execution and bound every case to the dataset payload and candidate source by
SHA-256. The runner rejects source, input-key, period, or horizon drift. On the
same 388 outcome-visible candidates, 356 completed (91.8%), comprising 213
bounded-equivalent and 143 divergent pairs. The two searches agreed on all
completed cases (`A=0`, `B=0`); the corresponding Wilson 95% upper bounds are
2.62% and 1.77%, respectively. Across the 213 full-space equivalent pairs,
the exact search evaluated 142,685 transitions and Behavioral Explorer 16,372
(88.5% fewer). Median, p95, and maximum Explorer times were 0.25 ms, 3.71 ms,
and 81.14 ms. These remain development measurements because the candidate set
was already used to repair the Explorer, the manifest is not frozen, its
static domain builder shares implementation analysis, and both searches share
the one-step runners.

## Held-out candidate run

A generation manifest selected all 388 dataset rows before running the active
Gemma-4-26B model. The first attempt produced 388 generation errors because
the model wrapped otherwise valid guided JSON in Markdown fences. That attempt
is retained. A technical retry changed only mapping-response normalization,
with three new regressions, and again selected all 388 rows before generation.

The retry produced 325 candidate programs and 63 explicit
`device_not_connected` generation failures. Before any A/B outcome was read,
the 388-case source set, per-candidate SHA-256, finite boundary domains, initial
GV domains, and H=32 were frozen. Static preflight marked 309 pairs READY, 15
unsupported, one preparation error, and the 63 generation errors.

Both the initial measured run and a metadata-only technical retry completed
all 309 READY pairs. The exact oracle labeled 228 bounded-equivalent and 81
divergent; Behavioral Explorer agreed on every pair (`A=0`, `B=0`). Wilson 95%
upper bounds are 4.53% for false accepts and 1.66% for false rejects. Across
the 228 full-space equivalent pairs, exact enumeration evaluated 424,105
pair-transitions and Behavioral Explorer 109,834 (74.1% fewer). Median, p95,
and maximum Explorer times in the retry were 0.60 ms, 50.67 ms, and 268.14 ms.

These are **confirmatory-candidate**, not yet abstract-ready, results. The
case/output selection and input manifest were frozen, but E1 currently covers
only a six-case common subset, input-domain review is not independent, and the
exact and optimized searches share the IR/code one-step runners.

## Post-audit repair and v3 held-out result

The static audit of v2 found that 15 READY programs read environment values
that flowed directly into observable action arguments but had no explicit
input axis. Twelve additional clock findings were audit false positives. The
Explorer was changed to enumerate a declared three-value finite domain for
otherwise unpartitioned observable value flows, and zero-argument IR queries
were aligned with grounded device keys. The same v2 candidates were then used
only as a development regression: 309/309 READY pairs passed the revised
domain audit and exact differential comparison with A=0 and B=0.

After that repair, the evaluator was committed and a new v3 generation plan
selected all 388 rows before model execution. No v3 output had been observed
during the repair. The resulting 388 candidates were frozen by SHA-256 with
H=32 and explicit input/initial-state domains before A/B results were read.
Static preflight marked 311 READY, 15 unsupported, one preparation error, and
61 generation errors. A separate static read audit that does not use
`runner.axes` or `derive_axes` covered every READY pair (311/311).

Both exact tick traversal and Behavioral Explorer completed all 311 READY
pairs. Exact traversal labeled 231 bounded-equivalent and 80 divergent;
Explorer agreed on every pair (false accepts A=0/80, false rejects B=0/231).
The corresponding Wilson 95% upper bounds are 4.58% and 1.64%. Across the 231
full-space equivalent pairs, exact traversal evaluated 427,685 pair
transitions and Explorer evaluated 113,558, a 73.45% reduction. Explorer time
was 0.65 ms median, 52.09 ms p95, and 280.12 ms maximum.

This result is suitable for the following bounded search-layer statement:
“At H=32, Behavioral Explorer matched exhaustive tick-by-tick traversal on all
311 evaluable IR–code pairs while reducing pair-transition evaluations by
73.4% on equivalent pairs (p95 52.1 ms).” It must not be shortened to “the
verifier is 100% accurate”: the oracle shares the concrete one-step runners,
the result is restricted to the frozen finite input models, and 77 of 388
generation attempts were not READY.
