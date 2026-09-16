# Ablation: repair without the counterexample (2026-09-16)

`protocol_e3_feedback_ablation.json`, run `e3_feedback_ablation_68_20260916`. Same 68 E3
DIVERGE_CONFIRMED candidates, same model and settings, same frozen evaluator as
`protocol_e3_feedback_v1.json`. The only change is what the model is told: instead of the F1/F2/F3
counterexample it receives `verifier_result = {"verdict": "not equivalent to the IR", "detail":
"withheld: no input history, no mismatching instant, no location"}`. The prompt is `repair_v5` with
the "Reading the evidence" section replaced by one paragraph and the four references to F1–F4
dropped; the repair rules, the shape checklist and the worked examples A–G are byte-identical, so
the ablated variable is the counterexample itself.

Question: does the recovery measured in v1 come from the counterexample, or from being asked again
in a fresh context with a better instruction?

## Result

| arm | EQUIV-FIXPOINT of 68 |
| --- | --- |
| v1, one counterexample per case | 36 (52.9 %) |
| ablation, verdict only | **31 (45.6 %)** |

Paired over the same 68 cases:

| | n |
| --- | --- |
| repaired by both arms | 26 |
| repaired only with the counterexample | 10 |
| repaired only without it | 5 |
| repaired by neither | 27 |

McNemar exact two-sided p = 0.30. **The difference is not statistically distinguishable from
chance at this sample size.**

Ablation terminal statuses: EQUIV-FIXPOINT 31, DIVERGE_CONFIRMED 29, PREPARATION_ERROR 3,
TIMEOUT 4, INVALID_OUTPUT 1. Repair stage: REVISED 67, INVALID_OUTPUT 1, 25,273 completion tokens,
208.5 s.

## Reading

Most of the recovery is not attributable to the counterexample. Told only that the candidate is
wrong, the model re-derives a correct lowering for 31 of 68 cases from the IR and the repair prompt
alone. The counterexample's net contribution is five cases.

It is not uniformly positive: it rescues 10 cases and costs 5. The cost has a visible mechanism.
The prompt instructs a focused, smallest-edit repair supported by the evidence, so a witness makes
the model adjust the one thing the witness points at and keep the rest. Without a witness it
rewrites the block against the IR. In C20_014 the witness showed an action 1 s early, the model
raised the threshold and left `period` wrong (0); the ablation wrote `period` 100 with the same
threshold and passed. In C24_005 the witness pointed at the missing first capture, the model bolted
the counted bodies on at top level; the ablation rebuilt the sustain-then-count shape correctly.
The same mechanism explains the round-1 failure analysis: a focused edit preserves whatever the
witness did not touch, including a dropped `OP|`.

## What this means for the write-up

A causal claim that the counterexample drives the repair is **not supported** by this data. The
defensible statements are:

- one round of verifier-guided repair brings 36 of 68 rejected candidates to EQUIV-FIXPOINT, and
  two rounds bring 40;
- every accepted repair is certified by the same frozen verifier, so the loop is closed by
  verification rather than by trust in the model;
- an ablation without the counterexample reaches 31 of 68, so at this model size the counterexample
  adds about five cases and the difference is within noise; what the loop mainly supplies is a
  reliable accept/reject signal, not a localisation hint.

The third point is a finding, not a weakness, and it is consistent with round 2: a second
counterexample added only four cases, and the model's own round-2 diagnoses showed it understood
the defect but could not express the fix in JoI.

## Files

`protocol_e3_feedback_ablation.json`, `prompts/repair_ablation_no_counterexample.md`,
`runs/e3_feedback_ablation_68_20260916/` (payloads as sent, raw responses, summaries),
`explorer/eval/results/qwen3_5_9b_fp8_e3_feedback_ablation_*`,
`explorer/candidates/qwen3_5-9b-fp8-e3-feedback-ablation`.
