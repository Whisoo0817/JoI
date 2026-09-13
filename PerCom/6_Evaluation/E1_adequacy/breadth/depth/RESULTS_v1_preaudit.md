# E1 depth additions — results (2026-09-13, before the author's semantic audit)

Inputs frozen before encoding: `../frozen_cases/` (commit `35e6043`), `depth_cases.py` + `fixture.py` (commit `6f2c040`).
Encodings and attempt history: `depth_attempts.py`. Raw run: `runs/e1_depth.json` (fixture catalog sha256 `1ffb6363…`).
Rerun: `python depth/run_depth.py --explorer` from `breadth/`.

**Status.** These are execution results, not final E1 adequacy. E1 adequacy is the author's semantic audit plus
reference execution; the audit of these eight encodings has not been done (see `../AUTHOR_TODO.md`).

## Table

| Case | Timeline result | Frontend | Outside extractor.md | Reference runner (tol / exact) | Catalog | JoI fallback | Explorer (aux) |
|---|---|---|---|---|---|---|---|
| E1-092 parallel shutdown | **impossible** | accepted | — | **0/1 / 0/1** — `Alarm.Set` at t+2 missing | stubs House, Alexa, Lights, Locks, Alarm | 1/1 / 1/1, two JoI blocks | EQUIV (self-product) |
| E1-095 daily average | **partial** | accepted; accumulator attempt refused | period 0 | 1/1 / 1/1 (unrolled five reads) | stubs PoolPH, PoolChlorine, Pool | 1/1 / 1/1, mutable vars (v3) | REFUSED: input domain |
| E1-086 cancelable sprinklers | complete | accepted | period 0, wait.timeout | 1/1 / 1/1 | global (Switch, Valve) | n/a | EQUIV |
| E1-099 motion extension | complete | accepted | Clock.Timestamp, nested cycle, null, period 0 | 1/1 / 1/1 | global (Switch, MotionSensor) | n/a | REFUSED: joint-guard |
| E1-028 rolling feeder limit | complete | accepted | Clock.Timestamp, nested cycle, null, period 0 | 1/1 / 1/1 | stub Feeder | n/a | REFUSED: joint-guard, derived-guard |
| E1-034 oven confirmation | complete | accepted | wait.timeout | 2/2 / 2/2 | stubs Oven, Notify | n/a | EQUIV |
| E1-072 home/away lighting | complete | accepted | period 0 | 1/1 / 1/1 | global (PresenceSensor, Switch) | n/a | UNKNOWN (graph not closed) |
| E1-062 two-light sync | complete | accepted | period 0 | 1/1 / 1/1 | global (Switch) | n/a | EQUIV |

Timeline IR: complete 6, partial 1, impossible 1 (of 8). Every Timeline encoding above is the first attempt (v1).
Reference execution: all 8 histories of the seven complete/partial cases match exactly; E1-092 does not.
Explorer column: IR against itself only, i.e. whether verification completes. It is not counted in E1 adequacy and
says nothing about the injected fault.

## What each non-complete case shows

**E1-092 — single control flow is a real boundary once failures are isolated.** Timeline has one flow, so the
Alexa and house commands are interleaved in it. The injected failure of `Alexa.AnnounceNews` (issued t+1, delivered
t+2, rule T7) ends that one instance, and the house flow's `Alarm.Set` at t+2 never happens. Delivering the failure
after instead of before the t+2 step would not help: the same instance would then also issue
`Alexa.AnnounceAlarmSettings`, which the frozen trace excludes (checked by running that variant: all house commands
appear, plus an extra `Alexa.AnnounceAlarmSettings` at t+2). No error or availability construct was added, by
decision. JoI scripts have no in-script parallel construct either; the fallback matches only as **two JoI blocks
deployed side by side**, where the failure ends the Alexa instance and the house instance continues. The frozen record
has only the failure history, so a failure-free run was not tested.

**E1-095 — no assignment.** `sum += value` cannot be written: `read` copies a catalog attribute and nothing else
(attempt A, `read` from `$sum_ph + PoolPH.Value`, is refused: `unknown catalog value`). Because the frozen window has
a literal five samples, five unrolled read pairs with the mean computed in the call arguments reproduce the trace
exactly. That is why the result is partial, not complete: the behaviour matches, the required mechanism does not
exist, and an aggregate whose sample count depends on input remains unexpressed (argued, not probed). The JoI fallback
accumulates with `:=` slots and matches exactly.

## Other observations

- **Reference-runner gap.** `explorer.runtime.interp.clock_state` provides timestamp, hour, minute and weekday, but not
  `Clock.Second`, which the catalog lists. JoI v2 of E1-095 used it, read null, and reported nothing. v3 avoids it.
  Not a language limit; any second-resolution JoI clock condition would hit the same gap.
- **Frontend grammar.** 7 of 8 encodings use constructs outside `files/timeline_ir/extractor.md` (only E1-092 does
  not, and it fails for a different reason). As in Stage A, these are hand-writable but not reachable through the
  current NL→IR prompt.
- **Bounded literals.** E1-028 is expressible because the limit is the literal 2 (two timestamp slots written by
  counter parity). A limit of N needs N slots; a limit given at run time was not tested (finite-state limit, unprobed).
- **Explorer.** The joint-guard refusal seen in probes P1–P3 recurs (E1-099, E1-028); E1-095 needs an explicit input
  domain; E1-072 is inconclusive. Auxiliary only.

## Caveats to carry into the paper

- One or two histories per case, exactly as frozen. A match is trace agreement on those histories, not equivalence.
- Comparison rule T5 treats commands issued at the same instant as unordered; rule T7 fixes the failure model.
- Leaf stubs (depth_cases.py `stubs`) test orchestration only and are not evidence of device support.
