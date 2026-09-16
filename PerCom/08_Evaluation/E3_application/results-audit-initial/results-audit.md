# Results Audit

> WITHDRAWN FROM PAPER USE: this run used the same faulty service-prefix
> postprocessor as the completed run. Counts below are historical records only;
> they must not be attributed to model performance.

## Audit Summary

- Paper ID: joi-timer-regions-percom
- Identity version: 1
- Audit status: complete
- Assurance boundary: repository-local exploratory self-audit; not confirmatory or independent

## Audit E3-QWEN-INITIAL-20260915

- Claim ID: E3-APPLICATION-CORRECTNESS
- Bounded verdict: inconclusive
- Attained assurance class: none
- Audited claim effect: inconclusive
- Run-selection rule: all 388 frozen protocol cases exactly once

The accounting is complete but generation is not: 208 cases reached
`EQUIV-FIXPOINT`, 27 reached replay-confirmed `DIVERGE`, 27 were statically
`REFUSED`, and 126 ended in `APIConnectionError` after the endpoint reset.
The 126 cases contain no model candidate and are neither semantic failures nor
eligible for omission from the denominator.

The strongest contrary evidence is the case-order confound caused by the
server interruption. Predecessor outcomes also informed contract remediation,
so the run is exploratory. The minimum corrective action is a lineage-recorded
technical retry of exactly the 126 failed generations after endpoint recovery,
followed by new preparation and full 388-case accounting. Counterexample
feedback is not included; its protocol has not been designed or frozen.
