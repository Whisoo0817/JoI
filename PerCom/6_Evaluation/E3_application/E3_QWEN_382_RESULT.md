# E3 Qwen3.5-9B: 382-case evaluation

Model: `Hyper-AI/Qwen3.5-9B-fp8`. Candidate tag:
`qwen3_5-9b-fp8-e3-prefix-fixed-v2`. Explorer uses `H=None`.

| Outcome | Count | Of 382 |
| --- | ---: | ---: |
| EQUIV-FIXPOINT | 307 | 80.37% |
| DIVERGE_CONFIRMED | 70 | 18.32% |
| REFUSED | 3 | 0.79% |
| UNKNOWN | 2 | 0.52% |
| Total | 382 | 100.00% |

Decision coverage: 377/382 (98.69%). Generation errors, capability errors,
syntax preparation errors, and arity errors: zero in this run. All 70
divergences have confirmed replay. Source and candidate hash continuity passed
during evaluation. These are model-relative results, not independent proof of
real-device behavior; the divergence causes have not been individually audited.

## Candidate accounting

325 candidates were reused byte-for-byte with matching current row payloads.
57 were regenerated: 56 prefix-affected cases plus C05_015, whose confirmed
mode is now `drying`. The earlier estimate of 58 double-counted C26_006,
which is excluded with the other timeout cases. All 57 new candidates have
raw lowering traces. Their outcomes are 44 EQUIV, 11 DIVERGE, and 2 UNKNOWN.
C05_015 is EQUIV-FIXPOINT.

The original 388-row dataset is preserved. All six timeout cases C26_001–006
are outside the current E3 scope. No feedback-loop results are included.
The lowering prompts were not changed for this partial regeneration.

## Remaining non-decisions

- C01_015: GenerateImage BINARY return assignment is outside the reviewed service model.
- C03_003: unbounded target-temperature arithmetic requires an explicit domain.
- C11_006: the large illuminance domain cannot be automatically enumerated exactly.
- C11_001 and C11_005: SMT query timeout under the existing 1-second per-query limit.

Generation took about 60 seconds; complete external evaluation took 30.56
seconds. UNKNOWN was retained without changing limits or retrying searches.
This mixed-provenance evaluation is exploratory; it is not a fresh 382-case
generation or a confirmatory replication.

## Artifacts

All paths below are relative to the repository root, under `explorer/eval/results/`:

- `e3_prefix_fixed_382_20260915_lineage.json`: exact reuse/regeneration/exclusion IDs and old byte hashes.
- `e3_prefix_fixed_382_20260915_candidates.json`: all 382 candidate hashes and payload checks.
- `e3_prefix_fixed_382_20260915_protocol.json`: evaluation policy and source snapshot, created after candidate generation and before evaluation.
- `e3_prefix_fixed_382_20260915_manifest.json`: prepared cases.
- `e3_prefix_fixed_382_20260915_run/summary.json`: aggregate results and continuity checks.
- `e3_prefix_fixed_382_20260915_run/case_outcomes.jsonl`: per-case decisions, certificates and replays.
