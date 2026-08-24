#!/usr/bin/env python3
"""정답 IR 표 — 문형 틀 하나에 Timeline IR 조각 하나.

문장을 우리가 만들었으니 어떤 틀을 썼는지 안다. 그래서 IR 도 추론이 아니라
같은 자리에서 같이 만든다. 이 파일은 "이 틀은 어떤 IR 이 되는가" 만 적는다.

규약은 기존 정답 IR 377개에서 그대로 가져왔다.
  start_at  anchor "now" 또는 "cron" + cron "분 시 * * 요일"
  wait      cond, edge("none"/"rising"), 지속이면 for "10 MIN"
  cycle     until(null 또는 "clock.time >= 1500" / "n >= 4"), period "10 MIN", 반복수 count "n"
  if        cond, then, else
  call      target "Category.Method", args {…}
  read      var, src
  delay     duration "5 MIN"
  break

IR 은 기기 id 를 쓰지 않는다 — 카테고리·서비스까지만이다. 어느 기기냐는
dataset_5k.csv 의 targets 열이 따로 답한다 (파이프라인 2단계).

슬롯은 "$n" 처럼 적고 문장을 만들 때 고른 값으로 바꾼다.
"{CAT}" 는 그 시나리오의 센서 카테고리로 바뀐다.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import templates as T
CATALOG = os.path.join(os.path.dirname(HERE), "files", "service_list_ver3.1.0.json")

# ── 센서에서 숫자를 읽는 속성 ──────────────────────────────────────────
# "{sensor} 가 300 을 넘으면" 처럼 센서 이름만 대는 틀이 어느 속성을 읽는지.
READ_ATTR = {
    "TemperatureSensor": "Temperature", "HumiditySensor": "Humidity",
    "PressureSensor": "Pressure", "WeightSensor": "Weight",
    "WaterLevelSensor": "WaterLevel", "GasSensor": "GasLevel",
    "WaterQualitySensor": "Turbidity", "SoilMoistureSensor": "SoilMoisture",
    "FlowSensor": "FlowRate", "AirQualitySensor": "VeryFineDustLevel",
    "SoundSensor": "Sound", "LightSensor": "Brightness", "PowerMeter": "Power",
    "VibrationSensor": "VibrationLevel", "WindSensor": "WindSpeed",
    "ProximitySensor": "Distance", "TiltSensor": "TiltAngle",
    "Battery": "BatteryLevel", "CarbonDioxideSensor": "CarbonDioxide",
    "CarbonMonoxideSensor": "CarbonMonoxide",
}


def _t(cat, cond=None, edge="rising", hold=None, cron=None, delay=None, cycle=None):
    """트리거 조각 하나. cat 이 '*' 면 그 시나리오의 센서에 맞춰 붙는다."""
    d = {"cat": cat}
    for k, v in (("cond", cond), ("edge", edge), ("for", hold),
                 ("cron", cron), ("delay", delay), ("cycle", cycle)):
        if v is not None:
            d[k] = v
    return d


# ── 언제 (TRIG 틀 → IR) ────────────────────────────────────────────────
SUN_DOWN = 'SunProvider.SunState == "belowHorizon"'
SUN_UP = 'SunProvider.SunState == "aboveHorizon"'

TRIG_IR = {
    # 해
    "at sunset":                    _t("SunProvider", SUN_DOWN),
    "when the sun goes down":       _t("SunProvider", SUN_DOWN),
    "as the sun sets":              _t("SunProvider", SUN_DOWN),
    "around sundown":               _t("SunProvider", SUN_DOWN),
    "at sunrise":                   _t("SunProvider", SUN_UP),
    "when the sun comes up":        _t("SunProvider", SUN_UP),
    "once it gets dark outside":    _t("SunProvider", "SunProvider.IsDaylight == false"),
    # 시각 — cron. $HM 은 시각 슬롯이, $DOW 는 요일이 들어간다
    "at {time}":                    _t("Clock", cron="$time"),
    "every day at {time}":          _t("Clock", cron="$time"),
    "at {time} on weekdays":        _t("Clock", cron="$time@1-5"),
    "every morning at {time_am}":   _t("Clock", cron="$time_am"),
    "every night at {time_pm}":     _t("Clock", cron="$time_pm"),
    "on {weekday} at {time}":       _t("Clock", cron="$time@$weekday"),
    "every {n} minutes":            _t("Clock", cycle="$n MIN"),
    # 타이머
    "after {n} minutes":            _t("Clock", delay="$n MIN"),
    "{n} minutes from now":         _t("Clock", delay="$n MIN"),
    "after waiting {n} minutes":    _t("Clock", delay="$n MIN"),
    "once the {n} minute timer runs out": _t("Clock", delay="$n MIN"),
    # 움직임
    "when the motion sensor picks something up": _t("MotionSensor", "MotionSensor.Motion == true"),
    "when {sensor} detects movement":            _t("MotionSensor", "MotionSensor.Motion == true"),
    "if motion is detected in the {place}":      _t("MotionSensor", "MotionSensor.Motion == true"),
    "the moment something moves in the {place}": _t("MotionSensor", "MotionSensor.Motion == true"),
    "when nothing has moved for {n} minutes":
        _t("MotionSensor", "MotionSensor.Motion == false", edge="none", hold="$n MIN"),
    # 재실
    "while someone is in the {place}":     _t("PresenceSensor", "PresenceSensor.Presence == true", edge="none"),
    "when the {place} is occupied":        _t("PresenceSensor", "PresenceSensor.Presence == true"),
    "when someone shows up in the {place}": _t("PresenceSensor", "PresenceSensor.Presence == true"),
    "once the {place} is empty":           _t("PresenceSensor", "PresenceSensor.Presence == false"),
    "while nobody is around":              _t("PresenceSensor", "PresenceSensor.Presence == false", edge="none"),
    # 귀가·외출
    "when I get home":            _t("PersonTracker", "PersonTracker.IsHome == true"),
    "as soon as I arrive home":   _t("PersonTracker", "PersonTracker.IsHome == true"),
    "when I pull into the driveway": _t("PersonTracker", "PersonTracker.IsHome == true"),
    "once I am back home":        _t("PersonTracker", "PersonTracker.IsHome == true"),
    "when I am close to home":    _t("PersonTracker", "PersonTracker.DistanceToHome < 1"),
    "when I leave home":          _t("PersonTracker", "PersonTracker.IsHome == false"),
    "once everyone has left":     _t("PersonTracker", "PersonTracker.IsHome == false"),
    "after I head out":           _t("PersonTracker", "PersonTracker.IsHome == false"),
    "when I am away from home":   _t("PersonTracker", "PersonTracker.IsHome == false", edge="none"),
    # 문·창 — true 가 닫힘이다 (기존 377개 정답 IR 의 극성)
    "when the {place} door opens":        _t("ContactSensor", "ContactSensor.Contact == false"),
    "when {sensor} says the door is open": _t("ContactSensor", "ContactSensor.Contact == false"),
    "if a window is left open":           _t("ContactSensor", "ContactSensor.Contact == false", edge="none"),
    "once the door has been open for {n} minutes":
        _t("ContactSensor", "ContactSensor.Contact == false", edge="none", hold="$n MIN"),
    "when the door closes":               _t("ContactSensor", "ContactSensor.Contact == true"),
    # 초인종
    "when someone rings the doorbell":  _t("Doorbell", "Doorbell.DoorbellPressed == true"),
    "if the doorbell goes off":         _t("Doorbell", "Doorbell.DoorbellPressed == true"),
    "when there is somebody at the door": _t("Doorbell", "Doorbell.DoorbellPressed == true"),
    # 버튼
    "when I press the button":          _t("Button", 'Button.Button == "pushed"'),
    "with a single press of {dev_t}":   _t("Button", 'Button.Button == "pushed"'),
    "with one tap on the wall switch":  _t("Button", 'Button.Button == "pushed"'),
    "when the scene switch is pressed": _t("Button", 'Button.Button == "pushed"'),
    "when I double-press {dev_t}":      _t("Button", 'Button.Button == "double"'),
    # 임계값 — 문장이 대는 물리량과 시나리오의 센서가 맞아야 한다
    "when the temperature goes above {deg} degrees":
        _t("TemperatureSensor", "TemperatureSensor.Temperature > $deg"),
    "if the temperature drops below {deg} degrees":
        _t("TemperatureSensor", "TemperatureSensor.Temperature < $deg"),
    "while the temperature stays over {deg} degrees":
        _t("TemperatureSensor", "TemperatureSensor.Temperature > $deg", edge="none"),
    "when the humidity climbs over {pct} percent":
        _t("HumiditySensor", "HumiditySensor.Humidity > $pct"),
    "once the air quality gets worse than {lvl}":
        _t("AirQualitySensor", "AirQualitySensor.VeryFineDustLevel > $lvl"),
    "if {sensor} reads more than {lvl}":  _t("*", "{CAT}.{ATTR} > $lvl"),
    "once {sensor} goes over {lvl}":      _t("*", "{CAT}.{ATTR} > $lvl"),
    "if {sensor} falls under {lvl}":      _t("*", "{CAT}.{ATTR} < $lvl"),
    "while {sensor} stays above {lvl}":   _t("*", "{CAT}.{ATTR} > $lvl", edge="none"),
    # 날씨
    "when it starts raining":     _t("WeatherProvider", 'WeatherProvider.Weather == "rain"'),
    "if rain is in the forecast": _t("WeatherProvider", 'WeatherProvider.Weather == "rain"', edge="none"),
    "when snow is expected":      _t("WeatherProvider", 'WeatherProvider.Weather == "snow"', edge="none"),
    "when it gets hot outside":   _t("WeatherProvider", "WeatherProvider.TemperatureWeather > $too_warm_c"),
    "if the outside temperature drops below {deg}":
        _t("WeatherProvider", "WeatherProvider.TemperatureWeather < $deg"),
    "if the forecast says frost": _t("WeatherProvider", "WeatherProvider.TemperatureWeather <= 0", edge="none"),
    # 일정
    "when a meeting is about to start": _t("CalendarProvider", "CalendarProvider.IsBusy == true"),
    "at the start of my next event":    _t("CalendarProvider", "CalendarProvider.IsBusy == true"),
    "when today's first event begins":  _t("CalendarProvider", "CalendarProvider.IsBusy == true"),
    "if my calendar says I am busy":    _t("CalendarProvider", "CalendarProvider.IsBusy == true", edge="none"),
    # 휴대폰
    "when my phone connects to the home wi-fi": _t("PersonTracker", 'PersonTracker.ConnectedWifi != ""'),
    "if my phone battery falls under {pct} percent": _t("PersonTracker", "PersonTracker.BatteryLevel < $pct"),
    "when my phone goes into sleep mode": _t("PersonTracker", "PersonTracker.SleepMode == true"),
    "while I am on a call":               _t("PersonTracker", "PersonTracker.OnCall == true", edge="none"),
    # 배터리
    "when the battery drops below {pct} percent": _t("Battery", "Battery.BatteryLevel < $pct"),
    "if any sensor battery is running low":       _t("Battery", 'Battery.BatteryState == "low"', edge="none"),
    "once the battery is full":                   _t("Battery", 'Battery.BatteryState == "full"'),
    # 카메라 — 우리 카탈로그의 카메라는 사람을 감지하지 못한다. 카메라 자신의 상태로 건다
    "when the camera starts recording": _t("Camera", 'Camera.RecordingState == "recording"'),
    "if the camera comes on":           _t("Camera", 'Camera.CameraState == "on"'),
    "while the camera is recording":    _t("Camera", 'Camera.RecordingState == "recording"', edge="none"),
    "once the camera goes offline":     _t("Camera", 'Camera.CameraState == "unavailable"'),
    # 연기·일산화탄소
    "when the smoke detector goes off": _t("SmokeDetector", "SmokeDetector.Smoke == true"),
    "when {sensor} reports smoke":      _t("SmokeDetector", "SmokeDetector.Smoke == true"),
    "if the smoke alarm sounds":        _t("SmokeDetector", "SmokeDetector.Smoke == true"),
    # 누수
    "when a water leak is detected":       _t("LeakSensor", "LeakSensor.Leakage == true"),
    "if {sensor} finds water on the floor": _t("LeakSensor", "LeakSensor.Leakage == true"),
    "when the leak sensor trips":          _t("LeakSensor", "LeakSensor.Leakage == true"),
    # 가스
    "when the gas sensor goes over {lvl}": _t("GasSensor", "GasSensor.GasLevel > $lvl"),
    "if a gas leak is detected":           _t("GasSensor", "GasSensor.Gas == true"),
    "when {sensor} reads a dangerous level": _t("GasSensor", "GasSensor.GasLevel > $gas_danger_ppm"),
    # 전력
    "when power draw goes over {watt} watts": _t("PowerMeter", "PowerMeter.Power > $watt"),
    "if the meter reads above {watt}":        _t("PowerMeter", "PowerMeter.Power > $watt"),
    "when energy use spikes":                 _t("PowerMeter", "PowerMeter.Power > $power_spike_w"),
    "if power draw stays above {watt} watts": _t("PowerMeter", "PowerMeter.Power > $watt", edge="none"),
    # 세탁·생산 — 끝났다는 신호가 기기마다 다르다
    "when the washing machine finishes": _t("LaundryWasher", "LaundryWasher.RemainingTime == 0"),
    "as soon as the load is finished":   _t("LaundryWasher", "LaundryWasher.RemainingTime == 0"),
    "when the wash cycle ends":          _t("LaundryWasher", "LaundryWasher.RemainingTime == 0"),
    "when the machine finishes its cycle": _t("ProductionMachine", 'ProductionMachine.MachineState == "idle"'),
    "once the line run is done":           _t("ProductionMachine", 'ProductionMachine.MachineState == "idle"'),
    "when {dev_t} reports it is done":     _t("ProductionMachine", 'ProductionMachine.MachineState == "idle"'),
    # 다른 기기가 켜짐
    "when {dev_t} turns on":       _t("Switch", "Switch.Switch == true"),
    "if {dev_t} is switched off":  _t("Switch", "Switch.Switch == false"),
    "once {dev_t} has been on for {n} minutes":
        _t("Switch", "Switch.Switch == true", edge="none", hold="$n MIN"),
    # 진동·기울기·근접·바람
    "when {sensor} picks up heavy vibration": _t("VibrationSensor", "VibrationSensor.Vibration == true"),
    "when the machine starts shaking":        _t("VibrationSensor", "VibrationSensor.Vibration == true"),
    "if vibration goes over {lvl}":           _t("VibrationSensor", "VibrationSensor.VibrationLevel > $lvl"),
    "when the load tilts past {tilt} degrees": _t("TiltSensor", "TiltSensor.TiltAngle > $tilt"),
    "if {sensor} reports a tilt":              _t("TiltSensor", "TiltSensor.Tilt == true"),
    "when something comes within {cm} centimeters": _t("ProximitySensor", "ProximitySensor.Distance < $cm"),
    "if {sensor} sees an object in the way":        _t("ProximitySensor", "ProximitySensor.Proximity == true"),
    "when the wind picks up past {wind}": _t("WindSensor", "WindSensor.WindSpeed > $wind"),
    "if wind speed goes over {wind}":     _t("WindSensor", "WindSensor.WindSpeed > $wind"),
    # 비상정지·안전문
    "when the emergency stop is hit":       _t("EmergencyStop", 'EmergencyStop.EmergencyStopState == "triggered"'),
    "if anyone presses the emergency stop": _t("EmergencyStop", 'EmergencyStop.EmergencyStopState == "triggered"'),
    "when the safety barrier is broken":    _t("SafetyBarrier", 'SafetyBarrier.BarrierState == "blocked"'),
    "if someone crosses the light curtain": _t("SafetyBarrier", 'SafetyBarrier.BarrierState == "blocked"'),
}


# ── 켜다·끄다 ──────────────────────────────────────────────────────────
# 카테고리마다 "켠다" 가 다른 서비스다. 전원 스위치가 달린 기기는 Switch.On 이고
# (기존 정답 IR 이 69번 그렇게 쓴다), 모드가 전원을 겸하는 기기는 그 모드다.
# None 이면 Switch.On/Off 로 간다.
P_ON, P_OFF = "$on", "$off"
POWER = {
    "Light":            (None, None),
    "Switch":           (None, None),
    "Plug":             (None, None),
    "Television":       (None, None),
    "GrowLight":        (None, None),
    "Pump":             (None, None),
    "Camera":           (None, None),
    "Humidifier":       (("SetHumidifierMode", {"Mode": "auto"}), None),
    "AirConditioner":   (("SetAirConditionerMode", {"Mode": "auto"}),
                         ("SetAirConditionerMode", {"Mode": "off"})),
    "Fan":              (("SetFanMode", {"Mode": "auto"}), ("SetFanMode", {"Mode": "off"})),
    "AirPurifier":      (("SetAirPurifierMode", {"Mode": "auto"}),
                         ("SetAirPurifierMode", {"Mode": "off"})),
    "Thermostat":       (("SetThermostatMode", {"Mode": "heat"}),
                         ("SetThermostatMode", {"Mode": "off"})),
    "WaterHeater":      (("SetWaterHeaterMode", {"Mode": "heat"}),
                         ("SetWaterHeaterMode", {"Mode": "off"})),
    "Heater":           (("On", {}), ("Off", {})),
    "Ventilator":       (("SetVentilatorMode", {"Mode": "auto"}),
                         ("SetVentilatorMode", {"Mode": "off"})),
    "Chamber":          (("SetChamberMode", {"Mode": "auto"}),
                         ("SetChamberMode", {"Mode": "off"})),
    "Siren":            (("SetSirenMode", {"Mode": "emergency"}), ("Deactivate", {})),
    "Sprinkler":        (("Start", {"Minutes": 10.0}), ("Stop", {})),
    "Valve":            (("Open", {}), ("Close", {})),
    "GarageDoor":       (("Open", {}), ("Close", {})),
    "DoorLock":         (("Lock", {}), ("Unlock", {})),
    "WindowCovering":   (("UpOrOpen", {}), ("DownOrClose", {})),
    "RobotVacuumCleaner": (("SetRobotVacuumCleanerMode", {"Mode": "auto"}),
                           ("SetRobotVacuumCleanerMode", {"Mode": "stop"})),
    "Mower":            (("StartMowing", {}), ("Dock", {})),
    "CoffeeMaker":      (("Brew", {"Strength": "normal"}), ("Stop", {})),
    "ConveyorBelt":     (("Start", {}), ("Stop", {})),
    "AirCompressor":    (("Start", {}), ("Stop", {})),
    "FeedDispenser":    (("Dispense", {}), None),
    "Speaker":          (("Play", {"MediaSource": "$default"}), ("Stop", {})),
    "Display":          (("PowerOn", {}), ("PowerOff", {})),
    "ArmRobot":         (("SendCommand", {"Command": "start"}),
                         ("SendCommand", {"Command": "stop"})),
    "StatusLight":      (("SetStatus", {"Mode": "green"}), ("SetStatus", {"Mode": "off"})),
}


def c(target, **args):
    return {"op": "call", "target": target, "args": args}


# ── 색 ─────────────────────────────────────────────────────────────────
# 흰빛 계열은 색온도로, 나머지는 색상·채도로 간다.
KELVIN = {"warm white": 2700, "daylight white": 5500}
HUE = {"red": 0, "orange": 30, "amber": 45, "green": 120, "blue": 240,
       "purple": 280, "pink": 320}

# ── 장면 ───────────────────────────────────────────────────────────────
# 카탈로그에 Scene 서비스가 없다. 장면은 조명 값들의 묶음으로 푼다 — 벤치마크 명세다.
SCENE = {
    "movie":   [("bri", 20), ("k", 2700)],
    "party":   [("bri", 80), ("hue", "purple")],
    "relax":   [("bri", 30), ("k", 2700)],
    "reading": [("bri", 90), ("k", 4000)],
    "night":   [("bri", 5),  ("k", 2200)],
    "morning": [("bri", 70), ("k", 5000)],
    "focus":   [("bri", 100), ("k", 5500)],
    "dinner":  [("bri", 40), ("k", 2700)],
    "away":    [("off", None)],
}


def scene_calls(name):
    out = []
    for kind, v in SCENE[name]:
        if kind == "bri":
            out.append(c("Light.MoveToBrightness", Brightness=float(v), Rate=0.0))
        elif kind == "k":
            out.append(c("Light.MoveToColorTemperature", ColorTemperature=v))
        elif kind == "hue":
            out.append(c("Light.MoveToHueAndSaturation",
                         Hue=float(HUE[v]), Saturation=100.0))
        elif kind == "off":
            out.append(P_OFF)
    return out


def color_calls(name):
    if name in KELVIN:
        return [c("Light.MoveToColorTemperature", ColorTemperature=KELVIN[name])]
    return [c("Light.MoveToHueAndSaturation", Hue=float(HUE[name]), Saturation=100.0)]


# ── 무엇을 (ACT 틀 → IR) ───────────────────────────────────────────────
# 같은 문구가 여러 종류에 쓰이므로 (종류, 틀) 로 건다.
ACT_IR = {
    "light.on":  {t: [P_ON] for t in
                  ["turn on {dev}", "switch {dev} on", "put {dev} on",
                   "get {dev} on", "light up {dev}"]},
    "light.off": {t: [P_OFF] for t in
                  ["turn off {dev}", "switch {dev} off", "shut {dev} off", "kill {dev}"]},
    "light.dim": {
        "dim {dev} to {n} percent":    [c("Light.MoveToBrightness", Brightness="$n", Rate=0.0)],
        "set {dev} brightness to {n} percent": [c("Light.MoveToBrightness", Brightness="$n", Rate=0.0)],
        "bring {dev} down to {lo} percent": [c("Light.MoveToBrightness", Brightness="$lo", Rate=0.0)],
        "turn {dev} up to {hi} percent":    [c("Light.MoveToBrightness", Brightness="$hi", Rate=0.0)],
    },
    "light.color": {t: "$color" for t in
                    ["set {dev} to {color}", "make {dev} {color}",
                     "change {dev} to {color}", "turn {dev} {color}"]},
    "light.scene": {t: "$scene" for t in
                    ["set the lights to the {scene} scene",
                     "switch {dev} to the {scene} scene",
                     "put {dev} into {scene} mode",
                     "run the {scene} scene on the lights"]},
    "switch": {"turn on {dev}": [P_ON], "switch {dev} on": [P_ON],
               "turn off {dev}": [P_OFF], "toggle {dev}": [c("Switch.Toggle")]},
    "plug": {"turn on {dev}": [P_ON], "cut power to {dev}": [P_OFF],
             "switch {dev} off": [P_OFF]},
    "thermostat": {
        "set {dev} to {n} degrees":  [c("Thermostat.SetTargetTemperature", Temperature="$n")],
        "put {dev} on {n} degrees":  [c("Thermostat.SetTargetTemperature", Temperature="$n")],
        "turn the heating up to {n}": [c("Thermostat.SetThermostatMode", Mode="heat"),
                                       c("Thermostat.SetTargetTemperature", Temperature="$n")],
        "turn the heating off":       [c("Thermostat.SetThermostatMode", Mode="off")],
    },
    "ac": {
        "turn on {dev}":          [c("AirConditioner.SetAirConditionerMode", Mode="cool")],
        "put {dev} on cool":      [c("AirConditioner.SetAirConditionerMode", Mode="cool")],
        "set {dev} to {n} degrees": [c("AirConditioner.SetTargetTemperature", Temperature="$n")],
        "turn {dev} off":         [c("AirConditioner.SetAirConditionerMode", Mode="off")],
    },
    "fan": {
        "turn on {dev}":          [c("Fan.SetFanMode", Mode="auto")],
        "turn {dev} off":         [c("Fan.SetFanMode", Mode="off")],
        "set {dev} to high":      [c("Fan.SetFanMode", Mode="high")],
        "run {dev} for {n} minutes": [c("Fan.SetFanMode", Mode="auto"),
                                      {"op": "delay", "duration": "$n MIN"},
                                      c("Fan.SetFanMode", Mode="off")],
    },
    "purifier": {
        "turn on {dev}":     [c("AirPurifier.SetAirPurifierMode", Mode="auto")],
        "put {dev} on auto": [c("AirPurifier.SetAirPurifierMode", Mode="auto")],
        "run {dev} on turbo": [c("AirPurifier.SetAirPurifierMode", Mode="turbo")],
        "turn {dev} off":    [c("AirPurifier.SetAirPurifierMode", Mode="off")],
    },
    "humidity": {
        "turn on {dev}":            [c("Humidifier.SetHumidifierMode", Mode="auto")],
        "set {dev} to {n} percent": [c("Humidifier.SetTargetHumidity", Humidity="$n")],
        "turn {dev} off":           [P_OFF],
    },
    "cover": {
        "close {dev}":     [c("WindowCovering.DownOrClose")],
        "pull {dev} shut": [c("WindowCovering.DownOrClose")],
        "open {dev}":      [c("WindowCovering.UpOrOpen")],
        "raise {dev}":     [c("WindowCovering.UpOrOpen")],
        "lower {dev} to {n} percent": [c("WindowCovering.SetLevel", Level="$n")],
    },
    "lock": {"lock {dev}": [c("DoorLock.Lock")], "unlock {dev}": [c("DoorLock.Unlock")],
             "make sure {dev} is locked": [c("DoorLock.Lock")]},
    "garage": {"close {dev}": [c("GarageDoor.Close")], "shut {dev}": [c("GarageDoor.Close")],
               "open {dev}": [c("GarageDoor.Open")]},
    "media": {
        "turn on {dev}":  [P_ON],
        "turn {dev} off": [P_OFF],
        "pause {dev}":    [c("Speaker.Pause")],
        "play some music on {dev}": [c("Speaker.Play", MediaSource="$default")],
        "set the volume on {dev} to {n}": [c("Television.SetVolume", Volume="$n")],
    },
    "speaker": {
        "announce it on {dev}":      [c("Speaker.Speak", Text="$msg")],
        "say it out loud on {dev}":  [c("Speaker.Speak", Text="$msg")],
        "play a chime on {dev}":     [c("Speaker.Play", MediaSource="chime")],
    },
    "camera": {
        "start recording on {dev}":  [c("Camera.StartRecording")],
        "stop recording on {dev}":   [c("Camera.StopRecording")],
        "take a snapshot with {dev}": [c("Camera.CaptureImage")],
        "turn on {dev}":             [P_ON],
    },
    "siren": {"set off {dev}": [c("Siren.SetSirenMode", Mode="emergency")],
              "sound {dev}":   [c("Siren.SetSirenMode", Mode="emergency")],
              "turn {dev} off": [c("Siren.Deactivate")]},
    "vacuum": {
        "start {dev}": [c("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="auto")],
        "stop {dev}":  [c("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="stop")],
        "run {dev} in the {place}": [c("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="part")],
        "send {dev} back to its dock": [c("RobotVacuumCleaner.GoHome")],
    },
    "mower": {"start {dev}": [c("Mower.StartMowing")], "park {dev}": [c("Mower.Dock")],
              "send {dev} back to the dock": [c("Mower.Dock")]},
    "coffee": {"start {dev}": [c("CoffeeMaker.Brew", Strength="normal")],
               "brew a cup on {dev}": [c("CoffeeMaker.Brew", Strength="normal")],
               "turn {dev} off": [c("CoffeeMaker.Stop")]},
    "waterheater": {
        "turn on {dev}":            [c("WaterHeater.SetWaterHeaterMode", Mode="heat")],
        "set {dev} to {n} degrees": [c("WaterHeater.SetTargetTemperature", Temperature="$n")],
        "turn {dev} off":           [c("WaterHeater.SetWaterHeaterMode", Mode="off")],
    },
    "timer": {
        "set a {n} minute timer":          "$timer",
        "start a countdown for {n} minutes": "$timer",
        "cancel the timer":                [{"op": "break"}],
    },
    "sprinkler": {"start {dev}": [c("Sprinkler.Start", Minutes=10.0)],
                  "stop {dev}":  [c("Sprinkler.Stop")],
                  "run {dev} for {n} minutes": [c("Sprinkler.Start", Minutes="$n")]},
    "growlight": {"turn on {dev}": [P_ON], "turn {dev} off": [P_OFF],
                  "run {dev} for {n} hours": [P_ON,
                                              {"op": "delay", "duration": "$n HOUR"},
                                              P_OFF]},
    "ventilator": {"turn on {dev}":  [c("Ventilator.SetVentilatorMode", Mode="auto")],
                   "turn {dev} off": [c("Ventilator.SetVentilatorMode", Mode="off")],
                   "run {dev} for {n} minutes":
                       [c("Ventilator.SetVentilatorMode", Mode="auto"),
                        {"op": "delay", "duration": "$n MIN"},
                        c("Ventilator.SetVentilatorMode", Mode="off")]},
    "feeder": {"run {dev}": [c("FeedDispenser.Dispense")],
               "dispense feed with {dev}": [c("FeedDispenser.Dispense")],
               "skip the next feeding": [{"op": "break"}]},
    "pump": {"start {dev}": [c("Pump.SetPumpMode", PumpMode="normal")],
             "stop {dev}":  [P_OFF],
             "run {dev} for {n} minutes": [c("Pump.SetPumpMode", PumpMode="normal"),
                                           {"op": "delay", "duration": "$n MIN"}, P_OFF]},
    "valve": {"close {dev}": [c("Valve.Close")], "shut {dev} right away": [c("Valve.Close")],
              "open {dev}": [c("Valve.Open")]},
    "chamber": {"set {dev} to {n} degrees": [c("Chamber.SetTargetTemperature", Temperature="$n")],
                "start {dev}": [c("Chamber.SetChamberMode", Mode="auto")],
                "stop {dev}":  [c("Chamber.SetChamberMode", Mode="off")]},
    "conveyor": {"start {dev}": [c("ConveyorBelt.Start")], "stop {dev}": [c("ConveyorBelt.Stop")],
                 "slow {dev} down": [c("ConveyorBelt.SetBeltSpeed", BeltSpeed=0.5)]},
    "compressor": {"start {dev}": [c("AirCompressor.Start")], "stop {dev}": [c("AirCompressor.Stop")]},
    "statuslight": {"turn {dev} green": [c("StatusLight.SetStatus", Mode="green")],
                    "turn {dev} red":   [c("StatusLight.SetStatus", Mode="red")],
                    "switch {dev} to amber": [c("StatusLight.SetStatus", Mode="yellow")]},
    "armrobot": {"start {dev}": [c("ArmRobot.SendCommand", Command="start")],
                 "stop {dev}":  [c("ArmRobot.SendCommand", Command="stop")],
                 "park {dev}":  [c("ArmRobot.SendCommand", Command="park")]},
}


# ── 알림 ───────────────────────────────────────────────────────────────
# 어느 채널로 보낼지는 dataset_5k.csv 의 target_svc 열이 이미 정했다
# (policy.NOTIFY_ORDER). 여기서는 인자 이름과 문구만 만든다.
NOTIFY_ARGS = {
    "NotificationProvider.SendPush":  lambda m: {"Title": "Home", "Body": m},
    "NotificationProvider.SendToast": lambda m: {"Message": m},
    "NotificationProvider.SendAlert": lambda m: {"Message": m, "Level": "info"},
    "Speaker.Speak":                  lambda m: {"Text": m},
    "Display.ShowMessage":            lambda m: {"Message": m, "DurationSeconds": 10.0},
}
# 무엇을 알리나 — 문장을 만든 트리거가 정한다
NOTIFY_TEXT = {
    "now": "Here is the status", "sun": "The sun has set", "time": "It is time",
    "timer": "The timer has finished", "motion": "Motion was detected",
    "presence": "Someone is in the room", "arrive": "You are home",
    "leave": "You have left home", "contact": "The door has opened",
    "doorbell": "Someone is at the door", "button": "The button was pressed",
    "threshold": "The sensor passed its threshold", "weather": "The weather has changed",
    "calendar": "Your next event is starting", "phone": "Your phone status changed",
    "battery": "The battery is low", "security": "The camera state changed",
    "smoke": "Smoke has been detected", "leak": "A water leak has been detected",
    "gas": "A dangerous gas level has been detected",
    "power": "Power draw is high", "finished": "The machine has finished",
    "device": "The device changed state", "vibration": "Heavy vibration detected",
    "tilt": "The load has tilted", "proximity": "Something is too close",
    "wind": "The wind is strong", "emergency": "The emergency stop was hit",
    "barrier": "The safety barrier was broken",
}

# ── 조회 ───────────────────────────────────────────────────────────────
# 읽어서 말해 준다. read 로 변수에 담고 그 변수를 알림 문구에 끼운다 (기존 정답 IR 방식).
def _q(var, src, text):
    return {"read": (var, src), "say": text}


QUERY_IR = {
    "tell me the temperature in the {place}": _q("Temperature", "TemperatureSensor.Temperature",
                                                 "The temperature is $Temperature"),
    "what is the temperature in the {place}": _q("Temperature", "TemperatureSensor.Temperature",
                                                 "The temperature is $Temperature"),
    "read out the humidity":  _q("Humidity", "HumiditySensor.Humidity", "The humidity is $Humidity"),
    "how humid is the {place}": _q("Humidity", "HumiditySensor.Humidity", "The humidity is $Humidity"),
    "how much power is {dev} using":  _q("Power", "PowerMeter.Power", "The power draw is $Power"),
    "how much power is {dev} pulling": _q("Power", "PowerMeter.Power", "The power draw is $Power"),
    "check whether {dev} is on": _q("Switch", "Switch.Switch", "The switch is $Switch"),
    "is {dev} on right now":     _q("Switch", "Switch.Switch", "The switch is $Switch"),
    "what is {dev} doing":       _q("Switch", "Switch.Switch", "The switch is $Switch"),
    "what is {dev} set to":      _q("Switch", "Switch.Switch", "The switch is $Switch"),
    "tell me if {dev} is open":  _q("Contact", "ContactSensor.Contact", "The contact is $Contact"),
    "is anyone in the {place}":  _q("Presence", "$OCCUPANCY", "Presence is $Presence"),
}

# 즉시 실행일 때만 쓰는 알림 문형 (build_dataset.NOW_OVERRIDE) — 무엇을 알리는지가 문장에 있다
NOW_NOTIFY_TEXT = {
    "let me know if {dev} is still on": "The device is still on",
    "send me the {place} temperature":  "The temperature is $Temperature",
    "ping me when {dev} finishes":      "The device has finished",
    "remind me to check {dev}":         "Please check the device",
    "text me the humidity in the {place}": "The humidity is $Humidity",
    "let me know whether anyone is in the {place}": "Presence is $Presence",
    "send me a note if {dev} stays on": "The device is still on",
}
NOW_NOTIFY_READ = {
    "send me the {place} temperature": ("Temperature", "TemperatureSensor.Temperature"),
    "text me the humidity in the {place}": ("Humidity", "HumiditySensor.Humidity"),
    "let me know whether anyone is in the {place}": ("Presence", "$OCCUPANCY"),
}

# ── 기기를 안 대는 문장 → 어떤 동작으로 푸나 ────────────────────────────
# 후보 카테고리가 하나로 정해진 뒤의 이야기다 (여럿이면 되묻기라 IR 이 없다).
# 여기 적은 서비스의 카테고리가 이긴 카테고리와 다르면 그 카테고리의 전원으로 떨어진다.
_DIM_HALF = [c("Light.MoveToBrightness", Brightness="$Light.CurrentBrightness * 0.5", Rate=0.0)]
_WARM = [c("Light.MoveToColorTemperature", ColorTemperature=2700)]

VAGUE_IR = {}
def _v(kind, texts, calls):
    for t in texts:
        VAGUE_IR[t] = calls

_v("ac", ["it is too hot in here", "I am sweating", "this room is stuffy and hot",
          "cool this place down", "make it less warm", "bring the temperature down"],
   [c("AirConditioner.SetAirConditionerMode", Mode="cool")])
_v("fan", ["it feels stuffy", "there is no air in here", "the air is not moving",
           "get some air moving", "make it breezy"], [c("Fan.SetFanMode", Mode="auto")])
_v("thermostat", ["I am cold", "it is freezing in here", "it is chilly",
                  "warm this room up", "make it cozy", "take the chill off"],
   [c("Thermostat.SetThermostatMode", Mode="heat"),
    c("Thermostat.SetTargetTemperature", Temperature="$Thermostat.CurrentTemperature + 2")])
_v("cover", ["the glare is bad", "the sun is in my eyes", "block the sun",
             "give me some privacy", "shut out the light from outside"],
   [c("WindowCovering.DownOrClose")])
_v("light.on", ["it is too dark in here", "I cannot see anything", "this room is gloomy",
                "brighten this place up", "give me some light to read by"], [P_ON])
_v("light.off", ["it is too bright", "I am going to sleep",
                 "kill the lights in here", "make it dark"], [P_OFF])
_v("light.dim", ["this is harsh on the eyes", "make it dimmer", "tone it down a bit",
                 "set the mood softer"], _DIM_HALF)
_v("light.color", ["this white light is harsh", "give this room some color",
                   "make it feel warmer in here", "set a calmer tone"], _WARM)
VAGUE_IR["make it cozy in here"] = "$scene:relax"
VAGUE_IR["set the mood for a movie"] = "$scene:movie"
VAGUE_IR["get this place ready for guests"] = "$scene:party"
VAGUE_IR["make it feel like morning"] = "$scene:morning"
_v("purifier", ["the air feels bad", "it smells in this room", "the air quality is awful",
                "clean the air in here", "freshen this room up"],
   [c("AirPurifier.SetAirPurifierMode", Mode="auto")])
_v("humidity", ["the air is too dry", "my throat is dry", "the windows are fogging up",
                "fix the humidity in here"], [c("Humidifier.SetHumidifierMode", Mode="auto")])
_v("ventilator", ["it smells terrible in here", "the fumes are getting bad",
                  "air this place out", "get fresh air in here"],
   [c("Ventilator.SetVentilatorMode", Mode="auto")])
_v("vacuum", ["the floor is dirty", "there are crumbs everywhere", "the carpet needs a pass",
              "clean up in here", "tidy the floor"],
   [c("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="auto")])
_v("mower", ["the grass is getting long", "the lawn looks rough", "deal with the lawn"],
   [c("Mower.StartMowing")])
_v("coffee", ["I need caffeine", "I am half asleep", "get me something hot to drink",
              "make me a cup"], [c("CoffeeMaker.Brew", Strength="normal")])
_v("waterheater", ["the water is cold", "no hot water again", "I want a hot shower",
                   "get the water hot"], [c("WaterHeater.SetWaterHeaterMode", Mode="heat")])
_v("media", ["it is too quiet in here", "I cannot hear the show", "put something on",
             "I want some music"], [c("Speaker.Play", MediaSource="$default")])
_v("media_down", ["it is too loud", "turn it down a bit"], [c("Speaker.VolumeDown")])
_v("speaker", ["say it out loud", "tell everyone in the house", "let me hear it"],
   [c("Speaker.Speak", Text="$msg")])
_v("lock", ["I do not feel safe", "I am heading out", "make sure the place is secure",
            "lock things up"], [c("DoorLock.Lock")])
_v("garage", ["I am pulling out", "I parked already", "close things up out front"],
   [c("GarageDoor.Close")])
_v("camera", ["keep an eye on the place", "let me see what is going on", "record this"],
   [c("Camera.StartRecording")])
_v("siren", ["scare them off", "make some noise", "raise the alarm"],
   [c("Siren.SetSirenMode", Mode="intruder")])
_v("switch", ["I am done for the day", "nothing needs to be on right now",
              "shut everything down in here"], [P_OFF])
_v("plug", ["we are wasting electricity", "let us save some power",
            "cut the standby draw"], [P_OFF])
_v("query", ["is everything alright at home", "how are things in here",
             "did I leave anything on", "what is the situation"], "$status")
_v("notify", ["keep me posted", "tell me if something is off",
              "I want to know when it changes"], "$notify")
_v("timer", ["remind me in a bit", "give me a few minutes"], "$timer")
_v("sprinkler", ["the crops look dry", "the soil is parched", "these plants need water",
                 "get water to the field"], [c("Sprinkler.Start", Minutes=10.0)])
_v("growlight", ["the plants are not getting enough light", "it is dim in the grow room",
                 "give the plants more light"], [P_ON])
_v("feeder", ["the animals look hungry", "feeding time is overdue", "feed them"],
   [c("FeedDispenser.Dispense")])
_v("pump", ["the tank is running low", "we need more water in the line",
            "get the water moving"], [c("Pump.SetPumpMode", PumpMode="normal")])
_v("conveyor", ["something is jammed", "stop the line", "hold production"],
   [c("ConveyorBelt.Stop")])
_v("valve", ["water is going everywhere", "there is a leak", "shut the water off",
             "stop the flow"], [c("Valve.Close")])
_v("compressor", ["the air pressure is dropping", "build the pressure back up"],
   [c("AirCompressor.Start")])
VAGUE_IR["show everyone we are running"] = [c("StatusLight.SetStatus", Mode="green")]
VAGUE_IR["flag this line as stopped"] = [c("StatusLight.SetStatus", Mode="red")]
VAGUE_IR["park the arm"] = [c("ArmRobot.SendCommand", Command="park")]
VAGUE_IR["hold the cell"] = [c("ArmRobot.SendCommand", Command="stop")]
_v("chamber", ["the samples are getting warm", "this batch is off temperature",
               "get the samples back on temperature"],
   [c("Chamber.SetChamberMode", Mode="auto")])

# ── 조건절 (LOGIC 틀의 {cond}) ─────────────────────────────────────────
# policy.PREDICATE 를 그대로 쓴다. 숫자가 문장에 있는 것만 여기서 직접 적는다.
COND_IR = {
    "the room is too warm":            "@too warm",
    "nobody is home":                  "@nobody here",
    "the door is open":                "@door open",
    "the window is open":              "@window open",
    "it is dark outside":              "@dark outside",
    "the washing machine is running":  "@washer running",
    "someone is in the room":          "@someone here",
    "the tank is below half":          "@tank below half",
    "the humidity is over 60 percent": "HumiditySensor.Humidity > 60",
    "the temperature is under 18 degrees": "TemperatureSensor.Temperature < 18",
    "the battery is under 20 percent": "Battery.BatteryLevel < 20",
}

# 집이 아닌 공간용 별명 — 뜻이 같으니 IR 도 같다 (templates.NONHOME)
for _old, _new in T.NONHOME.items():
    if _old in COND_IR:
        COND_IR[_new] = COND_IR[_old]
    if _old in TRIG_IR:
        TRIG_IR[_new] = TRIG_IR[_old]


# ── 조립 ───────────────────────────────────────────────────────────────
# 우리가 덧붙인 표기 세 가지. 카탈로그에 없는 것이라 여기 적어 둔다.
#   wait 의 "timeout"     "10분 안에 안 오면" — 기다림에 제한시간을 준다
#   src 의 "@-1HOUR"      같은 값의 한 시간 전 읽기 (D11 비교)
#   src 의 "@count:today" 오늘 그 조건이 몇 번 참이었나 (D12 누적)
#   GlobalVariable.Value("Human")  재실을 전역 변수로 두는 공간 (spaces.json 의 변수 이름과 같다)
OCC_SRC = {
    "motion":   "MotionSensor.Motion",
    "presence": "PresenceSensor.Presence",
    "phone":    "PersonTracker.IsHome",
    "global":   'GlobalVariable.Value("Human")',
    "none":     'GlobalVariable.Value("Human")',
}

_TOKEN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def subst(x, slots):
    """"$n" 같은 자리를 고른 값으로 바꾼다. 슬롯에 없는 $이름은 그대로 둔다
    ("$Light.CurrentBrightness" 는 실행 중에 읽는 값이라 우리가 건드리지 않는다)."""
    if isinstance(x, dict):
        return {k: subst(v, slots) for k, v in x.items()}
    if isinstance(x, list):
        return [subst(v, slots) for v in x]
    if not isinstance(x, str):
        return x
    m = _TOKEN.fullmatch(x)
    if m and m.group(1) in slots:
        return slots[m.group(1)]          # 통째로 한 슬롯이면 값의 자료형을 지킨다
    return _TOKEN.sub(lambda k: str(slots[k.group(1)]) if k.group(1) in slots
                      else k.group(0), x)


# ── 시각 → cron ────────────────────────────────────────────────────────
DOW = {"Monday": "1", "Tuesday": "2", "Wednesday": "3", "Thursday": "4",
       "Friday": "5", "Saturday": "6", "Sunday": "7", "weekends": "6,7"}


def hhmm(t):
    t = t.strip().lower()
    if t == "midnight":
        return 0, 0
    if t == "noon":
        return 0, 12
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", t)
    if not m:
        raise ValueError("시각을 못 읽음: " + t)
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return mi, h


def cron_of(spec, slots):
    """"$time@1-5" 처럼 적힌 것을 "0 8 * * 1-5" 로."""
    key, _, dow = spec.partition("@")
    mi, h = hhmm(str(slots[key.lstrip("$")]))
    if dow.startswith("$"):
        dow = DOW[str(slots[dow.lstrip("$")])]
    return f"{mi} {h} * * {dow or '*'}"


# ── 전원 ───────────────────────────────────────────────────────────────
def power_call(cat, on):
    """그 카테고리에서 "켠다/끈다" 가 어느 서비스인가."""
    pair = POWER.get(cat)
    spec = pair[0 if on else 1] if pair else None
    if spec is None:
        return c("Switch.On" if on else "Switch.Off")
    meth, args = spec
    return c(f"{cat}.{meth}", **args)


def _cat_of(call):
    return call["target"].split(".")[0] if isinstance(call, dict) and "target" in call else None


_CAT_CACHE = []


def _catalog():
    if not _CAT_CACHE:
        _CAT_CACHE.append(json.load(open(CATALOG, encoding="utf-8")))
    return _CAT_CACHE[0]


def arg_names(c0, m, spec):
    """그 서비스의 인자 이름들. 기존 정답 IR 이 쓰는 이름이 있으면 그쪽이 먼저다."""
    if (c0, m) in ARG_ALIAS:
        return ARG_ALIAS[(c0, m)]
    fmt = spec.get("argument_format")
    if fmt:
        return [w.strip().title().replace("_", "") for w in fmt.split("|")]
    return ["Mode"] if spec.get("argument_type") == "ENUM" else []


def coerce(call):
    """DOUBLE 자리에 정수가 들어가지 않게 한다 — 기존 정답 IR 이 5.0, 0.0 으로 쓴다."""
    cat = _catalog()
    c0, _, m = call["target"].partition(".")
    spec = cat.get(c0, {}).get(m)
    if not spec or not call.get("args"):
        return call
    names = arg_names(c0, m, spec)
    types = [t.strip() for t in (spec.get("argument_type") or "").split("|")]
    if not names and len(types) == 1 and len(call["args"]) == 1:
        names = list(call["args"])        # 인자가 하나뿐이면 이름을 카탈로그가 안 적어도 된다
    for i, nm in enumerate(names):
        if nm in call["args"] and i < len(types):
            v = call["args"][nm]
            if types[i] == "DOUBLE" and isinstance(v, int) and not isinstance(v, bool):
                call["args"][nm] = float(v)
            elif types[i] == "INTEGER" and isinstance(v, float) and v.is_integer():
                call["args"][nm] = int(v)
    return call


def _notify_call(svc, msg):
    if svc not in NOTIFY_ARGS:
        return None
    return c(svc, **NOTIFY_ARGS[svc](msg))


def act_nodes(*, act, tpl, act_cat, vague_tpl, slots, notify_svc, trig_kind, occ_src):
    """동작절 → 노드 목록. 못 만들면 None."""
    msg = NOTIFY_TEXT.get(trig_kind, "Here is the status")
    if vague_tpl is not None:
        raw = VAGUE_IR.get(vague_tpl)
    elif act == "notify":
        raw = "$notify"
        if tpl in NOW_NOTIFY_TEXT:
            msg = NOW_NOTIFY_TEXT[tpl]
    elif act == "query":
        raw = QUERY_IR.get(tpl)
    else:
        raw = ACT_IR.get(act, {}).get(tpl)
    if raw is None:
        return None

    # 특별한 표시들
    if raw == "$notify":
        pre = []
        if vague_tpl is None and tpl in NOW_NOTIFY_READ:
            var, src = NOW_NOTIFY_READ[tpl]
            pre = [{"op": "read", "var": var, "src": occ_src if src == "$OCCUPANCY" else src}]
        call = _notify_call(notify_svc, msg)
        return None if call is None else pre + [call]
    if raw == "$status":
        call = _notify_call(notify_svc, "Everything looks normal")
        return None if call is None else [call]
    if raw == "$timer":
        call = _notify_call(notify_svc, "The timer has finished")
        # "이따 알려줘" 처럼 숫자를 안 대면 5분으로 본다 (벤치마크 명세)
        node = [{"op": "delay", "duration": "%s MIN" % slots.get("n", 5)}]
        return node + ([call] if call else [])
    if raw == "$color":
        raw = color_calls(slots["color"])
    elif raw == "$scene":
        raw = scene_calls(slots["scene"])
    elif isinstance(raw, str) and raw.startswith("$scene:"):
        raw = scene_calls(raw.split(":")[1])
    if isinstance(raw, dict) and "read" in raw:          # 조회
        var, src = raw["read"]
        node = {"op": "read", "var": var,
                "src": occ_src if src == "$OCCUPANCY" else src}
        call = _notify_call(notify_svc, raw["say"])
        return None if call is None else [node, call]

    out = []
    for x in json.loads(json.dumps(raw)):
        if x == P_ON:
            out.append(power_call(act_cat, True))
        elif x == P_OFF:
            out.append(power_call(act_cat, False))
        else:
            x = subst(x, slots)
            if x.get("op") == "call":
                # 의도 문장이 이긴 카테고리와 다른 서비스를 가리키면 전원으로 떨어진다
                if vague_tpl is not None and _cat_of(x) != act_cat:
                    x = power_call(act_cat, True)
            out.append(x)
    # 자리표시자는 마지막에 한 번에 푼다 — 전원 호출로 떨어진 것도 빠뜨리지 않는다
    for x in out:
        if isinstance(x, dict) and x.get("op") == "call" and x.get("args"):
            x["args"] = {k: (msg if v == "$msg"
                             else "default playlist" if v == "$default" else v)
                         for k, v in x["args"].items()}
    return out


def _cond(cond_text, occ_src, kind):
    """조건절 문구 → 조건식. policy.PREDICATE 를 쓴다."""
    import policy
    e = COND_IR.get(cond_text)
    if e is None:
        return None
    if not e.startswith("@"):
        return e
    svc, op, ref = policy.PREDICATE[e[1:]]
    if svc == "$OCCUPANCY":
        svc = occ_src
    if isinstance(ref, str) and ref in policy.CONST:
        ref = policy.const(ref, kind)
    val = ("true" if ref is True else "false" if ref is False
           else f'"{ref}"' if isinstance(ref, str) else ref)
    return f"{svc} {op} {val}"


def _lhs(cond):
    """조건식에서 읽는 쪽만 떼어낸다 — "TemperatureSensor.Temperature > 26" → 앞부분."""
    m = re.match(r"([A-Za-z_][A-Za-z0-9_.]*(?:\([^)]*\))?)", cond or "")
    return m.group(1) if m else "GlobalVariable.Value(\"state\")"


def logic_nodes(frame, acts, cond, slots, trig_cond, off_call):
    """로직 문형 → 노드 목록. n·m 은 이미 slots 에 있다."""
    n = slots.get("n", 10)
    m = slots.get("m", 3)
    per = f"{n} MIN"
    reps = max(1, int(m) * 60 // int(n))          # "m시간 동안 n분마다" 의 반복 횟수
    src = _lhs(trig_cond)

    def cyc(body, until=None, count=None, period=per):
        d = {"op": "cycle", "until": until, "period": period, "body": body}
        if count:
            d["count"] = count
        return [d]

    def iff(cnd, body):
        return [{"op": "if", "cond": cnd, "then": body, "else": []}]

    F = {
        "if {cond} right now, {a}":              lambda: iff(cond, acts),
        "{a}, but only if {cond}":               lambda: iff(cond, acts),
        "{a}, then {n} minutes later turn it back off":
            lambda: acts + [{"op": "delay", "duration": per}] + [off_call],
        "wait {n} minutes and then {a}":
            lambda: [{"op": "delay", "duration": per}] + acts,
        "keep checking and {a} for as long as {cond}":
            lambda: cyc(acts, until=f"not ({cond})", period="1 MIN"),
        "{a} while {cond}, and stop once that changes":
            lambda: cyc(acts, until=f"not ({cond})", period="1 MIN"),
        "check every {n} minutes and {a} if {cond}":
            lambda: cyc(iff(cond, acts)),
        "{a} every {n} minutes":                 lambda: cyc(acts),
        "{a} every {n} minutes for the next {m} hours":
            lambda: cyc(acts, until=f"n >= {reps}", count="n"),
        "repeat this {m} times: {a}, then wait {n} minutes":
            lambda: cyc(acts, until=f"n >= {m}", count="n"),
        "{a} every {n} minutes until {cond}":    lambda: cyc(acts, until=cond),
        "once {cond}, {a} every {n} minutes":
            lambda: [{"op": "wait", "cond": cond, "edge": "rising"}] + cyc(acts),
        # "after that happens, …" 와 "give it {n} minutes, and if nothing has changed …"
        # 두 문형은 뺐다. 문장은 기다림·조건을 말하는데 IR 에는 둘 다 없어서
        # 문제와 정답이 어긋났다 (2026-08-25, whisoo 확인).
        "wait up to {n} minutes to see if {cond}; if not, {a}":
            lambda: [{"op": "wait", "cond": cond, "edge": "rising", "timeout": per}] \
                    + iff(f"not ({cond})", acts),
        "if it is higher than it was an hour ago, {a}":
            lambda: [{"op": "read", "var": "Current", "src": src},
                     {"op": "read", "var": "Previous", "src": src + "@-1HOUR"}]
                    + iff("Current > Previous", acts),
        "compare it with yesterday at the same time and {a} if it went up":
            lambda: [{"op": "read", "var": "Current", "src": src},
                     {"op": "read", "var": "Previous", "src": src + "@-1DAY"}]
                    + iff("Current > Previous", acts),
        "if that has happened more than {m} times today, {a}":
            lambda: [{"op": "read", "var": "Count", "src": src + "@count:today"}]
                    + iff(f"Count > {m}", acts),
        "count how many times it happens and {a} once it passes {m}":
            lambda: [{"op": "read", "var": "Count", "src": src + "@count:today"}]
                    + iff(f"Count >= {m}", acts),
        "{a} every {n} minutes while {cond}, and stop after {m} hours":
            lambda: cyc(acts, until=f"n >= {reps} or not ({cond})", count="n"),
        "wait until {cond}, then {a} every {n} minutes for {m} hours":
            lambda: [{"op": "wait", "cond": cond, "edge": "rising"}]
                    + cyc(acts, until=f"n >= {reps}", count="n"),
    }
    f = F.get(frame)
    return f() if f else None


def make_ir(*, act, act_tpl, act_cat, vague_tpl, trig_tpl, cat_t, trig_kind,
            frame, cond_text, slots, tslots, lslots, kind, occupancy, notify_svc):
    """한 문장의 정답 IR. 못 만들면 None 을 돌려준다.

    슬롯이 세 벌인 이유: 한 문장에 숫자가 여러 개 들어간다.
    "10분마다 확인해서 선풍기를 20분 돌려라" 의 10 과 20 은 다른 값이다.
      slots  동작절이 고른 값   tslots 시간절이 고른 값   lslots 로직 문형이 고른 값
    """
    import policy
    occ_src = OCC_SRC.get(occupancy or "none", OCC_SRC["none"])
    tslots = dict(tslots)
    for name in ("too_warm_c", "power_spike_w", "gas_danger_ppm"):
        tslots[name] = policy.const(name, kind)
    acts = act_nodes(act=act, tpl=act_tpl, act_cat=act_cat, vague_tpl=vague_tpl,
                     slots=slots, notify_svc=notify_svc, trig_kind=trig_kind,
                     occ_src=occ_src)
    if not acts:
        return None

    # 트리거
    head, wrap_cycle, trig_cond = [], None, None
    anchor = {"op": "start_at", "anchor": "now"}
    if trig_tpl:
        t = TRIG_IR.get(trig_tpl)
        if t is None:
            return None
        if t["cat"] == "*":
            attr = READ_ATTR.get(cat_t)
            if not attr:
                return None
            base = t["cond"].replace("{CAT}", cat_t).replace("{ATTR}", attr)
        else:
            base = t.get("cond")
        if "cron" in t:
            anchor = {"op": "start_at", "anchor": "cron", "cron": cron_of(t["cron"], tslots)}
        elif "cycle" in t:
            wrap_cycle = subst(t["cycle"], tslots)
        elif "delay" in t:
            head = [{"op": "delay", "duration": subst(t["delay"], tslots)}]
        else:
            trig_cond = subst(base, tslots)
            w = {"op": "wait", "cond": trig_cond, "edge": t.get("edge", "rising")}
            if "for" in t:
                w["for"] = subst(t["for"], tslots)
            head = [w]

    # 로직 문형
    if frame:
        cond = _cond(cond_text, occ_src, kind) if "{cond}" in frame else None
        if "{cond}" in frame and cond is None:
            return None
        body = logic_nodes(frame, acts, cond, lslots, trig_cond,
                           power_call(act_cat, False))
        if body is None:
            return None
    else:
        body = acts

    if wrap_cycle:
        body = [{"op": "cycle", "until": None, "period": wrap_cycle, "body": body}]
    out = {"timeline": [anchor] + head + body}
    for n in _walk(out["timeline"]):
        if n.get("op") == "call":
            coerce(n)
    return out


# ── 검산 ───────────────────────────────────────────────────────────────
# 우리가 지어낸 표기 — 카탈로그에 없어도 되는 것들
OURS = {"@-1HOUR", "@-1DAY", "@count:today"}
ARG_ALIAS = {          # 카탈로그의 argument_format 과 정답 IR 의 인자 이름이 다른 자리
    ("Pump", "SetPumpMode"): ["PumpMode"],
    ("Speaker", "Play"): ["MediaSource"],      # 기존 정답 IR 이 쓰는 이름
    ("Light", "MoveToBrightness"): ["Brightness", "Rate"],
    ("Light", "MoveToColorTemperature"): ["ColorTemperature"],
    ("Light", "MoveToHueAndSaturation"): ["Hue", "Saturation"],
    ("Sprinkler", "Start"): ["Minutes"],
    ("ConveyorBelt", "SetBeltSpeed"): ["BeltSpeed"],
    ("Humidifier", "SetTargetHumidity"): ["Humidity"],
    ("Display", "ShowMessage"): ["Message", "DurationSeconds"],
    ("NotificationProvider", "SendPush"): ["Title", "Body"],
    ("NotificationProvider", "SendToast"): ["Message"],
    ("NotificationProvider", "SendAlert"): ["Message", "Level"],
    ("CoffeeMaker", "Brew"): ["Strength"],
    ("ArmRobot", "SendCommand"): ["Command"],
}


def _walk(nodes):
    for n in nodes:
        yield n
        for k in ("then", "else", "body"):
            if isinstance(n.get(k), list):
                yield from _walk(n[k])


def check(cat):
    """표에 적은 서비스·인자·열거값이 카탈로그에 있는가."""
    bad = []

    def one(call, where):
        c0, _, m = call["target"].partition(".")
        if c0 not in cat or m not in cat[c0]:
            bad.append(f"{where}: {call['target']} 가 카탈로그에 없음")
            return
        spec = cat[c0][m]
        want = arg_names(c0, m, spec)
        if set(call["args"]) - set(want) and want:
            bad.append(f"{where}: {call['target']} 인자 {list(call['args'])} ≠ {want}")
        en = spec.get("argument_enums") or []
        if en and "|" not in (spec.get("argument_type") or ""):   # 인자 하나짜리 열거만 본다
            for v in call["args"].values():
                if isinstance(v, str) and not v.startswith("$") and v not in en:
                    bad.append(f"{where}: {call['target']} 값 {v!r} 가 열거값에 없음 {en}")

    for tpl, t in TRIG_IR.items():
        for c0m in re.findall(r"\b([A-Z][A-Za-z]*)\.([A-Za-z0-9]+)", t.get("cond") or ""):
            if c0m[0] == "CAT":
                continue
            if c0m[0] not in cat or c0m[1] not in cat[c0m[0]]:
                bad.append(f"TRIG {tpl!r}: {'.'.join(c0m)} 가 카탈로그에 없음")
    for cat_name, attr in READ_ATTR.items():
        if cat_name not in cat or attr not in cat[cat_name]:
            bad.append(f"READ_ATTR {cat_name}.{attr} 가 카탈로그에 없음")
    for cn, pair in POWER.items():
        if cn not in cat:
            bad.append(f"POWER {cn} 카테고리가 없음")
            continue
        for spec in pair:
            if spec and spec[0] not in cat[cn]:
                bad.append(f"POWER {cn}.{spec[0]} 가 없음")
    for act, d in ACT_IR.items():
        for tpl, raw in d.items():
            if isinstance(raw, str):
                continue
            for x in raw:
                if isinstance(x, dict) and x.get("op") == "call":
                    one(x, f"ACT {act} {tpl!r}")
    for tpl, raw in VAGUE_IR.items():
        if isinstance(raw, str):
            continue
        for x in raw:
            if isinstance(x, dict) and x.get("op") == "call":
                one(x, f"VAGUE {tpl!r}")
    for name, fn in NOTIFY_ARGS.items():
        one(c(name, **fn("x")), "NOTIFY")
    for tpl, q in QUERY_IR.items():
        src = q["read"][1]
        if src != "$OCCUPANCY":
            c0, _, m = src.partition(".")
            if c0 not in cat or m not in cat[c0]:
                bad.append(f"QUERY {tpl!r}: {src} 가 카탈로그에 없음")
    return bad


OPS = {"start_at", "call", "if", "wait", "cycle", "read", "delay", "break"}
OP_SLOTS = {"start_at": {"anchor", "cron"}, "call": {"target", "args", "var"},
            "if": {"cond", "then", "else"}, "wait": {"cond", "edge", "for", "timeout"},
            "cycle": {"until", "period", "body", "count"}, "read": {"var", "src"},
            "delay": {"duration"}, "break": set()}
_DUR = re.compile(r"^-?\d+(\.\d+)?\s(MSEC|SEC|MIN|HOUR)$")
_CRON = re.compile(r"^\d{1,2} \d{1,2} \* \* (\*|[0-9,\-]+)$")
_SVCREF = re.compile(r"\b([A-Z][A-Za-z0-9]*)\.([A-Za-z0-9]+)")


def check_ir(obj, cat, where, space_cats=None):
    """만들어진 IR 하나가 규약과 카탈로그에 맞는가."""
    bad = []

    def svc_ok(name):
        c0, _, m = name.partition(".")
        return c0 in cat and m in cat[c0]

    def cond_ok(txt):
        for c0, m in _SVCREF.findall(txt or ""):
            if c0 in ("MIN", "HOUR", "SEC", "MSEC"):
                continue
            if not svc_ok(f"{c0}.{m}"):
                bad.append(f"{where}: 조건의 {c0}.{m} 가 카탈로그에 없음")

    def walk(ns, depth=0):
        for n in ns:
            op = n.get("op")
            if op not in OPS:
                bad.append(f"{where}: 모르는 op {op}")
                continue
            extra = set(n) - OP_SLOTS[op] - {"op"}
            if extra:
                bad.append(f"{where}: {op} 에 모르는 슬롯 {sorted(extra)}")
            if op == "call":
                if not svc_ok(n["target"]):
                    bad.append(f"{where}: {n['target']} 가 카탈로그에 없음")
                elif space_cats is not None:
                    c0 = n["target"].split(".")[0]
                    if c0 not in space_cats and c0 != "Switch":
                        bad.append(f"{where}: {c0} 가 그 공간에 없음")
            elif op == "start_at":
                if depth:
                    bad.append(f"{where}: start_at 이 안쪽에 있음")
                if n["anchor"] == "cron" and not _CRON.match(n.get("cron", "")):
                    bad.append(f"{where}: cron 형식 {n.get('cron')!r}")
            elif op == "wait":
                cond_ok(n["cond"])
                if n["edge"] not in ("none", "rising", "falling"):
                    bad.append(f"{where}: edge {n['edge']!r}")
                for k in ("for", "timeout"):
                    if k in n and not _DUR.match(str(n[k])):
                        bad.append(f"{where}: {k} 형식 {n[k]!r}")
            elif op == "delay":
                if not _DUR.match(str(n["duration"])):
                    bad.append(f"{where}: duration 형식 {n['duration']!r}")
            elif op == "cycle":
                if not _DUR.match(str(n["period"])):
                    bad.append(f"{where}: period 형식 {n['period']!r}")
                cond_ok(n["until"])
                if "n >" in str(n["until"] or "") and n.get("count") != "n":
                    bad.append(f"{where}: 반복수를 안 세면서 n 을 씀")
                walk(n["body"], depth + 1)
            elif op == "if":
                cond_ok(n["cond"])
                walk(n["then"], depth + 1)
                walk(n["else"], depth + 1)
            elif op == "read":
                src = re.sub(r"@.*$", "", n["src"])
                if not src.startswith("GlobalVariable") and not svc_ok(src):
                    bad.append(f"{where}: 읽을 {n['src']} 가 카탈로그에 없음")

    tl = obj.get("timeline")
    if not tl or tl[0].get("op") != "start_at":
        return [f"{where}: start_at 으로 시작하지 않음"]
    if len(tl) < 2:
        bad.append(f"{where}: 동작이 없음")
    walk(tl)
    return bad


def main():
    cat = json.load(open(CATALOG, encoding="utf-8"))
    bad = check(cat)
    n_scene = sum(len(v) for v in SCENE.values())
    print(f"ir.py — 트리거 틀 {len(TRIG_IR)} · 동작 틀 "
          f"{sum(len(v) for v in ACT_IR.values())} · 의도 틀 {len(VAGUE_IR)} · "
          f"조회 {len(QUERY_IR)} · 조건 {len(COND_IR)} · 장면 {len(SCENE)}종 {n_scene}칸")
    if bad:
        print("검산:", *bad[:25], sep="\n  ")
        print(f"  … 모두 {len(bad)}건")
    else:
        print("검산: 카탈로그와 어긋난 것 없음 ✅")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())


# ── 방아쇠가 무엇을 읽나 ────────────────────────────────────────────────
# "한 시간 전보다 높으면" 같은 문형은 숫자를 읽는 방아쇠에만 붙어야 한다.
# 버튼 눌림이나 문 열림을 크고 작음으로 견줄 수는 없다.
NUM_RETURN = {"INTEGER", "DOUBLE"}


def _cat_json():
    # 위의 _catalog() 를 그대로 쓴다. 예전에 여기서 _CAT_CACHE 를 다시 만들어
    # 앞의 캐시를 가렸다 — coerce() 가 None 을 받는 잠복 버그였다.
    return _catalog()


def trig_reads(tpl):
    """그 방아쇠가 읽는 값. 시각·타이머처럼 조건이 없으면 빈 문자열."""
    e = TRIG_IR.get(tpl) or {}
    c = e.get("cond") or ""
    return _lhs(c) if c else ""


def reads_number(tpl):
    """그 방아쇠가 읽는 값이 숫자인가."""
    src = trig_reads(tpl)
    if "." not in src:
        return False
    c, a = src.split(".", 1)
    d = (_cat_json().get(c) or {}).get(a) or {}
    return d.get("return_type") in NUM_RETURN
