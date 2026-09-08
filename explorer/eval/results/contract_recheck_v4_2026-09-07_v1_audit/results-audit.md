# Existing-candidate recheck self-audit

## Audit E3-CONTRACT-RECHECK-V4-V1

- Bounded verdict: supports_exploratory_follow_up
- Assurance: exploratory; self-review.

On all 388 existing fresh-v4 candidate IDs, the current frozen 3200ms contract yields descriptive verification outcomes and agreement on jointly completed finite searches; symbolic certificates are counted separately.

Before: {"EQUIV-BOUNDED": 203, "REFUSED": 46, "INCONCLUSIVE": 1, "DIVERGE": 77, "GENERATION_ERROR": 59, "PREPARATION_ERROR": 2}
After: {"EQUIV-BOUNDED": 207, "REFUSED": 43, "INCONCLUSIVE": 1, "DIVERGE": 76, "GENERATION_ERROR": 59, "PREPARATION_ERROR": 2}

Jointly completed finite searches: 267; disagreements: 0. Symbolic certificates: 3, separate from that denominator.
All errors/refusals/incomplete outcomes retained. Existing candidate digests preserved; no new LLM call. Input policies and reference repairs changed along with the verifier.
No independent replication, causal ablation, holdout generalization, full-language formal proof or speedup is established.

Canonical support: results-audit.json. Detailed counts and transitions: ../contract_recheck_v4_2026-09-07_v1/metrics.json.

Next: Use these bounded descriptive counts with explicit model assumptions; address remaining input cap and map proof obligations/support boundaries to the manuscript. Stronger generalization requires independent evidence.
