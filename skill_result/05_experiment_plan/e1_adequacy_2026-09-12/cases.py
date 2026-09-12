"""E1 Stage A — external requirements: fixed interpretation + expected traces.

WRITTEN BEFORE ANY TIMELINE IR. The IR for each case lives in irs.py, which was
written only after this file was hashed (see README.md).

Each case fixes:
  id, source, source_url, accessed, verbatim  : provenance
  elements                                    : behavior elements R1..R10 / boundary B1..B5 (README §1)
  boundary_intent                             : True when the case was chosen to stress the IR
  spec                                        : fixed interpretation (English, paper-facing)
  assumptions                                 : researcher additions not present in the source (Korean, for audit)
  devices / binding / selectors               : binding plan (one selector per Service.Method)
  t_start_ms                                  : absolute logical start; t=0 is Monday 00:00 (explorer.runtime.interp.clock_state)
  cron                                        : "" or 5-field cron when the request is calendar-anchored
  histories                                   : events relative to t_start; expected = hand-derived ACTION trace

History fields
  kind      nominal | boundary
  events    [(t_rel_ms, {"Device.Attr": value}), ...]   t=0 entry sets every input
  horizon   last relative time compared
  expected  [(t_rel_ms, "Service.Method", [args], device_id), ...]

Comparison (README §3, decided by whisoo 2026-09-12): same ACTION signature in the same
order, each time within TOLERANCE_MS. Exact-time match is recorded separately.
"""

S = 1000
M = 60 * S
H = 60 * M
TOLERANCE_MS = 1000

MON = 0                     # t=0 is Monday 00:00
def clock(h, m=0):          # absolute ms for Monday hh:mm
    return MON + h * H + m * M


def dev(did, category, *tags):
    return {did: {"category": [category], "tags": list(tags) + [category]}}


def act(t, sm, args, did):
    return (t, sm, list(args), did)


CASES = []

