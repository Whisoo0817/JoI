# E3 feedback run — results (2026-09-16)

Run id `e3_feedback_68_20260916`, protocol `protocol_e3_feedback_v1.json`
(sha `b9b3b367…`), prompt `prompts/repair.md` (v5), model `Hyper-AI/Qwen3.5-9B-fp8` via vLLM,
thinking off, temperature 0, seed 0, max_tokens 4096, IR timing facts on, **one** repair call per
case, no retry. Evaluator = the E3 final `frozen_contract` snapshot (`snapshot_continuity: true`),
outcomes sha `b5db22c8…`. Git HEAD at run time `c63f614`, tree clean.

Question answered: of the 68 E3 candidates the Explorer rejected with a replay-confirmed
counterexample, how many does one counterexample-guided revision bring to EQUIV-FIXPOINT?

## Headline

| final status | n |
|---|---|
| **EQUIV-FIXPOINT** | **36 / 68 (52.9 %)** |
| DIVERGE_CONFIRMED | 26 |
| TIMEOUT (evaluator 20 s cap) | 5 |
| MODEL_ERROR (request over context) | 1 |

All 67 answered calls were well-formed and changed the script (`REVISED` 67, `NO_CHANGE` 0,
`INVALID_OUTPUT` 0). Everything that is not EQUIV-FIXPOINT stays in the denominator.

By divergence type (2026-09-15 audit labels, `e3_68_divergence_types.json`):

| type | EQUIV / n |
|---|---|
| event wait lowered to 1 s polling | 15 / 31 |
| sustained condition fires one tick early | 15 / 21 |
| call scope / termination / preceding action | 2 / 5 |
| sustain confused with the following cycle period | 1 / 4 |
| first cycle body missing or delayed | 0 / 3 |
| saved value replaced by a fresh read | 2 / 2 |
| signed difference turned into abs | 1 / 1 |
| output string changed | 0 / 1 |

## Cost and latency

Model (67 calls, 4 client threads; the server admitted one sequence at a time, so client-side
seconds include queueing and are not per-request latency):

| | median | p90 | max |
|---|---|---|---|
| prompt tokens | 6,814 | 21,068 | 53,124 |
| completion tokens | 368 | 524 | 1,061 |
| client seconds (incl. queue) | 15.1 | 69.0 | 98.4 |

Totals: 719,607 prompt tokens, 27,012 completion tokens, wall 397.7 s → **5.9 s per case
effective**, ≈68 completion tokens/s at the server. Completion length does not separate
successes from failures (median 368 vs 361 tokens). Prompt size is driven by the counterexample:
the system prompt is ≈5.5 k tokens; long sustain witnesses (10–30 MIN at 1 s steps) push the
F1 input history to 20–50 k tokens, and C20_016 (30 MIN, 1,799-step witness, ≈96 k tokens)
exceeded the 100 k context → MODEL_ERROR, recorded and not retried per protocol.

Verifier (68 cases, frozen contract): process wall median 0.06 s, p90 0.71 s, max 20.0 s (the cap);
peak RSS ≤ 50 MiB. The same 68 in the E3 baseline: median 0.07 s, max 0.6 s. Evaluate stage wall
106.7 s. Five repaired candidates hit the 20 s cap (see below).

## Why 32 did not reach EQUIV

Read from the new witness of each case (`explorer/eval/results/…_run/case_outcomes.jsonl`) and the
returned script (`runs/e3_feedback_68_20260916/responses/`). Where a cause is claimed below it was
tested: the script was rewritten by a mechanical rule and re-verified
(`runs/e3_feedback_68_20260916/failure_cause_diagnostic.json`, diagnostic only, outside the
protocol, not counted in the 36).

1. **The guard condition was rewritten and lost JoI's exists-quantified compare — 12 cases**
   C07_024, C08_018, C08_020, C08_021, C08_022, C08_024, C08_026, C08_027, C08_029, C08_032,
   C10_003, C12_007 (and C14_006, same class, see 6).
   JoI writes "at least one device satisfies" as `OP|` (`==|`, `<|`, `>=|` …); the plain operator over
   a device group means all-satisfy (`files/re_translate.md`, `explorer/runtime/joi_parser.py`).
   The original candidates used `OP|` correctly for `{any: [...]}` slots. When the model rewrote the
   periodic `if` into a blocking wait it normalised the condition and dropped the `|`, turning
   "any sensor crossed" into "every sensor crossed". Of the 13 candidates that used `OP|`, 11 dropped
   it, and **all 11 failed; none that dropped it passed**. A second, related slip: the rearm wait was
   written as the algebraic complement (`>= 50` for a `< 50` trigger) instead of `not (C)`, which also
   never fires when a reading is null.
   Restoring just these two things — keep `OP|`, rearm as `not (<trigger>)` — turns all 10 of the
   rising-edge cases into EQUIV-FIXPOINT, and `OP|` alone fixes C10_003 and C12_007. Testing each
   edit on its own (`single_edit_split.json`) splits the 12 by how little was wrong:

   | what was wrong | n | cases |
   | --- | --- | --- |
   | only the `\|` on one comparison operator | 5 | C07_024, C08_018, C08_032, C10_003, C12_007 |
   | only the rearm wait (trigger condition correct) | 4 | C08_020, C08_022, C08_027, C08_029 |
   | both | 3 | C08_021, C08_024, C08_026 |

   In the first five the repair is otherwise exactly right — the periodic `if` became the blocking
   two-wait shape, the body, targets, literals and period are all correct — and restoring one
   character turns a rejected candidate into EQUIV-FIXPOINT. One character, but not a cosmetic one:
   `==|` asks whether any sensor of the group crossed, `==` whether all of them did.
   `prompts/repair.md` never mentions `OP|` (0 occurrences) and its worked examples all use
   single-device conditions, so the model had no reason to preserve it. This is a prompt gap, not a
   limitation of the counterexample: the witness pinpointed the instant correctly, and in most of
   these cases its input row even contained the discriminating assignment (one sensor crossing,
   the other null or below).

