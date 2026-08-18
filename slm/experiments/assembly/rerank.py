# -*- coding: utf-8 -*-
"""② top-1 재정렬 규칙 (preference 사전) — 매핑 top-5 안에서 형제 후보를 고를 때 텍스트 단서로 보너스를 준다.
함수(ACT):  발화("…라고 말해/출력") → Speaker.Speak | "모드"·모드어 → *Mode 함수 | 조명 켜→Light.MoveToBrightness, 끄→Switch.Off
            | 사이렌 울려 → Siren.SetSirenMode | 카테고리 별칭이 텍스트에 있으면 그 카테고리 +2
값(COND):   "켜져/꺼져 있" 상태 → Switch.Switch (강제) | 센서 어휘 사전(초미세>미세, 비/날씨→Weather, 온도→TemperatureSensor …)
환경 RERANK=0 이면 전부 비활성."""
import os, re, json
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
AL = json.load(open(os.path.join(ROOT, "mapping_v2", "category_aliases.json")))["aliases"]
ON = os.environ.get("RERANK", "1") == "1"

SPEECH = re.compile(r"라고|말해|알려|출력해|안내해|방송해|안내(?![가-힣])")
QUOTED = re.compile(r"[\"'“‘].+[\"'”’]")
LIGHT = re.compile(r"조명|전등|램프|라이트|(?<![가-힣])불(?![가-힣])|불을|불도|불만")
BRIGHT_NUM = re.compile(r"\d+\s*(%|퍼센트|으로|로)|밝기|밝게|어둡|색")
MODE = re.compile(r"모드|냉방|난방|송풍|자동|수동|건조|강풍|약풍|터보|절전|취침|긴급|응급|급속|표준|강력|조용|강하게|약하게|세게")
OUTDOOR = re.compile(r"바깥|외부|실외|밖의|밖에|야외")
SENSOR_LEX = [   # (정규식, 서비스) — 앞이 우선(초미세 > 미세). B8: 바깥/외부는 WeatherProvider, 실내는 AirQualitySensor
    (r"(바깥|외부|실외|밖의|밖에|야외).*초미세", "WeatherProvider.Pm25Weather"), (r"(바깥|외부|실외|밖의|밖에|야외).*미세", "WeatherProvider.Pm10Weather"),
    (r"(바깥|외부|실외|밖의|밖에|야외).*온도", "WeatherProvider.TemperatureWeather"), (r"(바깥|외부|실외|밖의|밖에|야외).*습도", "WeatherProvider.HumidityWeather"),
    (r"초미세", "AirQualitySensor.VeryFineDustLevel"), (r"미세\s*먼지|미세먼지|먼지", "AirQualitySensor.FineDustLevel"),
    (r"이산화탄소|CO2|co2", "AirQualitySensor.CarbonDioxide"), (r"비가|비 오|비오|눈이|날씨|맑|흐리|폭우|폭설", "WeatherProvider.Weather"),
    (r"(?<!목표 )(?<!설정 )온도", "TemperatureSensor.Temperature"), (r"습도", "HumiditySensor.Humidity"),
    (r"조도|럭스|lux", "LightSensor.Brightness"), (r"움직임|동작|모션|인기척", "MotionSensor.Motion"),
    (r"사람|재실|아무도|누군가|누가", "PresenceSensor.Presence"), (r"연기", "SmokeDetector.Smoke"),
    (r"소리|소음|시끄", "SoundSensor.Sound"), (r"누수|물이 새|침수", "LeakSensor.Leakage"),
    (r"(창문|창)(이|가|은|는|도)? ?(하나라도 )?(열|닫)", "WindowCovering.CurrentPosition"),   # B1: 창문=WindowCovering
    (r"(금고|도어락|자물쇠)(이|가|은|는|도)? ?(하나라도 |모두 )?(열|잠|풀)", "DoorLock.DoorLockState"),   #     금고·도어락=DoorLock
    (r"(문|뚜껑|서랍)(이|가|은|는|도)? ?(하나라도 )?(열|닫)", "ContactSensor.Contact"),                #     문=ContactSensor (r"전압", "Charger.Voltage"), (r"전류", "Charger.Current"), (r"충전", "Charger.ChargingState"),
]
STATE = re.compile(r"(켜|꺼|끄)(져 ?있|진 상태|져만|짐 상태|진 \S+가 (하나라도 )?있)|(작동|가동)(하고 있|중이|되고 있|되어 있)")   # 상태(있으면) → Switch.Switch
EVENT_ON = re.compile(r"(켜|꺼|끄)(지면|질 때|지는|졌|지고)")                                          # 사건(켜지면) → 조명이면 CurrentBrightness

