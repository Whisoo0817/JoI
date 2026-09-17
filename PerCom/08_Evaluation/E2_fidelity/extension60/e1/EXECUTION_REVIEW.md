# E1 extension execution review

Snapshot: 2026-09-17T16:14:44.031956+00:00. Complete: all 48 frozen pairs have results.

This reviewer inspected frozen source and recorded results only; no evaluator was run or runtime file edited. Result snapshot SHA-256: `c9611bc6088de2ef331b3fc2a4b04030ce492c3f7adb3b04e630293d268fe70f`.

## Short-circuit correctness

`install_reference_short_circuit` calls the original `_reference_once` with `stop_at_diverge=True` for each selector assignment. One concrete differing history is sufficient to reject that assignment; later histories cannot restore universal equality. `reference_side` still enumerates alternative B5 assignments and accepts equivalence only when an assignment completes all histories equally. Unsupported assignments remain undecided under the original B5 fold. Therefore early divergence does not collapse the existential assignment search.

The wrapper counts actual examined histories by summing returned per-history outcome counts. `n_histories` retains its inherited available-history meaning; use `n_histories_examined` and `reference_assignment_checks` for actual coverage. For each short-circuit witness, it reruns the exact named history under the same assignment with short-circuit disabled and requires `REF-DIVERGE`, restoring diagnostic trace evidence. Replays are recorded separately and should not be mistaken for additional distinct histories. Original and supplementary assignment searches remain separate, preserving the historical fold described in REVIEW.md.

The reviewed runner now includes the lowering tree in runtime source hashes, resolving the earlier source-coverage note.

## Recorded result audit

- Rows: 48 / 48; missing: none.
- Explorer: `{"DIVERGE": 42, "REFUSED": 3, "TIMEOUT": 3}`.
- Reference: `{"REF-DIVERGE": 44, "REF-UNSUPPORTED-JOI": 2, "REF-EQUIV-CHECKED": 2}`.
- Agreement: `{"AGREE-DIVERGE": 39, "EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS": 3, "EXPLORER-REFUSED": 3, "EXPLORER-TIMEOUT": 3}`.
- Candidate false verdicts: 0.
- Freeze/input/catalog/runtime hashes checked: 224; mismatches or other audit problems: 0.
- Recorded assignment checks: 1469; actual history checks across assignments: 5121; diagnostic replays: 1462. These are execution counts, not unique histories or independent requests.

Problems: []

Divergence witness replay exceptions: []

Every checked equivalent assignment must have examined its whole available set; checked count sums and supplement eligibility were validated from the rows. Refusals, timeouts, and unsupported references are retained separately and are not treated as false verdicts. The two C16 variants, if present, retain unsupported aggregate reference results while their Explorer witnesses can independently confirm divergence; witness confirmation does not turn their aggregate reference outcomes into `REF-DIVERGE`.

Full machine-readable audit: `EXECUTION_REVIEW.json`.
