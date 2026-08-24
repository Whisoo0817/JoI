# -*- coding: utf-8 -*-
"""벤치마크용 공간 40개 (기기 목록 40벌) → bench/spaces.json.

명령어마다 connected_devices 를 즉석에서 만들지 않고, 공간 40개를 먼저 만들어
명령어에는 space_id 만 붙인다. 같은 문장이 공간에 따라 실행/되묻기/거절로
갈리게 하는 것이 목적 (기기 없음·같은 종류 여러 대·별명 유무를 공간이 통제).

구성: 가정집 20 · 오피스 6 · 연구실 5 · 농장 4 · 공장 5.
LAB01 은 run.py 의 실제 연구실 허브 인벤토리 그대로(카테고리만 3.0.0 이름으로).

  python bench/build_spaces.py        # bench/spaces.json 생성 + 요약 출력
"""
import ast, json, os, re, sys

from nick_lexicon import to_en

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CATALOG = os.path.join(ROOT, "files", "service_list_ver3.1.0.json")

# 허브가 언제나 제공하는 것 — 기기 수(≥10)에는 세지 않는다.
SYSTEM = [("Clock", "Clock"), ("GlobalVariable", "전역 변수"),
          ("NotificationProvider", "알림"), ("SunProvider", "해")]

# ── 미리 정의된 전역 변수 ──────────────────────────────────────────────────
# 40 공간 중 정확히 20곳에만 둔다(반반). 나머지 20곳은 허브가 변수를 지원하지만
# 정의된 것이 없는 상태 — 같은 문장이 공간에 따라 변수를 읽거나 센서를 읽게 된다.
#
# 읽기 규칙 (명령문이 정한다, 공간이 뒤집지 못한다):
#   1) 기기를 대놓고 지목하면  → 그 기기.  "움직임 센서에 사람이 감지되면" = MotionSensor
#   2) 지목이 없으면          → 전역 변수가 있으면 그것, 없으면 MotionSensor/PresenceSensor
#      "거실에 사람이 있는 동안" = Human 변수 있으면 Human, 없으면 센서
# ── 외부 정보 제공자를 둘 공간 ────────────────────────────────────────────
# 있는 공간에서는 정상 실행, 없는 공간에서는 같은 문장이 되묻기/거절이 된다.
WEATHER = [        # 28곳 — 바깥 날씨는 SunProvider 처럼 시스템으로 붙는다.
                   # 없는 12곳에서는 날씨 조건이 되묻기·거절이 된다.
    "HOME01", "HOME02", "HOME03", "HOME04", "HOME05", "HOME06", "HOME07", "HOME08",
    "HOME09", "HOME10", "HOME12", "HOME13", "HOME15", "HOME16", "HOME18", "HOME19",
    "OFFICE01", "OFFICE02", "OFFICE03", "OFFICE05",
    "LAB01", "LAB03",
    "FARM01", "FARM02", "FARM03", "FARM04",
    "FACT01", "FACT05",
]
PERSON_TRACKER = [  # 20곳 — 폰 위치는 집에서 제일 많이 쓰인다
    "HOME02", "HOME03", "HOME04", "HOME05", "HOME06", "HOME07", "HOME08", "HOME11",
    "HOME13", "HOME15", "HOME16", "HOME18", "HOME19", "HOME20",
    "OFFICE01", "OFFICE02", "OFFICE05", "OFFICE06", "LAB01", "LAB04",
]
CALENDAR = [       # 12곳 — 일정은 오피스·연구실 쪽
    "OFFICE01", "OFFICE02", "OFFICE03", "OFFICE04", "OFFICE05", "OFFICE06",
    "LAB01", "LAB03", "LAB04", "HOME15", "HOME19", "FACT01",
]

# ── 재실 판단 주체: 공간마다 딱 하나 ──────────────────────────────────
# "거실에 사람 있으면" 처럼 기기를 지목하지 않은 문장의 정답을 하나로 고정한다.
#   global   : Human 전역 변수를 읽는다 (센서가 같이 있어도 지목 없으면 Human)
#   motion   : MotionSensor 만 있다
#   presence : PresenceSensor 만 있다
#   phone    : 재실 센서가 없고 PersonTracker 로 판단한다 (1인 거주)
#   none     : 판단할 방법이 없다 → 되묻기/거절
# 기기를 대놓고 지목하면 이 표와 무관하게 그 기기를 쓴다.
# 이 표에 맞춰 build 뒤에 겹치는 센서를 잘라낸다(_prune_occupancy).
OCCUPANCY = {
    # 전역 변수 15
    "HOME03": "global", "HOME04": "global", "HOME06": "global", "HOME08": "global",
    "HOME09": "global", "HOME12": "global", "HOME13": "global", "HOME15": "global",
    "HOME18": "global", "OFFICE02": "global", "OFFICE03": "global", "OFFICE05": "global",
    "LAB01": "global", "LAB03": "global", "LAB04": "global",
    # 움직임 센서 8
    "HOME01": "motion", "HOME05": "motion", "HOME10": "motion", "HOME16": "motion",
    "HOME17": "motion", "OFFICE06": "motion", "FARM03": "motion", "FACT02": "motion",
    # 재실 센서 3 — 앉아만 있어 움직임이 안 잡히는 곳
    "HOME19": "presence", "OFFICE01": "presence", "LAB05": "presence",
    # 폰 4 — 1인 거주라 폰 하나로 집 재실이 결정된다
    "HOME02": "phone", "HOME07": "phone", "HOME11": "phone", "HOME20": "phone",
    # 판단 불가 10
    "HOME14": "none", "OFFICE04": "none", "LAB02": "none",
    "FARM01": "none", "FARM02": "none", "FARM04": "none",
    "FACT01": "none", "FACT03": "none", "FACT04": "none", "FACT05": "none",
}
DROP = {"motion": ("PresenceSensor",), "presence": ("MotionSensor",),
        "phone": ("MotionSensor", "PresenceSensor"),
        "none": ("MotionSensor", "PresenceSensor"), "global": ()}


def _prune_occupancy(S):
    """재실 판단 주체가 아닌 센서를 잘라내고 occupancy 필드를 박는다."""
    cut = 0
    for sid, sp in S.items():
        mode = OCCUPANCY[sid]
        sp["occupancy"] = mode
        for did in [k for k in sp["devices"]]:
            v = sp["devices"][did]
            if any(c in DROP[mode] for c in v["category"]):
                v["category"] = [c for c in v["category"] if c not in DROP[mode]]
                v["tags"] = [t for t in v["tags"] if t not in DROP[mode]]
                if not v["category"]:
                    del sp["devices"][did]
                    cut += 1
    return cut


def _check_occupancy(S):
    """공간마다 재실 답이 정확히 하나인지 확인."""
    bad = []
    for sid, sp in S.items():
        mode, cats = sp["occupancy"], set()
        gv = {}
        for v in sp["devices"].values():
            cats.update(v["category"])
            gv.update(v.get("variables", {}))
        m, pr = "MotionSensor" in cats, "PresenceSensor" in cats
        ph, hu = "PersonTracker" in cats, "Human" in gv
        if mode == "global" and not hu:
            bad.append(f"{sid}: global 인데 Human 변수 없음")
        if mode == "motion" and not (m and not pr and not hu):
            bad.append(f"{sid}: motion 인데 motion={m} presence={pr} Human={hu}")
        if mode == "presence" and not (pr and not m and not hu):
            bad.append(f"{sid}: presence 인데 motion={m} presence={pr} Human={hu}")
        if mode == "phone" and not (ph and not m and not pr and not hu):
            bad.append(f"{sid}: phone 인데 phone={ph} motion={m} presence={pr} Human={hu}")
        if mode == "none" and (m or pr or hu or ph):
            bad.append(f"{sid}: none 인데 motion={m} presence={pr} Human={hu} phone={ph}")
    return bad


BOOL = "BOOL"
HUMAN = {"Human": {"type": BOOL, "desc": "Fused occupancy: motion and presence sensors "
                                         "combined by a separate scenario"}}
