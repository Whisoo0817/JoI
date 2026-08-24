# -*- coding: utf-8 -*-
"""② top-1 재정렬 규칙 (preference 사전) — 매핑 top-5 안에서 형제 후보를 고를 때 텍스트 단서로 보너스를 준다.
함수(ACT):  발화("…라고 말해/출력") → Speaker.Speak | "모드"·모드어 → *Mode 함수 | 조명 켜/끄 → Switch.On/Off(Switch 가 없는 조명만 밝기)
            | 사이렌 울려 → Siren.SetSirenMode | 카테고리 별칭이 텍스트에 있으면 그 카테고리 +2
값(COND):   "켜져/꺼져 있" 상태 → Switch.Switch | 센서 어휘 사전(초미세>미세, 비/날씨→Weather, 온도→TemperatureSensor …)
형제 후보는 연결된 기기(conn)에 있는 쪽을 먼저 쓴다 — 예: "문이 열리면" 은 Door 가 붙어 있으면 Door.DoorState, 없으면 ContactSensor.Contact.
"""
import re
from .catalog import AL, svc_info
ON = True

# ── 알림 채널 고르기 (허브 설정) ──────────────────────────────────────
_HUB = [None]
def _notify_order():
    """[(서비스, 있어야 하는 기기, 가리키는 말)] — 허브 설정에서 읽는다. 없으면 빈 목록."""
    if _HUB[0] is None:
        import json as _j, os as _o
        f = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "..", "files", "hub_config.json")
        try: cfg = _j.load(open(f, encoding="utf-8"))
        except Exception: cfg = {}
        _HUB[0] = [(x["서비스"], x.get("있어야 하는 기기"), x.get("가리키는 말") or "")
                   for x in cfg.get("알림_순서", [])]
    return _HUB[0]

NOTIFY = {s for s, _, _ in _notify_order()}
NOTIFY_WORD = re.compile("|".join(w for _, _, w in _notify_order() if w) or r"(?!x)x")

def notify_pick(text, conn):
    """알림을 낼 서비스 하나. 채널을 지목한 말이 있으면 그것, 아니면 허브 순서."""
    for svc, _need, words in _notify_order():
        if words and re.search(words, text) and (conn is None or svc.split(".")[0] in conn):
            return svc
    for svc, need, _w in _notify_order():
        if conn is None: return svc
        if svc.split(".")[0] in conn and (need is None or need in conn): return svc
    return None

def pick(conn, *svcs):
    """형제 후보를 앞에서부터 보며 연결된 기기에 있는 첫 서비스를 고른다. 연결 정보가 없으면 맨 앞."""
    if conn:
        for s_ in svcs:
            if s_.split(".")[0] in conn: return s_
        return None
    return svcs[0]

