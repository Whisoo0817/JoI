# E3 contract remediation and Qwen3.5-9B rerun plan

Status: corrected 382-case evaluation complete: 325 byte-identical reuses and 57 regenerations; 307 EQUIV, 70 DIVERGE, 3 REFUSED, 2 UNKNOWN. See [E3_QWEN_382_RESULT.md](E3_QWEN_382_RESULT.md). The historical 388-case report remains withdrawn. Feedback evaluation is deferred.
Predecessor: `runs/e3_gemma_v3_b5_hnone_20260915/` remains unchanged.
Current execution: regenerate only prefix-affected in-scope cases and C05_015; reuse all other matching candidates, then evaluate all 382 under one frozen evaluator contract. This supersedes the full-generation requirement in the original R5/R6 plan below.

Current scope: exclude every IR containing `timeout` or `on_timeout` (C26_001–006), leaving 382 E3 cases. The source dataset retains 388 rows. See [E3_SCOPE.md](E3_SCOPE.md).

## Objective and evidence boundary

The immediate objective is to remove mismatches between the declared E3 input
(`ir_gt` plus `binding_gt`) and the semantics actually consumed by lowering and
Explorer. The corrected 382-case Qwen run is a complete exploratory rerun, not
an independent confirmatory run, because the dataset and predecessor outcomes
have already been inspected. Confirmatory promotion requires a separately
frozen, previously unseen case set.

No case-specific edit may be made solely to change its verdict. Every change
must be stated as a general contract rule, covered by positive and negative
tests, and applied to all 382 rows before Qwen candidate generation.

## Sequential execution plan

### R0. Freeze the semantic decision sheet

Write one normative decision for each unresolved boundary before editing code:

1. **Polling period:** an unspecified re-arming/edge trigger uses `1 SEC`.
   Explicit IR periods are otherwise preserved exactly. Existing C14 reference
   rows that encode an implicit edge default as `100 MSEC` are audited against
   this rule rather than special-cased.
2. **Query cardinality:** a return-valued query assigned to one scalar variable
   requires exactly one bound provider. Action calls may still fan out.
3. **Effectful return:** declare whether a catalog function such as `SetVolume`
   has both an observable effect and a returned value. An unused return must not
   be represented by `call.var`.
4. **Numeric boundaries:** relative updates must define boundary behavior. Do
   not assume wrap, clamp, or invalid-call behavior without stating it.
5. **Window-end predicates:** “from A to B, if X never occurred” is evaluated at
   B using a persistent seen/not-seen state. Early abort after the first X is an
   equivalent optimization only when it suppresses the B-time action.
6. **Group Boolean reads:** define the quantifier explicitly. “No motion from
   any monitored sensor” becomes `all(sensor.Motion == false)`, equivalently
   `not any(sensor.Motion == true)`.

Gate R0: no implementation begins until these rules have a single source of
truth shared by Timeline extraction, lowering, and Explorer.

### R1. Repair the E3 input harness

1. Inject both confirmed `ir_gt` and confirmed `binding_gt` into generation.
2. Bypass natural-language service mapping and selector inference in E3.
3. Verify every bound device ID exists and declares the required capability.
4. Reject candidate reuse when embedded IR, binding, devices, or command bytes
   differ from the current dataset row.
5. Record dataset, catalog, prompt, lowering, Explorer, and model hashes.

Gate R1: a no-model preflight over 382 rows must report zero mapping calls,
zero missing binding IDs, and zero unnoticed payload mismatches.

### R2. Repair reference IR and binding data

Apply only rules frozen in R0:

- `C01_006`: represent “channel down” with the catalog's relative operation, or
  define a guarded/clamped SetChannel rule; do not leave a possible `-1` call.
- `C03_003`: provide an authoritative TargetTemperature domain or retain an
  explicit unsupported-domain outcome. Do not invent a temperature range.
- `C14_001`, `C14_002`, `C14_005`, `C14_006`: reconcile implicit edge polling
  with the frozen 1-second rule and remove stale payload drift.
- `C18_006`: encode interval state and evaluate it at 23:00; make the multi-
  sensor Boolean quantifier explicit.
- `C15_009`, `C15_010`: bind exactly one MenuProvider. If inventory metadata
  cannot identify the restaurant provider, enrich/fix the inventory first;
  never choose Main or Office arbitrarily.