GLOBALS = {
    # 가정집 10
    "HOME03": {**HUMAN, "HomeMode": {"type": "ENUM", "enums": ["home", "away", "sleep", "guest"],
                                     "desc": "Current household mode"}},
    "HOME04": {**HUMAN, "Night": {"type": BOOL, "desc": "Night-time flag"},
               "HomeMode": {"type": "ENUM", "enums": ["home", "away", "sleep", "guest"],
                            "desc": "Current household mode"}},
    "HOME06": {**HUMAN, "Night": {"type": BOOL, "desc": "Night-time flag"},
               "Armed": {"type": BOOL, "desc": "Security system armed"}},
    "HOME08": {**HUMAN, "PetAlone": {"type": BOOL, "desc": "Pet is home without people"}},
    "HOME09": {**HUMAN, "BabyAsleep": {"type": BOOL, "desc": "Baby is asleep"},
               "Night": {"type": BOOL, "desc": "Night-time flag"}},
    "HOME12": {**HUMAN, "SharedAreaBusy": {"type": BOOL, "desc": "Shared area is in use"}},
    "HOME13": {**HUMAN, "Night": {"type": BOOL, "desc": "Night-time flag"}},
    "HOME15": {**HUMAN, "HomeMode": {"type": "ENUM", "enums": ["home", "away", "sleep", "guest"],
                                     "desc": "Current household mode"},
               "Night": {"type": BOOL, "desc": "Night-time flag"},
               "Armed": {"type": BOOL, "desc": "Security system armed"}},
    "HOME16": {"Vacation": {"type": BOOL, "desc": "House is empty for a long stay away"},
               "Armed": {"type": BOOL, "desc": "Security system armed"}},
    "HOME18": {**HUMAN, "CarHome": {"type": BOOL, "desc": "Car is parked in the garage"}},
    # 오피스 3
    "OFFICE02": {**HUMAN, "WorkHours": {"type": BOOL, "desc": "Inside working hours"}},
    "OFFICE03": {**HUMAN, "MeetingInProgress": {"type": BOOL, "desc": "A meeting is running"}},
    "OFFICE05": {**HUMAN, "WorkHours": {"type": BOOL, "desc": "Inside working hours"},
                 "FireDrill": {"type": BOOL, "desc": "Fire drill in progress"}},
    # 연구실 3
    "LAB01": {**HUMAN, "Night": {"type": BOOL, "desc": "Night-time flag"}},
    "LAB03": {**HUMAN, "IncubationRunning": {"type": BOOL, "desc": "An incubation run is active"}},
    "LAB04": {**HUMAN, "RobotEnabled": {"type": BOOL, "desc": "Robot cell is enabled"}},
    # 농장 2
    "FARM01": {"IrrigationActive": {"type": BOOL, "desc": "An irrigation cycle is running"},
               "GrowthStage": {"type": "ENUM",
                               "enums": ["seedling", "vegetative", "flowering", "harvest"],
                               "desc": "Current crop growth stage"}},
    "FARM04": {"IrrigationActive": {"type": BOOL, "desc": "A nutrient cycle is running"},
               "GrowthStage": {"type": "ENUM",
                               "enums": ["seedling", "vegetative", "flowering", "harvest"],
                               "desc": "Current crop growth stage"}},
    # 공장 2
    "FACT01": {"ShiftActive": {"type": BOOL, "desc": "A production shift is running"},
               "LineRunning": {"type": BOOL, "desc": "The line is running"},
               "MaintenanceMode": {"type": BOOL, "desc": "Maintenance mode is on"}},
    "FACT05": {"ShiftActive": {"type": BOOL, "desc": "A production shift is running"},
               "MaintenanceMode": {"type": BOOL, "desc": "Maintenance mode is on"}},
}

# 카테고리를 얹으면 따라오는 affordance/fixture 태그 (tag_lexicon 규약)
AFFORD = {"LightSwitch": "Switch", "Door": "ContactSensor", "Window": "ContactSensor"}


def d(n, cats, place, extra="", nick=None, brand=None):
    """기기 n대. cats='Light|Switch', extra='LightSwitch,Main', nick='거실 등 {i}'"""
    return (n, cats, place, extra, nick, brand)


def build(sid, kind, name, size, notes, rows, missing=()):
    devices, seen = {}, {}
    for (n, cats, place, extra, nick, brand) in rows:
        cl = cats.split("|")
        ex = [t for t in extra.split(",") if t]
        for i in range(1, n + 1):
            key = f"{sid}_{place}_{cl[0]}"
            seen[key] = seen.get(key, 0) + 1
            did = f"{key}_{seen[key]}"
            tags = ([place] if place else []) + ex + ([brand] if brand else []) + cl
            devices[did] = {
                "nickname": (nick.format(i=i) if nick else None),
                "category": cl,
                "tags": list(dict.fromkeys(t for t in tags if t)),
            }
            if devices[did]["nickname"] is None:
                del devices[did]["nickname"]
    extra = ([("WeatherProvider", "날씨")] if sid in WEATHER else []) + \
            ([("PersonTracker", "내 폰")] if sid in PERSON_TRACKER else []) + \
            ([("CalendarProvider", "일정")] if sid in CALENDAR else [])
    for cat, nk in SYSTEM + extra:
        e = {"nickname": nk, "category": [cat], "tags": ["System", cat]}
        if cat == "GlobalVariable":
            e["variables"] = GLOBALS.get(sid, {})
        devices[f"{sid}_System_{cat}"] = e
    return {"kind": kind, "name_ko": name, "size": size, "notes": notes,
            "missing_on_purpose": list(missing), "devices": devices}


S = {}   # space_id → space

# ══ 가정집 20 ═══════════════════════════════════════════════════════════════
S["HOME01"] = build("HOME01", "home", "원룸 (1인)", "S",
    "가장 작은 집. 방 하나뿐이라 장소 한정어가 거의 쓸모없음 — 기기 종류만으로 지목.", [
    d(2, "Light|Switch", "Room", "LightSwitch"),
    d(1, "AirConditioner|Switch", "Room"),
    d(1, "Speaker", "Room"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "Fan|Switch", "Room"),
    d(1, "MotionSensor", "Room"),
    d(2, "Plug|Switch|PowerMeter", "Room"),
    d(1, "TemperatureSensor", "Room"),
    d(1, "HumiditySensor", "Room"),
    d(1, "Button", "Room"),
    d(1, "Fan", "Room"),
    d(1, "DoorLock", "Entrance"),
], missing=["WindowCovering", "RobotVacuumCleaner", "Camera"])

