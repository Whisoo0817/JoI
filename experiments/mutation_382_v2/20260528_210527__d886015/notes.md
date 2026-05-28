# mutation_382_v2 — 2026-05-28 (git d886015 + dirty: break_drop op & sim caps)

Re-run after closing the construct x operator matrix gap. Seeds = stageB_382
verifier-passing JoI (356 valid). 11 operators (10 + break_drop). 5 parallel groups.

## What changed vs mutation_382
- ADDED op_break_drop: deletes a standalone `break`. In the sustain idiom
  (`if (hold_ticks>=N){act;break}`) this turns a one-shot into a per-tick re-fire
  = extra_call divergence (a fire-COUNT fault, NOT sub-tolerance timing).
- EXCLUDED op_wait_drop: in-scope but 25/25 mutants equivalent on our scenarios
  (event_synth satisfies the gate condition at t=0, so wait-existence is
  unobservable; the wait CONDITION is already covered by guard/comparator/enum).
  Documented in _OUT_OF_SCOPE_OPERATORS.
- FIXED joi_simulator runaway: the sustain `hold_ticks++` marks every tick as
  progress so the idle early-stop never fires; only `break` terminates. A
  break-dropped (or unsatisfiable-threshold) mutant therefore ticked to MAX_T_MS
  (7d/100ms = 6M iters) = a 35-min hang. Added MAX_TICKS=300_000 and MAX_RAW=20_000
  caps (far above any real scenario ~18k ticks); a runaway's partial trace has
  already diverged, so verdicts are unchanged — only cost is bounded.

## Result
- TOTAL: 1461/1475 = 99.05%  (valid_seeds=356, 11 operators)
- break_drop: 37/37 = 100% (kind=extra_call). All other ops 100% EXCEPT
  comparator 88/102 = 86.3%.
- Survivors: 14, UNCHANGED class = comparator `>=`->`>` on sustain tick-counter
  (13 C20 + 1 C23), sub-tolerance 1-tick (within max(500ms,10%)) = by-design.

## Why this matters (reviewer-facing)
- Closes the construct x operator matrix: every IR construct now has >=1 operator
  (break terminator was the last gap). break_drop hits the SAME sustain construct
  the survivors live in, but with a NON-timing fault -> 100% caught -> rebuts
  "the sustain construct is a verifier blind spot" (only the 1-tick comparator
  boundary is, and that is a tolerance artifact, shown by the sweep).
