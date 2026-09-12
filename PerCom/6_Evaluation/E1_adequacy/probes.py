"""E1 boundary probes — requirements chosen BEFORE any encoding attempt.

These are NOT part of the Stage A success corpus and never enter its denominator.
They are pre-identified boundary requirements (README §1 B1-B5) selected because the
Stage A cases did not exercise them. Each probe fixes its interpretation and expected
ACTION traces here; the attempted encodings live in probe_attempts.py, written only
after this file was hashed (README §6).

A probe may end in any verdict. "완전" is a legitimate probe outcome and means the
boundary candidate turned out to be expressible; it is reported as such and is not
moved into the Stage A count.

Same schema as cases.py, plus:
  probe_of     : the boundary element this probe targets
  why_probe    : why Stage A could not answer it
"""

from cases import S, M, H, clock, dev, act  # noqa: F401  (same helpers, same conventions)

PROBES = []

# ─────────────────────────────────────────────────────────────────────────────
# P1  C20-U — the unordered variant of the C20 sentence (B3: look-back pairing)
#     Stage A evaluated only the ordered "AND AFTERWARDS" sentence; the paired
#     unordered sentence was separated by the B audit and is answered here.
# ─────────────────────────────────────────────────────────────────────────────
PROBES.append(dict(
    id="P1", probe_of="B3", pair_of="C20-O",
    source="Brackenbury et al., How Users Interpret Bugs in TAP (CHI 2019), Table 1 (unordered member of the pair)",
    source_url="https://par.nsf.gov/biblio/10106413", accessed="2026-09-12",
    verbatim="IF Sally enters the bedroom AND the sun sets WITHIN 2 hours THEN turn on the bedroom lights.",
    why_probe=("C20-O covers only the ordered reading. The unordered reading requires remembering that one event "
               "happened while the flow may be occupied elsewhere, and re-testing on every later event of the other kind."),
    elements=["R1", "R10", "B3"], boundary_intent=True,
    spec=("Two event kinds: ENTRY = bedroom presence changes absent->present; SUNSET = outdoor brightness changes "
          "from >=50 to <50. On each ENTRY, if a SUNSET occurred at most 2 hours earlier, call Switch.On at the instant "
          "of the ENTRY. On each SUNSET, if an ENTRY occurred at most 2 hours earlier, call Switch.On at the instant of "
          "the SUNSET. Order does not matter and the rule re-arms: every new event is tested against the most recent "
          "event of the other kind, so the same SUNSET may pair with several later ENTRYs. Before the first event of a "
          "kind, no pairing exists. Never ends."),
    assumptions=["[가정] 해넘이 = LightSensor.Brightness 가 50 아래로 떨어지는 사건 (C20-O 와 동일)",
                 "[가정] '가장 최근의 반대편 사건' 과만 짝짓는다. 더 오래된 사건은 덮어쓴다",
                 "[가정] 같은 사건이 여러 번 짝지어질 수 있다(원문의 WITHIN 2 hours 에 1회 제한이 없음)"],
    devices={**dev("Bed_Presence", "PresenceSensor", "Bedroom"), **dev("Outdoor_Lux", "LightSensor", "Outdoor"),
             **dev("Bed_Light", "Switch", "Bedroom", "Light")},
    binding={"PresenceSensor": ["Bed_Presence"], "LightSensor": ["Outdoor_Lux"], "Switch": ["Bed_Light"]},
    selectors={"PresenceSensor.Presence": "(#Bedroom #PresenceSensor)", "LightSensor.Brightness": "(#Outdoor #LightSensor)",
               "Switch.On": "(#Bedroom #Light)"},
    t_start_ms=clock(16, 0), cron="",
    histories=[
        # identical to a C20-O history: the ordered reading also fires here
        dict(name="entry_then_sunset", kind="nominal", horizon=4 * H,
             events=[(0, {"Bed_Presence.Presence": False, "Outdoor_Lux.Brightness": 500.0}),
                     (600 * S, {"Bed_Presence.Presence": True}), (3600 * S, {"Outdoor_Lux.Brightness": 20.0})],
             expected=[act(3600 * S, "Switch.On", [], "Bed_Light")]),
        # discriminating history: the ordered reading does NOT fire, the unordered one does
        dict(name="sunset_then_entry", kind="boundary", horizon=4 * H,
             events=[(0, {"Bed_Presence.Presence": False, "Outdoor_Lux.Brightness": 500.0}),
                     (600 * S, {"Outdoor_Lux.Brightness": 20.0}), (3600 * S, {"Bed_Presence.Presence": True})],
             expected=[act(3600 * S, "Switch.On", [], "Bed_Light")]),
        # re-arming: one sunset pairs with two later entries
        dict(name="one_sunset_two_entries", kind="boundary", horizon=4 * H,
             events=[(0, {"Bed_Presence.Presence": False, "Outdoor_Lux.Brightness": 500.0}),
                     (600 * S, {"Outdoor_Lux.Brightness": 20.0}), (3600 * S, {"Bed_Presence.Presence": True}),
                     (5400 * S, {"Bed_Presence.Presence": False}), (6600 * S, {"Bed_Presence.Presence": True})],
             expected=[act(3600 * S, "Switch.On", [], "Bed_Light"), act(6600 * S, "Switch.On", [], "Bed_Light")]),
        # window boundary: 2h10m apart, no pairing
        dict(name="gap_too_large", kind="boundary", horizon=4 * H,
             events=[(0, {"Bed_Presence.Presence": False, "Outdoor_Lux.Brightness": 500.0}),
                     (600 * S, {"Outdoor_Lux.Brightness": 20.0}), (8400 * S, {"Bed_Presence.Presence": True})],
             expected=[]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# P2  "door opened within the last x minutes" (B3: look-back event memory)
# ─────────────────────────────────────────────────────────────────────────────
PROBES.append(dict(
    id="P2", probe_of="B3", pair_of=None,
    source="Home Assistant Community thread 363863 (2021-12-06), original post",
    source_url="https://community.home-assistant.io/t/automation-condition-for-door-opened-within-the-last-x-minutes/363863",
    accessed="2026-09-12",
    verbatim=("I have an automation which sends a notification along with a camera capture for when motion is detected "
              "near my front door, which is also equipped with a sensor. ... I wanted to create a condition for the "
              "automation, such that this will only get triggered if and only if the door sensor has been triggered "
              "(i.e., state changed to \"open\") within the previous x minutes. Note that within these x minutes, the "
              "automation should be able to run as many times as needed/triggered."),
    why_probe=("The condition is a past event, not a current level, and the rule must fire on every motion inside the "
               "window. No Stage A case needed a remembered event time."),
    elements=["R1", "B3"], boundary_intent=True,
    spec=("x is fixed at 10 minutes. On each motion no-motion->motion change, call MessageSender.SendSms at that "
          "instant if and only if the front door changed to open at some time in the preceding 10 minutes "
          "(inclusive). Several motion changes inside the same window each send. Motion before the first door "
          "opening never sends. Never ends."),
    assumptions=["[가정] Contact == false 가 '열림'(C05 와 같은 규약). '문이 열림으로 바뀜' = Contact true->false",
                 "[가정] 알림 = MessageSender.SendSms 고정 인자. 카메라 캡처는 호출 열을 정하지 않으므로 범위 밖",
                 "[가정] 창은 문이 열린 순간부터 10분(닫힘 시각과 무관)"],
    devices={**dev("Front_Door", "ContactSensor", "Front"), **dev("Front_Motion", "MotionSensor", "Front"),
             **dev("Phone_SMS", "MessageSender", "Owner")},
    binding={"ContactSensor": ["Front_Door"], "MotionSensor": ["Front_Motion"], "MessageSender": ["Phone_SMS"]},
    selectors={"ContactSensor.Contact": "(#Front #ContactSensor)", "MotionSensor.Motion": "(#Front #MotionSensor)",
               "MessageSender.SendSms": "(#Owner #MessageSender)"},
    t_start_ms=clock(14, 0), cron="",
    histories=[
        dict(name="open_then_motions_in_and_out", kind="nominal", horizon=20 * M,
             events=[(0, {"Front_Door.Contact": True, "Front_Motion.Motion": False}),
                     (300 * S, {"Front_Door.Contact": False}), (360 * S, {"Front_Door.Contact": True}),
                     (480 * S, {"Front_Motion.Motion": True}), (500 * S, {"Front_Motion.Motion": False}),
                     (720 * S, {"Front_Motion.Motion": True}), (740 * S, {"Front_Motion.Motion": False}),
                     (960 * S, {"Front_Motion.Motion": True})],
             expected=[act(480 * S, "MessageSender.SendSms", ["owner", "Motion near the front door", "door"], "Phone_SMS"),
                       act(720 * S, "MessageSender.SendSms", ["owner", "Motion near the front door", "door"], "Phone_SMS")]),
        dict(name="motion_without_any_open", kind="boundary", horizon=20 * M,
             events=[(0, {"Front_Door.Contact": True, "Front_Motion.Motion": False}),
                     (120 * S, {"Front_Motion.Motion": True}), (140 * S, {"Front_Motion.Motion": False}),
                     (600 * S, {"Front_Motion.Motion": True})],
             expected=[]),
        dict(name="three_motions_inside_one_window", kind="boundary", horizon=20 * M,
             events=[(0, {"Front_Door.Contact": True, "Front_Motion.Motion": False}),
                     (60 * S, {"Front_Door.Contact": False}), (90 * S, {"Front_Door.Contact": True}),
                     (180 * S, {"Front_Motion.Motion": True}), (200 * S, {"Front_Motion.Motion": False}),
                     (360 * S, {"Front_Motion.Motion": True}), (380 * S, {"Front_Motion.Motion": False}),
                     (540 * S, {"Front_Motion.Motion": True})],
             expected=[act(t * S, "MessageSender.SendSms", ["owner", "Motion near the front door", "door"], "Phone_SMS")
                       for t in (180, 360, 540)]),
        dict(name="second_open_opens_new_window", kind="boundary", horizon=20 * M,
             events=[(0, {"Front_Door.Contact": True, "Front_Motion.Motion": False}),
                     (60 * S, {"Front_Door.Contact": False}), (120 * S, {"Front_Door.Contact": True}),
                     (700 * S, {"Front_Motion.Motion": True}), (720 * S, {"Front_Motion.Motion": False}),
                     (800 * S, {"Front_Door.Contact": False}), (860 * S, {"Front_Door.Contact": True}),
                     (900 * S, {"Front_Motion.Motion": True})],
             expected=[act(900 * S, "MessageSender.SendSms", ["owner", "Motion near the front door", "door"], "Phone_SMS")]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# P3  variable repetition interval (B4)
# ─────────────────────────────────────────────────────────────────────────────
PROBES.append(dict(
    id="P3", probe_of="B4", pair_of=None,
    source="Home Assistant Community thread 541232 (2023-02-27), original post",
    source_url="https://community.home-assistant.io/t/tryng-to-repeat-an-action-every-n-minutes-where-n-is-variable/541232",
    accessed="2026-09-12",
    verbatim=("turn on a GPIO at a repeatable interval where the interval is configurable via a home assistant input "
              "number. Once turned on, then the GPIO needs to stay on for a period of time depending on the value of a "
              "second home assistant input number, then turn off. ... I thought I could use 'interval.interval' but it "
              "seems that the it's not templatable and will only take fixed numbers."),
    why_probe="No Stage A case needed a repetition interval or an on-time that is read from a device at run time.",
    elements=["R7", "R2", "B4"], boundary_intent=True,
    spec=("Repeat forever. At the start of each cycle read I = Interval_Setting.CurrentLevel and "
          "D = OnTime_Setting.CurrentLevel, both in minutes. Call Switch.On at the start of the cycle, call Switch.Off "
          "exactly D minutes later, and start the next cycle exactly I minutes after this cycle's On. A change to "
          "either setting takes effect from the next cycle that starts after the change."),
    assumptions=["[가정] input_number 두 개 = LevelControl.CurrentLevel 두 대(분 단위). 원문 ESPHome GPIO = Switch",
                 "[가정] I > D 이며 값은 회차 시작에 읽는다(회차 중 변경은 그 회차에 영향 없음)",
                 "[가정] 첫 회차는 t_start 에 시작"],
    devices={**dev("Hydro_Pump", "Switch", "Greenhouse", "Pump"),
             **dev("Interval_Setting", "LevelControl", "Greenhouse", "IntervalKnob"),
             **dev("OnTime_Setting", "LevelControl", "Greenhouse", "OnTimeKnob")},
    binding={"Switch": ["Hydro_Pump"], "LevelControl": ["Interval_Setting"], "LevelControl#2": ["OnTime_Setting"]},
    selectors={"Switch.On": "(#Greenhouse #Pump)", "Switch.Off": "(#Greenhouse #Pump)",
               "LevelControl.CurrentLevel": "(#Greenhouse #IntervalKnob)"},
    t_start_ms=clock(8, 0), cron="",
    histories=[
        dict(name="constant_20_5", kind="nominal", horizon=50 * M,
             events=[(0, {"Interval_Setting.CurrentLevel": 20.0, "OnTime_Setting.CurrentLevel": 5.0,
                          "Hydro_Pump.Switch": False})],
             expected=[act(0, "Switch.On", [], "Hydro_Pump"), act(5 * M, "Switch.Off", [], "Hydro_Pump"),
                       act(20 * M, "Switch.On", [], "Hydro_Pump"), act(25 * M, "Switch.Off", [], "Hydro_Pump"),
                       act(40 * M, "Switch.On", [], "Hydro_Pump"), act(45 * M, "Switch.Off", [], "Hydro_Pump")]),
        dict(name="interval_changed_to_10", kind="boundary", horizon=60 * M,
             events=[(0, {"Interval_Setting.CurrentLevel": 20.0, "OnTime_Setting.CurrentLevel": 5.0,
                          "Hydro_Pump.Switch": False}),
                     (25 * M, {"Interval_Setting.CurrentLevel": 10.0})],
             expected=[act(0, "Switch.On", [], "Hydro_Pump"), act(5 * M, "Switch.Off", [], "Hydro_Pump"),
                       act(20 * M, "Switch.On", [], "Hydro_Pump"), act(25 * M, "Switch.Off", [], "Hydro_Pump"),
                       act(40 * M, "Switch.On", [], "Hydro_Pump"), act(45 * M, "Switch.Off", [], "Hydro_Pump"),
                       act(50 * M, "Switch.On", [], "Hydro_Pump"), act(55 * M, "Switch.Off", [], "Hydro_Pump")]),
        dict(name="ontime_changed_to_10", kind="boundary", horizon=65 * M,
             events=[(0, {"Interval_Setting.CurrentLevel": 20.0, "OnTime_Setting.CurrentLevel": 5.0,
                          "Hydro_Pump.Switch": False}),
                     (25 * M, {"OnTime_Setting.CurrentLevel": 10.0})],
             expected=[act(0, "Switch.On", [], "Hydro_Pump"), act(5 * M, "Switch.Off", [], "Hydro_Pump"),
                       act(20 * M, "Switch.On", [], "Hydro_Pump"), act(25 * M, "Switch.Off", [], "Hydro_Pump"),
                       act(40 * M, "Switch.On", [], "Hydro_Pump"), act(50 * M, "Switch.Off", [], "Hydro_Pump"),
                       act(60 * M, "Switch.On", [], "Hydro_Pump")]),
    ]))

PROBE_BY_ID = {p["id"]: p for p in PROBES}
