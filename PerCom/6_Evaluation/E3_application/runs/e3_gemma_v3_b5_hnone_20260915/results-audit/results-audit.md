# E3 result audit

## Audit E3-GEMMA-V3-B5-HNONE-20260915

- Bounded verdict: supports_exploratory_follow_up
- Assurance: exploratory; self-review.

The frozen run accounted for all 388 selected cases. It produced 246 closed horizon-free equivalence certificates, 57 replay-confirmed divergences, 23 refusals, 61 generation errors, and one preparation error. All positive and divergence invariants passed the post-run audit.

This supports using the run as a complete exploratory application result under the declared B1/B2/B5 and H=None contract. It does not support code-accuracy, natural-language accuracy, independent-verification, or confirmatory claims because the familiar candidate bytes and their predecessor outcomes were already visible and there is no independent unbounded oracle.

The minimum corrective action is a separately frozen fresh-generation run after the Gemma endpoint is restored, followed by independent semantic review. The present artifacts must not be overwritten or pooled into that future run.
