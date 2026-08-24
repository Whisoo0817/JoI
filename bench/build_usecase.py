#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""joi usecase 616문장 → 우리 벤치마크 행(U0001~) — 4단계. dataset_5k.csv 뒤에 얹는다.

플랫폼 개발자가 준 dataset-usecase.xlsx(한국어 씨앗 616문장, 5개 도메인)를
우리 문장·공간·정답으로 옮긴다. 씨앗 문장은 한 줄도 싣지 않는다 — 뜻만 가져오고
영어 문장은 전부 새로 쓴다. 공간은 그 기기를 실제로 가진 곳으로 고른다.

  python bench/build_usecase.py          # 검산 + dataset_5k.csv 에 U행 반영(멱등)

싣지 않는 것 (36행) — 왜:
  자동화 관리(목록·수정·삭제) 16   그 서비스가 카탈로그에 없다. 나중 일.
  시스템 자기설명(Help·기기목록) 9  기기가 아니라 허브가 자기 카탈로그로 답할 일.
  일반 대화(인사·잡담) 6           IoT 명령이 아니다.
  "확인 없이 ~" 3                  확인 버튼은 실행 UI 의 일 — 판정 축이 아니다(whisoo).
  기기 한 대만 능력이 없는 경우 2   카탈로그가 카테고리 단위라 "색 안 되는 조명"이 없다.

판정 규칙 — 기존 5,000과 같은 원칙에 몇 가지를 보탠다:
  confirm / execute-confirm → execute   확인 버튼은 모든 실행에 붙는다(whisoo 결정)
  answer → execute                      read + 알림. 값 하나로 답이 정해지면 실행이다
  열린 요약·다기기 모드 → ask           "상태 어때?", "외출 모드" — 무엇을 읽을지/할지 미정
  주소가 필요한 채널(문자·카톡·메일) → ask   받는 주소를 모른다. 알림(notify)은 안 묻는다
  슬랙 → execute                        팀 채널이라 주소가 없다 (3.1.0 SendSlack)
  예보·"10분 전" → refuse no_service    WeatherProvider 에 예보가, 달력에 예측 대기가 없다
  기록 나열·주간 요약 → refuse no_service  기록을 나열하는 서비스가 없다
  과거 값 → read 의 @표기               @-1HOUR/@-1DAY/@count:today (기존) +
                                        @avg|min|max:today, @avg:yesterday, @diff:today (3.1.0)
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ir as IR                    # noqa: E402
import policy as PL                # noqa: E402

CAT = json.load(open(os.path.join(HERE, "..", "files", "service_list_ver3.1.0.json"),
                     encoding="utf-8"))
S = json.load(open(os.path.join(HERE, "spaces.json"), encoding="utf-8"))["spaces"]
csv.field_size_limit(10 ** 7)

CATS = {sid: set().union(*(set(v["category"]) for v in sp["devices"].values()))
        for sid, sp in S.items()}


def devs(sid, cat, room=None, nick=None):
    out = []
    for did, v in S[sid]["devices"].items():
        if cat not in v["category"]:
            continue
        if room and not did.startswith(f"{sid}_{room}_"):
            continue
        if nick and nick not in (v.get("nickname") or ""):
            continue
        out.append(did)
    return sorted(out)


# ── IR 조각 ────────────────────────────────────────────────────────────
NOW = {"op": "start_at", "anchor": "now"}


def CRON(x):
    return {"op": "start_at", "anchor": "cron", "cron": x}


def CL(target, **args):
    return IR.coerce({"op": "call", "target": target, "args": args})


def PON(cat):
    return IR.power_call(cat, True)


def POFF(cat):
    return IR.power_call(cat, False)


def W(cond, edge="rising", for_=None):
    d = {"op": "wait", "cond": cond, "edge": edge}
    if for_:
        d["for"] = for_
    return d


def DL(dur):
    return {"op": "delay", "duration": dur}


def CY(period, body, until=None):
    return {"op": "cycle", "until": until, "period": period, "body": body}


def RD(var, src):
    return {"op": "read", "var": var, "src": src}


def IF(cond, then, els=None):
    return {"op": "if", "cond": cond, "then": then, "else": els or []}


DARK = 'SunProvider.SunState == "belowHorizon"'


def occ(sid, present):
    """이 공간의 재실 조건 — 재실 주체(occupancy)가 공간마다 정해져 있다."""
    o = S[sid].get("occupancy")
    v = "true" if present else "false"
    if o == "motion":
        return f"MotionSensor.Motion == {v}"
    if o == "presence":
        return f"PresenceSensor.Presence == {v}"
    if o == "phone":
        return f"PersonTracker.IsHome == {v}"
    return f'GlobalVariable.Value("occupancy") == {v}'


_LAST_SVC = [""]


def nn(sid, msg):
    """알림 노드 — 채널은 policy.NOTIFY_ORDER 가 공간을 보고 정한다."""
    for svc, need in PL.NOTIFY_ORDER:
        c0 = svc.split(".")[0]
        if c0 in CATS[sid] and (not need or need in CATS[sid]):
            _LAST_SVC[0] = svc
            return IR.c(svc, **IR.NOTIFY_ARGS[svc](msg))
    raise AssertionError(f"{sid}: 알림 채널이 없다")


def tsvc():
    return _LAST_SVC[0]


# ── 행 조립 ────────────────────────────────────────────────────────────
ROWS = []


def _resolve(sid, sel):
    ids = []
    for s in sel or []:
        if isinstance(s, str):
            assert s in S[sid]["devices"], f"{sid}: 기기 {s} 없음"
            ids.append(s)
        else:
            cat, room, nick = (list(s) + [None, None])[:3]
            got = devs(sid, cat, room, nick)
            assert got, f"{sid}: {s} 기기 없음"
            ids += got
    return list(dict.fromkeys(ids))


def _row(idx, en, sid, **kw):
    ids = kw.pop("targets", [])
    ROWS.append(dict(
        idx=idx, space_id=sid, kind=S[sid]["kind"], command=en, mode="usecase",
        trig=kw.get("trig", "now"), act=kw["act"],
        dev_trig=kw.get("dev_trig", ""), dev_act=kw.get("dev_act", ""),
        ref=kw.get("ref", "plain"), tone=kw.get("tone", "bare"),
        expect=kw["expect"], d=kw.get("d", "D1"), tier=kw.get("tier", "T0"),
        b1=kw.get("b1", "act"), b3=str(kw.get("b3", 1)),
        context=kw.get("ctx", "none"), why=kw.get("why", ""),
        targets=" ".join(ids), n_target=str(len(ids)),
        target_svc=kw.get("tsvc", ""), match=kw["match"],
        ir_gt=(json.dumps({"timeline": kw["ir"]}, ensure_ascii=False)
               if kw.get("ir") else "")))


def X(idx, en, sid, ir, tgt=(), **kw):
    """실행 행. tgt = [(카테고리, 방, 별명조각) ...] 또는 기기 id."""
    ids = _resolve(sid, tgt)
    if "dev_act" not in kw:
        kw["dev_act"] = (tgt[0][0] if tgt and not isinstance(tgt[0], str) else
                         ("NotificationProvider" if kw.get("act") == "notify" else ""))
    if "b3" not in kw:
        kw["b3"] = max(1, len({S[sid]["devices"][d]["category"][0] for d in ids})) \
            if ids else 1
    kw.setdefault("ref", "place" if (tgt and not isinstance(tgt[0], str)
                                     and len(tgt[0]) > 1 and tgt[0][1]) else "plain")
    _row(idx, en, sid, expect="execute", match="all", ir=ir, targets=ids, **kw)


def A(idx, en, sid, cands=(), **kw):
    """되묻기 행. cands 는 후보 기기(정의된 후보가 없으면 빈 채로)."""
    ids = _resolve(sid, cands) if cands else []
    kw.setdefault("dev_act", cands[0][0] if cands and not isinstance(cands[0], str) else "")
    _row(idx, en, sid, expect="ask", match="ask", targets=ids, **kw)


def RF(idx, en, sid, why, **kw):
    """거절 행. why = no_device | no_service | no_channel | no_context."""
    _row(idx, en, sid, expect="refuse", match="none", why=why, targets=[], **kw)


def Q(idx, en, sid, src, var, msg, tgt=(), extra=(), body=None, **kw):
    """조회 행 — read + 알림. src 'Cat.Attr[@표기]'. 과거는 extra 로 더 읽는다."""
    note = [nn(sid, msg)] if body is None else body
    nodes = [NOW, RD(var, src)] + [RD(v2, s2) for v2, s2 in extra] + note
    ids = _resolve(sid, tgt)
    kw.setdefault("b1", "read")
    kw.setdefault("act", "query")
    kw.setdefault("dev_act", src.split(".")[0])
    kw.setdefault("tone", "ask")
    kw.setdefault("tsvc", tsvc())
    _row(idx, en, sid, expect="execute", match="all", ir=nodes, targets=ids, **kw)


HUE = IR.HUE  # red 0, blue 240, ...
WARM, COOL = 2700, 5500


def hue(name):
    return CL("Light.MoveToHueAndSaturation", Hue=float(HUE[name]), Saturation=100.0)


def bright(n):
    return CL("Light.MoveToBrightness", Brightness=float(n), Rate=0.0)


def ctemp(k):
    return CL("Light.MoveToColorTemperature", ColorTemperature=int(k))


