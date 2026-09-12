"""E1 Stage A — Timeline IR candidates, written AFTER cases.py was hashed (README §4).

Language = the paper's Timeline contract (start_at, wait[cond, edge, for, timeout/on_timeout], delay, read, call,
if, cycle[until, period, count], break) as implemented by explorer.runtime.ir_step.compile_ir. Where the
frontend validator (timeline_ir.validate_ir) is narrower, run_e1.py records the difference in column A-frontend.

Each entry: ir, lang ('full' | 'partial' | 'unsupported' | 'hold'), note (encoding rationale / what is not
captured). `lang` is the author's pre-execution claim; execution (column C) may contradict it and then the
contradiction is reported, not silently edited.

Encoding devices used more than once (kept explicit so the audit can judge them):
  E-TIMEOUT-ABORT : a `wait` with `timeout` and a NON-empty `on_timeout` ends the current iteration
                    (runner: GOTO -1). With an EMPTY on_timeout the program continues past the wait.
                    A `read` into a dummy variable is used as the smallest non-observable statement.
  E-ZERO-PERIOD   : `cycle.period: "0 MSEC"` is used ONLY for event-driven loops whose body always blocks on a
                    wait/timeout, so the loop cannot spin; it is not a licence for an instantaneous unbounded loop.
                    Rationale: period is waited AFTER the body, so a non-zero period would delay a cadence that the
                    body's own timeout already provides (audit 2026-09-12).
  E-PREV          : previous-iteration snapshot via `read` at the end of a 100 ms polling cycle, so that
                    "which input changed" can be decided in the next iteration.
"""

NOOP = {"op": "read", "var": "_noop", "src": "Clock.Hour"}   # non-observable statement (E-TIMEOUT-ABORT)

IRS = {}

IRS["C01"] = dict(lang="full", note=(
    "Restart mode as one flow. Outer: rising motion -> On. Inner cycle: wait no-motion; wait motion with a 2-minute "
    "timeout -> on timeout Off and `break` out of the inner cycle (E-TIMEOUT-ABORT + break); motion returned in time -> "
    "explicit On and back to 'wait no-motion'. After the break the outer loop-top rising wait observes the false level "
    "and re-arms for the next pass."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
            {"op": "wait", "cond": "MotionSensor.Motion == true", "edge": "rising"},
            {"op": "call", "target": "Switch.On", "args": {}},
            {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
                {"op": "wait", "cond": "MotionSensor.Motion == false", "edge": "none"},
                {"op": "wait", "cond": "MotionSensor.Motion == true", "edge": "none", "timeout": "2 MIN",
                 "on_timeout": [{"op": "call", "target": "Switch.Off", "args": {}}, {"op": "break"}]},
                {"op": "call", "target": "Switch.On", "args": {}},
            ]},
        ]}]})
IRS["C01"]["history"] = (
    "v1 (2026-09-12): single cycle, no explicit On after the timeout-wait -> 3/4; the On for motion returning inside the "
    "window was missing because the loop-top rising wait's latch is not updated while other waits run. "
    "v2: added explicit On at the end of the body -> still 3/4; after that On the loop-top rising wait stayed latched and "
    "the flow never returned to 'wait no-motion', so the final Off was missing. "
    "v3: inner cycle with break on timeout (this version).")

IRS["C03"] = dict(lang="full", note=(
    "Rising crossing -> On, fixed delay, Off. Re-crossings during the delay are unobserved (ignored). "
    "History 'already_high_at_start' tests the initial-true edge policy of the contract against the requirement."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "wait", "cond": "CarbonDioxideSensor.CarbonDioxide <= 1000", "edge": "none"},
        {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
            {"op": "wait", "cond": "CarbonDioxideSensor.CarbonDioxide > 1000", "edge": "rising"},
            {"op": "call", "target": "Switch.On", "args": {}},
            {"op": "delay", "duration": "15 MIN"},
            {"op": "call", "target": "Switch.Off", "args": {}},
        ]}]})
IRS["C03"]["history"] = ("v1 (2026-09-12): no leading wait -> On at t=0 in 'already_high_at_start' (initial-true edge fires). "
    "v2 adds wait(<= 1000) before the cycle.")

IRS["C04"] = dict(lang="full", note="Calendar anchor + delay. Reference runner rejects the cron anchor; executed with anchor erased at 12:00.",
    ir={"timeline": [
        {"op": "start_at", "anchor": "cron", "cron": "0 12 * * *"},
        {"op": "call", "target": "Switch.On", "args": {}},
        {"op": "delay", "duration": "15 MIN"},
        {"op": "call", "target": "Switch.Off", "args": {}},
    ]})

IRS["C05"] = dict(lang="full", note=(
    "Sustain 2 min, then an inner cycle: send; wait up to 60 s for the door to close (E-TIMEOUT-ABORT with empty "
    "block = just continue). Inner `until` checks closed at each iteration start; a close during the 60 s makes the "
    "wait succeed at once, so the next until-check exits without sending. Nested cycle: frontend may refuse."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
            {"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "none", "for": "2 MIN"},
            {"op": "cycle", "until": "ContactSensor.Contact == true", "period": "0 MSEC", "body": [
                {"op": "call", "target": "MessageSender.SendSms", "args": {"To": "owner", "Text": "Back door is open", "Subject": "door"}},
                {"op": "wait", "cond": "ContactSensor.Contact == true", "edge": "none", "timeout": "1 MIN"},
            ]},
        ]}]})
