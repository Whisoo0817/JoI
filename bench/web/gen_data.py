#!/usr/bin/env python3
"""웹 화면이 읽을 JSON 을 뽑는다 — spaces.json + dataset_5k.csv + effects.py → public/data/

  python bench/web/gen_data.py            # HOME06 만
  python bench/web/gen_data.py --all      # 40 공간 전부

내는 것
  public/data/spaces.json        공간 목록 (고르는 칸용)
  public/data/space.<ID>.json    방 네모 + 기기 위치 + 시스템 기기
  public/data/cmds.<ID>.json     그 공간의 명령어와 정답
  public/data/effects.json       서비스 → 실세계 효과 (애니메이션 표)

방 배치
  spaces.json 에는 좌표가 없다. 방 이름만 있다. 그래서 여기서 네모를 정한다.
  손으로 적은 것이 LAYOUT 에 있으면 그것을 쓰고, 없으면 기기 수에 맞춰 격자로 깐다.
  기기는 방 네모 안에 다시 격자로 놓는다.
"""
import argparse
import collections
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
OUT = os.path.join(HERE, "public", "data")
sys.path.insert(0, BENCH)

csv.field_size_limit(10 ** 7)

# ── 방 이름 한국어 ─────────────────────────────────────────────────────
ROOM_KO = {
    "LivingRoom": "거실", "Bedroom": "침실", "Kitchen": "주방", "Bathroom": "욕실",
    "Study": "서재", "Hallway": "복도", "Entrance": "현관", "BackDoor": "뒷문",
    "Garage": "차고", "Garden": "마당", "Outdoor": "실외", "Utility": "다용도실",
    "Balcony": "발코니", "BabyRoom": "아기방", "Pantry": "팬트리", "Storage": "창고",
    "Stairs": "계단", "RestRoom": "화장실", "Room": "방", "RoomA": "A방",
    "RoomB": "B방", "RoomC": "C방", "OpenSpace": "업무공간", "MeetingRoom": "회의실",
    "LabRoom": "실험실", "TestBed": "테스트베드", "ColdRoom": "저온실",
    "ProcessRoom": "공정실", "MachineShop": "기계실", "Line": "생산라인",
    "Warehouse": "창고", "Dock": "하역장", "BoilerRoom": "보일러실",
    "PumpRoom": "펌프실", "TankYard": "탱크야드", "ColdStorage": "냉장창고",
    "Greenhouse": "온실", "GrowRoom": "재배실", "Barn": "축사", "Field": "밭",
    "System": "시스템",
}