# "알려" 는 여기 없다 — 채널을 가리키는 말이 아니라 그냥 "알려 달라"는 뜻이다.
# 코퍼스로 확인: "알려" 든 405행 중 폰이 있으면 178:16 으로 푸시, 없으면 200:8 로
# 스피커. 곧 허브의 알림_순서 그대로다. 여기서 스피커에 점수를 주면 허브를 이긴다.
SPEECH = re.compile(r"라고|말해|출력해|안내해|방송해|안내(?![가-힣])")
QUOTED = re.compile(r"[\"'“‘].+[\"'”’]")
LIGHT = re.compile(r"조명|전등|램프|라이트|(?<![가-힣])불(?![가-힣])|불을|불도|불만")
BRIGHT_NUM = re.compile(r"\d+\s*(%|퍼센트|으로|로)|밝기|밝게|어둡|색")
MODE = re.compile(r"모드|냉방|난방|송풍|자동|수동|건조|강풍|약풍|터보|절전|취침|긴급|응급|급속|표준|강력|조용|강하게|약하게|세게|가열|보온")
OUTDOOR = re.compile(r"바깥|외부|실외|밖의|밖에|야외")
SENSOR_LEX = [   # (정규식, 서비스…) — 규칙은 앞이 우선(초미세 > 미세), 서비스도 앞이 우선(연결된 기기에 있는 첫 서비스). B8: 바깥/외부는 WeatherProvider, 실내는 AirQualitySensor
    (r"(바깥|외부|실외|밖의|밖에|야외).*초미세", "WeatherProvider.Pm25Weather"), (r"(바깥|외부|실외|밖의|밖에|야외).*미세", "WeatherProvider.Pm10Weather"),
    (r"(바깥|외부|실외|밖의|밖에|야외).*온도", "WeatherProvider.TemperatureWeather"), (r"(바깥|외부|실외|밖의|밖에|야외).*습도", "WeatherProvider.HumidityWeather"),
    (r"초미세", "AirQualitySensor.VeryFineDustLevel"), (r"미세\s*먼지|미세먼지|먼지", "AirQualitySensor.FineDustLevel"),
    (r"이산화탄소|CO2|co2", "CarbonDioxideSensor.CarbonDioxide", "AirQualitySensor.CarbonDioxide"), (r"비가|비 오|비오|비 그|비가 그", "RainSensor.Rain", "WeatherProvider.Weather"),
    (r"눈이|날씨|맑|흐리|폭우|폭설", "WeatherProvider.Weather"),
    (r"(?<!목표 )(?<!설정 )온도", "TemperatureSensor.Temperature"), (r"습도", "HumiditySensor.Humidity"),
    (r"조도|럭스|lux", "LightSensor.Brightness"), (r"움직임|동작|모션|인기척", "MotionSensor.Motion", "PresenceSensor.Presence"),
    (r"사람|재실|아무도|누군가|누가", "PresenceSensor.Presence", "MotionSensor.Motion"), (r"연기", "SmokeDetector.Smoke"),
    (r"스피커.{0,10}(멈|정지|재생|일시)", "Speaker.PlaybackState"), (r"소리|소음|시끄", "SoundSensor.Sound"), (r"누수|물이 새|침수", "LeakSensor.Leakage"),
    (r"(창문|창)(이|가|은|는|도)? ?(하나라도 )?(열|닫)", "WindowCovering.CurrentPosition"),   # B1: 창문=WindowCovering
    (r"금고.{0,12}(열|잠|풀)", "Safe.SafeState", "DoorLock.LockState"),      #     금고=Safe(없으면 도어락)
    (r"(도어락|자물쇠).{0,12}(열|잠|풀)", "DoorLock.LockState"),
    (r"(문|뚜껑|서랍)(이|가|은|는|도)? ?(하나라도 )?(열|닫)", "Door.DoorState", "ContactSensor.Contact"),   #     문=Door(없으면 접촉 센서)
    (r"전압", "Charger.Voltage"), (r"전류", "Charger.Current"),
    (r"전력|소비\s*전력|전력\s*소모|와트", "Charger.Power"), (r"충전", "Charger.ChargingState"),
]
STATE = re.compile(r"(켜|꺼|끄)(져 ?있|진 상태|져만|짐 상태|진 \S+가 (하나라도 )?있)|(작동|가동)(하고 있|중이|되고 있|되어 있)")   # 상태(있으면) → Switch.Switch
EVENT_ON = re.compile(r"(켜|꺼|끄)(지면|질 때|지는|졌|지고)")                                          # 사건(켜지면) → 조명이면 CurrentBrightness

JOSA = r"(을|를|이|가|은|는|도|의|만|과|와|랑|이랑)"
def _alias_in(alias, text):
    """별칭이 텍스트에 나오나. 한 글자 별칭(문·불)은 앞뒤가 다른 한글에 붙어 있지 않을 때만 (창문·눈불 오인 방지)."""
    a = alias.strip()
    if len(a) >= 2: return a in text
    return len(a) == 1 and re.search(r"(?<![가-힣])" + re.escape(a) + JOSA, text) is not None

def named_categories(text, cands):
    """절이 이름을 대고 부른 기기 종류 — 후보들의 카테고리 별칭이 텍스트에 나오는 것."""
    out = set()
    for s_ in cands:
        cat = s_.split(".")[0]
        if cat in ("Switch", "LevelControl"): continue          # 능력 이름이지 기기 이름이 아니다
        if any(_alias_in(a, text) for a in AL.get(cat, [])): out.add(cat)
    return out

def switchable(text, sw):
    """이 절이 부른 기기를 Switch 로 켜고 끌 수 있나.
    sw 가 None 이면 기기 정보가 없다는 뜻이라 막지 않는다. 빈 집합이면 Switch 달린 기기가 하나도 없다는 뜻."""
    if sw is None: return True
    named = {c for c in AL if c not in ("Switch", "LevelControl") and any(_alias_in(a, text) for a in AL[c])}
    return bool(named & sw) if named else bool(sw)

def sets_mode(svc):
    """모드를 정해주는 함수인가 — 이름에 Mode 가 있거나, Mode 라는 골라 쓰는 인자를 받거나.
    (RiceCooker.SetCookingParameters 처럼 이름엔 Mode 가 없어도 모드를 정하는 함수가 있다.)"""
    if "Mode" in svc.split(".", 1)[1]: return True
    spec = svc_info(svc)[1] or {}
    return any(a.get("type") == "ENUM" and "Mode" in a.get("id", "") for a in spec.get("arguments", []))

