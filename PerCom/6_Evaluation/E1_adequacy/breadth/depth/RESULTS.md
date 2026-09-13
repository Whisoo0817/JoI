# E1 depth additions — results after the author semantic audit (v2, 2026-09-13)

- Decisions: `AUTHOR_ADJUDICATION_2026-09-13.md`.
- v2 records, frozen before v2 encoding (commit `85d3ab8`): `depth_cases_v2.py`, `fixture_v2.py`.
- v2 encodings: `depth_attempts_v2.py`. Run: `runs/e1_depth_v2.json`, reproduced with
  `~/temp/bin/python depth/run_depth_v2.py --explorer` from `breadth/`.
- Kept unchanged: `../frozen_cases/`, `depth_cases.py`, `fixture.py`, `depth_attempts.py`, `runs/e1_depth.json`
  and the pre-audit summary `RESULTS_v1_preaudit.md`.

E1 adequacy = author semantic audit + reference execution. The Explorer columns are auxiliary and are not part of
any count. **No number here goes into the paper until the manual corpus coding is finished.**

## Table

| Case | Final label | Deployed | Reference runner (tol / exact) | v1 on added history | Explorer (aux) |
|---|---|---|---|---|---|
| E1-092 | complete via multi-Timeline decomposition | 2 Timeline IRs (A Alexa, B house) + their 2 JoI blocks | IR 1/1 / 1/1; JoI 1/1 / 1/1 | (v1 single Timeline: 0/1) | self EQUIV ×2; IR vs JoI EQUIV ×2 |
| E1-095 | complete for fixed-cardinality aggregation | 1 IR (v1, reused) | 1/1 / 1/1 | — | REFUSED (input domain) |
| E1-086 | complete | 1 IR (v1, reused) | 1/1 / 1/1 | — | EQUIV |
| E1-099 | complete | 1 IR (v2, motion first) | 2/2 / 2/2 | 0/1 | REFUSED (joint-guard) |
| E1-028 | complete for the fixed bound of two | 1 IR (v1, reused) | 1/1 / 1/1 | — | REFUSED (joint-guard, derived-guard) |
| E1-034 | complete | 1 IR (v2, repeating cycle) | 3/3 / 3/3 | 0/1 | EQUIV |
| E1-072 | complete | 1 IR (v2, daylight input) | 2/2 / 2/2 | 0/1 | EQUIV |
| E1-062 | complete | 1 IR (v1, reused) | 1/1 / 1/1 | — | EQUIV |

All 12 histories of the v2 records match exactly. All frontends accept and all encodings compile on the reference runner.

## Per case

**E1-092.** Automation A issues AnnounceTasks (t+0) and AnnounceNews (t+1). The injected failure is delivered at
t+2 and stops A only (rule T7), so AnnounceAlarmSettings is never issued. Automation B issues Lights.Off,
Locks.Lock and Alarm.Set at t+0, t+1 and t+2. The merged trace equals the frozen trace. The JoI deployment gives the
same trace. The v1 single-Timeline encoding (0/1, Alarm.Set missing) stays recorded.
Claim scope: one Timeline has no parallel branch, and mutually independent flows can be decomposed into several
Timeline IRs. This does not cover fork–join or shared-state parallelism.

**E1-095.** The fixed interpretation is satisfied by five snapshot variables and `(v1+…+v5)/5`. The refused v1
accumulator attempt (`read` from `$sum_ph + PoolPH.Value` → `unknown catalog value`) documents a separate boundary:
Timeline IR has no general mutable accumulator and no input-dependent aggregation. General averages, counts and
history are described as backend-service delegation, not as a Timeline capability or a measured gain.

**E1-099.** New history `motion_at_deadline_instant`: on at t, a motion at t+5 min exactly when the deadline falls.
v2 handles the motion first, extends the deadline, and turns off at t+7 min. v1 is kept as evidence of the
deadline-first behaviour: it turns off at t+5 min.

**E1-034.** New history `C_confirm_restart_then_no_response`:
- first alert at t+4 h;
- confirmation at t+4 h 30 s;
- second alert at t+8 h 30 s;
- off at t+8 h 1 min 30 s.

v2 matches it and also histories A and B. v1 stops after the first confirmation, so it misses the second alert and
the off.

**E1-072.** The guards read `Sun.IsDaylight`, a platform environment input and E1 stub; no literal clock hours
remain. History `night_home_then_day_away` sets sunrise 06:00 and sunset 18:00 as that run's values. New history
`later_sunrise_from_environment` sets sunrise 07:30, so arriving home at 07:00 turns the lights on. v1, with
hard-coded hours, misses those two commands.

**E1-028, E1-062, E1-086.** Approved as encoded in v1; rerun under v2 with identical traces. E1-028's claim is limited
to the fixed bound 2; nothing is claimed for a run-time N or unbounded history.

## Not claimed from E1

- General mutable accumulators, dynamic N, or unbounded history.
- Finite-state properties (no probe).
- Fork–join or shared-state parallelism.
- The extractor-prompt grammar and reference-runner clock observations. They are not E1 results; see
  `ENGINEERING_NOTES.md`.

Caveat: one to three histories per case, as recorded. A match is trace agreement on those histories, not equivalence.
