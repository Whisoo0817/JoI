# Lowering and backend decision

## Core decision

Retain LLM-assisted lowering as the current system path because the approved paper concerns LLM-generated automation code. Do not argue that a deterministic compiler is infeasible or inferior. Correctness is established, if supported, by behavioral comparison rather than by the lowering mechanism.

## Separation of concerns

- Timeline IR interpreter: implements the frozen reference semantics.
- Lowerer: produces target-platform code and may vary structurally.
- Backend adapter: injects the declared initial state and timed exogenous inputs, controls/reset execution, and normalizes platform actions.
- Comparator: receives only normalized traces and scope/completion records.

The lowerer and adapter cannot read expected IR actions, equivalence labels, or fault labels. Generated code runs in a fresh isolated state per explored history or an exactly snapshotted state.

## Backend contract

The adapter must declare supported event/value mappings, logical-to-platform time mapping, action aliases/normalization, reset/snapshot completeness, errors/timeouts, and all hidden-input exclusions. One adapter justifies only one-backend evidence.

## Inactive optional extension

A deterministic-compiler comparison could answer a different lowering-quality question; a second backend could test portability. Both change empirical scope and remain inactive under A09/A10. Neither is needed to support the core bounded reference-relative verification claim.