# ── 기기 종류 한국어 + 그림글자 ────────────────────────────────────────
# 그림글자는 눈으로 바로 알아보라고 쓴다. 없으면 첫 글자를 쓴다.
CAT = {
    "Light":              ("조명", "💡"),
    "GrowLight":          ("식물등", "🌱"),
    "StatusLight":        ("표시등", "🚦"),
    "Switch":             ("스위치", "🔘"),
    "Plug":               ("플러그", "🔌"),
    "Fan":                ("선풍기", "🌀"),
    "AirConditioner":     ("에어컨", "❄️"),
    "Thermostat":         ("온도조절기", "🌡️"),
    "Heater":             ("난방기", "🔥"),
    "ElectricBlanket":    ("전기장판", "🛏️"),
    "Humidifier":         ("가습기", "💧"),
    "Dehumidifier":       ("제습기", "🏜️"),
    "AirPurifier":        ("공기청정기", "🍃"),
    "Ventilator":         ("환풍기", "🌬️"),
    "RangeHood":          ("레인지후드", "🍳"),
    "Speaker":            ("스피커", "🔊"),
    "Television":         ("TV", "📺"),
    "Projector":          ("프로젝터", "📽️"),
    "Display":            ("디스플레이", "🖥️"),
    "WindowCovering":     ("블라인드", "🪟"),
    "DoorLock":           ("도어락", "🔒"),
    "GarageDoor":         ("차고문", "🚪"),
    "Doorbell":           ("초인종", "🔔"),
    "Siren":              ("사이렌", "📢"),
    "Camera":             ("카메라", "📷"),
    "MotionSensor":       ("동작감지", "🏃"),
    "PresenceSensor":     ("재실감지", "👤"),
    "OccupancyCounter":   ("인원계수", "🔢"),
    "ContactSensor":      ("열림감지", "🚩"),
    "TemperatureSensor":  ("온도계", "🌡️"),
    "HumiditySensor":     ("습도계", "💦"),
    "AirQualitySensor":   ("공기질", "😷"),
    "SmokeDetector":      ("연기감지", "🚨"),
    "GasSensor":          ("가스감지", "☣️"),
    "CarbonMonoxideSensor": ("일산화탄소", "☠️"),
    "LeakSensor":         ("누수감지", "🚿"),
    "RainSensor":         ("비감지", "🌧️"),
    "WindSensor":         ("풍속계", "🎐"),
    "UvSensor":           ("자외선", "🔆"),
    "SoilMoistureSensor": ("토양수분", "🌾"),
    "WaterLevelSensor":   ("수위계", "📏"),
    "WaterQualitySensor": ("수질계", "🧪"),
    "FlowSensor":         ("유량계", "🌊"),
    "PressureSensor":     ("압력계", "⏲️"),
    "WeightSensor":       ("중량계", "⚖️"),
    "VibrationSensor":    ("진동감지", "📳"),
    "TiltSensor":         ("기울기", "📐"),
    "ProximitySensor":    ("근접감지", "🎯"),
    "PowerMeter":         ("전력계", "⚡"),
    "EnergyMeter":        ("전력량계", "🔋"),
    "Battery":            ("배터리", "🔋"),
    "Button":             ("버튼", "⏺️"),
    "MultiButton":        ("멀티버튼", "🎛️"),
    "RfidReader":         ("RFID", "🪪"),
    "EmergencyStop":      ("비상정지", "🛑"),
    "SafetyBarrier":      ("안전바", "⛔"),
    "RobotVacuumCleaner": ("로봇청소기", "🤖"),
    "Mower":              ("잔디깎이", "🚜"),
    "ArmRobot":           ("로봇팔", "🦾"),
    "ConveyorBelt":       ("컨베이어", "📦"),
    "ProductionMachine":  ("생산기계", "🏭"),
    "AirCompressor":      ("공기압축기", "💨"),
    "Printer":            ("프린터", "🖨️"),
    "Chamber":            ("챔버", "🧫"),
    "Dishwasher":         ("식기세척기", "🍽️"),
    "LaundryWasher":      ("세탁기", "🧺"),
    "LaundryDryer":       ("건조기", "♨️"),
    "ClothingCare":       ("의류관리기", "👔"),
    "CoffeeMaker":        ("커피포트", "☕"),
    "Microwave":          ("전자레인지", "🍲"),
    "Oven":               ("오븐", "🍞"),
    "Refrigerator":       ("냉장고", "🧊"),
    "WaterHeater":        ("온수기", "🚰"),
    "WaterPurifier":      ("정수기", "🥤"),
    "Valve":              ("밸브", "🔧"),
    "Pump":               ("펌프", "⛽"),
    "Sprinkler":          ("스프링클러", "💦"),
    "FeedDispenser":      ("사료급이기", "🌽"),
    "PetFeeder":          ("반려동물급식기", "🐾"),
    "EvCharger":          ("EV충전기", "🔌"),
    "Clock":              ("시계", "🕐"),
    "GlobalVariable":     ("전역변수", "📦"),
    "NotificationProvider": ("알림", "📨"),
    "MessageSender":      ("메시지", "💬"),
    "EmailProvider":      ("메일", "📧"),
    "ChatProvider":       ("챗", "🗨️"),
    "NewsProvider":       ("뉴스", "📰"),
    "SunProvider":        ("해", "🌇"),
    "WeatherProvider":    ("날씨", "⛅"),
    "CalendarProvider":   ("일정", "📅"),
    "PersonTracker":      ("내 폰", "📱"),
}

