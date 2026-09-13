"""E2 pairs on the E1 20 base IRs — hand-written JoI implementations and single-change faults.

Written for E2 before any reference or Explorer run on these pairs (protocol §2, "Scale").
Built and validated by build_e1_pairs.py.

Conventions
- Correct implementations follow the JoI lowering idioms in files/joi_cycle.md (rising-edge flag, tick
  counters for sustained conditions and timeouts, phase variables). Where an IR cycle has a 100 MSEC period,
  the JoI period is 100 ms; tick counters therefore count 100 ms steps. Blocking statements appear only at top
  level of one-shot scripts or nested in `if` of periodic scripts (never inside `loop`).
- Selectors use tags ending in the category tag. `retag` changes only the tag lists of the E2 device inventory
  where the E1 inventory had no tag combination that selects the intended devices (IR binding is by device ID and
  is unaffected).
- A fault is (family, description, old, new[, count]): `old` must occur exactly `count` times (default 1) and
  every occurrence is replaced. The label of each pair comes from the reference, not from this intent.
"""
from textwrap import dedent


def J(s):
    return dedent(s).strip("\n")


BASES = []

# ─────────────────────────────────────────────────────────────── Stage A
BASES.append(dict(id="C01", case="C01", period=100, script=J("""
    armed := true
    state := 0
    ticks := 0
    m = (#Hallway #MotionSensor).Motion
    if (state == 0) {
        if (m == true) {
            if (armed == true) {
                (#Hallway #Switch).On()
                armed = false
                state = 1
            }
        } else {
            armed = true
        }
    } else if (state == 1) {
        if (m == false) {
            state = 2
            ticks = 0
        }
    } else {
        ticks = ticks + 1
        if (m == true) {
            (#Hallway #Switch).On()
            state = 1
        } else if (ticks >= 1200) {
            (#Hallway #Switch).Off()
            state = 0
        }
    }
    """), faults=[
    ("timing", "no-motion wait 60 s instead of 120 s", "ticks >= 1200", "ticks >= 600"),
    ("sustain-reset", "no-motion timer not restarted when a new no-motion period begins",
     "        state = 2\n        ticks = 0\n", "        state = 2\n"),
    ("edge-rearm", "rising-edge flag never re-armed", "    } else {\n        armed = true\n    }\n", "    }\n"),
    ("missing-call", "no On when motion returns during the wait",
     "        (#Hallway #Switch).On()\n        state = 1\n", "        state = 1\n"),
]))

BASES.append(dict(id="C03", case="C03", period=100, script=J("""
    ready := false
    armed := false
    c = (#Office #CarbonDioxideSensor).CarbonDioxide
    if (ready == false) {
        if (c <= 1000) {
            ready = true
            armed = true
        }
    } else if (c > 1000) {
        if (armed == true) {
            (#Office #Switch).On()
            delay(15 MIN)
            (#Office #Switch).Off()
            armed = false
        }
    } else {
        armed = true
    }
    """), faults=[
    ("timing", "fan runs 10 min instead of 15", "delay(15 MIN)", "delay(10 MIN)"),
    ("missing-call", "no Off", "        (#Office #Switch).Off()\n", ""),
    ("edge-rearm", "never re-armed after the first run", "} else {\n    armed = true\n}", "}"),
    ("order", "Off before On",
     "(#Office #Switch).On()\n        delay(15 MIN)\n        (#Office #Switch).Off()",
     "(#Office #Switch).Off()\n        delay(15 MIN)\n        (#Office #Switch).On()"),
]))

BASES.append(dict(id="C04", case="C04", period=0, script=J("""
    (#Office #Switch).On()
    delay(15 MIN)
    (#Office #Switch).Off()
    """), faults=[
    ("timing", "16 min instead of 15", "delay(15 MIN)", "delay(16 MIN)"),
    ("missing-call", "no Off", "\n(#Office #Switch).Off()", ""),
    ("order", "Off before On", "(#Office #Switch).On()\ndelay(15 MIN)\n(#Office #Switch).Off()",
     "(#Office #Switch).Off()\ndelay(15 MIN)\n(#Office #Switch).On()"),
    ("extra-call", "Off issued twice", "(#Office #Switch).Off()", "(#Office #Switch).Off()\n(#Office #Switch).Off()"),
]))

