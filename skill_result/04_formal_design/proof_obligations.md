# Proof obligations

## Semantic obligations

| ID | Obligation | Purpose |
| --- | --- | --- |
| PO-01 | Expression totality and uniqueness | Every well-typed expression yields exactly one typed value, including missing-value cases. |
| PO-02 | Primitive determinism | `set`, timer operations, calls, delay, and wait each emit one residual/effect result. |
| PO-03 | Merge compatibility and uniqueness | Every well-formed effect collection has exactly one merged effect. |
| PO-04 | Merge associativity, commutativity, identity, and permutation invariance | Branch enumeration and runtime scheduling cannot change behavior. |
| PO-05 | Constructor preservation | `if`, `seq`, `par`, temporal constructs, and finite repeat preserve determinism under well-formedness. |
| PO-06 | Reentry uniqueness | `ignore` and `restart` each select one next instance/timer map. |
| PO-07 | Time/tie uniqueness | Boundary, cancellation, expiry, batching, and derived-event phase rules select one transition. |
| PO-08 | Preservation | A transition from a well-formed configuration produces a well-formed configuration. |
| PO-09 | Progress/input totality | Every valid configuration and modeled input yields a transition, including stutter. |
| PO-10 | Reaction termination | Zero-time microsteps terminate; no same-tick recursive cycle exists. |
| PO-11 | One-step determinism | Same configuration and canonical input imply the same action batch and successor. |
| PO-12 | Unique-trace theorem | Induction over a fixed timed input trace yields one observable trace. |

## Explorer obligations

| ID | Obligation | Purpose |
| --- | --- | --- |
| PO-13 | Finite branching and bounded state/history space | Search terminates at fixpoint or declared bound. |
| PO-14 | Successor coverage | Every enabled environment transition is enumerated once per canonical state/history. |
| PO-15 | Exact-key soundness | Merged nodes are future-behavior equivalent because the key includes all future-relevant product state. |
| PO-16 | Completion honesty | Frontier/resource exhaustion yields `inconclusive`, never pass. |
| PO-17 | Adapter noninterference | Adapter sees inputs/time/model state but cannot inspect IR outputs or verdict labels. |

## Evidence division

PO-01–PO-12 require formal definitions and paper proof; tests only check the implementation. PO-13–PO-17 require algorithm arguments plus E1/E3/E4 protocol evidence. No experiment substitutes for the language theorem.