- `C17_003`: separate the current-volume read from SetVolume, remove an unused
  return assignment, and apply the frozen upper-bound behavior.

Then run a dataset-wide validator for catalog method existence, argument type
and bounds, VOID/return assignment consistency, scalar-query cardinality,
binding capability, and occurrence-slot cardinality.

Gate R2: all 388 source references pass static validation, except limitations that are
explicitly retained and named before evaluation.

### R3. Extend Explorer only where a sound general rule is available

Implement in this order:

1. **Opaque STRING identity flow:** model an external STRING return such as
   `ChatWithAI` as a relational symbolic value when it is forwarded unchanged.
   Do not enumerate arbitrary strings or allow untracked string transforms.
2. **Boolean group normalization:** support bare grouped Boolean reads by
   normalizing them to an explicit `== true/false` quantifier form.
3. **Numeric action expressions:** support bounded affine/min/max expressions
   only if the verifier checks the full declared input domain and proves every
   emitted action argument satisfies the catalog domain.
4. **Periodic arithmetic:** extend beyond one-shot SMT only with a finite-state
   or inductive argument. Hoisting arithmetic into a temporary variable is not
   accepted as proof.

Each extension needs at least one self-equivalent test and one seeded faulty
variant that must produce a replayable divergence or a deliberate refusal.

Gate R3: all existing Explorer regression tests plus new soundness tests pass;
no former refusal is converted to EQUIV merely by disabling a safety check.

### R4. Contract-level dry run without Qwen

1. Re-run static preparation for all 382 confirmed IR/binding pairs.
2. Run canonical self-equivalence and seeded-fault probes for every newly
   supported semantic family.
3. Confirm that failures are classified separately as reference error, invalid
   candidate, Explorer refusal, resource failure, EQUIV, or replay-confirmed
   DIVERGE.
4. Review the complete change list once; after approval, prohibit further
   semantic changes during the Qwen run.

Gate R4: zero unexplained preparation failures and successful non-vacuity
probes. A failing gate returns to the responsible earlier stage, not to Qwen.

### R5. Freeze the Qwen protocol

Before starting the model server, create a new run ID and snapshot:

- all 382 row payloads and case IDs;
- the Qwen3.5-9B exact model ID and serving/sampling parameters;
- generation prompts and lowering code;
- catalog, binding policy, Explorer code, caps, timeout, and outcome taxonomy;
- the rule that all 382 cases occur exactly once in the denominator;
- no scientific retry or post-result rebinding.

Gate R5: all hashes and decision rules exist before the first candidate byte.

### R6. Generate fresh Qwen candidates

Generate all 382 candidates under a new tag. Do not reuse the existing
`explorer/candidates/qwen3_5-9b-awq-4bit` bytes. Generation is resumable for
technical interruption, but every retry and predecessor artifact remains
visible.

Gate R6: candidate manifest contains exactly one terminal generation record per
case and every embedded input matches the R5 snapshot.

### R7. Run Explorer and audit results

1. Run horizon-free Explorer with the frozen binding and evaluator contract.
2. Require closed-state evidence for `EQUIV-FIXPOINT` and successful replay for
   `DIVERGE_CONFIRMED`.
3. Report unconditional counts over 382 and conditional decision coverage.
4. Keep generation errors, invalid candidates, reference errors, Explorer
   refusals, timeouts, crashes, and replay failures as distinct outcomes.
5. Compare with the Gemma predecessor only as a lineage-aware exploratory
   comparison; do not pool their denominators or relabel the predecessor.

Gate R7: artifact hashes and complete outcome accounting pass before any paper
number is updated.

### Deferred: counterexample-feedback loop

Feedback prompt, interaction policy, retry control, and success metric have not
yet been designed or frozen. No feedback result is part of E3. When designed,
it must run as a separately preregistered experiment and must not overwrite or
relabel the historical 388 initial E3 outcomes.

## Must-run versus optional work

Must-run: R0 through R7. In R3, opaque STRING
identity and Boolean normalization are must-run if those cases remain in the
claimed supported fragment. Numeric/periodic arithmetic may remain an explicit
Explorer refusal if a sound extension cannot be completed; it must not be
silently approximated.

Optional confirmatory follow-up: after R7, freeze a new unseen held-out set and
run it once without changing the semantic contract. Only that separate block
can support a confirmatory label.
