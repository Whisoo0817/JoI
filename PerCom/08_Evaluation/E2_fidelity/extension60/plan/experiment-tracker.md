# Experiment Tracker

| Run ID | Block | Gate ID | Purpose | Priority | Status | Owner | Output | Cost | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E2-ext48 | B1 | G1 | New faults | must-run | analyzed | root | ../runs/e1_new48.jsonl | parallel hours | Static freeze done; awaiting runner preflight |
| E2-ext12 | B2 | G2 | New generated candidates | must-run | analyzed | root | ../runs/llm_new12.jsonl | minutes | Static selection and histories frozen |

## Updates
- Prepared before new engine evaluations. Old140 current-version regression running separately.

- Both batches launched after runtime and input freeze. All old140 current-version Explorer verdicts unchanged. InitialLLM12 contains one input-conversion harness error (weeklycron start None); preserve run and technicalretry the same candidate with explicit clock-anchor correction. New48 references use sufficient-counterexample short-circuit; old controls and B5 alternative-assignment preflight passed.

- Complete: B1 48/48, B2 12/12 with C15 technical retry retained, baseline140 current-version replay unchanged. Final200:64EQUIV/119DIVERGE/9REFUSED/8TIMEOUT;183issued verdicts consistent with specifiedreferencechecks. No universal correctness or external independentverification claim.
