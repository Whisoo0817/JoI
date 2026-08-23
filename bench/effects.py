#!/usr/bin/env python3
"""서비스가 실세계에 주는 효과 — 카탈로그 3.0.0 의 함수 서비스 184개 전부.

왜 필요한가
  "시원하게 해줘" 는 기기를 안 댄다. 무엇이 시원하게 만드는지 알아야 후보를 찾는다.
  descriptor 산문으로는 안 된다 — Fan.SetFanMode 의 설명에 "cool" 이 없어서
  선풍기가 검색에 안 걸린다. 그래서 서비스마다 "이걸 실행하면 세상에서 무엇이 바뀌나"
  를 정해진 단어로 적는다.

직접 효과만 적는다
  블라인드를 닫으면 낮에는 온도가 내려가지만 밤에는 아니다. 그런 간접 효과는 조건이
  붙어 애매해서 뺀다. 그 서비스가 *그 기기로* 바로 바꾸는 것만 적는다.

표기
  quantity+   그 양을 올린다          quantity-   내린다
  quantity=   인자 값으로 맞춘다      quantity~   바꾸되 방향이 인자에 달렸다
  enum 인자는 값마다 효과가 갈리므로 dict 로 적는다. "*" 는 나머지 전부.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(os.path.dirname(HERE), "files", "service_list_ver3.0.0.json")

# ── 효과 어휘 (이름표) ──────────────────────────────────────────────────
# 이 밖의 단어는 못 쓴다. 검증이 막는다.
VOCAB = {
    # 환경 — 센서가 재는 것과 같은 이름
    "temperature":     "방 온도 (온도계 숫자)",
    "thermal_comfort": "사람이 느끼는 시원함·따뜻함. 선풍기는 온도를 못 내리지만 이건 내린다",
    "humidity":        "습도",
    "air_quality":     "공기질 — 미세먼지·CO2·냄새가 좋아지면 +",
    "air_motion":      "바람·공기 흐름",
    "illuminance":     "밝기",
    "color":           "빛의 색",
    "sound":           "소리 크기",
    "power_draw":      "쓰는 전기",
    "water_flow":      "물 흐름 (밸브·펌프·스프링클러)",
    "water_level":     "탱크 수위",
    "water_temperature": "물 온도",
    "soil_moisture":   "토양 수분",
    "light_spectrum":  "빛의 파장 (식물용)",
    # 상태 — 기기가 어떤 상태에 있나
    "openness":        "열림 정도 (문·창·커튼·차고)",
    "locked":          "잠김",
    "running":         "기기가 돌고 있나 — 전원이 켜져 있다는 뜻. 모든 켜기·끄기가 이걸 가진다",
    "process":         "사이클이 돌고 있나 (세탁·건조·설거지·조리·인쇄·생산)",
    "motion_run":      "움직이는 기기가 움직이고 있나 (청소기·컨베이어·로봇팔·잔디깎이·컴프레서)",
    "recording":       "녹화·녹음 중",
    "position":        "물리적 위치 (로봇팔·청소기 도킹)",
    "floor_clean":     "바닥·잔디가 깨끗해짐 (청소기·잔디깎이)",
    "item_clean":      "옷·그릇·기구가 깨끗해짐 (세탁·건조·설거지·의류관리·살균)",
    "cooked":          "음식이 익음",
    "charge":          "배터리 충전량",
    "visual_signal":   "눈에 보이는 신호 (상태등·깜빡임·화면)",
    "audio_signal":    "귀에 들리는 신호 (차임·사이렌·안내 음성)",
    "message_sent":    "사람에게 메시지가 간다",
    "data_out":        "정보를 돌려준다 (읽기·조회·생성)",
    "variable":        "전역 변수 값",
    "count":           "누적 횟수·카운터",
    "feed":            "사료·물 배급",
    "halted":          "비상 정지",
    "media":           "재생 중인 콘텐츠",
    "enrolled":        "등록된 얼굴·데이터",
}

# ── 184 개 ────────────────────────────────────────────────────────────
E = {}

E["AirCompressor"] = {"Start": ["motion_run+", "running+", "power_draw+", "sound+"],
                      "Stop":  ["motion_run-", "running-", "power_draw-", "sound-"]}
E["AirConditioner"] = {
    "SetAirConditionerMode": {
        "cool": ["temperature-", "thermal_comfort-", "power_draw+"],
        "heat": ["temperature+", "thermal_comfort+", "power_draw+"],
        "dry":  ["humidity-", "power_draw+"],
        "fan":  ["air_motion+", "thermal_comfort-"],
        "auto": ["temperature~", "power_draw+"],
        "off":  ["running-", "power_draw-"]},
    "SetTargetTemperature": ["temperature=", "thermal_comfort="],
    "SetFanMode":  ["air_motion=", "sound~"],
    "SetSwingMode": ["air_motion~"]}
E["AirPurifier"] = {"SetAirPurifierMode": {
    "off": ["running-", "power_draw-"],
    "*":   ["air_quality+", "air_motion+", "sound~", "power_draw+"]}}
E["ArmRobot"] = {"SendCommand": ["position~", "motion_run+"],
                 "SetPosition": ["position="],
                 "Hello": ["position~"]}
E["AudioRecorder"] = {"RecordStart": ["recording+"], "RecordStop": ["recording-", "data_out+"],
                      "RecordWithDuration": ["recording+", "data_out+"]}
E["CalendarProvider"] = {"GetNextEvent": ["data_out+"]}
E["Camera"] = {"StartStream": ["recording+"], "StopStream": ["recording-"],
               "CaptureImage": ["data_out+"], "CaptureVideo": ["recording+", "data_out+"],
               "StartRecording": ["recording+"], "StopRecording": ["recording-"]}
E["Chamber"] = {
    "SetChamberMode": {
        "off": ["running-", "power_draw-"], "heat": ["temperature+"],
        "cool": ["temperature-"], "humidify": ["humidity+"], "dehumidify": ["humidity-"],
        "sterilize": ["item_clean+", "temperature+"], "auto": ["temperature~", "humidity~"]},
    "SetTargetTemperature": ["temperature="],
    "SetTargetHumidity": ["humidity="]}
E["ChatProvider"] = {"Ask": ["data_out+"]}
E["Clock"] = {"Delay": []}     # 시간만 보낸다. 세상은 안 바뀐다
E["ClothingCare"] = {"SetClothingCareMode": {
    "off": ["running-", "power_draw-"],
    "*":   ["item_clean+", "process+", "power_draw+"]}}
E["CloudServiceProvider"] = {
    "IsAvailable": ["data_out+"], "UploadFile": ["data_out+"], "TextToSpeech": ["data_out+"],
    "SpeechToText": ["data_out+"], "GenerateImage": ["data_out+"], "ExplainImage": ["data_out+"],
    "ChatWithAI": ["data_out+"], "SaveToFile": ["data_out+"], "UploadToCloudStorage": ["data_out+"]}
E["CoffeeMaker"] = {"Brew": ["cooked+", "process+", "power_draw+"],
                    "Stop": ["process-"]}
E["ColorControl"] = {"SetColor": ["color="]}
E["ConveyorBelt"] = {"Start": ["motion_run+", "power_draw+"], "Stop": ["motion_run-", "power_draw-"],
                     "SetBeltSpeed": ["motion_run="]}
E["Dehumidifier"] = {"SetDehumidifierMode": ["humidity-", "power_draw+"],
                     "SetTargetHumidity": ["humidity="]}
E["Dishwasher"] = {"SetDishwasherMode": ["item_clean+", "process+", "power_draw+"]}
E["Display"] = {"PowerOn": ["visual_signal+", "power_draw+"],
                "PowerOff": ["visual_signal-", "power_draw-"],
                "ShowMessage": ["visual_signal+", "message_sent+"],
                "SetBrightness": ["illuminance="]}
E["Door"] = {"Open": ["openness+"], "Close": ["openness-"]}
E["DoorLock"] = {"Lock": ["locked+"], "Unlock": ["locked-"]}
E["Doorbell"] = {"Chime": {"silent": [], "*": ["audio_signal+"]}}
E["ElectricBlanket"] = {
    "SetBlanketMode": {"off": ["running-", "power_draw-"],
                       "*": ["thermal_comfort+", "power_draw+"]},
    "SetTargetTemperature": ["thermal_comfort="]}
E["EmailProvider"] = {"SendMail": ["message_sent+"], "SendMailWithFile": ["message_sent+"]}
E["EmergencyStop"] = {"Trigger": ["halted+", "motion_run-", "process-"], "Reset": ["halted-"]}
E["EvCharger"] = {"StartCharging": ["charge+", "power_draw+"],
                  "StopCharging": ["charge-", "power_draw-"],   # 충전이 멈춘다 = 오르던 것이 멈춤
                  "SetChargeLimit": ["charge="]}
E["FaceRecognizer"] = {"Start": ["process+"], "End": ["process-"],
                       "AddFace": ["enrolled+"], "DeleteFace": ["enrolled-"]}
E["Fan"] = {
    "SetFanMode": {"off": ["running-", "air_motion-", "power_draw-"],
                   "*": ["air_motion+", "thermal_comfort-", "sound~", "power_draw+"]},
    "SetFanSpeed": ["air_motion=", "thermal_comfort-", "sound~"],
    "SetOscillation": ["air_motion~"]}
E["FeedDispenser"] = {"Dispense": ["feed+"]}
E["GarageDoor"] = {"Open": ["openness+"], "Close": ["openness-"], "Stop": ["openness~"]}
E["GlobalVariable"] = {"GetValue": ["data_out+"], "SetValue": ["variable="],
                       "Increment": ["variable+", "count+"], "Reset": ["variable=", "count-"]}
E["GrowLight"] = {"SetSpectrum": ["light_spectrum="],
                  "SetIntensity": ["illuminance=", "power_draw~"]}
E["Humidifier"] = {"SetHumidifierMode": ["humidity+", "power_draw+"],
                   "SetTargetHumidity": ["humidity="]}
E["LaundryDryer"] = {"SetLaundryDryerMode": ["item_clean+", "process+", "power_draw+"],
                     "SetSpinSpeed": ["process="]}
E["LaundryWasher"] = {"SetLaundryWasherMode": ["item_clean+", "process+", "power_draw+"],
                      "SetWaterTemperature": ["water_temperature="],
                      "SetSpinSpeed": ["process="],
                      "Start": ["process+", "item_clean+", "power_draw+"],
                      "Pause": ["process-"], "Stop": ["process-", "power_draw-"]}
E["LevelControl"] = {"MoveToLevel": ["illuminance="]}
E["Light"] = {"MoveToBrightness": ["illuminance="], "MoveToHue": ["color="],
              "MoveToSaturation": ["color="], "MoveToHueAndSaturation": ["color="],
              "MoveToRGB": ["color="], "MoveToXY": ["color="],
              "MoveToColorTemperature": ["color="]}
E["MenuProvider"] = {"GetMenu": ["data_out+"]}
E["MessageSender"] = {"SendSMS": ["message_sent+"], "SendKakaoTalk": ["message_sent+"]}
E["Microwave"] = {"SetCookingParameters": ["cooked+", "process+", "power_draw+"],
                  "AddMoreTime": ["cooked+", "process+"], "Stop": ["process-", "power_draw-"]}
E["Mower"] = {"StartMowing": ["motion_run+", "floor_clean+"], "Pause": ["motion_run-"],
              "Dock": ["motion_run-", "position="]}
E["NewsProvider"] = {"GetNews": ["data_out+"]}
E["NotificationProvider"] = {"SendToast": ["message_sent+"], "SendPush": ["message_sent+"],
                             "SendAlert": ["message_sent+"]}
# SendPush 는 사용자 폰(PersonTracker)이 그 공간에 있어야 간다. 효과는 같아도 쓸 수 있는
# 조건이 다르다 — policy.py 의 NOTIFY_ORDER 가 이 순서를 정한다.
NEEDS = {"NotificationProvider.SendPush": "PersonTracker"}
E["OccupancyCounter"] = {"ResetCount": ["count-"]}
E["Oven"] = {"SetOvenMode": ["cooked+", "temperature+", "process+", "power_draw+"],
             "SetCookingParameters": ["cooked+", "temperature=", "process+"],
             "AddMoreTime": ["cooked+", "process+"]}
E["PetFeeder"] = {"Dispense": ["feed+"]}
E["Printer"] = {"PrintFile": ["data_out+", "process+"], "CancelJobs": ["process-"]}
E["ProductionMachine"] = {"Start": ["process+", "motion_run+", "power_draw+", "count+"],
                          "Stop": ["process-", "motion_run-", "power_draw-"], "ResetCounter": ["count-"]}
E["Projector"] = {"PowerOn": ["visual_signal+", "illuminance+", "power_draw+"],
                  "PowerOff": ["visual_signal-", "illuminance-", "power_draw-"],
                  "SetInputSource": ["media="]}
E["Pump"] = {"SetPumpMode": ["water_flow=", "water_level~", "power_draw~"]}
E["RangeHood"] = {"SetHoodMode": {"off": ["running-", "power_draw-"],
                                  "*": ["air_quality+", "air_motion+", "sound~", "power_draw+"]},
                  "SetLight": ["illuminance~"]}
E["Refrigerator"] = {"SetRefrigeratorTemperature": ["temperature="],
                     "SetFreezerTemperature": ["temperature="],
                     "SetRefrigeratorMode": {"quickCool": ["temperature-", "power_draw+"],
                                             "quickFreeze": ["temperature-", "power_draw+"],
                                             "eco": ["power_draw-"], "vacation": ["power_draw-"],
                                             "*": ["temperature~"]},
                     "SetIceMaker": ["process~"]}
E["RiceCooker"] = {"AddMoreTime": ["cooked+", "process+"],
                   "SetRiceCookerMode": {"cooking": ["cooked+", "process+", "power_draw+"],
                                         "keepWarm": ["temperature+", "power_draw+"],
                                         "reheating": ["temperature+", "power_draw+"],
                                         "autoClean": ["item_clean+", "process+"],
                                         "soakInnerPot": ["process+"]},
                   "SetCookingParameters": ["cooked+", "process+"]}
E["RobotVacuumCleaner"] = {
    "SetRobotVacuumCleanerMode": {"stop": ["motion_run-"], "charge": ["motion_run-", "position=", "charge+"],
                                  "map": ["motion_run+", "data_out+"],
                                  "*": ["floor_clean+", "motion_run+", "sound+"]},
    "GoHome": ["motion_run-", "position=", "charge+"]}
E["Safe"] = {"Lock": ["locked+"], "Unlock": ["locked-"]}
E["Siren"] = {"SetSirenMode": ["audio_signal="], "Activate": ["audio_signal+", "sound+"],
              "Deactivate": ["audio_signal-", "sound-"]}
E["Speaker"] = {"Play": ["media=", "sound+"], "Pause": ["sound-"], "Stop": ["sound-", "media-"],
                "FastForward": ["media~"], "Rewind": ["media~"], "SetVolume": ["sound="],
                "VolumeUp": ["sound+"], "VolumeDown": ["sound-"],
                "Speak": ["audio_signal+", "message_sent+"], "Mute": ["sound-"], "Unmute": ["sound+"]}
E["Sprinkler"] = {"Start": ["water_flow+", "soil_moisture+"], "Stop": ["water_flow-"]}
E["StatusLight"] = {"SetStatus": {"off": ["visual_signal-"], "*": ["visual_signal=", "color="]},
                    "SetBlinking": ["visual_signal~"]}
# Switch 는 전원 스위치다. 무엇에 달려 있느냐에 따라 세상에 주는 효과가 다르다 —
# 조명에 달리면 밝기, 선풍기에 달리면 바람. 그건 서비스가 아니라 기기의 성질이라
# 여기엔 전원 효과만 적고, 같이 달린 카테고리의 효과는 SWITCH_CARRIES 로 붙인다.
E["Switch"] = {"On": ["running+", "power_draw+"], "Off": ["running-", "power_draw-"],
               "Toggle": ["running~", "power_draw~"]}
# Switch 가 붙은 기기에서 Switch.On / Off 가 추가로 내는 효과 (카테고리별)
SWITCH_CARRIES = {
    "Light":          {"On": ["illuminance+"], "Off": ["illuminance-"]},
    "GrowLight":      {"On": ["illuminance+"], "Off": ["illuminance-"]},
    "Fan":            {"On": ["air_motion+", "thermal_comfort-"], "Off": ["air_motion-"]},
    "AirConditioner": {"On": ["thermal_comfort~"], "Off": []},
    "AirPurifier":    {"On": ["air_quality+"], "Off": []},
    "Humidifier":     {"On": ["humidity+"], "Off": []},
    "Dehumidifier":   {"On": ["humidity-"], "Off": []},
    "Ventilator":     {"On": ["air_quality+", "air_motion+"], "Off": ["air_motion-"]},
    "ElectricBlanket": {"On": ["thermal_comfort+"], "Off": []},
    "WaterHeater":    {"On": ["water_temperature+"], "Off": []},
    "CoffeeMaker":    {"On": ["cooked+"], "Off": []},
    "Television":     {"On": ["media+", "visual_signal+"], "Off": ["media-", "visual_signal-"]},
    "Speaker":        {"On": ["sound+"], "Off": ["sound-"]},
    "Projector":      {"On": ["visual_signal+"], "Off": ["visual_signal-"]},
    "Display":        {"On": ["visual_signal+"], "Off": ["visual_signal-"]},
    "Camera":         {"On": ["recording+"], "Off": ["recording-"]},
    "Pump":           {"On": ["water_flow+"], "Off": ["water_flow-"]},
    "Sprinkler":      {"On": ["water_flow+", "soil_moisture+"], "Off": ["water_flow-"]},
    "RangeHood":      {"On": ["air_quality+"], "Off": []},
    "Siren":          {"On": ["audio_signal+"], "Off": ["audio_signal-"]},
    "StatusLight":    {"On": ["visual_signal+"], "Off": ["visual_signal-"]},
    "Plug":           {"On": [], "Off": []},    # 플러그 자체는 전원뿐
}
E["Television"] = {"ChannelUp": ["media~"], "ChannelDown": ["media~"], "SetChannel": ["media="],
                   "SetVolume": ["sound="], "VolumeUp": ["sound+"], "VolumeDown": ["sound-"],
                   "Mute": ["sound-"], "Unmute": ["sound+"]}
E["Thermostat"] = {
    "SetTargetTemperature": ["temperature=", "thermal_comfort="],
    "SetThermostatMode": {"off": ["running-", "power_draw-"],
                          "heat": ["temperature+", "thermal_comfort+", "power_draw+"],
                          "cool": ["temperature-", "thermal_comfort-", "power_draw+"],
                          "dry": ["humidity-", "power_draw+"],
                          "fanOnly": ["air_motion+"],
                          "eco": ["power_draw-", "temperature~"],
                          "away": ["power_draw-", "temperature~"],
                          "auto": ["temperature~", "power_draw+"]},
    "SetTemperatureRange": ["temperature="]}
E["Valve"] = {"Open": ["water_flow+", "openness+"], "Close": ["water_flow-", "openness-"]}
E["Ventilator"] = {"SetVentilatorMode": {"off": ["running-", "air_motion-", "power_draw-"],
                                         "*": ["air_quality+", "air_motion+", "sound~", "power_draw+"]},
                   "SetAirflowRate": ["air_motion=", "air_quality+"]}
E["WaterHeater"] = {"SetTargetTemperature": ["water_temperature="],
                    "SetWaterHeaterMode": {"off": ["running-", "power_draw-"],
                                           "eco": ["water_temperature+", "power_draw-"],
                                           "away": ["power_draw-"], "vacation": ["power_draw-"],
                                           "*": ["water_temperature+", "power_draw+"]}}
E["WaterPurifier"] = {"Dispense": ["water_flow+"], "SetWaterTemperatureMode": ["water_temperature="]}
E["WeatherProvider"] = {"GetWeatherInfo": ["data_out+"]}
E["WeightSensor"] = {"Tare": ["count-"]}
E["WindowCovering"] = {"UpOrOpen": ["openness+", "illuminance+"],
                       "DownOrClose": ["openness-", "illuminance-"],
                       "Stop": ["openness~"], "SetLevel": ["openness=", "illuminance~"],
                       "SetTiltAngle": ["openness~", "illuminance~"]}


def flat(v):
    return sum(v.values(), []) if isinstance(v, dict) else list(v)


def effects_of(cat, method, device_cats=()):
    """한 기기에서 cat.method 를 부르면 나는 효과. Switch 면 같이 달린 카테고리 효과를 얹는다."""
    out = list(flat(E.get(cat, {}).get(method, [])))
    if cat == "Switch":
        for c in device_cats:
            out += SWITCH_CARRIES.get(c, {}).get(method, [])
    return out


def main():
    cat = json.load(open(CATALOG, encoding="utf-8"))
    cats = [k for k in cat if not k.startswith("$")]
    funcs = {(c, m) for c in cats for m, v in cat[c].items() if v["type"] == "function"}
    have = {(c, m) for c in E for m in E[c]}
    bad = []
    for c, m in sorted(funcs - have):
        bad.append(f"효과 없음: {c}.{m}")
    for c, m in sorted(have - funcs):
        bad.append(f"카탈로그에 없음: {c}.{m}")
    for c in E:
        for m, v in E[c].items():
            for e in flat(v):
                q, d = e[:-1], e[-1]
                if d not in "+-=~" or q not in VOCAB:
                    bad.append(f"어휘 밖: {c}.{m} '{e}'")
            if isinstance(v, dict):
                en = cat.get(c, {}).get(m, {}).get("argument_enums") or []
                if en and isinstance(en[0], list):
                    en = en[0]
                names = {str(x).split(" - ")[0] for x in en}
                for k in v:
                    if k != "*" and k not in names:
                        bad.append(f"열거값 아님: {c}.{m}[{k}] (있는 것: {sorted(names)})")
    for c, v in SWITCH_CARRIES.items():
        if c not in cat:
            bad.append(f"SWITCH_CARRIES: {c} 가 카탈로그에 없음")
        for m, es in v.items():
            for e in es:
                if e[:-1] not in VOCAB or e[-1] not in "+-=~":
                    bad.append(f"어휘 밖: SWITCH_CARRIES[{c}][{m}] '{e}'")
    n = len(have)
    print(f"effects.py — 어휘 {len(VOCAB)}개, 함수 서비스 {n}/{len(funcs)}개에 효과")
    print("검산:", *bad, sep="\n  ") if bad else print("검산: 어긋난 것 없음 ✅")
    import collections
    use = collections.Counter(e[:-1] for c in E for v in E[c].values() for e in flat(v))
    use.update(e[:-1] for v in SWITCH_CARRIES.values() for es in v.values() for e in es)
    print("\n어휘별 쓰임:")
    for q, d in VOCAB.items():
        print(f"  {q:18s}{use[q]:4d}  {d}")
    unused = [q for q in VOCAB if not use[q]]
    if unused:
        print("  안 쓰인 어휘:", unused)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