def func_bonus(text, cands, conn=None, sw=None):
    """→ (bonus dict svc→score, extra 후보 목록). conn: 연결된 기기 카테고리, sw: 그중 Switch 로 켜고 끌 수 있는 종류"""
    if not ON: return {}, []
    b = {}; extra = []
    def add(s, v):
        b[s] = b.get(s, 0) + v
        if s not in cands and s not in extra: extra.append(s)
    if re.search(r"\d+\s*(초|분|시간)\s*(짜리|동안|간)\s*\S*\s*(영상|녹화|촬영)", text): add("Camera.CaptureVideo", 6)   # "5분짜리 영상을 녹화" = 길이 지정 녹화
    if re.search(r"toggle|토글|켜고 끄|켰다 껐다", text, re.I) and pick(conn, "Switch.Toggle") and switchable(text, sw): add("Switch.Toggle", 8)
    if re.search(r"(사진|이미지|그림)\S*\s*(생성|만들)", text): add("CloudServiceProvider.GenerateImage", 8)
    if SPEECH.search(text): add("Speaker.Speak", 8)
    if SPEECH.search(text) or QUOTED.search(text): text = QUOTED.sub("\"…\"", text)      # 인용문 안의 기기·모드어는 무시
    elif QUOTED.search(text) and not re.search(r"재생|틀어|저장|보내|전송|업로드", text): add("Speaker.Speak", 3)
    if re.search(r"재생|틀어", text) and QUOTED.search(text): add("Speaker.Play", 4)
    if LIGHT.search(text) and not BRIGHT_NUM.search(text):      # 사용자 결정: 조명도 켜고 끄는 건 Switch 가 우선, Switch 가 없는 조명만 밝기로
        on_off = pick(conn, "Switch.On", "Light.MoveToBrightness") if switchable(text, sw) else "Light.MoveToBrightness"
        if re.search(r"켜|점등", text): add(on_off or "Light.MoveToBrightness", 4)
        elif re.search(r"꺼|끄|소등", text): add(("Switch.Off" if on_off == "Switch.On" else "Light.MoveToBrightness"), 4)
    if re.search(r"사이렌", text) and re.search(r"울려|울리|작동|켜", text): add("Siren.SetSirenMode", 4)
    if LIGHT.search(text) and re.search(r"색조|채도|Hue|hue", text): add("Light.MoveToHueAndSaturation", 6)          # A10
    elif LIGHT.search(text) and re.search(r"(빨간|파란|초록|노란|보라|주황|분홍|흰|하얀|빨강|파랑|노랑|녹)색?으?로|색(으로|을|깔)", text): add("Light.MoveToColor", 6)
    if re.search(r"저장", text): add("CloudServiceProvider.SaveToFile", 5)                                          # A13
    if re.search(r"업로드|올려\s*줘$", text) and re.search(r"클라우드|파일|사진", text): add("CloudServiceProvider.UploadFile", 5)
    if MODE.search(text):
        for s in cands:
            if sets_mode(s): b[s] = b.get(s, 0) + 4
    if re.search(r"채널", text):
        for s in cands:
            if s.endswith("SetChannel") and re.search(r"\d+\s*번", text): b[s] = b.get(s, 0) + 6
            if s.endswith(("ChannelUp", "ChannelDown")) and re.search(r"하나|한 ?칸|다음|이전|올려|내려", text) and not re.search(r"\d+\s*번", text): b[s] = b.get(s, 0) + 6
    elif not LIGHT.search(text) and not MODE.search(text) and switchable(text, sw):   # A3: 모드어 없는 기기 켜기/끄기 = Switch.On/Off
        if re.search(r"켜|틀어|가동", text) and not re.search(r"꺼|끄", text): add("Switch.On", 4)
        elif re.search(r"꺼|끄", text): add("Switch.Off", 4)
    if re.search(r"\d+\s*(%|퍼센트)", text):                                # A9: 수치(%) 지정은 Set*/MoveTo* (극성어 무시)
        for s in cands:
            if s.split(".")[1].startswith(("Set", "MoveTo")): b[s] = b.get(s, 0) + 4
    # 알림을 어디로 보낼지 — 허브가 정한다 (files/hub_config.json 의 알림_순서).
    # 문장이 채널을 콕 집었으면("화면에 띄워") 그것, 아니면 순서대로 있는 첫 채널.
    # 임베딩만 두면 "보내" 라는 말에 끌려 폰도 없는 공간에서 푸시를 고른다.
    # 이 절이 알림 요청일 때만 — 1등 후보가 이미 알림 계열이면 "무엇을" 은 정해졌고
    # "어디로" 만 남는다. 그때만 채널을 바꾼다. (앞서 후보 안에 알림이 하나라도 있으면
    # 걸리게 했더니 "스피커 볼륨 올려" 같은 절까지 알림으로 끌려갔다.)
    if cands and cands[0] in NOTIFY:
        win = notify_pick(text, conn)
        if win and win != cands[0]: add(win, 6)

    named = named_categories(text, cands + extra)
    can_switch = switchable(text, sw)
    for s in cands + extra:
        cat = s.split(".")[0]
        if cat == "Switch":
            if not can_switch: b[s] = b.get(s, 0) - 4                  # 이 기기는 스위치로 켜고 끌 수 없다
            continue
        if cat == "LevelControl": continue
        if cat in named: b[s] = b.get(s, 0) + 2
        elif named: b[s] = b.get(s, 0) - 2                     # 다른 기기를 이름 대고 불렀다
    return b, extra

