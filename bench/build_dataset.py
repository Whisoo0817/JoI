#!/usr/bin/env python3
"""scenarios.csv 의 배분대로 영어 명령문 5,000개를 만든다 — 3단계.

한 문장 = (공간) + (기기 지목 방식) + (문형 틀) + (말투).
공간이 실행·되묻기·거절을 가른다:
  execute  시킬 기기가 있고 어느 기기인지 정해진다
  ask      기기를 안 댔는데 후보가 여러 종류다 / 단수로 불렀는데 같은 기기가 여럿이다
  refuse   그 공간에 그 기기가 없다

원천(IFTTT·HA)의 문장은 한 줄도 안 쓴다 — 시나리오만 가져오고 문장은 새로 쓴다.
"""
import collections
import csv
import json
import os
import random
import re
import sys

import ir as IR
import templates as T
import korean as KO
from effects import E, effects_of
from want import WANT
from policy import NOTIFY_ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20260823
REFUSE_RATE = 0.10
# TAP(트리거-액션 한 줄)로는 표현할 수 없는 문형에 얼마를 줄지.
# 원천(IFTTT·HA)에는 이런 게 0 에 가깝다 — 그 플랫폼들이 표현을 못 해서다.
HARD_RATE = 0.20       # 반복·제한시간·누적·비교 (D7~D13)
SOFT_RATE = 0.06       # 조건·지연이 얹힌 정도 (D2·D3·D5)

# 기기도 서비스도 안 대는 문장("시원하게 해줘")에 얼마를 줄지.
# 이건 난이도 축이 아니라 "기기 지목" 축의 값이다 — 그래서 T0~T4 분포는 안 건드리고
# 다른 지목 방식(별명·장소·종류·전체·단수)에서 비례로 가져온다.
# T3·T4(반복·누적)에는 안 붙인다. 의도만 말하는 사람이 복잡한 반복 규칙을 같이 주지 않는다.
# 200줄을 한 주기로 본다. 로직 슬롯(7의 배수)과 의도 슬롯(23의 배수)이 겹치는 자리가
# 있어서 명목 비율과 실제 비율이 다르다 — 실제로 10.0% 가 나오는 칸수를 직접 적는다.
VAGUE_SLOTS = 29       # 200줄 중 29칸. T3·T4 를 뺀 뒤 실제 10.0%
ASK_RATE = 0.10

ACT_CAT = {
    "light.on": "Light", "light.off": "Light", "light.dim": "Light",
    "light.color": "Light", "light.scene": "Light", "switch": "Switch",
    "plug": "Plug", "thermostat": "Thermostat", "ac": "AirConditioner", "fan": "Fan",
    "purifier": "AirPurifier", "humidity": "Humidifier", "cover": "WindowCovering",
    "lock": "DoorLock", "garage": "GarageDoor", "media": "Television",
    "speaker": "Speaker", "camera": "Camera", "siren": "Siren",
    "vacuum": "RobotVacuumCleaner", "mower": "Mower", "coffee": "CoffeeMaker",
    "waterheater": "WaterHeater", "notify": "NotificationProvider", "query": "",
    "timer": "Clock", "sprinkler": "Sprinkler", "growlight": "GrowLight",
    "ventilator": "Ventilator", "feeder": "FeedDispenser", "pump": "Pump",
    "valve": "Valve", "chamber": "Chamber", "conveyor": "ConveyorBelt",
    "compressor": "AirCompressor", "statuslight": "StatusLight", "armrobot": "ArmRobot",
}

# 기기를 안 댔을 때("시원하게 해줘") 후보 찾기는 효과로 한다 — effects.py + want.py.
# 원하는 효과를 내는 서비스를 가진 기기의 카테고리를 모은다. 효과를 내는 카테고리만 센다
# (에어컨에 온도센서가 같이 달렸다고 온도센서가 후보가 되면 안 된다).
def rival_cats(sp, act):
    want = set(WANT.get(act, []))
    if not want:
        return set()
    out = set()
    for d in sp["devices"].values():
        combo = tuple(d["category"])
        for c in combo:
            if c == "Switch":
                # Switch 효과는 달린 기기 쪽으로 돌린다
                for m in E.get("Switch", {}):
                    if set(effects_of("Switch", m, combo)) & want:
                        out.update(x for x in combo if x != "Switch")
                continue
            for m in E.get(c, {}):
                if set(effects_of(c, m, ())) & want:
                    out.add(c)
    return out


# 장소가 아닌 태그 — LAB01 은 실제 허브라 브랜드·연동 이름이 태그로 붙어 있다
NOT_PLACE = {"AirQualityManagement", "Builtin", "Hejhome", "Matter", "PhilipsHue",
             "Smartthings", "Tuya", "가습기", "NoneNecessary", "lindytest",
             "LightSwitch", "SharedLight", "ModeToggle", "Door", "Window"}
PLACE_FIX = {"BabyRoom": "nursery", "OpenSpace": "open space", "TestBed": "test bed",
             "ColdRoom": "cold room", "ColdStorage": "cold storage",
             "MachineShop": "machine shop", "ProcessRoom": "process room",
             "GrowRoom": "grow room", "PumpRoom": "pump room",
             "BoilerRoom": "boiler room", "TankYard": "tank yard",
             "MeetingRoom": "meeting room", "LivingRoom": "living room",
             "LabRoom": "lab", "BackDoor": "back entrance",
             "Section1": "zone 1", "Section2": "zone 2", "Section3": "zone 3",
             "Section4": "zone 4", "Section5": "zone 5", "Section6": "zone 6"}


def place_en(tag):
    if tag in PLACE_FIX:
        return PLACE_FIX[tag]
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", tag)
    parts = s.split()
    return " ".join(p if len(p) == 1 else p.lower() for p in parts)


