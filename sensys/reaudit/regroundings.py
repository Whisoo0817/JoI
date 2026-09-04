"""382 재감사: 사라진 7스킬(2.0.4→2.0.5) 참조를 v2.0.7 카탈로그로 치환.

가족별 규칙:
  A. 문 상태 읽기 전용   → ContactSensor.Contact (closed=true / open=false)
  B. 문 액션(+읽기)      → DoorLock(잠금 언어로 NL 수정) / 창문·밸브로 재조준
  C. Safe               → DoorLock (금고의 잠금장치; NL 무변경)
  D. RainSensor.Rain    → WeatherProvider.Weather == "rain" (NL 무변경)
  E. 주방가전(모드/시간) → 생존 모드 기기로 명령 재작성 (NL 영/한 모두)
  F. 미끼(인벤토리만)    → 카테고리 교체 (충돌 회피)
추가: 함수 오용 4건 (C17_009, C08_038, C03_029, C03_002).

실행: joi 디렉토리에서  python3 scratchpad/regroundings.py
"""
import csv
import json
import re
import sys

PATH = "dataset.csv"
GONE = {"Door", "Safe", "RainSensor", "Oven", "RiceCooker", "Dishwasher",
        "LaundryDryer"}


def key_of(r):
    return f'{r["category_v2"]}_{int(float(r["index"])):03d}'


# ---------- 공용 문자열 치환 ----------

def sub_cond(c):
    """조건 문자열 안의 사라진 서비스 읽기를 신 카탈로그로."""
    c = c.replace('Door.DoorState == "open" or Door.DoorState == "opening"',
                  'ContactSensor.Contact == false')
    c = c.replace('Door.DoorState == "open"', 'ContactSensor.Contact == false')
    c = c.replace('Door.DoorState == "closed"', 'ContactSensor.Contact == true')
    c = c.replace('Safe.SafeState == "closed"', 'DoorLock.DoorLockState == "closed"')
    c = c.replace('Safe.SafeState == "open"', 'DoorLock.DoorLockState == "open"')
    c = c.replace('Safe.SafeState != "locked"', 'DoorLock.DoorLockState != "closed"')
    c = c.replace('RainSensor.Rain == true', 'WeatherProvider.Weather == "rain"')
    c = c.replace('RainSensor.Rain == false', 'WeatherProvider.Weather != "rain"')
    return c


def walk_subst(steps, call_map, cond_fn):
    """IR 트리 전체에 call 표적 치환 + 조건 문자열 치환."""
    for s in steps:
        if not isinstance(s, dict):
            continue
        if s.get("op") == "call" and s.get("target") in call_map:
            new = call_map[s["target"]]
            if isinstance(new, tuple):
                s["target"], s["args"] = new[0], dict(new[1])
            else:
                s["target"] = new
        for f in ("cond", "until", "for"):
            if s.get(f):
                s[f] = cond_fn(s[f])
        for v in s.values():
            if isinstance(v, list):
                walk_subst(v, call_map, cond_fn)


DOOR_CALLS = {"Door.Open": "DoorLock.Unlock", "Door.Close": "DoorLock.Lock",
              "Safe.Lock": "DoorLock.Lock", "Safe.Unlock": "DoorLock.Unlock"}


# ---------- 기기 인벤토리 치환 ----------

DISTRACTOR_MAP = {"Door": "DoorLock", "Safe": "DoorLock", "Oven": "Fan",
                  "RiceCooker": "Humidifier", "LaundryDryer": "Fan",
                  "Dishwasher": "Fan", "RainSensor": "WeatherProvider"}
FALLBACKS = ["Fan", "Humidifier", "AirPurifier", "Dehumidifier", "Plug",
             "Printer", "Charger"]


def swap_dev(devs, old_cat, new_cat, keep_old_tag=False):
    """카테고리 old→new 교체. 태그의 old도 new로 (keep_old_tag면 old 태그 유지+new 추가)."""
    out = {}
    for did, d in devs.items():
        if old_cat in d.get("category", []):
            d = dict(d)
            d["category"] = [new_cat if c == old_cat else c for c in d["category"]]
            tags = list(d.get("tags", []))
            if keep_old_tag:
                tags = tags + [new_cat] if new_cat not in tags else tags
            else:
                tags = [new_cat if t == old_cat else t for t in tags]
            d["tags"] = tags
            did = did.replace(old_cat, new_cat)
        out[did] = d
    return out


