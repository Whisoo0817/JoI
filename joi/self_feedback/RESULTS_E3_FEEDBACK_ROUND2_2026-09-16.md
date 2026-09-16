# E3 feedback, round 2 on the 26 still-rejected cases (2026-09-16)

Round 1 (`protocol_e3_feedback_v1.json`, run `e3_feedback_68_20260916`) left 26 of 68 as
DIVERGE_CONFIRMED, 5 as evaluator TIMEOUT and 1 as MODEL_ERROR. Only the 26 have a fresh confirmed
counterexample, so only they are eligible for a second round. Cases that reached EQUIV-FIXPOINT in
round 1 are final and were not re-run.

Two arms, same 26 cases, same evidence, same model settings, same frozen evaluator:

| arm | prompt | status |
| --- | --- | --- |
| **r2a** | `prompts/repair.md`, byte-identical to round 1 | reportable; no knowledge of the round-1 outcomes enters it |
| r2b | `prompts/repair_r2_quantifier.md` (= `repair_v6a`) | **exploratory only**; its rule was derived from the round-1 failures of these very cases |

## Result

| | round 2 EQUIV | two-round total of 68 |
| --- | --- | --- |
| r2a (same prompt) | 4 / 26 | **40 / 68 (58.8 %)** |
| r2b (quantifier rules added) | 6 / 26 | 42 / 68 (61.8 %), not reportable |

Terminal statuses this round:

| status | r2a | r2b |
| --- | --- | --- |
| EQUIV-FIXPOINT | 4 | 6 |
| DIVERGE_CONFIRMED | 14 | 10 |
| PREPARATION_ERROR (script rejected by the parser) | 4 | 3 |
| INVALID_OUTPUT (not valid JSON) | 1 | 6 |
| NO_CHANGE | 3 | 1 |

Round 1 had zero syntax or format failures; round 2 has 5 (r2a) and 9 (r2b).

## What the second counterexample actually did

The evidence works. Given the new witness the model names the defect correctly — C07_024's r2b
diagnosis reads "the IR specifies a rising-edge wait over a slot declared `any`, which requires the
existential operator; the candidate used `all` (universal), causing the wait to block until *both*
sensors were true". Six of 26 r2a answers and 12 of 26 r2b answers discuss the quantifier, against
none in round 1.

What fails is expressing the fix in JoI:

- `any(...)` in action position (C08_020, C08_021, C10_003 in r2a) — the contract allows the `any`
  selector only inside a condition, so the candidate never reaches the verifier. Replacing it with
  `all(...)` in that position recovers C10_003 only (`any_in_action_diagnostic.json`).
- the `|` written after the value instead of on the operator: `sound > 30|` rather than
  `sound >| 30` (C08_020, C08_032, C10_003 in r2b). The parser rejects the token.
- `all(#G1_Dehum_1, #G1_Dehum_2)` — an invented multi-device selector (C08_027, r2a).

So the bottleneck at this model size is not the evidence and not the concept; it is surface
knowledge of the JoI quantifier syntax. That is the same gap the failure analysis of round 1 found,
and a second counterexample does not close it.

## A defect in the r2b prompt

Six r2b answers are invalid JSON. The added checklist row contains the literal text `{"any": [...]}`,
and the model copies it into the `diagnosis.summary` string without escaping the inner quotes. This
is a flaw in the prompt I wrote, not evidence about the rule, and it inflates r2b's failure count.
Any future version must not put literal JSON with double quotes into the prompt text.

## Reading

Round 2 with the unchanged prompt adds 4 cases, from 36/68 to 40/68. That is the number to use if a
second round is reported. The quantifier arm adds 2 more, is post-hoc on this evaluation set, and
carries the prompt defect above, so it should be cited only as a diagnostic — and it is itself
evidence that stating the rule does not reliably help this model.

## Files

- `protocol_e3_feedback_r2a.json`, `protocol_e3_feedback_r2b.json` (frozen; round-1 run and candidate
  tag as baseline, 26 case ids with their round-1 candidate hashes).
- `runs/e3_feedback_r2a_26_20260916/`, `runs/e3_feedback_r2b_26_20260916/`: evidence, raw responses,
  repair and evaluation summaries; `any_in_action_diagnostic.json` under the r2a run.
- `explorer/eval/results/qwen3_5_9b_fp8_e3_feedback_r2{a,b}_*`: evaluator records.
- `explorer/candidates/qwen3_5-9b-fp8-e3-feedback-r2{a,b}`: the evaluated copies.
- Harness: `run_e3_feedback.py` now takes the protocol file from `FEEDBACK_PROTOCOL` and reads the
  population size from the protocol instead of assuming 68.
