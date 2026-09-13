"""E1 depth additions — executable transcription of the eight frozen case records. NO TIMELINE IR, NO JoI.

Written after `../frozen_cases/*.md` were hashed (FREEZE_MANIFEST.md) and BEFORE any encoding attempt.
This file only transcribes those records into the runner's input format; it does not change an
interpretation, add a history, or add an expected ACTION. It is itself hashed before encoding
(depth/README.md). Transcription choices that the frozen records leave open are listed per case in
`transcription` and apply the uniform rules below.

Uniform transcription rules (fixed before encoding)
  T1  Time. `t_start_ms` is absolute (t=0 is Monday 00:00, explorer.runtime.interp.clock_state).
      History time rel=0 is the state just before the scenario; the frozen record's "t+0" is rel=1000 ms.
      A frozen row "X becomes on at t+k" is an input change at rel=1000+k. This keeps "becomes" a change
      rather than an initial value. Clock-time records (E1-072, E1-095) use the same rule, so the stated
      clock time is rel=1000 and t_start is one second earlier.
  T2  Momentary events (request, motion, confirmation) are 1 s pulses: true at the event time, false 1 s later.
  T3  An automation's own command does not change an input unless the frozen record lists the resulting
      state event (E1-062 lists it; the others do not).
  T4  ACTIONs are (rel_ms, "Service.Method", [args], device_id). A fan-out command in a frozen record
      ("Lights.On(light1, light2)") is one ACTION per device.
  T5  Comparison. Same multiset of ACTION signatures (service, method, args, device). ACTIONs whose expected
      times are equal form an unordered group, because the frozen records do not order commands issued at
      the same instant (and E1-092's are issued by parallel flows). Tolerance match: every expected ACTION is
      paired with a distinct actual ACTION of the same signature within TOLERANCE_MS. Exact match: equal
      multisets of (time, signature). Numeric arguments compare with NUM_EPS (E1-095 means are decimals).
  T6  Input sampling. `step_ms` is 100 ms, or 1000 ms for histories longer than one hour; every input change
      and expected time in this file is on that grid.
  T7  Fault injection (E1-092 only, whisoo decision 2026-09-13). The reference executor's mock fails the
      matching command: the command is still issued (it appears in the trace, as in the frozen record), and
      the failure is delivered `after_ms` later to the automation instance that issued it. From that tick on
      the instance is terminated before it steps and issues nothing further. No error value, availability
      flag or error-handling API is visible to the program. Other deployed instances are unaffected.

E1-local leaf stubs (whisoo decision 2026-09-13). These exist only in the E1 fixture catalog
(depth/fixture.py), never in files/service_list_ver2.0.7.json. They are typed leaf inputs/actions for testing
orchestration: they do no timing, history, averaging, counting or error recovery.
"""

S = 1000
M = 60 * S
H = 60 * M
TOLERANCE_MS = 1000
NUM_EPS = 1e-9
T0 = 1000                       # rule T1: frozen "t+0"


def clock(day, h, m=0, s=0):    # day 0 = Monday
    return day * 24 * H + h * H + m * M + s * S


def dev(did, category, *tags):
    return {did: {"category": [category], "tags": list(tags) + [category]}}


def act(t, sm, args, did):
    return (t, sm, list(args), did)


CASES = []

# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="E1-092", frozen="frozen_cases/E1-092.md",
    spec=("At a shutdown request, the Alexa announcement flow (tasks, news, alarm settings) and the house-shutdown "
          "flow (downstairs lights off, front/back locks, alarm armed) start together. An Alexa communication failure "
          "ends only the Alexa flow; it must not stop or delay the house-shutdown flow. No completion deadline."),
    stubs=["House.ShutdownRequested (BOOL input)", "Alexa.AnnounceTasks()", "Alexa.AnnounceNews()",
           "Alexa.AnnounceAlarmSettings()", "Lights.Off(Area: STRING)", "Locks.Lock(Doors: STRING)",
           "Alarm.Set(Mode: STRING)"],
    devices={**dev("House_Hub", "House", "Home"), **dev("Echo", "Alexa", "LivingRoom"),
             **dev("Downstairs_Lights", "Lights", "Downstairs"), **dev("Door_Locks", "Locks", "Entrance"),
             **dev("Alarm_Panel", "Alarm", "Home")},
    transcription=["frozen per-step spacing of 1 s in each flow (t+0, t+1, t+2) kept as issued times",
                   "`Lights.Off(downstairs)` -> Area='downstairs'; `Locks.Lock(front, back)` -> Doors='front, back'; "
                   "`Alarm.Set(armed)` -> Mode='armed'",
                   "fault: Alexa.AnnounceNews issued at t+1 fails; failure delivered at t+2 (after_ms=1000), rule T7"],
    t_start_ms=clock(0, 22, 0) - T0,
    histories=[dict(
        name="alexa_news_fails", kind="boundary", step_ms=100, horizon=T0 + 3 * S + S,
        events=[(0, {"House_Hub.ShutdownRequested": False}),
                (T0, {"House_Hub.ShutdownRequested": True}),
                (T0 + S, {"House_Hub.ShutdownRequested": False})],
        faults=[dict(service="Alexa", method="AnnounceNews", device="Echo", after_ms=1000)],
        expected=[act(T0, "Alexa.AnnounceTasks", [], "Echo"),
                  act(T0, "Lights.Off", ["downstairs"], "Downstairs_Lights"),
                  act(T0 + S, "Alexa.AnnounceNews", [], "Echo"),
                  act(T0 + S, "Locks.Lock", ["front, back"], "Door_Locks"),
                  act(T0 + 2 * S, "Alarm.Set", ["armed"], "Alarm_Panel")])],
))

# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="E1-095", frozen="frozen_cases/E1-095.md",
    spec=("Every day, read pH and chlorine at 10:00, 11:00, 12:00, 13:00 and 14:00. At 15:00 report the arithmetic "
          "mean of the five readings of each sensor. The primary version accumulates internally (sum += value, "
          "count += 1) and does not delegate averaging to a history or statistics service."),
    stubs=["PoolPH.Value (DOUBLE input)", "PoolChlorine.Value (DOUBLE input)",
           "Pool.ReportDailyQuality(MeanPH: DOUBLE, MeanChlorine: DOUBLE)"],
    devices={**dev("Pool_PH", "PoolPH", "Pool"), **dev("Pool_Chlorine", "PoolChlorine", "Pool"),
             **dev("Pool_Report", "Pool", "Pool")},
    transcription=["readings are sensor values present at the stated clock times; the pre-scenario value (rel 0) "
                   "equals the 10:00 value, which is never read before 10:00",
                   "one daily window is executed (the frozen record has one day)",
                   "expected means 7.30 and 1.10 compared numerically (rule T5, NUM_EPS)"],
    t_start_ms=clock(0, 10, 0) - T0,
    histories=[dict(
        name="five_readings_one_day", kind="nominal", step_ms=1000, horizon=T0 + 5 * H + M,
        events=[(0, {"Pool_PH.Value": 7.2, "Pool_Chlorine.Value": 1.0}),
                (T0, {"Pool_PH.Value": 7.2, "Pool_Chlorine.Value": 1.0}),
                (T0 + 1 * H, {"Pool_PH.Value": 7.4, "Pool_Chlorine.Value": 1.2}),
                (T0 + 2 * H, {"Pool_PH.Value": 7.3, "Pool_Chlorine.Value": 1.1}),
                (T0 + 3 * H, {"Pool_PH.Value": 7.5, "Pool_Chlorine.Value": 0.9}),
                (T0 + 4 * H, {"Pool_PH.Value": 7.1, "Pool_Chlorine.Value": 1.3})],
        expected=[act(T0 + 5 * H, "Pool.ReportDailyQuality", [7.30, 1.10], "Pool_Report")])],
))

# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="E1-086", frozen="frozen_cases/E1-086.md",
    spec=("Turning the control input on starts zone 1 for ten minutes, then a 30-second gap, then zone 2 for ten "
          "minutes. Turning the input off at any point immediately turns off both zones and cancels all remaining "
          "waits and actions. Restart behaviour is excluded."),
    stubs=[],
    devices={**dev("Sprinkler_Run", "Switch", "Garden", "SprinklerRun"),
             **dev("Zone1_Valve", "Valve", "Zone1"), **dev("Zone2_Valve", "Valve", "Zone2")},
    transcription=["`SprinklerRun` boolean -> catalog Switch.Switch on device Sprinkler_Run",
                   "`Valve.On(zoneN)` / `Valve.Off(zoneN)` -> catalog Valve.Open / Valve.Close on ZoneN_Valve "
                   "(catalog method names; same command)"],
    t_start_ms=clock(0, 6, 0) - T0,
    histories=[dict(
        name="cancel_during_zone1", kind="boundary", step_ms=100, horizon=T0 + 25 * M,
        events=[(0, {"Sprinkler_Run.Switch": False}),
                (T0, {"Sprinkler_Run.Switch": True}),
                (T0 + 5 * M, {"Sprinkler_Run.Switch": False})],
        expected=[act(T0, "Valve.Open", [], "Zone1_Valve"),
                  act(T0 + 5 * M, "Valve.Close", [], "Zone1_Valve"),
                  act(T0 + 5 * M, "Valve.Close", [], "Zone2_Valve")])],
))

# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="E1-099", frozen="frozen_cases/E1-099.md",
    spec=("A manual switch-on creates a five-minute off deadline. Every motion event while the light is on adds two "
          "minutes to the current deadline. At the deadline, turn the light off only when there has been no motion "
          "during the preceding two minutes. Motion extends the existing deadline; it does not restart a timer."),
    stubs=[],
    devices={**dev("Hall_Light", "Switch", "Hall", "Light"), **dev("Hall_Motion", "MotionSensor", "Hall")},
    transcription=["`ManualLightOn` -> Hall_Light.Switch becomes true (the history contains only manual switch-ons)",
                   "`MotionDetected` -> Hall_Motion.Motion 1 s pulse (rule T2)",
                   "`Light.Off(hall)` -> catalog Switch.Off on Hall_Light"],
    t_start_ms=clock(0, 20, 0) - T0,
    histories=[dict(
        name="two_motions_extend", kind="nominal", step_ms=100, horizon=T0 + 12 * M,
        events=[(0, {"Hall_Light.Switch": False, "Hall_Motion.Motion": False}),
                (T0, {"Hall_Light.Switch": True}),
                (T0 + 1 * M, {"Hall_Motion.Motion": True}), (T0 + 1 * M + S, {"Hall_Motion.Motion": False}),
                (T0 + 4 * M, {"Hall_Motion.Motion": True}), (T0 + 4 * M + S, {"Hall_Motion.Motion": False})],
        expected=[act(T0 + 9 * M, "Switch.Off", [], "Hall_Light")])],
))

# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="E1-028", frozen="frozen_cases/E1-028.md",
    spec=("'Every 4 hours' is a rolling four-hour window. A dispense request succeeds only when fewer than two bowls "
          "were dispensed during the preceding four hours, counting prior dispenses in (t-4h, t). An over-limit "
          "request emits no dispense action and no notification."),
    stubs=["Feeder.DispenseRequested (BOOL input)", "Feeder.Dispense(Portion: STRING)"],
    devices={**dev("Pet_Feeder", "Feeder", "Kitchen")},
    transcription=["dispense request -> Pet_Feeder.DispenseRequested 1 s pulse (rule T2)",
                   "`Feeder.Dispense(one_bowl)` -> Portion='one_bowl'"],
    t_start_ms=clock(0, 8, 0) - T0,
    histories=[dict(
        name="third_request_rejected_fourth_after_expiry", kind="boundary", step_ms=1000, horizon=T0 + 4 * H + M,
        events=[(0, {"Pet_Feeder.DispenseRequested": False})]
               + [e for k in (0, 60, 120, 240)
                  for e in ((T0 + k * M, {"Pet_Feeder.DispenseRequested": True}),
                            (T0 + k * M + S, {"Pet_Feeder.DispenseRequested": False}))],
        expected=[act(T0, "Feeder.Dispense", ["one_bowl"], "Pet_Feeder"),
                  act(T0 + 60 * M, "Feeder.Dispense", ["one_bowl"], "Pet_Feeder"),
                  act(T0 + 240 * M, "Feeder.Dispense", ["one_bowl"], "Pet_Feeder")])],
))

# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="E1-034", frozen="frozen_cases/E1-034.md",
    spec=("After four hours of continuous oven-on time, send a confirmation alert. ConfirmContinue within one minute "
          "leaves the oven on for the bounded trace. If no confirmation arrives by one minute after the alert, turn "
          "the oven off."),
    stubs=["Oven.State (BOOL input)", "Oven.Off()", "Notify.ConfirmContinue (BOOL input)", "Notify.OvenOverrun()"],
    devices={**dev("Kitchen_Oven", "Oven", "Kitchen"), **dev("Owner_Phone", "Notify", "Owner")},
    transcription=["`OvenState = on` -> Kitchen_Oven.State becomes true",
                   "`ConfirmContinue` -> Owner_Phone.ConfirmContinue 1 s pulse (rule T2)"],
    t_start_ms=clock(0, 12, 0) - T0,
    histories=[
        dict(name="A_no_response", kind="boundary", step_ms=1000, horizon=T0 + 4 * H + 2 * M,
             events=[(0, {"Kitchen_Oven.State": False, "Owner_Phone.ConfirmContinue": False}),
                     (T0, {"Kitchen_Oven.State": True})],
             expected=[act(T0 + 4 * H, "Notify.OvenOverrun", [], "Owner_Phone"),
                       act(T0 + 4 * H + M, "Oven.Off", [], "Kitchen_Oven")]),
        dict(name="B_response_within_minute", kind="boundary", step_ms=1000, horizon=T0 + 4 * H + 2 * M,
             events=[(0, {"Kitchen_Oven.State": False, "Owner_Phone.ConfirmContinue": False}),
                     (T0, {"Kitchen_Oven.State": True}),
                     (T0 + 4 * H + 30 * S, {"Owner_Phone.ConfirmContinue": True}),
                     (T0 + 4 * H + 31 * S, {"Owner_Phone.ConfirmContinue": False})],
             expected=[act(T0 + 4 * H, "Notify.OvenOverrun", [], "Owner_Phone")])],
))

# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="E1-072", frozen="frozen_cases/E1-072.md",
    spec=("On transition to HOME, turn on light1 and light2 only between sunset and sunrise. On transition to AWAY, "
          "turn off light1, light2 and light3 only between sunrise and sunset. No action in the complementary ranges."),
    stubs=[],
    devices={**dev("Home_Presence", "PresenceSensor", "Home"),
             **dev("Light1", "Switch", "Light1"), **dev("Light2", "Switch", "Light2"), **dev("Light3", "Switch", "Light3")},
    transcription=["`HomePresence` HOME/AWAY -> catalog PresenceSensor.Presence true/false",
                   "sunrise 06:00 and sunset 18:00 are fixed for this history, as the frozen record states; the "
                   "reference executor has no sun events, so they enter as clock times",
                   "`Lights.On(light1, light2)` -> Switch.On on Light1 and Light2 (rule T4)"],
    t_start_ms=clock(0, 19, 0) - T0,
    histories=[dict(
        name="night_home_then_day_away", kind="boundary", step_ms=1000, horizon=T0 + 13 * H + M,
        events=[(0, {"Home_Presence.Presence": False}),
                (T0, {"Home_Presence.Presence": True}),                  # Mon 19:00 HOME
                (T0 + 1 * H, {"Home_Presence.Presence": False}),         # Mon 20:00 AWAY
                (T0 + 12 * H, {"Home_Presence.Presence": True}),         # Tue 07:00 HOME
                (T0 + 13 * H, {"Home_Presence.Presence": False})],       # Tue 08:00 AWAY
        expected=[act(T0, "Switch.On", [], "Light1"), act(T0, "Switch.On", [], "Light2"),
                  act(T0 + 13 * H, "Switch.Off", [], "Light1"), act(T0 + 13 * H, "Switch.Off", [], "Light2"),
                  act(T0 + 13 * H, "Switch.Off", [], "Light3")])],
))

# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="E1-062", frozen="frozen_cases/E1-062.md",
    spec=("Each state change of light A is copied to light B only when B differs; each state change of B is copied "
          "to A only when A differs. The guard prevents feedback-loop actions after a synchronizing command."),
    stubs=[],
    devices={**dev("LightA", "Switch", "Office", "LightA"), **dev("LightB", "Switch", "LivingRoom", "LightB")},
    transcription=["`LightA`/`LightB` state -> catalog Switch.Switch on LightA/LightB; commands -> Switch.On/Off",
                   "the frozen 't+0+' resulting-state events are input changes 100 ms after the command (rule T3)"],
    t_start_ms=clock(0, 9, 0) - T0,
    histories=[dict(
        name="copy_both_directions_no_feedback", kind="boundary", step_ms=100, horizon=T0 + 2 * M,
        events=[(0, {"LightA.Switch": False, "LightB.Switch": False}),
                (T0, {"LightA.Switch": True}),
                (T0 + 100, {"LightB.Switch": True}),
                (T0 + M, {"LightB.Switch": False}),
                (T0 + M + 100, {"LightA.Switch": False})],
        expected=[act(T0, "Switch.On", [], "LightB"),
                  act(T0 + M, "Switch.Off", [], "LightA")])],
))

CASE_BY_ID = {c["id"]: c for c in CASES}
