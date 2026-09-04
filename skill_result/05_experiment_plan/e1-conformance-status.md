# E1 Interpreter Conformance Status

## Status

- **Evidence class:** development-only
- **Pilot result:** 6/6 common-subset cases passed
- **Artifact:** `results/E1/legacy-conformance-dev/`
- **Independent implementation:** retained SenSys IR and JoI simulators, with
  separate parsers, expression evaluators, worlds, and control-flow engines

## Covered in the pilot

- immediate calls;
- periodic level conditions and numeric boundaries;
- rising-edge behavior implemented with a persistent latch;
- `if`/`else` and a literal action argument;
- one-shot delay and continuation;
- multiple calls with observable action order.

For each case, the current IR runner is compared with the legacy IR simulator,
the current code runner with the legacy JoI simulator, and both implementations
must also agree on the paired behavior within the declared horizon.

## Boundary of this evidence

This is not yet the confirmatory E1 result. The legacy simulators are an
independent implementation, but not the normative formal semantics. The pilot
does not compare concrete device targets and does not yet cover grounding,
reentry, cancellation, cron, missing values, timer ties, or merge laws. Those
constructs require a frozen hand-derived boundary oracle or a second evaluator
implemented directly from the final operational rules.

## Next E1 step

Freeze hand-derived expected traces for the uncovered boundary cases, seed
faulty interpreter variants to demonstrate non-vacuity, and retain every
discrepancy before promoting E1 beyond exploratory evidence.
