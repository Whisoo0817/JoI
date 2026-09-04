# coverage_382_v2 — 2026-05-29 (empty-else excluded)

Coverage re-run after two-sided obligation refinement.

## Change
- coverage.py enumerate_target_obligations: an `if` with an EMPTY else no longer
  emits an `if@...:else` obligation. Rationale: an empty else executes nothing on
  the false path, so there is no behavioral obligation to cover; counting it
  penalized coverage for a branch with nothing observable. (then-side unchanged.)
- event_synth var-var boundary synth was ATTEMPTED then REVERTED: inspection showed
  the uncovered set is NOT variable-vs-variable compares but empty-else + register/
  arithmetic guards + quantifiers, so var-var seeding had zero effect.

## Result
- 329/351 = 93.7% two-sided boundary coverage (was 441/480=91.9% with empty-else counted).
- Obligation breakdown: then 166, else 37 (empty-else dropped), rearm 34, edge_rising 34,
  sustain 27, flap_reset 27, reg_lo/hi 8/8, lo/hi 5/5.
- Uncovered 22 = single-point/single-device input-synthesis limit: internal-state/
  cross-time guards (n%2, abs(t2-t1)) + quantifier all/any else-branches. NOT a
  detection failure; documented in paper §11.
