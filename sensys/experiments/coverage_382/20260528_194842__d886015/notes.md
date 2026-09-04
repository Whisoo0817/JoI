# coverage_382 — 2026-05-28 19:48 (git d886015, dataset.csv 382 rows)

Two-sided IR-FSM transition-obligation coverage. run_coverage_report.py, LLM-free.
480 obligations = sum over 382 IRs of obligation counts (if->then+else,
sustain->met+break, rearm, edge, expr->lo+hi).

## Result
- spec-side: 441/480 = 91.9%  (identical to prior 91.9%)
- 39 uncovered = else-branch scenarios that produced no distinguishing events
  because the guard is not synthesizable: var-comparison / quantifier (all/any) /
  arithmetic-in-guard / non-numeric domain.
- These are INPUT-SYNTHESIS limits (we can't auto-generate a discriminating
  trigger), NOT verifier detection failures. Each tagged with reason.

## Framing
- Coverage criterion bounds the mutation claim: "mutation-adequate coverage over
  the declared IR fault model". The 39 uncovered = honest ceiling (covered != proven).
- Pairs with mutation 99.03% as RQ3 evidence.
