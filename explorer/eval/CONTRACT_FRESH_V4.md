# Contract-v1 fresh-generation evaluation (2026-09-07)

This run uses new generated JoI candidates on the existing 388-task corpus.
The task corpus has been used in development. It is a fresh generation sample,
not an unseen-task held-out split, and its audit assurance is exploratory.
No historical v3 number is transferred to the current implementation.

## Final outcome

| Outcome | Cases |
|---|---:|
| Explorer equivalent within 3200ms | 203 |
| Explorer counterexample, replay confirmed | 77 |
| Explorer incomplete | 1 |
| Preparation REFUSED | 46 |
| Generation pipeline failure | 59 |
| Parsing/preparation error | 2 |
| All selected attempts | 388 |

Both searches completed on **267 cases** and agreed on all of them: 191 bounded
equivalent, 76 divergent. Dense search was incomplete on 14 cases: Explorer
completed 12 as bounded equivalent and one as divergent; both were incomplete
on C01_014 (100,003 PM10 values exceeded the frozen 100,000-combination cap).
There were no timeouts, crashes or unconfirmed Explorer replays.

Generation took 899 seconds; evaluation took 194.794 seconds. Across 281 prepared
cases, Explorer search median/p95/max was 0.406ms/107.858ms/3.424s; process wall
including startup/preparation was 69.857ms/194.962ms/3.583s. Maximum process RSS
was 92,900KiB. Many cases terminate immediately; the dense comparator has a
smaller median search time, so these results do not support a blanket speedup.

**Overlap audit:** 308 of 329 valid generated scripts exactly match their old-v3
counterpart; only 21 differ. All remain in the denominator. This substantially
limits code-level holdout evidence despite fresh model calls. None of the 281
READY cases has a nonempty initial-GV model; this corpus does not independently
strengthen the initial-GV coverage evidence.

Artifacts: [metrics](results/contract_fresh_v4_2026-09-07/metrics.json),
[full outcomes](results/contract_fresh_v4_2026-09-07/case_outcomes.jsonl),
[audit](results/contract_fresh_v4_2026-09-07_audit/results-audit.md).
Audit verdict: **supports_exploratory_follow_up**, with self-review and shared
semantics disclosed. Next: separate development exposure/duplicates when designing
new evaluation samples, and examine longer horizons without rewriting this run.

## Frozen execution protocol

- Protocol: `results/contract_fresh_v4_2026-09-07_protocol.json`, written before
  starting generation. All 388 selected IDs remain in every accounting table.
- Generator: existing `explorer.e3 gen`, local Gemma-4-26B-A4B AWQ server,
  gold IR injection, fresh mapping/lowering, four workers, 120 seconds per row.
  No model-output retries conditioned on Explorer results. Stage settings are
  preserved by the generation-source hashes; the helper exposes no fixed seed.
- Fixed inventory and gold binding from the dataset. Actual service catalog
  validation stays on. External changes every 100ms, exact integer-ms deadlines,
  DOUBLE lattice 0.1, nullable snapshots and the agreed ACTION observation.
- Both searches use the same serialized input and initial-GV domains at the
  same absolute start time, over **0–3200ms inclusive**. The input changes at
  0, 100, ..., 3200ms. Long delays beyond this horizon may never produce an
  ACTION; bounded equality does not imply they eventually behave alike.
- Sensor/return domains come from the catalog and certified joint partition.
  Exact observable values require supported finite domains. Predicate-family
  initial/external GV models are declared normative domains, not measured
  deployed stores. Missing required explicit domains are REFUSED; no invented
  subset or silent non-null filtering is used to obtain a verdict.
- Each search: 200,000 states, 500,000 transitions, 100,000 input combinations,
  20 seconds process wall time, 768MiB address-space limit. These are resource
  limits, not semantic completeness bounds. A failed exact search does not
  suppress the separately executed Explorer result.
- One evaluation worker; Explorer then dense 1ms search, each in a fresh
  process. Generation finishes before evaluation starts. Per-case results are
  flushed immediately. Timeout memory measurements are unavailable, not zero.
- Hash checks establish repository-local continuity, not physical isolation or
  external attestation. The production evaluator SHA remains
  `6742008b73e0dbf4475b95386766534084a66f227667ce49a9f71031195dc946`.

## Reading the results

Preparation REFUSED is distinct from a demonstrated ACTION difference. A
dynamic catalog rejection during exploration also produces no equivalence
verdict. Generation errors, parse/preparation errors, resource failures and
unconfirmed counterexample replays remain visible.

Agreement uses only cases where **both** searches completed, with its denominator
reported alongside all 388 attempts. The dense search shares interpreters and
observation with Explorer; it is a traversal cross-check, not an independent
semantic ground-truth label. Existing internal E1 evidence is separate.

The report records all-attempt process latency, conditional search latency and
observed process peak RSS separately. Transition/time comparisons use the same
completed bounded-equivalent cases; early counterexample termination is not
counted as evidence of a general exhaustive-search speedup. No inference to
unseen-task accuracy or full-language correctness is made.

## Development and technical history

- Five-case old-v3 pilot selected the first case of the first five categories,
  sorted by ID: two completed agreements, two preparation refusals, one old
  generation error. Total measured execution wall time 0.289 seconds. This
  mostly simple smoke check does not estimate the full corpus runtime.
- Worker/direct-adapter differential smoke check: six actual-catalog development
  fixtures, both engines, twelve verdict comparisons matched. This includes
  argument-order, string-return and integer-boundary differences plus a
  wait/delay case. No production verifier code was changed.
- Before protocol creation, a relative `__file__` path caused the new harness
  snapshot command to fail. Fixed before candidate freeze/search; subsequent
  missing-file commands created no result. No scientific run was retried.
- The new harness and reporter were syntax-checked. The existing 142-test result
  remains the preceding internal-E1 run; it is not represented as rerun here.

## Commands

```bash
python explorer/eval/frozen_contract.py prepare \
  --protocol explorer/eval/results/contract_fresh_v4_2026-09-07_protocol.json \
  --output explorer/eval/results/contract_fresh_v4_2026-09-07_manifest.json
python explorer/eval/frozen_contract.py run \
  --protocol explorer/eval/results/contract_fresh_v4_2026-09-07_protocol.json \
  --manifest explorer/eval/results/contract_fresh_v4_2026-09-07_manifest.json \
  --output explorer/eval/results/contract_fresh_v4_2026-09-07
python explorer/eval/report_frozen.py \
  --prefix explorer/eval/results/contract_fresh_v4_2026-09-07
```

The first two commands refuse existing output paths. Preserve the final
artifacts. Once documentation/source snapshots change, a new run needs a new
version and protocol rather than bypassing the continuity check.
