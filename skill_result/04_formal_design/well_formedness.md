# Types and well-formedness

## Type layer

Primitive types are finite `Bool`, bounded `Int`, finite `Enum`, bounded `String/ID`, `Duration`, and `Option<T>` for modeled missing values. Action signatures and sensor/device references are declared in the environment schema.

## Required judgments

- `Γ ⊢ e : τ`: expression is pure, total, and type-correct.
- `Γ ⊢ Δ compatible`: an effect collection can be merged uniquely.
- `Γ ⊢ s wf`: statement has resolved references, finite control, and defined timing.
- `Γ, M ⊢ P wf`: program is valid under finite environment model `M`.

## Static rules

1. Every reference, event field, timer, target, operation, and parameter resolves to one declared typed entity.
2. Every expression operator is defined for its operands. Division by zero, overflow policy, and invalid conversion are statically excluded or map to an explicit value; they never inherit host-language behavior.
3. `Option<T>` cannot be used as `T`. Guards evaluating a missing optional value are `false` unless `is_missing` is tested explicitly.
4. Durations are positive integers. Absolute times and interval endpoints use the declared logical unit.
5. Repetition bounds are finite constants; the static zero-time control graph is acyclic.
6. Every rule selects `ignore` or `restart` reentry explicitly.
7. `wait_until` either observes a model variable or has an explicit finite timeout; it cannot create an unbounded exploration obligation.
8. Parallel branches that may update the same IR state/timer incompatibly in one reaction are rejected conservatively.
9. Parallel order-sensitive calls to the same target/channel are rejected. Identical duplicate calls remain distinct only when the action schema declares multiplicity meaningful and commutative.
10. Environment variable domains, input alphabet, initial configurations, time horizon, and resource bounds are declared before exploration.

## Dynamic validation outcome

Only well-formed programs become confirmed executable references. An invalid candidate receives a validation diagnostic before confirmation; `Conflict` is not silently turned into a runtime choice.

