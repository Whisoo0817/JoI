# Dense-replay adjudication protocol (pre-registered 2026-06-06, before full run)

Purpose: independently adjudicate the §8.2 deployment verdicts. The gate's
accept/reject is decided on boundary-synthesized scenarios; here the SAME
(gt_ir, accepted JoI) pairs are replayed under randomized dense scenarios
(domain-wide values, off-boundary times, many events, noise keys) and compared
with the same comparator. The oracle (IR-sim) is unchanged; only the input
distribution is independent of the synthesizer.

## Scope
- Generator: 9B paired run `experiments/stageB_382/20260604_220553__paired`
  (off arm = `20260528_170116__d886015`).
- PASS side: all 360 deployed pairs (349 off-pass + 11 repaired_ok), K=100.
- FAIL side: semantic rejects (per_row outcome=rejected, graded=fail), K=50,
  purpose = reproduce divergence under dense inputs (flag not a scenario
  artifact).
- Seed: 7 (deterministic; per-row rng keyed `seed:name`).

## Pre-registered exclusions (with reasons; decided BEFORE running)
1. `l2-exc` rejects (subset failures): fail-closed parser/simulator-subset
   rejections have no simulatable JoI — nothing to replay.
2. Read-modify-write keys are not dense-seeded (same exclusion as boundary
   seeding, paper §6.2): IR var-capture vs JoI device-read semantics
   legitimately differ there; seeding them manufactures divergence.
3. Per-key minimum dwell = max(IR cycle period, JoI tick period, 1s): inputs
   that flip faster than the sampling cadence are outside the observation
   model (§6.1, polling-period quantization) — allowing them measures the
   sampling abstraction, not bugs.
4. Truncation guard: traces hitting MAX_TRACE are compared on the
   fully-observed common prefix (same guard as l2_runtime).

## Disagreement adjudication (every dump is kept)
Classify each trace-mismatch into exactly one of:
- `genuine-miss`: the accepted JoI really diverges from the IR on a legal
  input → reported as a finding (boundary-targeting residual, §6.5).
- `artifact`: divergence caused by harness/observation-model edges (e.g.
  grouping at tolerance boundary). Each artifact class must be described and
  either fixed or added here with its reason; rows re-run after a fix.
- `sim-error`: exception in either simulator → reported as subset failure.
No silent drops: counts of all three classes are reported.

## Escalation
Any PASS row with ≥1 unresolved mismatch after adjudication → re-run K=500.

## Output
`paper/Final/evaluation/results/dense_replay.json` (+ pilot file).
