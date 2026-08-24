#!/usr/bin/env python3
"""벤치마크 명세 — 숫자 없는 말을 정답으로 바꾸는 표.

카탈로그가 아니다. 서비스를 새로 만들지 않고, 규칙을 기기에 박지도 않는다.
"더우면", "시원하게" 같은 말이 어느 서비스의 어떤 값이 되는지만 적는다.

세 부분:
  CONST      공간 종류별 기준값. "덥다" 는 집에서 26℃, 온실에서 30℃ 다.
  PREDICATE  숫자 없는 조건 → (서비스, 비교). 열거값으로 풀리는 것은 상수가 필요 없다.
  INTENT     기기를 안 댄 명령 → 후보가 하나일 때 어떻게 푸는가.

INTENT 은 후보가 **하나뿐일 때만** 쓴다. 여럿이면 되묻기, 없으면 거절이다
(dataset_5k.csv 의 expect 열이 이미 그렇게 갈라 놓았다).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(os.path.dirname(HERE), "files", "service_list_ver3.1.0.json")
KINDS = ("home", "office", "lab", "farm", "factory")

# ── 공간 종류별 기준값 ──────────────────────────────────────────────────
# 근거: 온·습도는 국내 실내 권장(여름 26℃ / 겨울 20℃, 습도 40~60%),
#       미세먼지는 환경부 '나쁨' 경계(PM10 81, PM2.5 36), CO2 는 실내공기질 1,000ppm.
#       농장·공장 값과 전력 기준은 우리가 정한 값이다 — 근거 문헌이 아니라 설정이다.
CONST = {
    #                      home  office   lab   farm  factory
    "too_warm_c":         (  26,     25,    24,    30,      32),
    "too_cold_c":         (  18,     19,    20,    12,      10),
    "too_humid_pct":      (  70,     65,    60,    85,      70),
    "too_dry_pct":        (  30,     30,    35,    50,      25),
    "dust_bad_ugm3":      (  81,     81,    50,   150,     150),   # PM10
    "fine_dust_bad_ugm3": (  36,     36,    25,    75,      75),   # PM2.5
    "co2_high_ppm":       (1000,   1000,   800,  3000,    1500),
    "too_dark_lux":       (  50,    100,   100,  1000,     150),
    "too_bright_lux":     (1000,   1000,  1000, 50000,    2000),
    "too_loud_db":        (  60,     55,    60,    75,      85),
    "battery_low_pct":    (  20,     20,    20,    20,      20),
    "tank_low_pct":       (  50,     50,    50,    50,      50),
    "soil_dry_pct":       (  30,     30,    30,    30,      30),
    "power_spike_w":      (3000,  10000,  5000, 10000,   50000),
    "wind_strong_ms":     (  10,     10,    10,     8,      12),
    "gas_danger_ppm":     ( 200,    200,   100,   200,     100),
    "vibration_high_mms": (  10,     10,     5,    15,      20),
}


def const(name, kind):
    return CONST[name][KINDS.index(kind)]


# ── 숫자 없는 조건 → 서비스와 비교 ──────────────────────────────────────
# (읽을 서비스, 연산, 기준). 기준이 CONST 이름이면 공간 종류로 값이 갈리고,
# 리터럴이면 공간과 무관하다.
PREDICATE = {
    # 숫자가 필요한 것
    "too warm":        ("TemperatureSensor.Temperature", ">", "too_warm_c"),
    "too cold":        ("TemperatureSensor.Temperature", "<", "too_cold_c"),
    "too humid":       ("HumiditySensor.Humidity", ">", "too_humid_pct"),
    "too dry":         ("HumiditySensor.Humidity", "<", "too_dry_pct"),
    "air quality bad": ("AirQualitySensor.VeryFineDustLevel", ">", "fine_dust_bad_ugm3"),
    "co2 high":        ("AirQualitySensor.CarbonDioxide", ">", "co2_high_ppm"),
    "too dark":        ("LightSensor.Brightness", "<", "too_dark_lux"),
    "too bright":      ("LightSensor.Brightness", ">", "too_bright_lux"),
    "too loud":        ("SoundSensor.Sound", ">", "too_loud_db"),
    "battery low":     ("Battery.BatteryLevel", "<", "battery_low_pct"),
    "tank below half": ("WaterLevelSensor.WaterLevel", "<", "tank_low_pct"),
    "soil dry":        ("SoilMoistureSensor.SoilMoisture", "<", "soil_dry_pct"),
    "energy spike":    ("PowerMeter.Power", ">", "power_spike_w"),
    "wind strong":     ("WindSensor.WindSpeed", ">", "wind_strong_ms"),
    "gas dangerous":   ("GasSensor.GasLevel", ">", "gas_danger_ppm"),
    "vibration high":  ("VibrationSensor.VibrationLevel", ">", "vibration_high_mms"),
    # 열거값·불리언으로 끝나는 것 — 기준값이 필요 없다
    # 극성 주의: 기존 377개 정답 IR 이 Contact == true 를 "감지됨 = 접점 붙음 = 닫힘" 으로
    # 쓰고 있다 ("When the contact sensor is closed" → Contact == true). 그쪽을 따른다.
    # HA(binary_sensor door: on = open)와 반대이므로 카탈로그 descriptor 에도 적었다.
    "door open":       ("ContactSensor.Contact", "==", False),
    "door closed":     ("ContactSensor.Contact", "==", True),
    "window open":     ("ContactSensor.Contact", "==", False),
    "dark outside":    ("SunProvider.SunState", "==", "belowHorizon"),
    "daylight":        ("SunProvider.IsDaylight", "==", True),
    "washer running":  ("LaundryWasher.RemainingTime", ">", 0),
    "dishwasher running": ("Dishwasher.RemainingTime", ">", 0),
    "raining":         ("WeatherProvider.Weather", "==", "rain"),
    "snowing":         ("WeatherProvider.Weather", "==", "snow"),
    "hot outside":     ("WeatherProvider.TemperatureWeather", ">", "too_warm_c"),
    "cold outside":    ("WeatherProvider.TemperatureWeather", "<", "too_cold_c"),
    "someone here":    ("$OCCUPANCY", "==", True),    # 공간의 occupancy 주체가 정한다
    "nobody here":     ("$OCCUPANCY", "==", False),
}

# ContactSensor.Contact 의 극성. 기존 377개 정답 IR 이 정한 대로다.
CONTACT_TRUE_MEANS = "closed"

# ── 기기를 안 댄 명령 → 어떻게 푸는가 ───────────────────────────────────
# 후보를 찾는 건 effects.py + want.py 가 한다:
#   "시원하게 해줘" 가 원하는 효과(want.py: thermal_comfort-)를 내는 서비스를
#   effects.py 에서 찾으면 후보 기기가 나온다. 공간에 하나면 실행, 여럿이면 되묻기, 없으면 거절.
# 여기엔 "하나로 정해진 뒤 값을 어떻게 넣나" 만 남긴다. 이것도 어휘 단위다 — 기기 단위가 아니다.
DELTA = {
    "thermal_comfort": 2,    # "시원하게/따뜻하게" = 현재 온도에서 2℃
    "temperature": 2,
    "humidity": 10,          # "건조해/눅눅해" = 현재 습도에서 10%p
    "illuminance": 0.5,      # "어둡게" = 현재 밝기의 절반, "밝게" = 80% 로
    "sound": 10,             # 볼륨 한 단계 = 10
}
# 효과가 + 나 - 인 서비스는 그냥 부른다. = 인 서비스(SetTargetTemperature 등)는
# 현재값 ± DELTA 로 인자를 만든다. 현재값은 같은 이름의 센서·상태 서비스에서 읽는다.
# 예) "시원하게" + AirConditioner 하나:
#     모드가 off → SetAirConditionerMode("cool")          (effects 에 thermal_comfort- 가 있는 enum)
#     켜져 있음  → SetTargetTemperature($T - 2)            (effects 에 thermal_comfort= 가 있는 함수)


# ── 알림은 되묻지 않는다 — 순서대로 첫 번째 되는 것으로 보낸다 ────────────
# "알려줘" 는 message_sent+ 를 내는 서비스가 여럿이어도(푸시·토스트·스피커·화면) 되묻기가
# 아니다. 사람은 "어디로 알려드릴까요?" 를 원하지 않는다. 있는 것 중 첫 번째로 보낸다.
#   푸시  ← 사용자 폰(PersonTracker)이 그 공간에 있을 때만
#   스피커 ← 말로 읽어 준다
#   토스트 ← 허브 화면 (NotificationProvider 는 모든 공간에 있다)
#   화면  ← Display.ShowMessage
NOTIFY_ORDER = [
    ("NotificationProvider.SendPush", "PersonTracker"),   # (서비스, 있어야 하는 기기)
    ("Speaker.Speak", None),
    ("NotificationProvider.SendToast", None),
    ("Display.ShowMessage", None),
]

# ── 후보가 여럿일 때 — 예외 없이 되묻는다 ──────────────────────────────
# "다 꺼줘"(switch/plug) 는 후보가 20종이 넘는다. 전부에 실행하는 게 자연스러워 보이지만
# 냉장고·서버·의료 장비까지 꺼 버릴 수 있어 치명적이다. 되묻는다.
# 위의 알림(NOTIFY_ORDER)만 예외다 — 어디로 알리든 해는 없다.
ASK_WHEN_MANY = True

def main():
    cat = json.load(open(CATALOG, encoding="utf-8"))
    bad = []
    for name, (svc, op, ref) in PREDICATE.items():
        if svc.startswith("$"):
            continue
        c, m = svc.split(".")
        if c not in cat or m not in cat[c]:
            bad.append(f"{name}: {svc} 가 카탈로그에 없음")
        if isinstance(ref, str) and ref in CONST:
            continue
        if isinstance(ref, str) and ref not in CONST and op == "==":
            en = cat.get(c, {}).get(m, {}).get("enums_descriptor") or []
            names = [x.split(" - ")[0] for x in en]
            if names and ref not in names:
                bad.append(f"{name}: {ref} 가 {svc} 의 열거값에 없음 {names}")
    for k, v in CONST.items():
        if len(v) != len(KINDS):
            bad.append(f"CONST[{k}] 길이가 {len(v)}")
    print(f"policy.py — 기준값 {len(CONST)}종 × 공간 {len(KINDS)}종, "
          f"조건 {len(PREDICATE)}개, 값 보폭 {len(DELTA)}개")
    print("검산:", *bad, sep="\n  ") if bad else print("검산: 어긋난 것 없음 ✅")

    import textwrap
    print("\n── 공간 종류별 기준값")
    print("  " + "항목".ljust(22) + "".join(k.rjust(9) for k in KINDS))
    for k, v in CONST.items():
        print("  " + k.ljust(22) + "".join(str(x).rjust(9) for x in v))
    print("\n── 숫자가 필요 없는 조건 (열거값·불리언으로 끝남)")
    print(textwrap.fill("  " + ", ".join(
        k for k, (s, o, r) in PREDICATE.items() if not (isinstance(r, str) and r in CONST)),
        96, subsequent_indent="  "))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
