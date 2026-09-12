# Evaluation — PerCom working draft

We organize the evaluation around four questions that follow the VETS guarantee boundary.

## E1: What reactive-temporal behavior can Timeline represent?

We will select an external automation corpus before inspecting VETS outcomes, reconstruct each request's behavioral contract, and classify it as exactly representable, partially representable, unsupported, or insufficiently specified. The analysis separates language adequacy, reference-interpreter support, Explorer support, and binding limitations. **[CORPUS, ANNOTATION PROCEDURE, AND RESULTS PENDING]**.

## E2: Does the validator implement the declared semantics faithfully?

We will compare Timeline and JoI execution and Explorer verdicts against an independent oracle on boundary cases and positive and negative program pairs. Fault families include missing or additional calls, timing, snapshot value, order, sustain reset, edge re-arming, and repetition state. Unsupported, runtime-error, incomplete, false-equivalence, and false-divergence outcomes will be reported separately. **[FROZEN E2 PROTOCOL AND RESULTS PENDING]**.

## E3: What happens on generated JoI candidates?

We will generate JoI candidates from frozen confirmed Timeline and binding inputs and report every request as certified equivalent, divergent, unsupported or refused, incomplete, generation failure, or preparation failure. Equivalent outcomes must satisfy the applicable horizon-free closure conditions; a finite-prefix agreement will not be promoted to a certificate. The current development corpus and earlier fixed-horizon runs will remain provenance records rather than final E3 evidence. **[FROZEN E3 GENERATION PROTOCOL, MODEL CONFIGURATION, AND RESULTS PENDING]**.

## E4: How much exploration does VETS require?

The final E4 will vary input domains, control-flow size, timers, cycles, and state while reporting states, transitions, completion class, wall time, peak memory, and each reduction mechanism. Comparisons will use the same execution and observation contract and distinguish horizon-free closure, divergence, refusal, and incomplete exploration. Transition-count reduction will not be presented as a runtime speedup unless wall-time and resource measurements support that claim. **[SYSTEMATIC SCALE GRID, ABLATIONS, AND HORIZON-FREE COST RESULTS PENDING]**.

E1 and E2 remain necessary before broader adequacy or semantic-fidelity claims, and development evaluations on familiar candidates remain separate from final evidence.
