# Proof sketch and Gate G3

## Lemma structure

1. **Expression lemma.** Structural induction on typed expressions. Literals/references are unique; every operator is a total function on its finite typed domain; `Option<T>` cases are explicit.
2. **Primitive lemma.** Each primitive applies a fixed constructor to the snapshot and emits one typed effect/residual state.
3. **Merge lemma.** Static compatibility removes conflicting shared writes and order-sensitive parallel calls. The remaining typed merge is componentwise union/map update with preserved occurrence IDs, hence associative, commutative, and permutation invariant.
4. **Constructor lemma.** Structural induction on statements: total guards choose one branch; `seq` has one active position; `par` combines unique child results with unique merge; deadlines and repeat counters are arithmetic functions; reentry modes have one transition.
5. **Reaction lemma.** Input normalization, snapshot, tie handling, activation, evaluation, merge, and commit are each functions. Their composition is a function.
6. **Preservation/progress.** Static restrictions and atomic commit preserve declarations, types, finite control, and timer invariants. A reaction always exists; empty work produces stutter.
7. **Termination.** The zero-time control graph is acyclic and finite-repeat counters decrease. Derived events move to a later logical step, so a reaction has finitely many microsteps.

## Theorems

**One-step input determinism.** For well-formed `P`, configuration `C`, and valid canonical batch `E`, if both `C --E/A1--> C1` and `C --E/A2--> C2`, then `A1=A2` and `C1=C2`.

**Unique observable trace.** By induction on a fixed finite timed-input trace, a well-formed program and initial configuration induce exactly one normalized observable action trace. Stutter covers inputs with no action.

**Determinism-preserving composition.** Each admitted constructor maps deterministic, compatible children to a deterministic composite. This is the composition property required by C3; contextual congruence is not required for the main claim.

## Gate G3

**Advisor design decision: PASS, conditional on implementation and formalization matching these files.**

- Every valid configuration/input has a transition or stutter.
- Simultaneous events, conflict, timer ties, missing values, reentry, derived events, and interval boundaries have one explicit policy.
- PO-01–PO-17 cover the required language, composition, termination, Explorer, and adapter obligations.
- E1–E4 can be planned without selecting an unresolved semantic policy.

This pass freezes the recommended advisor contract; it does not claim that a proof or implementation already exists.