def load_spaces():
    S = json.load(open(os.path.join(HERE, "spaces.json"), encoding="utf-8"))["spaces"]
    for sid, sp in S.items():
        by_cat = collections.defaultdict(list)
        for did, d in sp["devices"].items():
            place = next((t for t in d["tags"]
                          if t not in d["category"] and t != "System"
                          and t not in NOT_PLACE and "_" not in t), "")
            for c in d["category"]:
                by_cat[c].append((did, d.get("nickname"), place,
                                  d.get("nickname_ko")))
        sp["_by_cat"] = by_cat
        sp["_cats"] = set(by_cat)
    return S


# ── 기기 지목 ──────────────────────────────────────────────────────────
NOUN = {
    "Light": "lights", "Switch": "switch", "Plug": "plug", "Fan": "fan",
    "AirConditioner": "air conditioner", "Thermostat": "thermostat",
    "AirPurifier": "air purifier", "Humidifier": "humidifier",
    "WindowCovering": "blinds", "DoorLock": "door lock", "GarageDoor": "garage door",
    "Television": "TV", "Speaker": "speaker", "Camera": "camera", "Siren": "siren",
    "RobotVacuumCleaner": "vacuum", "Mower": "mower", "CoffeeMaker": "coffee maker",
    "WaterHeater": "water heater", "Sprinkler": "sprinkler", "GrowLight": "grow lights",
    "Ventilator": "ventilation fan", "FeedDispenser": "feeder", "Pump": "pump",
    "Valve": "valve", "Chamber": "chamber", "ConveyorBelt": "conveyor",
    "AirCompressor": "compressor", "StatusLight": "status light", "ArmRobot": "robot arm",
    "MotionSensor": "motion sensor", "PresenceSensor": "presence sensor",
    "ContactSensor": "door sensor", "SmokeDetector": "smoke detector",
    "LeakSensor": "leak sensor", "GasSensor": "gas sensor",
    "VibrationSensor": "vibration sensor", "TiltSensor": "tilt sensor",
    "ProximitySensor": "proximity sensor", "WindSensor": "wind sensor",
    "PowerMeter": "power meter", "Button": "button", "MultiButton": "scene switch",
    "ProductionMachine": "machine", "Projector": "projector", "Display": "display",
    "Dishwasher": "dishwasher", "LaundryWasher": "washing machine",
    "LaundryDryer": "dryer", "Oven": "oven", "Microwave": "microwave",
    "Refrigerator": "fridge", "ElectricBlanket": "electric blanket",
    "Dehumidifier": "dehumidifier", "Doorbell": "doorbell", "Door": "door",
    "EvCharger": "EV charger", "PetFeeder": "pet feeder", "RangeHood": "range hood",
    "WaterPurifier": "water purifier", "ClothingCare": "clothing care unit",
    "AudioRecorder": "recorder", "Printer": "printer", "Safe": "safe",
    "RiceCooker": "rice cooker", "SafetyBarrier": "safety barrier",
    "EmergencyStop": "emergency stop", "Charger": "charger",
    "TemperatureSensor": "temperature sensor", "HumiditySensor": "humidity sensor",
    "AirQualitySensor": "air quality sensor", "SoilMoistureSensor": "soil sensor",
    "WaterLevelSensor": "water level sensor", "FlowSensor": "flow meter",
    "WaterQualitySensor": "water quality sensor", "WeightSensor": "scale",
    "OccupancyCounter": "people counter", "SoundSensor": "noise sensor",
    "LightSensor": "light sensor", "PressureSensor": "pressure sensor",
    "RainSensor": "rain sensor", "UvSensor": "UV sensor", "Battery": "battery",
    "EnergyMeter": "energy meter", "CarbonDioxideSensor": "CO2 sensor",
    "CarbonMonoxideSensor": "CO sensor", "RfidReader": "badge reader",
    "FaceRecognizer": "face reader", "RotaryControl": "dial", "LevelControl": "dial",
    "ColorControl": "color control",
}


SING = {"Light": "light", "GrowLight": "grow light", "WindowCovering": "blind",
        "MultiButton": "scene switch"}


def plural(n):
    if n.endswith(("ch", "sh", "s", "x", "z")):
        return n + "es"
    return n + "s"


def noun(cat):
    return NOUN.get(cat, re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cat).lower())


def _verdict(hit, is_pl):
    """단수로 부르는데 후보가 여럿이면 되물어야 한다. 복수로 부르면 전부가 정답."""
    if not is_pl and len(hit) > 1:
        return "ask", "ask"
    return "execute", "all"


def refer(rng, sp, cat, style):
    """기기 지목 문구, 가리키는 기기들, 판정, 실제로 쓴 방식, 채점 방식, 한국어 지목구."""
    devs = sp["_by_cat"].get(cat, [])
    if not devs:
        return None
    n = noun(cat)
    is_pl = n.endswith("s")
    if style == "nick":
        cands = [d for d in devs if d[1]]
        if not cands:
            style = "place"
        else:
            did, nick, _, nick_ko = rng.choice(cands)
            return (f"the {nick}", [did], "execute", "nick", "all",
                    KO.refer_ko("nick", cat, nick_ko=nick_ko or nick))
    if style == "place":
        places = [d[2] for d in devs if d[2]]
        if not places:
            style = "plain"
        else:
            pl = rng.choice(places)
            hit = [d[0] for d in devs if d[2] == pl]
            pe = place_en(pl)
            ko = KO.refer_ko("place", cat, place_tag=pl)
            # 같은 방에 같은 기기가 여럿이면 같은 목적으로 놓인 것으로 본다.
            # "the barn fan" 은 축사 선풍기 4대를 다 켜라는 말이지 되물을 일이 아니다.
            if set(pe.split()) & set(n.split()):   # "back door door" 를 막는다
                return f"the {n}", hit, "execute", "place", "all", ko
            return f"the {pe} {n}", hit, "execute", "place", "all", ko
    ids = [d[0] for d in devs]
    if style == "all":
        return (f"all the {n if is_pl else plural(n)}", ids, "execute", "all", "all",
                KO.refer_ko("all", cat))
    if style == "any":
        return (f"any of the {n if is_pl else plural(n)}", ids,
                "execute", "any", "any", KO.refer_ko("any", cat))
    if style == "onedup":
        # 단수로 부르는데 같은 기기가 여럿 — 어느 것인지 되물어야 한다
        # ★ 한국어에는 수가 없어 plain 과 같은 말이 된다 (korean.refer_ko 참고)
        sing = SING.get(cat, n[:-1] if is_pl and not n.endswith("ss") else n)
        v, m = _verdict(ids, False)
        return f"the {sing}", ids, v, "onedup", m, KO.refer_ko("onedup", cat)
    v, m = _verdict(ids, is_pl)
    # 영어는 "the lights"(복수=전부) 와 "the light"(단수=어느 것?) 로 갈리는데
    # 한국어에는 수가 없다. 복수 쪽만 "다" 를 붙여 구분을 살린다.
    return (f"the {n}", ids, v, "plain", m,
            KO.refer_ko("plain", cat, plural=is_pl))


