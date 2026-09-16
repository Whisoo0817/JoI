# E3 application — B1/B2/B5, H=None exploratory recheck

Run date: 2026-09-15. Candidate: fixed `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit` Gemma-v3 bytes. This is a complete exploratory recheck, not a fresh-generation confirmatory experiment.

## Outcome distribution

| Outcome | Count | All-request rate |
| --- | ---: | ---: |
| EQUIV-FIXPOINT | 246 | 63.40% |
| DIVERGE_CONFIRMED | 57 | 14.69% |
| REFUSED | 23 | 5.93% |
| GENERATION_ERROR | 61 | 15.72% |
| PREPARATION_ERROR | 1 | 0.26% |
| Total | 388 | 100.00% |

The verifier made a behavioral decision for 303/388 requests (78.09%). Conditional on the 304 candidates admitted by preparation, it decided 303 (99.67%); this conditional number must not replace the all-request rate.

## Integrity and semantics

- All 388 protocol IDs appear exactly once and candidate/source snapshot continuity passed.
- All 246 positives have `closed=true`, `bounded_horizon_ms=null`, `bounded_horizon_ticks=null`, and claim `EQUIV-FIXPOINT`.
- All 57 divergences contain at least one confirmed replay.
- No timeout, memory-limit, crash, harness error, incomplete closure, or unconfirmed replay occurred.
- Preparation selected 298 explicit finite-closure cases, five symbolic-value-flow cases, and one SMT case. The positives comprise 241 explicit-closure and five symbolic certificates; the SMT case refused during execution.
- Median/p95/max per-case process wall time among 304 attempts was 0.061/0.077/0.862 seconds. Observed peak RSS was 25.6/25.6/63.6 MiB (median/p95/max). These are conditional process measurements, not end-to-end generation latency.

## Scope

Timeline extraction was not evaluated: each confirmed `ir_gt` was injected. No LLM call occurred; the mapping/lowering outputs are fixed historical bytes. The current verifier used B1/B2/B5 selector binding and `H=None` without bounded fallback.

The 78.09% decision rate is neither code accuracy nor NL-intent accuracy. Equality is relative to the supplied confirmed Timeline and declared service/input model. The run has no independent H=None oracle and is self-reviewed.

Fresh confirmatory E3 remains blocked because the configured model endpoint is unavailable and the repository SSH tunnel cannot authenticate. A future fresh run requires a new pre-generation freeze and separate output path.
