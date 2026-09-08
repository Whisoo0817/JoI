# Existing-candidate recheck self-audit

## Audit E3-CONTRACT-RECHECK-V4-V2

- Bounded verdict: supports_exploratory_follow_up
- Assurance: exploratory; self-review.

On all 388 existing fresh-v4 candidate IDs, the current frozen 3200ms contract yields descriptive verification outcomes and agreement on jointly completed finite searches; symbolic certificates are counted separately.

Before: {"EQUIV-BOUNDED": 207, "REFUSED": 43, "INCONCLUSIVE": 1, "DIVERGE": 76, "GENERATION_ERROR": 59, "PREPARATION_ERROR": 2}
After: {"EQUIV-BOUNDED": 208, "REFUSED": 43, "DIVERGE": 76, "GENERATION_ERROR": 59, "PREPARATION_ERROR": 2}

Jointly completed finite searches: 267; disagreements: 0. Symbolic certificates: 4, separate from that denominator.
All errors/refusals/incomplete outcomes retained. Existing candidate digests preserved; no new LLM call. Source/model/reference differences are recorded in protocols and metrics.
No independent replication, causal ablation, holdout generalization, full-language formal proof or speedup is established.

Canonical support: results-audit.json. Detailed counts and transitions: ../contract_recheck_v4_2026-09-07_v2/metrics.json.

Next: Use these bounded descriptive counts with explicit model assumptions; account for any remaining limits and map proof obligations/support boundaries to the manuscript. Stronger generalization requires independent evidence.
