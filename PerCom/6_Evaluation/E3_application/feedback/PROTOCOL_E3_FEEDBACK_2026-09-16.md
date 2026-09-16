# E3 feedback run — protocol (frozen 2026-09-16)

Machine-readable copy: `protocol_e3_feedback_v1.json` (prompt hash, model settings, the 68 case
IDs with candidate hashes, baseline hashes, evaluator policy). This page explains it.

## Question

Given a confirmed Timeline IR, its binding, a generated JoI that the Explorer rejected with a
replay-confirmed counterexample, and that counterexample: after **one** repair call, how many of
the 68 E3 divergences become EQUIV-FIXPOINT under the unchanged E3 evaluator?

There is no comparison arm. The claim stays "the counterexample is directly usable for repair";
nothing about repair rates without counterexamples (author decision 2026-09-16).

## Population and baseline

The 68 `DIVERGE_CONFIRMED` cases of the E3 final run (`e3_single_binding_382_20260915_run`,
309/68/3/2). Candidate bytes are pinned by SHA-256 in the protocol. The baseline result and the
lowering prompts are not changed.

## Input to the model (per case, fresh context, one call)

- System prompt: `prompts/repair.md` (hash pinned). Contains the repair instruction, the JoI
  grammar/execution contract, a repair shape checklist and seven worked examples on scenarios that
  are not in the dataset.
- User payload (JSON): confirmed IR, binding slots, device inventory, the current candidate with
  numbered lines, and the counterexample: F1 input history up to the first replay-confirmed
  mismatch, F2 the IR and JoI actions at that instant, plus `ir_timing_facts` (durations in the IR
  converted to ms and 100 ms ticks; deterministic, read off the IR, no advice).
- The model never sees verifier internals, gold code, dataset text, or other cases.

## Model settings

`Hyper-AI/Qwen3.5-9B-fp8` via vLLM, thinking **off**, temperature **0**, top_p 0.95, top_k 20,
seed 0, max_tokens 4096. Chosen on the dev set (`DEV_NOTES_2026-09-16.md`): thinking on exhausted
8k and 16k budgets on sustained-condition cases; sampling at 0.6 varied 9–12/14 across seeds;
greedy gave 13/14 at ~330 completion tokens.

## Stopping and accounting

Exactly one model call per case. Terminal statuses: `REVISED` (goes to the evaluator),
`NO_CHANGE`, `INVALID_OUTPUT`, `MODEL_ERROR` — the last three count as not repaired. No retry,
resampling, or second round. The denominator is 68 in every table.

## Verification of the revision

`explorer.eval.frozen_contract` exactly as in the E3 final run: `--unbounded` (H=None), Explorer
only, B5 selector assignments, caps 200000 states / 500000 transitions / 100000 input
combinations / 20 s × assignments / 768 MiB. `preflight` refuses to run unless the source
snapshot equals the E3 final protocol's. Revised candidates are written into a new candidate tag
(`qwen3_5-9b-fp8-e3-feedback-v1`, a byte copy of the 382 originals with the revised 68 replaced),
and only the 68 are evaluated. Accepted = `EQUIV-FIXPOINT`; everything else stays a failure.

## Report

repaired/68; by divergence type (`e3_68_divergence_types.json`); every terminal status; prompt
and completion tokens and wall time; raw responses under `runs/<run-id>/responses/`. Evaluator
artifacts under `explorer/eval/results/<tag>_<run-id>_{lineage,protocol,manifest,run}`.

## Commands

```
~/temp/bin/python joi/self_feedback/run_e3_feedback.py preflight --run-id e3_feedback_68_YYYYMMDD
~/temp/bin/python joi/self_feedback/run_e3_feedback.py repair    --run-id e3_feedback_68_YYYYMMDD
~/temp/bin/python joi/self_feedback/run_e3_feedback.py evaluate  --run-id e3_feedback_68_YYYYMMDD
```

## Limitations to carry into the write-up

Single model and a single greedy decode; prompt selection on a separate dev set is prompt
development and is reported as such; binding/selector errors cannot appear (they verify EQUIV
under B1/B5); the 68 candidates were inspected in the 2026-09-15 audit, the prompt was not tuned
on them.
