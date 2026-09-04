# Experiment Tracker

The v3 bounded search-layer confirmatory run is complete. Broader E1–E4
system evidence remains in progress; development runs are kept separately.

| Run ID | Block ID | Gate ID | Purpose | Priority | Status | Owner | Dependency | Output artifact | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-E1-PLAN | E1 | G-E1 | Interpreter conformance confirmatory pack | must-run | planned | unassigned research team | formal artifacts frozen | `results/E1/conformance_summary.json` | pilot and snapshots required first |
| R-E2-PLAN | E2 | G-E2 | Expressive-adequacy annotation pack | must-run | planned | unassigned annotation team | E1 contract | `results/E2/adequacy_summary.json` | external corpus/provenance required |
| R-E3-PLAN | E3 | G-E3 | IR–code equivalence confirmatory pack | must-run | planned | unassigned research team | E1, E2 | `results/E3/equivalence_summary.json` | freeze gold labels before checker output |
| R-E4-PLAN | E4 | G-E4 | Explorer capacity/frontier pack | must-run | planned | unassigned systems evaluator | E1, E2 | `results/E4/scalability_summary.json` | freeze factor grid and resource caps |
| R-E1-DEV-LEGACY | E1 | G-E1 | Common-subset differential conformance against retained SenSys simulators | must-run | analyzed | implementation team | none | `results/E1/legacy-conformance-dev/` | exploratory 6/6 pass; targets, grounding, reentry, cancellation, cron, missing values, timer ties, and merge laws remain |
| R-E3-DEV-ORACLE | E3 | G-E3 | Bounded tick-oracle and A/B harness development | must-run | analyzed | implementation team | frozen outcome contract | `explorer/exact_tick.py`, `ab-evaluation-protocol.md` | exploratory only; manifest H=8 run: 356/388 complete, A=0, B=0, R=88.5%, max=81.14 ms; not final evidence |
| R-E3-GEMMA-V1 | E3 | G-E3 | First frozen Gemma held-out generation attempt | must-run | analyzed | implementation team | generation snapshot v1 | `snapshots/E3_heldout_input_manifest_h32.json` | 388/388 generation errors from fenced JSON; retained as failed predecessor |
| R-E3-GEMMA-V2 | E3 | G-E3 | Frozen Gemma held-out A/B candidate run | must-run | analyzed | implementation team | v1 failure, response-normalization regression, frozen v2 manifests | `results/E3/heldout-gemma-v2-h32-retry1/` | 309 READY pairs all completed; 228 EQUIV/81 DIVERGE, A=0, B=0, R=74.1%, max=268.14 ms; awaits E1/domain/audit gates |
| R-E3-V2-POSTAUDIT | E3 | G-E3 | Outcome-visible regression after value-flow domain repair | must-run | analyzed | implementation team | v2 static domain audit | `results/E3/v2-postaudit-regression-h32/` | development only; 309/309 READY agree, A=0, B=0; confirms repair before new holdout |
| R-E3-GEMMA-V3-DOMAIN | E3 | G-E3 | Static audit of frozen v3 behavior-relevant input keys | must-run | analyzed | implementation team | frozen v3 input manifest | `results/E3/heldout-gemma-v3-domain-audit/` | 311/311 READY pass; does not use runner axes, but shares parsing/grounding/compilation |
| R-E3-GEMMA-V3 | E3 | G-E3 | Frozen post-repair Gemma held-out bounded differential evaluation | must-run | analyzed | implementation team | clean evaluator commit, frozen v3 generation/input manifests, v3 domain audit | `results/E3/heldout-gemma-v3-h32/` | 311/311 READY complete; 231 EQUIV/80 DIVERGE, A=0, B=0, R=73.45%, p95=52.09 ms, max=280.12 ms; supports scoped H=32 search-layer claim |
