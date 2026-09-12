"""E1 boundary probes — attempted Timeline encodings.

Written AFTER probes.py was hashed (sha256 9ffee57593f6731e3216b6b23af1792c7a59ff86c1ad87b9b754ac4a5b219e1c).
The requirements and expected traces in probes.py were not edited to fit these attempts.

Per README §2 a probe is not declared unrepresentable until composition has actually been tried.
Each entry records every attempt, including the ones that were refused or that diverged, so the
verdict rests on attempts rather than on the absence of a keyword.

Encoding devices used here (in addition to those documented in irs.py):
  E-PREV      previous-iteration snapshot via `read`, to tell which input changed (also used by C11).
  E-STAMP     `read t from Clock.Timestamp` at the instant an event is observed, so a later iteration
              can test `Clock.Timestamp - $t <= W`. Clock.Timestamp is whole seconds
              (explorer.runtime.interp.clock_state: now_ms // 1000), so window tests are second-resolution.
  E-NULL      an unread variable is null; `$t != null` therefore distinguishes "this event has not
              happened yet". This behaviour is NOT stated in VERIFICATION_CONTRACT.md and null is not in
              the extractor grammar — see README §7. Arithmetic on null coerces to 0, so the null test
              must be written explicitly; `Clock.Timestamp - $unset <= W` alone is not a correct guard.
"""

ATTEMPTS = {}

# ─────────────────────────────────────────────────────────────────────────────
# P1  unordered look-back pairing (B3)
# ─────────────────────────────────────────────────────────────────────────────
ATTEMPTS["P1"] = dict(
    lang="full", verdict_claim="완전",
    note=("E-PREV + E-STAMP + E-NULL. One polling flow wakes on any change of either input, records the "
          "timestamp of whichever event just occurred, and tests it against the stored timestamp of the other "
          "event kind. Symmetric, so order does not matter, and the stored timestamp is not consumed, so one "
          "sunset can pair with several later entries."),
    history=("v1 (race encoding) was written first: wait for the rising edge of `Presence == true or Brightness < 50`, "
             "branch on whichever is true, then wait for the other with a 2 HOUR timeout. Executed: 3/4 histories. "
             "It fails `one_sunset_two_entries` — after the first pairing the disjunction is still true (it is still "
             "dark), so the loop's rising edge never fires again and the second entry at 6600 s produces no ACTION. "
             "v2 replaces the edge wait with the snapshot pattern below, which holds no latch."),
    explorer=("REFUSED: 'explicit input domain required for observable large/unbounded catalog value'. Reading the raw "
              "DOUBLE brightness into $b_prev makes the value itself observable, so the Explorer fail-closes instead of "
              "certifying. The language and the reference runner accept the encoding; the verifier does not."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "read", "var": "p_prev", "src": "PresenceSensor.Presence"},
            {"op": "read", "var": "b_prev", "src": "LightSensor.Brightness"},
            {"op": "wait", "cond": "PresenceSensor.Presence != $p_prev or LightSensor.Brightness != $b_prev",
             "edge": "none"},
            {"op": "if", "cond": "PresenceSensor.Presence == true and $p_prev == false", "then": [
                {"op": "read", "var": "t_entry", "src": "Clock.Timestamp"},
                {"op": "if", "cond": "$t_sunset != null and $t_entry - $t_sunset <= 7200",
                 "then": [{"op": "call", "target": "Switch.On", "args": {}}]},
            ]},
            {"op": "if", "cond": "LightSensor.Brightness < 50 and $b_prev >= 50", "then": [
                {"op": "read", "var": "t_sunset", "src": "Clock.Timestamp"},
                {"op": "if", "cond": "$t_entry != null and $t_sunset - $t_entry <= 7200",
                 "then": [{"op": "call", "target": "Switch.On", "args": {}}]},
            ]},
        ]}]})

