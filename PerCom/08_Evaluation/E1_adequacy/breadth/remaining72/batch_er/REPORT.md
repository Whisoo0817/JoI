# Elicited and research remaining-case execution

The 33 agent-fixed interpretations produced **97/99 exact core history matches**. Thirty-two cases match all three frozen histories; E1-024 remains a partial candidate (1/3). Four separately frozen adversarial sensitivity histories for E1-020/E1-031 now match exactly. These are agent interpretations and executions, not author semantic validation or proofs over all histories.

## Freeze and reference execution

`cases.py` and its 99 source-derived expected histories were hashed before `attempts.py` existed. `FREEZE_MANIFEST.json` records the unchanged hash; `FROZEN_CASES.json` serializes all interpretations, source quotations/locators, alternatives, and favorable-bias notes. `sensitivity/` is a separate later freeze, preserving the original 99 histories. The reference runner, global service catalog, original20 files, and eight-case depth cohort were not changed. All 33 frontend/catalog validations and reference compilations passed. Explorer was not run.

All fixture members are explicitly typed current input values or observable leaf actions. There are no fixture timers, counters, duration/history/recency computations, aggregators, or admission policies. Native Blink is a leaf-action assumption for E1-038/E1-041. Daylight is the platform environment convention already used in E1-072.

## Retained counterexamples and revised candidates

- **E1-020:** v1 admitted a dishwasher request before the preceding washer start was acknowledged. The separate delayed-acknowledgement history exposes an extra StartDish. v2 reserves admission until the selected appliance is observed running and then stopped; all three core histories plus the added race history match. Scope requires controller-mediated starts and sampled acknowledgement transitions. No claim of physical mutual exclusion against arbitrary external starts is made.
- **E1-031:** v1 missed a request at the exact second toothbrush-use onset and counted an initially held signal as a use. Both sensitivity failures are retained. v2 enables at the second rise and requires a false baseline before the first rise. Core 3/3 plus sensitivity 3/3 include initial-state and midnight-reset cases. The raw-event fixed-two phase implementation is stronger than the original author-permitted backend daily-count guard; it is not evidence for arbitrary accumulation.
- **E1-043:** v1 passed a quoted string as a literal, producing the wrong color argument. v2 passes raw `blue`; the original v1 attempt and results are retained.
- **E1-024:** the tested Timeline candidate imposes a 48-hour cooldown after one capped session. It suppresses valid split sessions under the frozen demand-serving rolling-budget interpretation: 1/3 core histories match. This is a candidate limitation, not a proof of Timeline impossibility, and the stronger demand-serving interpretation adds liveness to the source safety constraint. A conservative controller can satisfy the literal never-exceed limit while refusing legal requests. A separately executed ordinary JoI mutable accumulator matches 3/3 histories, but only for a prefix before any session ages out of the rolling window; it does not implement rolling expiry and is not counted as a full JoI solution. `runs/accumulator_probe.json` separately records why ordinary `read.src` arithmetic is not an available mutable accumulator.

## Interpretation qualifications

- Sources phrased as safety constraints are evaluated through explicit request-admission or corrective-action interpretations. That follows the prior20 convention but does not demonstrate unrestricted source-property enforcement. In particular E1-020 reserves admission, E1-023 uses a chosen 24-hour rain-recency interval, E1-024 has a rolling 48-hour runtime budget, and E1-026 uses a chosen 100-lux threshold.
- E1-032 omits the informal smoke/fire/smell exception; E1-033 omits the informal not-going-to-work exception and adds closing at 18:00. These source-to-controller choices remain visible in frozen records.
- Strict more-than durations in E1-013/014/035 mean the first integer-second sample beyond the threshold. Exact trace matches are on the declared discrete grid, not a continuous-time equivalence claim. Calendar histories use a 60-second grid for exact minute boundaries; the horizon-zero negative history is only an initialization check, while longer histories test recurrence and neighboring boundaries.
- E1-045 treats sleep as one continuous episode, not nightly fragmented total. E1-049/053 use qualifying episodes and can brew again after condition re-entry. Event-versus-state startup and window inclusivity are fixed individually and listed in `cases.py`.

## Per-case result

| Case | Core exact | Outcome / qualification |
|---|---:|---|
| E1-013 | 3/3 | complete under agent-fixed interpretation |
| E1-014 | 3/3 | complete under agent-fixed interpretation |
| E1-016 | 3/3 | complete under agent-fixed interpretation |
| E1-019 | 3/3 | complete under agent-fixed interpretation |
| E1-020 | 3/3 | complete for serialized request admission with acknowledged lifecycle |
| E1-021 | 3/3 | complete under agent-fixed interpretation |
| E1-022 | 3/3 | complete under agent-fixed interpretation |
| E1-023 | 3/3 | complete under agent-fixed interpretation |
| E1-024 | 1/3 | partial: conservative one-session cooldown |
| E1-025 | 3/3 | complete under agent-fixed interpretation |
| E1-026 | 3/3 | complete under agent-fixed interpretation |
| E1-029 | 3/3 | complete under agent-fixed interpretation |
| E1-030 | 3/3 | complete under agent-fixed interpretation |
| E1-031 | 3/3 | complete for fixed-two raw-event interpretation |
| E1-032 | 3/3 | complete under agent-fixed interpretation |
| E1-033 | 3/3 | complete under agent-fixed interpretation |
| E1-035 | 3/3 | complete under agent-fixed interpretation |
| E1-038 | 3/3 | complete under agent-fixed interpretation |
| E1-039 | 3/3 | complete under agent-fixed interpretation |
| E1-040 | 3/3 | complete under agent-fixed interpretation |
| E1-041 | 3/3 | complete under agent-fixed interpretation |
| E1-042 | 3/3 | complete under agent-fixed interpretation |
| E1-043 | 3/3 | complete under agent-fixed interpretation |
| E1-044 | 3/3 | complete under agent-fixed interpretation |
| E1-045 | 3/3 | complete under agent-fixed interpretation |
| E1-046 | 3/3 | complete under agent-fixed interpretation |
| E1-047 | 3/3 | complete under agent-fixed interpretation |
| E1-048 | 3/3 | complete under agent-fixed interpretation |
| E1-049 | 3/3 | complete under agent-fixed interpretation |
| E1-050 | 3/3 | complete under agent-fixed interpretation |
| E1-051 | 3/3 | complete under agent-fixed interpretation |
| E1-052 | 3/3 | complete under agent-fixed interpretation |
| E1-053 | 3/3 | complete under agent-fixed interpretation |

## Reproduce

```sh
~/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_er
~/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_er/sensitivity
~/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/batch_er/joi_fallback.py
```

Core v1 traces are `runs/results_v1.json`; v1 candidates are `attempts_v1.py`. Sensitivity v1 counterexamples are `sensitivity/runs/results_v1.json`. Final reference traces are `runs/results.json` and `sensitivity/runs/results.json`.