IRS["C05"]["history"] = ("v1 (2026-09-12): inner period 100 MSEC -> match 4/4 but exact 0/4 (100 ms added per iteration: 130.0, 190.1, "
    "250.2, ...). B audit: the body's 60 s timeout already carries the cadence, so v2 sets the inner period to 0 MSEC "
    "(E-ZERO-PERIOD). Expected after v2: exact 4/4.")

IRS["C07"] = dict(lang="full", note=(
    "Sustained conjunction (clock >= 22 and open) for 10 min; snapshot B0; outer cycle (count c, period 5 MIN = pause "
    "after the body) with until 'c >= 7 or closed'; inner blink cycle (count k, until 'k >= 10 or closed'). Each half-blink "
    "delay is a wait-for-close with 500 ms timeout, so a close interrupts at the exact instant and the following "
    "restore(B0) is emitted then. After the inner loop the restore is emitted once; a close during the pause exits at "
    "the next until-check with no ACTION. Nested cycles and count/until on the same cycle: frontend may refuse."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "wait", "cond": "Clock.Hour >= 22 and ContactSensor.Contact == false", "edge": "none", "for": "10 MIN"},
        {"op": "read", "var": "b0", "src": "Light.CurrentBrightness"},
        {"op": "cycle", "until": "c >= 7 or ContactSensor.Contact == true", "period": "5 MIN", "count": "c", "body": [
            {"op": "cycle", "until": "k >= 10 or ContactSensor.Contact == true", "period": "0 MSEC", "count": "k", "body": [
                {"op": "call", "target": "Light.MoveToBrightness", "args": {"Brightness": 10, "Rate": 0}},
                {"op": "wait", "cond": "ContactSensor.Contact == true", "edge": "none", "timeout": "500 MSEC", "on_timeout": [
                    {"op": "call", "target": "Light.MoveToBrightness", "args": {"Brightness": 100, "Rate": 0}},
                    {"op": "wait", "cond": "ContactSensor.Contact == true", "edge": "none", "timeout": "500 MSEC", "on_timeout": [NOOP]},
                ]},
            ]},
            {"op": "call", "target": "Light.MoveToBrightness", "args": {"Brightness": "$b0", "Rate": 0}},
        ]}]})
IRS["C07"]["history"] = ("v1 (2026-09-12): both half-blink timeouts 500 ms -> 1/4; each blink iteration took 1.1 s because cycle.period is "
    "waited AFTER the body, so 10 blinks drifted 1 s and the next cycle started 1.1 s late. v2 sets the second timeout to "
    "400 ms so body + period = 1.0 s -> match 4/4, exact 3/4: the restore after a close during blinking was up to 100 ms "
    "late because the inner period ran after the body. B audit: v3 uses 500 ms + 500 ms and inner period 0 MSEC "
    "(E-ZERO-PERIOD), so blink cadence stays 1 s and a close is answered at its own instant. Expected after v3: exact 4/4.")

IRS["C09"] = dict(lang="full", note=(
    "Rising presence -> Lock, forever. The contract fires a rising-edge wait when its condition is already true at "
    "first evaluation, so an initial wait for absence is needed to make 'present at start' a non-event."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "wait", "cond": "PresenceSensor.Presence == false", "edge": "none"},
        {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
            {"op": "wait", "cond": "PresenceSensor.Presence == true", "edge": "rising"},
            {"op": "call", "target": "DoorLock.Lock", "args": {}},
        ]}]})
IRS["C09"]["history"] = "v1 (2026-09-12): no leading wait -> Lock at t=0 in 'present_at_start' (initial-true edge fires). v2 adds wait(absent)."

IRS["C11"] = dict(lang="full", note=(
    "Two reactions in one flow via E-PREV: poll every 100 ms; the previous iteration's snapshots decide which input "
    "changed. Both `if`s may fire in one iteration (both changed together), in the required order. Does not spawn "
    "two flows; whether this is 'the same behavior' as two TAP rules is the audit's call (B2)."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "read", "var": "v_prev", "src": "RobotVacuumCleaner.RobotVacuumCleanerOperatingState"},
        {"op": "read", "var": "c_prev", "src": "WindowCovering.CurrentPosition"},
        {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
            {"op": "if", "cond": ("RobotVacuumCleaner.RobotVacuumCleanerOperatingState == \"running\" and WindowCovering.CurrentPosition > 0 "
                                  "and $v_prev != \"running\""),
             "then": [{"op": "call", "target": "WindowCovering.DownOrClose", "args": {}}]},
            {"op": "if", "cond": ("RobotVacuumCleaner.RobotVacuumCleanerOperatingState == \"running\" and WindowCovering.CurrentPosition > 0 "
                                  "and $c_prev == 0"),
             "then": [{"op": "call", "target": "RobotVacuumCleaner.SetRobotVacuumCleanerRunMode", "args": {"Mode": "idle"}}]},
            {"op": "read", "var": "v_prev", "src": "RobotVacuumCleaner.RobotVacuumCleanerOperatingState"},
            {"op": "read", "var": "c_prev", "src": "WindowCovering.CurrentPosition"},
        ]}]})

