# PerCom paper pattern map

## Status of the observations

The table below reports tendencies observed in the seven-paper purposive sample. They are not official PerCom rules and do not establish why any paper was accepted.

| Observed tendency | Sample evidence | Advice for new OVLA |
| --- | --- | --- |
| Pervasive context appears early and concretely | homes, edge clusters, cameras, IoT messaging, and constrained devices are introduced as the operating context | Open with failure consequences and verification needs in reactive-temporal smart-home automation, not generic code equivalence. |
| A concrete measurement/example motivates the mechanism | ScaleWave trace study; real-home and real-video observations | Use a compact old-OVLA failure example only as motivation; do not count legacy numbers as new evidence. |
| Contribution is embodied in a runnable artifact | every sampled systems paper implements the proposed mechanism | Make interpreter, adapter, Explorer, comparator, and counterexample output visibly one artifact. |
| Evaluation combines realism and controlled coverage | real datasets/deployments plus synthetic or controlled conditions | Pair an independently sourced automation corpus with property-based/exhaustive semantic cases and a factorial state-space generator. |
| Baselines/controls match the claimed question | platform baselines, labeling alternatives, system variants, ablations | For OVLA's effectiveness, use positive equivalence controls and negative faults; for semantics, use an independent oracle. Do not invent a performance race with unrelated verifiers. |
| Multiple metrics and failure outcomes are retained | accuracy/task metrics plus latency/resource/tails; N/A, limitations, high-load tests | Report false accepts, false rejects, coverage, timeout/frontier, counterexample length, latency, and peak memory. |
| Mechanism isolation is common when causal attribution matters | component ablations in SenseLess, OCTOPINF, DiTMoS | Restrict ablation to active semantic/checker mechanisms; lowering or second-backend comparisons remain optional and inactive. |
| Deployment/resource realism strengthens systems claims | homes, outdoor sites, heterogeneous edge hardware, MCU runs | An edge-hardware subcondition can strengthen E4, but must not be worded as physical-device correctness. |
| Limitations are explicit | cross-home, labeling, hardware, workload, and model limitations | Give finite-model, domain, backend, observation, and confirmation limitations their own space. |

## Page-budget implication

With nine technical pages, the paper should prioritize one system/method contribution and four decisive evidence blocks. Related-work breadth, formal proof detail, and large taxonomies should move to compact tables or an artifact; optional extensions should not compete for the main narrative.

