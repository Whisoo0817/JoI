"""Motivation pilot tasks: hidden gold specifications (never shown to the generator
except the Timeline IR in the IR condition).

Each task fixes:
  - command  : natural-language request (all conditions)
  - spec     : explicit behavior contract in prose (SPEC condition only)
  - ir       : confirmed Timeline IR (IR condition only)
  - devices / binding / selectors : binding plan, given to every condition
  - services : catalog members shown as [Service Details]
  - histories: input histories with hand-derived expected ACTION traces

History fields
  kind           nominal | boundary
  nl_determined  True when the natural-language command alone fixes the expected
                 trace. False when only the explicit contract fixes it (reported
                 separately for the NL condition).
  events         [(t_ms, {"Device.Attr": value}), ...]; the t=0 entry sets every input.
  horizon_ms     last logical time compared.
  expected       [(t_ms, "Service.Method", [args], device_id), ...]

Timing convention: inputs change on whole seconds; the comparison tolerates a
timing offset of at most TOLERANCE_MS per ACTION (1 s polling granularity).
"""

S = 1000
M = 60 * S

DOOR = {"Front_Door": {"category": ["ContactSensor"], "tags": ["Entrance", "Door", "ContactSensor"]}}
HALL_SPK = {"Hall_Speaker": {"category": ["Speaker"], "tags": ["Hallway", "Speaker"]}}


def speak(t, dev, text):
    return (t, "Speaker.Speak", [text], dev)


