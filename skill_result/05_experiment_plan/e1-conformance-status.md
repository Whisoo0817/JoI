# E1 Interpreter Conformance Status

## Latest update — internal semantics, deployment measurements optional

The user fixed the claim scope to timed ACTION trace equivalence of the confirmed
IR and JoI code under the defined semantics. Physical-device and deployed-runtime
measurements are **not prerequisites** for this model-level claim.

- Added a stdlib-only generator reference independent of production parsers,
  evaluators, runners, scheduler, input inference and observation normalization.
- 11 programs × 243 input histories: **2,673 histories / 5,346 adapter trace
  comparisons matched**, plus **1 IR-only nested-cycle history matched**.
- **2 actual interpreter-function mutants detected** by ACTION discrepancies.
  These are distinct from the earlier changed-program controls.
- All **142 existing regression tests passed again**.
- Source/fixture hashes and outcomes: [e1_internal_semantics_2026-09-07_v1.json](../../explorer/eval/results/e1_internal_semantics_2026-09-07_v1.json).

Scope/proof linkage: [INTERNAL_SEMANTICS.md](../../explorer/INTERNAL_SEMANTICS.md).
This completes the present internal kernel audit, not a mechanized proof of all
supported constructs or full confirmatory E1 coverage. Broader constructor-specific
coverage remains a possible strengthening; deployed-runtime conformance is an
optional extension, not a blocker. Next: freeze the evaluation model/candidates
and conduct a new held-out evaluation. Historical results below are retained.

## Earlier update — 2026-09-07 target-runtime contract

The user authorized resolving ambiguous runtime policies in favor of an
efficient formal model, with the JoI implementation to be aligned as needed.
The normative target is now [RUNTIME_CONTRACT.md](../../explorer/RUNTIME_CONTRACT.md),
not an inferred behavior of an uninspected deployment. It fixes completion-relative
periods, blocking continuation, snapshot reads, missing values and first-iteration
initialization. Earlier runtime-policy questions no longer block specification work.

New development evidence: **14 hand-derived ACTION traces matched**, **1 expected
refusal**, and **3 changed-program controls detected**. The existing contract and
frontend suites also passed again (**55 cases**). The controls mutate programs,
not independently implemented interpreters. Local ANTLR accepted all 15 probe
scripts; fractional-unit delay remains a documented grammar discrepancy.

Artifact: [e1_target_runtime_2026-09-07_v1.json](../../explorer/eval/results/e1_target_runtime_2026-09-07_v1.json).
It records fixtures, expected/observed traces and source hashes. Actual runtime
runs: **0**. Overall E1: **incomplete**, still development-only. Independent
semantic-oracle/interpreter-fault evidence and deployment conformance remain
distinct obligations. The historical pilot below retains its original scope.

## Status

- **Evidence class:** development-only
- **Pilot result:** 6/6 common-subset cases passed
- **Artifact:** `results/E1/legacy-conformance-dev/`
- **Independent implementation:** retained SenSys IR and JoI simulators, with
  separate parsers, expression evaluators, worlds, and control-flow engines

## Covered in the pilot

- immediate calls;
- periodic level conditions and numeric boundaries;
- rising-edge behavior implemented with a persistent latch;
- `if`/`else` and a literal action argument;
- one-shot delay and continuation;
- multiple calls with observable action order.

For each case, the current IR runner is compared with the legacy IR simulator,
the current code runner with the legacy JoI simulator, and both implementations
must also agree on the paired behavior within the declared horizon.

## Boundary of this evidence

This is not yet the confirmatory E1 result. The legacy simulators are an
independent implementation, but not the normative formal semantics. The pilot
does not compare concrete device targets and does not yet cover grounding,
reentry, cancellation, cron, missing values, timer ties, or merge laws. Those
constructs require a frozen hand-derived boundary oracle or a second evaluator
implemented directly from the final operational rules.

## Next E1 step

Freeze hand-derived expected traces for the uncovered boundary cases, seed
faulty interpreter variants to demonstrate non-vacuity, and retain every
discrepancy before promoting E1 beyond exploratory evidence.