BASES.append(dict(id="C05", case="C05", period=100, script=J("""
    state := 0
    ticks := 0
    c = (#Back #ContactSensor).Contact
    if (state == 0) {
        if (c == false) {
            ticks = ticks + 1
            if (ticks > 1200) {
                (#Owner #MessageSender).SendSms("owner", "Back door is open", "door")
                state = 1
                ticks = 0
            }
        } else {
            ticks = 0
        }
    } else {
        if (c == true) {
            state = 0
            ticks = 0
        } else {
            ticks = ticks + 1
            if (ticks >= 600) {
                (#Owner #MessageSender).SendSms("owner", "Back door is open", "door")
                ticks = 0
            }
        }
    }
    """), faults=[
    ("timing", "first alert after 60 s open instead of 120 s", "ticks > 1200", "ticks > 600"),
    ("sustain-reset", "open-time counter not reset when the door closes before 2 min",
     "    } else {\n        ticks = 0\n    }\n} else {", "    }\n} else {"),
    ("repetition-state", "repeat counter carried over after the door closes",
     "        state = 0\n        ticks = 0\n", "        state = 0\n"),
    ("missing-call", "no repeated alerts",
     '            (#Owner #MessageSender).SendSms("owner", "Back door is open", "door")\n            ticks = 0\n        }\n    }\n}',
     "            ticks = 0\n        }\n    }\n}"),
]))

BASES.append(dict(id="C07", case="C07", period=100, script=J("""
    phase := 0
    ticks := 0
    k := 0
    c := 0
    b0 := 0
    closed = (#Garage #ContactSensor).Contact
    h = (#Clock).Hour
    if (phase == 0) {
        if (h >= 22 and closed == false) {
            ticks = ticks + 1
            if (ticks > 6000) {
                b0 = (#Kitchen #Light).CurrentBrightness
                (#Kitchen #Light).MoveToBrightness(10, 0)
                phase = 1
                ticks = 0
                k = 0
                c = 0
            }
        } else {
            ticks = 0
        }
    } else if (phase == 1) {
        ticks = ticks + 1
        if (closed == true) {
            (#Kitchen #Light).MoveToBrightness(b0, 0)
            c = c + 1
            ticks = 0
            if (c >= 7) {
                phase = 3
            } else {
                phase = 2
            }
        } else if (ticks == 5) {
            (#Kitchen #Light).MoveToBrightness(100, 0)
        } else if (ticks == 10) {
            k = k + 1
            ticks = 0
            if (k >= 10) {
                (#Kitchen #Light).MoveToBrightness(b0, 0)
                c = c + 1
                if (c >= 7) {
                    phase = 3
                } else {
                    phase = 2
                }
            } else {
                (#Kitchen #Light).MoveToBrightness(10, 0)
            }
        }
    } else if (phase == 2) {
        ticks = ticks + 1
        if (ticks == 3000) {
            if (closed == true) {
                phase = 3
            } else {
                (#Kitchen #Light).MoveToBrightness(10, 0)
                phase = 1
                ticks = 0
                k = 0
            }
        }
    }
    """), faults=[
    ("timing", "bright half-step after 400 ms instead of 500 ms", "ticks == 5)", "ticks == 4)"),
    ("snapshot-value", "restores a fixed 100 instead of the brightness read at the start",
     "b0 = (#Kitchen #Light).CurrentBrightness", "b0 = 100"),
    ("repetition-state", "6 blink cycles instead of 7", "c >= 7", "c >= 6", 2),
    ("sustain-reset", "10-minute open timer not reset when the condition breaks",
     "    } else {\n        ticks = 0\n    }\n} else if (phase == 1) {", "    }\n} else if (phase == 1) {"),
]))

