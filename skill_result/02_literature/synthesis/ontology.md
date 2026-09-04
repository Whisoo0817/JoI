# Literature ontology for new OVLA

## Purpose and corpus boundary

This ontology organizes 13 targeted sources needed to position the already-approved `new_ovla` flow. It is a scoped advisor corpus, not a systematic-review claim of completeness.

## Axes

| Axis | Values used here | Why it matters |
| --- | --- | --- |
| Authoring input | natural language; structured UI; TAP/property; formal model | Separates intent acquisition from post-confirmation checking. |
| Reference object | prompt/request; examples; safety/liveness property; executable IR | Identifies what the implementation is checked against. |
| Target artifact | TAP; IoT/AIoT program; platform app; transition system | Prevents conflating TAP verification with arbitrary host-language code checking. |
| Temporal expressiveness | instantaneous TAP; latency/timers; branches/sequence/parallelism | Locates new OVLA's reactive-temporal scope. |
| Verification relation | generation accuracy; property satisfaction; repair; observational equality | States the semantic question actually answered. |
| Search scope | sampled/replayed; explicit reachable states; bounded symbolic search | Forces boundedness language. |
| Human role | request author; property author; feedback provider; IR confirmer | Defines the confirmation boundary without claiming intent correctness. |
| Evidence | user study; market corpus; benchmark; formal argument; implementation test | Keeps novelty evidence distinct from empirical validation. |

## Six strands

1. **LLM–IoT generation:** ChatIoT, AutoIOT, and GPIoT establish that LLM-assisted IoT program generation and benchmarks already exist.
2. **Reactive-temporal IoT:** Practical TAP and TAPInspector establish usable rule abstractions and verification models with latency/concurrency.
3. **Verification/equivalence:** IoTSan and AutoTap establish formal analysis, model checking, synthesis, and repair for IoT automation.
4. **Executable semantics:** timed automata and synchronous languages supply foundations for time, reaction, causality, and determinism.
5. **Reachability/boundedness:** SPIN and bounded model checking supply foundations for reachable-state exploration and finite-bound language.
6. **Confirmation boundary:** AwareAuto and TAP debugging establish interactive authoring/feedback, while exposing why confirmation must not be equated with true intent.

## Position occupied by new OVLA

The planned system starts after a user has confirmed Timeline IR. That IR is both the executable behavioral reference and the source of the finite environment model. For fixed modeled inputs, deterministic IR execution and adapted generated-code execution produce normalized observable traces; the checker compares those traces over all reachable histories within declared finite domains and bounds.

This position is a combination/integration claim. The underlying elements—LLM generation, user interaction, timed semantics, deterministic reactive languages, model checking, bounded search, and IoT verification—must be credited as prior foundations.

