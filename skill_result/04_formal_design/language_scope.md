# Timeline IR core language scope

## Status

This is the minimum advisor-recommended semantic core needed to realize the approved C2–C4 claims. It clarifies open choices in `new_ovla` Section 18 without changing the paper flow.

## Supported behavior dimensions

- external edge/event and state-based triggers;
- total Boolean, comparison, and finite arithmetic expressions;
- persistent IR and modeled-device state reads/updates;
- discrete durations, deadlines, timer start/cancel/expiry;
- typed device/service actions with parameters;
- sequence, conditional, parallel branches, and finite repetition;
- explicit reentry mode: `ignore` or `restart`;
- multiple simultaneous external events under a canonical batch rule.

## Deliberate restrictions

- Logical time is a nonnegative integer in a declared unit; no continuous real-valued time.
- Domains and exploration horizon are finite and declared per verification model.
- Expressions are pure and total; missing input is an explicit typed value.
- No recursion, unbounded loop, zero-duration cycle, dynamic code loading, or hidden wall-clock read.
- Potential simultaneous conflicting writes/actions are rejected unless the core declares them compatible; source order is never a resolution policy.
- Derived events are visible no earlier than the next logical step.
- `queue` reentry, priorities, rich conflict-resolution operators, continuous time, abstraction, and POR are not in the core.

## Why this is sufficient

The restrictions make a confirmed IR executable, input-total, proof-tractable, and finite-model explorable while retaining every behavior dimension already named by C2–C4. Richer policies would create new language and evaluation obligations and remain optional extensions.

