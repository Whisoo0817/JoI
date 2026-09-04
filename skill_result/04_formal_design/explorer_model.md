# Explorer model

## Finite environment model

`M` declares finite sensor/event alphabets, finite value domains, valid input transitions, initial configurations, timer granularity, horizon `H`, and resource limits. Environment choice may branch; IR execution remains a function for a fixed choice.

## Search

Use deterministic breadth-first exploration for shortest counterexamples. Successors are generated in canonical input-label order. The default implementation is exact: no abstraction or partial-order reduction.

Canonical search state contains:

```text
(environment state, logical time, IR state/control/timers,
 code-adapter verification state, pending derived events)
```

State merging is permitted only when the adapter supplies a complete, deterministic serialization of all future-relevant code state. If that contract is unavailable, use bounded history-tree exploration without merging code states; merging on IR state alone is unsound because equal IR states may conceal different code states.

## Algorithm contract

1. enqueue every declared initial product configuration;
2. dequeue FIFO and enumerate every enabled modeled input batch;
3. run one IR reaction and one isolated code-adapter reaction with the identical batch;
4. compare normalized action batches immediately;
5. return the first canonical shortest divergence, if any;
6. otherwise enqueue unseen exact product states, or histories in fallback mode;
7. terminate at fixpoint, declared horizon, or explicit resource bound.

## Completion accounting

For every run record reachable states/histories, transitions, maximum frontier, horizon reached, wall time, peak RSS, adapter resets, errors, skips, retries, and timeouts. Distinguish:

- `fixpoint-complete`;
- `horizon-complete` (all histories through `H`);
- `resource-incomplete`;
- `execution-error`.

Only the first two support bounded-equivalence language, with their exact scope stated.

