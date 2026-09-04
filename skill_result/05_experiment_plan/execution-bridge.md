# Execution Bridge

This is a future hand-off specification. It does not authorize or record experiment execution.

## Block Hand-off

### E1

- **Claim IDs:** EC-01
- **Decision gate ID:** G-E1
- **Current/requested evidence:** exploratory / confirmatory
- **Inputs required:** frozen grammar/semantics, generated-case schema, boundary suite, small finite models, recorded seeds.
- **Declared input snapshot paths:** `05_experiment_plan/snapshots/E1_inputs_manifest.json`
- **Declared evaluator snapshot paths:** `05_experiment_plan/snapshots/E1_oracle_manifest.json`
- **Expected implementation entrypoint:** manual hand-off pending implementation; record exact argv before execution.
- **Expected command or notebook:** no command is authorized now; future runner must be noninteractive and manifest-driven.
- **Output artifacts to produce:** `results/E1/conformance_summary.json`, `results/E1/case_outcomes.jsonl`.
- **Auditor-facing checks:** semantic-version digests, oracle independence, stratum coverage, seeded-fault detection, complete outcomes, retry linkage.
- **Intended lineage relation:** baseline for the frozen semantics; later reruns are replication or technical_retry.
- **Parent run ID or rationale:** initial baseline has no parent; record `R-E1-*` as parent for retries.
- **Hidden information unavailable to the evaluated system:** oracle outputs, expected boundary results, seeded-fault identity, aggregate discrepancy rate.
- **Failure, skip, null, timeout, and retry states to retain:** all states plus invalid, crash, uniqueness violation, and incomplete generation with reason.
- **Idempotency and restart requirements:** clean process/state per shard; immutable snapshots; retries create new linked run IDs and never overwrite originals.
- **Known blockers:** production interpreter and independent evaluator are not yet implemented/frozen.

### E2

- **Claim IDs:** EC-02
- **Decision gate ID:** G-E2
- **Current/requested evidence:** exploratory / confirmatory
- **Inputs required:** frozen taxonomy/manual, complete eligible corpus lists, external provenance, negative controls, annotator assignments.
- **Declared input snapshot paths:** `05_experiment_plan/snapshots/E2_corpus_manifest.json`, `05_experiment_plan/snapshots/E2_taxonomy.md`.
- **Declared evaluator snapshot paths:** `05_experiment_plan/snapshots/E2_annotation_manual.md`.
- **Expected implementation entrypoint:** manual blinded annotation workflow with immutable case IDs and separate adjudication import.
- **Expected command or notebook:** no command is authorized now; future aggregation script must consume untouched independent label files.
- **Output artifacts to produce:** `results/E2/adequacy_summary.json`, `results/E2/case_annotations.csv`.
- **Auditor-facing checks:** inclusion/exclusion reconciliation, provenance, blinded independent labels, agreement, adjudication, denominators, unsupported controls.
- **Intended lineage relation:** baseline annotation of the frozen core; reannotation is replication or technical_retry after a version change.
- **Parent run ID or rationale:** initial baseline has no parent; any corrected import links to its original annotation run.
- **Hidden information unavailable to the evaluated system:** aggregate desired coverage, other annotator labels, eventual claim language, post-hoc exclusion requests.
- **Failure, skip, null, timeout, and retry states to retain:** missing source, invalid case, disagreement, withdrawal, skip, null label, import failure, and reannotation.
- **Idempotency and restart requirements:** immutable case list; append-only labels/adjudication; aggregation reproducible from snapshots.
- **Known blockers:** external corpus and annotator/adjudicator roles have not been fixed.

### E3

- **Claim IDs:** EC-01
- **Decision gate ID:** G-E3
- **Current/requested evidence:** exploratory / confirmatory
- **Inputs required:** frozen positive/negative gold pairs, finite models/bounds, adapter/normalizer, fault provenance, labels, seeds, timeout.
- **Declared input snapshot paths:** `05_experiment_plan/snapshots/E3_gold_manifest.json`.
- **Declared evaluator snapshot paths:** `05_experiment_plan/snapshots/E3_checker_adapter_manifest.json`, `05_experiment_plan/snapshots/E3_gold_labels.json`.
- **Expected implementation entrypoint:** manual hand-off pending checker runner; record exact isolated-run command before execution.
- **Expected command or notebook:** no command is authorized now; future runner must reset/snapshot both executions and accept only manifest IDs.
- **Output artifacts to produce:** `results/E3/equivalence_summary.json`, `results/E3/pair_outcomes.jsonl`, `results/E3/counterexamples/`.
- **Auditor-facing checks:** split/provenance, label freeze, input identity, adapter noninterference, exact completion, false accepts/rejects, CI, error/timeout separation.
- **Intended lineage relation:** baseline gold-set evaluation; dense replay is an explicitly labeled alternative_hypothesis/sensitivity cross-check.
- **Parent run ID or rationale:** initial baseline has no parent; technical retries must reference the failed parent pair/run.
- **Hidden information unavailable to the evaluated system:** gold label, expected IR actions, mutant/fault class, counterexample target, comparator outcome.
- **Failure, skip, null, timeout, and retry states to retain:** TP/TN, false accept/reject, invalid, adapter error, crash, null, skip, timeout, incomplete frontier, retry.
- **Idempotency and restart requirements:** fresh isolated state per pair/history; deterministic manifests; append-only attempts; raw traces immutable.
- **Known blockers:** E1 must pass and the E2 scope/gold construction must be frozen.

### E4

- **Claim IDs:** EC-02
- **Decision gate ID:** G-E4
- **Current/requested evidence:** exploratory / confirmatory
- **Inputs required:** frozen factorial grid, real-workload anchors, generator, hardware/container manifest, search modes, timeout and memory caps.
- **Declared input snapshot paths:** `05_experiment_plan/snapshots/E4_factor_grid.json`, `05_experiment_plan/snapshots/E4_workload_manifest.json`.
- **Declared evaluator snapshot paths:** `05_experiment_plan/snapshots/E4_environment_manifest.json`.
- **Expected implementation entrypoint:** manual hand-off pending reproducible Explorer benchmark runner and resource monitor.
- **Expected command or notebook:** no command is authorized now; future command must run one manifest cell/seed and emit machine-readable completion state.
- **Output artifacts to produce:** `results/E4/scalability_summary.json`, `results/E4/run_outcomes.jsonl`, `results/E4/raw_metrics/`.
- **Auditor-facing checks:** grid completeness, randomized order, repetitions, process isolation, raw wall/RSS/frontier metrics, completion classification, real-anchor provenance.
- **Intended lineage relation:** parameter_variation baseline; repeated seeds are replication and diagnosed anomalies are sensitivity or technical_retry.
- **Parent run ID or rationale:** each grid baseline has no parent; retry/sensitivity attempts reference the original cell/seed.
- **Hidden information unavailable to the evaluated system:** aggregate frontier, desired capacity boundary, post-run cell-selection decisions.
- **Failure, skip, null, timeout, and retry states to retain:** fixpoint/horizon complete, resource incomplete, timeout, OOM, adapter error, invalid, crash, skip, null, retry.
- **Idempotency and restart requirements:** one isolated process per cell/seed; fixed inputs; no overwrite; raw metrics and logs content-addressed.
- **Known blockers:** E1 semantic version and E2 real-workload anchors must be frozen; benchmark runner does not yet exist.
