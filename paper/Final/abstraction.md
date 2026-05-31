VIOLA: On-device Verification of LLM-Generated IoT Automations via Timeline IR

Abstract

Smart home automation increasingly relies on Large Language Models (LLMs) to translate natural language (NL) user intents into executable reactive rules. However, deploying these rules directly on edge hubs poses severe reliability and safety risks since reactive IoT automations are temporally complex, involving precise triggers, durations, and repetitions. Existing validation methods rely heavily on human code inspection, offline experts, or resource-heavy cloud LLM re-checks, failing edge privacy and latency constraints.

To tackle this challenge, we present VIOLA, an on-device pipeline for deterministic, LLM-free verification of IoT automations before deployment. VIOLA shifts verification ahead of code generation: from the user's command it first fixes the target temporal behavior as a typed Timeline IR. VIOLA then automatically synthesizes reference event traces and boundary cases from this IR, and an efficient verifier simulates the generated code against them to detect behavioral discrepancies and guide automated repairs via counterexamples.

Evaluated with a local, quantized ≤9B model across 382 automations, VIOLA caught every faulty program in our evaluation set, repairing 32% of them and rejecting the rest. Under 1,475 injected temporal bugs, it detected 99.0%, while its synthesized scenarios exercised 97.4% of the targeted boundary cases, improving end-to-end correctness by Δ percentage points, all without any LLM in the verification loop.
