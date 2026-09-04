# Literature-to-claim support map

| Planned claim/component | Literature role | Required manuscript treatment |
| --- | --- | --- |
| C1: behavioral verification target | ChatIoT, AutoIOT, GPIoT show generation is established; IoTSan, TAPInspector, AutoTap show IoT verification is established | Define the delta as reference-relative exact observable behavior within bounds, not “first LLM IoT generation” or “first IoT verification.” |
| C2: executable reference specification | AutoTap and TAPInspector clarify the difference between property satisfaction and complete behavior; AwareAuto clarifies interaction/confirmation precedent | State that confirmation selects the operational reference; never infer true intent from confirmation. |
| C3: determinism-enabling semantics | synchronous languages and timed automata provide foundations | Cite foundations and claim only the concrete semantics engineered for Timeline IR and its checking contract. |
| C4: reachable exploration | SPIN and bounded model checking provide method provenance | Say “all reachable histories within the declared finite model and bounds”; report completion, exhaustion, timeouts, and frontier. |
| C5: evaluation | generation benchmarks, market corpora, real deployments, and PerCom exemplars motivate breadth and systems evidence | Combine conformance, adequacy, equivalence effectiveness, and scalability; do not reuse predecessor results as new-system evidence. |

## Citation needs

| ID | Need | Candidate sources | Status |
| --- | --- | --- | --- |
| CN-01 | LLM-driven IoT authoring exists | ChatIoT, AutoIOT, GPIoT | verified metadata/primary records |
| CN-02 | TAP supports end-user automation but becomes difficult under interaction/complexity | Practical TAP, TAP debugging | verified |
| CN-03 | Existing IoT formal systems target safety/liveness properties or repair | IoTSan, TAPInspector, AutoTap | verified |
| CN-04 | Deterministic reactive execution has established semantic precedents | synchronous languages | verified |
| CN-05 | Formal time modeling precedent | timed automata | verified |
| CN-06 | Explicit and bounded model exploration precedent | SPIN, bounded model checking | verified |
| CN-07 | Human interaction can structure complex automation requests | AwareAuto | preprint; describe as such |

## Evidence boundary

These citations support motivation, positioning, and method provenance. They cannot support claims that the new OVLA implementation is correct, expressive, effective, or scalable; those remain blocked until Phase 4 experiments are executed and audited.