# 즉시 실행일 때의 알림·조회는 대상이 있어야 문장이 된다
NOW_OVERRIDE = {
    "notify": ["let me know if {dev} is still on", "send me the {place} temperature",
               "ping me when {dev} finishes", "remind me to check {dev}",
               "text me the humidity in the {place}",
               "let me know whether anyone is in the {place}",
               "send me a note if {dev} stays on"],
    "query": ["what is the temperature in the {place}", "is {dev} on right now",
              "how humid is the {place}", "tell me if {dev} is open",
              "how much power is {dev} pulling", "what is {dev} set to",
              "is anyone in the {place}"],
}

ALARM_TRIG = {"leak", "smoke", "gas", "emergency", "barrier", "vibration",
              "security", "tilt", "proximity"}
SAFE_START = ("close", "stop", "shut", "turn off", "cut", "lock", "park", "set off",
              "sound", "kill", "send", "let me know", "push", "tell", "make sure",
              "announce", "say", "play a chime", "start recording", "take a snapshot",
              "turn {dev} off", "turn {dev} red")


# ── 라벨 ───────────────────────────────────────────────────────────────
# D축: relabel.py 와 같은 코드 체계. 우리가 만든 문장이라 어떤 틀을 썼는지 알고 있다.
D_NAME = {"D1": "지금 한 번", "D2": "순서+지연", "D3": "조건 지금", "D4": "트리거 기다림",
          "D5": "지속 조건", "D6": "정해진 시각", "D7": "주기 반복"}
# 난이도 5단계 — TAP(IFTTT 같은 트리거 하나 → 동작 하나)이 표현할 수 있느냐가 기준
TIER = {"D1": "T0",                                    # 즉시 실행 (TAP 이전)
        "D4": "T1", "D6": "T1",                        # TAP 그대로
        "D2": "T2", "D3": "T2", "D5": "T2",            # 조건·지연이 얹힘
        "D7": "T3", "D8": "T3", "D9": "T3", "D10": "T3",   # 반복·제한시간 — TAP 불가
        "D11": "T4", "D12": "T4", "D13": "T4"}             # 변수·비교·누적 — TAP 불가
TIER_NAME = {"T0": "즉시 실행", "T1": "TAP 그대로", "T2": "조건·지연",
             "T3": "반복·제한시간", "T4": "변수·비교·누적"}

# B1축: 서비스를 어떻게 쓰나. 문장을 보고 정한다 —
# "거실 온도 알려줘" 는 act 가 notify 여도 값을 읽는 명령이다.
B1 = {"query": "read", "light.dim": "set", "light.color": "set",
      "light.scene": "set", "thermostat": "set", "ac": "set", "humidity": "set",
      "waterheater": "set", "chamber": "set", "cover": "set", "media": "set",
      "statuslight": "set", "timer": "set"}
READ_RE = re.compile(
    r"\b(what|how much|how many|how humid|how hot|tell me the|tell me if|tell me whether|"
    r"send me the|text me the|read out|check whether|check if|is .* (on|open|running)\b|"
    r"let me know (if|whether)|compare it with|is set to)", re.I)


def b1_of(act, sent):
    base = B1.get(act, "act")
    if READ_RE.search(sent):
        return "read" if base in ("act", "read") else base + "|read"
    return base
CONTEXT = {"SunProvider": "sun", "WeatherProvider": "weather",
           "PersonTracker": "phone", "CalendarProvider": "calendar"}


def d_code(mode, tpl):
    """쓴 문형 틀에서 시간·로직 유형을 읽는다."""
    if mode == "now":
        return "D1"
    t = tpl
    if ("while " in t or "stays over" in t or "has been" in t or "has not" in t
            or "for {n} minutes" in t):
        return "D5"
    if "every {n} minutes" in t:
        return "D7"
    if ("every day at" in t or "every morning" in t or "every night" in t
            or "on {weekday}" in t or t.startswith("at {time")):
        return "D6"
    if ("after {n} minutes" in t or "minutes from now" in t or "timer runs out" in t
            or "after waiting" in t):
        return "D2"
    return "D4"


NOTIFY_CHANNEL = {
    "notify.phone":   ("NotificationProvider.SendPush", "PersonTracker"),
    "notify.speaker": ("Speaker.Speak", None),
    "notify.screen":  ("Display.ShowMessage", None),
}


def notify_target(sp, channel_act):
    """알림이 어디로 가나. (서비스, 판정)."""
    if channel_act in NOTIFY_CHANNEL:
        svc, need = NOTIFY_CHANNEL[channel_act]
        c0 = svc.split(".")[0]
        ok = c0 in sp["_cats"] and (not need or need in sp["_cats"])
        return ([svc] if ok else []), ("execute" if ok else "refuse")
    for svc, need in NOTIFY_ORDER:
        c0 = svc.split(".")[0]
        if c0 in sp["_cats"] and (not need or need in sp["_cats"]):
            return [svc], "execute"
    return [], "refuse"