TASKS = [
    # ── L1: one temporal mechanism ────────────────────────────────────────────
    dict(
        id="T01", family="sustain", level=1,
        command="If the front door stays open for 1 minute, announce 'Please close the front door' through the hallway speaker.",
        spec=("Monitor the front door contact sensor from the start. When the door has been open continuously "
              "for 60 seconds, speak 'Please close the front door' once on the hallway speaker and then stop the "
              "automation for good. If the door closes before 60 seconds have elapsed, discard the elapsed time; "
              "timing starts again from zero the next time the door opens."),
        devices={**DOOR, **HALL_SPK},
        binding={"ContactSensor": ["Front_Door"], "Speaker": ["Hall_Speaker"]},
        selectors={"ContactSensor.Contact": "(#Entrance #ContactSensor)", "Speaker.Speak": "(#Hallway #Speaker)"},
        services=["ContactSensor.Contact", "Speaker.Speak"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "none", "for": "1 MIN"},
            {"op": "call", "target": "Speaker.Speak", "args": {"Text": "Please close the front door"}}]},
        histories=[
            dict(name="open_and_stay", kind="nominal", nl_determined=True, horizon_ms=4 * M,
                 events=[(0, {"Front_Door.Contact": True}), (10 * S, {"Front_Door.Contact": False})],
                 expected=[speak(70 * S, "Hall_Speaker", "Please close the front door")]),
            dict(name="closed_before_minute", kind="boundary", nl_determined=True, horizon_ms=5 * M,
                 events=[(0, {"Front_Door.Contact": True}), (10 * S, {"Front_Door.Contact": False}),
                         (50 * S, {"Front_Door.Contact": True}), (55 * S, {"Front_Door.Contact": False})],
                 expected=[speak(115 * S, "Hall_Speaker", "Please close the front door")]),
            dict(name="no_second_announcement", kind="boundary", nl_determined=True, horizon_ms=5 * M,
                 events=[(0, {"Front_Door.Contact": True}), (10 * S, {"Front_Door.Contact": False}),
                         (80 * S, {"Front_Door.Contact": True}), (90 * S, {"Front_Door.Contact": False})],
                 expected=[speak(70 * S, "Hall_Speaker", "Please close the front door")]),
        ]),
    dict(
        id="T04", family="edge", level=1,
        command="The next time the garage door opens, turn on the garage light.",
        spec=("Wait until the garage door contact sensor reports open. At that moment turn on the garage light "
              "once and stop the automation for good; any later openings do nothing."),
        devices={"Garage_Door": {"category": ["ContactSensor"], "tags": ["Garage", "Door", "ContactSensor"]},
                 "Garage_Light": {"category": ["Light", "Switch"], "tags": ["Garage", "Light"]}},
        binding={"ContactSensor": ["Garage_Door"], "Switch": ["Garage_Light"]},
        selectors={"ContactSensor.Contact": "(#Garage #ContactSensor)", "Switch.On": "(#Garage #Light)"},
        services=["ContactSensor.Contact", "Switch.On"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "none"},
            {"op": "call", "target": "Switch.On", "args": {}}]},
        histories=[
            dict(name="single_opening", kind="nominal", nl_determined=True, horizon_ms=2 * M,
                 events=[(0, {"Garage_Door.Contact": True}), (30 * S, {"Garage_Door.Contact": False})],
                 expected=[(30 * S, "Switch.On", [], "Garage_Light")]),
            dict(name="repeated_openings", kind="boundary", nl_determined=True, horizon_ms=3 * M,
                 events=[(0, {"Garage_Door.Contact": True}), (30 * S, {"Garage_Door.Contact": False}),
                         (40 * S, {"Garage_Door.Contact": True}), (50 * S, {"Garage_Door.Contact": False}),
                         (60 * S, {"Garage_Door.Contact": True}), (70 * S, {"Garage_Door.Contact": False})],
                 expected=[(30 * S, "Switch.On", [], "Garage_Light")]),
            dict(name="open_for_long", kind="boundary", nl_determined=True, horizon_ms=3 * M,
                 events=[(0, {"Garage_Door.Contact": True}), (30 * S, {"Garage_Door.Contact": False})],
                 expected=[(30 * S, "Switch.On", [], "Garage_Light")]),
        ]),
    dict(
        id="T07", family="snapshot", level=1,
        command="Remember the living room TV channel, switch the TV to channel 7, and switch back to the remembered channel after 30 minutes.",
        spec=("At the start, read the TV's current channel C. Immediately set the channel to 7. Exactly 30 minutes "
              "later set the channel to C, the value read at the start, even if the channel was changed in the "
              "meantime. Then stop."),
        devices={"LR_TV": {"category": ["Television"], "tags": ["LivingRoom", "Television"]}},
        binding={"Television": ["LR_TV"]},
        selectors={"Television.Channel": "(#LivingRoom #Television)", "Television.SetChannel": "(#LivingRoom #Television)"},
        services=["Television.Channel", "Television.SetChannel"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "read", "var": "ch", "src": "Television.Channel"},
            {"op": "call", "target": "Television.SetChannel", "args": {"Channel": 7}},
            {"op": "delay", "duration": "30 MIN"},
            {"op": "call", "target": "Television.SetChannel", "args": {"Channel": "$ch"}}]},
        histories=[
            dict(name="channel_follows_command", kind="nominal", nl_determined=True, horizon_ms=35 * M,
                 events=[(0, {"LR_TV.Channel": 11}), (1 * S, {"LR_TV.Channel": 7})],
                 expected=[(0, "Television.SetChannel", [7], "LR_TV"),
                           (30 * M, "Television.SetChannel", [11], "LR_TV")]),
            dict(name="channel_changed_meanwhile", kind="boundary", nl_determined=True, horizon_ms=35 * M,
                 events=[(0, {"LR_TV.Channel": 11}), (1 * S, {"LR_TV.Channel": 7}),
                         (10 * M, {"LR_TV.Channel": 9})],
                 expected=[(0, "Television.SetChannel", [7], "LR_TV"),
                           (30 * M, "Television.SetChannel", [11], "LR_TV")]),
        ]),
    dict(
        id="T10", family="repetition", level=1,
        command="Starting now, check every 5 minutes whether the living room window is open, and if it is, announce 'Please close the window' through the living room speaker. Stop after 4 checks.",
        spec=("Check the window contact sensor exactly at t = 0, 5, 10 and 15 minutes (4 checks in total). At each "
              "check, if the window reads open at that instant, speak 'Please close the window' once. Changes "
              "between checks are not reacted to. After the 4th check, stop for good."),
        devices={"LR_Window": {"category": ["ContactSensor"], "tags": ["LivingRoom", "Window", "ContactSensor"]},
                 "LR_Speaker": {"category": ["Speaker"], "tags": ["LivingRoom", "Speaker"]}},
        binding={"ContactSensor": ["LR_Window"], "Speaker": ["LR_Speaker"]},
        selectors={"ContactSensor.Contact": "(#LivingRoom #Window)", "Speaker.Speak": "(#LivingRoom #Speaker)"},
        services=["ContactSensor.Contact", "Speaker.Speak"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": "n >= 4", "period": "5 MIN", "count": "n", "body": [
                {"op": "if", "cond": "ContactSensor.Contact == false",
                 "then": [{"op": "call", "target": "Speaker.Speak", "args": {"Text": "Please close the window"}}],
                 "else": []}]}]},
        histories=[
            dict(name="open_whole_time", kind="nominal", nl_determined=True, horizon_ms=30 * M,
                 events=[(0, {"LR_Window.Contact": False})],
                 expected=[speak(t, "LR_Speaker", "Please close the window") for t in (0, 5 * M, 10 * M, 15 * M)]),
            dict(name="open_between_checks", kind="boundary", nl_determined=True, horizon_ms=30 * M,
                 events=[(0, {"LR_Window.Contact": True}), (2 * M, {"LR_Window.Contact": False}),
                         (4 * M, {"LR_Window.Contact": True}), (9 * M + 50 * S, {"LR_Window.Contact": False}),
                         (11 * M, {"LR_Window.Contact": True}), (17 * M, {"LR_Window.Contact": False})],
                 expected=[speak(10 * M, "LR_Speaker", "Please close the window")]),
        ]),

    # ── L2: mechanism + re-arming or one more operator ───────────────────────
    dict(
        id="T02", family="sustain", level=2,
        command="Whenever there is no motion in the living room for 2 minutes, turn off the living room light.",
        spec=("Keep running. Each time motion in the living room has been continuously absent for 120 seconds, turn "
              "off the living room light once. If motion is detected before 120 seconds have elapsed, the countdown "
              "is cancelled and restarts from zero when motion stops again. After turning the light off, do not turn "
              "it off again until motion has been detected and then been absent again for a full 120 seconds."),
        devices={"LR_Motion": {"category": ["MotionSensor"], "tags": ["LivingRoom", "MotionSensor"]},
                 "LR_Light": {"category": ["Light", "Switch"], "tags": ["LivingRoom", "Light"]}},
        binding={"MotionSensor": ["LR_Motion"], "Switch": ["LR_Light"]},
        selectors={"MotionSensor.Motion": "(#LivingRoom #MotionSensor)", "Switch.Off": "(#LivingRoom #Light)"},
        services=["MotionSensor.Motion", "Switch.Off"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
                {"op": "wait", "cond": "MotionSensor.Motion == false", "edge": "none", "for": "2 MIN"},
                {"op": "call", "target": "Switch.Off", "args": {}},
                {"op": "wait", "cond": "MotionSensor.Motion == true", "edge": "none"}]}]},
        histories=[
            dict(name="motion_stops_once", kind="nominal", nl_determined=True, horizon_ms=7 * M,
                 events=[(0, {"LR_Motion.Motion": True}), (10 * S, {"LR_Motion.Motion": False})],
                 expected=[(130 * S, "Switch.Off", [], "LR_Light")]),
            dict(name="motion_interrupts_countdown", kind="boundary", nl_determined=True, horizon_ms=7 * M,
                 events=[(0, {"LR_Motion.Motion": True}), (10 * S, {"LR_Motion.Motion": False}),
                         (100 * S, {"LR_Motion.Motion": True}), (105 * S, {"LR_Motion.Motion": False})],
                 expected=[(225 * S, "Switch.Off", [], "LR_Light")]),
            dict(name="rearm_after_motion", kind="boundary", nl_determined=True, horizon_ms=9 * M,
                 events=[(0, {"LR_Motion.Motion": True}), (10 * S, {"LR_Motion.Motion": False}),
                         (200 * S, {"LR_Motion.Motion": True}), (210 * S, {"LR_Motion.Motion": False})],
                 expected=[(130 * S, "Switch.Off", [], "LR_Light"), (330 * S, "Switch.Off", [], "LR_Light")]),
        ]),
    dict(
        id="T05", family="edge", level=2,
        command="Every time the living room temperature rises above 28°C, turn on the living room fan plug.",
        spec=("Keep running. Each time the living room temperature changes from 28°C or below to above 28°C, turn on "
              "the fan plug once. While the temperature stays above 28°C, do nothing more; it must first return to "
              "28°C or below before the next rise can trigger again."),
        devices={"LR_Temp": {"category": ["TemperatureSensor"], "tags": ["LivingRoom", "TemperatureSensor"]},
                 "LR_FanPlug": {"category": ["Plug", "Switch"], "tags": ["LivingRoom", "Plug"]}},
        binding={"TemperatureSensor": ["LR_Temp"], "Switch": ["LR_FanPlug"]},
        selectors={"TemperatureSensor.Temperature": "(#LivingRoom #TemperatureSensor)", "Switch.On": "(#LivingRoom #Plug)"},
        services=["TemperatureSensor.Temperature", "Switch.On"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
                {"op": "wait", "cond": "TemperatureSensor.Temperature > 28", "edge": "rising"},
                {"op": "call", "target": "Switch.On", "args": {}}]}]},
        histories=[
            dict(name="single_rise", kind="nominal", nl_determined=True, horizon_ms=2 * M,
                 events=[(0, {"LR_Temp.Temperature": 25.0}), (10 * S, {"LR_Temp.Temperature": 29.0})],
                 expected=[(10 * S, "Switch.On", [], "LR_FanPlug")]),
            dict(name="oscillating", kind="boundary", nl_determined=True, horizon_ms=2 * M,
                 events=[(0, {"LR_Temp.Temperature": 25.0}), (10 * S, {"LR_Temp.Temperature": 29.0}),
                         (20 * S, {"LR_Temp.Temperature": 27.0}), (30 * S, {"LR_Temp.Temperature": 29.0}),
                         (40 * S, {"LR_Temp.Temperature": 28.0}), (50 * S, {"LR_Temp.Temperature": 28.5})],
                 expected=[(t * S, "Switch.On", [], "LR_FanPlug") for t in (10, 30, 50)]),
            dict(name="exactly_threshold", kind="boundary", nl_determined=True, horizon_ms=2 * M,
                 events=[(0, {"LR_Temp.Temperature": 25.0}), (10 * S, {"LR_Temp.Temperature": 28.0}),
                         (20 * S, {"LR_Temp.Temperature": 28.1})],
                 expected=[(20 * S, "Switch.On", [], "LR_FanPlug")]),
        ]),
    dict(
        id="T08", family="snapshot", level=2,
        command="Check the wine cellar temperature now and again 10 minutes later. If it has risen by 2°C or more, set the cellar air conditioner's target temperature to the first reading.",
        spec=("Read the cellar temperature t1 at the start. Exactly 10 minutes later read it again as t2. If "
              "t2 - t1 >= 2, set the air conditioner's target temperature to t1 once at that moment; otherwise do "
              "nothing. A drop in temperature never triggers. Readings between the two checks are ignored. Then stop."),
        devices={"Cellar_Temp": {"category": ["TemperatureSensor"], "tags": ["WineCellar", "TemperatureSensor"]},
                 "Cellar_AC": {"category": ["AirConditioner"], "tags": ["WineCellar", "AirConditioner"]}},
        binding={"TemperatureSensor": ["Cellar_Temp"], "AirConditioner": ["Cellar_AC"]},
        selectors={"TemperatureSensor.Temperature": "(#WineCellar #TemperatureSensor)",
                   "AirConditioner.SetTargetTemperature": "(#WineCellar #AirConditioner)"},
        services=["TemperatureSensor.Temperature", "AirConditioner.SetTargetTemperature"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "read", "var": "t1", "src": "TemperatureSensor.Temperature"},
            {"op": "delay", "duration": "10 MIN"},
            {"op": "read", "var": "t2", "src": "TemperatureSensor.Temperature"},
            {"op": "if", "cond": "$t2 - $t1 >= 2",
             "then": [{"op": "call", "target": "AirConditioner.SetTargetTemperature", "args": {"Temperature": "$t1"}}],
             "else": []}]},
        histories=[
            dict(name="steady_rise", kind="nominal", nl_determined=True, horizon_ms=15 * M,
                 events=[(0, {"Cellar_Temp.Temperature": 14.0}), (10 * M, {"Cellar_Temp.Temperature": 17.0})],
                 expected=[(10 * M, "AirConditioner.SetTargetTemperature", [14.0], "Cellar_AC")]),
            dict(name="spike_between_checks", kind="boundary", nl_determined=True, horizon_ms=15 * M,
                 events=[(0, {"Cellar_Temp.Temperature": 14.0}), (5 * M, {"Cellar_Temp.Temperature": 17.0}),
                         (10 * M, {"Cellar_Temp.Temperature": 15.0})],
                 expected=[]),
            dict(name="exactly_two", kind="boundary", nl_determined=True, horizon_ms=15 * M,
                 events=[(0, {"Cellar_Temp.Temperature": 14.0}), (10 * M, {"Cellar_Temp.Temperature": 16.0})],
                 expected=[(10 * M, "AirConditioner.SetTargetTemperature", [14.0], "Cellar_AC")]),
            dict(name="drop", kind="boundary", nl_determined=True, horizon_ms=15 * M,
                 events=[(0, {"Cellar_Temp.Temperature": 14.0}), (10 * M, {"Cellar_Temp.Temperature": 11.0})],
                 expected=[]),
        ]),
    dict(
        id="T11", family="repetition", level=2,
        command="Each time the mailbox is opened, announce 'Mail has arrived' through the kitchen speaker, but stop after the third announcement.",
        spec=("Keep running until three announcements have been made. On each change of the mailbox from closed to "
              "open, speak 'Mail has arrived' once; staying open does not repeat it. After the third announcement, "
              "stop for good; later openings do nothing."),
        devices={"Mailbox": {"category": ["ContactSensor"], "tags": ["Mailbox", "ContactSensor"]},
                 "Kitchen_Speaker": {"category": ["Speaker"], "tags": ["Kitchen", "Speaker"]}},
        binding={"ContactSensor": ["Mailbox"], "Speaker": ["Kitchen_Speaker"]},
        selectors={"ContactSensor.Contact": "(#Mailbox #ContactSensor)", "Speaker.Speak": "(#Kitchen #Speaker)"},
        services=["ContactSensor.Contact", "Speaker.Speak"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": "n >= 3", "period": "100 MSEC", "count": "n", "body": [
                {"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "rising"},
                {"op": "call", "target": "Speaker.Speak", "args": {"Text": "Mail has arrived"}}]}]},
        histories=[
            dict(name="three_short_openings", kind="nominal", nl_determined=True, horizon_ms=5 * M,
                 events=[(0, {"Mailbox.Contact": True}),
                         (10 * S, {"Mailbox.Contact": False}), (15 * S, {"Mailbox.Contact": True}),
                         (60 * S, {"Mailbox.Contact": False}), (65 * S, {"Mailbox.Contact": True}),
                         (120 * S, {"Mailbox.Contact": False}), (125 * S, {"Mailbox.Contact": True})],
                 expected=[speak(t * S, "Kitchen_Speaker", "Mail has arrived") for t in (10, 60, 120)]),
            dict(name="long_opening_and_fourth", kind="boundary", nl_determined=True, horizon_ms=6 * M,
                 events=[(0, {"Mailbox.Contact": True}),
                         (10 * S, {"Mailbox.Contact": False}), (100 * S, {"Mailbox.Contact": True}),
                         (110 * S, {"Mailbox.Contact": False}), (115 * S, {"Mailbox.Contact": True}),
                         (200 * S, {"Mailbox.Contact": False}), (205 * S, {"Mailbox.Contact": True}),
                         (250 * S, {"Mailbox.Contact": False}), (255 * S, {"Mailbox.Contact": True})],
                 expected=[speak(t * S, "Kitchen_Speaker", "Mail has arrived") for t in (10, 110, 200)]),
        ]),

    # ── L3: composition with repetition and another mechanism ───────────────
    dict(
        id="T03", family="sustain", level=3,
        command="Every time the front door is opened, if it is not closed within 3 minutes, announce 'The front door is still open' through the hallway speaker.",
        spec=("Keep running. Each time the front door changes from closed to open, start a 180-second countdown. If "
              "the door closes before the countdown ends, cancel it silently. If the countdown ends while the door "
              "is still open, speak 'The front door is still open' once. A new countdown starts only at the next "
              "closed-to-open change."),
        devices={**DOOR, **HALL_SPK},
        binding={"ContactSensor": ["Front_Door"], "Speaker": ["Hall_Speaker"]},
        selectors={"ContactSensor.Contact": "(#Entrance #ContactSensor)", "Speaker.Speak": "(#Hallway #Speaker)"},
        services=["ContactSensor.Contact", "Speaker.Speak"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
                {"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "rising"},
                {"op": "wait", "cond": "ContactSensor.Contact == true", "timeout": "3 MIN",
                 "on_timeout": [{"op": "call", "target": "Speaker.Speak", "args": {"Text": "The front door is still open"}}]}]}]},
        histories=[
            dict(name="left_open", kind="nominal", nl_determined=True, horizon_ms=7 * M,
                 events=[(0, {"Front_Door.Contact": True}), (10 * S, {"Front_Door.Contact": False})],
                 expected=[speak(190 * S, "Hall_Speaker", "The front door is still open")]),
            dict(name="closed_then_reopened", kind="boundary", nl_determined=True, horizon_ms=9 * M,
                 events=[(0, {"Front_Door.Contact": True}), (10 * S, {"Front_Door.Contact": False}),
                         (60 * S, {"Front_Door.Contact": True}), (120 * S, {"Front_Door.Contact": False})],
                 expected=[speak(300 * S, "Hall_Speaker", "The front door is still open")]),
            dict(name="two_separate_episodes", kind="boundary", nl_determined=True, horizon_ms=11 * M,
                 events=[(0, {"Front_Door.Contact": True}), (10 * S, {"Front_Door.Contact": False}),
                         (250 * S, {"Front_Door.Contact": True}), (260 * S, {"Front_Door.Contact": False})],
                 expected=[speak(190 * S, "Hall_Speaker", "The front door is still open"),
                           speak(440 * S, "Hall_Speaker", "The front door is still open")]),
        ]),
    dict(
        id="T06", family="edge", level=3,
        command="Every time motion is detected at the entrance, turn on the entrance light, then turn it off 1 minute later.",
        spec=("Keep running. When the entrance motion sensor changes from no motion to motion, turn on the entrance "
              "light, wait exactly 60 seconds, then turn it off. Motion changes during those 60 seconds are ignored: "
              "they neither extend the timer nor turn the light on again. After the light is turned off, the next "
              "cycle starts only at a new change from no motion to motion."),
        devices={"Entrance_Motion": {"category": ["MotionSensor"], "tags": ["Entrance", "MotionSensor"]},
                 "Entrance_Light": {"category": ["Light", "Switch"], "tags": ["Entrance", "Light"]}},
        binding={"MotionSensor": ["Entrance_Motion"], "Switch": ["Entrance_Light"]},
        selectors={"MotionSensor.Motion": "(#Entrance #MotionSensor)",
                   "Switch.On": "(#Entrance #Light)", "Switch.Off": "(#Entrance #Light)"},
        services=["MotionSensor.Motion", "Switch.On", "Switch.Off"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
                {"op": "wait", "cond": "MotionSensor.Motion == true", "edge": "rising"},
                {"op": "call", "target": "Switch.On", "args": {}},
                {"op": "delay", "duration": "1 MIN"},
                {"op": "call", "target": "Switch.Off", "args": {}}]}]},
        histories=[
            dict(name="short_motion", kind="nominal", nl_determined=True, horizon_ms=3 * M,
                 events=[(0, {"Entrance_Motion.Motion": False}), (10 * S, {"Entrance_Motion.Motion": True}),
                         (15 * S, {"Entrance_Motion.Motion": False})],
                 expected=[(10 * S, "Switch.On", [], "Entrance_Light"), (70 * S, "Switch.Off", [], "Entrance_Light")]),
            dict(name="second_motion_while_on", kind="boundary", nl_determined=False, horizon_ms=3 * M,
                 events=[(0, {"Entrance_Motion.Motion": False}), (10 * S, {"Entrance_Motion.Motion": True}),
                         (15 * S, {"Entrance_Motion.Motion": False}), (30 * S, {"Entrance_Motion.Motion": True}),
                         (35 * S, {"Entrance_Motion.Motion": False})],
                 expected=[(10 * S, "Switch.On", [], "Entrance_Light"), (70 * S, "Switch.Off", [], "Entrance_Light")]),
            dict(name="motion_lasts_past_off", kind="boundary", nl_determined=True, horizon_ms=4 * M,
                 events=[(0, {"Entrance_Motion.Motion": False}), (10 * S, {"Entrance_Motion.Motion": True}),
                         (100 * S, {"Entrance_Motion.Motion": False})],
                 expected=[(10 * S, "Switch.On", [], "Entrance_Light"), (70 * S, "Switch.Off", [], "Entrance_Light")]),
            dict(name="two_separate_detections", kind="boundary", nl_determined=True, horizon_ms=4 * M,
                 events=[(0, {"Entrance_Motion.Motion": False}), (10 * S, {"Entrance_Motion.Motion": True}),
                         (15 * S, {"Entrance_Motion.Motion": False}), (100 * S, {"Entrance_Motion.Motion": True}),
                         (105 * S, {"Entrance_Motion.Motion": False})],
                 expected=[(10 * S, "Switch.On", [], "Entrance_Light"), (70 * S, "Switch.Off", [], "Entrance_Light"),
                           (100 * S, "Switch.On", [], "Entrance_Light"), (160 * S, "Switch.Off", [], "Entrance_Light")]),
        ]),
    dict(
        id="T09", family="snapshot", level=3,
        command="Every time the front door opens, remember the living room speaker's volume, lower it to 10, and restore the remembered volume 2 minutes later.",
        spec=("Keep running. On each change of the front door from closed to open: read the speaker's current volume "
              "V at that moment, set the volume to 10, wait exactly 120 seconds, then set the volume back to V. Door "
              "changes during those 120 seconds are ignored. Every episode uses the volume read at its own start. "
              "The next episode begins only at a closed-to-open change after the volume was restored."),
        devices={**DOOR, "LR_Speaker": {"category": ["Speaker"], "tags": ["LivingRoom", "Speaker"]}},
        binding={"ContactSensor": ["Front_Door"], "Speaker": ["LR_Speaker"]},
        selectors={"ContactSensor.Contact": "(#Entrance #ContactSensor)",
                   "Speaker.Volume": "(#LivingRoom #Speaker)", "Speaker.SetVolume": "(#LivingRoom #Speaker)"},
        services=["ContactSensor.Contact", "Speaker.Volume", "Speaker.SetVolume"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": None, "period": "100 MSEC", "body": [
                {"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "rising"},
                {"op": "read", "var": "vol", "src": "Speaker.Volume"},
                {"op": "call", "target": "Speaker.SetVolume", "args": {"Volume": 10}},
                {"op": "delay", "duration": "2 MIN"},
                {"op": "call", "target": "Speaker.SetVolume", "args": {"Volume": "$vol"}}]}]},
        histories=[
            dict(name="one_visit", kind="nominal", nl_determined=True, horizon_ms=5 * M,
                 events=[(0, {"Front_Door.Contact": True, "LR_Speaker.Volume": 40}),
                         (10 * S, {"Front_Door.Contact": False}), (11 * S, {"LR_Speaker.Volume": 10}),
                         (20 * S, {"Front_Door.Contact": True})],
                 expected=[(10 * S, "Speaker.SetVolume", [10], "LR_Speaker"),
                           (130 * S, "Speaker.SetVolume", [40], "LR_Speaker")]),
            dict(name="volume_changed_before_second_visit", kind="boundary", nl_determined=True, horizon_ms=10 * M,
                 events=[(0, {"Front_Door.Contact": True, "LR_Speaker.Volume": 40}),
                         (10 * S, {"Front_Door.Contact": False}), (11 * S, {"LR_Speaker.Volume": 10}),
                         (20 * S, {"Front_Door.Contact": True}), (131 * S, {"LR_Speaker.Volume": 40}),
                         (300 * S, {"LR_Speaker.Volume": 55}),
                         (400 * S, {"Front_Door.Contact": False}), (401 * S, {"LR_Speaker.Volume": 10}),
                         (410 * S, {"Front_Door.Contact": True})],
                 expected=[(10 * S, "Speaker.SetVolume", [10], "LR_Speaker"),
                           (130 * S, "Speaker.SetVolume", [40], "LR_Speaker"),
                           (400 * S, "Speaker.SetVolume", [10], "LR_Speaker"),
                           (520 * S, "Speaker.SetVolume", [55], "LR_Speaker")]),
            dict(name="reopened_during_wait", kind="boundary", nl_determined=False, horizon_ms=5 * M,
                 events=[(0, {"Front_Door.Contact": True, "LR_Speaker.Volume": 40}),
                         (10 * S, {"Front_Door.Contact": False}), (11 * S, {"LR_Speaker.Volume": 10}),
                         (20 * S, {"Front_Door.Contact": True}), (30 * S, {"Front_Door.Contact": False}),
                         (40 * S, {"Front_Door.Contact": True})],
                 expected=[(10 * S, "Speaker.SetVolume", [10], "LR_Speaker"),
                           (130 * S, "Speaker.SetVolume", [40], "LR_Speaker")]),
        ]),
    dict(
        id="T12", family="repetition", level=3,
        command="Each time the front door is left open for 1 minute, announce 'Please close the door' through the hallway speaker, and stop after 3 announcements.",
        spec=("Keep running until three announcements have been made. Each time the front door has been open "
              "continuously for 60 seconds, speak 'Please close the door' once. If the door closes before 60 seconds, "
              "the countdown is cancelled. While the door stays open after an announcement, do not repeat it; the "
              "next announcement requires the door to close and then stay open for another full 60 seconds. After "
              "the third announcement, stop for good."),
        devices={**DOOR, **HALL_SPK},
        binding={"ContactSensor": ["Front_Door"], "Speaker": ["Hall_Speaker"]},
        selectors={"ContactSensor.Contact": "(#Entrance #ContactSensor)", "Speaker.Speak": "(#Hallway #Speaker)"},
        services=["ContactSensor.Contact", "Speaker.Speak"],
        ir={"timeline": [
            {"op": "start_at", "anchor": "now"},
            {"op": "cycle", "until": "n >= 3", "period": "100 MSEC", "count": "n", "body": [
                {"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "none", "for": "1 MIN"},
                {"op": "call", "target": "Speaker.Speak", "args": {"Text": "Please close the door"}},
                {"op": "wait", "cond": "ContactSensor.Contact == true", "edge": "none"}]}]},
        histories=[
            dict(name="three_long_openings", kind="nominal", nl_determined=True, horizon_ms=15 * M,
                 events=[(0, {"Front_Door.Contact": True}),
                         (10 * S, {"Front_Door.Contact": False}), (100 * S, {"Front_Door.Contact": True}),
                         (200 * S, {"Front_Door.Contact": False}), (300 * S, {"Front_Door.Contact": True}),
                         (400 * S, {"Front_Door.Contact": False}), (500 * S, {"Front_Door.Contact": True}),
                         (600 * S, {"Front_Door.Contact": False}), (700 * S, {"Front_Door.Contact": True})],
                 expected=[speak(t * S, "Hall_Speaker", "Please close the door") for t in (70, 260, 460)]),
            dict(name="interrupted_and_held_open", kind="boundary", nl_determined=True, horizon_ms=15 * M,
                 events=[(0, {"Front_Door.Contact": True}),
                         (10 * S, {"Front_Door.Contact": False}), (50 * S, {"Front_Door.Contact": True}),
                         (55 * S, {"Front_Door.Contact": False}), (130 * S, {"Front_Door.Contact": True}),
                         (200 * S, {"Front_Door.Contact": False}), (400 * S, {"Front_Door.Contact": True}),
                         (450 * S, {"Front_Door.Contact": False}), (520 * S, {"Front_Door.Contact": True}),
                         (600 * S, {"Front_Door.Contact": False}), (700 * S, {"Front_Door.Contact": True})],
                 expected=[speak(t * S, "Hall_Speaker", "Please close the door") for t in (115, 260, 510)]),
        ]),
]

TOLERANCE_MS = 1000

if __name__ == "__main__":
    import json
    from pathlib import Path
    out = Path(__file__).with_name("tasks.json")
    out.write_text(json.dumps(TASKS, ensure_ascii=False, indent=1))
    print(f"{len(TASKS)} tasks, {sum(len(t['histories']) for t in TASKS)} histories -> {out}")
