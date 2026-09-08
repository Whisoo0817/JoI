# Refusal attribution audit

## Audit E3-V4-REFUSAL-TRIAGE

- Bounded verdict: internally_consistent_only
- Assurance: exploratory, self-review.

All 46 first refusal reasons were reproduced. Primary counts are generated-contract mismatch23, reference/catalog mismatch6, intentional unsupported14, input-model limit2, frontend extension candidate1. These are post-outcome diagnostic categories and not new benchmark verdicts. Secondary problems may overlap.

The C18_006 in-memory explicit-bool variant passed preparation and produced a replay-confirmed divergence at horizon0; the original candidate remains REFUSED. No production, dataset, catalog, candidate or raw result was modified.

Detailed case evidence: `explorer/eval/results/contract_fresh_v4_refusal_triage_2026-09-07_v1.json`. Explanation and next steps: `explorer/eval/REFUSAL_TRIAGE_V4.md`.

Next: review six reference/catalog mismatches, design BOOL any frontend normalization, and assess two domain limits without silently narrowing coverage.