# 재실 판단 권한 → 그 일을 맡은 기기 종류. 공간마다 하나로 못박아 뒀다.
OCC_CAT = {"motion": "MotionSensor", "presence": "PresenceSensor",
           "phone": "PersonTracker"}


def query_targets(sp, sent):
    """"거실 온도 알려줘" 가 어느 센서를 읽는지."""
    low = sent.lower()
    if "anyone" in low or "anybody" in low:
        cat = OCC_CAT.get(sp.get("occupancy", ""))
        if not cat:
            # 전역 변수로 판단하거나 아예 안 보는 공간
            return [], ("global" if sp.get("occupancy") == "global" else "no_device")
    elif "temperature" in low:
        cat = "TemperatureSensor"
    elif "humid" in low:
        cat = "HumiditySensor"
    else:
        return [], ""
    devs = sp["_by_cat"].get(cat, [])
    if not devs:
        return [], "no_device"
    pl = LAST_PLACE[0]
    hit = [d for d, _, p, *_ in devs if p == pl] if pl else []
    return (hit or [d for d, *_ in devs]), ""


def nonhome(tpl, sp):
    """집이 아닌 공간에서는 "집" 이라는 말을 쓰지 않는다 (templates.NONHOME).
    뜻은 같으므로 IR·한국어는 별명으로 같은 자리에 걸린다."""
    return T.NONHOME.get(tpl, tpl) if sp["kind"] != "home" else tpl


def trig_pool(trig, cat_t):
    """문장이 대는 물리량과 시나리오의 센서가 어긋나지 않게 문형을 걸러낸다.
    (압력 센서 시나리오에 "온도가 30도를 넘으면" 이 붙는 것을 막는다)"""
    pool = T.TRIG[trig]
    ok = [t for t in pool
          if IR.TRIG_IR.get(t, {}).get("cat") in (cat_t, "*")
          and (IR.TRIG_IR.get(t, {}).get("cat") != "*" or cat_t in IR.READ_ATTR)]
    return ok or pool


# 이미 끄는 동작에는 "그러고 나서 다시 꺼" 를 얹을 수 없다.
# ("커피포트를 끄고, 30분 뒤에 다시 꺼")  "set off"(작동시킨다)는 켜는 쪽이라 뺀다.
OFF_ACT = re.compile(r"^(close|shut|stop|pause|lock|kill|cancel|disarm|mute|lower)\b"
                     r"|(?<!set )\boff\b|\bis locked\b|\bback to (its|the) dock\b", re.I)


def logic_pool(pool, mode, trig, cat_t, act, body=""):
    """이 상황에서 말이 되는 문형만 남긴다.

    - 이전 값과 견주는 문형(D11)은 숫자를 읽는 방아쇠라야 한다.
      버튼 눌림을 "한 시간 전보다 높으면" 으로 견줄 수는 없다.
    - 오늘 몇 번인지 세는 문형(D12)은 셀 사건이 있어야 한다.
      시각·타이머는 사건이 아니다.
    - 둘 다 방아쇠가 없는 즉시 실행 문장에는 붙을 수 없다.
      무엇을 견주고 무엇을 세는지가 문장에 없기 때문이다.
    - 알림·조회·타이머는 "다시 끄기" 가 없다.
    """
    tp = trig_pool(trig, cat_t) if cat_t else []
    has_num = any(IR.reads_number(t) for t in tp)
    has_evt = any(IR.trig_reads(t) for t in tp)
    out = []
    for di, frame in pool:
        if di in ("D11", "D12") and mode == "now":
            continue
        if di == "D11" and not has_num:
            continue
        if di == "D12" and not has_evt:
            continue
        if "turn it back off" in frame and (act in ("notify", "query", "timer")
                                            or OFF_ACT.search(body)):
            continue
        out.append((di, frame))
    return out or [x for x in pool if x[0] not in ("D11", "D12")] or pool


def act_pool(act, trig):
    """위험 신호로 켜는 문장이 나오지 않게 문형을 걸러낸다."""
    pool = T.ACT[act]
    if trig in ALARM_TRIG:
        safe = [t for t in pool if t.startswith(SAFE_START)]
        if safe:
            return safe
    return pool


def pick_n(rng, act):
    pool = T.VALUES["n"].get(act, T.VALUES["n"]["_default"])
    return rng.choice(pool)


def degrammar(t):
    """"1 minutes" 같은 것을 고친다."""
    t = re.sub(r"\b1 (minute|hour|degree|percent|centimeter|watt)s\b", r"1 \1", t)
    # "all the door locks is locked" → "are locked". 복수로 부르면 동사도 복수다.
    t = re.sub(r"\b(all the [a-z0-9 ]*?s)\s+is\b", r"\1 are", t, flags=re.I)
    return t


LAST_PLACE = [None]
DEV_T_KO = [None]      # {dev_t}(버튼 문형) 의 한국어 지목구
SLOTS = [{}]             # fill() 이 이번에 고른 값들 — 정답 IR 이 같은 값을 써야 한다


def fill(rng, text, sp, act, cat_t):
    """{n} {time} {color} 같은 자잘한 슬롯을 채운다."""
    LAST_PLACE[0] = None
    SLOTS[0] = {}
    if "{n}" in text:
        v = pick_n(rng, act)
        SLOTS[0]["n"] = v
        text = text.replace("{n}", str(v))
    for key in ("time_am", "time_pm", "time", "weekday", "color", "scene",
                "deg", "pct", "lvl", "watt", "kwh", "tilt", "cm", "wind",
                "lo", "hi"):
        if "{%s}" % key in text:
            v = rng.choice(T.VALUES[key])
            SLOTS[0][key] = v
            text = text.replace("{%s}" % key, str(v))
    if "{place}" in text:
        places = sorted({d[2] for c in sp["_by_cat"].values() for d in c if d[2]})
        raw = rng.choice(places) if places else ""
        LAST_PLACE[0] = raw or None
        pl = place_en(raw) if raw else "room"
        # "zone 6" 같은 이름 앞에는 관사가 붙지 않는다
        if pl.split()[0] in ("zone", "line", "row", "barn", "greenhouse", "tier", "room"):
            text = text.replace("the {place}", "{place}")
        text = text.replace("{place}", pl)
    if "{sensor}" in text:
        text = text.replace("{sensor}", "the " + noun(cat_t) if cat_t else "the sensor")
    text = degrammar(text)
    if "{dev_t}" in text:
        r = refer(rng, sp, cat_t, "plain") if cat_t else None
        text = text.replace("{dev_t}", r[0] if r else "it")
        DEV_T_KO[0] = r[5] if r else "그것"
    return text


