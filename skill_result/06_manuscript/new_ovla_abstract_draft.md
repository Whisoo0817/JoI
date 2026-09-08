# New OVLA abstract draft

## Status

This is a pre-results abstract. It reflects the frozen seven-step logic, C1–C5 contribution order, formal design, and E1–E4 plan as of 2026-09-04. It intentionally contains no result numbers because no new-OVLA experiment has been executed or audited. Results from the predecessor OVLA are not evidence for the redesigned semantics and Explorer.

## Contrast with the SenSys abstract

| Abstract role | Previous OVLA | New OVLA |
|---|---|---|
| Opening problem | Reliability and safety risks of deploying LLM-generated rules on an edge hub | Reactive-temporal correctness cannot be judged from source form because behavior depends on event, state, time, and history |
| Central obstacle | Existing validation depends on human inspection, experts, or cloud LLMs | No executable per-request behavioral reference exists; syntax-different code may be behaviorally equal and syntax-similar code may diverge |
| Main contribution | Deterministic, LLM-free, on-device verification pipeline | Reference-relative behavioral verification of generated code over reachable modeled histories |
| Role of Timeline IR | Compact machine-checkable representation and deterministic user-facing rendering | Enabling executable specification that makes implicit behavior-bearing semantics explicit after confirmation |
| Formal basis | Typed IR plus boundary-event simulation | Input-total operational semantics, determinism-preserving composition, and a unique reference trace for fixed modeled input |
| Search/check | Synthesized transition-boundary scenarios over a bounded horizon | Reachable-history exploration in a declared finite environment model and bounds, with explicit completion accounting |
| Verdict | Pass/fail deployment gate with repair | Equality, shortest counterexample, or inconclusive when exploration is incomplete |
| Evaluation | Legacy mutation, replay, latency, and physical-deployment numbers | E1 semantics conformance, E2 expressive adequacy, E3 equivalence discrimination, and E4 completion/resource frontier |
| Guarantee boundary | Often summarized as preventing unsafe or divergent deployment | Equality relative to the confirmed IR, shared model, input contract, observation contract, completed search, and declared bounds |
| Explicit anti-claims | Human confirmation limitation acknowledged late | No latent-intent, usability, physical-device, cross-backend, or unbounded-correctness claim |

## Draft abstract v1

Large language models lower the barrier to authoring smart-home automations by translating natural-language requests into platform-specific code. Yet determining whether the generated code implements the specified behavior remains difficult. IoT automations are reactive-temporal programs whose actions depend on asynchronous events, persistent state, timers, and execution history. Consequently, substantially different code idioms can implement the same behavior, while syntactically plausible implementations can produce divergent action traces. Source similarity, structural checks, and LLM-based judgments therefore cannot by themselves establish behavioral correctness.

We present OVLA, a framework for verifying LLM-generated reactive-temporal IoT code against a user-confirmed executable specification. Timeline IR maps one selected interpretation of a natural-language request, including its otherwise implicit event-, state-, time-, and history-dependent semantics, into a deliberately restricted space of typed reactive-temporal operators. It serves both as a user-inspectable intermediate specification and as an authoring surface that connects natural-language requests to formal specifications. Once confirmed, the IR becomes the authoritative specification; OVLA does not claim to validate whether it captures the user's latent intent. We give Timeline IR input-total operational semantics and determinism-preserving composition rules, ensuring that a fixed initial configuration and modeled timed input trace produce a unique normalized observable action trace.

OVLA's Explorer enumerates reachable histories within a declared finite environment model and exploration bounds. It executes the confirmed IR and candidate code under identical input and observation contracts, reporting behavioral equality, a shortest counterexample, or an inconclusive result when exploration is incomplete. We evaluate semantic conformance, expressive adequacy, equivalence discrimination, and the completion and resource frontier of exploration. OVLA thus formulates generated IoT-code validation as bounded, reference-relative behavioral-equivalence verification, with explicit limits imposed by user confirmation, environmental modeling, backend semantics, observability, and exploration bounds.

## Results insertion contract

The final abstract should replace the evaluation sentence with audited findings only after all applicable gates pass:

- E1: interpreter conformance and remaining discrepancy bound;
- E2: exact, partial, and unsupported adequacy by declared scope;
- E3: false accepts, false rejects, completion rate, and counterexample evidence;
- E4: completed exploration frontier, tail latency, and peak memory.

Do not reuse the predecessor's `99.3%`, `35,800 replays`, `0.97 ms`, or six-automation deployment as evidence for the redesigned system. Those results may appear only as predecessor motivation or provenance unless rerun under the frozen new semantics and Explorer protocol.