# ─────────────────────────────────────────────────────────────────────────────
# C01  Home Assistant official blueprint motion_light.yaml (mode: restart)
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C01", source="Home Assistant core, blueprints/motion_light.yaml",
    source_url="https://github.com/home-assistant/core/blob/dev/homeassistant/components/automation/blueprints/motion_light.yaml",
    accessed="2026-09-12",
    verbatim=('description: "Turn on a light when motion is detected." / no_motion_wait: "Time to leave the light on '
              'after last motion is detected." / mode: restart / actions: light.turn_on -> wait_for_trigger(motion on->off) '
              '-> delay(no_motion_wait) -> light.turn_off'),
    elements=["R1", "R3", "R7", "B1"], boundary_intent=True,
    spec=("Whenever the hallway motion sensor changes from no-motion to motion, call Switch.On on the hallway light "
          "at that instant, even if the light is already on. After a motion->no-motion change, if no motion is "
          "detected for 120 s continuously, call Switch.Off at the end of those 120 s. A new motion during the "
          "120 s cancels the pending Off and (being a motion rising edge) emits On again. The automation never ends."),
    assumptions=["[가정] no_motion_wait 기본값 120초 사용",
                 "[가정] HA restart 모드를 문자 그대로 해석: 새로운 motion off→on 재트리거마다 turn_on을 다시 호출한다(중복 On 호출도 관측 ACTION)",
                 "[가정] 시작 시 이미 motion=true면 사건이 아니므로 On을 내지 않는다"],
    devices={**dev("Hall_Motion", "MotionSensor", "Hallway"), **dev("Hall_Light", "Switch", "Hallway", "Light")},
    binding={"MotionSensor": ["Hall_Motion"], "Switch": ["Hall_Light"]},
    selectors={"MotionSensor.Motion": "(#Hallway #MotionSensor)", "Switch.On": "(#Hallway #Light)", "Switch.Off": "(#Hallway #Light)"},
    t_start_ms=clock(20, 0), cron="",
    histories=[
        dict(name="single_pass", kind="nominal", horizon=10 * M,
             events=[(0, {"Hall_Motion.Motion": False}), (10 * S, {"Hall_Motion.Motion": True}), (20 * S, {"Hall_Motion.Motion": False})],
             expected=[act(10 * S, "Switch.On", [], "Hall_Light"), act(140 * S, "Switch.Off", [], "Hall_Light")]),
        dict(name="remotion_during_wait_restarts", kind="boundary", horizon=10 * M,
             events=[(0, {"Hall_Motion.Motion": False}), (10 * S, {"Hall_Motion.Motion": True}), (20 * S, {"Hall_Motion.Motion": False}),
                     (60 * S, {"Hall_Motion.Motion": True}), (70 * S, {"Hall_Motion.Motion": False})],
             expected=[act(10 * S, "Switch.On", [], "Hall_Light"), act(60 * S, "Switch.On", [], "Hall_Light"),
                       act(190 * S, "Switch.Off", [], "Hall_Light")]),
        dict(name="motion_stays_long", kind="boundary", horizon=10 * M,
             events=[(0, {"Hall_Motion.Motion": False}), (10 * S, {"Hall_Motion.Motion": True}), (300 * S, {"Hall_Motion.Motion": False})],
             expected=[act(10 * S, "Switch.On", [], "Hall_Light"), act(420 * S, "Switch.Off", [], "Hall_Light")]),
        dict(name="second_pass_after_off", kind="boundary", horizon=12 * M,
             events=[(0, {"Hall_Motion.Motion": False}), (10 * S, {"Hall_Motion.Motion": True}), (20 * S, {"Hall_Motion.Motion": False}),
                     (400 * S, {"Hall_Motion.Motion": True}), (410 * S, {"Hall_Motion.Motion": False})],
             expected=[act(10 * S, "Switch.On", [], "Hall_Light"), act(140 * S, "Switch.Off", [], "Hall_Light"),
                       act(400 * S, "Switch.On", [], "Hall_Light"), act(530 * S, "Switch.Off", [], "Hall_Light")]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C03  IFTTT applet quoted in TAPInspector §V-D
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C03", source="TAPInspector (arXiv 2102.01468v2) §V-D, IFTTT applet",
    source_url="https://arxiv.org/html/2102.01468v2", accessed="2026-09-12",
    verbatim="Turn on fan for 15 minutes when CO₂>1000ppm",
    elements=["R1", "R2"], boundary_intent=False,
    spec=("When the office CO₂ reading changes from ≤1000 to >1000 ppm, call Switch.On on the office fan at that "
          "instant and call Switch.Off exactly 15 minutes later. While the fan run is pending, further crossings "
          "above 1000 are ignored. After the Off, the next crossing from ≤1000 to >1000 starts a new run."),
    assumptions=["[가정] 15분 진행 중 재교차는 무시(single 실행). 대안 해석(15분 재시작)은 채택하지 않음",
                 "[가정] 시작 시 이미 >1000이면 교차 사건이 아니므로 시작하지 않음"],
    devices={**dev("Office_CO2", "CarbonDioxideSensor", "Office"), **dev("Office_Fan", "Switch", "Office", "Fan")},
    binding={"CarbonDioxideSensor": ["Office_CO2"], "Switch": ["Office_Fan"]},
    selectors={"CarbonDioxideSensor.CarbonDioxide": "(#Office #CarbonDioxideSensor)", "Switch.On": "(#Office #Fan)", "Switch.Off": "(#Office #Fan)"},
    t_start_ms=clock(9, 0), cron="",
    histories=[
        dict(name="one_crossing", kind="nominal", horizon=20 * M,
             events=[(0, {"Office_CO2.CarbonDioxide": 800.0}), (60 * S, {"Office_CO2.CarbonDioxide": 1200.0})],
             expected=[act(60 * S, "Switch.On", [], "Office_Fan"), act(960 * S, "Switch.Off", [], "Office_Fan")]),
        dict(name="recross_during_run_ignored", kind="boundary", horizon=20 * M,
             events=[(0, {"Office_CO2.CarbonDioxide": 800.0}), (60 * S, {"Office_CO2.CarbonDioxide": 1200.0}),
                     (120 * S, {"Office_CO2.CarbonDioxide": 900.0}), (180 * S, {"Office_CO2.CarbonDioxide": 1300.0})],
             expected=[act(60 * S, "Switch.On", [], "Office_Fan"), act(960 * S, "Switch.Off", [], "Office_Fan")]),
        dict(name="second_run_after_off", kind="boundary", horizon=40 * M,
             events=[(0, {"Office_CO2.CarbonDioxide": 800.0}), (60 * S, {"Office_CO2.CarbonDioxide": 1200.0}),
                     (1000 * S, {"Office_CO2.CarbonDioxide": 900.0}), (1100 * S, {"Office_CO2.CarbonDioxide": 1200.0})],
             expected=[act(60 * S, "Switch.On", [], "Office_Fan"), act(960 * S, "Switch.Off", [], "Office_Fan"),
                       act(1100 * S, "Switch.On", [], "Office_Fan"), act(2000 * S, "Switch.Off", [], "Office_Fan")]),
        dict(name="already_high_at_start", kind="boundary", horizon=20 * M,
             events=[(0, {"Office_CO2.CarbonDioxide": 1500.0})],
             expected=[]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C04  IFTTT applet quoted in TAPInspector §V-D (calendar anchor)
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C04", source="TAPInspector (arXiv 2102.01468v2) §V-D, IFTTT applet",
    source_url="https://arxiv.org/html/2102.01468v2", accessed="2026-09-12",
    verbatim="At noon turn your fan on for 15 minutes",
    elements=["R9", "R2"], boundary_intent=False,
    spec="Every day at 12:00:00 call Switch.On on the fan and call Switch.Off at 12:15:00. No inputs are read.",
    assumptions=["[가정] 매일 반복(cron '0 12 * * *'). 실행 확인은 한 번의 발화 창(12:00~12:15)만 검사"],
    devices=dev("Office_Fan", "Switch", "Office", "Fan"),
    binding={"Switch": ["Office_Fan"]},
    selectors={"Switch.On": "(#Office #Fan)", "Switch.Off": "(#Office #Fan)"},
    t_start_ms=clock(12, 0), cron="0 12 * * *",
    histories=[
        dict(name="noon_window", kind="nominal", horizon=20 * M, events=[(0, {})],
             expected=[act(0, "Switch.On", [], "Office_Fan"), act(15 * M, "Switch.Off", [], "Office_Fan")]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C05  HA community 520305 (2023-01-18)
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C05", source="Home Assistant Community thread 520305 (2023-01-18)",
    source_url="https://community.home-assistant.io/t/how-to-set-notifications-when-door-is-left-open/520305", accessed="2026-09-12",
    verbatim=("set notification if door is left open for 2 minutes and if not closed after that it should send "
              "notifications each minute"),
    elements=["R3", "R7"], boundary_intent=False,
    spec=("When the back door has been open continuously for 2 minutes, send an SMS at that instant, then send one "
          "every 60 s while the door stays open. Sending stops as soon as the door closes. If the door closes before "
          "2 minutes the elapsed time is discarded. After a close, a new opening starts again from a full 2 minutes. "
          "Never ends."),
    assumptions=["[가정] Contact=false 가 '열림'", "[가정] 알림 = MessageSender.SendSms 고정 인자",
                 "[가정] 닫힌 뒤 다시 열리면 알림 간격 중이었더라도 2분 지속부터 다시 셈"],
    devices={**dev("Back_Door", "ContactSensor", "Back", "Door"), **dev("Phone_SMS", "MessageSender", "Owner")},
    binding={"ContactSensor": ["Back_Door"], "MessageSender": ["Phone_SMS"]},
    selectors={"ContactSensor.Contact": "(#Back #ContactSensor)", "MessageSender.SendSms": "(#Owner #MessageSender)"},
    t_start_ms=clock(18, 0), cron="",
    histories=[
        dict(name="open_then_close_at_400", kind="nominal", horizon=10 * M,
             events=[(0, {"Back_Door.Contact": True}), (10 * S, {"Back_Door.Contact": False}), (400 * S, {"Back_Door.Contact": True})],
             expected=[act(t * S, "MessageSender.SendSms", ["owner", "Back door is open", "door"], "Phone_SMS")
                       for t in (130, 190, 250, 310, 370)]),
        dict(name="closed_before_2min_restarts", kind="boundary", horizon=6 * M,
             events=[(0, {"Back_Door.Contact": True}), (10 * S, {"Back_Door.Contact": False}), (60 * S, {"Back_Door.Contact": True}),
                     (100 * S, {"Back_Door.Contact": False}), (300 * S, {"Back_Door.Contact": True})],
             expected=[act(t * S, "MessageSender.SendSms", ["owner", "Back door is open", "door"], "Phone_SMS") for t in (220, 280)]),
        dict(name="reopen_after_close", kind="boundary", horizon=10 * M,
             events=[(0, {"Back_Door.Contact": True}), (10 * S, {"Back_Door.Contact": False}), (200 * S, {"Back_Door.Contact": True}),
                     (300 * S, {"Back_Door.Contact": False}), (500 * S, {"Back_Door.Contact": True})],
             expected=[act(t * S, "MessageSender.SendSms", ["owner", "Back door is open", "door"], "Phone_SMS") for t in (130, 190, 420, 480)]),
        dict(name="brief_close_between_notifications", kind="boundary", horizon=10 * M,
             events=[(0, {"Back_Door.Contact": True}), (10 * S, {"Back_Door.Contact": False}), (395 * S, {"Back_Door.Contact": True}),
                     (405 * S, {"Back_Door.Contact": False})],
             expected=[act(t * S, "MessageSender.SendSms", ["owner", "Back door is open", "door"], "Phone_SMS")
                       for t in (130, 190, 250, 310, 370, 525, 585)]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C07  HA community 783900 (2024-10-20) — composite case
# ─────────────────────────────────────────────────────────────────────────────
def _c07_expected(close_at=None, cycles=7, blinks=10, step=500, pause=5 * M, start=15 * M, b0=70.0):
    """Hand model of the C07 contract. Times relative to t_start (21:55).
    start = instant at which (after 22:00 AND door open) has held 10 min.
    close_at = door-close instant (None = stays open)."""
    out, t = [], start
    for c in range(cycles):
        # blinking: 10 x (dim to 10, back to 100), 0.5 s per step
        for k in range(blinks):
            for level in (10.0, 100.0):
                if close_at is not None and t >= close_at:
                    out.append(act(close_at, "Light.MoveToBrightness", [b0, 0.0], "Kitchen_Light"))
                    return out
                out.append(act(t, "Light.MoveToBrightness", [level, 0.0], "Kitchen_Light"))
                t += step
        # restore original brightness
        if close_at is not None and t >= close_at:
            out.append(act(close_at, "Light.MoveToBrightness", [b0, 0.0], "Kitchen_Light"))
            return out
        out.append(act(t, "Light.MoveToBrightness", [b0, 0.0], "Kitchen_Light"))
        if c == cycles - 1:
            return out
        # pause; door closing during the pause ends the automation with no further ACTION
        if close_at is not None and t < close_at <= t + pause:
            return out
        t += pause
    return out


CASES.append(dict(
    id="C07", source="Home Assistant Community thread 783900 (2024-10-20)",
    source_url="https://community.home-assistant.io/t/how-to-automate-open-door-notifications/783900", accessed="2026-09-12",
    verbatim=('trigger: "garage door is left open after 22:00 for more than 10 minutes"; "Blink the kitchen lights by '
              'dimming up and down 10 times in quick succession"; "pause for 5 minutes"; "Repeat the cycle up to 7 times"; '
              '"If at any point during the blinking cycles, the garage door is closed, stop the automation immediately"; '
              '"Ensure the kitchen lights return to their original state ... after the automation ends or during the pauses"'),
    elements=["R9", "R3", "R5", "R8", "B5", "B1"], boundary_intent=True,
    spec=("From 22:00, when the garage door has been open continuously for 10 minutes (counted only while the clock is "
          "at or after 22:00), read the kitchen light brightness B0 and run up to 7 cycles. A cycle is 10 blinks, each "
          "blink = MoveToBrightness(10) then 0.5 s later MoveToBrightness(100), 0.5 s apart; after the 10th blink restore "
          "MoveToBrightness(B0); then pause 5 minutes. If the door closes during blinking, restore B0 at that instant and "
          "stop. If the door closes during a pause, stop with no further call (B0 already restored). After the 7th cycle's "
          "restore, stop."),
    assumptions=["[가정] '깜빡임' = MoveToBrightness(10)/(100) 를 0.5초 간격, Rate=0", "[가정] 원상태 = 시작 시 읽은 밝기 B0 하나 (색 등은 제외)",
                 "[가정] 22:00 이후 조건과 문 열림의 지속 10분은 둘이 동시에 성립한 시각부터 셈",
                 "[가정] 자동화는 한 번 실행되고 끝남(다음 날 재시작은 범위 밖)", "[가정] Contact=false 가 '열림'"],
    devices={**dev("Garage_Door", "ContactSensor", "Garage", "Door"), **dev("Kitchen_Light", "Light", "Kitchen")},
    binding={"ContactSensor": ["Garage_Door"], "Light": ["Kitchen_Light"]},
    selectors={"ContactSensor.Contact": "(#Garage #ContactSensor)", "Light.CurrentBrightness": "(#Kitchen #Light)",
               "Light.MoveToBrightness": "(#Kitchen #Light)"},
    t_start_ms=clock(21, 55), cron="",
    histories=[
        # door opens 21:58 (rel 180 s); conjunction true from 22:00 (rel 300 s); 10 min -> rel 900 s = start
        dict(name="stays_open_all_7_cycles", kind="nominal", horizon=60 * M,
             events=[(0, {"Garage_Door.Contact": True, "Kitchen_Light.CurrentBrightness": 70.0}), (180 * S, {"Garage_Door.Contact": False})],
             expected=_c07_expected()),
        dict(name="closes_during_second_pause", kind="boundary", horizon=60 * M,
             events=[(0, {"Garage_Door.Contact": True, "Kitchen_Light.CurrentBrightness": 70.0}), (180 * S, {"Garage_Door.Contact": False}),
                     (15 * M + 10 * S + 5 * M + 10 * S + 60 * S, {"Garage_Door.Contact": True})],   # rel 1580 s, in pause #2
             expected=_c07_expected(close_at=15 * M + 10 * S + 5 * M + 10 * S + 60 * S)),
        dict(name="closes_during_first_blinking", kind="boundary", horizon=60 * M,
             events=[(0, {"Garage_Door.Contact": True, "Kitchen_Light.CurrentBrightness": 70.0}), (180 * S, {"Garage_Door.Contact": False}),
                     (15 * M + 3 * S + 200, {"Garage_Door.Contact": True})],                          # rel 903.2 s, mid-blink (was 903.25: off the 100 ms input grid; fixed 2026-09-12 after hashing)
             expected=_c07_expected(close_at=15 * M + 3 * S + 200)),
        dict(name="closed_before_10min_no_run", kind="boundary", horizon=40 * M,
             events=[(0, {"Garage_Door.Contact": True, "Kitchen_Light.CurrentBrightness": 70.0}), (180 * S, {"Garage_Door.Contact": False}),
                     (700 * S, {"Garage_Door.Contact": True})],
             expected=[]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C09  AutoTap Study 1 template (g), converted from property to automation
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C09", source="AutoTap (ICSE 2019) §III, Event-Event Conditional sample",
    source_url="https://homes.cs.washington.edu/~jessejm/data/ZhangICSE2019.pdf", accessed="2026-09-12",
    verbatim="My smart door lock should always lock after I come in.",
    elements=["R1", "R4"], boundary_intent=False,
    spec=("Every time the entrance presence sensor changes from absent to present, call DoorLock.Lock at that "
          "instant. A presence that is already true when the automation starts is not an arrival. Never ends."),
    assumptions=["[연구자 변환] 원문은 안전 속성; '들어오면 잠근다' 자동화로 바꿈", "[가정] 잠금 시각 = 도착 순간(지연 없음)",
                 "[가정] 시작 시 이미 present 면 사건이 아님"],
    devices={**dev("Entrance_Presence", "PresenceSensor", "Entrance"), **dev("Front_Lock", "DoorLock", "Entrance", "Front")},
    binding={"PresenceSensor": ["Entrance_Presence"], "DoorLock": ["Front_Lock"]},
    selectors={"PresenceSensor.Presence": "(#Entrance #PresenceSensor)", "DoorLock.Lock": "(#Entrance #DoorLock)"},
    t_start_ms=clock(17, 0), cron="",
    histories=[
        dict(name="one_arrival", kind="nominal", horizon=5 * M,
             events=[(0, {"Entrance_Presence.Presence": False}), (30 * S, {"Entrance_Presence.Presence": True})],
             expected=[act(30 * S, "DoorLock.Lock", [], "Front_Lock")]),
        dict(name="two_arrivals", kind="boundary", horizon=5 * M,
             events=[(0, {"Entrance_Presence.Presence": False}), (30 * S, {"Entrance_Presence.Presence": True}),
                     (100 * S, {"Entrance_Presence.Presence": False}), (200 * S, {"Entrance_Presence.Presence": True})],
             expected=[act(30 * S, "DoorLock.Lock", [], "Front_Lock"), act(200 * S, "DoorLock.Lock", [], "Front_Lock")]),
        dict(name="present_at_start_is_not_arrival", kind="boundary", horizon=5 * M,
             events=[(0, {"Entrance_Presence.Presence": True}), (50 * S, {"Entrance_Presence.Presence": False}),
                     (80 * S, {"Entrance_Presence.Presence": True})],
             expected=[act(80 * S, "DoorLock.Lock", [], "Front_Lock")]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C11  AutoTap Study 2 Task 11 (Roomba / curtain) — two-direction rule
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C11", source="AutoTap (ICSE 2019) §VI-A Task 11 and authors' rule explanation",
    source_url="https://homes.cs.washington.edu/~jessejm/data/ZhangICSE2019.pdf", accessed="2026-09-12",
    verbatim=('"IF Roomba becomes on WHILE the curtain is open, THEN close the curtain; IF curtain becomes open WHILE '
              'Roomba is on, THEN turn off Roomba" (property: "Roomba is on should NEVER be active WHILE curtain is open")'),
    elements=["R1", "B2"], boundary_intent=True,
    spec=("Two reactions in one automation. (a) When the vacuum's operating state changes to \"running\" while the "
          "curtain position is >0 (open), call WindowCovering.DownOrClose at that instant. (b) When the curtain "
          "position changes from 0 to >0 while the vacuum state is \"running\", call "
          "RobotVacuumCleaner.SetRobotVacuumCleanerRunMode(\"idle\") at that instant. If both changes occur at the same "
          "instant, do (a) then (b). Never ends."),
    assumptions=["[가정] Roomba on = OperatingState == 'running'; 끄기 = SetRobotVacuumCleanerRunMode('idle') "
                 "(2026-09-12 해시 후 수정: 처음 쓴 'cleaning'/'stop' 은 catalog enum 에 없음 — 값 이름만 바꿈, 행동 해석 불변)",
                 "[가정] 커튼 열림 = CurrentPosition > 0", "[가정] 동시 변화면 (a) 다음 (b) 순서로 둘 다 호출",
                 "[메모] 이 사례의 두 rule 에는 delay·중첩 인스턴스·action→trigger 되먹임이 없어 직전 snapshot 판별이 두 독립 rule 과 같은 trace 를 낸다. 일반적으로 snapshot 이 병렬 rule 을 대체한다는 주장이 아님(감사 2026-09-12)",
                 "[가정] 자동화의 ACTION 이 만든 상태 변화(커튼 닫힘 등)는 입력 이력에 명시된 시점에만 반영"],
    devices={**dev("LR_Vacuum", "RobotVacuumCleaner", "LivingRoom"), **dev("LR_Curtain", "WindowCovering", "LivingRoom", "Curtain")},
    binding={"RobotVacuumCleaner": ["LR_Vacuum"], "WindowCovering": ["LR_Curtain"]},
    selectors={"RobotVacuumCleaner.RobotVacuumCleanerOperatingState": "(#LivingRoom #RobotVacuumCleaner)",
               "RobotVacuumCleaner.SetRobotVacuumCleanerRunMode": "(#LivingRoom #RobotVacuumCleaner)",
               "WindowCovering.CurrentPosition": "(#LivingRoom #Curtain)", "WindowCovering.DownOrClose": "(#LivingRoom #Curtain)"},
    t_start_ms=clock(10, 0), cron="",
    histories=[
        dict(name="vacuum_starts_while_open", kind="nominal", horizon=5 * M,
             events=[(0, {"LR_Vacuum.RobotVacuumCleanerOperatingState": "docked", "LR_Curtain.CurrentPosition": 100}),
                     (60 * S, {"LR_Vacuum.RobotVacuumCleanerOperatingState": "running"})],
             expected=[act(60 * S, "WindowCovering.DownOrClose", [], "LR_Curtain")]),
        dict(name="curtain_opens_while_cleaning", kind="nominal", horizon=5 * M,
             events=[(0, {"LR_Vacuum.RobotVacuumCleanerOperatingState": "running", "LR_Curtain.CurrentPosition": 0}),
                     (60 * S, {"LR_Curtain.CurrentPosition": 100})],
             expected=[act(60 * S, "RobotVacuumCleaner.SetRobotVacuumCleanerRunMode", ["idle"], "LR_Vacuum")]),
        dict(name="both_change_together", kind="boundary", horizon=5 * M,
             events=[(0, {"LR_Vacuum.RobotVacuumCleanerOperatingState": "docked", "LR_Curtain.CurrentPosition": 0}),
                     (60 * S, {"LR_Vacuum.RobotVacuumCleanerOperatingState": "running", "LR_Curtain.CurrentPosition": 100})],
             expected=[act(60 * S, "WindowCovering.DownOrClose", [], "LR_Curtain"),
                       act(60 * S, "RobotVacuumCleaner.SetRobotVacuumCleanerRunMode", ["idle"], "LR_Vacuum")]),
        dict(name="sequence_of_both_directions", kind="boundary", horizon=10 * M,
             events=[(0, {"LR_Vacuum.RobotVacuumCleanerOperatingState": "docked", "LR_Curtain.CurrentPosition": 100}),
                     (60 * S, {"LR_Vacuum.RobotVacuumCleanerOperatingState": "running"}),
                     (70 * S, {"LR_Curtain.CurrentPosition": 0}),           # curtain reached closed
                     (200 * S, {"LR_Curtain.CurrentPosition": 100}),        # someone opens it while cleaning
                     (210 * S, {"LR_Vacuum.RobotVacuumCleanerOperatingState": "docked"})],
             expected=[act(60 * S, "WindowCovering.DownOrClose", [], "LR_Curtain"),
                       act(200 * S, "RobotVacuumCleaner.SetRobotVacuumCleanerRunMode", ["idle"], "LR_Vacuum")]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C15  Ur et al. CHI 2014, participant behavior
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C15", source="Ur et al., Practical Trigger-Action Programming in the Smart Home (CHI 2014), participant quote",
    source_url="https://www.blaseur.com/papers/TriggerActionCHI14.pdf", accessed="2026-09-12",
    verbatim="When I get up at night, I would want my lights to turn on and off as I enter and exit the room.",
    elements=["R4", "R7", "R9"], boundary_intent=False,
    spec=("Night is 22:00–05:59 by the clock. Whenever the bedroom presence changes absent->present during night, call "
          "Switch.On; whenever it then changes present->absent, call Switch.Off (also if the exit happens after 06:00). "
          "Entries outside night do nothing. Never ends."),
    assumptions=["[가정] 밤 = Clock.Hour >= 22 또는 < 6", "[가정] 밤에 들어와 켠 뒤 06:00 이후에 나가도 Off 는 낸다",
                 "[가정] '방' = 침실 하나, 사람 감지 = PresenceSensor"],
    devices={**dev("Bed_Presence", "PresenceSensor", "Bedroom"), **dev("Bed_Light", "Switch", "Bedroom", "Light")},
    binding={"PresenceSensor": ["Bed_Presence"], "Switch": ["Bed_Light"]},
    selectors={"PresenceSensor.Presence": "(#Bedroom #PresenceSensor)", "Switch.On": "(#Bedroom #Light)", "Switch.Off": "(#Bedroom #Light)"},
    t_start_ms=clock(21, 30), cron="",
    histories=[
        dict(name="two_visits_at_night", kind="nominal", horizon=3 * H,
             events=[(0, {"Bed_Presence.Presence": False}),
                     (2 * H + 60 * S, {"Bed_Presence.Presence": True}), (2 * H + 120 * S, {"Bed_Presence.Presence": False}),
                     (2 * H + 300 * S, {"Bed_Presence.Presence": True}), (2 * H + 360 * S, {"Bed_Presence.Presence": False})],
             expected=[act(2 * H + 60 * S, "Switch.On", [], "Bed_Light"), act(2 * H + 120 * S, "Switch.Off", [], "Bed_Light"),
                       act(2 * H + 300 * S, "Switch.On", [], "Bed_Light"), act(2 * H + 360 * S, "Switch.Off", [], "Bed_Light")]),
        dict(name="entry_before_night_ignored", kind="boundary", horizon=2 * H,
             events=[(0, {"Bed_Presence.Presence": False}), (600 * S, {"Bed_Presence.Presence": True}),   # 21:40
                     (900 * S, {"Bed_Presence.Presence": False}),                                          # 21:45
                     (2400 * S, {"Bed_Presence.Presence": True}), (2700 * S, {"Bed_Presence.Presence": False})],  # 22:10 / 22:15
             expected=[act(2400 * S, "Switch.On", [], "Bed_Light"), act(2700 * S, "Switch.Off", [], "Bed_Light")]),
        dict(name="in_room_when_night_starts", kind="boundary", horizon=2 * H,
             events=[(0, {"Bed_Presence.Presence": False}), (600 * S, {"Bed_Presence.Presence": True}),   # enters 21:40, stays
                     (3600 * S, {"Bed_Presence.Presence": False})],                                        # leaves 22:30
             expected=[]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C16  Ur et al. CHI 2014, lab task I
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C16", source="Ur et al. (CHI 2014) Table 1, Task I",
    source_url="https://www.blaseur.com/papers/TriggerActionCHI14.pdf", accessed="2026-09-12",
    verbatim="If it is 10:00pm and my bedroom door is closed and the lights are off, turn the television off.",
    elements=["R9", "R6"], boundary_intent=False,
    spec=("Every day at 22:00:00, if the bedroom door contact is closed and the bedroom light switch is off at that "
          "instant, call Switch.Off on the television; otherwise do nothing. No later re-check."),
    assumptions=["[가정] '10:00pm' = 22:00 정각 한 번 검사 (창 아님)", "[가정] Contact=true 가 '닫힘'; TV 끄기 = TV 기기의 Switch.Off"],
    devices={**dev("Bed_Door", "ContactSensor", "Bedroom", "Door"), **dev("Bed_Light", "Switch", "Bedroom", "Light"),
             **dev("Bed_TV", "Switch", "Bedroom", "Television")},
    # Switch appears twice with different methods (read Switch.Switch on the light, call Switch.Off on the TV):
    # one selector per Service.Method, expressed as two binding slots in IR walk order (gate.parse_binding).
    # 2026-09-12 fix after hashing: was {"Switch": ["Bed_Light", "Bed_TV"]}, which would mean one fan-out slot.
    binding={"ContactSensor": ["Bed_Door"], "Switch": ["Bed_Light"], "Switch#2": ["Bed_TV"]},
    selectors={"ContactSensor.Contact": "(#Bedroom #ContactSensor)", "Switch.Switch": "(#Bedroom #Light)", "Switch.Off": "(#Bedroom #Television)"},
    t_start_ms=clock(22, 0), cron="0 22 * * *",
    histories=[
        dict(name="conditions_hold", kind="nominal", horizon=5 * M,
             events=[(0, {"Bed_Door.Contact": True, "Bed_Light.Switch": False})],
             expected=[act(0, "Switch.Off", [], "Bed_TV")]),
        dict(name="light_on_no_action", kind="boundary", horizon=5 * M,
             events=[(0, {"Bed_Door.Contact": True, "Bed_Light.Switch": True}), (60 * S, {"Bed_Light.Switch": False})],
             expected=[]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C18  Huang & Cakmak (UbiComp 2015) Study 2, Q3
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C18", source="Huang & Cakmak, Supporting Mental Model Accuracy in TAP (UbiComp 2015), Table 5 Q3",
    source_url="https://homes.cs.washington.edu/~mcakmak/pdfs/2015/huang2015ubicomp.pdf", accessed="2026-09-12",
    verbatim="If the doorbell rings and the time is 3:00 pm, then unlock the front door for 10 seconds",
    elements=["R1", "R9", "R2"], boundary_intent=False,
    spec=("While the clock hour is 15 (15:00:00–15:59:59), each doorbell 'pushed' event calls DoorLock.Unlock at that "
          "instant and DoorLock.Lock 10 s later. Presses while an unlock is pending are ignored. Presses outside the "
          "hour do nothing. Never ends."),
    assumptions=["[가정] '3:00 pm' = 15시 한 시간 창 (원 논문이 순간/창 해석이 갈린다고 보고한 항목)",
                 "[가정] 벨 = Button 값이 'pushed' 로 바뀌는 사건; 같은 값이 유지되는 것은 새 사건이 아님",
                 "[가정] 10초 진행 중 재누름 무시"],
    devices={**dev("Doorbell", "Button", "Entrance"), **dev("Front_Lock", "DoorLock", "Entrance", "Front")},
    binding={"Button": ["Doorbell"], "DoorLock": ["Front_Lock"]},
    selectors={"Button.Button": "(#Entrance #Button)", "DoorLock.Unlock": "(#Entrance #DoorLock)", "DoorLock.Lock": "(#Entrance #DoorLock)"},
    t_start_ms=clock(14, 58), cron="",
    histories=[
        dict(name="press_in_window", kind="nominal", horizon=10 * M,
             events=[(0, {"Doorbell.Button": "released"}), (180 * S, {"Doorbell.Button": "pushed"}), (181 * S, {"Doorbell.Button": "released"})],
             expected=[act(180 * S, "DoorLock.Unlock", [], "Front_Lock"), act(190 * S, "DoorLock.Lock", [], "Front_Lock")]),
        dict(name="press_before_and_after_window", kind="boundary", horizon=65 * M,
             events=[(0, {"Doorbell.Button": "released"}), (60 * S, {"Doorbell.Button": "pushed"}), (61 * S, {"Doorbell.Button": "released"}),
                     (63 * M, {"Doorbell.Button": "pushed"}), (63 * M + S, {"Doorbell.Button": "released"})],   # 14:59 and 16:01
             expected=[]),
        dict(name="double_press_ignored", kind="boundary", horizon=10 * M,
             events=[(0, {"Doorbell.Button": "released"}), (180 * S, {"Doorbell.Button": "pushed"}), (181 * S, {"Doorbell.Button": "released"}),
                     (185 * S, {"Doorbell.Button": "pushed"}), (186 * S, {"Doorbell.Button": "released"})],
             expected=[act(180 * S, "DoorLock.Unlock", [], "Front_Lock"), act(190 * S, "DoorLock.Lock", [], "Front_Lock")]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C19  Huang & Cakmak (UbiComp 2015) Study 2, P3
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C19", source="Huang & Cakmak (UbiComp 2015), Table 4 P3",
    source_url="https://homes.cs.washington.edu/~mcakmak/pdfs/2015/huang2015ubicomp.pdf", accessed="2026-09-12",
    verbatim=("Your work starts at 9:00 am. On days when you get to work on time, you want to send an email to yourself "
              "saying \"I got to work on time!\""),
    elements=["R10", "R9"], boundary_intent=False,
    spec=("Each day from 06:00, wait for the office presence sensor to change to present. If that happens at or before "
          "09:00:00, call EmailProvider.SendMail at that instant and stop for the day. If 09:00:00 passes without "
          "arrival, stop for the day with no call."),
    assumptions=["[가정] 감시 시작 06:00 (cron '0 6 * * *'); 실행 확인은 하루 창만",
                 "[가정] '정시' = 09:00:00 이하 (같음 포함)", "[가정] 도착 = PresenceSensor 가 present 로 바뀜"],
    devices={**dev("Office_Presence", "PresenceSensor", "Office"), **dev("My_Mail", "EmailProvider", "Owner")},
    binding={"PresenceSensor": ["Office_Presence"], "EmailProvider": ["My_Mail"]},
    selectors={"PresenceSensor.Presence": "(#Office #PresenceSensor)", "EmailProvider.SendMail": "(#Owner #EmailProvider)"},
    t_start_ms=clock(6, 0), cron="0 6 * * *",
    histories=[
        dict(name="arrive_0800", kind="nominal", horizon=4 * H,
             events=[(0, {"Office_Presence.Presence": False}), (2 * H, {"Office_Presence.Presence": True})],
             expected=[act(2 * H, "EmailProvider.SendMail", ["me@example.com", "On time", "I got to work on time!"], "My_Mail")]),
        dict(name="arrive_0930_no_mail", kind="boundary", horizon=4 * H,
             events=[(0, {"Office_Presence.Presence": False}), (3 * H + 30 * M, {"Office_Presence.Presence": True})],
             expected=[]),
        dict(name="arrive_exactly_0900", kind="boundary", horizon=4 * H,
             events=[(0, {"Office_Presence.Presence": False}), (3 * H, {"Office_Presence.Presence": True})],
             expected=[act(3 * H, "EmailProvider.SendMail", ["me@example.com", "On time", "I got to work on time!"], "My_Mail")]),
        # added after the B audit (2026-09-12): the audit found the real risk is a presence already true at 06:00
        dict(name="already_present_at_start_no_mail", kind="boundary", horizon=4 * H,
             events=[(0, {"Office_Presence.Presence": True})],
             expected=[]),
        dict(name="arrive_0900_30_no_mail", kind="boundary", horizon=4 * H,
             events=[(0, {"Office_Presence.Presence": False}), (3 * H + 30 * S, {"Office_Presence.Presence": True})],
             expected=[]),
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# C20  Brackenbury et al. CHI 2019, Table 1 Event–Event paradigm
# ─────────────────────────────────────────────────────────────────────────────
CASES.append(dict(
    id="C20", source="Brackenbury et al., How Users Interpret Bugs in TAP (CHI 2019), Table 1",
    source_url="https://par.nsf.gov/biblio/10106413", accessed="2026-09-12",
    verbatim=("IF Sally enters the bedroom AND AFTERWARDS the sun sets WITHIN 2 hours THEN turn on the bedroom lights. "
              "(unordered variant: IF Sally enters the bedroom AND the sun sets WITHIN 2 hours THEN ...)"),
    elements=["R1", "R2", "B1"], boundary_intent=True,   # B3 removed after the B audit: the unordered variant is a separate requirement
    spec=("ORDERED variant (evaluated): when bedroom presence changes absent->present, open a 2-hour window. If the "
          "outdoor brightness changes from ≥50 to <50 (sunset) inside the window, call Switch.On at that instant and "
          "close the window. A new absent->present change during an open window restarts the window. If the window "
          "expires, nothing happens. Never ends. UNORDERED variant (recorded as B3, not executed): the rule also fires "
          "if sunset happened up to 2 hours BEFORE the entry."),
    assumptions=["[가정] 해넘이 = LightSensor.Brightness 가 50 아래로 떨어지는 사건", "[가정] 창 안 재입장은 창을 다시 시작(restart)",
                 "[감사 2026-09-12] 이 사례는 순서형 문장(AND AFTERWARDS)만을 대상으로 확정. paired unordered variant requires look-back event memory and is excluded from this ordered-variant case — Stage B limitation candidate (B3)"],
    devices={**dev("Bed_Presence", "PresenceSensor", "Bedroom"), **dev("Outdoor_Lux", "LightSensor", "Outdoor"),
             **dev("Bed_Light", "Switch", "Bedroom", "Light")},
    binding={"PresenceSensor": ["Bed_Presence"], "LightSensor": ["Outdoor_Lux"], "Switch": ["Bed_Light"]},
    selectors={"PresenceSensor.Presence": "(#Bedroom #PresenceSensor)", "LightSensor.Brightness": "(#Outdoor #LightSensor)",
               "Switch.On": "(#Bedroom #Light)"},
    t_start_ms=clock(16, 0), cron="",
    histories=[
        dict(name="enter_then_sunset_in_window", kind="nominal", horizon=4 * H,
             events=[(0, {"Bed_Presence.Presence": False, "Outdoor_Lux.Brightness": 500.0}),
                     (600 * S, {"Bed_Presence.Presence": True}), (3600 * S, {"Outdoor_Lux.Brightness": 20.0})],
             expected=[act(3600 * S, "Switch.On", [], "Bed_Light")]),
        dict(name="sunset_after_window_expired", kind="boundary", horizon=4 * H,
             events=[(0, {"Bed_Presence.Presence": False, "Outdoor_Lux.Brightness": 500.0}),
                     (600 * S, {"Bed_Presence.Presence": True}), (8400 * S, {"Outdoor_Lux.Brightness": 20.0})],
             expected=[]),
        dict(name="sunset_before_entry_ordered_no_fire", kind="boundary", horizon=4 * H,
             events=[(0, {"Bed_Presence.Presence": False, "Outdoor_Lux.Brightness": 500.0}),
                     (600 * S, {"Outdoor_Lux.Brightness": 20.0}), (1200 * S, {"Bed_Presence.Presence": True})],
             expected=[]),
        dict(name="reentry_restarts_window", kind="boundary", horizon=4 * H,
             events=[(0, {"Bed_Presence.Presence": False, "Outdoor_Lux.Brightness": 500.0}),
                     (600 * S, {"Bed_Presence.Presence": True}), (3000 * S, {"Bed_Presence.Presence": False}),
                     (6000 * S, {"Bed_Presence.Presence": True}), (8000 * S, {"Outdoor_Lux.Brightness": 20.0})],
             expected=[act(8000 * S, "Switch.On", [], "Bed_Light")]),
    ]))

CASE_BY_ID = {c["id"]: c for c in CASES}

if __name__ == "__main__":
    import json
    from pathlib import Path
    out = Path(__file__).with_name("cases.json")
    out.write_text(json.dumps(CASES, ensure_ascii=False, indent=1, default=str))
    print(f"{len(CASES)} cases, {sum(len(c['histories']) for c in CASES)} histories -> {out}")
