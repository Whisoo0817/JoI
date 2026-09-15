# E3 application experiment plan

## Context

- Claim: given a confirmed Timeline and binding plan, the verifier can either certify generated JoI behavior, return a replay-confirmed mismatch, or retain an explicit non-decision/failure.
- Evaluation target: all 388 rows in `dataset.csv` having `category_v2` and `ir_gt`.
- Current/requested evidence class: exploratory. The reused Gemma-v3 candidates are outcome-visible and familiar-task artifacts, so this run cannot be promoted to confirmatory evidence.
- Predecessor: the bounded `H=32` run is retained as historical development evidence and is not pooled with this run.

## Frozen decisions

- Timeline extractor grammar: not exercised. The confirmed `ir_gt` is injected directly.
- Candidate mapping/lowering: no LLM call in this run; reuse the 388 candidate bytes hashed by `E3_heldout_input_manifest_v3_h32.json`.
- Binding: current B1/B2/B5 policy, with `selector_binding=True`; no result-dependent rebinding.
- Verification: `horizon_ms=None`, automatic exact-closure/relational/symbolic/SMT dispatch, no bounded fallback.
- `EQUIV-FIXPOINT` requires a closed graph and both bounded-horizon fields to be null.
- `DIVERGE_CONFIRMED` requires at least one successfully replayed witness.
- Every selected case remains in the denominator exactly once. Refusal, generation/preparation error, timeout, memory limit, crash, replay failure, and incomplete closure are retained separately.
- No scientific retry is allowed in this run. A technical retry must use a new run ID and retain this predecessor.

## Non-vacuity preflight

- Pass: the selected bytes contain valid candidates and generation failures, and predecessor results contain both equivalent and divergent behaviors.
- Pass: all 388 candidate hashes match the frozen predecessor manifest.
- Pass: neither a refusal nor a missing result is counted as equivalence.
- Exploratory-only gate: candidates and tasks have already been inspected in prior runs.

## Block E3-B1

- Purpose: apply the current B1–B5, horizon-free verifier to the complete fixed candidate population.
- Metrics: unconditional outcome distribution and completion rate; verification-method distribution; conditional runtime/RSS summaries.
- Success criterion: artifact integrity and complete accounting. Scientific success is not defined as a favorable EQUIV rate.
- Failure interpretation: unclosed/resource-limited cases narrow applicability; a non-replayed divergence is inconclusive; an invalid positive blocks use of the EQUIV count.
- Required outputs: protocol, preparation manifest, JSONL outcomes, summary, result audit, hashes.

## Next block

A fresh-generation confirmatory E3 requires restoration of the frozen Gemma endpoint, a new pre-generation manifest, and a new candidate tag. It must not overwrite or pool this run.