BASES.append(dict(id="C09", case="C09", period=100, script=J("""
    ready := false
    armed := false
    p = (#Entrance #PresenceSensor).Presence
    if (ready == false) {
        if (p == false) {
            ready = true
            armed = true
        }
    } else if (p == true) {
        if (armed == true) {
            (#Entrance #DoorLock).Lock()
            armed = false
        }
    } else {
        armed = true
    }
    """), faults=[
    ("edge-rearm", "locks only on the first arrival", "} else {\n    armed = true\n}", "}"),
    ("edge-rearm", "level instead of edge: locks every tick while present",
     "        (#Entrance #DoorLock).Lock()\n        armed = false\n", "        (#Entrance #DoorLock).Lock()\n"),
    ("extra-call", "Lock issued twice per arrival", "(#Entrance #DoorLock).Lock()",
     "(#Entrance #DoorLock).Lock()\n        (#Entrance #DoorLock).Lock()"),
    ("edge-at-start", "skips the initial absence check", "ready := false", "ready := true"),
]))

BASES.append(dict(id="C11", case="C11", period=100, script=J("""
    v_prev := (#LivingRoom #RobotVacuumCleaner).RobotVacuumCleanerOperatingState
    c_prev := (#LivingRoom #WindowCovering).CurrentPosition
    v = (#LivingRoom #RobotVacuumCleaner).RobotVacuumCleanerOperatingState
    c = (#LivingRoom #WindowCovering).CurrentPosition
    if (v == "running" and c > 0 and v_prev != "running") {
        (#LivingRoom #WindowCovering).DownOrClose()
    }
    if (v == "running" and c > 0 and c_prev == 0) {
        (#LivingRoom #RobotVacuumCleaner).SetRobotVacuumCleanerRunMode("idle")
    }
    v_prev = v
    c_prev = c
    """), faults=[
    ("order", "vacuum rule before curtain rule",
     'if (v == "running" and c > 0 and v_prev != "running") {\n    (#LivingRoom #WindowCovering).DownOrClose()\n}\n'
     'if (v == "running" and c > 0 and c_prev == 0) {\n    (#LivingRoom #RobotVacuumCleaner).SetRobotVacuumCleanerRunMode("idle")\n}',
     'if (v == "running" and c > 0 and c_prev == 0) {\n    (#LivingRoom #RobotVacuumCleaner).SetRobotVacuumCleanerRunMode("idle")\n}\n'
     'if (v == "running" and c > 0 and v_prev != "running") {\n    (#LivingRoom #WindowCovering).DownOrClose()\n}'),
    ("snapshot-value", "previous curtain position never updated", "\nc_prev = c", ""),
    ("missing-call", "curtain never closed", "    (#LivingRoom #WindowCovering).DownOrClose()\n", "    noop = 0\n"),
    ("guard", "curtain at position 0 counts as open", "c > 0 and v_prev", "c >= 0 and v_prev"),
]))

BASES.append(dict(id="C15", case="C15", period=100, script=J("""
    armed := true
    p = (#Bedroom #PresenceSensor).Presence
    if (p == true) {
        if (armed == true) {
            armed = false
            h = (#Clock).Hour
            if (h >= 22 or h < 6) {
                (#Bedroom #Switch).On()
                wait until((#Bedroom #PresenceSensor).Presence == false)
                (#Bedroom #Switch).Off()
            }
        }
    } else {
        armed = true
    }
    """), faults=[
    ("guard", "night window includes 06:xx", "h < 6", "h <= 6"),
    ("edge-rearm", "only the first entry is handled", "} else {\n    armed = true\n}", "}"),
    ("missing-call", "no Off on leaving", "            (#Bedroom #Switch).Off()\n", ""),
    ("timing", "Off 1 min after On instead of on leaving",
     "wait until((#Bedroom #PresenceSensor).Presence == false)", "delay(1 MIN)"),
]))

BASES.append(dict(id="C16", case="C16", period=0, cron="0 22 * * *", script=J("""
    if ((#Bedroom #ContactSensor).Contact == true and (#Light #Switch).Switch == false) {
        (#Television #Switch).Off()
    }
    """), faults=[
    ("target", "turns off the light instead of the TV", "(#Television #Switch).Off()", "(#Light #Switch).Off()"),
    ("guard", "or instead of and", "== true and", "== true or"),
    ("guard", "requires the light on instead of off", "Switch == false", "Switch == true"),
    ("extra-call", "also turns off the light", "(#Television #Switch).Off()",
     "(#Television #Switch).Off()\n    (#Light #Switch).Off()"),
]))

