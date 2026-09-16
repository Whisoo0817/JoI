# E4 — Cost and scale

**Question (confirmed_ir_evaluation_2026-09-10 §E4):** how far up the input / program /
time / state axes does the Explorer still finish, and what does it cost?

E4 measures **cost and completion only**. Whether a verdict is *right* is E2's
question and was answered there, so E4 runs no independent reference oracle. That
is why E4 is roughly 1/30 of E2's compute: E2's 9.3 h was almost entirely the
reference replay, not the Explorer.

## What is varied

One parametric program family, four axes, all inside the supported fragment (no
nested or parallel composition — the plan forbids mixing unsupported constructs
into a scale axis):

| axis | meaning | levels |
|---|---|---|
| `W` | input width: how many BOOL sensors the guard reads (domain = 2^W) | 1–7 |
| `B` | program size: sequential wait→call stages, one actuator each | 1–6 |
| `T` | wait length: the timeout on the falling-edge wait | 100 ms – 4 h |
| `K` | state memory: how many times the cycle body repeats | 1–200 |

Four one-factor-at-a-time sweeps from a mid-scale base (`W2 B2 T120000 K5`), plus a
**diagonal** where all axes grow together — that is where the budget actually runs
out. 34 sweep points over 30 distinct programs.

`W` is capped at 7 and `B` at 6 because that is how many independent BOOL sensor
values and on/off actuator pairs `files/service_list_ver2.0.7.json` actually has.
`Clock.IsHoliday` is excluded: it is a time service, not a varying input.

## How the pairs are built

`gen_grid.py` emits the IR **and** the JoI from the same parameters, so EQUIV is the
expected verdict — the case that makes the Explorer do the full closure work. A
DIVERGE would short-circuit the search early and understate the cost.

The JoI side is an explicit state machine that mirrors the IR exactly:

- `prev` carries the guard's previous value, so the rising-edge wait is encoded
  exactly. An `armed` flag only approximates it and breaks when the cycle wraps.
- the falling edge advances to the next stage and wraps the cycle `k` times;
- the timeout path fires the off call and then stops, which is what the IR's
  `break` does;
- stage `WRAP` burns the one `period` the IR waits between cycle iterations.

Every generated pair was checked to return EQUIV before the grid was run; a
non-EQUIV cell means the template is wrong, not that the Explorer is.

## Modes (reported separately, never merged)

| mode | what runs | reported as |
|---|---|---|
| `free` | the Explorer as used in E2/E3 (`horizon_ms=None`) | **Explorer** |
| `explicit` | same call, timer zones disabled (`no_timer_zones`): event-driven explicit-state search that jumps to the next timer event and merges identical states; same unbounded claim | **main baseline** |
| `fixedT` | horizon 2·T + 5 s, every 100 ms step simulated | one sentence ("fixed-step simulation") |
| `fixed10` | horizon 10 s | measured, **not reported** |

`fixed10` was dropped (whisoo 09-17): a 10 s window never reaches a 2 min, 30 min or 4 h
wait, so its "decided" is not the same question. The manuscript does not use a
horizon ("H") at all. A bounded run that finishes returns `EQUIV-BOUNDED`, which is
never merged with the unbounded `EQUIV`.

`explicit` disables zones by making `timer_product` raise `Unsupported` inside the
worker, so the Explorer takes its normal exact-search path. The Explorer code is not
changed.

## Budget and denominators

120 s per run — the same budget the E2 run used, so the two are read on one scale.
Each run is its own process, so `peak_rss_mb` is that run's peak.

`TIMEOUT`, `OOM`, `ERROR`, `REFUSED` and `UNKNOWN` all stay in the denominator.
Nothing is dropped.

**State and transition counts are reported as counts.** They are never restated as a
runtime speedup; wall time and peak RSS are reported on their own. If no result
shows the Explorer is faster, E4 reports the completion range and claims no speed
advantage (plan §E4, HANDOFF common rules).

## Which runs are the result (and why worker count matters)

The Explorer's timer-zone proof, which every decided `free` run in this grid went
through, has an internal wall-clock give-up (`timer_product.py`) and then falls back
to the concrete search, which cannot finish these programs in 120 s. On an overloaded
machine a proof near that limit crosses it, so for `free` the machine load changes
*whether* a run is decided, not only how long it takes. (Internal detail: not stated
in the manuscript; the 120 s timeout is presented as a user parameter.)

