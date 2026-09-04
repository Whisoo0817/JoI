# Confirmed motivation

## Approved problem chain

Reactive-temporal IoT automation code reacts to asynchronous events, persistent state, timers, concurrency, and prior history. Source form is therefore an insufficient correctness criterion: different implementations can be behaviorally equal, while superficially plausible implementations can diverge under particular timed histories.

Behavioral checking requires an executable reference that determines expected observable actions for modeled timed inputs. In the approved workflow, the user-confirmed Timeline IR becomes that authoritative reference after authoring. The verification problem then separates cleanly from natural-language interpretation: determine whether the IR and generated code yield the same normalized observable action trace under identical initial conditions and every reachable timed input explored within a declared finite environment model and bounds.

## PerCom-facing stakes

The motivation is a pervasive-systems problem, not source-code style checking in the abstract. A wrong reactive-temporal home automation can remain dormant until a rare ordering, timer boundary, state combination, or concurrent reaction occurs. The system contribution is valuable when it exposes such histories reproducibly before deployment and states exactly which modeled histories were covered.

## Logic preserved

1. Source form is insufficient.
2. Behavior comparison needs an executable reference.
3. Confirmed Timeline IR fixes the reference boundary.
4. Fixed modeled input yields a unique observable IR trace.
5. Composition preserves that property.
6. Explorer enumerates reachable histories within finite model/bounds.
7. IR and code are compared under identical input and observation contracts.

No new motivation branch or contribution is introduced.