def replace_rain_devs(devs):
    """RainSensor 기기 → WeatherProvider 하나로 (이미 있으면 그냥 제거)."""
    has_wp = any("WeatherProvider" in d.get("category", []) for d in devs.values())
    out, added = {}, False
    for did, d in devs.items():
        if "RainSensor" in d.get("category", []):
            if not has_wp and not added:
                out["Home_WeatherProvider"] = {"category": ["WeatherProvider"],
                                               "tags": ["WeatherProvider"]}
                added = True
            continue
        out[did] = d
    return out


# ---------- 행별 처리 ----------

def load_rows():
    with open(PATH, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        return list(rdr), rdr.fieldnames


def gone_in(r):
    ir = r["ir_gt"]
    refs = {g for g in GONE if g + "." in ir}
    devs = json.loads(r["connected_devices"]) if r["connected_devices"] else {}
    cats = {c for d in devs.values() for c in d.get("category", []) if c in GONE}
    return refs, cats, devs


# 수기 명세: key → dict(eng, kor, ir(선택: 함수로), dev(함수))
def ir_edit(call_map=None, cond=True):
    def f(ir):
        walk_subst(ir["timeline"], call_map or DOOR_CALLS,
                   sub_cond if cond else (lambda c: c))
        return ir
    return f


MANUAL = {}

def man(key, eng=None, kor=None, ir_fn=None, dev_fn=None):
    MANUAL[key] = {"eng": eng, "kor": kor, "ir": ir_fn, "dev": dev_fn}


# --- B군: 문 액션 → DoorLock (NL 잠금 언어) ---
man("C01_021", "Lock the door.", "문을 잠가줘.",
    ir_edit(), lambda d: swap_dev(d, "Door", "DoorLock"))
man("C03_022",
    "If the temperature on the airquality sensor is below 20 degrees, lock the door.",
    "회의실 온도가 20도 미만이면, 회의실 문을 잠가줘.",
    ir_edit(), lambda d: swap_dev(d, "Door", "DoorLock"))
man("C09_006",
    "If the dust level concentration is 2000ppm or above, lock the door and close the valve after 4 hours.",
    "외부 미세먼지 농도가 2000 이상이면 문을 잠그고 4시간 뒤에 밸브를 잠궈줘.",
    ir_edit(), lambda d: swap_dev(d, "Door", "DoorLock"))
man("C09_018",
    "Lock the meeting room door. After 3 seconds take a picture with the meeting room camera.",
    "회의실 문을 잠그고 3초 뒤에 회의실 카메라로 촬영해줘.",
    ir_edit(), lambda d: swap_dev(d, "Door", "DoorLock"))
man("C15_013", "Every 11 PM, lock all doors with even tags.",
    "밤 11시에 짝수 태그가 붙은 모든 문을 잠가줘.",
    ir_edit(), lambda d: swap_dev(d, "Door", "DoorLock"))
man("C18_010",
    "At midnight, lock the door and check the light every hour until 6 AM; if the brightness is greater than 30, lower it to 10.",
    "자정이 되면 문을 잠그고, 오전 6시까지 한 시간마다 조명을 체크해서 밝기가 30보다 크면 10으로 낮춰줘.",
    ir_edit(), lambda d: swap_dev(d, "Door", "DoorLock"))
man("C08_034", "Whenever it rains, close all windows and lock all doors.",
    "비가 올때마다, 모든 창문을 닫고 모든 문을 잠가줘",
    ir_edit(),
    lambda d: replace_rain_devs(swap_dev(d, "Door", "DoorLock")))
man("C22_009", "Every 3 minutes, unlock the garage door. Repeat 3 times.",
    "3분마다 차고 문 잠금을 해제해줘. 3번만 반복.",
    ir_edit(), lambda d: swap_dev(d, "Door", "DoorLock"))
man("C05_009",
    "If the fine dust level is 150 or higher and the door is unlocked, lock the door and set the air purifier to high.",
    "미세먼지 농도가 150 이상이고 문이 잠겨 있지 않으면, 문을 잠그고 공기청정기를 강풍으로 작동시켜줘.",
    ir_edit({"Door.Close": "DoorLock.Lock"}, cond=False),
    lambda d: swap_dev(d, "Door", "DoorLock"))


def _c05_009_cond(ir):
    walk_subst(ir["timeline"], {"Door.Close": "DoorLock.Lock"},
               lambda c: c.replace('Door.DoorState == "open"',
                                   'DoorLock.DoorLockState == "open"'))
    return ir
MANUAL["C05_009"]["ir"] = _c05_009_cond

# C05_020: 욕실 문 → 욕실 창문 (WindowCovering, 상태는 CurrentPosition)
def _c05_020_ir(ir):
    walk_subst(ir["timeline"], {"Door.Open": "WindowCovering.UpOrOpen"},
               lambda c: c.replace('Door.DoorState == "closed"',
                                   'WindowCovering.CurrentPosition == 0'))
    return ir
def _c05_020_dev(d):
    d = dict(d)
    d.pop("Bathroom_Door", None); d.pop("Bedroom_Door", None)
    d["Bathroom_Window"] = {"category": ["WindowCovering"],
                            "tags": ["Bathroom", "Window", "WindowCovering"]}
    d["Bedroom_Window"] = {"category": ["WindowCovering"],
                           "tags": ["Bedroom", "Window", "WindowCovering"]}
    return d
man("C05_020",
    "If the bathroom humidity is 85% or higher and the bathroom window is closed, turn on the light and open the window.",
    "욕실 습도가 85% 이상이고 욕실 창문이 닫혀 있으면, 조명을 켜고 창문을 열어줘.",
    _c05_020_ir, _c05_020_dev)

# C05_021: 도어락만 남기고 Door.Open 제거
def _c05_021_ir(ir):
    then = ir["timeline"][1]["then"]
    ir["timeline"][1]["then"] = [s for s in then
                                 if s.get("target") != "Door.Open"]
    return ir
def _c05_021_dev(d):
    return {k: v for k, v in d.items()
            if "Door" not in v.get("category", [])}
man("C05_021",
    "If the face ID 'family' is recognized at the entrance and the door lock is locked , unlock the door lock.",
    '현관에서 인식된 얼굴 ID가 "가족"이고 도어락이 잠겨 있으면, 도어락을 풀어줘.',
    _c05_021_ir, _c05_021_dev)

# C10_004: 문 → 창문 (환기 의도), 비 → WeatherProvider
def _c10_004_ir(ir):
    walk_subst(ir["timeline"],
               {"Door.Close": "WindowCovering.DownOrClose",
                "Door.Open": "WindowCovering.UpOrOpen"}, sub_cond)
    return ir
def _c10_004_dev(d):
    d = replace_rain_devs(d)
    d.pop("Front_Door", None); d.pop("Back_Door", None)
    d["Front_Window"] = {"category": ["WindowCovering"],
                         "tags": ["Front", "Window", "WindowCovering"]}
    d["Back_Window"] = {"category": ["WindowCovering"],
                        "tags": ["Back", "Window", "WindowCovering"]}
    return d
man("C10_004",
    "When it rains, close the window and check again after 1 hour; if it's not raining then, open the window again.",
    "비가 오면 창문을 닫고 1시간 뒤에 체크해서 비가 안오면 창문을 다시 열어줘.",
    _c10_004_ir, _c10_004_dev)

# C13_001: 문 여닫기 반복 → 수도 밸브
def _c13_001_ir(ir):
    walk_subst(ir["timeline"], {"Door.Open": "Valve.Open",
                                "Door.Close": "Valve.Close"}, lambda c: c)
    return ir
man("C13_001", "Every hour, repeat opening and closing the water valve.",
    "1시간마다 수도 밸브를 열었다 잠갔다 반복해줘.",
    _c13_001_ir,
    lambda d: {"Kitchen_Valve": {"category": ["Valve"], "tags": ["Kitchen", "Valve"]},
               "Basement_Valve": {"category": ["Valve"], "tags": ["Basement", "Valve"]}})

# C12_003: 문 읽기 → ContactSensor, 금고 → DoorLock
man("C12_003", None, None, ir_edit({}, cond=True),
    lambda d: swap_dev(swap_dev(d, "Door", "ContactSensor"),
                       "Safe", "DoorLock", keep_old_tag=True))

# --- E군: 주방가전 재작성 ---
def set_timeline(*steps):
    def f(ir):
        ir["timeline"] = [{"op": "start_at", "anchor": "now"}] + list(steps)
        return ir
    return f

man("C01_001", "Switch the dehumidifier to drying mode.", "제습기를 건조 모드로 설정해줘.",
    set_timeline({"op": "call", "target": "Dehumidifier.SetDehumidifierMode",
                  "args": {"Mode": "drying"}}),
    lambda d: {"Kitchen_Dehumidifier": {"category": ["Dehumidifier"],
                                        "tags": ["Kitchen", "Dehumidifier"]},
               "Utility_Dehumidifier": {"category": ["Dehumidifier"],
                                        "tags": ["Utility", "Dehumidifier"]}})
man("C01_002", "Record a 5-minute video with the camera.", "카메라로 5분짜리 영상을 녹화해줘.",
    set_timeline({"op": "call", "target": "Camera.CaptureVideo",
                  "args": {"Duration": 300.0}}),
    lambda d: {"Entrance_Camera": {"category": ["Camera"],
                                   "tags": ["Entrance", "Camera"]},
               "Garage_Camera": {"category": ["Camera"],
                                 "tags": ["Garage", "Camera"]}})
man("C01_003", "Set the blinds to 50 percent.", "블라인드를 50퍼센트로 맞춰줘.",
    set_timeline({"op": "call", "target": "WindowCovering.SetLevel",
                  "args": {"Level": 50}}),
    lambda d: {"Living_Blind": {"category": ["WindowCovering"],
                                "tags": ["Living", "Blind", "WindowCovering"]},
               "Bedroom_Blind": {"category": ["WindowCovering"],
                                 "tags": ["Bedroom", "Blind", "WindowCovering"]}})
man("C03_003",
    "If the air conditioner is in cool mode, lower the target temperature by 2 degrees.",
    "에어컨이 냉방 모드이면, 설정 온도를 2도 낮춰줘.",
    set_timeline({"op": "if", "cond": 'AirConditioner.AirConditionerMode == "cool"',
                  "then": [{"op": "call",
                            "target": "AirConditioner.SetTargetTemperature",
                            "args": {"Temperature":
                                     "$AirConditioner.TargetTemperature - 2"}}],
                  "else": []}),
    lambda d: {"Living_AC": {"category": ["AirConditioner", "Switch"],
                             "tags": ["Living", "AirConditioner", "Switch"]},
               "Bedroom_AC": {"category": ["AirConditioner", "Switch"],
                              "tags": ["Bedroom", "AirConditioner", "Switch"]}})
man("C03_004",
    "If the robot vacuum cleaner is in manual mode, switch it to auto mode.",
    "로봇청소기가 수동 모드이면, 자동 모드로 변경해줘.",
    set_timeline({"op": "if",
                  "cond": 'RobotVacuumCleaner.RobotVacuumCleanerCleaningMode == "manual"',
                  "then": [{"op": "call",
                            "target": "RobotVacuumCleaner.SetRobotVacuumCleanerCleaningMode",
                            "args": {"Mode": "auto"}}],
                  "else": []}),
    lambda d: {"Living_RVC": {"category": ["RobotVacuumCleaner"],
                              "tags": ["Living", "RobotVacuumCleaner"]},
               "Kitchen_RVC": {"category": ["RobotVacuumCleaner"],
                               "tags": ["Kitchen", "RobotVacuumCleaner"]}})
man("C03_009",
    "If the air purifier is in quiet mode, switch it to high speed mode.",
    "공기청정기가 저소음 모드이면, 강풍 모드로 바꿔줘.",
    set_timeline({"op": "if", "cond": 'AirPurifier.AirPurifierMode == "quiet"',
                  "then": [{"op": "call", "target": "AirPurifier.SetAirPurifierMode",
                            "args": {"Mode": "high"}}],
                  "else": []}),
    lambda d: {"Living_AP": {"category": ["AirPurifier"],
                             "tags": ["Living", "AirPurifier"]},
               "Bedroom_AP": {"category": ["AirPurifier"],
                              "tags": ["Bedroom", "AirPurifier"]}})
man("C07_020",
    "When the laundry room fan's speed drops to 5 or below, announce through the living room speaker that the fan has slowed down.",
    "세탁실 환풍기 속도가 5 이하가 되면 거실 스피커로 환풍기가 느려졌다고 알려줘.",
    None,  # 아래 별도 처리 (speak 텍스트도 교체)
    lambda d: swap_dev(d, "LaundryDryer", "Fan"))
def _c07_020_ir(ir):
    ir["timeline"][1]["cond"] = "Fan.Speed <= 5"
    ir["timeline"][2]["args"]["Text"] = "The fan has slowed down"
    return ir
MANUAL["C07_020"]["ir"] = _c07_020_ir

man("C12_008",
    "When the fan speed becomes 0, say 'Please check the fan' through the speaker every 10 minutes thereafter.",
    "환풍기 속도가 0이 되면, 그 이후로 10분마다 '환풍기를 확인하세요'라고 스피커로 말해줘.",
    None, lambda d: swap_dev(d, "LaundryDryer", "Fan"))
def _c12_008_ir(ir):
    ir["timeline"][1]["cond"] = "Fan.Speed == 0"
    ir["timeline"][2]["body"][0]["args"]["Text"] = "Please check the fan"
    return ir
MANUAL["C12_008"]["ir"] = _c12_008_ir

man("C09_005",
    "Set the air conditioner to cool mode and change it to auto mode after 10 minutes.",
    "에어컨을 냉방 모드로 설정하고 10분 뒤에 자동 모드로 바꿔줘.",
    set_timeline({"op": "call", "target": "AirConditioner.SetAirConditionerMode",
                  "args": {"Mode": "cool"}},
                 {"op": "delay", "duration": "10 MIN"},
                 {"op": "call", "target": "AirConditioner.SetAirConditionerMode",
                  "args": {"Mode": "auto"}}),
    lambda d: swap_dev(d, "Oven", "AirConditioner"))
man("C10_002",
    "When the fan enters high mode, switch it to low mode after 3 seconds.",
    "선풍기가 강풍 모드가 되면 3초 뒤에 약풍 모드로 바꿔줘.",
    None, lambda d: swap_dev(d, "Oven", "Fan"))
def _c10_002_ir(ir):
    walk_subst(ir["timeline"],
               {"Oven.SetOvenMode": ("Fan.SetFanMode", {"Mode": "low"})},
               lambda c: c.replace('Oven.OvenMode == "heating"',
                                   'Fan.FanMode == "high"'))
    return ir
MANUAL["C10_002"]["ir"] = _c10_002_ir

man("C05_011",
    "If the air conditioner is heating and no one is being detected, change the mode to auto and notify that the mode has been changed to auto.",
    "에어컨이 난방 중이고 아무도 없으면, 에어컨을 자동 모드로 변경하고 스피커로 자동 모드로 변경했다고 알려줘.",
    None, lambda d: swap_dev(d, "Oven", "AirConditioner"))
def _c05_011_ir(ir):
    s = ir["timeline"][1]
    s["cond"] = ('AirConditioner.AirConditionerMode == "heat" and '
                 'PresenceSensor.Presence == false')
    s["then"][0] = {"op": "call", "target": "AirConditioner.SetAirConditionerMode",
                    "args": {"Mode": "auto"}}
    s["then"][1]["args"]["Text"] = \
        "The air conditioner mode has been changed to auto."
    return ir
MANUAL["C05_011"]["ir"] = _c05_011_ir

man("C15_004", "Set the humidifier to auto mode every morning at 7 AM.",
    "매일 아침 7시에 가습기를 자동 모드로 설정해줘.",
    None, lambda d: swap_dev(d, "RiceCooker", "Humidifier"))
def _c15_004_ir(ir):
    walk_subst(ir["timeline"],
               {"RiceCooker.SetRiceCookerMode": ("Humidifier.SetHumidifierMode",
                                                 {"Mode": "auto"})}, lambda c: c)
    return ir
MANUAL["C15_004"]["ir"] = _c15_004_ir

man("C15_007", "On weekdays at 7 AM, start the robot vacuum cleaner in auto mode.",
    "평일 오전 7시에 로봇청소기를 자동 모드로 작동해줘.",
    None, lambda d: swap_dev(d, "RiceCooker", "RobotVacuumCleaner"))
def _c15_007_ir(ir):
    walk_subst(ir["timeline"],
               {"RiceCooker.SetRiceCookerMode":
                ("RobotVacuumCleaner.SetRobotVacuumCleanerCleaningMode",
                 {"Mode": "auto"})}, lambda c: c)
    return ir
MANUAL["C15_007"]["ir"] = _c15_007_ir

# --- 함수 오용 4건 ---
def _c17_009_ir(ir):
    body = ir["timeline"][1]["body"]
    ir["timeline"][1]["body"] = [s for s in body
                                 if s.get("target") != "DoorLock.DoorLockState"]
    return ir
man("C17_009", None, None, _c17_009_ir, None)

def _stream_ir(ir):
    walk_subst(ir["timeline"], {"Camera.StartStream": "Camera.StartRecording"},
               lambda c: c)
    return ir
man("C08_038",
    "Whenever the kitchen leak sensor detects a leak, start recording with the kitchen camera.",
    "주방의 누수 센서가 감지될 때마다 주방 카메라로 녹화를 시작해줘.",
    _stream_ir, None)
man("C03_029",
    "If the face recognized at the entrance is 'visitor', start recording with the entrance camera.",
    '현관에서 인식된 얼굴이 "방문자"이면, 현관 카메라로 녹화를 시작해줘.',
    _stream_ir, None)

def _c03_002_ir(ir):
    tl = ir["timeline"]
    cond_step = tl[1]
    tl[1:2] = [{"op": "call", "target": "CloudServiceProvider.IsAvailable",
                "args": {}, "var": "IsAvailable"}, cond_step]
    cond_step["cond"] = "$IsAvailable == true"
    return ir
man("C03_002", None, None, _c03_002_ir, None)


# ---------- 실행 ----------

def main():
    rows, fields = load_rows()
    changed = []
    for r in rows:
        key = key_of(r)
        refs, cats, devs = gone_in(r)
        spec = MANUAL.get(key)
        if not spec and not refs and not cats:
            continue

        ir = json.loads(r["ir_gt"])
        if spec:
            if spec["eng"]: r["command_eng"] = spec["eng"]
            if spec["kor"]: r["command_kor"] = spec["kor"]
            if spec["ir"]: ir = spec["ir"](ir)
            if spec["dev"]: devs = spec["dev"](devs)
        # 남은 기계적 치환 (A/C/D군 읽기·호출 + F군 미끼)
        walk_subst(ir["timeline"], DOOR_CALLS, sub_cond)
        ir_txt = json.dumps(ir, ensure_ascii=False)

        # 기기: 읽기 전용 Door → ContactSensor (IR이 Contact를 읽는 경우)
        if "ContactSensor.Contact" in ir_txt and \
                any("Door" in d.get("category", []) for d in devs.values()):
            devs = swap_dev(devs, "Door", "ContactSensor", keep_old_tag=True)
            devs = {(k.replace("_Door", "_DoorContact") if "_Door" in k else k): v
                    for k, v in devs.items()}
        if "RainSensor" in json.dumps(list(devs.values())):
            devs = replace_rain_devs(devs)
        # Safe 기기 (IR이 DoorLock을 쓰게 된 경우)
        if any("Safe" in d.get("category", []) for d in devs.values()):
            devs = swap_dev(devs, "Safe", "DoorLock", keep_old_tag=True)
        # 나머지 미끼 (IR이 안 쓰는 사라진 카테고리)
        for cat in sorted({c for d in devs.values()
                           for c in d.get("category", []) if c in GONE}):
            new = DISTRACTOR_MAP[cat]
            present = {c for d in devs.values() for c in d.get("category", [])}
            if new in present:
                new = next(x for x in FALLBACKS if x not in present)
            # NL이 그 기기를 언급하면 미끼가 아님 → 중단하고 알림
            kw = {"Door": "door", "Safe": "safe", "Oven": "oven",
                  "RiceCooker": "rice cooker", "LaundryDryer": "dryer",
                  "Dishwasher": "dishwasher", "RainSensor": "rain"}[cat]
            if kw in r["command_eng"].lower() and cat not in ("Door", "Safe"):
                print(f"!! {key}: NL이 '{kw}' 언급 — 수기 확인 필요")
            devs = swap_dev(devs, cat, new)

        r["ir_gt"] = ir_txt
        r["connected_devices"] = json.dumps(devs, ensure_ascii=False)
        changed.append(key)

    with open(PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"수정 {len(changed)}행:", " ".join(changed))


if __name__ == "__main__":
    main()