# ── 손으로 적은 방 배치 ────────────────────────────────────────────────
# 없는 공간은 아래 auto_layout() 이 격자로 깐다.
# (x, y, w, h, 실외인가)
LAYOUT = {
    "HOME06": {
        "canvas": (1040, 720),
        "rooms": {
            "Kitchen":    (40, 40, 240, 180, False),
            "LivingRoom": (280, 40, 380, 300, False),
            "Utility":    (40, 220, 240, 120, False),
            "Entrance":   (40, 340, 180, 100, False),
            "Hallway":    (220, 340, 440, 100, False),
            "Bedroom":    (40, 440, 240, 240, False),
            "Bathroom":   (280, 440, 180, 240, False),
            "Study":      (460, 440, 200, 240, False),
            "BackDoor":   (660, 560, 40, 120, False),
            "Garage":     (700, 40, 300, 200, True),
            "Outdoor":    (700, 260, 300, 80, True),
            "Garden":     (700, 360, 300, 320, True),
        },
    },
}

OUTDOOR_HINT = {"Garden", "Outdoor", "Field", "Balcony", "Dock", "TankYard", "Barn",
                "Greenhouse", "Garage", "BackDoor"}


def auto_layout(rooms, counts):
    """손으로 안 적은 공간 — 기기 수에 비례해 격자로 깐다. 눈으로 고칠 밑그림."""
    n = len(rooms)
    cols = max(1, round(math.sqrt(n * 1.4)))
    rows = math.ceil(n / cols)
    cw, ch, pad = 300, 240, 20
    out, canvas_w = {}, cols * cw + pad
    for i, r in enumerate(sorted(rooms, key=lambda x: -counts[x])):
        cx, cy = i % cols, i // cols
        out[r] = (pad + cx * cw, pad + cy * ch, cw - pad, ch - pad,
                  r in OUTDOOR_HINT)
    return {"canvas": (canvas_w, rows * ch + pad), "rooms": out}


def place(x, y, w, h, n):
    """방 네모 안에 기기 n 개를 격자로 놓는다. 방 이름 자리로 위쪽을 비운다."""
    if n == 0:
        return []
    top, pad = 26, 12
    iw, ih = w - pad * 2, h - top - pad
    cols = max(1, min(n, round(math.sqrt(n * iw / max(ih, 1)))))
    rows = math.ceil(n / cols)
    # 칸이 너무 작아지면 열을 늘려 납작하게 깐다
    while ih / rows < 26 and cols < n:
        cols += 1
        rows = math.ceil(n / cols)
    cw, ch = iw / cols, ih / rows
    pts = []
    for i in range(n):
        c, r = i % cols, i // cols
        # 마지막 줄은 가운데로 모은다
        in_row = min(cols, n - r * cols)
        off = (cols - in_row) * cw / 2
        pts.append((round(x + pad + off + cw * (c + 0.5), 1),
                    round(y + top + ch * (r + 0.5), 1),
                    round(min(cw, ch) * 0.42, 1)))
    return pts


def room_of(dev_id, sid, tags):
    """기기 이름에서 방을 읽는다. 규칙을 안 따르면(LAB01) 태그에서 찾는다."""
    if dev_id.startswith(sid + "_"):
        return dev_id.split("_")[1]
    for t in tags:
        if t in ROOM_KO:
            return t
    return "Unplaced"


