# Execution Bridge

### B1

Claim IDs: C1. Decision gate ID: G1.

Inputs: cohort_snapshot.json, corpus_100.csv, original20 frozen interpretations and author adjudication. Preserve original20 and runtime sources unchanged. Work only on new artifacts in ../remaining72/.

Expected implementation entrypoint: agent-created case and IR modules with a repeatable local reference-replay command, to be documented in the output README.

Required outputs: per-case interpretation/assumptions/alternatives, pre-encoding freeze, operator compositions, IR or attempted encoding, histories/expected/actual actions, exact and tolerance results, limitations and aggregate summary. Account for all72 even if partial or unsupported. Preserve pre-correction artifacts for substantive oracle revisions.

Lineage: replication of prior E1 procedure with new cases and agent instead of author adjudication; technical retries retain failure history. Runtime cannot access expected traces. Fixture observations cannot compute policy outcomes. Re-runs must not overwrite immutable freezes or historical failures.

Audit checks: membership against snapshot, unchanged original20/runtime, source-policy fidelity and material assumptions, nonvacuous tests, actual runtime provenance, exact action/time comparison, bias and independence limitations. No manuscript success claims before results exist.
