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

## Horizon modes (reported separately, never merged)

| mode | `horizon_ms` | what it shows |
|---|---|---|
| `free` | `None` | the closure the Explorer actually claims |
| `fixed10` | 10 s | a cheap bounded horizon that covers only the opening |
| `fixedT` | 2·T + 5 s | a bounded horizon wide enough to cover the behaviour |

A bounded run that finishes returns `EQUIV-BOUNDED`, which holds only up to H. It is
counted as completed **in its own arm** and is never merged with the unbounded
`EQUIV`.

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

The Explorer's timer-zone proof, which every decided horizon-free run in this grid
went through, gives up after **30 s of wall clock** (`timer_product.py`, "timer zone
proof budget (30s)") and falls back to the concrete search, which cannot finish these
programs in 120 s. On an overloaded machine a 20 s proof crosses 30 s, so for the
horizon-free mode the machine load changes *whether* a run is decided, not only how
long it takes.

- `runs/e4_run.jsonl` — first run, 12 workers on 8 physical cores. Kept as a record
  only; **not reported**. Horizon-free decided 80/90 there against 84/90 alone.
- `runs/e4_free_serial.jsonl` — horizon-free, one run at a time. **Reported.**
- `runs/e4_fixed_w4.jsonl` — both fixed horizons, 4 workers. **Reported.** These
  modes have no wall-clock budget inside the Explorer, so load only stretches time.
- `runs/e4_boundary_solo.jsonl` — the two cells that were 1/3 in the first run,
  alone: 3/3 each (K200 17.8 s, 5/5/20 20.0 s).

## Result in short

| mode | programs decided in all 3 repeats | runs decided | not decided |
|---|---|---|---|
| no horizon (Explorer) | **28/30** | 84/90 | TIMEOUT 6 |
| fixed H = 10 s | 7/30 | 21/90 (EQUIV-BOUNDED) | TIMEOUT 69 |
| fixed H covering the wait | 2/30 | 6/90 (EQUIV-BOUNDED) | TIMEOUT 79, REFUSED 5 (state cap, 1.8 GB) |

Horizon-free decided runs: median 0.48 s, p95 17.8 s, max 20.2 s, peak RSS <= 44 MB.
Wait length 100 ms -> 4 h: 0.05-0.35 s. Input width is the costliest axis:
transitions double per added sensor (W7: 31,832 transitions, 9.2 s).

Where both a bounded search and the Explorer decided, the bounded one used
3,184-174,030 states, 1.5-85 s and up to 840 MB; the Explorer used 6-393 states,
<= 0.35 s. The two claims differ (EQUIV-BOUNDED holds only up to H), so this is
reported as completion range, not as a speedup.

## The two programs the Explorer did not decide (`diag_unfinished.py`)

Both are inside the supported fragment; neither was refused as unsupported.

| program | as is | 30 s give-up lifted (diagnostic only) |
|---|---|---|
| W6 B6 K50 | timer-zone proof gives up at 30 s | **EQUIV in 242 s** (1,110 states) — needs time |
| W7 B6 K100 | timer-zone proof gives up at 30 s | stops at the 2,000,000-transition cap after 793 s, not closed — too many cases for the current caps |

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
| `run_e4.py` | the grid runner; restartable, appends to `runs/e4_run.jsonl` |
| `make_e4_results.py` | `RESULTS.md`, `figs/e4_cost.pdf` (paper: all axes together), `figs/e4_cost_full.pdf` (every sweep) |
| `run_followup.py` | boundary cells alone (`solo`); long-budget re-runs (`long`, not used) |
| `diag_unfinished.py` | why the two undecided programs were not decided |

```
~/temp/bin/python run_e4.py --modes free --workers 1 --out runs/e4_free_serial.jsonl
~/temp/bin/python run_e4.py --modes fixed10,fixedT --workers 4 --out runs/e4_fixed_w4.jsonl
~/temp/bin/python make_e4_results.py
```

## Note on the mechanism ablation

The plan asks for an ablation of "mechanisms you can actually switch on and off".
Explorer's silent-time elision (`silent-time-v1`) has **no on/off switch** — it is
unconditional inside `_timed_product`, so ablating it would mean writing new
verifier code, not flipping a flag.

What *is* a real switch is the horizon: `horizon_ms=None` routes through
`timer_product` (timer-zone reduction) and falls back to concrete BFS, while a fixed
`horizon_ms` goes straight to concrete BFS. That is the contrast E4 reports, and the
plan already required the two horizons to be reported separately.
