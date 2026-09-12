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
    lang="partial", verdict_claim="부분",
    missing=("a duration operand that is read at run time. `delay.duration`, `wait.for`, `wait.timeout` and "
             "`cycle.period` are all resolved by explorer.runtime.ir_step.parse_duration at compile time and accept "
             "only a literal number or '<n> <UNIT>' string."),
    note=("Attempt B below fixes the two settings at their initial values (20 min interval, 5 min on-time) and "
          "therefore reproduces the requirement only while the settings do not change. The body takes 5 min and "
          "cycle.period is waited after the body, so period 15 MIN gives a 20 min cadence."),
    history=("Attempt A writes the durations as variables, exactly as the requirement states them. The reference "
             "runner refuses it at compile time with `Unsupported: duration format: '$d_min MIN'`; run_probes.py "
             "reproduces the message rather than quoting it. Attempt C, enumerating the "
             "possible settings with nested `if` branches and a literal delay per branch, is not written out: "
             "LevelControl.CurrentLevel is typed DOUBLE in the service catalog, so the branch set is not finite. "
             "Attempt B is the closest encoding that compiles."),
    explorer=("EQUIV-FIXPOINT on attempt B. A constant-cadence loop is inside the certified fragment; the refusal is "
              "in the language, not in the verifier."),
    attempt_a=P3_ATTEMPT_A,
    ir={"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "cycle", "until": None, "period": "15 MIN", "body": [
            {"op": "call", "target": "Switch.On", "args": {}},
            {"op": "delay", "duration": "5 MIN"},
            {"op": "call", "target": "Switch.Off", "args": {}},
        ]}]})
