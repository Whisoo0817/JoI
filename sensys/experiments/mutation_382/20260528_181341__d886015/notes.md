# mutation_382 — 2026-05-28 18:13 (git d886015, dataset.csv 382 rows)

Rejection-power mutation test. Seeds = stageB_382 verifier-passing JoI (356 valid
seeds, harvest re-verifies each clean vs gt_ir). 5 parallel groups (C04 merged
into C03). LLM-free (simulation). 10 operators.

## Result
- TOTAL: 1424/1438 genuine mutants caught = 99.03%
- valid_seeds = 356
- Per-operator: ALL 100% except comparator 88/102 = 86.3%.
  arg_numeric 100, arith_op 100, assign_init 100, call_add 100, call_drop 100,
  cmp_direction 100, enum_flip 100, guard_polarity 100, tick_scale 100.

## Survivors (14) — ALL by-design, single class
- 14 survivors = comparator `>=`->`>` on C20 sustained tick-counter (`hold_ticks > N`
  instead of `>= N`). Fires exactly 1 tick (0.1s) late -> within max(500ms,10%)
  tolerance -> NOT flagged. This is the documented sub-tolerance timing class,
  a tolerance artifact, NOT a sensor-value comparison miss and NOT a verifier
  insensitivity. (13 on C20 + 1 on C23, both the same sustained-counter class.
  vs prior 99.3%/9-surv: this run's Stage-B seeds had more C20/C23 sustain blocks
  -> more comparator sites -> seed variance, same fault class.)

## Framing
- This is the RQ3 hero evidence (verifier믿을만한가): prompt-INDEPENDENT,
  injected-bug ground truth (non-circular). Report as "mutation-adequate coverage
  over the declared IR fault model", never "bounded completeness".
