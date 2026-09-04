# Frozen anti-claims

| ID | The paper does not claim | Required protective wording |
| --- | --- | --- |
| AC-01 | Natural language was interpreted according to latent user intent | User confirmation fixes the verification specification; it is not evidence of intent correctness. |
| AC-02 | Arbitrary users understand or can author Timeline IR | No usability/readability conclusion is drawn without a separate approved human study. |
| AC-03 | The model predicts all physical device, network, or environment outcomes | Correctness is relative to the declared environment/adapter model and observation contract. |
| AC-04 | Post-deployment fault localization, repair, or self-healing | Counterexamples identify a divergent modeled history; downstream diagnosis/repair is outside scope. |
| AC-05 | Unbounded equivalence of arbitrary reactive programs | Exploration is exhaustive only within the declared finite model, bounds, and completed search. |
| AC-06 | Backend-independent verification from one backend | One adapter supports only the tested backend and contract. |
| AC-07 | LLM-based lowering is inherently superior to or required instead of a deterministic compiler | Lowering is an implementation choice; compiler comparison is inactive optional work. |
| AC-08 | Reachability search, deterministic-reactive semantics, or formal IoT verification is itself new | Credit timed automata, synchronous languages, model checking, and IoT verification foundations. |
| AC-09 | Legacy OVLA results validate the redesigned verifier | Old results motivate the redesign and may supply candidate cases; new claims require new E1–E4 evidence. |