IRS["C15"] = dict(lang="full", note=(
    "Rising presence, then branch on the night window; only then On / wait absent / Off. Putting the clock inside the "
    "rising condition would fire at 22:00 for someone already in the room, which the contract rejects."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
            {"op": "wait", "cond": "PresenceSensor.Presence == true", "edge": "rising"},
            {"op": "if", "cond": "Clock.Hour >= 22 or Clock.Hour < 6", "then": [
                {"op": "call", "target": "Switch.On", "args": {}},
                {"op": "wait", "cond": "PresenceSensor.Presence == false", "edge": "none"},
                {"op": "call", "target": "Switch.Off", "args": {}},
            ]},
        ]}]})

IRS["C16"] = dict(lang="full", note="Cron anchor + one-shot branch. Two Switch binding slots (read on light, call on TV). Executed with anchor erased at 22:00.",
    ir={"timeline": [
        {"op": "start_at", "anchor": "cron", "cron": "0 22 * * *"},
        {"op": "if", "cond": "ContactSensor.Contact == true and Switch.Switch == false", "then": [
            {"op": "call", "target": "Switch.Off", "args": {}},
        ]},
    ]})

IRS["C18"] = dict(lang="full", note="Rising 'pushed' event, hour-window branch, unlock/delay/lock. Presses during the delay are unobserved.",
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
            {"op": "wait", "cond": "Button.Button == \"pushed\"", "edge": "rising"},
            {"op": "if", "cond": "Clock.Hour == 15", "then": [
                {"op": "call", "target": "DoorLock.Unlock", "args": {}},
                {"op": "delay", "duration": "10 SEC"},
                {"op": "call", "target": "DoorLock.Lock", "args": {}},
            ]},
        ]}]})

IRS["C19"] = dict(lang="full", note=(
    "Wait for absence first (a presence already true at 06:00 is not an arrival), then race arrival against 09:00 as a "
    "disjunctive wait. The race itself enforces the deadline: at 09:00:00 the wait fires with the clock, so a later "
    "arrival never reaches the branch; the branch only needs 'present'. Cron anchor erased at 06:00."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "cron", "cron": "0 6 * * *"},
        {"op": "wait", "cond": "PresenceSensor.Presence == false", "edge": "none"},
        {"op": "wait", "cond": "PresenceSensor.Presence == true or Clock.Hour >= 9", "edge": "none"},
        {"op": "if", "cond": "PresenceSensor.Presence == true", "then": [
            {"op": "call", "target": "EmailProvider.SendMail", "args": {"ToAddress": "me@example.com", "Title": "On time", "Body": "I got to work on time!"}},
        ]},
    ]})
IRS["C19"]["history"] = ("v1 (2026-09-12): no leading absence wait; branch 'Hour < 9 or (Hour == 9 and Minute == 0)' claimed as a "
    "minute-resolution approximation (lang=partial), match 3/3. B audit: that explanation was wrong (the race already ends at "
    "09:00:00, so 09:00:30 never passes); the real defect was treating a presence already true at start as an arrival. v2 "
    "adds wait(absent) first, simplifies the branch to 'present', lang=full; two histories added to cases.py.")

IRS["C20"] = dict(lang="full", note=(
    "ORDERED variant only (the case is defined as the 'AND AFTERWARDS' sentence; B audit 2026-09-12). The paired unordered "
    "variant requires look-back event memory and is excluded from this ordered-variant case (Stage B limitation candidate, B3). Rising entry opens the window; then wait (rising) for 'dark or left' with a 2 h timeout "
    "(E-TIMEOUT-ABORT). Leaving ends the window; a later re-entry opens a new one, which coincides with 'restart on "
    "re-entry' for entries that require a leave first. 'Dark already before entry' must NOT fire: relies on the edge "
    "latch not firing on an initially-true condition. The UNORDERED (look-back) variant is not encoded: B3."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
            {"op": "wait", "cond": "PresenceSensor.Presence == true", "edge": "rising"},
            {"op": "if", "cond": "LightSensor.Brightness >= 50", "then": [
                {"op": "wait", "cond": "LightSensor.Brightness < 50 or PresenceSensor.Presence == false", "edge": "rising",
                 "timeout": "2 HOUR", "on_timeout": [NOOP]},
                {"op": "if", "cond": "LightSensor.Brightness < 50 and PresenceSensor.Presence == true", "then": [
                    {"op": "call", "target": "Switch.On", "args": {}},
                ]},
            ]},
        ]}]})
IRS["C20"]["history"] = ("v1 (2026-09-12): no guard -> On at the entry instant when it was already dark (initial-true edge fires). "
    "v2 guards the window with 'bright at entry'.")