BASES.append(dict(id="C18", case="C18", period=100, script=J("""
    armed := true
    b = (#Entrance #Button).Button
    if (b == "pushed") {
        if (armed == true) {
            armed = false
            if ((#Clock).Hour == 15) {
                (#Entrance #DoorLock).Unlock()
                delay(10 SEC)
                (#Entrance #DoorLock).Lock()
            }
        }
    } else {
        armed = true
    }
    """), faults=[
    ("timing", "relocks after 5 s", "delay(10 SEC)", "delay(5 SEC)"),
    ("missing-call", "never relocks", "            (#Entrance #DoorLock).Lock()\n", ""),
    ("edge-rearm", "only the first press is handled", "} else {\n    armed = true\n}", "}"),
    ("guard", "any hour from 15 on", "Hour == 15", "Hour >= 15"),
]))

BASES.append(dict(id="C19", case="C19", period=0, cron="0 6 * * *", script=J("""
    wait until((#Office #PresenceSensor).Presence == false)
    wait until((#Office #PresenceSensor).Presence == true or (#Clock).Hour >= 9)
    if ((#Office #PresenceSensor).Presence == true) {
        (#Owner #EmailProvider).SendMail("me@example.com", "On time", "I got to work on time!")
    }
    """), faults=[
    ("edge-at-start", "presence already true at start counts as arrival",
     "wait until((#Office #PresenceSensor).Presence == false)\n", ""),
    ("timing", "deadline 10:00 instead of 09:00", "Hour >= 9)", "Hour >= 10)"),
    ("guard", "mail also sent when late", "if ((#Office #PresenceSensor).Presence == true) {",
     "if ((#Office #PresenceSensor).Presence == true or (#Clock).Hour >= 9) {"),
]))

BASES.append(dict(id="C20-O", case="C20-O", period=100, script=J("""
    armed := true
    state := 0
    ticks := 0
    p = (#Bedroom #PresenceSensor).Presence
    lux = (#Outdoor #LightSensor).Brightness
    if (state == 0) {
        if (p == true) {
            if (armed == true) {
                armed = false
                if (lux >= 50) {
                    state = 1
                    ticks = 0
                }
            }
        } else {
            armed = true
        }
    } else {
        ticks = ticks + 1
        if (lux < 50 or p == false) {
            if (lux < 50 and p == true) {
                (#Bedroom #Switch).On()
            }
            state = 0
        } else if (ticks >= 72000) {
            state = 0
        }
    }
    """), faults=[
    ("timing", "1-hour window instead of 2 hours", "ticks >= 72000", "ticks >= 36000"),
    ("edge-rearm", "only the first entry opens a window", "    } else {\n        armed = true\n    }", "    }"),
    ("guard", "window opens even when already dark", "lux >= 50", "lux >= 0"),
    ("guard", "leaving does not end the window", "lux < 50 or p == false", "lux < 50"),
]))

# ─────────────────────────────────────────────────────────────── depth v2
BASES.append(dict(id="E1-092-A", case="E1-092", automation="A_alexa", period=0, script=J("""
    wait until((#Home #House).ShutdownRequested == true)
    (#LivingRoom #Alexa).AnnounceTasks()
    delay(1 SEC)
    (#LivingRoom #Alexa).AnnounceNews()
    delay(1 SEC)
    (#LivingRoom #Alexa).AnnounceAlarmSettings()
    """), note="E1 JoI block alexa_flow (depth_attempts.py), unchanged.", faults=[
    ("extra-call", "news announced twice", "(#LivingRoom #Alexa).AnnounceNews()",
     "(#LivingRoom #Alexa).AnnounceNews()\n(#LivingRoom #Alexa).AnnounceNews()"),
    ("timing", "alarm settings 2 s after news", "delay(1 SEC)\n(#LivingRoom #Alexa).AnnounceAlarmSettings()",
     "delay(2 SEC)\n(#LivingRoom #Alexa).AnnounceAlarmSettings()"),
    ("order", "news before tasks", "(#LivingRoom #Alexa).AnnounceTasks()\ndelay(1 SEC)\n(#LivingRoom #Alexa).AnnounceNews()",
     "(#LivingRoom #Alexa).AnnounceNews()\ndelay(1 SEC)\n(#LivingRoom #Alexa).AnnounceTasks()"),
]))

