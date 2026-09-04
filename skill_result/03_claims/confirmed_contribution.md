# Confirmed contribution

## One-sentence system contribution

OVLA makes a user-confirmed Timeline IR an executable, input-total, compositionally deterministic behavioral reference and checks LLM-generated reactive-temporal IoT code against it over all reachable histories within a declared finite model and exploration bounds.

## Contribution sequence

1. **C1 — Behavioral verification.** A verification target based on normalized observable behavior rather than source form.
2. **C2 — Executable reference specification.** A user-confirmed Timeline IR whose event, state, and time semantics generate reference traces.
3. **C3 — Determinism-enabling semantics.** Operational semantics and composition rules that produce a unique observable trace for fixed modeled input.
4. **C4 — Reachable behavior exploration.** A finite-model Explorer that enumerates reachable timed histories and drives IR/code execution under the same contract.
5. **C5 — Evaluation.** Evidence on semantics conformance, expressive adequacy, equivalence discrimination, and Explorer capacity.

## Reviewer payoff

- The reviewer can identify the exact specification boundary.
- “Equivalent” has a concrete observation relation, input contract, and finite scope.
- The semantic argument and empirical checker evidence are separated.
- Counterexamples can be tied to reachable modeled histories rather than hand-picked replays alone.
- Unsupported, exhausted, and timed-out regions remain visible.

## Scope-preserving language

Preferred guarantee:

> For a user-confirmed, well-formed Timeline IR and generated code, OVLA checks whether both produce the same observable action trace for every reachable timed input explored within the declared finite environment model and exploration bounds.

Avoid “proves the generated automation correct,” “captures user intent,” and “verifies all real-world executions.”