2. **Tick arithmetic / period — 4 cases (+1 in group 6)**
   C20_007 (10 MIN → wrote 601, needs 6001), C23_003 (15 MIN → 901, needs 9001),
   C23_005 (3 MIN → 181, needs 1801): a ×10 slip despite the ms/tick facts in the payload.
   C20_014 set period 0 with threshold 6001 (one-shot script, never reaches the count).
   C23_001 kept period 1000 and only bumped the threshold to 601 (evaluator then timed out).

3. **Structure errors in sustain + follow-up shapes — 5 cases**
   C23_004 left `delay(20 MIN); Off` outside the sustain `if` (the original scope error untouched;
   only the threshold was fixed). C24_003 re-declares the counter `n := 0` inside the sustain block.
   C24_004 misplaced a brace so `else { hold = 0 }` binds to the inner `if` and resets every tick.
   C24_005 `break`s when the sustain completes and put the counted bodies at top level (fires at
   t=0). C18_010 (cron-anchored) moved the one-time lock into the hourly body and replaced the
   until-break with a wait.

4. **Pre-cycle action + cycle (phase pattern) — 3 cases**
   C12_004, C12_010 kept the phase pattern, so the first cycle body is still missing at the
   trigger instant; C12_012 dropped the phase pattern and now blocks on the trigger every cycle.
   Same weakness as dev case D4a.

5. **Over-simplified — 1 case**
   C14_004 dropped the rearm, the `min(…,100)` clamp and the `OP|`.

6. **Verifier could not decide — 5 TIMEOUT cases** (C14_001, C14_002, C14_005, C14_007, C23_001)
   The returned C14 scripts are the intended blocking two-wait shape with the clamp kept. Their
   arithmetic action argument (`min($Light.CurrentBrightness + 10, 100)`) is checked by full
   enumeration (2,209 states, 0.23 s in E3); combined with the blocking wait the search did not finish
   inside the frozen 20 s cap. An exploratory recheck (`gate_pair` default caps, 600 s allowance;
   `timeout_recheck_exploratory.json`) ends REFUSED/INCONCLUSIVE for all five at the 400,000-state cap
   after ≈55 s each, so this is a state explosion, not a slow-but-finite search. C14_006 lands in the
   same place once its condition is fixed. They count as not repaired; the headline is unchanged.

7. **MODEL_ERROR — 1 case** (C20_016): request over the model context, see above.

**Takeaway.** The dominant cause is one documentation gap, not repair ability and not the evidence
format: 12 of the 32 failures (13 with C14_006) are the model normalising a JoI operator the repair
prompt never taught it, and every one of those is mechanically recoverable. The genuine reasoning
failures are groups 2–5 (13 cases: ×10 tick slips, multi-block structure, the phase pattern), and
groups 6–7 (6 cases) are verifier and context limits, not the model.

**Tried and rejected.** Three v6 prompts teaching `OP|` and the `not (C)` rearm were written and
checked (`repair_v6a/v6b/v6.md`). All three scored *below* v5 on the 14-case dev set (means 12.25,
11.75, 11.50 against v5's 12.75 over four runs each), with new failures in families the edits never
touched. Teaching the rule cost more than it bought at this model size, and the dev set has no
`{"any": [...]}` slot so it could only measure the cost. Since the gap was also found by looking at
these 68 outcomes, any prompt fixed against it is post-hoc tuning on the evaluation set. Decision:
keep v5, report 36/68 as it stands, and carry `OP|` as an analysed cause and future work.
See `DEV_NOTES_2026-09-16.md` for the per-variant table.

## Files

- `runs/e3_feedback_68_20260916/`: `preflight.json`, `evidence/` (68 payloads as sent),
  `responses/` (68 raw answers), `repair_summary.json`, `repair.log`, `evaluate.log`,
  `summary.json` (headline, by type, 68 rows), `timeout_recheck_exploratory.json`,
  `failure_cause_diagnostic.json`, `single_edit_split.json`.
- `explorer/eval/results/qwen3_5_9b_fp8_e3_feedback_v1_e3_feedback_68_20260916_{lineage,protocol,manifest,manifest_full,run}`.
- `explorer/candidates/qwen3_5-9b-fp8-e3-feedback-v1/`: the evaluated copy (67 repaired scripts,
  each with a `feedback_repair` provenance field; unrepaired cases identical to the E3 tag).

## Run log

Preflight 10:36 UTC+9. The first `repair` process died with the previous agent session before any
call was made (0 responses); it was relaunched detached and completed 68 calls in 397.7 s.
`evaluate` failed twice on file-exists checks (my shell redirect pre-created its `evaluate.log`,
then the aborted attempt's lineage file); partial files were removed and the stage rerun once,
cleanly. The headline comes from one complete preflight → repair → evaluate sequence.
While analysing, `repair_core.ROOT` was found to point one directory too high after the move out
of `dev/` (only `dev/run_repair.py` verification used it; the 68-run does not) and was fixed.