# ══ home (0–146) ═══════════════════════════════════════════════════════
def sheet_home():
    H6, H3, H9, H15, H5 = "HOME06", "HOME03", "HOME09", "HOME15", "HOME05"
    # ── 기기 직접 제어 ──
    X(0, "Turn on the living room lights.", H6, [NOW, PON("Light")],
      [("Light", "LivingRoom")], act="light.on")
    X(1, "Turn off the bedroom lights.", H6, [NOW, POFF("Light")],
      [("Light", "Bedroom")], act="light.off")
    X(2, "Turn off all the lights in the house.", H6, [NOW, POFF("Light")],
      [("Light",)], act="light.off", ref="all")
    X(3, "Turn on the living room plugs.", H15, [NOW, PON("Plug")],
      [("Plug", "LivingRoom")], act="plug")
    A(4, "Switch off the power strip.", H15, [("Plug",)], act="plug", ref="plain")
    X(5, "Turn on the air conditioner, please.", H15,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner",)], act="ac", tone="polite")
    X(6, "Turn off the air purifier.", H3,
      [NOW, CL("AirPurifier.SetAirPurifierMode", Mode="off")],
      [("AirPurifier",)], act="purifier")
    X(7, "Start the humidifier.", H9,
      [NOW, CL("Humidifier.SetHumidifierMode", Mode="auto")],
      [("Humidifier",)], act="humidity")
    X(8, "Close the curtain.", H9, [NOW, CL("WindowCovering.DownOrClose")],
      [("WindowCovering",)], act="cover")
    X(9, "Raise the blinds.", H3, [NOW, CL("WindowCovering.UpOrOpen")],
      [("WindowCovering",)], act="cover")
    X(10, "Open the living room curtains.", H3, [NOW, CL("WindowCovering.UpOrOpen")],
      [("WindowCovering", "LivingRoom")], act="cover")
    X(11, "Start the robot vacuum.", H6,
      [NOW, CL("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="auto")],
      [("RobotVacuumCleaner",)], act="vacuum")
    X(12, "Stop the vacuuming.", H6,
      [NOW, CL("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="stop")],
      [("RobotVacuumCleaner",)], act="vacuum")
    X(13, "Turn off the TV.", H6, [NOW, POFF("Television")],
      [("Television",)], act="media")
    # ── 기기 속성 조절 ──
    X(14, "Set the living room lights to 50 percent.", H6, [NOW, bright(50)],
      [("Light", "LivingRoom")], act="light.dim", b1="set")
    A(15, "Make the lights a bit brighter.", H6, [("Light",)],
      act="light.dim", ref="vague", b1="set")
    X(16, "Dim the bedroom lights to 20 percent.", H6, [NOW, bright(20)],
      [("Light", "Bedroom")], act="light.dim", b1="set")
    X(17, "Turn the bedroom lights blue.", H6, [NOW, hue("blue")],
      [("Light", "Bedroom")], act="light.color", b1="set")
    X(18, "Set the living room lights to a warm color.", H6, [NOW, ctemp(WARM)],
      [("Light", "LivingRoom")], act="light.color", b1="set")
    X(19, "Change the kitchen lights to a cool white.", H6, [NOW, ctemp(COOL)],
      [("Light", "Kitchen")], act="light.color", b1="set")
    X(20, "Set the air conditioner to 24 degrees.", H15,
      [NOW, CL("AirConditioner.SetTargetTemperature", Temperature=24.0)],
      [("AirConditioner",)], act="ac", b1="set")
    X(21, "Set the heating to 22 degrees.", "HOME16",
      [NOW, CL("Thermostat.SetThermostatMode", Mode="heat"),
       CL("Thermostat.SetTargetTemperature", Temperature=22.0)],
      [("Thermostat",)], act="thermostat", b1="set")
    X(22, "Turn the living room temperature down to 22 degrees.", H5,
      [NOW, CL("Thermostat.SetTargetTemperature", Temperature=22.0)],
      [("Thermostat",)], act="thermostat", b1="set")
    X(23, "Set the living room fans to high.", H3,
      [NOW, CL("Fan.SetFanMode", Mode="high")],
      [("Fan", "LivingRoom")], act="fan", b1="set")
    X(24, "Put the baby room air purifier on auto.", H9,
      [NOW, CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier", "BabyRoom")], act="purifier", b1="set")
    X(25, "Switch the air conditioner to heat mode.", H15,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="heat")],
      [("AirConditioner",)], act="ac", b1="set")
    A(26, "Turn the speaker volume down.", H6, [("Speaker",)],
      act="speaker", b1="set")
    X(27, "Turn up the living room speakers.", H6, [NOW, CL("Speaker.VolumeUp")],
      [("Speaker", "LivingRoom")], act="speaker", b1="set")
    X(28, "Set the TV volume to 30.", H6, [NOW, CL("Television.SetVolume", Volume=30)],
      [("Television",)], act="media", b1="set")
    # ── 공간/기기 상태 조회 ──
    Q(29, "What is the temperature in the living room right now?", H6,
      "TemperatureSensor.Temperature", "Temperature", "The temperature is $Temperature",
      [("TemperatureSensor", "LivingRoom")], ref="place")
    Q(30, "Is the air quality in the house okay?", H3,
      "AirQualitySensor.VeryFineDustLevel", "Dust", "The fine dust level is $Dust",
      [("AirQualitySensor",)])
    Q(31, "What is the humidity in the living room?", H6,
      "HumiditySensor.Humidity", "Humidity", "The humidity is $Humidity",
      [("HumiditySensor", "LivingRoom")], ref="place")
    Q(32, "Is the air conditioner on?", H15,
      "AirConditioner.AirConditionerMode", "Mode", "The air conditioner is $Mode",
      [("AirConditioner",)])
    Q(33, "Is the air purifier running?", H3,
      "AirPurifier.AirPurifierMode", "Mode", "The air purifier is $Mode",
      [("AirPurifier",)])
    Q(34, "Are the living room lights off?", H6,
      "Switch.Switch", "Switch", "The lights are $Switch",
      [("Light", "LivingRoom")], dev_act="Light", ref="place")
    Q(35, "Is the front door open?", H6,
      "ContactSensor.Contact", "Contact", "The door contact reads $Contact",
      [("ContactSensor", "Entrance")], ref="place")
    Q(36, "Are the living room windows closed?", H6,
      "ContactSensor.Contact", "Contact", "The window contact reads $Contact",
      [("ContactSensor", "LivingRoom")], ref="place")
    Q(37, "Tell me the state of the balcony door.", H3,
      "ContactSensor.Contact", "Contact", "The balcony door contact reads $Contact",
      [("ContactSensor", "Balcony")], ref="place", tone="bare")
    Q(38, "Is anyone home?", H5,
      "MotionSensor.Motion", "Motion", "Motion reads $Motion",
      [("MotionSensor",)])
    Q(39, "Was motion detected in the living room?", "HOME16",
      "MotionSensor.Motion", "Motion", "Motion reads $Motion",
      [("MotionSensor", "LivingRoom")], ref="place")
    Q(40, "Is nobody home right now?", "HOME16",
      "MotionSensor.Motion", "Motion", "Motion reads $Motion",
      [("MotionSensor",)])
    Q(41, "How much power is the house using right now?", H15,
      "EnergyMeter.Power", "Power", "The power draw is $Power",
      [("EnergyMeter",)])
    Q(42, "How much power are the living room plugs using?", H15,
      "Plug.Power", "Power", "The plug power draw is $Power",
      [("Plug", "LivingRoom")], ref="place")
    Q(43, "Is today's electricity use high?", H15,
      "EnergyMeter.EnergyConsumed@diff:today", "Used", "Today's usage is $Used",
      [("EnergyMeter",)], d="D12", tier="T4")
    # ── 조건 기반 자동화 ──
    X(44, "When nobody is home, turn off the lights.", H5,
      [NOW, W(occ(H5, False)), POFF("Light")], [("Light",)],
      act="light.off", trig="presence", dev_trig="MotionSensor", d="D4", tier="T1")
    X(45, "When someone comes home, turn on the stairs light.", H5,
      [NOW, W(occ(H5, True)), PON("Light")], [("Light", "Stairs")],
      act="light.on", trig="presence", dev_trig="MotionSensor", d="D4", tier="T1")
    X(46, "If nobody is home, turn off the air conditioner.", H5,
      [NOW, W(occ(H5, False)), CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="presence", dev_trig="MotionSensor",
      d="D4", tier="T1")
    X(47, "Let me know when the front door opens.", H6,
      [NOW, W("ContactSensor.Contact == false"), nn(H6, "The door has opened")],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D4", tier="T1",
      tsvc=tsvc())
    X(48, "If the window is open, turn off the air conditioner.", H6,
      [NOW, W("ContactSensor.Contact == false"),
       CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="contact", dev_trig="ContactSensor",
      d="D4", tier="T1")
    X(49, "When the door closes, turn off the hallway light.", H6,
      [NOW, W("ContactSensor.Contact == true"), POFF("Light")],
      [("Light", "Hallway")], act="light.off", trig="contact",
      dev_trig="ContactSensor", d="D4", tier="T1")
    X(50, "If the temperature goes above 28 degrees, turn on the air conditioner.", H15,
      [NOW, W("TemperatureSensor.Temperature > 28"),
       CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner",)], act="ac", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    X(51, "If the humidity gets low, turn on the humidifier.", H9,
      [NOW, W("HumiditySensor.Humidity < 30"),
       CL("Humidifier.SetHumidifierMode", Mode="auto")],
      [("Humidifier",)], act="humidity", trig="threshold",
      dev_trig="HumiditySensor", d="D4", tier="T1")
    X(52, "If the CO2 gets high, let me know.", H3,
      [NOW, W("AirQualitySensor.CarbonDioxide > 1000"),
       nn(H3, "The sensor passed its threshold")],
      [], act="notify", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(53, "When it gets dark outside, turn on the living room lights.", H15,
      [NOW, W("LightSensor.Brightness < 50"), PON("Light")],
      [("Light", "LivingRoom")], act="light.on", trig="threshold",
      dev_trig="LightSensor", d="D4", tier="T1")
    X(54, "When the sun sets, close the curtains.", H3,
      [NOW, W(DARK), CL("WindowCovering.DownOrClose")],
      [("WindowCovering",)], act="cover", trig="sun", dev_trig="SunProvider",
      d="D4", tier="T1", ctx="sun")
    X(55, "When it is bright, turn off the lights.", H15,
      [NOW, W("LightSensor.Brightness > 1000"), POFF("Light")],
      [("Light",)], act="light.off", trig="threshold", dev_trig="LightSensor",
      d="D4", tier="T1", ref="plain")
    X(56, "When the TV turns on, dim the living room lights.", H6,
      [NOW, W('Switch.Switch == true'), bright(20)],
      [("Light", "LivingRoom")], act="light.dim", trig="device",
      dev_trig="Television", d="D4", tier="T1")
    X(57, "Tell me when the laundry is done.", H6,
      [NOW, W("LaundryWasher.RemainingTime == 0"), nn(H6, "The machine has finished")],
      [], act="notify", trig="finished", dev_trig="LaundryWasher", d="D4", tier="T1",
      tsvc=tsvc())
    X(58, "If the air purifier turns off, turn it back on.", H3,
      [NOW, W('AirPurifier.AirPurifierMode == "off"'),
       CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier", trig="device", dev_trig="AirPurifier",
      d="D4", tier="T1")
    # ── 시간/스케줄 자동화 ──
    X(59, "Turn off all the lights at 11 pm.", H6, [CRON("0 23 * * *"), POFF("Light")],
      [("Light",)], act="light.off", trig="time", dev_trig="Clock", d="D6", tier="T1",
      ref="all")
    X(60, "Open the curtains at 7 am.", H3, [CRON("0 7 * * *"),
      CL("WindowCovering.UpOrOpen")], [("WindowCovering",)], act="cover",
      trig="time", dev_trig="Clock", d="D6", tier="T1")
    X(61, "Turn off the air conditioner at 6 pm.", H15, [CRON("0 18 * * *"),
      CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="time", dev_trig="Clock", d="D6", tier="T1")
    X(62, "Turn on the air purifier every morning at 8.", H3, [CRON("0 8 * * *"),
      CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(63, "Turn on the living room lights at 7 pm on weekdays.", H6,
      [CRON("0 19 * * 1-5"), PON("Light")], [("Light", "LivingRoom")],
      act="light.on", trig="time", dev_trig="Clock", d="D6", tier="T1")
    X(64, "Run the robot vacuum every weekend at 10.", H6, [CRON("0 10 * * 0,6"),
      CL("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="auto")],
      [("RobotVacuumCleaner",)], act="vacuum", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(65, "Turn off the air conditioner in 10 minutes.", H15,
      [NOW, DL("10 MIN"), CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="timer", dev_trig="Clock",
      d="D2", tier="T2")
    X(66, "Turn off the bedroom lights in an hour.", H6,
      [NOW, DL("1 HOUR"), POFF("Light")], [("Light", "Bedroom")],
      act="light.off", trig="timer", dev_trig="Clock", d="D2", tier="T2")
    A(67, "Turn off the air purifier in a little while.", H3, [("AirPurifier",)],
      act="purifier", trig="timer", dev_trig="Clock", ref="plain")
    X(68, "Run the air purifier for 30 minutes.", H3,
      [NOW, CL("AirPurifier.SetAirPurifierMode", Mode="auto"), DL("30 MIN"),
       CL("AirPurifier.SetAirPurifierMode", Mode="off")],
      [("AirPurifier",)], act="purifier", trig="timer", dev_trig="Clock",
      d="D2", tier="T2")
    X(69, "Run the air conditioner for just 2 hours.", H15,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="cool"), DL("2 HOUR"),
       CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="timer", dev_trig="Clock",
      d="D2", tier="T2")
    X(70, "Keep the hallway light on for 10 minutes.", H6,
      [NOW, PON("Light"), DL("10 MIN"), POFF("Light")], [("Light", "Hallway")],
      act="light.on", trig="timer", dev_trig="Clock", d="D2", tier="T2")
    X(71, "At night, if motion is detected, turn the lights on low.", H5,
      [NOW, W("MotionSensor.Motion == true"), IF(DARK, [bright(20)])],
      [("Light",)], act="light.dim", trig="motion", dev_trig="MotionSensor",
      d="D13", tier="T2", ctx="sun", ref="plain")
    X(72, "In the morning, open the baby room curtain.", H9,
      [CRON("0 7 * * *"), CL("WindowCovering.UpOrOpen")],
      [("WindowCovering", "BabyRoom")], act="cover", trig="time",
      dev_trig="Clock", d="D6", tier="T1")
    A(73, "Late at night, don't turn off the speaker alerts.", H6, [("Speaker",)],
      act="speaker", trig="time", dev_trig="Clock", ref="plain")
    # ── 장면/모드 실행 — 다기기 묶음 모드는 정의가 없으므로 전부 되묻기 ──
    A(74, "I'm heading out.", H6, [], act="light.scene", ref="vague", tone="terse")
    A(75, "Turn on away mode.", H6, [], act="light.scene", ref="vague")
    A(76, "Make it like when the house is empty.", H6, [], act="light.scene",
      ref="vague")
    A(77, "I'm home now.", H6, [], act="light.scene", ref="vague", tone="terse")
    A(78, "Run the coming-home mode.", H6, [], act="light.scene", ref="vague")
    A(79, "Get the house ready for me.", H6, [], act="light.scene", ref="vague")
    A(80, "Get things ready for bed.", H6, [], act="light.scene", ref="vague")
    A(81, "Turn on sleep mode.", H6, [], act="light.scene", ref="vague")
    A(82, "Make it like bedtime.", H6, [], act="light.scene", ref="vague")
    A(83, "Get ready for a movie.", H6, [], act="light.scene", ref="vague")
    A(84, "Switch to relax mode.", H6, [], act="light.scene", ref="vague")
    A(85, "Set a nice mood in here.", H6, [], act="light.scene", ref="vague")
    X(86, "Run the cleaning mode.", H6,
      [NOW, CL("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="auto")],
      [("RobotVacuumCleaner",)], act="vacuum")
    A(87, "Turn on ventilation mode.", H3, [], act="fan", ref="vague")
    A(88, "Get the air circulating in the house.", H3, [], act="fan", ref="vague")
    # ── 안전/보안 요청 ──
    X(89, "Lock the front door.", H6, [NOW, CL("DoorLock.Lock")],
      [("DoorLock", "Entrance")], act="lock")
    Q(90, "Is the door lock locked?", H6, "DoorLock.LockState", "Lock",
      "The door lock is $Lock", [("DoorLock",)])
    X(91, "Lock the front door when I leave.", H6,
      [NOW, W(occ(H6, False)), CL("DoorLock.Lock")], [("DoorLock", "Entrance")],
      act="lock", trig="leave", dev_trig="GlobalVariable", d="D4", tier="T1")
    X(92, "Open the front door.", H6, [NOW, CL("DoorLock.Unlock")],
      [("DoorLock", "Entrance")], act="lock")
    X(93, "Unlock the door lock.", "HOME08", [NOW, CL("DoorLock.Unlock")],
      [("DoorLock",)], act="lock")
    X(94, "Could you unlock the door?", "HOME12", [NOW, CL("DoorLock.Unlock")],
      [("DoorLock",)], act="lock", tone="could")
    X(95, "If there is motion while I'm out, let me know.", H6,
      [NOW, W("MotionSensor.Motion == true"), IF(occ(H6, False),
       [nn(H6, "Motion was detected")])],
      [], act="notify", trig="motion", dev_trig="MotionSensor", d="D13", tier="T2",
      tsvc=tsvc())
    X(96, "If the door opens while nobody is home, warn me.", H6,
      [NOW, W("ContactSensor.Contact == false"), IF(occ(H6, False),
       [nn(H6, "The door has opened")])],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D13", tier="T2",
      tsvc=tsvc())
    X(97, "If motion is detected while I'm away, take a snapshot.", H6,
      [NOW, W("MotionSensor.Motion == true"), IF(occ(H6, False),
       [CL("Camera.CaptureImage")])],
      [("Camera",)], act="camera", trig="motion", dev_trig="MotionSensor",
      d="D13", tier="T2")
    X(98, "Show me the living room camera.", H15, [NOW, CL("Camera.StartStream")],
      [("Camera", "LivingRoom")], act="camera")
    X(99, "When the door opens, take a picture.", H6,
      [NOW, W("ContactSensor.Contact == false"), CL("Camera.CaptureImage")],
      [("Camera",)], act="camera", trig="contact", dev_trig="ContactSensor",
      d="D4", tier="T1")
    X(100, "If motion is detected, record a 10-second clip.", "HOME16",
      [NOW, W("MotionSensor.Motion == true"), CL("Camera.CaptureVideo", Seconds=10.0)],
      [("Camera",)], act="camera", trig="motion", dev_trig="MotionSensor",
      d="D4", tier="T1")
    X(101, "If smoke is detected, warn me.", H6,
      [NOW, W("SmokeDetector.Smoke == true"), nn(H6, "Smoke was detected")],
      [], act="notify", trig="smoke", dev_trig="SmokeDetector", d="D4", tier="T1",
      tsvc=tsvc())
    X(102, "If gas is detected, sound the siren.", "HOME10",
      [NOW, W("GasSensor.Gas == true"), CL("Siren.SetSirenMode", Mode="gas")],
      [("Siren",)], act="siren", trig="gas", dev_trig="GasSensor", d="D4", tier="T1")
    X(103, "If water leaks, let me know.", "HOME14",
      [NOW, W("LeakSensor.Leakage == true"), nn("HOME14", "A leak was detected")],
      [], act="notify", trig="leak", dev_trig="LeakSensor", d="D4", tier="T1",
      tsvc=tsvc())
    # ── 알림/보고 요청 ──
    X(104, "When the door opens, show a notification on the screen.", H6,
      [NOW, W("ContactSensor.Contact == false"),
       CL("NotificationProvider.SendToast", Message="The door has opened")],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D4", tier="T1",
      tsvc="NotificationProvider.SendToast")
    X(105, "If the air quality gets bad, put an alert on the screen.", H3,
      [NOW, W("AirQualitySensor.VeryFineDustLevel > 36"),
       CL("NotificationProvider.SendToast", Message="The air quality is bad")],
      [], act="notify", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1", tsvc="NotificationProvider.SendToast")
    X(106, "Send a push alert when the laundry finishes.", H6,
      [NOW, W("LaundryWasher.RemainingTime == 0"),
       CL("NotificationProvider.SendPush", Title="Home",
          Body="The machine has finished")],
      [], act="notify", trig="finished", dev_trig="LaundryWasher", d="D4", tier="T1",
      tsvc="NotificationProvider.SendPush")
    X(107, "If the CO2 gets high, say it on the speaker.", H3,
      [NOW, W("AirQualitySensor.CarbonDioxide > 1000"),
       CL("Speaker.Speak", Text="The CO2 level is high")],
      [("Speaker",)], act="speaker", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1")
    X(108, "When the front door opens, announce it out loud.", H3,
      [NOW, W("ContactSensor.Contact == false"),
       CL("Speaker.Speak", Text="The door has opened")],
      [("Speaker",)], act="speaker", trig="contact", dev_trig="ContactSensor",
      d="D4", tier="T1")
    X(109, "If the air quality gets bad, broadcast that we should ventilate.", H9,
      [NOW, W("AirQualitySensor.VeryFineDustLevel > 36"),
       CL("Speaker.Speak", Text="Please ventilate the room")],
      [("Speaker",)], act="speaker", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1")
    A(110, "When the door opens, send me a KakaoTalk message.", "HOME10", [],
      act="notify", trig="contact", dev_trig="ContactSensor",
      dev_act="MessageSender", d="D4", tier="T1")
    A(111, "If an intruder is detected, message the property manager.", "HOME16", [],
      act="notify", trig="motion", dev_trig="MotionSensor",
      dev_act="MessageSender", d="D4", tier="T1")
    A(112, "Email me when the door opens.", H15, [], act="notify", trig="contact",
      dev_trig="ContactSensor", dev_act="EmailProvider", d="D4", tier="T1")
    A(113, "Email me a snapshot from the camera.", H15, [], act="camera",
      dev_act="EmailProvider")
    X(114, "While the door stays open, remind me every 10 minutes.", H6,
      [NOW, W("ContactSensor.Contact == false"),
       CY("10 MIN", [nn(H6, "The door has opened")],
          until="not (ContactSensor.Contact == false)")],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D9", tier="T3",
      tsvc=tsvc())
    X(115, "While the CO2 stays high, alert me again every 30 minutes.", H3,
      [NOW, W("AirQualitySensor.CarbonDioxide > 1000"),
       CY("30 MIN", [nn(H3, "The CO2 level is high")],
          until="not (AirQualitySensor.CarbonDioxide > 1000)")],
      [], act="notify", trig="threshold", dev_trig="AirQualitySensor",
      d="D9", tier="T3", tsvc=tsvc())
    X(116, "If the leak continues, keep warning me.", "HOME07",
      [NOW, W("LeakSensor.Leakage == true"),
       CY("5 MIN", [nn("HOME07", "A leak was detected")],
          until="not (LeakSensor.Leakage == true)")],
      [], act="notify", trig="leak", dev_trig="LeakSensor", d="D9", tier="T3",
      tsvc=tsvc())
    # ── 일상 정보/대화 ──
    Q(117, "Is it raining today?", H6, "WeatherProvider.Weather", "Weather",
      "The weather is $Weather", [], ctx="weather", dev_act="WeatherProvider")
    RF(118, "Will it be cold tomorrow?", H6, "no_service", act="query",
       dev_act="WeatherProvider", tone="ask", b1="read", ctx="weather")
    RF(119, "Should I take an umbrella today?", H6, "no_service", act="query",
       dev_act="WeatherProvider", tone="ask", b1="read", ctx="weather")
    Q(120, "What time is it now?", H6, "Clock.Time", "Time", "It is $Time", [],
      dev_act="Clock")
    Q(121, "Do I have anything on my calendar today?", H15,
      "CalendarProvider.TodayEventCount", "Count", "You have $Count events today",
      [], ctx="calendar", dev_act="CalendarProvider")
    A(122, "Remind me tomorrow morning.", H6, [], act="notify", trig="time",
      dev_trig="Clock", dev_act="NotificationProvider")
    # 123-128 싣지 않음 — 시스템 자기설명 3, 일반 대화 3
    A(129, "Should I ventilate right now?", H3, [], act="query", tone="ask",
      b1="read", ref="vague")
    A(130, "Is it okay to open the windows today?", H3, [], act="query", tone="ask",
      b1="read", ref="vague", ctx="weather")
    A(131, "Is the house comfortable right now?", H6, [], act="query", tone="ask",
      b1="read", ref="vague")
    # ── 모호함/실패/비지원 ──
    A(132, "Turn off the light.", H6, [("Light",)], act="light.off", ref="plain")
    A(133, "Turn on the air conditioner.", H6, [("AirConditioner",)], act="ac",
      ref="plain")
    A(134, "Close the door.", H6, [], act="lock", ref="vague")
    A(135, "Make the house comfortable.", H6, [], act="ac", ref="vague")
    A(136, "Just set everything to a good state.", H6, [], act="ac", ref="vague")
    A(137, "Make it cozy for me.", H6, [], act="ac", ref="vague")
    A(138, "Send an email.", H15, [], act="notify", dev_act="EmailProvider")
    A(139, "Take a photo and send it to me.", H15, [], act="camera",
      dev_act="Camera")
    A(140, "Send a notification.", H6, [], act="notify",
      dev_act="NotificationProvider")
    RF(141, "Close the study curtains.", "HOME16", "no_device", act="cover",
       dev_act="WindowCovering")
    RF(142, "Open the garage door.", "HOME02", "no_device", act="garage",
       dev_act="GarageDoor")
    RF(143, "Lock the entrance door lock.", "HOME17", "no_device", act="lock",
       dev_act="DoorLock")
    # 144 싣지 않음 — 기기 한 대만 색이 안 되는 경우를 카탈로그가 표현 못 함
    RF(145, "Set the plug brightness to 50 percent.", H15, "no_service", act="plug",
       dev_act="Plug", b1="set")
    # 146 싣지 않음 — "확인 없이"


# ══ office (147–253) ═══════════════════════════════════════════════════
def sheet_office():
    O5, O1, O2, O3, O6 = "OFFICE05", "OFFICE01", "OFFICE02", "OFFICE03", "OFFICE06"
    # ── 기기 직접 제어 ──
    X(147, "Turn on the meeting room lights.", O5, [NOW, PON("Light")],
      [("Light", "MeetingRoom")], act="light.on")
    X(148, "Turn off all the lights in the office.", O5, [NOW, POFF("Light")],
      [("Light",)], act="light.off", ref="all")
    X(149, "Turn on only the open space lights.", O5, [NOW, PON("Light")],
      [("Light", "OpenSpace")], act="light.on")
    X(150, "Turn on the meeting room air conditioner.", O1,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner", "MeetingRoom")], act="ac")
    X(151, "Turn off the open space air conditioners.", O5,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner", "OpenSpace")], act="ac")
    X(152, "Start the air purifier.", O1,
      [NOW, CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier")
    RF(153, "Turn off the meeting room plugs.", O5, "no_device", act="plug",
       dev_act="Plug")
    RF(154, "Turn on the power strip by the desks.", O5, "no_device", act="plug",
       dev_act="Plug")
    X(155, "Lower the open space blinds.", O5, [NOW, CL("WindowCovering.DownOrClose")],
      [("WindowCovering", "OpenSpace")], act="cover")
    X(156, "Raise the window blinds.", O1, [NOW, CL("WindowCovering.UpOrOpen")],
      [("WindowCovering",)], act="cover")
    X(157, "Turn on the meeting room speakers.", O3,
      [NOW, CL("Speaker.Play", MediaSource="default playlist")],
      [("Speaker", "MeetingRoom")], act="media")
    X(158, "Mute the office speakers.", O5, [NOW, CL("Speaker.Mute")],
      [("Speaker",)], act="speaker", ref="plain")
    # ── 기기 속성 조절 ──
    X(159, "Set the meeting room lights to 70 percent.", O5, [NOW, bright(70)],
      [("Light", "MeetingRoom")], act="light.dim", b1="set")
    X(160, "Dim the open space lights to 30 percent.", O5, [NOW, bright(30)],
      [("Light", "OpenSpace")], act="light.dim", b1="set")
    X(161, "Set the meeting room lights to a cool white.", O5, [NOW, ctemp(COOL)],
      [("Light", "MeetingRoom")], act="light.color", b1="set")
    X(162, "Set the open space lights to a warm color.", O2, [NOW, ctemp(WARM)],
      [("Light", "OpenSpace")], act="light.color", b1="set")
    X(163, "Set the meeting room to 24 degrees.", O1,
      [NOW, CL("AirConditioner.SetTargetTemperature", Temperature=24.0)],
      [("AirConditioner", "MeetingRoom")], act="ac", b1="set")
    X(164, "Turn the office temperature down to 23 degrees.", O6,
      [NOW, CL("Thermostat.SetTargetTemperature", Temperature=23.0)],
      [("Thermostat",)], act="thermostat", b1="set")
    X(165, "Switch the air conditioners to cool mode.", O5,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner",)], act="ac", b1="set", ref="plain")
    X(166, "Put the air purifier on auto mode.", O2,
      [NOW, CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier", b1="set")
    X(167, "Turn down the meeting room speakers.", O3, [NOW, CL("Speaker.VolumeDown")],
      [("Speaker", "MeetingRoom")], act="speaker", b1="set")
    X(168, "Set the announcement volume to 30.", O5,
      [NOW, CL("Speaker.SetVolume", Volume=30)],
      [("Speaker",)], act="speaker", b1="set", ref="plain")
    # ── 공간/기기 상태 조회 ──
    Q(169, "What is the temperature in the open space?", O5,
      "TemperatureSensor.Temperature", "Temperature", "The temperature is $Temperature",
      [("TemperatureSensor", "OpenSpace")], ref="place")
    Q(170, "Is the office air quality okay?", O5,
      "AirQualitySensor.VeryFineDustLevel", "Dust", "The fine dust level is $Dust",
      [("AirQualitySensor",)])
    Q(171, "Tell me the CO2 level in the open space.", O5,
      "AirQualitySensor.CarbonDioxide", "CO2", "The CO2 level is $CO2",
      [("AirQualitySensor", "OpenSpace")], ref="place", tone="bare")
    Q(172, "Is anyone in the meeting room?", O3,
      "PresenceSensor.Presence", "Presence", "Presence reads $Presence",
      [("PresenceSensor", "MeetingRoom")], ref="place")
    Q(173, "Is the office empty right now?", O1,
      "PresenceSensor.Presence", "Presence", "Presence reads $Presence",
      [("PresenceSensor",)])
    Q(174, "Any motion in the open space?", O6,
      "MotionSensor.Motion", "Motion", "Motion reads $Motion",
      [("MotionSensor", "OpenSpace")], ref="place")
    Q(175, "Are the meeting room lights on?", O5,
      "Switch.Switch", "Switch", "The lights read $Switch",
      [("Light", "MeetingRoom")], dev_act="Light", ref="place")
    Q(176, "Is the air conditioner running?", O6,
      "AirConditioner.AirConditionerMode", "Mode", "The air conditioner is $Mode",
      [("AirConditioner",)])
    Q(177, "Is the air purifier off?", O1,
      "AirPurifier.AirPurifierMode", "Mode", "The air purifier is $Mode",
      [("AirPurifier",)])
    Q(178, "Is the entrance door open?", O1,
      "ContactSensor.Contact", "Contact", "The door contact reads $Contact",
      [("ContactSensor", "Entrance")], ref="place")
    Q(179, "Check whether the entrance door is closed.", O3,
      "ContactSensor.Contact", "Contact", "The door contact reads $Contact",
      [("ContactSensor", "Entrance")], ref="place", tone="bare")
    Q(180, "How much power has the office used today?", O5,
      "EnergyMeter.EnergyConsumed@diff:today", "Used", "Today's usage is $Used",
      [("EnergyMeter",)], d="D12", tier="T4")
    RF(181, "How much power are the meeting room plugs using?", O5, "no_device",
       act="query", dev_act="Plug", tone="ask", b1="read")
    Q(182, "What was the temperature range in the office today?", O5,
      "TemperatureSensor.Temperature@min:today", "Min",
      "Today it ranged from $Min to $Max",
      [("TemperatureSensor", "OpenSpace")],
      extra=[("Max", "TemperatureSensor.Temperature@max:today")],
      d="D12", tier="T4", ref="place")
    Q(183, "How was the CO2 level over the last hour?", O5,
      "AirQualitySensor.CarbonDioxide", "Now", "It is $Now now, an hour ago it was $Prev",
      [("AirQualitySensor",)],
      extra=[("Prev", "AirQualitySensor.CarbonDioxide@-1HOUR")],
      d="D11", tier="T4")
    Q(184, "What was the average office temperature yesterday?", O5,
      "TemperatureSensor.Temperature@avg:yesterday", "Avg",
      "Yesterday's average was $Avg",
      [("TemperatureSensor", "OpenSpace")], d="D12", tier="T4", ref="place")
    # ── 조건 기반 자동화 ──
    X(185, "When someone is detected, turn on the meeting room lights.", O3,
      [NOW, W("PresenceSensor.Presence == true"), PON("Light")],
      [("Light", "MeetingRoom")], act="light.on", trig="presence",
      dev_trig="PresenceSensor", d="D4", tier="T1")
    X(186, "When the meeting room is empty, turn off its lights.", O3,
      [NOW, W("PresenceSensor.Presence == false"), POFF("Light")],
      [("Light", "MeetingRoom")], act="light.off", trig="presence",
      dev_trig="PresenceSensor", d="D4", tier="T1")
    X(187, "If nobody is around, turn off the air conditioners.", O1,
      [NOW, W(occ(O1, False)), CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="presence", dev_trig="PresenceSensor",
      d="D4", tier="T1", ref="plain")
    X(188, "Notify me when the entrance door opens.", O1,
      [NOW, W("ContactSensor.Contact == false"), nn(O1, "The door has opened")],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D4", tier="T1",
      tsvc=tsvc())
    X(189, "If the entrance door opens after dark, send me a warning.", O3,
      [NOW, W("ContactSensor.Contact == false"), IF(DARK,
       [nn(O3, "The door has opened")])],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D13", tier="T2",
      ctx="sun", tsvc=tsvc())
    X(190, "If the door is open, turn off the air conditioner.", O6,
      [NOW, W("ContactSensor.Contact == false"),
       CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="contact", dev_trig="ContactSensor",
      d="D4", tier="T1")
    X(191, "If the CO2 gets high, tell us to ventilate.", O5,
      [NOW, W("AirQualitySensor.CarbonDioxide > 1000"),
       nn(O5, "Please ventilate the room")],
      [], act="notify", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(192, "If the temperature goes above 28, turn on the air conditioners.", O5,
      [NOW, W("TemperatureSensor.Temperature > 28"),
       CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner", "OpenSpace")], act="ac", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    X(193, "If the air quality gets bad, turn on the air purifier.", O2,
      [NOW, W("AirQualitySensor.VeryFineDustLevel > 36"),
       CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier", trig="threshold",
      dev_trig="AirQualitySensor", d="D4", tier="T1")
    X(194, "When it gets dark outside, turn on the office lights.", O5,
      [NOW, W(DARK), PON("Light")], [("Light",)], act="light.on", trig="sun",
      dev_trig="SunProvider", d="D4", tier="T1", ctx="sun", ref="plain")
    RF(195, "When the sunlight is strong, lower the blinds.", O5, "no_device",
       act="cover", dev_act="LightSensor", trig="threshold", dev_trig="LightSensor")
    RF(196, "When the TV turns on, dim the lights.", O5, "no_device",
       act="light.dim", dev_act="Television", trig="device", dev_trig="Television")
    X(197, "If the air purifier shuts off, switch it back on.", O1,
      [NOW, W('AirPurifier.AirPurifierMode == "off"'),
       CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier", trig="device", dev_trig="AirPurifier",
      d="D4", tier="T1")
    # ── 시간/스케줄 자동화 ──
    X(198, "Turn off the office lights at 6 pm.", O5, [CRON("0 18 * * *"),
      POFF("Light")], [("Light",)], act="light.off", trig="time", dev_trig="Clock",
      d="D6", tier="T1", ref="plain")
    X(199, "Turn on the meeting room air conditioner at 9 am.", O1,
      [CRON("0 9 * * *"), CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner", "MeetingRoom")], act="ac", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(200, "At noon, turn on the air purifier.", O2, [CRON("0 12 * * *"),
      CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(201, "Turn on the office lights at 8 am on weekdays.", O5,
      [CRON("0 8 * * 1-5"), PON("Light")], [("Light",)], act="light.on",
      trig="time", dev_trig="Clock", d="D6", tier="T1", ref="plain")
    RF(202, "Run the robot vacuum every Friday at 7.", O5, "no_device",
       act="vacuum", dev_act="RobotVacuumCleaner", trig="time", dev_trig="Clock")
    RF(203, "Turn off all the plugs at quitting time every day.", O5, "no_device",
       act="plug", dev_act="Plug", trig="time", dev_trig="Clock")
    X(204, "Turn off the meeting room lights in 10 minutes.", O3,
      [NOW, DL("10 MIN"), POFF("Light")], [("Light", "MeetingRoom")],
      act="light.off", trig="timer", dev_trig="Clock", d="D2", tier="T2")
    X(205, "Five minutes after the meeting ends, turn off the air conditioner.", O1,
      [NOW, W("CalendarProvider.IsBusy == false"), DL("5 MIN"),
       CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner", "MeetingRoom")], act="ac", trig="calendar",
      dev_trig="CalendarProvider", d="D2", tier="T2", ctx="calendar")
    X(206, "Keep the meeting room air conditioner on for an hour.", O1,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="cool"), DL("1 HOUR"),
       CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner", "MeetingRoom")], act="ac", trig="timer",
      dev_trig="Clock", d="D2", tier="T2")
    A(207, "Hold presentation mode for 30 minutes.", O5, [], act="light.scene",
      ref="vague", trig="timer", dev_trig="Clock")
    # ── 회의/업무 모드 — 다기기 모드는 되묻기 ──
    A(208, "We're starting the meeting.", O5, [], act="light.scene", ref="vague",
      tone="terse")
    A(209, "Switch the meeting room to presentation mode.", O5, [],
      act="light.scene", ref="vague")
    A(210, "The meeting is over.", O5, [], act="light.scene", ref="vague",
      tone="terse")
    A(211, "Put the meeting room back to normal.", O5, [], act="light.scene",
      ref="vague")
    A(212, "Turn on focus mode.", O1, [], act="light.scene", ref="vague")
    A(213, "Run demo mode.", O5, [], act="light.scene", ref="vague")
    X(214, "When someone arrives at the office, play a welcome announcement.", O6,
      [NOW, W(occ(O6, True)), CL("Speaker.Speak", Text="Welcome to the office")],
      [("Speaker",)], act="speaker", trig="motion", dev_trig="MotionSensor",
      d="D4", tier="T1")
    # ── 알림/보고 요청 ──
    X(215, "If the CO2 gets high, put a warning on the screen.", O5,
      [NOW, W("AirQualitySensor.CarbonDioxide > 1000"),
       CL("Display.ShowMessage", Message="The CO2 level is high",
          DurationSeconds=10.0)],
      [], act="notify", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1", tsvc="Display.ShowMessage")
    X(216, "When the door opens, show it on the dashboard.", O3,
      [NOW, W("ContactSensor.Contact == false"),
       CL("Display.ShowMessage", Message="The door has opened",
          DurationSeconds=10.0)],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D4", tier="T1",
      tsvc="Display.ShowMessage")
    RF(217, "Announce the meeting on the speaker 10 minutes before it starts.", O5,
       "no_service", act="speaker", dev_act="Speaker", trig="calendar",
       dev_trig="CalendarProvider", ctx="calendar")
    X(218, "If the air quality gets bad, announce that we should ventilate.", O5,
      [NOW, W("AirQualitySensor.VeryFineDustLevel > 36"),
       CL("Speaker.Speak", Text="Please ventilate the office")],
      [("Speaker",)], act="speaker", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1")
    RF(219, "If motion is detected after hours, text the manager.", O6, "no_device",
       act="notify", dev_act="MessageSender", trig="motion", dev_trig="MotionSensor")
    RF(220, "If an intruder is detected, send a Slack message.", O6, "no_device",
       act="notify", dev_act="MessageSender", trig="motion", dev_trig="MotionSensor")
    A(221, "If the door opens, email the manager.", O5, [], act="notify",
      trig="contact", dev_trig="ContactSensor", dev_act="EmailProvider",
      d="D4", tier="T1")
    A(222, "Take a snapshot and email it to me.", O5, [], act="camera",
      dev_act="EmailProvider")
    X(223, "While the CO2 stays high, alert me every 10 minutes.", O5,
      [NOW, W("AirQualitySensor.CarbonDioxide > 1000"),
       CY("10 MIN", [nn(O5, "The CO2 level is high")],
          until="not (AirQualitySensor.CarbonDioxide > 1000)")],
      [], act="notify", trig="threshold", dev_trig="AirQualitySensor",
      d="D9", tier="T3", tsvc=tsvc())
    X(224, "While the door stays open, keep warning me.", O3,
      [NOW, W("ContactSensor.Contact == false"),
       CY("5 MIN", [nn(O3, "The door has opened")],
          until="not (ContactSensor.Contact == false)")],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D9", tier="T3",
      tsvc=tsvc())
    # ── 안전/보안 요청 ──
    X(225, "If there is motion in the office after dark, notify me.", O6,
      [NOW, W("MotionSensor.Motion == true"), IF(DARK,
       [nn(O6, "Motion was detected")])],
      [], act="notify", trig="motion", dev_trig="MotionSensor", d="D13", tier="T2",
      ctx="sun", tsvc=tsvc())
    X(226, "If the entrance door opens at night, warn me.", O6,
      [NOW, W("ContactSensor.Contact == false"), IF(DARK,
       [nn(O6, "The door has opened")])],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D13", tier="T2",
      ctx="sun", tsvc=tsvc())
    RF(227, "If motion is detected while nobody is in the office, check the camera.",
       O5, "no_device", act="camera", dev_act="MotionSensor", trig="motion",
       dev_trig="MotionSensor")
    X(228, "If smoke is detected, sound the alarm and warn everyone.", O5,
      [NOW, W("SmokeDetector.Smoke == true"),
       CL("Siren.SetSirenMode", Mode="fire"), nn(O5, "Smoke was detected")],
      [("Siren",)], act="siren", trig="smoke", dev_trig="SmokeDetector",
      d="D4", tier="T1", tsvc=tsvc())
    RF(229, "If water leaks, alert the manager.", O5, "no_device", act="notify",
       dev_act="LeakSensor", trig="leak", dev_trig="LeakSensor")
    X(230, "Show me the hallway cameras.", O5, [NOW, CL("Camera.StartStream")],
      [("Camera", "Hallway")], act="camera")
    X(231, "When motion is detected, capture a 10-second video.", O6,
      [NOW, W("MotionSensor.Motion == true"), CL("Camera.CaptureVideo", Seconds=10.0)],
      [("Camera",)], act="camera", trig="motion", dev_trig="MotionSensor",
      d="D4", tier="T1")
    # ── 일상 정보/대화 ──
    Q(232, "Is it raining right now?", O5, "WeatherProvider.Weather", "Weather",
      "The weather is $Weather", [], ctx="weather", dev_act="WeatherProvider")
    A(233, "Is it a good day to head out for a site visit?", O5, [], act="query",
      tone="ask", b1="read", ref="vague", ctx="weather")
    Q(234, "Do I have any meetings today?", O5,
      "CalendarProvider.TodayEventCount", "Count", "You have $Count events today",
      [], ctx="calendar", dev_act="CalendarProvider")
    Q(235, "When does my next meeting start?", O5,
      "CalendarProvider.NextEventStart", "Start", "Your next event starts at $Start",
      [], ctx="calendar", dev_act="CalendarProvider")
    # 236-238 싣지 않음 — 자기설명 2, 일반 대화 1
    A(239, "Should we ventilate right now?", O5, [], act="query", tone="ask",
      b1="read", ref="vague")
    A(240, "Is the meeting room comfortable right now?", O3, [], act="query",
      tone="ask", b1="read", ref="vague")
    # 241-244 싣지 않음 — 자동화 관리
    # ── 모호함/실패/비지원 ──
    A(245, "Turn off the lights.", O5, [("Light",)], act="light.off", ref="plain")
    A(246, "Can you turn on the air conditioner?", O5, [("AirConditioner",)],
      act="ac", ref="plain", tone="could")
    A(247, "Make the office comfortable.", O5, [], act="ac", ref="vague")
    A(248, "Get things ready for the meeting.", O5, [], act="light.scene",
      ref="vague")
    A(249, "Email the manager.", O5, [], act="notify", dev_act="EmailProvider")
    A(250, "Send out an alert.", O5, [], act="notify",
      dev_act="NotificationProvider")
    RF(251, "Lower the meeting room blinds.", O3, "no_device", act="cover",
       dev_act="WindowCovering")
    X(252, "Lock the entrance door locks.", O5, [NOW, CL("DoorLock.Lock")],
      [("DoorLock", "Entrance")], act="lock")
    # 253 싣지 않음 — 기기 한 대만 색이 안 되는 경우


# ══ factory (254–358) ══════════════════════════════════════════════════
def sheet_factory():
    F1, F2, F3, F4, F5 = "FACT01", "FACT02", "FACT03", "FACT04", "FACT05"
    # ── 기기 직접 제어 ──
    X(254, "Turn on the production line lights.", F1, [NOW, PON("Light")],
      [("Light", "Line")], act="light.on")
    X(255, "Turn off the warehouse lights.", F2, [NOW, POFF("Light")],
      [("Light", "Warehouse")], act="light.off")
    X(256, "Turn off all the lights in the plant.", F5, [NOW, POFF("Light")],
      [("Light",)], act="light.off", ref="all")
    X(257, "Power up the line 2 machine.", F1, [NOW, CL("ProductionMachine.Start")],
      [("ProductionMachine", "Line", "line 2")], act="machine", ref="nick")
    X(258, "Shut down the process room machines.", F3,
      [NOW, CL("ProductionMachine.Stop")], [("ProductionMachine", "ProcessRoom")],
      act="machine")
    X(259, "Start the line 1 conveyor.", F1, [NOW, CL("ConveyorBelt.Start")],
      [("ConveyorBelt", "Line", "line 1")], act="conveyor", ref="nick")
    A(260, "Stop the conveyor.", F3, [("ConveyorBelt",)], act="conveyor",
      ref="plain")
    X(261, "Start the coolant pump.", F3, [NOW, CL("Pump.SetPumpMode",
      PumpMode="normal")], [("Pump",)], act="pump")
    X(262, "Stop pump 3.", F5, [NOW, POFF("Pump")],
      [("Pump", "PumpRoom", "pump 3")], act="pump", ref="nick")
    X(263, "Close valve 1 in the pump room.", F5, [NOW, CL("Valve.Close")],
      [("Valve", "PumpRoom", "valve 1")], act="valve", ref="nick")
    X(264, "Open the process room valves.", F3, [NOW, CL("Valve.Open")],
      [("Valve", "ProcessRoom")], act="valve")
    X(265, "Turn on the workshop ventilators.", F4,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="auto")],
      [("Ventilator", "MachineShop")], act="ventilator")
    RF(266, "Turn off the workshop air conditioner.", F4, "no_device", act="ac",
       dev_act="AirConditioner")
    X(267, "Turn off the sirens.", F5, [NOW, CL("Siren.Deactivate")],
      [("Siren",)], act="siren", ref="plain")
    X(268, "Turn on the dock cameras.", F2, [NOW, CL("Camera.StartStream")],
      [("Camera", "Dock")], act="camera")
    # ── 기기 속성 조절 ──
    X(269, "Set the warehouse lights to 70 percent.", F2, [NOW, bright(70)],
      [("Light", "Warehouse")], act="light.dim", b1="set")
    X(270, "Brighten the line lights to full.", F1, [NOW, bright(100)],
      [("Light", "Line")], act="light.dim", b1="set")
    X(271, "Set the line status lights to green.", F1,
      [NOW, CL("StatusLight.SetStatus", Mode="green")],
      [("StatusLight", "Line")], act="statuslight", b1="set")
    X(272, "If a machine reports an error, turn the status lights red.", F1,
      [NOW, W('ProductionMachine.MachineState == "error"'),
       CL("StatusLight.SetStatus", Mode="red")],
      [("StatusLight", "Line")], act="statuslight", trig="device",
      dev_trig="ProductionMachine", d="D4", tier="T1", b1="set")
    RF(273, "Set the workshop to 24 degrees.", F4, "no_device", act="ac",
       dev_act="AirConditioner", b1="set")
    X(274, "Set the ventilators to high.", F4,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="high")],
      [("Ventilator", "MachineShop")], act="ventilator", b1="set")
    A(275, "Set the compressor to the standard pressure.", F4, [("AirCompressor",)],
      act="compressor", b1="set", ref="plain")
    RF(276, "Open the valve halfway.", F5, "no_service", act="valve",
       dev_act="Valve", b1="set")
    # ── 공간/설비 상태 조회 ──
    Q(277, "What is the temperature in the workshop?", F4,
      "TemperatureSensor.Temperature", "Temperature", "The temperature is $Temperature",
      [("TemperatureSensor", "MachineShop")], ref="place")
    Q(278, "Is the air okay in the boiler room?", F5,
      "GasSensor.GasLevel", "Gas", "The gas level is $Gas",
      [("GasSensor", "BoilerRoom")], ref="place")
    Q(279, "What is the humidity in the warehouse?", F2,
      "HumiditySensor.Humidity", "Humidity", "The humidity is $Humidity",
      [("HumiditySensor", "Warehouse")], ref="place")
    Q(280, "Is the line 1 conveyor running?", F1,
      "ConveyorBelt.ConveyorState", "State", "The conveyor is $State",
      [("ConveyorBelt", "Line", "line 1")], ref="nick")
    Q(281, "What is the status of the line 2 machine?", F1,
      "ProductionMachine.MachineState", "State", "The machine is $State",
      [("ProductionMachine", "Line", "line 2")], ref="nick")
    Q(282, "Is the compressor tank pressure in the normal range?", F1,
      "AirCompressor.TankPressure", "Pressure", "The tank pressure is $Pressure",
      [("AirCompressor",)])
    Q(283, "Has any gas been detected?", F5,
      "GasSensor.Gas", "Gas", "Gas detection reads $Gas",
      [("GasSensor",)], ref="plain")
    Q(284, "Is there a leak anywhere?", F5,
      "LeakSensor.Leakage", "Leak", "Leak detection reads $Leak",
      [("LeakSensor",)], ref="plain")
    Q(285, "Was the emergency stop pressed?", F1,
      "EmergencyStop.EmergencyStopState", "State", "The emergency stop is $State",
      [("EmergencyStop",)], ref="plain")
    Q(286, "How much power has the plant used today?", F5,
      "EnergyMeter.EnergyConsumed@diff:today", "Used", "Today's usage is $Used",
      [("EnergyMeter",)], d="D12", tier="T4")
    Q(287, "Is the plant power draw high right now?", F1,
      "EnergyMeter.Power", "Power", "The power draw is $Power",
      [("EnergyMeter",)])
    Q(288, "How did the line temperature change over the last hour?", F1,
      "TemperatureSensor.Temperature", "Now", "It is $Now now, an hour ago it was $Prev",
      [("TemperatureSensor", "Line")],
      extra=[("Prev", "TemperatureSensor.Temperature@-1HOUR")],
      d="D11", tier="T4", ref="place")
    RF(289, "How many pressure spikes were there today?", F5, "no_service",
       act="query", dev_act="PressureSensor", tone="ask", b1="read")
    RF(290, "Summarize the past week's power usage.", F5, "no_service",
       act="query", dev_act="EnergyMeter", b1="read")
    # ── 조건 기반 자동화 ──
    X(291, "If a conveyor stops, let me know.", F1,
      [NOW, W('ConveyorBelt.ConveyorState == "stopped"'),
       nn(F1, "The conveyor has stopped")],
      [], act="notify", trig="device", dev_trig="ConveyorBelt", d="D4", tier="T1",
      tsvc=tsvc())
    X(292, "When a machine goes into an error state, turn the status lights red.", F3,
      [NOW, W('ProductionMachine.MachineState == "error"'),
       CL("StatusLight.SetStatus", Mode="red")],
      [("StatusLight", "ProcessRoom")], act="statuslight", trig="device",
      dev_trig="ProductionMachine", d="D4", tier="T1")
    X(293, "If the machines overheat, shut them down.", F4,
      [NOW, W("TemperatureSensor.Temperature > 60"), CL("ProductionMachine.Stop")],
      [("ProductionMachine", "MachineShop")], act="machine", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    X(294, "If someone crosses the safety barrier, stop the conveyors.", F1,
      [NOW, W('SafetyBarrier.BarrierState == "blocked"'), CL("ConveyorBelt.Stop")],
      [("ConveyorBelt", "Line")], act="conveyor", trig="security",
      dev_trig="SafetyBarrier", d="D4", tier="T1")
    X(295, "If someone gets close, stop the robot arms.", F4,
      [NOW, W('SafetyBarrier.BarrierState == "blocked"'),
       CL("ArmRobot.SendCommand", Command="stop")],
      [("ArmRobot", "MachineShop")], act="armrobot", trig="security",
      dev_trig="SafetyBarrier", d="D4", tier="T1")
    X(296, "If motion is detected in the warehouse, take a snapshot.", F2,
      [NOW, W("MotionSensor.Motion == true"), CL("Camera.CaptureImage")],
      [("Camera", "Warehouse")], act="camera", trig="motion",
      dev_trig="MotionSensor", d="D4", tier="T1")
    X(297, "If the temperature goes above 35, turn on the ventilators.", F2,
      [NOW, W("TemperatureSensor.Temperature > 35"),
       CL("Ventilator.SetVentilatorMode", Mode="auto")],
      [("Ventilator", "Warehouse")], act="ventilator", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    RF(298, "If the humidity gets high, turn on the dehumidifier.", F3, "no_device",
       act="humidity", dev_act="Dehumidifier", trig="threshold",
       dev_trig="HumiditySensor")
    X(299, "If gas is detected, close the valves and warn me.", F5,
      [NOW, W("GasSensor.Gas == true"), CL("Valve.Close"),
       nn(F5, "Gas was detected")],
      [("Valve", "PumpRoom")], act="valve", trig="gas", dev_trig="GasSensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(300, "If a leak is detected, stop the pumps.", F5,
      [NOW, W("LeakSensor.Leakage == true"), POFF("Pump")],
      [("Pump", "PumpRoom")], act="pump", trig="leak", dev_trig="LeakSensor",
      d="D4", tier="T1")
    X(301, "If the pressure goes above 8 bar, open valve 1.", F5,
      [NOW, W("AirCompressor.TankPressure > 8"), CL("Valve.Open")],
      [("Valve", "PumpRoom", "valve 1")], act="valve", trig="threshold",
      dev_trig="AirCompressor", d="D4", tier="T1", ref="nick")
    X(302, "If the tank level drops below half, start pump 1.", F5,
      [NOW, W("WaterLevelSensor.WaterLevel < 50"),
       CL("Pump.SetPumpMode", PumpMode="normal")],
      [("Pump", "PumpRoom", "pump 1")], act="pump", trig="threshold",
      dev_trig="WaterLevelSensor", d="D4", tier="T1", ref="nick")
    X(303, "If the power draw spikes, let me know.", F1,
      [NOW, W("EnergyMeter.Power > 50000"), nn(F1, "The power draw spiked")],
      [], act="notify", trig="power", dev_trig="EnergyMeter", d="D4", tier="T1",
      tsvc=tsvc())
    X(304, "If the machine power draw spikes, stop the line.", F1,
      [NOW, W("EnergyMeter.Power > 50000"), CL("ConveyorBelt.Stop"),
       CL("ProductionMachine.Stop")],
      [("ConveyorBelt", "Line"), ("ProductionMachine", "Line")], act="conveyor",
      trig="power", dev_trig="EnergyMeter", d="D4", tier="T1")
    # ── 시간/스케줄 자동화 ──
    X(305, "Turn off the line lights at 6 pm.", F1, [CRON("0 18 * * *"),
      POFF("Light")], [("Light", "Line")], act="light.off", trig="time",
      dev_trig="Clock", d="D6", tier="T1")
    X(306, "Turn on the ventilators at 8 am.", F2, [CRON("0 8 * * *"),
      CL("Ventilator.SetVentilatorMode", Mode="auto")],
      [("Ventilator", "Warehouse")], act="ventilator", trig="time",
      dev_trig="Clock", d="D6", tier="T1")
    X(307, "Stop the conveyors at lunchtime.", F3, [CRON("0 12 * * *"),
      CL("ConveyorBelt.Stop")], [("ConveyorBelt", "ProcessRoom")],
      act="conveyor", trig="time", dev_trig="Clock", d="D6", tier="T1")
    X(308, "Send a machine-check reminder every morning.", F4, [CRON("0 9 * * *"),
      nn(F4, "Time for the machine check")],
      [], act="notify", trig="time", dev_trig="Clock", d="D6", tier="T1",
      tsvc=tsvc())
    X(309, "Turn off all the warehouse lights every Friday evening.", F2,
      [CRON("0 18 * * 5"), POFF("Light")], [("Light", "Warehouse")],
      act="light.off", trig="time", dev_trig="Clock", d="D6", tier="T1")
    A(310, "Switch the plant to power-saving mode at quitting time.", F1, [],
      act="light.scene", ref="vague", trig="time", dev_trig="Clock")
    X(311, "Turn off the ventilators in 10 minutes.", F5, [NOW, DL("10 MIN"),
      CL("Ventilator.SetVentilatorMode", Mode="off")],
      [("Ventilator", "BoilerRoom")], act="ventilator", trig="timer",
      dev_trig="Clock", d="D2", tier="T2")
    A(312, "Turn off the lights 5 minutes after the work is done.", F1,
      [("Light", "Line")], act="light.off", trig="timer", dev_trig="Clock")
    X(313, "Run the ventilators for 30 minutes.", F3,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="auto"), DL("30 MIN"),
       CL("Ventilator.SetVentilatorMode", Mode="off")],
      [("Ventilator", "ProcessRoom")], act="ventilator", trig="timer",
      dev_trig="Clock", d="D2", tier="T2")
    X(314, "Run the cooling pump for 2 hours.", F3,
      [NOW, CL("Pump.SetPumpMode", PumpMode="normal"), DL("2 HOUR"), POFF("Pump")],
      [("Pump",)], act="pump", trig="timer", dev_trig="Clock", d="D2", tier="T2")
    # ── 생산/운영 모드 — 되묻기 ──
    A(315, "Run the work-start mode.", F1, [], act="light.scene", ref="vague")
    A(316, "Switch to the end-of-work mode.", F1, [], act="light.scene",
      ref="vague")
    A(317, "Turn on the maintenance mode.", F1, [], act="light.scene", ref="vague")
    A(318, "Switch to night operation mode.", F1, [], act="light.scene",
      ref="vague")
    # ── 알림/보고 요청 ──
    X(319, "If the pressure gets high, put an alert on the dashboard.", F5,
      [NOW, W("AirCompressor.TankPressure > 8"),
       CL("Display.ShowMessage", Message="The pressure is high",
          DurationSeconds=10.0)],
      [], act="notify", trig="threshold", dev_trig="AirCompressor",
      d="D4", tier="T1", tsvc="Display.ShowMessage")
    X(320, "If a machine goes wrong, warn me on the screen.", F4,
      [NOW, W('ProductionMachine.MachineState == "error"'),
       CL("Display.ShowMessage", Message="A machine reported an error",
          DurationSeconds=10.0)],
      [], act="notify", trig="device", dev_trig="ProductionMachine",
      d="D4", tier="T1", tsvc="Display.ShowMessage")
    X(321, "If gas is detected, announce an evacuation on the speakers.", F5,
      [NOW, W("GasSensor.Gas == true"),
       CL("Speaker.Speak", Text="Gas detected, please evacuate")],
      [("Speaker", "PumpRoom")], act="speaker", trig="gas", dev_trig="GasSensor",
      d="D4", tier="T1")
    X(322, "At 8:50 every morning, announce that work starts in 10 minutes.", F1,
      [CRON("50 8 * * *"), CL("Speaker.Speak", Text="Work starts in 10 minutes")],
      [("Speaker", "Line")], act="speaker", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    A(323, "If a machine reports an error, text the manager.", F4, [],
      act="notify", trig="device", dev_trig="ProductionMachine",
      dev_act="MessageSender", d="D4", tier="T1")
    A(324, "In an emergency, send a KakaoTalk message to the person on duty.", F1,
      [], act="notify", dev_act="MessageSender", ref="vague")
    X(325, "If the line stops, send a Slack message.", F1,
      [NOW, W('ConveyorBelt.ConveyorState == "stopped"'),
       CL("MessageSender.SendSlack", Message="The line has stopped")],
      [], act="notify", trig="device", dev_trig="ConveyorBelt", d="D4", tier="T1",
      tsvc="MessageSender.SendSlack")
    RF(326, "Email me today's machine fault log.", F5, "no_service", act="query",
       dev_act="EmailProvider", b1="read")
    A(327, "Email the manager a snapshot from the camera.", F5, [], act="camera",
      dev_act="EmailProvider")
    X(328, "While the pressure stays high, alert me every 5 minutes.", F5,
      [NOW, W("AirCompressor.TankPressure > 8"),
       CY("5 MIN", [nn(F5, "The pressure is high")],
          until="not (AirCompressor.TankPressure > 8)")],
      [], act="notify", trig="threshold", dev_trig="AirCompressor",
      d="D9", tier="T3", tsvc=tsvc())
    X(329, "While gas keeps being detected, keep the alarm going.", F5,
      [NOW, W("GasSensor.Gas == true"),
       CY("5 MIN", [CL("Siren.SetSirenMode", Mode="gas")],
          until="not (GasSensor.Gas == true)")],
      [("Siren",)], act="siren", trig="gas", dev_trig="GasSensor", d="D9", tier="T3")
    # ── 안전/보안 요청 ──
    X(330, "If someone enters the danger zone, warn everyone.", F3,
      [NOW, W('SafetyBarrier.BarrierState == "blocked"'),
       nn(F3, "Someone entered the danger zone")],
      [], act="notify", trig="security", dev_trig="SafetyBarrier", d="D4", tier="T1",
      tsvc=tsvc())
    X(331, "If someone is in the danger zone, stop the robot arms.", F1,
      [NOW, W('SafetyBarrier.BarrierState == "blocked"'),
       CL("ArmRobot.SendCommand", Command="stop")],
      [("ArmRobot", "Line")], act="armrobot", trig="security",
      dev_trig="SafetyBarrier", d="D4", tier="T1")
    X(332, "If smoke is detected, sound the plant-wide alarm.", F2,
      [NOW, W("SmokeDetector.Smoke == true"),
       CL("Siren.SetSirenMode", Mode="fire"), nn(F2, "Smoke was detected")],
      [("Siren",)], act="siren", trig="smoke", dev_trig="SmokeDetector",
      d="D4", tier="T1", tsvc=tsvc())
    X(333, "If gas is detected, close the valves and announce an evacuation.", F5,
      [NOW, W("GasSensor.Gas == true"), CL("Valve.Close"),
       CL("Speaker.Speak", Text="Gas detected, please evacuate")],
      [("Valve", "PumpRoom"), ("Speaker", "PumpRoom")], act="valve", trig="gas",
      dev_trig="GasSensor", d="D4", tier="T1")
    X(334, "If water leaks, stop the pumps and let me know.", F5,
      [NOW, W("LeakSensor.Leakage == true"), POFF("Pump"),
       nn(F5, "A leak was detected")],
      [("Pump", "PumpRoom")], act="pump", trig="leak", dev_trig="LeakSensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(335, "If the emergency stop is pressed, halt the entire line.", F1,
      [NOW, W('EmergencyStop.EmergencyStopState == "triggered"'),
       CL("ConveyorBelt.Stop"), CL("ProductionMachine.Stop")],
      [("ConveyorBelt", "Line"), ("ProductionMachine", "Line")], act="conveyor",
      trig="emergency", dev_trig="EmergencyStop", d="D4", tier="T1")
    X(336, "If a worker is at risk of getting caught, stop the robot arm.", F1,
      [NOW, W('SafetyBarrier.BarrierState == "blocked"'),
       CL("ArmRobot.SendCommand", Command="stop")],
      [("ArmRobot", "Line")], act="armrobot", trig="security",
      dev_trig="SafetyBarrier", d="D4", tier="T1")
    A(337, "If something looks wrong, record a 10-second clip.", F1,
      [("Camera", "Line")], act="camera", ref="vague")
    # ── 일상 정보/대화 ──
    A(338, "How is the production line doing today?", F1, [], act="query",
      tone="ask", b1="read", ref="vague")
    A(339, "Is any machine having problems right now?", F1, [], act="query",
      tone="ask", b1="read", ref="vague")
    A(340, "Is today's humidity going to affect production?", F2, [], act="query",
      tone="ask", b1="read", ref="vague", ctx="weather")
    Q(341, "Is there a maintenance visit scheduled today?", F1,
      "CalendarProvider.TodayEventCount", "Count", "You have $Count events today",
      [], ctx="calendar", dev_act="CalendarProvider")
    # 342-343 싣지 않음 — 자기설명
    A(344, "Give me a rundown of the plant right now.", F1, [], act="query",
      tone="bare", b1="read", ref="vague")
    # 345-348 싣지 않음 — 자동화 관리
    # ── 모호함/실패/비지원 ──
    A(349, "Stop the line.", F1, [("ConveyorBelt", "Line"),
      ("ProductionMachine", "Line")], act="conveyor", ref="plain", tone="terse")
    A(350, "Turn off the machine.", F4, [("ProductionMachine", "MachineShop")],
      act="machine", ref="plain")
    A(351, "Make the plant safe.", F1, [], act="notify", ref="vague")
    A(352, "Get the line into good shape.", F1, [], act="machine", ref="vague")
    A(353, "Report to the manager.", F1, [], act="notify",
      dev_act="MessageSender", ref="vague")
    A(354, "Push an alert.", F1, [], act="notify", dev_act="NotificationProvider")
    RF(355, "Stop the line 4 conveyor.", F1, "no_device", act="conveyor",
       dev_act="ConveyorBelt")
    RF(356, "Close the gas valve.", F1, "no_device", act="valve", dev_act="Valve")
    RF(357, "Slow the plug down to 50 percent.", F4, "no_service", act="plug",
       dev_act="Plug", b1="set")
    # 358 싣지 않음 — "확인 없이"


# ══ lab (359–484) ══════════════════════════════════════════════════════
def sheet_lab():
    L1, L2, L3, L4, L5 = "LAB01", "LAB02", "LAB03", "LAB04", "LAB05"
    # ── 기기 직접 제어 ──
    X(359, "Turn on the lab room lights.", L2, [NOW, PON("Light")],
      [("Light", "LabRoom")], act="light.on")
    X(360, "Turn off the test bed lights.", L5, [NOW, POFF("Light")],
      [("Light", "TestBed")], act="light.off")
    X(361, "Turn on just the lab room lights.", L3, [NOW, PON("Light")],
      [("Light", "LabRoom")], act="light.on")
    X(362, "Turn on the lab air conditioner.", L4,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner",)], act="ac")
    X(363, "Turn on the ventilators.", L2,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="auto")],
      [("Ventilator",)], act="ventilator", ref="plain")
    X(364, "Switch off the air purifier.", L3,
      [NOW, CL("AirPurifier.SetAirPurifierMode", Mode="off")],
      [("AirPurifier",)], act="purifier")
    X(365, "Turn on the humidifier.", L1,
      [NOW, CL("Humidifier.SetHumidifierMode", Mode="auto")],
      [("Humidifier",)], act="humidity")
    RF(366, "Turn off the dehumidifier.", L2, "no_device", act="humidity",
       dev_act="Dehumidifier")
    X(367, "Turn off the bench plugs.", L2, [NOW, POFF("Plug")],
      [("Plug", "LabRoom")], act="plug")
    X(368, "Power up the lab equipment.", L2, [NOW, CL("ProductionMachine.Start")],
      [("ProductionMachine",)], act="machine", ref="plain")
    X(369, "Turn on the lab camera.", L2, [NOW, CL("Camera.StartStream")],
      [("Camera",)], act="camera")
    X(370, "Turn off the test bed camera.", L5, [NOW, CL("Camera.StopStream")],
      [("Camera", "TestBed")], act="camera")
    X(371, "Stop the robot arms.", L4, [NOW, CL("ArmRobot.SendCommand",
      Command="stop")], [("ArmRobot",)], act="armrobot", ref="plain")
    X(372, "Stop the lab equipment.", L4, [NOW, CL("ProductionMachine.Stop")],
      [("ProductionMachine",)], act="machine", ref="plain")
    X(373, "Close the lab valves.", L2, [NOW, CL("Valve.Close")],
      [("Valve", "LabRoom")], act="valve")
    X(374, "Turn on the cooling water pump.", L2, [NOW, CL("Pump.SetPumpMode",
      PumpMode="normal")], [("Pump",)], act="pump")
    # ── 기기 속성 조절 ──
    X(375, "Set the lab lights to 70 percent.", L4, [NOW, bright(70)],
      [("Light", "LabRoom")], act="light.dim", b1="set")
    X(376, "Brighten the test bed lights to full.", L5, [NOW, bright(100)],
      [("Light", "TestBed")], act="light.dim", b1="set")
    X(377, "Set the lab room lights to a cool white.", L2, [NOW, ctemp(COOL)],
      [("Light", "LabRoom")], act="light.color", b1="set")
    X(378, "If gas is detected, turn the lab lights red.", L2,
      [NOW, W("GasSensor.Gas == true"), hue("red")],
      [("Light", "LabRoom")], act="light.color", trig="gas", dev_trig="GasSensor",
      d="D4", tier="T1", b1="set")
    X(379, "Set the lab to 24 degrees.", L4,
      [NOW, CL("AirConditioner.SetTargetTemperature", Temperature=24.0)],
      [("AirConditioner",)], act="ac", b1="set")
    X(380, "Turn the lab temperature down to 22 degrees.", L4,
      [NOW, CL("AirConditioner.SetTargetTemperature", Temperature=22.0)],
      [("AirConditioner",)], act="ac", b1="set")
    X(381, "Set the humidity to around 50 percent.", L1,
      [NOW, CL("Humidifier.SetTargetHumidity", Humidity=50.0)],
      [("Humidifier",)], act="humidity", b1="set", ref="plain")
    X(382, "Turn the ventilators up to high.", L3,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="high")],
      [("Ventilator",)], act="ventilator", b1="set", ref="plain")
    X(383, "Turn down the lab speaker.", L2, [NOW, CL("Speaker.VolumeDown")],
      [("Speaker",)], act="speaker", b1="set")
    X(384, "Set the announcement volume to 50.", L4,
      [NOW, CL("Speaker.SetVolume", Volume=50)],
      [("Speaker",)], act="speaker", b1="set", ref="plain")
    # ── 공간/장비 상태 조회 ──
    Q(385, "What is the temperature in the lab right now?", L2,
      "TemperatureSensor.Temperature", "Temperature", "The temperature is $Temperature",
      [("TemperatureSensor", "LabRoom")], ref="place")
    Q(386, "What is the humidity in the lab?", L3,
      "HumiditySensor.Humidity", "Humidity", "The humidity is $Humidity",
      [("HumiditySensor", "LabRoom")], ref="place")
    Q(387, "Is the lab air quality okay?", L2,
      "AirQualitySensor.VeryFineDustLevel", "Dust", "The fine dust level is $Dust",
      [("AirQualitySensor",)])
    Q(388, "Tell me the CO2 level.", L3,
      "CarbonDioxideSensor.CarbonDioxide", "CO2", "The CO2 level is $CO2",
      [("CarbonDioxideSensor",)], tone="bare", ref="plain")
    Q(389, "Is the TVOC level high?", L2,
      "AirQualitySensor.TvocLevel", "Tvoc", "The TVOC level is $Tvoc",
      [("AirQualitySensor",)])
    Q(390, "Is anyone in the lab?", L4,
      "PresenceSensor.Presence", "Presence", "Presence reads $Presence",
      [("PresenceSensor",)])
    Q(391, "Was any motion detected in the lab?", L1,
      "MotionSensor.Motion", "Motion", "Motion reads $Motion",
      [("MotionSensor",)], ref="plain")
    Q(392, "Is the lab door open?", L2,
      "ContactSensor.Contact", "Contact", "The door contact reads $Contact",
      [("ContactSensor", "Entrance")], ref="place")
    Q(393, "Is the cold room door closed?", L3,
      "ContactSensor.Contact", "Contact", "The door contact reads $Contact",
      [("ContactSensor", "ColdRoom")], ref="place")
    Q(394, "Is the lab equipment running?", L2,
      "ProductionMachine.MachineState", "State", "The equipment is $State",
      [("ProductionMachine",)], ref="plain")
    RF(395, "Is the robot arm moving right now?", L4, "no_service", act="query",
       dev_act="ArmRobot", tone="ask", b1="read")
    Q(396, "Is the camera recording?", L2,
      "Camera.RecordingState", "State", "The camera recording state is $State",
      [("Camera",)])
    Q(397, "How much power are the bench plugs using?", L2,
      "Plug.Power", "Power", "The plug power draw is $Power",
      [("Plug", "LabRoom")], ref="place")
    Q(398, "Is today's equipment power usage high?", L4,
      "EnergyMeter.EnergyConsumed@diff:today", "Used", "Today's usage is $Used",
      [("EnergyMeter",)], d="D12", tier="T4")
    Q(399, "How has the CO2 changed over the past hour?", L3,
      "CarbonDioxideSensor.CarbonDioxide", "Now",
      "It is $Now now, an hour ago it was $Prev",
      [("CarbonDioxideSensor",)],
      extra=[("Prev", "CarbonDioxideSensor.CarbonDioxide@-1HOUR")],
      d="D11", tier="T4")
    Q(400, "What was the average lab temperature today?", L2,
      "TemperatureSensor.Temperature@avg:today", "Avg", "Today's average is $Avg",
      [("TemperatureSensor", "LabRoom")], d="D12", tier="T4", ref="place")
    Q(401, "Was the lab more humid than yesterday?", L3,
      "HumiditySensor.Humidity", "Now", "It is $Now now, yesterday it was $Prev",
      [("HumiditySensor", "LabRoom")],
      extra=[("Prev", "HumiditySensor.Humidity@-1DAY")],
      d="D11", tier="T4", ref="place")
    Q(402, "Did the door open at all today?", L2,
      "ContactSensor.Contact@count:today", "Count", "The door opened $Count times today",
      [("ContactSensor", "Entrance")], d="D12", tier="T4", ref="place")
    # ── 조건 기반 자동화 ──
    X(403, "When someone is detected, turn on the lab lights.", L4,
      [NOW, W("PresenceSensor.Presence == true"), PON("Light")],
      [("Light", "LabRoom")], act="light.on", trig="presence",
      dev_trig="PresenceSensor", d="D4", tier="T1")
    X(404, "When the lab is empty, turn off the lights.", L4,
      [NOW, W("PresenceSensor.Presence == false"), POFF("Light")],
      [("Light", "LabRoom")], act="light.off", trig="presence",
      dev_trig="PresenceSensor", d="D4", tier="T1")
    X(405, "If nobody is around, turn off the air conditioner.", L4,
      [NOW, W("PresenceSensor.Presence == false"),
       CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="presence", dev_trig="PresenceSensor",
      d="D4", tier="T1", ref="plain")
    X(406, "Let me know when the lab door opens.", L2,
      [NOW, W("ContactSensor.Contact == false"), nn(L2, "The door has opened")],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D4", tier="T1",
      tsvc=tsvc())
    X(407, "If the window stays open, switch the air conditioner off.", L1,
      [NOW, W("ContactSensor.Contact == false"),
       CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="contact", dev_trig="ContactSensor",
      d="D4", tier="T1")
    X(408, "If the door opens after hours, warn me.", L2,
      [NOW, W("ContactSensor.Contact == false"), IF(DARK,
       [nn(L2, "The door has opened")])],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D13", tier="T2",
      ctx="sun", tsvc=tsvc())
    X(409, "If the CO2 rises, remind us to ventilate.", L3,
      [NOW, W("CarbonDioxideSensor.CarbonDioxide > 800"),
       nn(L3, "Please ventilate the lab")],
      [], act="notify", trig="threshold", dev_trig="CarbonDioxideSensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(410, "If the TVOC goes above 500, warn me.", L2,
      [NOW, W("AirQualitySensor.TvocLevel > 500"), nn(L2, "The TVOC level is high")],
      [], act="notify", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(411, "If the temperature goes above 28, turn on the air conditioner.", L4,
      [NOW, W("TemperatureSensor.Temperature > 28"),
       CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner",)], act="ac", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    X(412, "If the air gets too dry, turn on the humidifier.", L1,
      [NOW, W("HumiditySensor.Humidity < 35"),
       CL("Humidifier.SetHumidifierMode", Mode="auto")],
      [("Humidifier",)], act="humidity", trig="threshold",
      dev_trig="HumiditySensor", d="D4", tier="T1")
    X(413, "If the air turns bad, start the air purifier.", L3,
      [NOW, W("CarbonDioxideSensor.CarbonDioxide > 800"),
       CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier", trig="threshold",
      dev_trig="CarbonDioxideSensor", d="D4", tier="T1")
    X(414, "When it gets dark, turn on the test bed lights.", L5,
      [NOW, W("LightSensor.Brightness < 100"), PON("Light")],
      [("Light", "TestBed")], act="light.on", trig="threshold",
      dev_trig="LightSensor", d="D4", tier="T1")
    X(415, "When it is bright, turn off the lab lights.", L5,
      [NOW, W("LightSensor.Brightness > 1000"), POFF("Light")],
      [("Light", "TestBed")], act="light.off", trig="threshold",
      dev_trig="LightSensor", d="D4", tier="T1")
    X(416, "If the equipment power spikes, let me know.", L4,
      [NOW, W("EnergyMeter.Power > 5000"), nn(L4, "The power draw spiked")],
      [], act="notify", trig="power", dev_trig="EnergyMeter", d="D4", tier="T1",
      tsvc=tsvc())
    RF(417, "When the robot arm starts moving, check it with the camera.", L4,
       "no_service", act="camera", dev_act="ArmRobot", trig="device",
       dev_trig="ArmRobot")
    X(418, "If the lab equipment stops, start it again.", L2,
      [NOW, W('ProductionMachine.MachineState == "idle"'),
       CL("ProductionMachine.Start")],
      [("ProductionMachine",)], act="machine", trig="device",
      dev_trig="ProductionMachine", d="D4", tier="T1")
    X(419, "If a leak is detected, tell me right away.", L2,
      [NOW, W("LeakSensor.Leakage == true"), nn(L2, "A leak was detected")],
      [], act="notify", trig="leak", dev_trig="LeakSensor", d="D4", tier="T1",
      tsvc=tsvc())
    X(420, "If gas is detected, turn on the ventilators and warn me.", L2,
      [NOW, W("GasSensor.Gas == true"),
       CL("Ventilator.SetVentilatorMode", Mode="exhaust"),
       nn(L2, "Gas was detected")],
      [("Ventilator",)], act="ventilator", trig="gas", dev_trig="GasSensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(421, "If smoke is detected, warn the whole lab.", L2,
      [NOW, W("SmokeDetector.Smoke == true"),
       CL("Siren.SetSirenMode", Mode="fire"), nn(L2, "Smoke was detected")],
      [("Siren",)], act="siren", trig="smoke", dev_trig="SmokeDetector",
      d="D4", tier="T1", tsvc=tsvc())
    # ── 시간/스케줄 자동화 ──
    X(422, "Turn off the lab lights at 6 pm.", L3, [CRON("0 18 * * *"),
      POFF("Light")], [("Light", "LabRoom")], act="light.off", trig="time",
      dev_trig="Clock", d="D6", tier="T1")
    X(423, "Turn on the air conditioner at 9 am.", L4, [CRON("0 9 * * *"),
      CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner",)], act="ac", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(424, "Turn on the air purifier at noon.", L3, [CRON("0 12 * * *"),
      CL("AirPurifier.SetAirPurifierMode", Mode="auto")],
      [("AirPurifier",)], act="purifier", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(425, "Send a ventilation reminder every morning.", L2, [CRON("0 9 * * *"),
      nn(L2, "Time to ventilate the lab")],
      [], act="notify", trig="time", dev_trig="Clock", d="D6", tier="T1",
      tsvc=tsvc())
    X(426, "Shut down the lab equipment at 7 pm on weekdays.", L2,
      [CRON("0 19 * * 1-5"), CL("ProductionMachine.Stop")],
      [("ProductionMachine",)], act="machine", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(427, "Run the robot vacuum every Friday at 5.", L1, [CRON("0 17 * * 5"),
      CL("RobotVacuumCleaner.SetRobotVacuumCleanerMode", Mode="auto")],
      [("RobotVacuumCleaner",)], act="vacuum", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(428, "Turn off the lab lights in 10 minutes.", L4, [NOW, DL("10 MIN"),
      POFF("Light")], [("Light", "LabRoom")], act="light.off", trig="timer",
      dev_trig="Clock", d="D2", tier="T2")
    X(429, "Turn off the air conditioner in an hour.", L1, [NOW, DL("1 HOUR"),
      CL("AirConditioner.SetAirConditionerMode", Mode="off")],
      [("AirConditioner",)], act="ac", trig="timer", dev_trig="Clock",
      d="D2", tier="T2")
    X(430, "Keep the ventilators running for 30 minutes.", L3,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="auto"), DL("30 MIN"),
       CL("Ventilator.SetVentilatorMode", Mode="off")],
      [("Ventilator",)], act="ventilator", trig="timer", dev_trig="Clock",
      d="D2", tier="T2")
    X(431, "Run the air purifier for just 2 hours.", L3,
      [NOW, CL("AirPurifier.SetAirPurifierMode", Mode="auto"), DL("2 HOUR"),
       CL("AirPurifier.SetAirPurifierMode", Mode="off")],
      [("AirPurifier",)], act="purifier", trig="timer", dev_trig="Clock",
      d="D2", tier="T2")
    X(432, "At night, when someone is on the test bed, turn the lights on low.", L5,
      [NOW, W("PresenceSensor.Presence == true"), IF(DARK, [bright(20)])],
      [("Light", "TestBed")], act="light.dim", trig="presence",
      dev_trig="PresenceSensor", d="D13", tier="T2", ctx="sun")
    X(433, "After hours, alert me whenever the cold room door opens.", L3,
      [NOW, W("ContactSensor.Contact == false"), IF(DARK,
       [nn(L3, "The door has opened")])],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D13", tier="T2",
      ctx="sun", tsvc=tsvc())
    # ── 실험/운영 모드 — 되묻기 ──
    A(434, "Run the experiment-start mode.", L2, [], act="light.scene", ref="vague")
    A(435, "The experiment is done.", L2, [], act="light.scene", ref="vague",
      tone="terse")
    A(436, "Put the lab back to its normal state.", L2, [], act="light.scene",
      ref="vague")
    A(437, "Turn on the equipment maintenance mode.", L2, [], act="light.scene",
      ref="vague")
    A(438, "Turn on the lab safety mode.", L2, [], act="light.scene", ref="vague")
    A(439, "Start demo mode.", L4, [], act="light.scene", ref="vague")
    A(440, "Switch on ventilation mode.", L2, [], act="ventilator", ref="vague")
    # ── 알림/보고 요청 ──
    X(441, "If the CO2 gets high, put it up on the dashboard.", L3,
      [NOW, W("CarbonDioxideSensor.CarbonDioxide > 800"),
       CL("NotificationProvider.SendToast", Message="The CO2 level is high")],
      [], act="notify", trig="threshold", dev_trig="CarbonDioxideSensor",
      d="D4", tier="T1", tsvc="NotificationProvider.SendToast")
    X(442, "When the door opens, show it on the screen.", L2,
      [NOW, W("ContactSensor.Contact == false"),
       CL("NotificationProvider.SendToast", Message="The door has opened")],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D4", tier="T1",
      tsvc="NotificationProvider.SendToast")
    X(443, "If the air quality gets bad, say it on the speaker.", L2,
      [NOW, W("AirQualitySensor.TvocLevel > 500"),
       CL("Speaker.Speak", Text="The air quality is bad")],
      [("Speaker",)], act="speaker", trig="threshold", dev_trig="AirQualitySensor",
      d="D4", tier="T1")
    X(444, "At 8:50, announce that the experiment starts in 10 minutes.", L4,
      [CRON("50 8 * * *"),
       CL("Speaker.Speak", Text="The experiment starts in 10 minutes")],
      [("Speaker",)], act="speaker", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    A(445, "If motion shows up after hours, send the manager a text.", L2, [],
      act="notify", dev_act="MessageSender", trig="motion", dev_trig="MotionSensor")
    A(446, "If gas is detected, send a KakaoTalk message to the person on duty.",
      L2, [], act="notify", dev_act="MessageSender", trig="gas",
      dev_trig="GasSensor")
    X(447, "If gas is detected, send a Slack message.", L2,
      [NOW, W("GasSensor.Gas == true"),
       CL("MessageSender.SendSlack", Message="Gas was detected in the lab")],
      [], act="notify", trig="gas", dev_trig="GasSensor", d="D4", tier="T1",
      tsvc="MessageSender.SendSlack")
    A(448, "When the door opens, send the manager an email.", L3, [], act="notify",
      dev_act="EmailProvider", trig="contact", dev_trig="ContactSensor")
    A(449, "Send me a camera snapshot by email.", L3, [], act="camera",
      dev_act="EmailProvider")
    RF(450, "Email me a summary of today's lab conditions.", L3, "no_service",
       act="query", dev_act="EmailProvider", b1="read")
    X(451, "If the CO2 stays high, ping me every 10 minutes.", L3,
      [NOW, W("CarbonDioxideSensor.CarbonDioxide > 800"),
       CY("10 MIN", [nn(L3, "The CO2 level is high")],
          until="not (CarbonDioxideSensor.CarbonDioxide > 800)")],
      [], act="notify", trig="threshold", dev_trig="CarbonDioxideSensor",
      d="D9", tier="T3", tsvc=tsvc())
    X(452, "If the door stays open, warn me over and over.", L2,
      [NOW, W("ContactSensor.Contact == false"),
       CY("5 MIN", [nn(L2, "The door has opened")],
          until="not (ContactSensor.Contact == false)")],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D9", tier="T3",
      tsvc=tsvc())
    X(453, "While gas keeps being detected, keep the warnings coming.", L2,
      [NOW, W("GasSensor.Gas == true"),
       CY("5 MIN", [nn(L2, "Gas was detected")],
          until="not (GasSensor.Gas == true)")],
      [], act="notify", trig="gas", dev_trig="GasSensor", d="D9", tier="T3",
      tsvc=tsvc())
    # ── 안전/보안 요청 ──
    X(454, "If someone is detected after hours, notify me.", L5,
      [NOW, W("PresenceSensor.Presence == true"), IF(DARK,
       [nn(L5, "Someone is in the room")])],
      [], act="notify", trig="presence", dev_trig="PresenceSensor", d="D13",
      tier="T2", ctx="sun", tsvc=tsvc())
    X(455, "If the lab door opens at night, warn me.", L1,
      [NOW, W("ContactSensor.Contact == false"), IF(DARK,
       [nn(L1, "The door has opened")])],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D13", tier="T2",
      ctx="sun", tsvc=tsvc())
    X(456, "If motion is detected while nobody is here, take a snapshot.", L1,
      [NOW, W("MotionSensor.Motion == true"),
       IF("PresenceSensor.Presence == false", [CL("Camera.CaptureImage")])],
      [("Camera",)], act="camera", trig="motion", dev_trig="MotionSensor",
      d="D13", tier="T2")
    X(457, "If smoke is detected, sound the lab-wide alarm.", L2,
      [NOW, W("SmokeDetector.Smoke == true"), CL("Siren.SetSirenMode", Mode="fire")],
      [("Siren",)], act="siren", trig="smoke", dev_trig="SmokeDetector",
      d="D4", tier="T1")
    X(458, "If gas is detected, start the ventilators and announce an evacuation.",
      L2,
      [NOW, W("GasSensor.Gas == true"),
       CL("Ventilator.SetVentilatorMode", Mode="exhaust"),
       CL("Speaker.Speak", Text="Gas detected, please evacuate")],
      [("Ventilator",), ("Speaker",)], act="ventilator", trig="gas",
      dev_trig="GasSensor", d="D4", tier="T1")
    A(459, "If water leaks, message the facility manager.", L2, [], act="notify",
      dev_act="MessageSender", trig="leak", dev_trig="LeakSensor")
    X(460, "If a person comes near, halt the robot arms.", L4,
      [NOW, W("PresenceSensor.Presence == true"),
       CL("ArmRobot.SendCommand", Command="stop")],
      [("ArmRobot",)], act="armrobot", trig="presence", dev_trig="PresenceSensor",
      d="D4", tier="T1")
    X(461, "If the equipment overheats, shut it down.", L2,
      [NOW, W("TemperatureSensor.Temperature > 60"), CL("ProductionMachine.Stop")],
      [("ProductionMachine",)], act="machine", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    A(462, "If anything odd is detected, record 10 seconds of video.", L2,
      [("Camera",)], act="camera", ref="vague")
    # ── 일상 정보/대화 ──
    A(463, "How is the lab doing today?", L2, [], act="query", tone="ask",
      b1="read", ref="vague")
    A(464, "Is any equipment having problems right now?", L2, [], act="query",
      tone="ask", b1="read", ref="vague")
    A(465, "Would it be fine to open the windows today?", L3, [], act="query", tone="ask",
      b1="read", ref="vague", ctx="weather")
    Q(466, "Do I have any experiments scheduled today?", L3,
      "CalendarProvider.TodayEventCount", "Count", "You have $Count events today",
      [], ctx="calendar", dev_act="CalendarProvider")
    # 467-468 싣지 않음 — 자기설명
    A(469, "Give me a rundown of the lab right now.", L2, [], act="query",
      tone="bare", b1="read", ref="vague")
    # 470-473 싣지 않음 — 자동화 관리
    # ── 모호함/실패/비지원 ──
    A(474, "Turn the lights off.", L2, [("Light",)], act="light.off", ref="plain")
    X(475, "Could you turn on the AC?", L4,
      [NOW, CL("AirConditioner.SetAirConditionerMode", Mode="cool")],
      [("AirConditioner",)], act="ac", tone="could", ref="plain")
    X(476, "Shut the equipment down.", L2, [NOW, CL("ProductionMachine.Stop")],
      [("ProductionMachine",)], act="machine", ref="plain", tone="terse")
    A(477, "Make the lab comfortable.", L2, [], act="ac", ref="vague")
    A(478, "Get things ready for the experiment.", L2, [], act="light.scene",
      ref="vague")
    A(479, "Send an email to the manager.", L3, [], act="notify", dev_act="EmailProvider")
    A(480, "Send me a notification.", L2, [], act="notify",
      dev_act="NotificationProvider")
    RF(481, "Lower the lab blinds.", L2, "no_device", act="cover",
       dev_act="WindowCovering")
    RF(482, "Stop the robot arm.", L2, "no_device", act="armrobot",
       dev_act="ArmRobot")
    # 483-484 싣지 않음 — 기기 한 대 능력 구분 1, "확인 없이" 1


# ══ farm (485–615) ═════════════════════════════════════════════════════
def sheet_farm():
    G1, G2, G3, G4 = "FARM01", "FARM02", "FARM03", "FARM04"
    # ── 기기 직접 제어 ──
    X(485, "Turn on the barn lights.", G2, [NOW, PON("Light")],
      [("Light", "Barn")], act="light.on")
    X(486, "Turn off the field lights.", G3, [NOW, POFF("Light")],
      [("Light", "Field")], act="light.off")
    X(487, "Turn off all the lights on the farm.", G2, [NOW, POFF("Light")],
      [("Light",)], act="light.off", ref="all")
    X(488, "Turn on the grow lights in greenhouse 1.", G1, [NOW, PON("GrowLight")],
      [("GrowLight", "Greenhouse", "greenhouse 1 ")], act="growlight", ref="nick")
    X(489, "Turn off all the grow lights in the grow room.", G4,
      [NOW, POFF("GrowLight")], [("GrowLight", "GrowRoom")], act="growlight",
      ref="all")
    X(490, "Start the irrigation pump.", G1, [NOW, CL("Pump.SetPumpMode",
      PumpMode="normal")], [("Pump",)], act="pump")
    X(491, "Stop the pumps in the utility room.", G4, [NOW, POFF("Pump")],
      [("Pump", "Utility")], act="pump")
    X(492, "Open the irrigation valve for greenhouse 1.", G1, [NOW, CL("Valve.Open")],
      [("Valve", "Greenhouse", "greenhouse 1 ")], act="valve", ref="nick")
    X(493, "Close all the greenhouse irrigation valves.", G1, [NOW, CL("Valve.Close")],
      [("Valve", "Greenhouse")], act="valve", ref="all")
    X(494, "Start the field sprinklers.", G3, [NOW, CL("Sprinkler.Start",
      Minutes=10.0)], [("Sprinkler", "Field")], act="sprinkler")
    X(495, "Turn off the zone 2 sprinkler.", G3, [NOW, CL("Sprinkler.Stop")],
      [("Sprinkler", "Field", "zone 2")], act="sprinkler", ref="nick")
    X(496, "Turn on the greenhouse ventilators.", G1,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="auto")],
      [("Ventilator", "Greenhouse")], act="ventilator")
    X(497, "Turn off the barn ventilators.", G2,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="off")],
      [("Ventilator", "Barn")], act="ventilator")
    X(498, "Turn on the barn humidifier.", G2,
      [NOW, CL("Humidifier.SetHumidifierMode", Mode="auto")],
      [("Humidifier", "Barn")], act="humidity")
    X(499, "Turn off the grow room dehumidifier.", G4,
      [NOW, CL("Dehumidifier.SetDehumidifierMode", Mode="off")],
      [("Dehumidifier", "GrowRoom")], act="humidity")
    X(500, "Run the barn 1 feeder.", G2, [NOW, CL("FeedDispenser.Dispense")],
      [("FeedDispenser", "Barn", "barn 1")], act="feeder", ref="nick")
    RF(501, "Stop the feed supply.", G2, "no_service", act="feeder",
       dev_act="FeedDispenser")
    X(502, "Turn on the greenhouse camera.", G1, [NOW, CL("Camera.StartStream")],
      [("Camera", "Greenhouse")], act="camera")
    # ── 기기 속성 조절 ──
    X(503, "Set the greenhouse grow lights to 70 percent.", G1,
      [NOW, CL("GrowLight.SetIntensity", Intensity=70.0)],
      [("GrowLight", "Greenhouse")], act="growlight", b1="set")
    X(504, "Brighten the grow room lights to full.", G4,
      [NOW, CL("GrowLight.SetIntensity", Intensity=100.0)],
      [("GrowLight", "GrowRoom")], act="growlight", b1="set")
    X(505, "Switch the grow lights to red light.", G4,
      [NOW, CL("GrowLight.SetSpectrum", Mode="red")],
      [("GrowLight", "GrowRoom")], act="growlight", b1="set", ref="plain")
    X(506, "Set the greenhouse grow lights to blue light.", G1,
      [NOW, CL("GrowLight.SetSpectrum", Mode="blue")],
      [("GrowLight", "Greenhouse")], act="growlight", b1="set")
    X(507, "Set the greenhouse to 24 degrees.", G1,
      [NOW, CL("Heater.SetTargetTemperature", Temperature=24.0)],
      [("Heater", "Greenhouse")], act="heater", b1="set")
    X(508, "Lower the grow room temperature to 22 degrees.", G4,
      [NOW, CL("AirConditioner.SetTargetTemperature", Temperature=22.0)],
      [("AirConditioner", "GrowRoom")], act="ac", b1="set")
    X(509, "Set the barn humidity to around 60 percent.", G2,
      [NOW, CL("Humidifier.SetTargetHumidity", Humidity=60.0)],
      [("Humidifier", "Barn")], act="humidity", b1="set")
    X(510, "Crank the ventilators up to high.", G4,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="high")],
      [("Ventilator", "GrowRoom")], act="ventilator", b1="set", ref="plain")
    A(511, "Set the watering time to 10 minutes.", G1, [], act="sprinkler",
      ref="vague", b1="set")
    A(512, "Water zone 1 a bit longer.", G3, [], act="sprinkler", ref="vague",
      b1="set")
    # ── 공간/작물 상태 조회 ──
    Q(513, "What is the temperature in the greenhouse right now?", G1,
      "TemperatureSensor.Temperature", "Temperature", "The temperature is $Temperature",
      [("TemperatureSensor", "Greenhouse")], ref="place")
    Q(514, "What is the humidity in the grow room?", G4,
      "HumiditySensor.Humidity", "Humidity", "The humidity is $Humidity",
      [("HumiditySensor", "GrowRoom")], ref="place")
    Q(515, "Tell me the CO2 level in the greenhouse.", G1,
      "CarbonDioxideSensor.CarbonDioxide", "CO2", "The CO2 level is $CO2",
      [("CarbonDioxideSensor", "Greenhouse")], tone="bare", ref="place")
    RF(516, "Is the air quality in the greenhouse okay?", G1, "no_device",
       act="query", dev_act="AirQualitySensor", tone="ask", b1="read")
    Q(517, "Is the greenhouse bright enough right now?", G1,
      "LightSensor.Brightness", "Brightness", "The brightness is $Brightness",
      [("LightSensor", "Greenhouse")], ref="place")
    Q(518, "How much sunlight did we get today?", G3,
      "LightSensor.Brightness@avg:today", "Avg", "Today's average brightness is $Avg",
      [("LightSensor", "Field")], d="D12", tier="T4")
    Q(519, "Is the soil dry?", G1,
      "SoilMoistureSensor.SoilMoisture", "Moisture", "The soil moisture is $Moisture",
      [("SoilMoistureSensor", "Greenhouse")], ref="plain")
    Q(520, "Tell me the soil moisture for greenhouse 1.", G1,
      "SoilMoistureSensor.SoilMoisture", "Moisture", "The soil moisture is $Moisture",
      [("SoilMoistureSensor", "Greenhouse", "greenhouse 1 ")], tone="bare",
      ref="nick")
    Q(521, "How much water is left in the tank?", G1,
      "WaterLevelSensor.WaterLevel", "Level", "The tank level is $Level",
      [("WaterLevelSensor",)])
    Q(522, "Is the nutrient water quality okay?", G1,
      "WaterQualitySensor.Ph", "Ph", "The nutrient pH is $Ph",
      [("WaterQualitySensor",)])
    Q(523, "Is the irrigation pump running?", G1,
      "Pump.PumpMode", "Mode", "The pump is $Mode", [("Pump",)])
    Q(524, "Are the sprinklers on?", G3,
      "Sprinkler.SprinklerState", "State", "The sprinklers read $State",
      [("Sprinkler", "Field")], ref="plain")
    Q(525, "Are the barn ventilators off?", G2,
      "Ventilator.VentilatorMode", "Mode", "The ventilators are $Mode",
      [("Ventilator", "Barn")], ref="place")
    Q(526, "Any motion out in the field?", G3,
      "MotionSensor.Motion", "Motion", "Motion reads $Motion",
      [("MotionSensor", "Field")], ref="place")
    Q(527, "Is the barn temperature okay?", G2,
      "TemperatureSensor.Temperature", "Temperature", "The temperature is $Temperature",
      [("TemperatureSensor", "Barn")], ref="place")
    Q(528, "What was the average greenhouse temperature today?", G1,
      "TemperatureSensor.Temperature@avg:today", "Avg", "Today's average is $Avg",
      [("TemperatureSensor", "Greenhouse")], d="D12", tier="T4", ref="place")
    Q(529, "How did the humidity change over the last hour?", G1,
      "HumiditySensor.Humidity", "Now", "It is $Now now, an hour ago it was $Prev",
      [("HumiditySensor", "Greenhouse")],
      extra=[("Prev", "HumiditySensor.Humidity@-1HOUR")], d="D11", tier="T4")
    RF(530, "Summarize this week's irrigation records.", G1, "no_service",
       act="query", dev_act="Pump", b1="read")
    Q(531, "Is the soil drier than yesterday?", G1,
      "SoilMoistureSensor.SoilMoisture", "Now",
      "It is $Now now, yesterday it was $Prev",
      [("SoilMoistureSensor", "Greenhouse")],
      extra=[("Prev", "SoilMoistureSensor.SoilMoisture@-1DAY")],
      d="D11", tier="T4")
    # ── 조건 기반 자동화 ──
    X(532, "If the soil gets dry, water the plants.", G1,
      [NOW, W("SoilMoistureSensor.SoilMoisture < 30"),
       CL("Sprinkler.Start", Minutes=10.0)],
      [("Sprinkler", "Greenhouse")], act="sprinkler", trig="threshold",
      dev_trig="SoilMoistureSensor", d="D4", tier="T1")
    X(533, "If the greenhouse 1 soil moisture gets low, start the irrigation pump.",
      G1,
      [NOW, W("SoilMoistureSensor.SoilMoisture < 30"),
       CL("Pump.SetPumpMode", PumpMode="normal")],
      [("Pump",)], act="pump", trig="threshold", dev_trig="SoilMoistureSensor",
      d="D4", tier="T1")
    X(534, "Once the soil is moist enough, stop the watering.", G1,
      [NOW, W("SoilMoistureSensor.SoilMoisture > 60"), CL("Sprinkler.Stop")],
      [("Sprinkler", "Greenhouse")], act="sprinkler", trig="threshold",
      dev_trig="SoilMoistureSensor", d="D4", tier="T1")
    X(535, "If the greenhouse goes above 30 degrees, turn on the ventilators.", G1,
      [NOW, W("TemperatureSensor.Temperature > 30"),
       CL("Ventilator.SetVentilatorMode", Mode="auto")],
      [("Ventilator", "Greenhouse")], act="ventilator", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    X(536, "If the temperature gets low, turn on the heater.", G1,
      [NOW, W("TemperatureSensor.Temperature < 12"), CL("Heater.On")],
      [("Heater", "Greenhouse")], act="heater", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    X(537, "If the barn gets hot, ventilate it.", G2,
      [NOW, W("TemperatureSensor.Temperature > 30"),
       CL("Ventilator.SetVentilatorMode", Mode="auto")],
      [("Ventilator", "Barn")], act="ventilator", trig="threshold",
      dev_trig="TemperatureSensor", d="D4", tier="T1")
    X(538, "If the barn air gets dry, run the humidifier.", G2,
      [NOW, W("HumiditySensor.Humidity < 50"),
       CL("Humidifier.SetHumidifierMode", Mode="auto")],
      [("Humidifier", "Barn")], act="humidity", trig="threshold",
      dev_trig="HumiditySensor", d="D4", tier="T1")
    X(539, "If it gets too humid, run the dehumidifier.", G4,
      [NOW, W("HumiditySensor.Humidity > 85"),
       CL("Dehumidifier.SetDehumidifierMode", Mode="auto")],
      [("Dehumidifier", "GrowRoom")], act="humidity", trig="threshold",
      dev_trig="HumiditySensor", d="D4", tier="T1")
    X(540, "If the CO2 drops below 400, send me an alert.", G4,
      [NOW, W("CarbonDioxideSensor.CarbonDioxide < 400"),
       nn(G4, "The CO2 level is low")],
      [], act="notify", trig="threshold", dev_trig="CarbonDioxideSensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(541, "If the ammonia level gets high, ventilate the barn.", G2,
      [NOW, W("GasSensor.GasLevel > 200"),
       CL("Ventilator.SetVentilatorMode", Mode="exhaust")],
      [("Ventilator", "Barn")], act="ventilator", trig="gas",
      dev_trig="GasSensor", d="D4", tier="T1")
    X(542, "When the sun sets, turn on the grow lights.", G1,
      [NOW, W(DARK), PON("GrowLight")], [("GrowLight", "Greenhouse")],
      act="growlight", trig="sun", dev_trig="SunProvider", d="D4", tier="T1",
      ctx="sun")
    X(543, "If there is not enough light, turn on the greenhouse grow lights.", G1,
      [NOW, W("LightSensor.Brightness < 1000"), PON("GrowLight")],
      [("GrowLight", "Greenhouse")], act="growlight", trig="threshold",
      dev_trig="LightSensor", d="D4", tier="T1")
    X(544, "If it starts raining, stop the sprinklers and let me know.", G3,
      [NOW, W("RainSensor.Rain == true"), CL("Sprinkler.Stop"),
       nn(G3, "It is raining, sprinklers stopped")],
      [("Sprinkler", "Field")], act="sprinkler", trig="weather",
      dev_trig="RainSensor", d="D4", tier="T1", tsvc=tsvc())
    X(545, "If the wind picks up, close the greenhouse screens.", G1,
      [NOW, W("WindSensor.WindSpeed > 8"), CL("WindowCovering.DownOrClose")],
      [("WindowCovering", "Greenhouse")], act="cover", trig="wind",
      dev_trig="WindSensor", d="D4", tier="T1")
    X(546, "If the tank level gets low, start the refill pump.", G1,
      [NOW, W("WaterLevelSensor.WaterLevel < 50"),
       CL("Pump.SetPumpMode", PumpMode="normal")],
      [("Pump",)], act="pump", trig="threshold", dev_trig="WaterLevelSensor",
      d="D4", tier="T1")
    X(547, "If the nutrient pH drops below 5.5, let me know.", G1,
      [NOW, W("WaterQualitySensor.Ph < 5.5"), nn(G1, "The nutrient pH is off")],
      [], act="notify", trig="threshold", dev_trig="WaterQualitySensor",
      d="D4", tier="T1", tsvc=tsvc())
    X(548, "If nothing moves in the field for 30 minutes, let me know.", G3,
      [NOW, W("MotionSensor.Motion == false", edge="none", for_="30 MIN"),
       nn(G3, "No motion in the field")],
      [], act="notify", trig="motion", dev_trig="MotionSensor", d="D5", tier="T2",
      tsvc=tsvc())
    X(549, "If the feed runs low, send me an alert.", G2,
      [NOW, W("FeedDispenser.FeedLevel < 20"), nn(G2, "The feed is running low")],
      [], act="notify", trig="threshold", dev_trig="FeedDispenser",
      d="D4", tier="T1", tsvc=tsvc())
    X(550, "If the irrigation pump stops, turn it back on.", G1,
      [NOW, W("Pump.FlowRate == 0"), CL("Pump.SetPumpMode", PumpMode="normal")],
      [("Pump",)], act="pump", trig="device", dev_trig="Pump", d="D4", tier="T1")
    X(551, "If a barn ventilator stops, let me know.", G2,
      [NOW, W('Ventilator.VentilatorMode == "off"'),
       nn(G2, "A ventilator has stopped")],
      [], act="notify", trig="device", dev_trig="Ventilator", d="D4", tier="T1",
      tsvc=tsvc())
    # ── 시간/스케줄 자동화 ──
    X(552, "Turn on the greenhouse grow lights at 7 am.", G1, [CRON("0 7 * * *"),
      PON("GrowLight")], [("GrowLight", "Greenhouse")], act="growlight",
      trig="time", dev_trig="Clock", d="D6", tier="T1")
    X(553, "Turn off the grow lights at 6 pm.", G4, [CRON("0 18 * * *"),
      POFF("GrowLight")], [("GrowLight", "GrowRoom")], act="growlight",
      trig="time", dev_trig="Clock", d="D6", tier="T1", ref="plain")
    X(554, "Water the field at 8 am.", G3, [CRON("0 8 * * *"),
      CL("Sprinkler.Start", Minutes=10.0)], [("Sprinkler", "Field")],
      act="sprinkler", trig="time", dev_trig="Clock", d="D6", tier="T1")
    X(555, "Ventilate the greenhouse every morning.", G1, [CRON("0 8 * * *"),
      CL("Ventilator.SetVentilatorMode", Mode="auto")],
      [("Ventilator", "Greenhouse")], act="ventilator", trig="time",
      dev_trig="Clock", d="D6", tier="T1")
    X(556, "Send a valve-check reminder every Monday.", G1, [CRON("0 9 * * 1"),
      nn(G1, "Time to check the irrigation valves")],
      [], act="notify", trig="time", dev_trig="Clock", d="D6", tier="T1",
      tsvc=tsvc())
    X(557, "Check the barn temperature every evening.", G2, [CRON("0 18 * * *"),
      RD("Temperature", "TemperatureSensor.Temperature"),
      nn(G2, "The barn temperature is $Temperature")],
      [("TemperatureSensor", "Barn")], act="query", trig="time", dev_trig="Clock",
      d="D6", tier="T1", b1="read", tsvc=tsvc(), ref="place")
    X(558, "Turn off the irrigation pump in 10 minutes.", G1, [NOW, DL("10 MIN"),
      POFF("Pump")], [("Pump",)], act="pump", trig="timer", dev_trig="Clock",
      d="D2", tier="T2")
    X(559, "Stop the sprinklers in 30 minutes.", G3, [NOW, DL("30 MIN"),
      CL("Sprinkler.Stop")], [("Sprinkler", "Field")], act="sprinkler",
      trig="timer", dev_trig="Clock", d="D2", tier="T2")
    X(560, "Water the field for 20 minutes.", G3,
      [NOW, CL("Sprinkler.Start", Minutes=20.0)], [("Sprinkler", "Field")],
      act="sprinkler", trig="timer", dev_trig="Clock", d="D2", tier="T2")
    X(561, "Run the barn ventilators for 2 hours.", G2,
      [NOW, CL("Ventilator.SetVentilatorMode", Mode="auto"), DL("2 HOUR"),
       CL("Ventilator.SetVentilatorMode", Mode="off")],
      [("Ventilator", "Barn")], act="ventilator", trig="timer", dev_trig="Clock",
      d="D2", tier="T2")
    X(562, "At night, if the greenhouse gets cold, turn on the heater.", G1,
      [NOW, W("TemperatureSensor.Temperature < 12"), IF(DARK, [CL("Heater.On")])],
      [("Heater", "Greenhouse")], act="heater", trig="threshold",
      dev_trig="TemperatureSensor", d="D13", tier="T2", ctx="sun")
    X(563, "During the day, if there is not enough light, turn on the grow lights.",
      G1,
      [NOW, W("LightSensor.Brightness < 1000"),
       IF("SunProvider.IsDaylight == true", [PON("GrowLight")])],
      [("GrowLight", "Greenhouse")], act="growlight", trig="threshold",
      dev_trig="LightSensor", d="D13", tier="T2", ctx="sun")
    # ── 농장/재배 운영 모드 — 되묻기 ──
    A(564, "Run the growing-start mode.", G1, [], act="light.scene", ref="vague")
    A(565, "We're done with farm work for today.", G1, [], act="light.scene",
      ref="vague", tone="terse")
    A(566, "Turn on irrigation mode.", G1, [], act="sprinkler", ref="vague")
    A(567, "Run ventilation mode.", G1, [], act="ventilator", ref="vague")
    A(568, "Switch the greenhouse to night mode.", G1, [], act="light.scene",
      ref="vague")
    A(569, "Run the heat-wave response mode.", G1, [], act="light.scene",
      ref="vague")
    A(570, "Turn on inspection mode.", G1, [], act="light.scene", ref="vague")
    # ── 알림/보고 요청 ──
    X(571, "If the soil gets dry, put it up on the dashboard.", G1,
      [NOW, W("SoilMoistureSensor.SoilMoisture < 30"),
       CL("NotificationProvider.SendToast", Message="The soil is dry")],
      [], act="notify", trig="threshold", dev_trig="SoilMoistureSensor",
      d="D4", tier="T1", tsvc="NotificationProvider.SendToast")
    X(572, "If the grow room gets hot, warn me on the screen.", G4,
      [NOW, W("TemperatureSensor.Temperature > 30"),
       CL("Display.ShowMessage", Message="The grow room is hot",
          DurationSeconds=10.0)],
      [], act="notify", trig="threshold", dev_trig="TemperatureSensor",
      d="D4", tier="T1", tsvc="Display.ShowMessage")
    X(573, "Every morning at 8:50, broadcast that work begins in 10 minutes.", G2,
      [CRON("50 8 * * *"), CL("Speaker.Speak", Text="Work starts in 10 minutes")],
      [("Speaker", "Barn")], act="speaker", trig="time", dev_trig="Clock",
      d="D6", tier="T1")
    X(574, "If the CO2 gets too high, say that we should ventilate.", G4,
      [NOW, W("CarbonDioxideSensor.CarbonDioxide > 3000"),
       CL("Speaker.Speak", Text="Please ventilate the grow room")],
      [("Speaker", "GrowRoom")], act="speaker", trig="threshold",
      dev_trig="CarbonDioxideSensor", d="D4", tier="T1")
    A(575, "If something looks wrong in the greenhouse, text the manager.", G1,
      [], act="notify", dev_act="MessageSender", ref="vague")
    A(576, "If the water level gets low, send a KakaoTalk message to the person on duty.",
      G1, [], act="notify", dev_act="MessageSender", trig="threshold",
      dev_trig="WaterLevelSensor")
    X(577, "If the nutrient readings go off, send a Slack message.", G4,
      [NOW, W("WaterQualitySensor.Ph < 5.5"),
       CL("MessageSender.SendSlack", Message="The nutrient pH is off")],
      [], act="notify", trig="threshold", dev_trig="WaterQualitySensor",
      d="D4", tier="T1", tsvc="MessageSender.SendSlack")
    RF(578, "Email me a summary of today's greenhouse conditions.", G1,
       "no_service", act="query", dev_act="EmailProvider", b1="read")
    RF(579, "Send me a camera photo by email.", G1, "no_device", act="camera",
       dev_act="EmailProvider")
    X(580, "While the soil stays dry, remind me every 10 minutes.", G1,
      [NOW, W("SoilMoistureSensor.SoilMoisture < 30"),
       CY("10 MIN", [nn(G1, "The soil is dry")],
          until="not (SoilMoistureSensor.SoilMoisture < 30)")],
      [], act="notify", trig="threshold", dev_trig="SoilMoistureSensor",
      d="D9", tier="T3", tsvc=tsvc())
    X(581, "While the tank level stays low, keep warning me.", G4,
      [NOW, W("WaterLevelSensor.WaterLevel < 50"),
       CY("10 MIN", [nn(G4, "The tank level is low")],
          until="not (WaterLevelSensor.WaterLevel < 50)")],
      [], act="notify", trig="threshold", dev_trig="WaterLevelSensor",
      d="D9", tier="T3", tsvc=tsvc())
    # ── 안전/보안 요청 ──
    X(582, "If the grow room door opens at night, warn me.", G4,
      [NOW, W("ContactSensor.Contact == false"), IF(DARK,
       [nn(G4, "The door has opened")])],
      [], act="notify", trig="contact", dev_trig="ContactSensor", d="D13", tier="T2",
      ctx="sun", tsvc=tsvc())
    X(583, "If motion is detected outside, check it with the cameras.", G3,
      [NOW, W("MotionSensor.Motion == true"), CL("Camera.CaptureImage")],
      [("Camera", "Field")], act="camera", trig="motion", dev_trig="MotionSensor",
      d="D4", tier="T1")
    RF(584, "If there is motion while nobody is at the farm, alert me.", G4,
       "no_device", act="notify", dev_act="MotionSensor", trig="motion",
       dev_trig="MotionSensor")
    RF(585, "If smoke is detected, sound the farm-wide alarm.", G2, "no_device",
       act="siren", dev_act="SmokeDetector", trig="smoke",
       dev_trig="SmokeDetector")
    X(586, "If ammonia is detected, ventilate and announce an evacuation.", G2,
      [NOW, W("GasSensor.GasLevel > 200"),
       CL("Ventilator.SetVentilatorMode", Mode="exhaust"),
       CL("Speaker.Speak", Text="Gas detected, please evacuate")],
      [("Ventilator", "Barn"), ("Speaker", "Barn")], act="ventilator", trig="gas",
      dev_trig="GasSensor", d="D4", tier="T1")
    RF(587, "If a water leak shows up, stop the pumps and tell me.", G1, "no_device",
       act="pump", dev_act="LeakSensor", trig="leak", dev_trig="LeakSensor")
    X(588, "If the barn temperature hits a dangerous level, alert me.", G2,
      [NOW, W("TemperatureSensor.Temperature > 35"),
       nn(G2, "The barn temperature is dangerous")],
      [], act="notify", trig="threshold", dev_trig="TemperatureSensor",
      d="D4", tier="T1", tsvc=tsvc())
    RF(589, "If the feeder stops working, let me know.", G2, "no_service",
       act="notify", dev_act="FeedDispenser", trig="device",
       dev_trig="FeedDispenser")
    A(590, "If anything odd happens, record 10 seconds of video.", G1,
      [("Camera", "Greenhouse")], act="camera", ref="vague")
    # ── 일상 정보/대화 ──
    A(591, "How is the greenhouse doing today?", G1, [], act="query", tone="ask",
      b1="read", ref="vague")
    A(592, "Is any zone having problems right now?", G1, [], act="query",
      tone="ask", b1="read", ref="vague")
    X(593, "Tell me whether the soil needs watering.", G1,
      [NOW, RD("Moisture", "SoilMoistureSensor.SoilMoisture"),
       IF("SoilMoistureSensor.SoilMoisture < 30",
          [nn(G1, "The soil is dry, watering is needed")],
          [nn(G1, "The soil is moist enough")])],
      [("SoilMoistureSensor", "Greenhouse")], act="query", b1="read", d="D3",
      tier="T2", tsvc=tsvc(), tone="bare")
    A(594, "Is it okay to ventilate today?", G1, [], act="query", tone="ask",
      b1="read", ref="vague", ctx="weather")
    Q(595, "Is it raining out there right now?", G1, "WeatherProvider.Weather", "Weather",
      "The weather is $Weather", [("WeatherProvider", "Outdoor")], ctx="weather")
    RF(596, "Is there a strong wind forecast for today?", G1, "no_service",
       act="query", dev_act="WeatherProvider", tone="ask", b1="read",
       ctx="weather")
    RF(597, "Is there an inspection scheduled today?", G1, "no_device",
       act="query", dev_act="CalendarProvider", tone="ask", b1="read",
       ctx="calendar")
    # 598-599 싣지 않음 — 자기설명
    A(600, "Give me a rundown of the farm right now.", G1, [], act="query",
      tone="bare", b1="read", ref="vague")
    # 601-604 싣지 않음 — 자동화 관리
    # ── 모호함/실패/비지원 ──
    A(605, "Water the plants.", G1, [("Sprinkler", "Greenhouse"),
      ("Valve", "Greenhouse")], act="sprinkler", ref="vague", tone="terse")
    A(606, "Ventilate this place.", G1, [("Ventilator", "Greenhouse"),
      ("WindowCovering", "Greenhouse")], act="ventilator", ref="vague")
    X(607, "Switch off the lights.", G4, [NOW, POFF("GrowLight")],
      [("GrowLight", "GrowRoom")], act="growlight", ref="plain")
    A(608, "Get the greenhouse into good shape.", G1, [], act="query", ref="vague")
    A(609, "Help the crops grow well.", G1, [], act="growlight", ref="vague")
    A(610, "Send the manager a report.", G1, [], act="notify",
      dev_act="MessageSender", ref="vague")
    A(611, "Send an alert.", G1, [], act="notify", dev_act="NotificationProvider")
    RF(612, "Turn on the zone 6 sprinkler.", G3, "no_device", act="sprinkler",
       dev_act="Sprinkler")
    RF(613, "Close the nutrient valve.", G2, "no_device", act="valve",
       dev_act="Valve")
    RF(614, "Put the barn lights into grow light mode.", G2, "no_service",
       act="light.color", dev_act="Light", b1="set")
    # 615 싣지 않음 — "확인 없이"


# ══ 검산과 출력 ═════════════════════════════════════════════════════════
# kind ← space_id, n_target ← targets, match ← expect 라서 안 싣는다. tone 은 안 쓴다.
COLS = ["id", "space_id", "command", "mode", "trig", "act", "dev_trig",
        "dev_act", "ref", "expect", "d", "tier", "b1", "b3", "context",
        "why", "targets", "target_svc", "ir_gt"]


def validate():
    bad = []
    seen = {}
    for r in ROWS:
        rid = r["id"]
        if r["command"] in seen:
            bad.append(f"{rid} 문장이 {seen[r['command']]} 와 겹침")
        seen[r["command"]] = rid
        t = r["targets"].split()
        devs_ = S[r["space_id"]]["devices"]
        for d in t:
            if d not in devs_:
                bad.append(f"{rid} 없는 기기 {d}")
        if (r["expect"] == "ask") != (r["match"] == "ask"):
            bad.append(f"{rid} 되묻기와 채점이 어긋남")
        if r["expect"] == "refuse" and (t or r["target_svc"]):
            bad.append(f"{rid} 거절인데 대상이 있음")
        if r["expect"] == "refuse" and not r["why"]:
            bad.append(f"{rid} 거절인데 이유가 없음")
        if r["match"] == "all" and not t and not r["target_svc"]:
            bad.append(f"{rid} 전부 맞춰야 하는데 대상이 없음")
        if r["expect"] == "execute" and not r["ir_gt"]:
            bad.append(f"{rid} 실행인데 정답 IR 이 없음")
        if r["expect"] != "execute" and r["ir_gt"]:
            bad.append(f"{rid} 실행이 아닌데 정답 IR 이 있음")
        # 거절 no_device: 그 기기가 정말 없는가
        if r["why"] == "no_device" and r["dev_act"] in CATS[r["space_id"]]:
            # 방·별명 한정 거절(라인 4, 6번 구역)은 카테고리가 있어도 된다 —
            # 문장 속 한정어가 없는 기기를 가리킨다. 그 경우만 통과시킨다.
            # "라인 4"·"6번 구역"·"양액 밸브"(축사엔 급수 밸브뿐) — 한정어가
            # 가리키는 그 기기가 없다. 카테고리가 있어도 거절이 맞다.
            if not any(w in r["command"] for w in ("line 4", "zone 6",
                                                   "nutrient valve")):
                bad.append(f"{rid} 거절인데 {r['dev_act']} 가 "
                           f"{r['space_id']} 에 있음")
        if r["ir_gt"]:
            ir = json.loads(r["ir_gt"])
            bad += IR.check_ir(ir, {k: v for k, v in CAT.items()
                                    if not k.startswith("$")},
                               rid, CATS[r["space_id"]])
            if t:
                tc = set()
                for d in t:
                    tc |= set(S[r["space_id"]]["devices"][d]["category"])
                import re as _re
                for tg in _re.findall(r'"target": "([^"]+)"', r["ir_gt"]):
                    c0 = tg.split(".")[0]
                    if c0 not in tc and c0 not in (
                            "Switch", "NotificationProvider", "Speaker",
                            "Display", "Clock", "GlobalVariable",
                            "MessageSender"):
                        bad.append(f"{rid} 지목한 기기가 {c0} 서비스를 못 함")
    return bad


def main():
    for f in (sheet_home, sheet_office, sheet_factory, sheet_lab, sheet_farm):
        f()
    ROWS.sort(key=lambda r: r["idx"])
    for i, r in enumerate(ROWS, 1):
        r["id"] = f"U{i:04d}"

    bad = validate()
    print(f"usecase 행 {len(ROWS)}개 (원본 616 중, 뺀 것 {616 - len(ROWS)})")
    import collections
    print("판정:", dict(collections.Counter(r["expect"] for r in ROWS)))
    print("도메인:", dict(collections.Counter(r["kind"] for r in ROWS)))
    print("난이도:", dict(sorted(collections.Counter(r["tier"] for r in ROWS).items())))
    print(f"검산: 어긋난 것 {len(bad)}건")
    for b in bad[:20]:
        print("  !", b)
    if bad:
        sys.exit(1)

    # dataset_5k.csv 에 반영 — 기존 U행을 걷어내고 다시 얹는다(멱등)
    path = os.path.join(HERE, "dataset_5k.csv")
    kept = [r for r in csv.DictReader(open(path, encoding="utf-8"))
            if not r["id"].startswith("U")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in kept:
            w.writerow({k: r[k] for k in COLS})
        for r in ROWS:
            w.writerow({k: r[k] for k in COLS})
    print(f"dataset_5k.csv: {len(kept)} + {len(ROWS)} = {len(kept) + len(ROWS)}문장")


if __name__ == "__main__":
    main()