S["HOME02"] = build("HOME02", "home", "신혼부부 아파트", "S", "기본 구성. 중복 기기 없음.", [
    d(2, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Button", "Bedroom"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "Speaker", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(1, "TemperatureSensor", "LivingRoom"),
    d(1, "AirPurifier|Switch", "LivingRoom"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(1, "Button", "LivingRoom"),
    d(1, "Thermostat", "LivingRoom"),
    d(1, "LaundryWasher", "Utility"),
], missing=["WindowCovering", "Camera", "Dishwasher"])

S["HOME03"] = build("HOME03", "home", "3인 가족 아파트", "M",
    "표준 아파트. 조명이 방마다 있어 장소 한정어가 반드시 필요.", [
    d(3, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(2, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "Light|Switch", "Bathroom", "LightSwitch"),
    d(1, "Fan", "Bathroom"),
    d(1, "Light|Switch", "Hallway", "LightSwitch"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "AirConditioner|Switch", "Bedroom"),
    d(1, "Button", "Bedroom"),
    d(1, "Speaker", "LivingRoom"),
    d(1, "Speaker", "Kitchen"),
    d(1, "Television|Switch", "LivingRoom"),
    d(2, "WindowCovering", "LivingRoom", "Blind"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "ContactSensor", "Balcony", "Window"),
    d(2, "Fan|Switch", "LivingRoom"),
    d(1, "DoorLock", "Entrance"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "HumiditySensor", "LivingRoom"),
    d(1, "AirQualitySensor", "LivingRoom"),
    d(1, "AirPurifier|Switch", "LivingRoom"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(1, "MultiButton", "LivingRoom"),
    d(1, "Dishwasher", "Kitchen"),
    d(1, "SmokeDetector", "Kitchen"),
], missing=["Camera", "GarageDoor", "Curtain"])

S["HOME04"] = build("HOME04", "home", "4인 가족 아파트 (중복 기기)", "M",
    "같은 종류를 여러 대 둔 집 — 에어컨 3, 공기청정기 2, 식기세척기 2. "
    "장소 없이 부르면 되묻기 대상.", [
    d(3, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(2, "Light|Switch", "Bedroom", "LightSwitch"),
    d(2, "Light|Switch", "Study", "LightSwitch"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "AirConditioner|Switch", "Bedroom"),
    d(1, "AirConditioner|Switch", "Study"),
    d(1, "Button", "Study"),
    d(1, "AirPurifier|Switch", "LivingRoom", nick="거실 공기청정기 큰거"),
    d(1, "AirPurifier|Switch", "Bedroom", nick="침실 공기청정기 작은거"),
    d(1, "Dishwasher", "Kitchen"),
    d(1, "Dishwasher", "Utility"),
    d(1, "ClothingCare", "Utility", nick="스타일러"),
    d(2, "Speaker", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(1, "Television|Switch", "Bedroom"),
    d(2, "WindowCovering", "LivingRoom", "Blind"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "TemperatureSensor", "Bedroom"),
    d(1, "PresenceSensor", "LivingRoom"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(1, "MultiButton", "LivingRoom"),
    d(1, "Fan", "LivingRoom"),
], missing=["Camera", "Siren"])

S["HOME05"] = build("HOME05", "home", "복층 빌라", "M",
    "층 태그(Floor1/Floor2)가 한정어로 쓰이는 집.", [
    d(3, "Light|Switch", "LivingRoom", "LightSwitch,Floor1,Main"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch,Floor1"),
    d(2, "Light|Switch", "Bedroom", "LightSwitch,Floor2"),
    d(1, "Light|Switch", "Study", "LightSwitch,Floor2"),
    d(1, "Light|Switch", "Stairs", "LightSwitch"),
    d(1, "AirConditioner|Switch", "LivingRoom", "Floor1"),
    d(1, "AirConditioner|Switch", "Bedroom", "Floor2"),
    d(1, "Speaker", "LivingRoom", "Floor1"),
    d(1, "Speaker", "Bedroom", "Floor2"),
    d(1, "MotionSensor", "Stairs"),
    d(2, "WindowCovering", "LivingRoom", "Blind,Floor1"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(2, "TemperatureSensor", "LivingRoom", "Floor1"),
    d(1, "TemperatureSensor", "Bedroom", "Floor2"),
    d(1, "Button", "Bedroom"),
    d(1, "Thermostat", "LivingRoom", "Floor1"),
    d(1, "WaterHeater", "Utility"),
    d(1, "RobotVacuumCleaner", "LivingRoom", "Floor1"),
    d(1, "Button", "LivingRoom"),
    d(1, "Fan", "LivingRoom"),
    d(1, "Thermostat", "LivingRoom"),
    d(1, "SmokeDetector", "Kitchen", "Floor1"),
], missing=["Camera", "GarageDoor"])

S["HOME06"] = build("HOME06", "home", "단독주택 (마당·차고)", "L",
    "큰 집. 실외 기기와 차고문이 있음. 층·구역 태그 병용.", [
    d(4, "Light|Switch", "LivingRoom", "LightSwitch,Floor1,Main"),
    d(2, "Light|Switch", "Kitchen", "LightSwitch,Floor1"),
    d(2, "Light|Switch", "Bedroom", "LightSwitch,Floor2"),
    d(1, "Light|Switch", "Study", "LightSwitch,Floor2"),
    d(2, "Light|Switch", "Bathroom", "LightSwitch"),
    d(1, "Fan", "Bathroom"),
    d(1, "Light|Switch", "Hallway", "LightSwitch"),
    d(2, "Light|Switch", "Garden", "LightSwitch,Outdoor"),
    d(1, "Light|Switch", "Garage", "LightSwitch"),
    d(1, "GarageDoor", "Garage"),
    d(1, "EvCharger", "Garage"),
    d(2, "AirConditioner|Switch", "LivingRoom", "Floor1"),
    d(1, "AirConditioner|Switch", "Bedroom", "Floor2"),
    d(1, "Thermostat", "LivingRoom"),
    d(1, "WaterHeater", "Utility"),
    d(2, "Speaker", "LivingRoom"),
    d(1, "Speaker", "Kitchen"),
    d(1, "Television|Switch", "LivingRoom"),
    d(3, "WindowCovering", "LivingRoom", "Blind"),
    d(2, "WindowCovering", "Bedroom", "Curtain"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "ContactSensor", "BackDoor", "Door"),
    d(2, "ContactSensor", "LivingRoom", "Window"),
    d(1, "DoorLock", "Entrance"),
    d(1, "Doorbell", "Entrance"),
    d(2, "Camera", "Garden", "Outdoor"),
    d(1, "Camera", "Garage"),
    d(1, "Siren|Switch", "Entrance", "Main"),
    d(3, "TemperatureSensor", "LivingRoom"),
    d(1, "TemperatureSensor", "Garden", "Outdoor"),
    d(1, "HumiditySensor", "LivingRoom"),
    d(1, "RainSensor", "Garden", "Outdoor"),
    d(1, "MotionSensor", "Garden", "Outdoor"),
    d(1, "PresenceSensor", "LivingRoom"),
    d(1, "Sprinkler", "Garden", "Outdoor"),
    d(1, "Valve", "Garden", "Outdoor"),
    d(1, "Mower", "Garden"),
    d(1, "Button", "Garden"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(1, "MultiButton", "LivingRoom"),
    d(1, "Dishwasher", "Kitchen"),
    d(1, "LaundryWasher", "Utility"),
    d(1, "LaundryDryer", "Utility"),
    d(1, "SmokeDetector", "Kitchen"),
    d(1, "GasSensor", "Kitchen"),
    d(1, "LeakSensor", "Utility"),
    d(1, "WeatherProvider", "Outdoor"),
    d(1, "EmailProvider", "System"),
])

S["HOME07"] = build("HOME07", "home", "전원주택 (태양광·우물)", "L",
    "실외 설비가 많은 집 — 펌프, 스프링클러, 물탱크, 전력 계측.", [
    d(3, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(2, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(3, "Light|Switch", "Garden", "LightSwitch,Outdoor"),
    d(1, "Light|Switch", "Barn", "LightSwitch,Outdoor"),
    d(1, "Thermostat", "LivingRoom"),
    d(1, "WaterHeater", "Utility"),
    d(1, "ElectricBlanket", "Bedroom"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(2, "Speaker", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(2, "Camera", "Garden", "Outdoor"),
    d(1, "Siren|Switch", "Entrance", "Main"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "TemperatureSensor", "Garden", "Outdoor"),
    d(1, "HumiditySensor", "LivingRoom"),
    d(1, "RainSensor", "Garden", "Outdoor"),
    d(1, "WindSensor", "Garden", "Outdoor"),
    d(1, "UvSensor", "Garden", "Outdoor"),
    d(1, "Pump", "Utility", nick="지하수 펌프"),
    d(1, "WaterLevelSensor", "Utility", nick="물탱크 수위"),
    d(2, "Valve", "Garden", "Outdoor"),
    d(2, "Sprinkler", "Garden", "Outdoor"),
    d(1, "Mower", "Garden"),
    d(1, "Button", "Garden"),
    d(1, "EnergyMeter", "Utility", nick="태양광 계측기"),
    d(1, "Battery", "Utility", nick="가정용 ESS"),
    d(1, "EvCharger", "Garage"),
    d(1, "GarageDoor", "Garage"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(1, "Button", "LivingRoom"),
    d(1, "LaundryWasher", "Utility"),
    d(1, "SmokeDetector", "Kitchen"),
    d(1, "LeakSensor", "Utility"),
    d(1, "WeatherProvider", "Outdoor"),
])

S["HOME08"] = build("HOME08", "home", "반려동물 있는 집", "M",
    "급식기·펫캠. 자리 비운 사이의 자동화가 많이 나올 공간.", [
    d(2, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "AirPurifier|Switch", "LivingRoom"),
    d(1, "PetFeeder", "Kitchen", nick="자동 급식기"),
    d(2, "Camera", "LivingRoom", nick="펫캠 {i}"),
    d(1, "Speaker", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(1, "MotionSensor", "LivingRoom"),
    d(1, "PresenceSensor", "LivingRoom"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "HumiditySensor", "LivingRoom"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(2, "Plug|Switch|PowerMeter", "LivingRoom"),
    d(1, "WindowCovering", "LivingRoom", "Blind"),
    d(1, "Button", "LivingRoom"),
    d(1, "Fan", "LivingRoom"),
], missing=["Siren", "GarageDoor"])

S["HOME09"] = build("HOME09", "home", "아기 있는 집", "M",
    "아기방 태그와 습도·공기질 중심. 소리 센서로 우는 소리 감지.", [
    d(2, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "BabyRoom", "LightSwitch", nick="아기방 무드등"),
    d(1, "ColorControl|Light|Switch", "BabyRoom", "LightSwitch", nick="아기방 컬러 무드등"),
    d(1, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "AirConditioner|Switch", "BabyRoom"),
    d(1, "Humidifier|Switch", "BabyRoom"),
    d(1, "AirPurifier|Switch", "BabyRoom"),
    d(1, "AirPurifier|Switch", "LivingRoom"),
    d(1, "AirQualitySensor", "BabyRoom"),
    d(1, "SoundSensor", "BabyRoom", nick="아기 울음 감지"),
    d(1, "Camera", "BabyRoom", nick="베이비 모니터"),
    d(2, "TemperatureSensor", "BabyRoom"),
    d(1, "HumiditySensor", "BabyRoom"),
    d(1, "TemperatureSensor", "LivingRoom"),
    d(2, "Speaker", "LivingRoom"),
    d(1, "Button", "LivingRoom"),
    d(1, "Speaker", "BabyRoom"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(1, "WindowCovering", "BabyRoom", "Curtain"),
    d(1, "Button", "BabyRoom"),
    d(1, "Fan", "BabyRoom"),
    d(1, "MotionSensor", "Hallway"),
], missing=["RobotVacuumCleaner", "Siren"])

S["HOME10"] = build("HOME10", "home", "노부모 집 (안전 중심)", "S",
    "재실·낙상·응급 위주. 화면 없이 스피커로만 알림.", [
    d(2, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Bathroom", "LightSwitch"),
    d(1, "Light|Switch", "Hallway", "LightSwitch"),
    d(1, "Speaker", "LivingRoom", "Main"),
    d(1, "Speaker", "Bedroom"),
    d(1, "PresenceSensor", "LivingRoom"),
    d(1, "PresenceSensor", "Bathroom"),
    d(1, "MotionSensor", "Hallway"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(1, "Doorbell", "Entrance"),
    d(1, "Siren|Switch", "LivingRoom", "Main"),
    d(1, "Button", "Bedroom", nick="응급 호출 버튼"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "Fan", "LivingRoom"),
    d(1, "GasSensor", "Kitchen"),
    d(1, "SmokeDetector", "Kitchen"),
    d(1, "MessageSender", "System"),
], missing=["Camera", "Television", "AirConditioner"])

S["HOME11"] = build("HOME11", "home", "오피스텔", "S", "작고 별명이 거의 없음.", [
    d(2, "Light|Switch", "Room", "LightSwitch,Main"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "Light|Switch", "Bathroom", "LightSwitch"),
    d(1, "AirConditioner|Switch", "Room"),
    d(1, "Speaker", "Room"),
    d(1, "Television|Switch", "Room"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(1, "WindowCovering", "Room", "Blind"),
    d(2, "Plug|Switch|PowerMeter", "Room"),
    d(1, "TemperatureSensor", "Room"),
    d(1, "Button", "Room"),
    d(1, "Thermostat", "Room"),
    d(1, "MotionSensor", "Entrance"),
], missing=["AirPurifier", "RobotVacuumCleaner", "Camera"])

S["HOME12"] = build("HOME12", "home", "셰어하우스 (방 3개)", "M",
    "방마다 사람이 다름 — 방 태그가 소유자 구분처럼 쓰임. 공용 구역 별도.", [
    d(1, "Light|Switch", "RoomA", "LightSwitch", nick="A방 등"),
    d(1, "Light|Switch", "RoomB", "LightSwitch", nick="B방 등"),
    d(1, "Light|Switch", "RoomC", "LightSwitch", nick="C방 등"),
    d(3, "Light|Switch", "LivingRoom", "LightSwitch,SharedLight,Main"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch,SharedLight"),
    d(2, "Light|Switch", "Bathroom", "LightSwitch,SharedLight"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "AirConditioner|Switch", "RoomA"),
    d(1, "AirConditioner|Switch", "RoomB"),
    d(1, "AirConditioner|Switch", "RoomC"),
    d(1, "ContactSensor", "RoomA", "Door"),
    d(1, "Button", "RoomA"),
    d(1, "ContactSensor", "RoomB", "Door"),
    d(1, "ContactSensor", "RoomC", "Door"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(1, "Speaker", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(1, "LaundryWasher", "Utility"),
    d(1, "LaundryDryer", "Utility"),
    d(1, "Dishwasher", "Kitchen"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(3, "TemperatureSensor", "LivingRoom"),
    d(1, "PresenceSensor", "LivingRoom"),
    d(1, "Button", "LivingRoom"),
    d(1, "Fan", "LivingRoom"),
    d(1, "MotionSensor", "Hallway"),
    d(1, "SmokeDetector", "Kitchen"),
    d(1, "OccupancyCounter", "Entrance"),
])

S["HOME13"] = build("HOME13", "home", "고층 아파트 (전동 커튼)", "M",
    "커튼·블라인드가 종류별로 섞임 — WindowCoveringType 구분이 필요한 공간.", [
    d(3, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(2, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "Light|Switch", "Study", "LightSwitch"),
    d(3, "WindowCovering", "LivingRoom", "Curtain", nick="거실 커튼 {i}"),
    d(2, "WindowCovering", "Bedroom", "Blind"),
    d(1, "WindowCovering", "Study", "Blind"),
    d(1, "ClothingCare", "Utility", nick="에어드레서"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "AirConditioner|Switch", "Bedroom"),
    d(1, "Button", "Bedroom"),
    d(1, "Fan", "Bedroom"),
    d(1, "AirPurifier|Switch", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(2, "Speaker", "LivingRoom"),
    d(1, "LightSensor", "LivingRoom"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "HumiditySensor", "LivingRoom"),
    d(1, "AirQualitySensor", "LivingRoom"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(2, "ContactSensor", "LivingRoom", "Window"),
    d(1, "DoorLock", "Entrance"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(1, "MultiButton", "LivingRoom"),
    d(1, "Dishwasher", "Kitchen"),
], missing=["Camera", "Siren", "GarageDoor"])

S["HOME14"] = build("HOME14", "home", "구옥 (보일러·온수기)", "S",
    "난방 중심. 최신 기기가 적어 '없는 기기' 요청이 잘 나옴.", [
    d(2, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "Thermostat", "LivingRoom", nick="거실 보일러"),
    d(1, "WaterHeater", "Bathroom", nick="온수기"),
    d(1, "ElectricBlanket", "Bedroom"),
    d(1, "Speaker", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "TemperatureSensor", "Bedroom"),
    d(1, "HumiditySensor", "LivingRoom"),
    d(1, "GasSensor", "Kitchen"),
    d(1, "SmokeDetector", "Kitchen"),
    d(1, "LeakSensor", "Bathroom"),
    d(1, "Fan", "Bathroom"),
], missing=["AirConditioner", "DoorLock", "Camera", "RobotVacuumCleaner",
            "WindowCovering", "AirPurifier"])

S["HOME15"] = build("HOME15", "home", "스마트홈 마니아 (브랜드 혼재)", "L",
    "별명이 가장 많은 공간. 브랜드 태그로 무리 지어 부르는 명령을 위한 곳 "
    "('투야 장치들 다 꺼줘').", [
    d(4, "Light|Switch", "LivingRoom", "LightSwitch,Main", "Hue 거실 {i}", "PhilipsHue"),
    d(2, "Light|Switch", "Bedroom", "LightSwitch", "Hue 침실 {i}", "PhilipsHue"),
    d(2, "Light|Switch", "Study", "LightSwitch", "스카이라이트 {i}", "Tuya"),
    d(2, "ColorControl|Light|Switch", "LivingRoom", "LightSwitch", "컬러 스트립 {i}", "Tuya"),
    d(6, "Switch", "Hallway", "LightSwitch,NoneNecessary", "전등 스위치 6구 {i}", "Tuya"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch", None, "Hejhome"),
    d(2, "MultiButton", "LivingRoom", "", "Hue dimmer switch {i}", "PhilipsHue"),
    d(1, "RotaryControl|MultiButton", "LivingRoom", "", "Hue tap dial", "PhilipsHue"),
    d(2, "LevelControl|Switch", "LivingRoom", "", "벽 디머 {i}", "Tuya"),
    d(1, "Button|Battery", "Bedroom", "", "투야 푸시 버튼", "Tuya"),
    d(1, "AirConditioner|Switch|TemperatureSensor", "LivingRoom", "",
      "헤이홈 IR 에어컨", "Hejhome"),
    d(1, "AirPurifier|Switch", "LivingRoom", "", "삼성 공기청정기 큰거", "Smartthings"),
    d(1, "AirPurifier|Switch", "Bedroom", "", "삼성 공기청정기 작은거", "Smartthings"),
    d(1, "Humidifier|Switch", "Bedroom", "", "미로 가습기", "Smartthings"),
    d(1, "RobotVacuumCleaner", "LivingRoom", "", "삼성 로봇청소기", "Smartthings"),
    d(3, "Plug|Switch|PowerMeter|EnergyMeter", "LivingRoom", "NoneNecessary",
      "스마트 Wi-Fi 플러그 {i}", "Matter"),
    d(2, "Speaker", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(1, "Camera", "LivingRoom", "", None, "Tuya"),
    d(2, "ContactSensor", "LivingRoom", "Window", None, "Matter"),
    d(1, "ContactSensor", "Entrance", "Door", None, "Matter"),
    d(1, "DoorLock", "Entrance"),
    d(1, "GarageDoor", "Entrance"),
    d(3, "TemperatureSensor", "LivingRoom", "", None, "Matter"),
    d(1, "HumiditySensor", "LivingRoom", "", None, "Matter"),
    d(2, "LightSensor", "LivingRoom", "", None, "Matter"),
    d(1, "AirQualitySensor", "LivingRoom", "", None, "Matter"),
    d(2, "PresenceSensor", "LivingRoom", "", None, "Matter"),
    d(1, "SmokeDetector|Battery", "Kitchen", "", "투야 화재 감지 센서", "Tuya"),
    d(3, "WindowCovering", "LivingRoom", "Blind"),
    d(1, "WeatherProvider", "Outdoor"),
    d(1, "EmailProvider", "System"),
    d(1, "ChatProvider", "System"),
    d(1, "CloudServiceProvider", "System"),
])

S["HOME16"] = build("HOME16", "home", "별장 (비어 있는 기간 있음)", "S",
    "사람이 없는 기간이 길어 동파·누수·침입 감시 자동화가 나올 공간.", [
    d(2, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Garden", "LightSwitch,Outdoor"),
    d(1, "Thermostat", "LivingRoom"),
    d(1, "WaterHeater", "Utility"),
    d(1, "Valve", "Utility", nick="주 급수 밸브"),
    d(1, "LeakSensor", "Utility"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(2, "ContactSensor", "LivingRoom", "Window"),
    d(1, "DoorLock", "Entrance"),
    d(2, "Camera", "Garden", "Outdoor"),
    d(1, "Siren|Switch", "Entrance", "Main"),
    d(1, "MotionSensor", "LivingRoom"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "TemperatureSensor", "Garden", "Outdoor"),
    d(1, "GarageDoor", "Garden"),
    d(1, "HumiditySensor", "LivingRoom"),
    d(1, "Button", "LivingRoom"),
    d(1, "EnergyMeter", "Utility"),
    d(1, "MessageSender", "System"),
], missing=["Speaker", "Television", "AirConditioner", "RobotVacuumCleaner"])

S["HOME17"] = build("HOME17", "home", "자취 원룸 (최소 구성)", "S",
    "기기 10대짜리 바닥선 공간. 요청 대비 기기가 자주 없음 → 거절 예시의 주 무대.", [
    d(1, "Light|Switch", "Room", "LightSwitch,Main"),
    d(1, "Light|Switch", "Bathroom", "LightSwitch"),
    d(1, "Fan", "Bathroom"),
    d(1, "AirConditioner|Switch", "Room"),
    d(1, "Speaker", "Room"),
    d(2, "Plug|Switch", "Room"),
    d(2, "Fan|Switch", "Room"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "TemperatureSensor", "Room"),
    d(1, "HumiditySensor", "Room"),
    d(1, "MotionSensor", "Room"),
], missing=["DoorLock", "Camera", "WindowCovering", "AirPurifier", "Television",
            "RobotVacuumCleaner", "Dishwasher", "Siren"])

S["HOME18"] = build("HOME18", "home", "타운하우스 (차고·EV)", "M", "차고와 전기차 중심.", [
    d(3, "Light|Switch", "LivingRoom", "LightSwitch,Floor1,Main"),
    d(2, "Light|Switch", "Bedroom", "LightSwitch,Floor2"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch,Floor1"),
    d(1, "Light|Switch", "Garage", "LightSwitch"),
    d(1, "GarageDoor", "Garage"),
    d(1, "EvCharger", "Garage", nick="EV 충전기"),
    d(2, "Charger", "Garage", "", "공구 충전기 {i}"),
    d(1, "EnergyMeter", "Garage"),
    d(1, "Camera", "Garage"),
    d(1, "MotionSensor", "Garage"),
    d(1, "Button", "Garage"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "AirConditioner|Switch", "Bedroom"),
    d(1, "Thermostat", "LivingRoom"),
    d(2, "Speaker", "LivingRoom"),
    d(1, "Television|Switch", "LivingRoom"),
    d(2, "WindowCovering", "LivingRoom", "Blind"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(1, "Doorbell", "Entrance"),
    d(2, "TemperatureSensor", "LivingRoom"),
    d(1, "RobotVacuumCleaner", "LivingRoom"),
    d(1, "MultiButton", "LivingRoom"),
    d(1, "LaundryWasher", "Utility"),
    d(1, "SmokeDetector", "Kitchen"),
])

S["HOME19"] = build("HOME19", "home", "재택근무 집 (홈오피스)", "M",
    "집 안에 사무 기기가 있음 — 프린터·디스플레이가 집 맥락에서 불림.", [
    d(2, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(2, "Light|Switch", "Study", "LightSwitch", nick="서재 조명 {i}"),
    d(1, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "AirConditioner|Switch", "Study"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "AirPurifier|Switch", "Study"),
    d(1, "Printer", "Study"),
    d(1, "Display", "Study", nick="서재 모니터"),
    d(1, "Speaker", "Study"),
    d(1, "Speaker", "LivingRoom"),
    d(1, "Button", "LivingRoom"),
    d(1, "Thermostat", "LivingRoom"),
    d(1, "Camera", "Study", nick="화상회의 캠"),
    d(1, "SoundSensor", "Study"),
    d(1, "WindowCovering", "Study", "Blind"),
    d(2, "TemperatureSensor", "Study"),
    d(1, "HumiditySensor", "Study"),
    d(1, "LightSensor", "Study"),
    d(1, "PresenceSensor", "Study"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "DoorLock", "Entrance"),
    d(3, "Plug|Switch|PowerMeter", "Study"),
    d(1, "Button", "Study"),
    d(1, "Fan", "Study"),
    d(1, "CoffeeMaker", "Kitchen"),
    d(1, "EmailProvider", "System"),
])

S["HOME20"] = build("HOME20", "home", "다세대 저층 (주방 가전 많음)", "S",
    "주방 가전이 몰려 있어 같은 방 안에서 기기 종류로만 갈라야 함.", [
    d(2, "Light|Switch", "LivingRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "Kitchen", "LightSwitch"),
    d(1, "Light|Switch", "Bedroom", "LightSwitch"),
    d(1, "Oven", "Kitchen"),
    d(1, "Microwave", "Kitchen"),
    d(1, "RiceCooker", "Kitchen"),
    d(1, "Dishwasher", "Kitchen"),
    d(1, "Refrigerator", "Kitchen"),
    d(1, "RangeHood", "Kitchen"),
    d(1, "CoffeeMaker", "Kitchen"),
    d(1, "WaterPurifier", "Kitchen"),
    d(1, "AirConditioner|Switch", "LivingRoom"),
    d(1, "Speaker", "Kitchen"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "TemperatureSensor", "LivingRoom"),
    d(1, "Thermostat", "LivingRoom"),
    d(1, "SmokeDetector", "Kitchen"),
    d(1, "GasSensor", "Kitchen"),
    d(1, "Button", "Kitchen"),
    d(1, "Fan", "Kitchen"),
], missing=["Camera", "DoorLock", "WindowCovering"])

# ══ 오피스 6 ════════════════════════════════════════════════════════════════
S["OFFICE01"] = build("OFFICE01", "office", "스타트업 사무실 (단층)", "S",
    "구역(Section) 태그로 자리를 가름.", [
    d(4, "Light|Switch", "OpenSpace", "LightSwitch,Main"),
    d(1, "Light|Switch", "MeetingRoom", "LightSwitch"),
    d(1, "Light|Switch", "Pantry", "LightSwitch"),
    d(2, "AirConditioner|Switch", "OpenSpace"),
    d(1, "AirConditioner|Switch", "MeetingRoom"),
    d(1, "AirPurifier|Switch", "OpenSpace"),
    d(1, "Speaker", "OpenSpace", "Main"),
    d(1, "Printer", "OpenSpace"),
    d(1, "Display", "MeetingRoom"),
    d(1, "DoorLock", "Entrance"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(2, "PresenceSensor", "OpenSpace"),
    d(1, "PresenceSensor", "MeetingRoom"),
    d(1, "Button", "MeetingRoom"),
    d(2, "TemperatureSensor", "OpenSpace"),
    d(1, "AirQualitySensor", "OpenSpace"),
    d(1, "CoffeeMaker", "Pantry"),
    d(1, "Fan", "Pantry"),
    d(2, "WindowCovering", "OpenSpace", "Blind"),
    d(1, "Thermostat", "OpenSpace"),
], missing=["Camera", "Projector", "Siren"])

S["OFFICE02"] = build("OFFICE02", "office", "공유오피스 한 층", "M",
    "구역 6개 + 공용 회의실 3개. 구역 번호 한정어가 핵심.", [
    d(6, "Light|Switch", "OpenSpace", "LightSwitch,Main", "구역 {i} 조명"),
    d(3, "Light|Switch", "MeetingRoom", "LightSwitch", "회의실 {i} 조명"),
    d(1, "Light|Switch", "Pantry", "LightSwitch"),
    d(1, "Light|Switch", "Hallway", "LightSwitch"),
    d(3, "AirConditioner|Switch", "OpenSpace"),
    d(3, "AirConditioner|Switch", "MeetingRoom"),
    d(2, "AirPurifier|Switch", "OpenSpace"),
    d(6, "PresenceSensor", "OpenSpace", "", "구역 {i} 재실 센서"),
    d(3, "PresenceSensor", "MeetingRoom"),
    d(3, "Display", "MeetingRoom", "", "회의실 {i} 디스플레이"),
    d(1, "Projector", "MeetingRoom"),
    d(2, "Printer", "OpenSpace"),
    d(2, "Speaker", "OpenSpace", "Main"),
    d(1, "OccupancyCounter", "Entrance"),
    d(1, "RfidReader", "Entrance"),
    d(2, "DoorLock", "Entrance"),
    d(4, "TemperatureSensor", "OpenSpace"),
    d(2, "AirQualitySensor", "OpenSpace"),
    d(1, "CarbonDioxideSensor", "MeetingRoom"),
    d(2, "MultiButton", "MeetingRoom"),
    d(2, "Ventilator", "OpenSpace"),
    d(1, "CoffeeMaker", "Pantry"),
    d(4, "WindowCovering", "OpenSpace", "Blind"),
    d(1, "SmokeDetector", "Pantry"),
])

S["OFFICE03"] = build("OFFICE03", "office", "회의실 중심 오피스", "M",
    "회의실 4개 — 예약·재실·환기 자동화. 회의실마다 같은 기기 한 벌씩(중복).", [
    d(4, "Light|Switch", "MeetingRoom", "LightSwitch", "회의실 {i} 조명"),
    d(4, "Display", "MeetingRoom", "", "회의실 {i} 화면"),
    d(4, "PresenceSensor", "MeetingRoom", "", "회의실 {i} 재실"),
    d(4, "AirConditioner|Switch", "MeetingRoom"),
    d(4, "CarbonDioxideSensor", "MeetingRoom"),
    d(2, "Projector", "MeetingRoom"),
    d(2, "Speaker", "MeetingRoom"),
    d(2, "Camera", "MeetingRoom", nick="화상회의 카메라 {i}"),
    d(2, "AudioRecorder", "MeetingRoom", "", "회의 녹음기 {i}"),
    d(3, "Light|Switch", "OpenSpace", "LightSwitch,Main"),
    d(1, "Speaker", "OpenSpace", "Main"),
    d(2, "Ventilator", "MeetingRoom"),
    d(3, "MultiButton", "MeetingRoom"),
    d(2, "TemperatureSensor", "OpenSpace"),
    d(1, "DoorLock", "Entrance"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "OccupancyCounter", "Entrance"),
    d(1, "Printer", "OpenSpace"),
])

S["OFFICE04"] = build("OFFICE04", "office", "콜센터 (소음·공조 중심)", "M",
    "좌석 구역별 소음·온도 관리.", [
    d(6, "Light|Switch", "OpenSpace", "LightSwitch,Main", "{i}열 조명"),
    d(1, "Light|Switch", "RestRoom", "LightSwitch"),
    d(1, "Light|Switch", "Pantry", "LightSwitch"),
    d(4, "AirConditioner|Switch", "OpenSpace"),
    d(3, "AirPurifier|Switch", "OpenSpace"),
    d(4, "SoundSensor", "OpenSpace", "", "{i}열 소음 센서"),
    d(4, "TemperatureSensor", "OpenSpace"),
    d(2, "HumiditySensor", "OpenSpace"),
    d(2, "CarbonDioxideSensor", "OpenSpace"),
    d(3, "Ventilator", "OpenSpace"),
    d(2, "Display", "OpenSpace", "", "실적 현황판 {i}"),
    d(2, "Speaker", "OpenSpace", "Main"),
    d(1, "OccupancyCounter", "Entrance"),
    d(1, "RfidReader", "Entrance"),
    d(1, "DoorLock", "Entrance"),
    d(1, "Printer", "OpenSpace"),
    d(1, "CoffeeMaker", "Pantry"),
    d(1, "Fan", "Pantry"),
    d(1, "SmokeDetector", "OpenSpace"),
    d(1, "MenuProvider", "System"),
])

S["OFFICE05"] = build("OFFICE05", "office", "대형 오피스 2개 층", "L",
    "가장 큰 오피스. 층 × 구역 두 단계 한정어가 모두 필요.", [
    d(8, "Light|Switch", "OpenSpace", "LightSwitch,Floor1,Main"),
    d(8, "Light|Switch", "OpenSpace", "LightSwitch,Floor2"),
    d(2, "Light|Switch", "MeetingRoom", "LightSwitch,Floor1"),
    d(2, "Light|Switch", "MeetingRoom", "LightSwitch,Floor2"),
    d(2, "Light|Switch", "Hallway", "LightSwitch,Floor1"),
    d(2, "Light|Switch", "Hallway", "LightSwitch,Floor2"),
    d(4, "AirConditioner|Switch", "OpenSpace", "Floor1"),
    d(4, "AirConditioner|Switch", "OpenSpace", "Floor2"),
    d(4, "PresenceSensor", "OpenSpace", "Floor1"),
    d(4, "PresenceSensor", "OpenSpace", "Floor2"),
    d(4, "TemperatureSensor", "OpenSpace", "Floor1"),
    d(4, "TemperatureSensor", "OpenSpace", "Floor2"),
    d(2, "AirQualitySensor", "OpenSpace", "Floor1"),
    d(2, "AirQualitySensor", "OpenSpace", "Floor2"),
    d(4, "Ventilator", "OpenSpace"),
    d(4, "Display", "MeetingRoom"),
    d(2, "Projector", "MeetingRoom"),
    d(2, "MultiButton", "MeetingRoom"),
    d(4, "Speaker", "OpenSpace", "Main"),
    d(4, "Printer", "OpenSpace"),
    d(2, "RfidReader", "Entrance"),
    d(2, "DoorLock", "Entrance"),
    d(2, "Door", "Entrance", "", "자동문 {i}"),
    d(2, "OccupancyCounter", "Entrance"),
    d(4, "Camera", "Hallway"),
    d(2, "SmokeDetector", "Hallway"),
    d(2, "Siren|Switch", "Hallway", "Main"),
    d(8, "WindowCovering", "OpenSpace", "Blind"),
    d(1, "Button", "OpenSpace"),
    d(2, "EnergyMeter", "Utility"),
    d(1, "EmailProvider", "System"),
    d(1, "CloudServiceProvider", "System"),
    d(1, "MenuProvider", "System"),
])

S["OFFICE06"] = build("OFFICE06", "office", "지점 사무소 (소형)", "S",
    "작은 지점. 금고와 출입 통제가 있음.", [
    d(3, "Light|Switch", "OpenSpace", "LightSwitch,Main"),
    d(1, "Light|Switch", "MeetingRoom", "LightSwitch"),
    d(1, "Button", "MeetingRoom"),
    d(1, "AirConditioner|Switch", "OpenSpace"),
    d(1, "Safe", "OpenSpace", nick="지점 금고"),
    d(1, "DoorLock", "Entrance"),
    d(1, "RfidReader", "Entrance"),
    d(2, "Camera", "OpenSpace"),
    d(1, "FaceRecognizer", "Entrance"),
    d(1, "Siren|Switch", "Entrance", "Main"),
    d(1, "MotionSensor", "OpenSpace"),
    d(1, "PresenceSensor", "OpenSpace"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(2, "TemperatureSensor", "OpenSpace"),
    d(1, "Printer", "OpenSpace"),
    d(1, "Speaker", "OpenSpace", "Main"),
    d(1, "Thermostat", "OpenSpace"),
    d(1, "CoffeeMaker", "Pantry"),
], missing=["Projector", "Display", "Ventilator"])

# ══ 연구실 5 ════════════════════════════════════════════════════════════════
def lab01():
    src = open(os.path.join(ROOT, "run.py"), encoding="utf-8").read()
    m = re.search(r"CONNECTED_DEVICES\s*=\s*(\{.*?\n\})", src, re.S)
    devs = ast.literal_eval(m.group(1))
    remap = {"ToastPublisher": "NotificationProvider"}
    for v in devs.values():
        v["category"] = [remap.get(c, c) for c in v["category"]]
        v["tags"] = [remap.get(t, t) for t in v["tags"]]
    for did, v in devs.items():
        if "GlobalVariable" in v["category"]:
            v["variables"] = GLOBALS.get("LAB01", {})
    # 실제 허브엔 없지만 벤치마크 배치상 넣는 것 (LAB01 은 build() 를 안 거친다)
    for cat, nk in [("SunProvider", "해")] + \
                   ([("WeatherProvider", "날씨")] if "LAB01" in WEATHER else []) + \
                   ([("PersonTracker", "내 폰")] if "LAB01" in PERSON_TRACKER else []) + \
                   ([("CalendarProvider", "일정")] if "LAB01" in CALENDAR else []):
        devs[f"LAB01_System_{cat}"] = {"nickname": nk, "category": [cat],
                                       "tags": ["System", cat]}
    return {"kind": "lab", "name_ko": "실제 연구실 허브 (run.py 인벤토리)", "size": "L",
            "notes": "손대지 않은 실물 목록. 별명·브랜드·구역 태그가 실제 그대로라 "
                     "이 벤치마크에서 유일한 '현장' 공간. ToastPublisher 만 3.0.0 의 "
                     "NotificationProvider 로 이름을 맞췄고, 전역 변수 정의만 얹었다.",
            "missing_on_purpose": [], "devices": devs}


S["LAB01"] = lab01()

S["LAB02"] = build("LAB02", "lab", "화학 실험실", "M",
    "후드·가스 감지·비상정지. 안전 자동화가 나올 공간.", [
    d(4, "Light|Switch", "LabRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "Storage", "LightSwitch"),
    d(3, "Ventilator", "LabRoom", "", "흄후드 {i}"),
    d(2, "GasSensor", "LabRoom"),
    d(1, "CarbonMonoxideSensor", "LabRoom"),
    d(1, "AirQualitySensor", "LabRoom"),
    d(1, "SmokeDetector", "LabRoom"),
    d(1, "EmergencyStop", "LabRoom", "Main"),
    d(1, "Siren|Switch", "LabRoom", "Main"),
    d(2, "Chamber", "LabRoom", "", "항온항습기 {i}"),
    d(1, "Refrigerator", "Storage", nick="시약 냉장고"),
    d(2, "TemperatureSensor", "LabRoom"),
    d(2, "HumiditySensor", "LabRoom"),
    d(1, "PressureSensor", "LabRoom"),
    d(1, "Pump", "LabRoom"),
    d(1, "LeakSensor", "LabRoom"),
    d(2, "Valve", "LabRoom"),
    d(1, "DoorLock", "Entrance"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "Camera", "LabRoom"),
    d(1, "Speaker", "LabRoom", "Main"),
    d(2, "Plug|Switch|PowerMeter", "LabRoom"),
    d(1, "Button", "LabRoom"),
    d(1, "ProductionMachine", "LabRoom"),
    d(1, "MessageSender", "System"),
])

S["LAB03"] = build("LAB03", "lab", "생물 실험실", "M",
    "배양·저온 보관 중심. 온도 이탈 감시 자동화.", [
    d(3, "Light|Switch", "LabRoom", "LightSwitch,Main"),
    d(1, "Light|Switch", "ColdRoom", "LightSwitch"),
    d(3, "Chamber", "LabRoom", "", "인큐베이터 {i}"),
    d(2, "Refrigerator", "ColdRoom", "", "초저온 냉동고 {i}"),
    d(1, "WaterQualitySensor", "LabRoom", nick="배양수 수질 센서"),
    d(4, "TemperatureSensor", "ColdRoom"),
    d(2, "TemperatureSensor", "LabRoom"),
    d(2, "HumiditySensor", "LabRoom"),
    d(1, "CarbonDioxideSensor", "LabRoom"),
    d(2, "Ventilator", "LabRoom"),
    d(1, "AirPurifier|Switch", "LabRoom"),
    d(1, "DoorLock", "Entrance"),
    d(1, "ContactSensor", "ColdRoom", "Door"),
    d(1, "Siren|Switch", "LabRoom", "Main"),
    d(1, "Speaker", "LabRoom", "Main"),
    d(1, "Camera", "LabRoom"),
    d(2, "Plug|Switch|EnergyMeter", "LabRoom"),
    d(1, "Button", "LabRoom"),
    d(1, "GasSensor", "LabRoom"),
    d(1, "MessageSender", "System"),
    d(1, "EmailProvider", "System"),
])

S["LAB04"] = build("LAB04", "lab", "전자·로봇 랩", "M",
    "로봇팔·계측 장비. 장비 전원과 소비 전력 자동화.", [
    d(4, "Light|Switch", "LabRoom", "LightSwitch,Main"),
    d(2, "ArmRobot", "LabRoom", "", "로봇팔 {i}"),
    d(1, "AirCompressor", "LabRoom"),
    d(1, "EmergencyStop", "LabRoom", "Main"),
    d(1, "SafetyBarrier", "LabRoom"),
    d(1, "StatusLight", "LabRoom"),
    d(4, "Plug|Switch|PowerMeter|EnergyMeter", "LabRoom", "", "장비 콘센트 {i}"),
    d(1, "Printer", "LabRoom", nick="3D 프린터"),
    d(2, "Camera", "LabRoom"),
    d(1, "Display", "LabRoom"),
    d(2, "TemperatureSensor", "LabRoom"),
    d(1, "HumiditySensor", "LabRoom"),
    d(1, "VibrationSensor", "LabRoom"),
    d(1, "SoundSensor", "LabRoom"),
    d(1, "AudioRecorder", "LabRoom"),
    d(1, "AirConditioner|Switch", "LabRoom"),
    d(1, "Ventilator", "LabRoom"),
    d(1, "DoorLock", "Entrance"),
    d(1, "PresenceSensor", "LabRoom"),
    d(1, "Speaker", "LabRoom", "Main"),
    d(1, "Button", "LabRoom"),
    d(1, "ProductionMachine", "LabRoom"),
])

S["LAB05"] = build("LAB05", "lab", "소형 테스트베드", "S",
    "기기 수가 적은 시험 공간. 구역 태그 1~3 만 있음.", [
    d(3, "Light|Switch", "TestBed", "LightSwitch,Main", "구역 {i} 조명"),
    d(3, "PresenceSensor", "TestBed", "", "구역 {i} 재실"),
    d(1, "MultiButton", "TestBed"),
    d(1, "LevelControl|Switch", "TestBed"),
    d(1, "Button", "TestBed"),
    d(1, "Speaker", "TestBed", "Main"),
    d(1, "AirQualitySensor", "TestBed"),
    d(2, "TemperatureSensor", "TestBed"),
    d(1, "HumiditySensor", "TestBed"),
    d(1, "LightSensor", "TestBed"),
    d(1, "MotionSensor", "TestBed"),
    d(2, "Plug|Switch|PowerMeter", "TestBed"),
    d(1, "Camera", "TestBed"),
    d(1, "Chamber", "TestBed"),
], missing=["AirConditioner", "DoorLock", "WindowCovering", "Siren"])

# ══ 농장 4 ══════════════════════════════════════════════════════════════════
S["FARM01"] = build("FARM01", "farm", "비닐하우스 (토마토)", "M",
    "구역 3개짜리 온실. 관수·환기·보광이 구역마다 한 벌씩.", [
    d(3, "GrowLight|Switch", "Greenhouse", "", "{i}번 하우스 보광등"),
    d(3, "SoilMoistureSensor", "Greenhouse", "", "{i}번 하우스 토양 센서"),
    d(3, "Valve", "Greenhouse", "", "{i}번 하우스 관수 밸브"),
    d(3, "Sprinkler", "Greenhouse"),
    d(3, "Ventilator", "Greenhouse", "", "{i}번 하우스 환기팬"),
    d(3, "WindowCovering", "Greenhouse", "Screen", "{i}번 하우스 차광막"),
    d(4, "TemperatureSensor", "Greenhouse"),
    d(3, "HumiditySensor", "Greenhouse"),
    d(2, "CarbonDioxideSensor", "Greenhouse"),
    d(1, "LightSensor", "Greenhouse"),
    d(1, "Heater", "Greenhouse", nick="온실 난방기"),
    d(1, "Pump", "Utility", nick="관수 펌프"),
    d(1, "WaterLevelSensor", "Utility", nick="양액 탱크 수위"),
    d(1, "WaterQualitySensor", "Utility", nick="양액 센서"),
    d(1, "Chamber", "Storage", nick="육묘 챔버"),
    d(1, "TemperatureSensor", "Outdoor"),
    d(1, "RainSensor", "Outdoor"),
    d(1, "WindSensor", "Outdoor"),
    d(1, "WeatherProvider", "Outdoor"),
    d(1, "Camera", "Greenhouse"),
    d(1, "Speaker", "Greenhouse", "Main"),
    d(1, "Button", "Greenhouse"),
    d(1, "GrowLight", "Greenhouse"),
    d(1, "MessageSender", "System"),
])

S["FARM02"] = build("FARM02", "farm", "축사 (양돈)", "M",
    "동별 급이·환기·암모니아 감시. 무게로 출하 판단.", [
    d(4, "Light|Switch", "Barn", "LightSwitch", "{i}동 조명"),
    d(4, "FeedDispenser", "Barn", "", "{i}동 급이기"),
    d(4, "Ventilator", "Barn", "", "{i}동 환기팬"),
    d(4, "Fan|Switch", "Barn", "", "{i}동 순환팬"),
    d(4, "TemperatureSensor", "Barn"),
    d(4, "HumiditySensor", "Barn"),
    d(2, "GasSensor", "Barn", "", "암모니아 센서 {i}"),
    d(1, "CarbonDioxideSensor", "Barn"),
    d(2, "WeightSensor", "Barn", "", "{i}동 체중계"),
    d(2, "WaterLevelSensor", "Barn", "", "{i}동 급수 탱크"),
    d(2, "FlowSensor", "Barn", "", "{i}동 급수 유량계"),
    d(2, "Valve", "Barn"),
    d(1, "Pump", "Utility"),
    d(4, "Camera", "Barn"),
    d(1, "Siren|Switch", "Barn", "Main"),
    d(1, "Speaker", "Barn", "Main"),
    d(1, "Humidifier", "Barn"),
    d(1, "Heater", "Barn", nick="축사 난방기"),
    d(1, "FeedDispenser", "Barn"),
    d(1, "EnergyMeter", "Utility"),
    d(1, "Battery", "Utility", nick="비상 발전 배터리"),
    d(1, "TemperatureSensor", "Outdoor"),
    d(1, "MessageSender", "System"),
])

S["FARM03"] = build("FARM03", "farm", "노지 과수원", "M",
    "실외뿐. 날씨 의존 자동화(서리·강풍·강우)가 나올 공간.", [
    d(4, "SoilMoistureSensor", "Field", "Outdoor", "{i}구역 토양 센서"),
    d(4, "Valve", "Field", "Outdoor", "{i}구역 관수 밸브"),
    d(4, "Sprinkler", "Field", "Outdoor", "{i}구역 스프링클러"),
    d(3, "TemperatureSensor", "Field", "Outdoor"),
    d(2, "HumiditySensor", "Field", "Outdoor"),
    d(1, "RainSensor", "Field", "Outdoor"),
    d(1, "WindSensor", "Field", "Outdoor"),
    d(1, "UvSensor", "Field", "Outdoor"),
    d(1, "LightSensor", "Field", "Outdoor"),
    d(1, "Pump", "Utility", nick="관정 펌프"),
    d(1, "WaterLevelSensor", "Utility"),
    d(1, "FlowSensor", "Utility"),
    d(2, "Camera", "Field", "Outdoor"),
    d(2, "Light|Switch", "Field", "LightSwitch,Outdoor"),
    d(1, "Siren|Switch", "Field", "Outdoor,Main", nick="조수 퇴치기"),
    d(2, "Charger", "Field", "Outdoor", "태양광 충전기 {i}"),
    d(1, "MotionSensor", "Field", "Outdoor"),
    d(1, "SoilMoistureSensor", "Field"),
    d(1, "EnergyMeter", "Utility"),
    d(1, "Humidifier", "Utility"),
    d(1, "WeatherProvider", "Outdoor"),
    d(1, "MessageSender", "System"),
], missing=["AirConditioner", "DoorLock", "Speaker"])

S["FARM04"] = build("FARM04", "farm", "수직 스마트팜", "L",
    "층(Tier) × 구역 두 단계 한정어. 양액 순환과 보광이 층마다.", [
    d(6, "GrowLight|Switch", "GrowRoom", "Tier1", "1단 보광등 {i}"),
    d(6, "GrowLight|Switch", "GrowRoom", "Tier2", "2단 보광등 {i}"),
    d(6, "GrowLight|Switch", "GrowRoom", "Tier3", "3단 보광등 {i}"),
    d(3, "Pump", "Utility", "", "양액 펌프 {i}"),
    d(3, "WaterQualitySensor", "Utility", "", "양액 센서 {i}"),
    d(3, "WaterLevelSensor", "Utility", "", "양액 탱크 {i}"),
    d(3, "FlowSensor", "GrowRoom"),
    d(2, "TiltSensor", "GrowRoom", "", "{i}단 트레이 기울기"),
    d(6, "Valve", "GrowRoom"),
    d(6, "TemperatureSensor", "GrowRoom"),
    d(3, "HumiditySensor", "GrowRoom"),
    d(2, "CarbonDioxideSensor", "GrowRoom"),
    d(3, "Ventilator", "GrowRoom"),
    d(2, "Chamber", "GrowRoom", "", "육묘 챔버 {i}"),
    d(2, "AirConditioner|Switch", "GrowRoom"),
    d(1, "Dehumidifier|Switch", "GrowRoom"),
    d(2, "Camera", "GrowRoom"),
    d(2, "EnergyMeter", "Utility"),
    d(1, "DoorLock", "Entrance"),
    d(1, "ContactSensor", "Entrance", "Door"),
    d(1, "Speaker", "GrowRoom", "Main"),
    d(1, "Display", "GrowRoom"),
    d(1, "Button", "GrowRoom"),
    d(1, "MessageSender", "System"),
])

# ══ 공장 5 ══════════════════════════════════════════════════════════════════
S["FACT01"] = build("FACT01", "factory", "조립 라인", "M",
    "라인 3개. 비상정지·안전 barrier·신호등이 있어 거절해야 마땅한 명령이 많음.", [
    d(3, "ConveyorBelt", "Line", "", "{i}라인 컨베이어"),
    d(3, "ProductionMachine", "Line", "", "{i}라인 조립기"),
    d(3, "StatusLight", "Line", "", "{i}라인 신호등"),
    d(3, "SafetyBarrier", "Line"),
    d(2, "EmergencyStop", "Line", "Main"),
    d(2, "ArmRobot", "Line"),
    d(6, "Light|Switch", "Line", "LightSwitch,Main"),
    d(3, "ProximitySensor", "Line"),
    d(2, "VibrationSensor", "Line"),
    d(3, "TemperatureSensor", "Line"),
    d(1, "HumiditySensor", "Line"),
    d(2, "Ventilator", "Line"),
    d(2, "Camera", "Line"),
    d(2, "Speaker", "Line", "Main"),
    d(1, "Display", "Line", nick="생산 현황판"),
    d(2, "EnergyMeter", "Utility"),
    d(1, "AirCompressor", "Utility"),
    d(1, "PowerMeter", "Utility"),
    d(1, "Siren|Switch", "Line", "Main"),
    d(1, "SmokeDetector", "Line"),
    d(1, "Button", "Line"),
    d(1, "RfidReader", "Entrance"),
    d(1, "MessageSender", "System"),
])

S["FACT02"] = build("FACT02", "factory", "물류 창고", "M",
    "도크 문·재고 계량·출입 인식. 실내외 경계가 있음.", [
    d(4, "GarageDoor", "Dock", "", "{i}번 도크 문"),
    d(4, "ProximitySensor", "Dock"),
    d(2, "ConveyorBelt", "Warehouse"),
    d(3, "WeightSensor", "Warehouse", "", "{i}번 계량대"),
    d(3, "TiltSensor", "Warehouse", "", "{i}번 적재 기울기 센서"),
    d(2, "RfidReader", "Dock"),
    d(1, "Door", "Entrance", "", "창고 자동문"),
    d(1, "FaceRecognizer", "Entrance"),
    d(8, "Light|Switch", "Warehouse", "LightSwitch,Main"),
    d(2, "Light|Switch", "Dock", "LightSwitch"),
    d(4, "MotionSensor", "Warehouse"),
    d(4, "Camera", "Warehouse"),
    d(2, "Camera", "Dock"),
    d(4, "TemperatureSensor", "Warehouse"),
    d(2, "HumiditySensor", "Warehouse"),
    d(3, "Ventilator", "Warehouse"),
    d(1, "SmokeDetector", "Warehouse"),
    d(1, "Siren|Switch", "Warehouse", "Main"),
    d(2, "Speaker", "Warehouse", "Main"),
    d(1, "Display", "Dock"),
    d(1, "Button", "Dock"),
    d(1, "OccupancyCounter", "Entrance"),
    d(1, "DoorLock", "Entrance"),
    d(2, "EnergyMeter", "Utility"),
    d(1, "MessageSender", "System"),
])

S["FACT03"] = build("FACT03", "factory", "식품 가공", "M",
    "위생·저온·수질. 냉장 이탈과 세척 자동화.", [
    d(3, "Chamber", "ProcessRoom", "", "{i}번 저온 챔버"),
    d(3, "Refrigerator", "ColdStorage", "", "{i}번 냉장고"),
    d(2, "ConveyorBelt", "ProcessRoom"),
    d(2, "ProductionMachine", "ProcessRoom", "", "{i}번 포장기"),
    d(2, "WaterQualitySensor", "Utility"),
    d(2, "FlowSensor", "Utility"),
    d(3, "Valve", "ProcessRoom"),
    d(1, "Pump", "Utility"),
    d(1, "PowerMeter", "Utility"),
    d(6, "TemperatureSensor", "ColdStorage"),
    d(3, "TemperatureSensor", "ProcessRoom"),
    d(3, "HumiditySensor", "ProcessRoom"),
    d(3, "Ventilator", "ProcessRoom"),
    d(6, "Light|Switch", "ProcessRoom", "LightSwitch,Main"),
    d(2, "ContactSensor", "ColdStorage", "Door"),
    d(2, "Camera", "ProcessRoom"),
    d(2, "StatusLight", "ProcessRoom"),
    d(1, "EmergencyStop", "ProcessRoom", "Main"),
    d(1, "Siren|Switch", "ProcessRoom", "Main"),
    d(2, "Speaker", "ProcessRoom", "Main"),
    d(1, "WeightSensor", "ProcessRoom"),
    d(1, "ConveyorBelt", "ProcessRoom"),
    d(1, "SafetyBarrier", "ProcessRoom"),
    d(1, "RfidReader", "Entrance"),
    d(1, "MessageSender", "System"),
])

S["FACT04"] = build("FACT04", "factory", "기계 가공 공장", "M",
    "진동·압축공기·공구 수명. 예지 보전 자동화가 나올 공간.", [
    d(4, "ProductionMachine", "MachineShop", "", "{i}호기"),
    d(4, "VibrationSensor", "MachineShop", "", "{i}호기 진동 센서"),
    d(2, "AirCompressor", "Utility"),
    d(2, "PressureSensor", "Utility"),
    d(1, "PowerMeter", "Utility"),
    d(2, "ArmRobot", "MachineShop"),
    d(2, "SafetyBarrier", "MachineShop"),
    d(2, "EmergencyStop", "MachineShop", "Main"),
    d(4, "StatusLight", "MachineShop"),
    d(6, "Light|Switch", "MachineShop", "LightSwitch,Main"),
    d(4, "TemperatureSensor", "MachineShop"),
    d(2, "SoundSensor", "MachineShop"),
    d(2, "Ventilator", "MachineShop"),
    d(2, "Camera", "MachineShop"),
    d(4, "EnergyMeter", "MachineShop", "", "{i}호기 전력계"),
    d(1, "Display", "MachineShop", nick="가동률 현황판"),
    d(2, "Speaker", "MachineShop", "Main"),
    d(1, "SmokeDetector", "MachineShop"),
    d(1, "ProximitySensor", "MachineShop"),
    d(1, "TiltSensor", "MachineShop"),
    d(1, "RfidReader", "Entrance"),
    d(1, "MessageSender", "System"),
])

S["FACT05"] = build("FACT05", "factory", "유틸리티 설비동", "L",
    "펌프·밸브·탱크·가스가 몰린 설비동. 같은 종류가 번호로만 갈림 — "
    "번호 한정어가 안 붙으면 되묻기.", [
    d(6, "Pump", "PumpRoom", "", "{i}번 펌프"),
    d(8, "Valve", "PumpRoom", "", "{i}번 밸브"),
    d(6, "PressureSensor", "PumpRoom"),
    d(4, "FlowSensor", "PumpRoom"),
    d(4, "WaterLevelSensor", "TankYard", "", "{i}번 탱크 수위"),
    d(2, "WaterQualitySensor", "TankYard"),
    d(3, "GasSensor", "BoilerRoom"),
    d(2, "CarbonMonoxideSensor", "BoilerRoom"),
    d(2, "AirCompressor", "BoilerRoom"),
    d(2, "WaterHeater", "BoilerRoom", "", "{i}번 보일러"),
    d(4, "TemperatureSensor", "BoilerRoom"),
    d(4, "VibrationSensor", "PumpRoom"),
    d(6, "EnergyMeter", "Utility", "", "{i}번 계량기"),
    d(6, "Light|Switch", "PumpRoom", "LightSwitch,Main"),
    d(2, "Light|Switch", "BoilerRoom", "LightSwitch"),
    d(3, "Ventilator", "BoilerRoom"),
    d(2, "EmergencyStop", "BoilerRoom", "Main"),
    d(4, "StatusLight", "PumpRoom"),
    d(2, "Siren|Switch", "BoilerRoom", "Main"),
    d(2, "Speaker", "PumpRoom", "Main"),
    d(2, "Camera", "PumpRoom"),
    d(2, "LeakSensor", "PumpRoom"),
    d(1, "Display", "PumpRoom"),
    d(1, "MessageSender", "System"),
    d(1, "EmailProvider", "System"),
])


def main():
    cat = json.load(open(CATALOG, encoding="utf-8"))
    known = {k for k in cat if not k.startswith("$")}

    assert set(OCCUPANCY) == set(S), set(OCCUPANCY) ^ set(S)
    cut = _prune_occupancy(S)
    occ_bad = _check_occupancy(S)
    print(f"재실 주체 정리: 겹치는 센서 {cut}대 제거")
    if occ_bad:
        print("재실 주체 충돌:", *occ_bad, sep="\n  ")

    bad, thin = [], []
    for sid, sp in S.items():
        real = [v for k, v in sp["devices"].items() if "System" not in v["tags"]]
        if len(real) < 10:
            thin.append((sid, len(real)))
        for did, v in sp["devices"].items():
            for c in v["category"]:
                if c not in known:
                    bad.append(f"{sid}/{did}: {c}")
    if bad:
        print("카탈로그에 없는 카테고리:", *sorted(set(bad))[:20], sep="\n  ")
    if thin:
        print("기기 10대 미만:", thin)

    # 별명을 영어로 — 데이터셋이 영어다. 한국어는 nickname_ko 로 남긴다.
    n_nick = 0
    for sp in S.values():
        for v in sp["devices"].values():
            if v.get("nickname"):
                v["nickname_ko"] = v["nickname"]
                v["nickname"] = to_en(v["nickname"])
                n_nick += 1
    print(f"별명 {n_nick}개를 영어로")

    out = {"$version": "1.1.0", "$catalog": "service_list_ver3.1.0.json",
           "$comment": "벤치마크 공간 40 — 명령어는 space_id 로 이 목록을 가리킨다.",
           "spaces": S}
    dst = os.path.join(HERE, "spaces.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    import collections
    kinds = collections.Counter(sp["kind"] for sp in S.values())
    tot = sum(len(sp["devices"]) for sp in S.values())
    cats = collections.Counter(c for sp in S.values() for v in sp["devices"].values()
                               for c in v["category"])
    nick = sum(1 for sp in S.values() for v in sp["devices"].values() if v.get("nickname"))
    print(f"\nspaces.json: {len(S)} 공간, 기기 {tot}대, 별명 {nick}개")
    print("종류별:", dict(kinds))
    print("공간별 기기 수:", {k: len(v["devices"]) for k, v in S.items()})
    withv = [k for k, v in S.items()
             if any(d.get("variables") for d in v["devices"].values())]
    for lbl, lst in (("WeatherProvider", WEATHER), ("PersonTracker", PERSON_TRACKER),
                     ("CalendarProvider", CALENDAR)):
        print(f"{lbl} 있는 공간 {len(lst)} / 없는 공간 {len(S) - len(lst)}")
    print(f"\n전역 변수 있는 공간 {len(withv)} / 없는 공간 {len(S) - len(withv)}")
    print("  있음:", ", ".join(sorted(withv)))
    print(f"\n쓰인 카테고리 {len(cats)}/{len(known)}")
    print("카탈로그에 있으나 어느 공간에도 없는 카테고리:",
          sorted(known - set(cats)))
    import collections as _c
    print("\n재실 판단 주체:", dict(_c.Counter(sp["occupancy"] for sp in S.values())))
    for m in ("global", "motion", "presence", "phone", "none"):
        print(f"  {m:9s}", ", ".join(k for k, v in S.items() if v["occupancy"] == m))
    return 1 if (bad or thin or occ_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