- `runs/e4_run.jsonl` — first run, 12 workers on 8 physical cores. Kept as a record
  only; **not reported**. `free` decided 80/90 there against 84/90 alone.
- `runs/e4_free_serial.jsonl` — `free`, one run at a time. **Reported.**
- `runs/e4_explicit_w4.jsonl` — `explicit`, 4 workers. **Reported.** No internal
  wall-clock give-up on this path, so load only stretches time.
- `runs/e4_fixed_w4.jsonl` — `fixed10` and `fixedT`, 4 workers. `fixedT` reported.
- `runs/e4_boundary_solo.jsonl` — the two cells that were 1/3 in the first run,
  alone: 3/3 each (K200 17.8 s, 5/5/20 20.0 s).

## Result in short

Paper table: `e4_table.md` (slowest of 3 runs; decided = all 3 runs decided).

| mode | programs decided | runs decided | not decided | slowest decided / peak RSS |
|---|---|---|---|---|
| Explorer | **28/30** | 84/90 | TIMEOUT 6 | 20.2 s / 44 MB |
| explicit-state (no zones) | **12/30** | 36/90 | TIMEOUT 54 | 100.3 s / 898 MB |
| fixed-step simulation | 2/30 | 6/90 (EQUIV-BOUNDED) | TIMEOUT 79, REFUSED 5 (state cap) | — |

- Explorer: 19 programs under 1 s, all 28 within 21 s. Wait 100 ms -> 4 h: 0.05-0.35 s.
  Sensors are the costliest axis: states stay 52, transitions roughly double per added
  sensor (W7: 31,832 transitions, 9.2 s).
- On the 12 programs both decided, the Explorer explored 99.2-99.9% fewer states when
  the wait was >= 10 s, and 44-45% fewer at 0.1 s and 1 s waits. Explicit-state timed
  out from a 30 min wait onward. The state counts are reported as counts, not as a
  speedup.
- Fixed-step simulation decided only the 0.1 s and 1 s wait programs.

## The two programs the Explorer did not decide (`diag_unfinished.py`)

Both are inside the supported fragment; neither was refused as unsupported.

| program | as is | internal give-up lifted (diagnostic only) |
|---|---|---|
| W6 B6 K50 | timer-zone proof gives up | **EQUIV in 242 s** (1,110 states) — needs time |
| W7 B6 K100 | timer-zone proof gives up | stops at the 2,000,000-transition cap after 793 s, not closed — too many cases for the current caps |

So "not decided" here means "not within the 120 s budget and the search caps", not
"cannot be decided by the Explorer".

## Counting note

`ProductResult.n_steps` adds 2 per paired transition (IR step + code step; the cap
check is `n_steps // 2 >= max_transitions`). Tables report `n_steps // 2`.

## Files

| file | what it does |
|---|---|
| `gen_grid.py` | the parametric family and the grid |
| `e4_worker.py` | one Explorer run in its own process; peak RSS and hard budget |
| `run_e4.py` | the grid runner; restartable, `--out` chooses the JSONL |
| `make_e4_results.py` | `RESULTS.md` (every program, every mode), `e4_table.md` (paper table; figures dropped 09-17) |
| `run_followup.py` | boundary cells alone (`solo`); long-budget re-runs (`long`, not used) |
| `diag_unfinished.py` | why the two undecided programs were not decided |

```
~/temp/bin/python run_e4.py --modes free --workers 1 --out runs/e4_free_serial.jsonl
~/temp/bin/python run_e4.py --modes explicit --workers 4 --out runs/e4_explicit_w4.jsonl
~/temp/bin/python run_e4.py --modes fixed10,fixedT --workers 4 --out runs/e4_fixed_w4.jsonl
~/temp/bin/python make_e4_results.py
```

## Note on the mechanism ablation

Silent-time elision (`silent-time-v1`) has **no on/off switch**, so it is not ablated.
The timer zones can be switched off without changing Explorer code (the `explicit`
mode above), and that is the contrast E4 reports. The zone technique itself is
existing work (difference-bound matrices, as in UPPAAL); the manuscript frames E4 as
"is verification light enough to be practical", and the VETS-specific part is binding
IR timers and code tick counters in one product (HANDOFF, whisoo 09-17).
