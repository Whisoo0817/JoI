# Current contract fresh-generation evaluation

## Audit E3-CONTRACT-FRESH-V4

- Bounded verdict: supports_exploratory_follow_up
- Assurance: exploratory; self-review.

Under the frozen contract-v1 model and 3200ms horizon, timed Explorer agrees with dense 1ms search on jointly completed new generated samples from the familiar 388-task corpus.

Selected 388; prepared 281; jointly completed 267.
Full outcomes: {"AGREE": 267, "REFUSED": 46, "NOT_COMPARABLE": 14, "GENERATION_ERROR": 59, "PREPARATION_ERROR": 2}
Explorer: {"EQUIV": 203, "UNKNOWN": 1, "DIVERGE": 77}
Dense search: {"EQUIV_BOUNDED": 191, "INCOMPLETE": 14, "DIVERGE": 76}

Code overlap: 308/329 valid generated scripts exactly match old-v3 for the same task; only 21 differ. Every duplicate stays in the denominator. New invocation is not new unseen code.

Fresh generated code on familiar tasks is not an unseen-task test set. Agreement is conditional on both searches completing.
Refusal means the checker made no equivalence decision; it does not automatically mean generated code is wrong.
Shared adapters/observation remain a common source of error. This run does not establish full-language correctness or unbounded equivalence.

Detailed results and timings: `explorer/eval/results/contract_fresh_v4_2026-09-07/metrics.json`.
Canonical support record: `results-audit.json`. Historical results and development pilot are not pooled.

Next: Use only bounded descriptive results; obtain task-independent samples and stronger independent semantic coverage before stronger generalization/accuracy claims.
