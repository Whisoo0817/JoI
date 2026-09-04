# Operational semantics decision

## Configuration

At logical time `t`, the IR configuration is

\[
C=\langle P,\sigma,\Theta,R,D,t\rangle
\]

where `P` is the rule/residual-control map, `σ` is IR plus modeled device state, `Θ` is the timer map, `R` is the active-instance/reentry map, and `D` is the next-step derived-event buffer.

A reaction is a total relation intended to be a function:

\[
C \xrightarrow{E_t/A_t} C'.
\]

## Time and interval decisions

- Time is discrete, monotone, and integer-valued in a declared unit.
- Intervals are half-open `[start,end)` unless the operator explicitly denotes an instant.
- A duration started at `t` with length `d>0` is due at `t+d`.
- The environment can advance only to a declared next input/deadline time and never backward.

## One reaction: snapshot–evaluate–merge–commit

1. **Input normalization.** Validate and canonicalize the external multiset at `t`. Multiple values for the same single-valued sensor in one batch are invalid input rather than implicitly ordered.
2. **Snapshot.** Apply exogenous sensor/device-state updates to form `σ_t`. Add event occurrences and `D` from the prior logical step. `σ_t` is immutable during evaluation.
3. **Timer tie rule.** Re-evaluate timer sustaining conditions against `σ_t`; cancellations caused by the external update take effect before due expirations are exposed. Remaining timers with deadline `t` produce expiry events in the same canonical batch.
4. **Activation/reentry.** Select triggered instances deterministically. An active `ignore` rule discards a new activation; `restart` replaces its residual instance and timers using one defined reset operation.
5. **Evaluate.** Every selected instance reads the same snapshot and emits a residual program plus typed effects; it does not mutate shared state.
6. **Merge.** Merge compatible state, timer, and action effects with an associative, commutative, permutation-invariant operator. A conflict cannot reach this phase for a well-formed core program.
7. **Commit.** Apply merged state/timer effects atomically, emit normalized `A_t`, and place action-derived modeled events in `D'` for the next logical step.
8. **Stutter.** If no rule produces an effect, emit an empty action batch and a unique stutter transition (time may still advance according to the environment schedule).

## Effect model

An effect has `(kind,target,operation,value,origin,causal-index,occurrence-id)`. Explicit `seq` edges contribute causal indices. Independent parallel effects are canonicalized but not given a causal relation. Multiplicity is preserved by `occurrence-id`.

## Hidden inputs forbidden

Wall clock, randomness, device response, network outcome, and callback scheduling must be declared as modeled external inputs or excluded. The interpreter never reads them implicitly.