def func_bonus(text, cands):
    """→ (bonus dict svc→score, extra 후보 목록)"""
    if not ON: return {}, []
    b = {}; extra = []
    def add(s, v):
        b[s] = b.get(s, 0) + v
        if s not in cands and s not in extra: extra.append(s)
    if re.search(r"\d+\s*(초|분|시간)\s*(짜리|동안|간)\s*\S*\s*(영상|녹화|촬영)", text): add("Camera.CaptureVideo", 6)   # "5분짜리 영상을 녹화" = 길이 지정 녹화
    if re.search(r"toggle|토글|켜고 끄|켰다 껐다", text, re.I): add("Switch.Toggle", 8)
    if re.search(r"(사진|이미지|그림)\S*\s*(생성|만들)", text): add("CloudServiceProvider.GenerateImage", 8)
    if SPEECH.search(text): add("Speaker.Speak", 8)
    if SPEECH.search(text) or QUOTED.search(text): text = QUOTED.sub("\"…\"", text)      # 인용문 안의 기기·모드어는 무시
    elif QUOTED.search(text) and not re.search(r"재생|틀어|저장|보내|전송|업로드", text): add("Speaker.Speak", 3)
    if re.search(r"재생|틀어", text) and QUOTED.search(text): add("Speaker.Play", 4)
    if LIGHT.search(text) and not BRIGHT_NUM.search(text):
        if re.search(r"켜|점등", text): add("Light.MoveToBrightness", 4)
        elif re.search(r"꺼|끄|소등", text): add("Switch.Off", 4)
    if re.search(r"사이렌", text) and re.search(r"울려|울리|작동|켜", text): add("Siren.SetSirenMode", 4)
    if LIGHT.search(text) and re.search(r"색조|채도|Hue|hue", text): add("Light.MoveToHueAndSaturation", 6)          # A10
    elif LIGHT.search(text) and re.search(r"(빨간|파란|초록|노란|보라|주황|분홍|흰|하얀|빨강|파랑|노랑|녹)색?으?로|색(으로|을|깔)", text): add("Light.MoveToColor", 6)
    if re.search(r"저장", text): add("CloudServiceProvider.SaveToFile", 5)                                          # A13
    if re.search(r"업로드|올려\s*줘$", text) and re.search(r"클라우드|파일|사진", text): add("CloudServiceProvider.UploadFile", 5)
    if MODE.search(text):
        for s in cands:
            if "Mode" in s.split(".")[1]: b[s] = b.get(s, 0) + 4
    if re.search(r"채널", text):
        for s in cands:
            if s.endswith("SetChannel") and re.search(r"\d+\s*번", text): b[s] = b.get(s, 0) + 6
            if s.endswith(("ChannelUp", "ChannelDown")) and re.search(r"하나|한 ?칸|다음|이전|올려|내려", text) and not re.search(r"\d+\s*번", text): b[s] = b.get(s, 0) + 6
    elif not LIGHT.search(text) and not MODE.search(text):                   # A3: 모드어 없는 기기 켜기/끄기 = Switch.On/Off
        if re.search(r"켜|틀어|가동", text) and not re.search(r"꺼|끄", text): add("Switch.On", 4)
        elif re.search(r"꺼|끄", text): add("Switch.Off", 4)
    if re.search(r"\d+\s*(%|퍼센트)", text):                                # A9: 수치(%) 지정은 Set*/MoveTo* (극성어 무시)
        for s in cands:
            if s.split(".")[1].startswith(("Set", "MoveTo")): b[s] = b.get(s, 0) + 4
    for s in cands:
        cat = s.split(".")[0]
        if cat in ("Switch", "Speaker", "LevelControl"): continue
        if any(len(a) >= 2 and a in text for a in AL.get(cat, [])): b[s] = b.get(s, 0) + 2
    return b, extra

