# Observation and equivalence model

## Observable record

Each externally meaningful action is normalized to:

```text
(logical_time, target, operation, normalized_arguments,
 causal_predecessors, occurrence_id)
```

The observer excludes source location, variable names, helper calls, internal control state, and runtime thread order.

## Batch equality

At each logical time, equality requires:

- identical action multiplicity;
- identical target, operation, and normalized arguments;
- identical explicit causal order induced by `seq`;
- no sensitivity to enumeration order among causally independent `par` effects.

A canonical serialization is used for hashing/reporting, but does not manufacture causal order. Parameter normalization, clock unit, numeric precision, default values, and platform aliases are frozen in the adapter specification before E3.

## Trace verdict

For initial configuration `s0` and modeled timed input `I`,

\[
Eq(T,C,s_0,I) \iff Obs(Run_{IR}(T,s_0,I))=Obs(Run_{Code}(C,s_0,I)).
\]

The global verifier passes only if equality holds for every history whose exploration completed within the declared finite model/bounds. It returns one of:

- `equivalent-within-completed-scope`;
- `divergent(counterexample)`;
- `inconclusive(resource-bound/frontier/adapter-error)`.

Timeout or incomplete frontier is never converted to `equivalent`.

## Counterexample content

Report the smallest discovered canonical timed-input history, the first mismatching action batch, both normalized traces through that point, model/bound identifiers, and execution provenance. Localization or repair is not claimed.