BASES.append(dict(id="E1-092-B", case="E1-092", automation="B_house", period=0, script=J("""
    wait until((#Home #House).ShutdownRequested == true)
    (#Downstairs #Lights).Off("downstairs")
    delay(1 SEC)
    (#Entrance #Locks).Lock("front, back")
    delay(1 SEC)
    (#Home #Alarm).Set("armed")
    """), note="E1 JoI block house_flow (depth_attempts.py), unchanged.", faults=[
    ("missing-call", "alarm never set", '\ndelay(1 SEC)\n(#Home #Alarm).Set("armed")', ""),
    ("order", "locks before lights", '(#Downstairs #Lights).Off("downstairs")\ndelay(1 SEC)\n(#Entrance #Locks).Lock("front, back")',
     '(#Entrance #Locks).Lock("front, back")\ndelay(1 SEC)\n(#Downstairs #Lights).Off("downstairs")'),
    ("argument", "alarm mode away instead of armed", '"armed"', '"away"'),
]))

BASES.append(dict(id="E1-095", case="E1-095", period=1000, retag={"Pool_Report": ["Report", "Pool"]}, script=J("""
    sum_ph := 0
    sum_cl := 0
    count := 0
    last_hour := -1
    h = (#Clock).Hour
    if (h >= 10 and h <= 14 and h != last_hour) {
        sum_ph = sum_ph + (#Pool #PoolPH).Value
        sum_cl = sum_cl + (#Pool #PoolChlorine).Value
        count = count + 1
        last_hour = h
    }
    if (h == 15 and count > 0) {
        (#Report #Pool).ReportDailyQuality(sum_ph / count, sum_cl / count)
        sum_ph = 0
        sum_cl = 0
        count = 0
    }
    """), note="E1 JoI v3 accumulator (depth_attempts.py) with the report selector retagged; an accumulator idiom against the IR's five snapshots.",
    faults=[
    ("repetition-state", "samples 10-13 h only", "h <= 14", "h <= 13"),
    ("timing", "report at 16 h", "h == 15", "h == 16"),
    ("argument", "pH and chlorine means swapped", "sum_ph / count, sum_cl / count", "sum_cl / count, sum_ph / count"),
    ("snapshot-value", "pH keeps only the last sample", "sum_ph = sum_ph + (#Pool #PoolPH).Value", "sum_ph = (#Pool #PoolPH).Value"),
]))

BASES.append(dict(id="E1-086", case="E1-086", period=100, script=J("""
    phase := 0
    ticks := 0
    r = (#Garden #Switch).Switch
    if (phase == 0) {
        if (r == true) {
            (#Zone1 #Valve).Open()
            phase = 1
            ticks = 0
        }
    } else if (phase == 1) {
        ticks = ticks + 1
        if (r == false) {
            (#Zone1 #Valve).Close()
            (#Zone2 #Valve).Close()
            break
        } else if (ticks >= 6000) {
            (#Zone1 #Valve).Close()
            phase = 2
            ticks = 0
        }
    } else if (phase == 2) {
        ticks = ticks + 1
        if (r == false) {
            (#Zone1 #Valve).Close()
            (#Zone2 #Valve).Close()
            break
        } else if (ticks >= 300) {
            (#Zone2 #Valve).Open()
            phase = 3
            ticks = 0
        }
    } else {
        ticks = ticks + 1
        if (r == false) {
            (#Zone1 #Valve).Close()
            (#Zone2 #Valve).Close()
            break
        } else if (ticks >= 6000) {
            (#Zone2 #Valve).Close()
            break
        }
    }
    """), faults=[
    ("missing-call", "cancel during zone 1 leaves zone 2 command out",
     "        (#Zone1 #Valve).Close()\n        (#Zone2 #Valve).Close()\n        break\n    } else if (ticks >= 6000) {\n        (#Zone1 #Valve).Close()",
     "        (#Zone1 #Valve).Close()\n        break\n    } else if (ticks >= 6000) {\n        (#Zone1 #Valve).Close()"),
    ("timing", "60 s gap instead of 30 s", "ticks >= 300", "ticks >= 600"),
    ("order", "cancel during zone 2 closes zone 2 first",
     "        (#Zone1 #Valve).Close()\n        (#Zone2 #Valve).Close()\n        break\n    } else if (ticks >= 6000) {\n        (#Zone2 #Valve).Close()",
     "        (#Zone2 #Valve).Close()\n        (#Zone1 #Valve).Close()\n        break\n    } else if (ticks >= 6000) {\n        (#Zone2 #Valve).Close()"),
    ("guard", "switch-off ignored during the gap",
     "    if (r == false) {\n        (#Zone1 #Valve).Close()\n        (#Zone2 #Valve).Close()\n        break\n    } else if (ticks >= 300) {",
     "    if (ticks >= 300) {"),
]))

