# State-of-the-art and gap map

## Comparison

| Work group | What is established | Reference checked | Search/evidence style | Boundary relative to new OVLA |
| --- | --- | --- | --- | --- |
| ChatIoT / AutoIOT / GPIoT | LLM-based IoT program synthesis and generation evaluation | request, structured grounding, tests/feedback | task benchmarks and execution feedback | Does not establish a confirmed executable per-request behavioral oracle plus reachable-history IR–code equality. |
| Practical TAP | End users can author useful trigger-action rules | user-authored TAP itself | field/user evidence | Not a separate reference-versus-implementation check. |
| TAPInspector / IoTSan | Formal safety/liveness analysis of interacting IoT rules/apps | predefined properties/invariants | model checking over extracted models | Property satisfaction can allow multiple behaviors; target is not exact behavior equality to a confirmed request-specific IR. |
| AutoTap | Synthesis/repair from user-facing temporal properties | selected LTL properties | synthesis/model checking and user study | A property is generally not a complete observable-behavior oracle. |
| AwareAuto / TAP debugging | Structured user interaction, confirmation-like steps, behavioral feedback, repair | inferred intent or annotated behavior | intention/usability/debugging studies | Human-in-the-loop support exists; OVLA must restrict itself to correctness relative to the confirmed IR. |
| Timed automata / synchronous languages | Formal timed and deterministic-reactive semantics | formal language/model definition | theory and language design | Foundations for OVLA semantics; not novelty. |
| SPIN / bounded model checking | Reachability and counterexample generation | transition system plus properties | explicit or bounded symbolic exploration | Foundations for Explorer; not novelty and not unbounded completeness. |

## Defensible gap statement

Within this targeted corpus, the closest systems do not combine all four of the following in one post-confirmation workflow:

1. a user-confirmed Timeline IR treated as the authoritative executable reference;
2. input-total, compositionally deterministic semantics for that IR;
3. the same modeled inputs and observation contract for IR and generated code; and
4. exhaustive comparison over reachable histories within an explicitly finite model and bounds.

This is a **scoped literature finding**, not proof that no such system exists. The manuscript should write “we did not identify, among the closest generation and IoT-verification systems reviewed, a system that combines …” until the final related-work search is frozen.

## Novelty center and non-novel components

The plausible novelty center is the verification target and end-to-end integration: an executable, confirmed behavioral reference for LLM-generated reactive-temporal IoT code, coupled to bounded reachable-history observational comparison. Grammar constructs, deterministic reactive semantics, explicit-state search, bounded model checking, and human confirmation are enabling components and should not be individually advertised as unprecedented.

## Consequence for paper flow

The approved seven-step flow remains intact. Literature strengthens step 1 (source form is insufficient), distinguishes step 2 (executable reference) from prior property checking, supplies foundations for steps 4–6, and constrains step 7 to bounded observational equality—not intent, physical, or unbounded correctness.