def build_space(sid, sp):
    devs = sp["devices"]
    by = collections.defaultdict(list)
    for did, v in devs.items():
        by[room_of(did, sid, v.get("tags", []))].append((did, v))

    system = [{"id": d, "cat": v["category"][0],
               "ko": CAT.get(v["category"][0], (v["category"][0], ""))[0],
               "icon": CAT.get(v["category"][0], ("", "•"))[1]}
              for d, v in sorted(by.pop("System", []))]

    counts = {r: len(v) for r, v in by.items()}
    lay = LAYOUT.get(sid)
    if lay:
        lay = {"canvas": lay["canvas"],
               "rooms": {r: lay["rooms"][r] for r in by if r in lay["rooms"]}}
        miss = [r for r in by if r not in lay["rooms"]]
        if miss:
            print(f"  ! {sid}: 배치에 없는 방 {miss} — 격자로 대신 깐다", file=sys.stderr)
            lay = auto_layout(list(by), counts)
    else:
        lay = auto_layout(list(by), counts)

    rooms, devices = [], []
    for r, (x, y, w, h, outdoor) in lay["rooms"].items():
        items = sorted(by[r])
        rooms.append({"id": r, "ko": ROOM_KO.get(r, r), "x": x, "y": y,
                      "w": w, "h": h, "outdoor": outdoor, "n": len(items)})
        for (did, v), (px, py, pr) in zip(items, place(x, y, w, h, len(items))):
            cat = v["category"][0]
            ko, icon = CAT.get(cat, (cat, "•"))
            devices.append({"id": did, "room": r, "cat": cat,
                            "cats": v["category"], "ko": ko, "icon": icon,
                            "x": px, "y": py, "r": pr,
                            "label": did.split("_", 2)[-1] if "_" in did else did})
    return {"id": sid, "kind": sp["kind"], "name": sp["name_ko"], "size": sp["size"],
            "canvas": {"w": lay["canvas"][0], "h": lay["canvas"][1]},
            "rooms": rooms, "devices": devices, "system": system,
            "missing": sp.get("missing_on_purpose", [])}


def build_cmds(sid, rows):
    out = []
    for r in rows:
        ir = None
        if r["ir_gt"]:
            try:
                ir = json.loads(r["ir_gt"])
            except json.JSONDecodeError:
                ir = None
        out.append({
            "id": r["id"], "text": r["command"], "expect": r["expect"],
            "match": r["match"], "why": r["why"], "tier": r["tier"], "d": r["d"],
            "mode": r["mode"], "trig": r["trig"], "act": r["act"],
            "targets": r["targets"].split() if r["targets"] else [],
            "ir": ir,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="40 공간 전부")
    ap.add_argument("--only", default="HOME06")
    a = ap.parse_args()

    S = json.load(open(os.path.join(BENCH, "spaces.json"), encoding="utf-8"))["spaces"]
    rows = list(csv.DictReader(open(os.path.join(BENCH, "dataset_5k.csv"), encoding="utf-8")))
    by_space = collections.defaultdict(list)
    for r in rows:
        by_space[r["space_id"]].append(r)

    os.makedirs(OUT, exist_ok=True)
    want = list(S) if a.all else [a.only]

    index = []
    for sid in want:
        sp = build_space(sid, S[sid])
        cm = build_cmds(sid, by_space[sid])
        json.dump(sp, open(f"{OUT}/space.{sid}.json", "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        json.dump(cm, open(f"{OUT}/cmds.{sid}.json", "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        index.append({"id": sid, "kind": sp["kind"], "name": sp["name"],
                      "size": sp["size"], "rooms": len(sp["rooms"]),
                      "devices": len(sp["devices"]), "cmds": len(cm),
                      "laid_out": sid in LAYOUT})
        print(f"{sid:9} 방 {len(sp['rooms']):2}  기기 {len(sp['devices']):3}  "
              f"명령 {len(cm):4}  {'손배치' if sid in LAYOUT else '자동배치'}")

    json.dump(index, open(f"{OUT}/spaces.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    import effects
    json.dump({"vocab": effects.VOCAB, "effects": effects.E,
               "switch_carries": effects.SWITCH_CARRIES},
              open(f"{OUT}/effects.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"\n→ {OUT}")


if __name__ == "__main__":
    main()