_P1_099 = J("""
    if (phase == 1) {
        if (mo == true) {
            t_m = ts
            has_m = true
            phase = 2
        } else if (ts >= t_on + 300 + 120 * k) {
            if (has_m == false or ts - t_m >= 120) {
                (#Hall #Switch).Off()
            }
            phase = 0
        }
    }
    """)
BASES.append(dict(id="E1-099", case="E1-099", period=100, script="\n".join([J("""
    armed := true
    phase := 0
    t_on := 0
    t_m := 0
    has_m := false
    k := 0
    s = (#Hall #Switch).Switch
    mo = (#Hall #MotionSensor).Motion
    ts = (#Clock).Timestamp
    if (phase == 2) {
        if (mo == false) {
            k = k + 1
            phase = 1
        }
    }
    """), _P1_099, J("""
    if (phase == 0) {
        if (s == true) {
            if (armed == true) {
                armed = false
                t_on = ts
                k = 0
                phase = 1
            }
        } else {
            armed = true
        }
    }
    """), _P1_099]),
    note=("The phase-1 block appears twice so that a switch to phase 1 is evaluated in the same tick, as the IR evaluates "
          "the next wait at the same instant."),
    faults=[
    ("repetition-state", "motion does not extend the deadline", "ts >= t_on + 300 + 120 * k", "ts >= t_on + 300", 2),
    ("guard", "turns off even with motion in the last 2 minutes", "if (has_m == false or ts - t_m >= 120) {",
     "if (has_m == false or has_m == true) {", 2),
    ("order", "deadline tested before motion (v1 behaviour)",
     "    if (mo == true) {\n        t_m = ts\n        has_m = true\n        phase = 2\n    } else if (ts >= t_on + 300 + 120 * k) {\n"
     "        if (has_m == false or ts - t_m >= 120) {\n            (#Hall #Switch).Off()\n        }\n        phase = 0\n    }",
     "    if (ts >= t_on + 300 + 120 * k) {\n        if (has_m == false or ts - t_m >= 120) {\n            (#Hall #Switch).Off()\n"
     "        }\n        phase = 0\n    } else if (mo == true) {\n        t_m = ts\n        has_m = true\n        phase = 2\n    }", 2),
    ("edge-rearm", "only the first manual switch-on is handled", "    } else {\n        armed = true\n    }", "    }"),
]))

BASES.append(dict(id="E1-028", case="E1-028", period=100, script=J("""
    armed := true
    slot := 0
    has_a := false
    has_b := false
    ta := 0
    tb := 0
    req = (#Kitchen #Feeder).DispenseRequested
    ts = (#Clock).Timestamp
    if (req == true) {
        if (armed == true) {
            armed = false
            if (has_a == false or ts - ta >= 14400 or has_b == false or ts - tb >= 14400) {
                (#Kitchen #Feeder).Dispense("one_bowl")
                if (slot == 0) {
                    ta = ts
                    has_a = true
                    slot = 1
                } else {
                    tb = ts
                    has_b = true
                    slot = 0
                }
            }
        }
    } else {
        armed = true
    }
    """), faults=[
    ("timing", "1-hour window instead of 4 hours", "14400", "3600", 2),
    ("snapshot-value", "always overwrites the same slot", "                slot = 1\n", "                slot = 0\n"),
    ("edge-rearm", "only the first request is handled", "} else {\n    armed = true\n}", "}"),
    ("guard", "window expiry needs strictly more than 4 hours for one slot", "ts - ta >= 14400", "ts - ta > 14400"),
]))

