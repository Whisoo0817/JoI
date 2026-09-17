# E1-024: rolling 48-hour sprinkler budget in existing Timeline IR

This candidate implements the stronger, demand-serving interpretation already frozen for E1-024: accept a positive duration request when capacity exists, stop when its duration or rolling budget is exhausted, and recover capacity as old watering leaves the preceding 48 hours. It uses the original integer-second replay model and an initially off sprinkler with no pre-start watering.

The earlier candidate in `../batch_er/attempts.py` waits 48 hours after one session. Its two counterexamples show a weakness of that candidate, not a missing Timeline operator. Those encodings, expectations and failures remain unchanged.

## Encoding

Ten minutes is 600 one-second units. The generated IR has 600 timestamp variables in a circular sequence. Each variable records the start of one second during which the sprinkler was actually commanded on. The next variable is the oldest retained usage record. It can be reused if unset or at least 172800 seconds old. Every admitted on-second overwrites that variable with `read Clock.Timestamp`, executes `delay 1 SEC`, and advances the control flow to the next variable. The last variable loops to the first.

There is no assignment to a computed sum, dynamic array, backend history input, extra output action, new operator, or runtime change. The program's execution position serves as the circular cursor. `read`, `if`, `wait`, `cycle`, `delay`, and `call` suffice. The generator expands the finite 600-slot construction into ordinary JSON; it is not executed by the IR runtime as a helper policy.

Request handling snapshots the requested duration and start time. It ignores new requests while busy and discards a request denied at an exhausted budget. It stops at the requested duration or before a second for which no slot is available. A new request exactly at completion can be admitted after the Off. Denied held requests are not automatically resumed when budget later returns.

## Why expiration works

The slots retain the most recent 600 on-second start times in chronological circular order. If the next slot is unset or old enough, consuming one more on-second cannot exceed the rolling limit. If that slot is still too recent, 600 on-seconds already occupy the window and another cannot be consumed. A new second can replace a second exactly 48 hours earlier: old usage leaves the window at the same rate that new usage enters it. This avoids both resetting all usage at midnight and waiting for an entire old session to expire.

On the integer-second model, rolling usage is linear between integer boundaries. Checking the boundary values therefore also bounds intermediate times. `run.py` independently integrates the actual On/Off intervals at all start/end and shifted-window breakpoints; that check uses intervals, not the IR's timestamp-slot logic.

## Scope and verification

`cases.py` and `frozen_cases.json` were hashed before `build_ir.py` existed. The tests retain the original three histories and add nine histories covering exact 48-hour reuse, split-session expiry, a third window, expiration during active watering, busy requests, duration snapshots, same-time Off/On, invalid durations, denied held requests, and 600 one-second sessions. `results.json` is the execution record; expected outputs never feed the candidate or runtime.

The supported parameters here are integer-second observations and durations, the same resolution used by the earlier E1-024 histories. Subsecond inputs/durations, pre-start history, uncontrolled external watering, missed input delivery and physical actuation are outside this test model. Finer resolution would require a corresponding clock model and more slots. This is a bounded rolling-budget implementation, not a claim of arbitrary unbounded aggregation or Explorer certification.

Reproduce from the repository root:

```sh
/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/e1_024_rolling/run.py
```

`build_ir.py` is the readable encoding generator; `timeline_ir.json` is the executable expanded IR. `run.py` validates the frontend and catalog, compiles through the unchanged existing preparation path, replays every history with the original reference replay function, and checks both exact traces and the rolling usage bound.
