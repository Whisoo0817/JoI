# Fixed aggregation unroll certificate

`fixed-aggregation-unroll-v1` certifies a narrow recurring pattern without
enumerating a large numeric sensor domain. It is a compiler pass, not a
bounded test: a fixed inclusive `Clock.Hour` interval is expanded into one
distinct symbolic input snapshot per hour, and the final ACTION expression is
compared with the independently expanded Timeline program.

## Admitted shape

- The Timeline is one unbounded outer cycle: wait for a literal Hour, then at
  most 32 nonempty read groups separated by exactly one hour, issue one ACTION,
  wait to leave the report hour, and repeat.
- The JoI block has a positive period that divides one hour and is aligned with
  the supplied start time. It starts before the first sample.
- A literal inclusive Hour interval and `h != last_hour` admit exactly one
  sample per hour. `last_hour` initially lies outside that interval.
- A literal count increases by exactly one at every sample. All carried numeric
  accumulators except `last_hour` are restored to their initial values after
  the single report ACTION. Neither controlling `if` has an `else` side effect.
- Every symbolic input is an INTEGER or DOUBLE catalog value. Dynamic bounds,
  timestamp arithmetic, data-dependent sample counts, cross-midnight windows,
  extra actions, incomplete resets and unsupported expressions are rejected
  by this pass and fall through to the ordinary fail-closed engines.

## Certificate argument

For sample index `i`, every external read becomes the distinct term
`input(device.member, i)`. Assignments are executed symbolically in original
statement order. Constant-only count arithmetic is folded; numeric expression
parenthesization is otherwise retained, so floating-point reassociation is
never assumed. The Timeline reads and ACTION arguments are expanded by a
separate parser into the same term language.

If sample hours, report hour, grounded ACTION identity and all argument terms
are identical, both programs emit the same daily trace for every valuation of
the symbolic snapshots. The post-report reset restores the common accumulator
base, while the retained `last_hour` differs from the next day's first sample
hour. This supplies the induction step for unbounded daily repetition.

Different summaries do not prove divergence. The pass constructs ordinary
finite numeric inputs and returns DIVERGE only if `replay_divergence` executes
the original, unmodified runners and observes different ACTION traces.

## Regression evidence

```sh
python -m explorer.tests.test_fixed_aggregation
```

The integration test uses the five frozen E1-095 candidates: correct is
EQUIV-FIXPOINT and fault1--4 are replay-confirmed DIVERGE. A dynamic-deadline
program (E1-099) and a sample guard with an effectful `else` are not admitted.