BASES.append(dict(id="E1-034", case="E1-034", period=100, script=J("""
    phase := 0
    hold := 0
    ticks := 0
    on = (#Kitchen #Oven).State
    cf = (#Owner #Notify).ConfirmContinue
    if (phase == 1) {
        ticks = ticks + 1
        if (cf == true) {
            phase = 0
            hold = 0
        } else if (ticks >= 600) {
            (#Kitchen #Oven).Off()
            phase = 0
            hold = 0
        }
    }
    if (phase == 0) {
        if (on == true) {
            hold = hold + 1
            if (hold > 144000) {
                (#Owner #Notify).OvenOverrun()
                if (cf == true) {
                    hold = 1
                } else {
                    phase = 1
                    ticks = 0
                }
            }
        } else {
            hold = 0
        }
    }
    """), faults=[
    ("repetition-state", "stops after a confirmation (v1 behaviour)",
     "        phase = 0\n        hold = 0\n    } else if (ticks >= 600) {", "        phase = 2\n    } else if (ticks >= 600) {"),
    ("timing", "30 s to confirm instead of 1 min", "ticks >= 600", "ticks >= 300"),
    ("sustain-reset", "on-time counter not reset when the oven is off", "    } else {\n        hold = 0\n    }\n}", "    }\n}"),
    ("missing-call", "oven never turned off", "        (#Kitchen #Oven).Off()\n", ""),
]))

BASES.append(dict(id="E1-072", case="E1-072", period=100,
    retag={"Light1": ["Light1", "Pair", "Switch"], "Light2": ["Light2", "Pair", "Switch"]}, script=J("""
    p_prev := (#Home #PresenceSensor).Presence
    p = (#Home #PresenceSensor).Presence
    d = (#Home #Sun).IsDaylight
    if (p != p_prev) {
        if (p == true and d == false) {
            all(#Pair #Switch).On()
        }
        if (p == false and d == true) {
            all(#Switch).Off()
        }
        p_prev = p
    }
    """), faults=[
    ("guard", "arrival lights on during daylight", "p == true and d == false", "p == true and d == true"),
    ("missing-call", "departure turns off two lights instead of three", "all(#Switch).Off()", "all(#Pair #Switch).Off()"),
    ("snapshot-value", "previous presence never updated", "    p_prev = p\n", ""),
    ("guard", "fixed hours instead of the daylight input (v1 behaviour)", "(p == true and d == false)",
     "(p == true and ((#Clock).Hour >= 18 or (#Clock).Hour < 6))"),
]))

BASES.append(dict(id="E1-062", case="E1-062", period=100, script=J("""
    a_prev := (#Office #Switch).Switch
    b_prev := (#LivingRoom #Switch).Switch
    a = (#Office #Switch).Switch
    b = (#LivingRoom #Switch).Switch
    if (a != a_prev or b != b_prev) {
        if (a == true and a_prev == false and b == false) {
            (#LivingRoom #Switch).On()
        }
        if (a == false and a_prev == true and b == true) {
            (#LivingRoom #Switch).Off()
        }
        if (b == true and b_prev == false and a == false) {
            (#Office #Switch).On()
        }
        if (b == false and b_prev == true and a == true) {
            (#Office #Switch).Off()
        }
        a_prev = a
        b_prev = b
    }
    """), faults=[
    ("guard", "no feedback guard on A-on rule", "a_prev == false and b == false)", "a_prev == false)"),
    ("snapshot-value", "previous B state never updated", "    b_prev = b\n", ""),
    ("target", "B-off rule turns off B instead of A", "        (#Office #Switch).Off()", "        (#LivingRoom #Switch).Off()"),
    ("order", "B-on rule before A-on rule",
     "    if (a == true and a_prev == false and b == false) {\n        (#LivingRoom #Switch).On()\n    }\n"
     "    if (a == false and a_prev == true and b == true) {\n        (#LivingRoom #Switch).Off()\n    }\n"
     "    if (b == true and b_prev == false and a == false) {\n        (#Office #Switch).On()\n    }",
     "    if (b == true and b_prev == false and a == false) {\n        (#Office #Switch).On()\n    }\n"
     "    if (a == false and a_prev == true and b == true) {\n        (#LivingRoom #Switch).Off()\n    }\n"
     "    if (a == true and a_prev == false and b == false) {\n        (#LivingRoom #Switch).On()\n    }"),
]))
