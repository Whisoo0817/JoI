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

## Observations

Told only that the candidate is wrong, the model re-derives a correct lowering for 31 of 68 cases
from the IR and the repair prompt alone. The counterexample's net contribution over that is five
cases, and it is not uniformly positive: it rescues 10 and costs 5.

The cost has a visible mechanism. The prompt instructs a focused, smallest-edit repair supported by
the evidence, so a witness makes the model adjust the one thing the witness points at and keep the
rest; without a witness it rewrites the block against the IR. In C20_014 the witness showed an
action 1 s early, the model raised the threshold and left `period` at 0, while the ablation wrote
`period` 100 with the same threshold and passed. In C24_005 the witness pointed at the missing first
capture and the model bolted the counted bodies on at top level, while the ablation rebuilt the
sustain-then-count shape. This is the same mechanism recorded in the round-1 failure analysis: a
focused edit preserves whatever the witness did not touch, including a dropped `OP|`.

## Why the ablation scores as high as it does

Analysed 2026-09-16, after this run. The ablation keeps the v5 repair prompt, and that prompt
carries rules the original lowering prompt does not have — most of all the sustain rule
(`files/joi_cycle.md` D-10 says wrapper period 1000 and threshold `for_ms / period`; the v5
checklist says period **100** and threshold `for_ms / 100 + 1`). 22 of the 31 ablation successes
fall in the two divergence families those rules address. So this arm measures a second lowering
pass with a failure-tuned prompt, not repair without evidence. Full account, with the per-family
table: `HANDOFF.md`.

## Files

`protocol_e3_feedback_ablation.json`, `prompts/repair_ablation_no_counterexample.md`,
`runs/e3_feedback_ablation_68_20260916/` (payloads as sent, raw responses, summaries),
`explorer/eval/results/qwen3_5_9b_fp8_e3_feedback_ablation_*`,
`explorer/candidates/qwen3_5-9b-fp8-e3-feedback-ablation`.