def value_bonus(text, cands, conn=None):
    if not ON: return {}, []
    b = {}; extra = []
    def add(s, v):
        b[s] = b.get(s, 0) + v
        if s not in cands and s not in extra: extra.append(s)
    if re.search(r"\d+\s*(초|분|시간)\s*(짜리|동안|간)\s*\S*\s*(영상|녹화|촬영)", text): add("Camera.CaptureVideo", 6)   # "5분짜리 영상을 녹화" = 길이 지정 녹화
    if re.search(r"toggle|토글|켜고 끄|켰다 껐다", text, re.I) and pick(conn, "Switch.Toggle") and switchable(text, sw): add("Switch.Toggle", 8)
    if re.search(r"(사진|이미지|그림)\S*\s*(생성|만들)", text): add("CloudServiceProvider.GenerateImage", 8)
    if STATE.search(text) or EVENT_ON.search(text):                             # B4: 켜짐/꺼짐 상태·사건은 Switch 우선
        add(pick(conn, "Switch.Switch", "Light.CurrentBrightness") or "Switch.Switch", 8)
    else:
        if MODE.search(text):                                                   # "가열 중이면" 같은 모드 이야기는 그 기기의 모드 값
            for s_ in cands:
                if s_.split(".")[1].endswith("Mode"): b[s_] = b.get(s_, 0) + 3
        named = named_categories(text, cands)
        for s_ in cands:
            cat = s_.split(".")[0]
            if cat in ("Switch", "LevelControl"): continue
            if cat in named: b[s_] = b.get(s_, 0) + 2
            elif named: b[s_] = b.get(s_, 0) - 2
        for rx, *sib in SENSOR_LEX:
            if re.search(rx, text):
                s_ = pick(conn, *sib)
                if s_: add(s_, 5)
                break
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
    if svc == "DoorLock.LockState":
        if re.search(r"잠기|잠겨|잠금|잠길|잠갔", text): return ('!= "locked"' if neg else '== "locked"')
        if re.search(r"열|풀|해제", text): return ('!= "unlocked"' if neg else '== "unlocked"')
    if svc in ("Door.DoorState", "Safe.SafeState"):
        if re.search(r"열", text): return ('!= "open"' if neg else '== "open"')
        if re.search(r"닫|잠", text): return ('!= "closed"' if neg else '== "closed"')
    if svc == "PresenceSensor.Presence":
        if re.search(r"부재|아무도|비어|없", text): return "== false"
    if svc.startswith(("Button.", "MultiButton.")):
        m = re.search(r"(두|세|네|다섯|2|3|4|5)\s*(번|회)\s*(눌|클릭|누르)", text)
        if m: return f'== "pushed_{KNUM_X[m.group(1)]}"'
        if re.search(r"길게|꾹|오래", text): return '== "held"'
    if svc == "WeatherProvider.Weather":
        if re.search(r"그치|그칠|그쳤|멈추|안 ?오|오지 않", text): return '!= "rain"'
    if svc == "RainSensor.Rain":
        if re.search(r"그치|그칠|그쳤|멈추|안 ?오|오지 않", text): return "== false"
        if re.search(r"비", text): return "== " + ("false" if neg else "true")
    return None
def unit_scale(svc, text, v):
    """단위 관례: Charger.Voltage는 mV, Current는 A 그대로"""
    if not ON: return v
    if svc == "Charger.Voltage" and re.search(r"\d+\s*(V|v|볼트)", text): return v * 1000
    return v