def tone(rng, s, i):
    name, frame = T.TONE[i % len(T.TONE)]
    if name in ("polite", "ask", "could", "wish"):
        s = s[0].lower() + s[1:]
        return name, frame.format(s=s)
    out = frame.format(s=s)
    return name, out[0].upper() + out[1:]


def main():
    rng = random.Random(SEED)
    S = load_spaces()
    sc = list(csv.DictReader(open(os.path.join(HERE, "scenarios.csv"), encoding="utf-8")))

    rows, seen, parts = [], set(), []
    stats = collections.Counter()
    for si, r in enumerate(sc):
        quota = int(r["quota"])
        elig = r["spaces"].split()
        acts = r["act"].split("+")
        cat_t0 = r["dev_trig"]
        # 그 기기가 없는 공간 — 거절 문장을 만들 자리
        cat_a0 = ACT_CAT.get(acts[0], r["dev_act"])
        missing = [sid for sid, sp in S.items()
                   if cat_a0 and cat_a0 not in sp["_cats"]
                   and (r["mode"] != "domain" or sp["kind"] == r["n_rules"])]
        # 트리거가 바깥 정보 제공자인데 그 공간에 없으면 그것도 거절 사유다
        if cat_t0 in CONTEXT:
            missing += [sid for sid, sp in S.items() if cat_t0 not in sp["_cats"]
                        and (not cat_a0 or cat_a0 in sp["_cats"])]
        n_ref = round(quota * REFUSE_RATE) if missing else 0
        n_ask = round(quota * ASK_RATE)

        for i in range(quota):
            plan = "refuse" if i < n_ref else ("ask" if i < n_ref + n_ask else "execute")
            for attempt in range(60):
                k = i * 7 + attempt * 101 + si * 13
                pool_s = elig
                if plan == "ask":
                    dup = [x for x in elig if len(S[x]["_by_cat"].get(cat_a0, [])) > 1]
                    pool_s = dup or elig
                sid = (rng.choice(missing) if plan == "refuse"
                       else (pool_s[k % len(pool_s)] if attempt == 0
                             else rng.choice(pool_s)))
                sp = S[sid]
                act = acts[0] if plan == "refuse" else acts[k % len(acts)]
                cat_a = ACT_CAT.get(act, r["dev_act"])
                # 카탈로그의 Camera 는 사람을 보지 못한다. 그래서 보안 방아쇠를
                # 카메라 자신의 상태로 걸어 왔는데, 동작까지 카메라면 제 꼬리를
                # 무는 문장이 된다("카메라가 켜지면 카메라를 끈다").
                # 그럴 때만 움직임 센서로 건다. 그것도 없으면 답할 길이 없다.
                cat_t, trig_kind, sec_dead = cat_t0, r["trig"], False
                if trig_kind == "security" and cat_a == "Camera":
                    if "MotionSensor" in sp["_cats"]:
                        cat_t, trig_kind = "MotionSensor", "motion"
                    else:
                        sec_dead = True
                style = ("onedup" if plan == "ask" else
                         ["plain", "place", "nick", "all", "plain", "place", "nick"][k % 7])
                # 시나리오 안의 순번(i)으로 세면 몫이 작은 시나리오가 전부 앞 칸에 걸린다.
                # 전체 행 번호로 세야 5,000줄에 고르게 퍼진다. 7·23 은 200 과 서로 소수.
                slot = (len(rows) * 7) % 200
                use_hard = slot < HARD_RATE * 200
                use_soft = not use_hard and slot < (HARD_RATE + SOFT_RATE) * 200
                use_logic = use_hard or use_soft
                # 의도만 말하는 문장. T3·T4 에는 안 붙인다.
                # 상태 서술("너무 어두워")은 즉시 실행일 때만 — 시간절이 붙으면 깨진다.
                is_t0 = (r["mode"] == "now" and not use_logic)
                vp = T.VAGUE.get(act, {"state": [], "goal": []})
                vpool = (vp["state"] + vp["goal"]) if is_t0 else vp["goal"]
                use_vague = (not use_hard and vpool
                             and (len(rows) * 23) % 200 < VAGUE_SLOTS)
                is_state = False
                tsvc, match, why_force = [], "none", ""
                aslots, tslots, lslots = {}, {}, {}
                act_tpl, vague_tpl, frame, cond_text = "", None, "", ""
                dev_ko, act_place, trig_place = None, None, None
                win_cat = cat_a
                if use_vague:
                    body = vague_tpl = rng.choice(vpool)
                    is_state = body in vp["state"]
                    targets, match = [], "none"
                    rivals = rival_cats(sp, act)
                    expect = ("ask" if len(rivals) > 1
                              else "execute" if len(rivals) == 1 else "refuse")
                    # 후보 카테고리의 기기를 실제로 적어 둔다. 하나면 그게 답,
                    # 여럿이면 되묻기의 선택지가 된다.
                    win_cat = list(rivals)[0] if len(rivals) == 1 else cat_a
                    if rivals:
                        targets = sorted({d for c in rivals
                                          for d, *_ in sp["_by_cat"].get(c, [])})
                        match = "ask" if len(rivals) > 1 else "all"
                    if act == "query":       # 읽은 값을 말해 줄 채널이 있어야 한다
                        tsvc, ok_ch = notify_target(sp, "notify")
                        if ok_ch != "execute":
                            expect, why_force = "refuse", "no_channel"
                    if act == "notify":      # 어디로 알리든 해가 없다 — 되묻지 않고 첫 번째로
                        expect = "execute" if rivals else "refuse"
                        targets, match = [], "none"
                        for svc, need in NOTIFY_ORDER:
                            c0 = svc.split(".")[0]
                            if c0 in sp["_cats"] and (not need or need in sp["_cats"]):
                                tsvc, match = [svc], "all"
                                break
                else:
                    pool = (NOW_OVERRIDE[act] if r["mode"] == "now"
                            and act in NOW_OVERRIDE else act_pool(act, trig_kind))
                    notify_act = act
                    if act == "notify" and r["mode"] != "now" and k % 4 == 0:
                        # 넷에 하나는 채널을 댄다
                        notify_act = ["notify.phone", "notify.speaker", "notify.screen"][k % 3]
                        pool = T.ACT[notify_act]
                    tpl = act_tpl = pool[k % len(pool)] if attempt == 0 else rng.choice(pool)
                    if "{dev}" in tpl:
                        c = cat_a
                        if tpl == "tell me if {dev} is open":
                            c = "ContactSensor"   # 스위치는 열리고 닫히지 않는다
                        elif c in ("", "NotificationProvider", "Clock"):
                            # 조회 문형은 "is {dev} on" 처럼 단수를 받는다 — 복수 명사는 뺀다
                            cand = ["Switch", "Plug", "Fan", "Camera"] if act == "query" \
                                else ["Light", "Switch", "Plug", "Fan", "Camera"]
                            c = rng.choice([x for x in cand if x in sp["_cats"]]
                                           or ["Switch"])
                        got = refer(rng, sp, c, style)
                        if got is None:
                            body = tpl.replace("{dev}", "the " + (noun(c) or noun(cat_a)))
                            dev_ko = KO.NOUN_KO.get(c) or KO.NOUN_KO.get(cat_a) or c
                            targets, expect, match = [], "refuse", "none"
                        else:
                            ref, targets, expect, style, match, dev_ko = got
                            body = tpl.replace("{dev}", ref)
                    else:
                        # 기기를 안 대지만 무엇을 움직이는지는 정해져 있다
                        # ("난방 올려줘" = 그 공간 난방기). 공간 것 전부가 답.
                        body, expect, style = tpl, "execute", "none"
                        hit = [d for d, *_ in sp["_by_cat"].get(cat_a, [])]
                        targets, match = (hit, "all") if hit else ([], "none")
                    if act == "notify":
                        tsvc, expect = notify_target(sp, notify_act)
                        targets, match = [], ("all" if tsvc else "none")
                        style = "none"          # 알림은 기기를 지목하는 문장이 아니다
                    body = fill(rng, body, sp, act, cat_t)
                    aslots, act_place = dict(SLOTS[0]), LAST_PLACE[0]
                    if act == "query":
                        # 읽은 값을 어디로 말해 주나. 채널이 없으면 답할 길이 없다.
                        tsvc, ok_ch = notify_target(sp, "notify")
                        if ok_ch != "execute":
                            expect, why_force = "refuse", "no_channel"
                    if act == "query" and not targets:
                        targets, qwhy = query_targets(sp, body)
                        # 재실 여부는 기기가 아니라 공용 변수가 답이다.
                        # 지목할 기기는 없지만 답할 채널은 있으니 채점은 알림과 같다.
                        match = "all" if (targets or qwhy == "global") else "none"
                        if qwhy == "no_device":
                            expect, why_force = "refuse", "no_device"
                # 카탈로그에 그 일을 할 서비스가 아예 없다.
                # Clock 은 Delay 뿐이라 타이머를 걸거나 끄지 못하고,
                # FeedDispenser 는 Dispense 뿐이라 다음 급여를 건너뛰지 못한다.
                if act == "timer" or act_tpl == "skip the next feeding":
                    expect, why_force = "refuse", "no_service"
                if plan == "refuse" and not use_vague and act != "notify":
                    expect = "refuse"
                if expect == "refuse":
                    targets, tsvc, match = [], [], "none"
                # 언제. 앞자리("At sunset, turn on ...")는 담백한 말투에서만 자연스럽다.

                raw_t = ""
                ti = (k % len(T.TONE) if attempt == 0
                      else rng.randrange(len(T.TONE)))
                if use_logic:
                    lp = logic_pool(T.LOGIC_HARD if use_hard else T.LOGIC_SOFT,
                                    r["mode"], trig_kind, cat_t, act, body)
                    di, frame = lp[k % len(lp)] if attempt == 0 else rng.choice(lp)
                    cond_text = nonhome(rng.choice(T.COND), sp)
                    lslots = {"n": rng.choice([5, 10, 15, 20, 30]),
                              "m": rng.choice([2, 3, 4, 5, 6])}
                    core = (frame.replace("{a}", body)
                            .replace("{cond}", cond_text)
                            .replace("{n}", str(lslots["n"]))
                            .replace("{m}", str(lslots["m"])))
                    if r["mode"] != "now" and di not in ("D9", "D10", "D13"):
                        tp = trig_pool(trig_kind, cat_t)
                        if di == "D11":     # 견주려면 숫자를 읽어야 한다
                            tp = [t for t in tp if IR.reads_number(t)] or tp
                        elif di == "D12":   # 세려면 사건이어야 한다
                            tp = [t for t in tp if IR.trig_reads(t)] or tp
                        # 주기 문형에 주기 시간절을 또 붙이면 주기가 두 번 적힌다
                        # ("Every 30 minutes, check every 20 minutes and ...")
                        if "every {n} minutes" in frame:
                            tp = [t for t in tp if t != "every {n} minutes"] or tp
                        raw_t = nonhome(
                            tp[k % len(tp)] if attempt == 0 else rng.choice(tp), sp)
                        core = f"{fill(rng, raw_t, sp, act, cat_t)}, {core}"
                        tslots, trig_place = dict(SLOTS[0]), LAST_PLACE[0]
                    dcode = di
                elif r["mode"] == "now":
                    core = body
                else:
                    tp = trig_pool(trig_kind, cat_t)
                    raw_t = nonhome(
                        tp[k % len(tp)] if attempt == 0 else rng.choice(tp), sp)
                    tt = fill(rng, raw_t, sp, act, cat_t)
                    tslots, trig_place = dict(SLOTS[0]), LAST_PLACE[0]
                    front = (ti in (0, 5) and k % 3 == 0)
                    # 본문이 이미 "when" 을 쓰고 있으면 뒤에 시간절을 또 붙일 수 없다
                    # ("I want to know when it changes when the wash cycle ends")
                    if re.search(r"\bwhen\b", body, re.I):
                        front = True
                    core = f"{tt}, {body}" if front else f"{body} {tt}"
                # 말투는 완성된 문장으로 판정한다. 명령문이 아니면 담백하게만 쓴다.
                imperative = not is_state and not re.match(
                    r"(what|is |are |how |who |it |i |if |once |wait |give |keep |"
                    r"check |repeat |compare |count |after |every |while |until |when |"
                    r"at |on |in |as |with |around |before |during |next |\d|"
                    r"the moment|right |the air|the floor|nobody)",
                    core, re.I)
                if not imperative:
                    ti = 0 if rng.random() < 0.5 else 5
                else:
                    ti = k % len(T.TONE) if attempt == 0 else rng.randrange(len(T.TONE))
                tname = T.TONE[ti][0]
                tname, sent = tone(rng, core, ti)
                # 같은 재료로 한국어 문장을 따로 만든다 (korean.py). 번역이 아니다.
                sent_ko = KO.sentence_ko(
                    act_tpl=act_tpl, vague_tpl=vague_tpl,
                    dev_ko=dev_ko,
                    aslots=aslots, act_place=act_place, sensor_cat=cat_t,
                    trig_tpl=raw_t, tslots=(tslots if raw_t else {}),
                    trig_place=trig_place, dev_t_ko=DEV_T_KO[0],
                    frame=(frame if use_logic else ""), cond_text=cond_text,
                    lslots=lslots, tone=tname) or ""
                # 실행이라 해놓고 그 공간에 기기가 없으면 다시 뽑는다
                tier_now = TIER[dcode if use_logic else d_code(r["mode"], raw_t)]
                ok = not (expect == "execute" and cat_a and cat_a not in sp["_cats"])
                if sec_dead:
                    ok = False      # 움직임 센서가 있는 공간으로 다시 뽑는다
                if use_vague and tier_now in ("T3", "T4"):
                    ok = False      # 의도만 말하는 문장에 반복·누적을 얹지 않는다
                # 바깥 정보 때문에 거절하려면 문장에 그 조건이 실제로 있어야 한다
                if (expect == "refuse" and not why_force
                        and cat_a and cat_a in sp["_cats"]
                        and act != "notify"
                        and (not raw_t or cat_t not in CONTEXT)):
                    ok = False
                if ok and sent.lower() not in seen:
                    break
            seen.add(sent.lower())
            # 정답 IR. 실행일 때만 만든다 — 되묻기·거절은 프로그램이 아니라 판정이 답이다.
            ir_gt = ""
            if expect == "execute":
                obj = IR.make_ir(
                    act=act, act_tpl=act_tpl, act_cat=win_cat, vague_tpl=vague_tpl,
                    trig_tpl=raw_t, cat_t=cat_t, trig_kind=trig_kind,
                    frame=(frame if use_logic else ""), cond_text=cond_text,
                    slots=aslots, tslots=tslots, lslots=lslots,
                    kind=sp["kind"], occupancy=sp.get("occupancy"),
                    notify_svc=(tsvc[0] if tsvc else ""))
                if obj:
                    ir_gt = json.dumps(obj, ensure_ascii=False)
            # 재실을 감지할 방법이 없는 공간(전역 변수도 재실 센서도 폰도 없다)에서
            # 재실을 묻는 명령은 답할 길이 없다 — 거절이다.
            # 층이 주체 목록을 훑다 빈손으로 끝나므로 결정적으로 알아챈다.
            if ir_gt and sp.get("occupancy") == "none" and "GlobalVariable" in ir_gt:
                expect, why_force, ir_gt = "refuse", "no_occupancy", ""
                targets, tsvc, match = [], [], "none"
            stats[expect] += 1
            parts.append({
                "id": f"G{len(rows)+1:05d}",
                "trig": raw_t or "",                      # 시간절 틀
                "act": vague_tpl or act_tpl or "",        # 동작절(또는 의도) 틀
                "is_vague": bool(vague_tpl),
                "frame": (frame if use_logic else ""),    # 로직 문형
                "cond": (cond_text if use_logic else ""), # 조건절 문구
                "tone": tname,
            })
            rows.append(dict(
                id=f"G{len(rows)+1:05d}", space_id=sid, kind=sp["kind"], command=sent,
                command_ko=sent_ko,
                mode=r["mode"], trig=trig_kind, act=act, dev_trig=cat_t, dev_act=cat_a,
                ref=("vague" if use_vague else style), tone=tname, expect=expect,
                d=(dcode if use_logic else d_code(r["mode"], raw_t)),
                why=(why_force
                     or ("no_channel" if (expect == "refuse" and act == "notify")
                         else "no_device" if (expect == "refuse" and cat_a
                                              and cat_a not in sp["_cats"])
                         else "no_context" if expect == "refuse" else "")),
                tier=TIER[dcode if use_logic else d_code(r["mode"], raw_t)],
                b1=b1_of(act, sent),
                b3=len(set(acts)), context=CONTEXT.get(cat_t, "none"),
                targets=" ".join(targets), n_target=len(targets),
                target_svc=" ".join(tsvc), match=match, ir_gt=ir_gt))

    # 안 싣는 열 넷 — 다른 열에서 그대로 나오거나(kind ← space_id, n_target ← targets,
    # match ← expect) 안 쓴다(tone). rows 안에는 남아 있어 아래 검산이 그대로 쓴다.
    cols = ["id", "space_id", "command", "command_ko", "mode", "trig", "act",
            "dev_trig", "dev_act", "ref", "expect", "d", "tier", "b1", "b3",
            "context", "why", "targets", "target_svc", "ir_gt"]
    dst = os.path.join(HERE, "dataset_5k.csv")
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # 행마다 어느 틀을 썼는지 — 학습·시험을 **틀 종류로** 가르는 데 쓴다 (문장이 아니라 틀 단위)
    with open(os.path.join(HERE, "parts_5k.json"), "w", encoding="utf-8") as f:
        json.dump(parts, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"parts_5k.json — {len(parts)}행이 쓴 틀")

    bad = []
    CAT = json.load(open(os.path.join(os.path.dirname(HERE), "files",
                                      "service_list_ver3.1.0.json"), encoding="utf-8"))
    for x in rows:
        cats = S[x["space_id"]]["_cats"]
        c = ACT_CAT.get(x["act"], "")
        if x["expect"] == "refuse" and x["why"] == "no_device" and c and c in cats:
            bad.append(f"{x['id']} 거절인데 {c} 가 {x['space_id']} 에 있음")
        if x["expect"] == "refuse" and x["why"] == "no_context" \
                and x["dev_trig"] in S[x["space_id"]]["_cats"]:
            bad.append(f"{x['id']} 거절인데 {x['dev_trig']} 가 {x['space_id']} 에 있음")
        if x["expect"] == "execute" and x["ref"] in ("plain", "place", "nick", "all") \
                and c and c not in cats:
            bad.append(f"{x['id']} 실행인데 {c} 가 {x['space_id']} 에 없음")
        # 대상 검산
        t = x["targets"].split()
        devs = S[x["space_id"]]["devices"]
        if len(t) != x["n_target"] or len(set(t)) != len(t):
            bad.append(f"{x['id']} 대상 개수가 안 맞음")
        for d in t:
            if d not in devs:
                bad.append(f"{x['id']} 없는 기기 {d}")
        if any("." in d for d in t):
            bad.append(f"{x['id']} 기기 칸에 서비스가 들어감")
        if x["target_svc"] and "." not in x["target_svc"]:
            bad.append(f"{x['id']} 서비스 형식이 아님")
        if (x["expect"] == "ask") != (x["match"] == "ask"):
            bad.append(f"{x['id']} 되묻기와 채점 방식이 어긋남")
        if x["expect"] == "refuse" and (t or x["target_svc"]):
            bad.append(f"{x['id']} 거절인데 대상이 있음")
        if x["match"] == "all" and not t and not x["target_svc"]:
            bad.append(f"{x['id']} 전부 맞춰야 하는데 대상이 없음")
        if x["ref"] == "nick" and x["expect"] == "execute" and x["n_target"] != 1:
            bad.append(f"{x['id']} 별명으로 불렀는데 대상이 {x['n_target']}개")
        # 정답 IR 검산
        if x["expect"] == "execute" and not x["ir_gt"]:
            bad.append(f"{x['id']} 실행인데 정답 IR 이 없음")
        if x["expect"] != "execute" and x["ir_gt"]:
            bad.append(f"{x['id']} 실행이 아닌데 정답 IR 이 있음")
        if x["ir_gt"]:
            bad += IR.check_ir(json.loads(x["ir_gt"]), CAT, x["id"], cats)
            tgt = x["targets"].split()
            if tgt and x["match"] == "all":
                tc = set()
                for d in tgt:
                    tc |= set(S[x["space_id"]]["devices"][d]["category"])
                for t in re.findall(r'"target": "([^"]+)"', x["ir_gt"]):
                    c0 = t.split(".")[0]
                    if c0 not in tc and c0 not in ("Switch", "NotificationProvider",
                                                   "Speaker", "Display", "Clock",
                                                   "GlobalVariable"):
                        bad.append(f"{x['id']} 지목한 기기가 {c0} 서비스를 못 함")
    print(f"검산: 어긋난 판정 {len(bad)}건", bad[:5])
    print(f"dataset_5k.csv: {len(rows)}문장 / 서로 다른 문장 {len(seen)}")
    print("판정:", dict(stats))
    print("공간별 최소/최대:",
          min(collections.Counter(x['space_id'] for x in rows).values()),
          max(collections.Counter(x['space_id'] for x in rows).values()))
    mt = collections.Counter(x["match"] for x in rows)
    nt = [x["n_target"] for x in rows if x["n_target"]]
    print("채점 방식: 전부일치 %d / 되묻기 %d / 대상없음 %d, 기기 %d대 지목(한 문장 최대 %d), 서비스 %d건"
          % (mt["all"], mt["ask"], mt["none"], sum(nt), max(nt),
             sum(1 for x in rows if x["target_svc"])))
    print("기기 지목:", dict(collections.Counter(x["ref"] for x in rows)))
    ops = collections.Counter()
    for x in rows:
        if x["ir_gt"]:
            for n in IR._walk(json.loads(x["ir_gt"])["timeline"]):
                ops[n["op"]] += 1
    print("정답 IR:", sum(1 for x in rows if x["ir_gt"]), "개 /",
          "op", dict(ops.most_common()))
    tc = collections.Counter(x["tier"] for x in rows)
    print("난이도:", " ".join(f"{k} {TIER_NAME[k]} {tc[k]}({tc[k]/len(rows):.1%})"
                            for k in sorted(tc)))
    print("D축:", {k: v for k, v in sorted(
        collections.Counter(x["d"] for x in rows).items())})
    print("B1축:", dict(collections.Counter(x["b1"] for x in rows)))
    print("바깥 정보:", dict(collections.Counter(x["context"] for x in rows)))
    print("\n표본:")
    for x in rows[::311][:16]:
        print(f"  [{x['expect']:7s}|{x['space_id']:8s}] {x['command']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
