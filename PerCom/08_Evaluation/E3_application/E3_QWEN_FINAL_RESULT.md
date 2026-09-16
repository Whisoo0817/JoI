# E3 Qwen3.5-9B result — withdrawn from paper use

Current corrected 382-case evaluation: [E3_QWEN_382_RESULT.md](E3_QWEN_382_RESULT.md).
The withdrawal below applies to the historical 388-case run only.

The run below is an invalid pipeline run, not a publishable model-performance
result. The lowering postprocessor selected skills using a global member-name
lookup instead of the confirmed IR/binding. It can turn correct `Temperature`,
`Humidity`, `CurrentPosition`, `Voltage`, and `Power` outputs into the wrong
skill. The 57 capability failures match these collisions; historical raw model
outputs were not retained, so individual model attribution is unproven.

All aggregate rates below are retained only as historical execution records.
Do not use them in the paper, subtract failures from the denominator, or turn
them into EQUIV without evaluation. Corrected model-performance counts require
a complete run with the fixed postprocessor and retained raw outputs.

Model: `Hyper-AI/Qwen3.5-9B-fp8`
Cases: 388 confirmed `ir_gt + binding_gt` pairs
Verification: horizon-free Explorer (`H=None`)
Evidence class: exploratory

| Outcome | Count | All cases |
| --- | ---: | ---: |
| EQUIV-FIXPOINT | 263 | 67.78% |
| DIVERGE_CONFIRMED | 61 | 15.72% |
| REFUSED | 61 | 15.72% |
| Invalid candidate | 3 | 0.77% |
| Total | 388 | 100.00% |

Explorer made a semantic decision for 324/388 cases (83.51%). Among decided
cases, 263/324 (81.17%) were equivalent. Every positive result has closed-state
evidence and every divergence has a successful replay.

## Non-decisions

| Cause | Count |
| --- | ---: |
| Capability mismatch contaminated by prefix postprocessing | 57 |
| Candidate syntax or invalid statement | 3 |
| Candidate argument arity | 1 |
| Explorer unbounded observable value | 2 |
| Explorer unreviewed effectful return | 1 |

## Confirmed divergence categories

| Category | Count |
| --- | ---: |
| Logic/argument | 49 |
| Device | 10 |
| Service | 2 |

The model endpoint was interrupted after 262 artifacts, producing 126 recorded
connection failures. Those failed artifacts and the initial manifest were
retained, and exactly those cases were continued after the same model endpoint
recovered. The completed candidate manifest contains all 388 matching payloads.

This run is not confirmatory: predecessor outcomes informed the general
IR--JoI contract remediation. A confirmatory claim requires a separately frozen,
previously unseen case set with no outcome-informed changes.
