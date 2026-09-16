# Results Audit

> WITHDRAWN FROM PAPER USE: confirmed-input lowering used a global member-name
> prefix lookup that corrupts skill identity. The historical counts and prior
> attribution below do not support model-performance claims. See
> `../E3_QWEN_FINAL_RESULT.md`. A corrected complete run is pending.

## Audit Summary

- Paper ID: joi-timer-regions-percom
- Identity version: 1
- Audit status: complete
- Assurance boundary: exploratory repository-local self-audit

## Audit E3-QWEN-COMPLETE-20260915

- Claim ID: E3-APPLICATION-CORRECTNESS
- Bounded verdict: supports_exploratory_follow_up
- Attained assurance class: exploratory
- Audited claim effect: strengthen
- Run-selection rule: all 388 frozen cases exactly once; no outcome exclusion

The completed run has 263 `EQUIV-FIXPOINT` (67.78%), 61 replay-confirmed
`DIVERGE` (15.72%), 61 `REFUSED` (15.72%), and 3 invalid candidates (0.77%).
Explorer issued a semantic decision for 324/388 cases (83.51%); within those
decided cases, 263/324 (81.17%) were equivalent. All 61 divergences replayed,
and all 263 positive decisions carried horizon-free closure evidence.

The 64 non-decisions comprise 57 candidate capability/device mismatches, three
candidate syntax/statement errors, one candidate arity error, two unbounded
observable-value refusals, and one unreviewed effectful-return refusal. The 61
divergences classify as 49 logic/argument, 10 device, and two service errors.

The result supports these exact exploratory descriptive counts only. It does
not support a confirmatory or population-general claim because predecessor
outcomes informed remediation and the task set is not unseen. A separate frozen
held-out run is the minimum next step for confirmatory evidence.
