# Candidate claim register

The records below split C1–C5 into falsifiable units without creating new contributions. “Blocked” means no new-system experiment has yet been run; it is not a judgment that the design is unsound.

| ID | Parent | Bounded claim | Evidence mode | Required support | Current status | Allowed manuscript action now |
| --- | --- | --- | --- | --- | --- | --- |
| PC-01 | C1 | Under one declared input and observation contract, OVLA can decide equality or divergence of IR/code observable traces for each completed explored history. | mixed | formal comparator definition + E3 | blocked | describe as design goal only |
| PC-02 | C2 | Every well-formed core Timeline IR has defined behavior or stutter for every modeled input configuration. | theoretical | totality/progress argument + E1 conformance | blocked pending formal freeze | qualify as intended property |
| PC-03 | C2 | Timeline IR contains the event, state, time, control-flow, and action information required for the declared target behavior space. | empirical | frozen taxonomy + E2 | blocked | do not assert adequacy |
| PC-04 | C3 | For fixed initial state and modeled timed input, core IR execution yields one normalized observable trace. | theoretical | primitive determinism + expression totality + merge invariance + composition proof | blocked pending formal freeze | state theorem obligation only |
| PC-05 | C3 | The chosen composition constructors preserve determinism and terminate each logical reaction. | theoretical/mixed | constructor proof + E1 boundary/property suites | blocked pending formal freeze | state obligation only |
| PC-06 | C4 | Exact-state exploration enumerates each reachable canonical state/history in the declared finite environment model and bounds, subject to reported resource completion. | theoretical/mixed | Explorer argument + E1 small-model check + E4 completion accounting | blocked | qualify by model, bounds, and completion |
| PC-07 | C4 | IR and backend adapter receive identical modeled inputs and use one normalized observation contract without verdict leakage. | methodological/empirical | adapter protocol inspection + E3 controls | blocked | describe protocol, not achieved result |
| PC-08 | C5 | The interpreter conforms to the frozen semantics over the declared core language and tested boundary space. | empirical | E1 | blocked | omit result language |
| PC-09 | C5 | The IR is adequate for the predeclared target corpus, with exact/partial/unsupported coverage reported. | empirical | E2 | blocked | omit result language |
| PC-10 | C5 | The checker distinguishes equivalent from divergent implementations on predeclared positive and negative cases within its completed explored scope. | empirical | E3 | blocked | omit result language |
| PC-11 | C5 | Explorer time/memory/completion behavior is characterized as state, timer, event, rule, and horizon complexity vary. | empirical | E4 | blocked | omit result language |

## Claim hierarchy

`PC-01` is the dominant system claim. `PC-02`–`PC-07` are enabling semantic and methodological claims. `PC-08`–`PC-11` are the four evidence-bearing evaluation claims. No record is a sixth contribution.