def value_bonus(text, cands):
    if not ON: return {}, []
    b = {}; extra = []
    def add(s, v):
        b[s] = b.get(s, 0) + v
        if s not in cands and s not in extra: extra.append(s)
    if re.search(r"\d+\s*(초|분|시간)\s*(짜리|동안|간)\s*\S*\s*(영상|녹화|촬영)", text): add("Camera.CaptureVideo", 6)   # "5분짜리 영상을 녹화" = 길이 지정 녹화
    if re.search(r"toggle|토글|켜고 끄|켰다 껐다", text, re.I): add("Switch.Toggle", 8)
    if re.search(r"(사진|이미지|그림)\S*\s*(생성|만들)", text): add("CloudServiceProvider.GenerateImage", 8)
    if STATE.search(text) or EVENT_ON.search(text): add("Switch.Switch", 8)     # B4: 켜짐/꺼짐 상태·사건은 Switch 우선
    else:
        for rx, s in SENSOR_LEX:
            if re.search(rx, text): add(s, 5); break
    return b, extra

# ── 값 표현 관례(gold 관례 사전): 서비스별 상태어 → 연산자·값 ──
NEG = r"(않으면|않고|않은|않는|없으면|없고|없는|아니면|안 ?되|지 않)"
KNUM_X = {"두": "2x", "세": "3x", "네": "4x", "다섯": "5x", "2": "2x", "3": "3x", "4": "4x", "5": "5x"}
def value_conv(svc, text):
    """→ 'op value' 문자열 또는 None (기본 규칙에 맡김)."""
    if not ON: return None
    neg = re.search(NEG, text) is not None
    def tf(v): return ("false" if v else "true") if neg else ("true" if v else "false")
    if svc == "ContactSensor.Contact":
        if re.search(r"열", text): return "== " + tf(False)
        if re.search(r"닫", text): return "== " + tf(True)
    if svc == "Switch.Switch":
        if re.search(r"꺼|끄", text): return "== " + tf(False)
        if re.search(r"켜|작동|가동", text): return "== " + tf(True)
    if svc == "WindowCovering.CurrentPosition":
        if re.search(r"열", text): return "== 0" if neg else "> 0"
        if re.search(r"닫", text): return "> 0" if neg else "== 0"
    if svc == "Light.CurrentBrightness":
        if re.search(r"켜", text): return "== 0" if neg else "> 0"
        if re.search(r"꺼|끄", text): return "> 0" if neg else "== 0"
    if svc == "DoorLock.DoorLockState":
        if re.search(r"잠기|잠겨|잠금|잠길|잠갔", text): return ('!= "closed"' if neg else '== "closed"')
        if re.search(r"열|풀|해제", text): return ('!= "open"' if neg else '== "open"')
    if svc == "PresenceSensor.Presence":
        if re.search(r"부재|아무도|비어|없", text): return "== false"
    if svc.startswith(("Button.", "MultiButton.")):
        m = re.search(r"(두|세|네|다섯|2|3|4|5)\s*(번|회)\s*(눌|클릭|누르)", text)
        if m: return f'== "pushed_{KNUM_X[m.group(1)]}"'
        if re.search(r"길게|꾹|오래", text): return '== "held"'
    if svc == "WeatherProvider.Weather":
        if re.search(r"그치|그칠|그쳤|멈추|안 ?오|오지 않", text): return '!= "rain"'
    return None
def unit_scale(svc, text, v):
    """단위 관례: Charger.Voltage는 mV, Current는 A 그대로"""
    if not ON: return v
    if svc == "Charger.Voltage" and re.search(r"\d+\s*(V|v|볼트)", text): return v * 1000
    return v