# ─────────────────────────────────────────────────────────────────────────────
# P2  "door opened within the last x minutes" (B3)
# ─────────────────────────────────────────────────────────────────────────────
ATTEMPTS["P2"] = dict(
    lang="full", verdict_claim="완전",
    note=("Same E-PREV + E-STAMP + E-NULL pattern. The door-open timestamp is overwritten by each new opening, "
          "which is what the requirement's sliding window needs, and the motion branch re-tests it on every "
          "motion, so several motions inside one window each send."),
    scope_limit=("This covers only openings the automation observes WHILE RUNNING. The execution model gives t=0 the "
                 "current value of each input and has no way to state that the door opened before t=0, so an opening "
                 "inside the ten minutes preceding start is invisible and cannot even be written as a history. "
                 "Home Assistant answers that case because the platform stores each entity's last_changed "
                 "independently of any automation, which is how the thread's own reply solves it "
                 "(`as_timestamp(states.cover.garage_door.last_changed)`). So the verdict is: remembering events "
                 "that happen during the run is expressible; pre-start history is outside the model, not merely "
                 "outside Timeline."),
    history=("v1 measured the window with a `wait(motion rising, timeout \"10 MIN\")` restarted per motion inside the "
             "door-open loop. Executed: 3/4 histories. It measures ten minutes from the previous motion rather than "
             "from the opening, because a wait's timeout restarts with the wait and the remaining time cannot be "
             "computed (durations are compile-time literals, see P3). On `open_then_motions_in_and_out` it emits a "
             "third SMS at 960 s, which is 11 min after the opening but only 4 min after the previous motion. "
             "v2 uses the timestamp test below."),
    explorer=("REFUSED: 'joint-guard: ((clock.timestamp - $t_open) <= 600)' is listed fail-closed as an unsupported "
              "pattern. The look-back window that makes this requirement expressible is outside the fragment the "
              "Explorer certifies."),
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "read", "var": "c_prev", "src": "ContactSensor.Contact"},
            {"op": "read", "var": "m_prev", "src": "MotionSensor.Motion"},
            {"op": "wait", "cond": "ContactSensor.Contact != $c_prev or MotionSensor.Motion != $m_prev",
             "edge": "none"},
            {"op": "if", "cond": "ContactSensor.Contact == false and $c_prev == true",
             "then": [{"op": "read", "var": "t_open", "src": "Clock.Timestamp"}]},
            {"op": "if", "cond": ("MotionSensor.Motion == true and $m_prev == false and $t_open != null "
                                  "and Clock.Timestamp - $t_open <= 600"),
             "then": [{"op": "call", "target": "MessageSender.SendSms",
                       "args": {"To": "owner", "Text": "Motion near the front door", "Subject": "door"}}]},
        ]}]})

# ─────────────────────────────────────────────────────────────────────────────
# P3  variable repetition interval (B4)
# ─────────────────────────────────────────────────────────────────────────────
# Attempt A is kept as executable data so the refusal is reproduced by run_probes.py rather than quoted.
P3_ATTEMPT_A = {"timeline": [
    {"op": "start_at", "anchor": "now"},
    {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
        {"op": "read", "var": "i_min", "src": "LevelControl.CurrentLevel"},
        {"op": "read", "var": "d_min", "src": "LevelControl.CurrentLevel"},   # second read -> slot LevelControl#2 by walk order
        {"op": "call", "target": "Switch.On", "args": {}},
        {"op": "delay", "duration": "$d_min MIN"},
        {"op": "call", "target": "Switch.Off", "args": {}},
        {"op": "delay", "duration": "$i_min MIN"},
    ]}]}

ATTEMPTS["P3"] = dict(
    lang="full", verdict_claim="완전 (단위 해상도)",
    missing=("nothing in the language. A duration OPERAND cannot be read at run time — `delay.duration`, `wait.for`, "
             "`wait.timeout` and `cycle.period` are all resolved by explorer.runtime.ir_step.parse_duration at compile "
             "time — but a variable-length WAIT is still expressible, because `cycle.until` does accept a variable and "
             "arithmetic. Attempt C below waits `$n` units by iterating a one-unit `delay` until the loop counter "
             "reaches `$n`."),
    note=("Attempt C: `cycle(until \"k >= $d_min\", count \"k\"){ delay \"1 MIN\" }` waits d_min minutes, where "
          "d_min was read from the device at the start of the outer iteration. The same shape waits (i_min - d_min) "
          "minutes for the rest of the period. Cost and resolution: the loop runs one iteration per unit, so the unit "
          "chosen (1 MIN here, 1 SEC or 100 MSEC for finer control) sets both the granularity of the interval and the "
          "number of states. This is unrolling, not a variable duration operand."),
    history=("Attempt A writes the durations as variables, exactly as the requirement states them. The reference "
             "runner refuses it at compile time with `Unsupported: duration format: '$d_min MIN'`; run_probes.py "
             "reproduces the message rather than quoting it. Attempt B fixed both settings at their initial literal "
             "values (period 15 MIN after a 5 MIN body) and scored 1/3: it cannot follow a setting change. "
             "Enumerating the settings with one literal delay per branch was rejected as an approach because "
             "LevelControl.CurrentLevel is typed DOUBLE, so the branch set is not finite. Attempt C, the reported "
             "encoding, waits a variable number of units with a counted loop and scores 3/3 exact. "
             "Note on the expected traces: `interval_changed_to_10` originally listed 8 ACTIONs; re-deriving it from "
             "the requirement text showed it had omitted the On at the 60 min horizon, and probes.py was corrected "
             "after the hash with that reason recorded in README §6. The correction was derived from the requirement, "
             "not from any encoding, and attempt B still scores 1/3 against the corrected trace."),
    attempt_a=P3_ATTEMPT_A,
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "0 MSEC", "body": [
            {"op": "read", "var": "i_min", "src": "LevelControl.CurrentLevel"},
            {"op": "read", "var": "d_min", "src": "LevelControl.CurrentLevel"},   # second read -> slot #2 by walk order
            {"op": "call", "target": "Switch.On", "args": {}},
            {"op": "cycle", "until": "k >= $d_min", "period": "0 MSEC", "count": "k",
             "body": [{"op": "delay", "duration": "1 MIN"}]},
            {"op": "call", "target": "Switch.Off", "args": {}},
            {"op": "cycle", "until": "j >= $i_min - $d_min", "period": "0 MSEC", "count": "j",
             "body": [{"op": "delay", "duration": "1 MIN"}]},
        ]}]})
