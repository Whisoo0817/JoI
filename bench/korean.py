#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""한국어판 문장 — 영어 틀과 같은 열쇠로 한국어 틀을 둔다.

번역이 아니다. `build_dataset.py` 가 영어 문장을 만들 때 **어떤 틀에 무엇을 끼웠는지**
알고 있으므로, 같은 자리에 한국어 틀을 끼워 한국어 문장을 따로 만든다.
영어 문장을 다시 읽어서 옮기면 틀린다 — 관사·복수가 이미 녹아 있기 때문이다.

한국어에서 깨지는 것 (build_korean.py 가 세어 보고한다)
  단수/복수    "the light"(하나) vs "the lights"(전부) 가 한국어에선 둘 다 "조명".
               ref=onedup(단수로 불러 되묻기 유발) 이 표시로는 안 드러난다.
  관사         "the camera" 의 '특정' 느낌이 없다.
  말투 6종     polite 와 could 가 한국어에선 둘 다 "-해 주세요" 로 뭉갠다.
  어순         시간절이 한국어에선 늘 앞. 영어의 앞/뒤 다양성이 사라진다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import templates as T

_LOGIC_SPLIT = re.compile(
    r"(\{(?:a_c|a|cond_while|cond_until|cond_q|cond_only|cond_when|cond)\})")

# ── 기기 이름 ──────────────────────────────────────────────────────────
NOUN_KO = {
    "Light": "조명", "Switch": "스위치", "Plug": "플러그", "Fan": "선풍기",
    "AirConditioner": "에어컨", "Thermostat": "온도조절기", "Heater": "난방기",
    "AirPurifier": "공기청정기", "Humidifier": "가습기", "Dehumidifier": "제습기",
    "WindowCovering": "블라인드", "DoorLock": "도어락", "GarageDoor": "차고문",
    "Television": "TV", "Speaker": "스피커", "Camera": "카메라", "Siren": "사이렌",
    "RobotVacuumCleaner": "로봇청소기", "Mower": "잔디깎이", "CoffeeMaker": "커피포트",
    "WaterHeater": "온수기", "Sprinkler": "스프링클러", "GrowLight": "생장등",
    "Ventilator": "환풍기", "FeedDispenser": "급이기", "Pump": "펌프",
    "Valve": "밸브", "Chamber": "챔버", "ConveyorBelt": "컨베이어",
    "AirCompressor": "공기압축기", "StatusLight": "상태등", "ArmRobot": "로봇팔",
    "MotionSensor": "동작 감지 센서", "PresenceSensor": "재실 센서",
    "ContactSensor": "문열림 센서", "SmokeDetector": "연기 감지기",
    "LeakSensor": "누수 센서", "GasSensor": "가스 센서",
    "VibrationSensor": "진동 센서", "TiltSensor": "기울기 센서",
    "ProximitySensor": "근접 센서", "WindSensor": "풍속계",
    "PowerMeter": "전력계", "Button": "버튼", "MultiButton": "씬 버튼",
    "ProductionMachine": "설비", "Projector": "프로젝터", "Display": "디스플레이",
    "Dishwasher": "식기세척기", "LaundryWasher": "세탁기",
    "LaundryDryer": "건조기", "Oven": "오븐", "Microwave": "전자레인지",
    "Refrigerator": "냉장고", "ElectricBlanket": "전기장판",
    "Doorbell": "초인종", "Door": "문",
    "EvCharger": "EV 충전기", "PetFeeder": "반려동물 급식기", "RangeHood": "레인지후드",
    "WaterPurifier": "정수기", "ClothingCare": "의류관리기",
    "AudioRecorder": "녹음기", "Printer": "프린터", "Safe": "금고",
    "RiceCooker": "밥솥", "SafetyBarrier": "안전 barrier",
    "EmergencyStop": "비상정지 버튼", "Charger": "충전기",
    "TemperatureSensor": "온도계", "HumiditySensor": "습도계",
    "AirQualitySensor": "공기질 센서", "SoilMoistureSensor": "토양 센서",
    "WaterLevelSensor": "수위 센서", "FlowSensor": "유량계",
    "WaterQualitySensor": "수질 센서", "WeightSensor": "저울",
    "OccupancyCounter": "인원 계수기", "SoundSensor": "소음 센서",
    "LightSensor": "조도 센서", "PressureSensor": "압력계",
    "RainSensor": "감우 센서", "UvSensor": "자외선 센서", "Battery": "배터리",
    "EnergyMeter": "전력량계", "CarbonDioxideSensor": "CO2 센서",
    "CarbonMonoxideSensor": "일산화탄소 센서", "RfidReader": "출입 카드 리더기",
    "FaceRecognizer": "얼굴 인식기", "RotaryControl": "다이얼", "LevelControl": "다이얼",
    "ColorControl": "색 조절기",
}

# ── 장소 ───────────────────────────────────────────────────────────────
PLACE_KO = {
    "LivingRoom": "거실", "Bedroom": "침실", "Kitchen": "주방", "Bathroom": "욕실",
    "Study": "서재", "Hallway": "복도", "Entrance": "현관", "BackDoor": "뒷문",
    "Garage": "차고", "Garden": "마당", "Outdoor": "실외", "Utility": "다용도실",
    "Balcony": "발코니", "BabyRoom": "아기방", "Pantry": "팬트리", "Storage": "창고",
    "Stairs": "계단", "RestRoom": "화장실", "Room": "방", "RoomA": "A방",
    "RoomB": "B방", "RoomC": "C방", "OpenSpace": "사무실", "MeetingRoom": "회의실",
    "LabRoom": "실험실", "TestBed": "테스트베드", "ColdRoom": "저온실",
    "ProcessRoom": "공정실", "MachineShop": "기계실", "Line": "생산라인",
    "Warehouse": "창고", "Dock": "하역장", "BoilerRoom": "보일러실",
    "PumpRoom": "펌프실", "TankYard": "탱크야드", "ColdStorage": "냉장창고",
    "Greenhouse": "온실", "GrowRoom": "재배실", "Barn": "축사", "Field": "밭",
}

# ── 색·씬 ──────────────────────────────────────────────────────────────
# 한국 조명 용어를 따른다 — warm white 는 '전구색', daylight white 는 '주광색'.
COLOR_KO = {"red": "빨간색", "blue": "파란색", "green": "초록색",
            "warm white": "전구색", "orange": "주황색", "purple": "보라색",
            "pink": "분홍색", "daylight white": "주광색", "amber": "호박색"}
SCENE_KO = {"movie": "영화", "party": "파티", "relax": "휴식", "reading": "독서",
            "night": "취침", "morning": "아침", "focus": "집중",
            "dinner": "저녁 식사", "away": "외출"}
WEEKDAY_KO = {"Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일",
              "Thursday": "목요일", "Friday": "금요일", "Saturday": "토요일",
              "Sunday": "일요일",
              # 영어 틀의 {weekday} 에는 "weekends" 도 들어온다
              "weekends": "주말"}


def time_ko(s):
    """'7:30 am' → '오전 7시 30분'. '11 pm' → '밤 11시'."""
    s = str(s).strip().lower()
    if s == "midnight":
        return "자정"
    if s == "noon":
        return "정오"
    ampm = "am" if s.endswith("am") else "pm" if s.endswith("pm") else ""
    s = s.replace("am", "").replace("pm", "").strip()
    h, _, m = s.partition(":")
    try:
        h = int(h)
    except ValueError:
        return s
    head = {"am": "오전", "pm": "오후"}.get(ampm, "")
    if ampm == "pm" and h >= 9:
        head = "밤"
    if ampm == "am" and h <= 5:
        head = "새벽"
    out = f"{head} {h}시" if head else f"{h}시"
    if m and int(m):
        out += f" {int(m)}분"
    return out



# ── 조사 ───────────────────────────────────────────────────────────────
# 한국어는 앞 글자에 받침이 있느냐로 조사가 갈린다. 영어 틀에는 없던 일이다.
# 틀에는 표시만 두고("{dev}%O") 여기서 고른다.
#   %O 을/를 · %S 이/가 · %T 은/는 · %L 으로/로 · %W 과/와
_JONG_LATIN = {          # 로마자로 끝나는 이름 — 읽었을 때 받침이 있나
    "l": True, "m": True, "n": True, "ng": True, "b": True, "p": True,
    "k": True, "g": True, "t": True, "d": True, "s": True, "c": True,
    "x": True, "z": True, "r": True,
}


def has_batchim(word):
    """마지막 글자에 받침이 있나. ㄹ 받침은 따로 알려 준다 → (있나, ㄹ인가)."""
    w = (word or "").rstrip(")]\u3011 ").rstrip()
    if not w:
        return False, False
    ch = w[-1]
    if "가" <= ch <= "힣":
        code = (ord(ch) - 0xAC00) % 28
        return code != 0, code == 8
    if ch.isdigit():                      # 숫자는 읽는 소리로 — 1,3,6,7,8,0 이 받침
        return ch in "1360378", ch in "18"
    low = ch.lower()
    if low.isalpha():
        return _JONG_LATIN.get(low, False), low == "l"
    return False, False


_JOSA = {"%O": ("을", "를"), "%S": ("이", "가"), "%T": ("은", "는"),
         "%W": ("과", "와")}


def josa(text):
    """치환이 끝난 문장에서 조사 표시를 실제 조사로 바꾼다."""
    for mark, (yes, no) in _JOSA.items():
        while mark in text:
            i = text.index(mark)
            b, _ = has_batchim(text[:i])
            text = text[:i] + (yes if b else no) + text[i + len(mark):]
    while "%L" in text:                   # 으로/로 — ㄹ 받침은 '로' 를 쓴다
        i = text.index("%L")
        b, is_l = has_batchim(text[:i])
        text = text[:i] + ("로" if (not b or is_l) else "으로") + text[i + 2:]
    return text


# ── 기기 지목 ──────────────────────────────────────────────────────────
_SECTION = re.compile(r"^(Section|Zone|Area)[_ ]?(\d+|[A-Z])$")


def place_ko(tag):
    """장소 태그를 한국어로. LAB01 처럼 'Section5' 꼴이면 '5구역' 으로 읽는다."""
    if not tag:
        return "방"
    if tag in PLACE_KO:
        return PLACE_KO[tag]
    m = _SECTION.match(tag)
    if m:
        # 기기 별명이 "구역 5 조명" 꼴이므로 장소도 같은 차례로 읽는다
        return f"구역 {m.group(2)}"
    return tag


def refer_ko(style, cat, place_tag=None, nick_ko=None, plural=False):
    """영어 refer() 가 고른 방식 그대로 한국어 지목구를 만든다.

    ★ 한국어에는 수가 없다. 영어는 "the lights"(복수=전부, 실행) 와
      "the light"(단수=어느 것?, 되묻기) 로 판정이 갈리는데 한국어로는 둘 다
      "조명" 이다. 복수 쪽에만 "다" 를 붙여 그 구분을 살린다 —
      한국어에서도 "조명 다 켜 줘" 와 "조명 켜 줘" 는 다른 말이다.
    """
    n = NOUN_KO.get(cat, cat)
    if style == "nick" and nick_ko:
        return nick_ko
    if style == "place" and place_tag:
        pl = place_ko(place_tag)
        return n if pl in n else f"{pl} {n}"
    if style == "all":
        # "전부" 를 뒤에 붙이면 조사가 안 붙는다 — "스피커 전부로 방송해"(x).
        # 앞에 두면 어떤 조사와도 맞는다 — "모든 스피커로 방송해"(o).
        return f"모든 {n}"
    if style == "any":
        return f"{n} 아무거나 하나"
    if style == "plain" and plural:
        return f"{n} 전부"
    return n            # 단수로 부른 자리 — 어느 것인지 되물어야 한다


# ── 동작절 ─────────────────────────────────────────────────────────────
# 영어 틀 문자열 그대로가 열쇠다. {dev} {n} {place} … 슬롯 이름도 같다.
ACT_KO = {
    "turn on {dev}": "{dev} 켜", "switch {dev} on": "{dev} 켜",
    "put {dev} on": "{dev} 켜", "get {dev} on": "{dev} 켜",
    "light up {dev}": "{dev} 켜",
    "turn off {dev}": "{dev} 꺼", "switch {dev} off": "{dev} 꺼",
    "shut {dev} off": "{dev} 꺼", "kill {dev}": "{dev} 꺼",
    "turn {dev} off": "{dev} 꺼", "toggle {dev}": "{dev} 껐다 켜",
    "cut power to {dev}": "{dev} 전원 차단해",
    "dim {dev} to {lo} percent": "{dev} 밝기%O {lo}퍼센트로 낮춰",
    "set {dev} brightness to {n} percent": "{dev} 밝기%O {n}퍼센트%L 맞춰",
    "bring {dev} down to {lo} percent": "{dev} 밝기%O {lo}퍼센트까지 낮춰",
    "turn {dev} up to {hi} percent": "{dev} 밝기%O {hi}퍼센트까지 올려",
    "set {dev} to {color}": "{dev} {color}%L 바꿔",
    "make {dev} {color}": "{dev} {color}%L 해",
    "change {dev} to {color}": "{dev} {color}%L 바꿔",
    "turn {dev} {color}": "{dev} {color}%L 켜",
    # 기기를 안 대는 두 틀도 "조명" 은 밝힌다 — "영화 모드로 해" 로는 무엇을
    # 바꾸라는 말인지 알 수 없다 (whisoo). 어느 조명인지는 여전히 안 댄다.
    "set the lights to the {scene} scene": "조명 {scene} 모드로 해",
    "switch {dev} to the {scene} scene": "{dev} {scene} 모드로 바꿔",
    "put {dev} into {scene} mode": "{dev} {scene} 모드로 해",
    "run the {scene} scene on the lights": "조명 {scene} 모드 실행해",
    "set {dev} to {n} degrees": "{dev} {n}도로 맞춰",
    "put {dev} on {n} degrees": "{dev} {n}도로 해",
    "turn the heating up to {n}": "난방 {n}도로 올려",
    "turn the heating off": "난방 꺼",
    "put {dev} on cool": "{dev} 냉방으로 해",
    "run {dev} for {n} minutes": "{dev}%O {n}분 동안 돌려",
    "run {dev} for {n} hours": "{dev}%O {n}시간 동안 켜 놔",
    "set {dev} to high": "{dev} 세게 틀어",
    "put {dev} on auto": "{dev} 자동 모드로 해",
    "run {dev} on turbo": "{dev} 터보로 돌려",
    "set {dev} to {n} percent": "{dev} {n}퍼센트로 맞춰",
    "close {dev}": "{dev} 닫아", "open {dev}": "{dev} 열어",
    "lower {dev} to {n} percent": "{dev} {n}퍼센트까지 내려",
    "pull {dev} shut": "{dev} 닫아", "raise {dev}": "{dev} 올려",
    "lock {dev}": "{dev} 잠가", "unlock {dev}": "{dev} 열어",
    "make sure {dev} is locked": "{dev} 잠겼는지 봐 줘",
    "shut {dev}": "{dev} 닫아",
    "pause {dev}": "{dev} 일시정지해",
    "play some music on {dev}": "{dev}%L 음악 좀 틀어",
    "set the volume on {dev} to {n}": "{dev} 볼륨 {n}%L 맞춰",
    "announce it on {dev}": "{dev}%L 알려",
    "say it out loud on {dev}": "{dev}%L 소리 내서 알려",
    "play a chime on {dev}": "{dev}%L 알림음 울려",
    "start recording on {dev}": "{dev} 녹화 시작해",
    "stop recording on {dev}": "{dev} 녹화 멈춰",
    "take a snapshot with {dev}": "{dev}%L 사진 찍어",
    "set off {dev}": "{dev} 울려", "sound {dev}": "{dev} 울려",
    "start {dev}": "{dev} 켜", "stop {dev}": "{dev} 멈춰",
    "send {dev} back to its dock": "{dev} 충전대로 보내",
    "send {dev} back to the dock": "{dev} 충전대로 보내",
    "run {dev} in the {place}": "{dev}%L {place} 청소해",
    "park {dev}": "{dev} 정위치로 보내",
    "brew a cup on {dev}": "{dev}%L 한 잔 내려",
    "send me a notification": "알림 보내 줘", "let me know": "알려 줘",
    "push me an alert": "알림 띄워 줘", "tell me about it": "알려 줘",
    "give me a heads-up": "꼭 알려 줘", "warn me": "경고해 줘",
    "send a warning to my phone": "폰으로 경고 보내 줘",
    "text my phone": "폰으로 문자 보내 줘", "ping my phone": "폰으로 알림 보내 줘",
    "say it out loud on the speaker": "스피커로 소리 내서 알려 줘",
    "announce it": "방송해 줘", "read it out": "소리 내서 읽어 줘",
    "show it on the screen": "화면에 띄워 줘",
    "pop it up on the display": "디스플레이에 띄워 줘",
    "tell me the temperature in the {place}": "{place} 온도 알려 줘",
    "what is {dev} doing": "{dev} 지금 뭐 하고 있어",
    "check whether {dev} is on": "{dev} 켜져 있는지 확인해 줘",
    "read out the humidity": "습도 읽어 줘",
    "how much power is {dev} using": "{dev} 전력 얼마나 쓰고 있어",
    "set a {n} minute timer": "{n}분 타이머 맞춰 줘",
    "start a countdown for {n} minutes": "{n}분 카운트다운 시작해 줘",
    "cancel the timer": "타이머 취소해 줘",
    "dispense feed with {dev}": "{dev}%L 사료 줘",
    "skip the next feeding": "다음 급여 건너뛰어",
    "run {dev}": "{dev} 돌려",
    "shut {dev} right away": "{dev} 당장 닫아",
    "slow {dev} down": "{dev} 속도 줄여",
    "turn {dev} green": "{dev} 초록색으로 바꿔",
    "turn {dev} red": "{dev} 빨간색으로 바꿔",
    "switch {dev} to amber": "{dev} 노란색으로 바꿔",
    # 즉시 실행 전용 문형 (build_dataset.NOW_OVERRIDE)
    'let me know if {dev} is still on': '{dev} 아직 켜져 있으면 알려 줘',
    'send me the {place} temperature': '{place} 온도 보내 줘',
    'ping me when {dev} finishes': '{dev} 끝나면 알려 줘',
    'remind me to check {dev}': '{dev} 확인하라고 알려 줘',
    'text me the humidity in the {place}': '{place} 습도 문자로 보내 줘',
    'let me know whether anyone is in the {place}': '{place}에 사람 있는지 알려 줘',
    'send me a note if {dev} stays on': '{dev} 계속 켜져 있으면 알려 줘',
    'what is the temperature in the {place}': '{place} 온도 몇 도야',
    'is {dev} on right now': '{dev} 지금 켜져 있어',
    'how humid is the {place}': '{place} 습도 얼마야',
    'tell me if {dev} is open': '{dev} 열려 있는지 알려 줘',
    'how much power is {dev} pulling': '{dev} 전력 얼마나 쓰고 있어',
    'what is {dev} set to': '{dev} 몇으로 맞춰져 있어',
    'is anyone in the {place}': '{place}에 사람 있어',
}

# ── 묻는 문장 ──────────────────────────────────────────────────────────
# 홀로 쓰면 물음이다 ("주방 온도 몇 도야?"). 그런데 앞에 시간절·조건절이 붙으면
# 한국어에서는 물음이 안 된다 ("문이 열리면 주방 온도 몇 도야?" — 말이 안 된다).
# 그럴 때 쓰는 '안긴 꼴' 을 따로 둔다.
ASK_KO = {
    'what is the temperature in the {place}', 'is {dev} on right now',
    'how humid is the {place}', 'how much power is {dev} pulling',
    'what is {dev} set to', 'is anyone in the {place}',
}
QUERY_EMBED_KO = {
    'what is the temperature in the {place}': '{place} 온도 알려 줘',
    'is {dev} on right now': '{dev} 켜져 있는지 알려 줘',
    'how humid is the {place}': '{place} 습도 알려 줘',
    'how much power is {dev} pulling': '{dev} 전력 얼마나 쓰는지 알려 줘',
    'what is {dev} set to': '{dev} 몇으로 맞춰져 있는지 알려 줘',
    'is anyone in the {place}': '{place}에 사람 있는지 알려 줘',
}

# ── 기기를 안 대는 문장 ────────────────────────────────────────────────
VAGUE_KO = {
    "it is too hot in here": "여기 너무 더워", "I am sweating": "땀 나",
    "this room is stuffy and hot": "방이 답답하고 더워",
    "cool this place down": "여기 좀 시원하게 해 줘",
    "make it less warm": "덜 덥게 해 줘", "bring the temperature down": "온도 좀 낮춰 줘",
    "it feels stuffy": "답답해", "there is no air in here": "여기 공기가 안 통해",
    "the air is not moving": "바람이 하나도 없어",
    "get some air moving": "바람 좀 통하게 해 줘", "make it breezy": "시원한 바람 좀 줘",
    "I am cold": "추워", "it is freezing in here": "여기 얼어 죽겠어",
    "it is chilly": "쌀쌀해", "warm this room up": "이 방 좀 따뜻하게 해 줘",
    "make it cozy": "포근하게 해 줘", "take the chill off": "한기 좀 없애 줘",
    "the glare is bad": "눈부심이 심해", "the sun is in my eyes": "햇빛이 눈에 들어와",
    "block the sun": "햇빛 좀 막아 줘", "give me some privacy": "안 보이게 가려 줘",
    "shut out the light from outside": "바깥 빛 좀 차단해 줘",
    "it is too dark in here": "여기 너무 어두워",
    "I cannot see anything": "아무것도 안 보여", "this room is gloomy": "방이 침침해",
    "brighten this place up": "여기 좀 밝게 해 줘",
    "give me some light to read by": "책 읽을 만큼 불 좀 줘",
    "it is too bright": "너무 밝아", "I am going to sleep": "이제 잘 거야",
    "kill the lights in here": "여기 불 다 꺼 줘", "make it dark": "어둡게 해 줘",
    "this is harsh on the eyes": "눈이 부셔",
    "make it dimmer": "좀 더 어둡게 해 줘", "tone it down a bit": "좀 낮춰 줘",
    "set the mood softer": "분위기 좀 부드럽게 해 줘",
    "this white light is harsh": "이 흰 불빛이 눈부셔",
    "give this room some color": "방에 색 좀 넣어 줘",
    "make it feel warmer in here": "여기 분위기 좀 따뜻하게 해 줘",
    "set a calmer tone": "차분한 톤으로 맞춰 줘",
    "make it cozy in here": "여기 아늑하게 해 줘",
    "set the mood for a movie": "영화 볼 분위기로 맞춰 줘",
    "get this place ready for guests": "손님 맞을 준비해 줘",
    "make it feel like morning": "아침 같은 분위기로 해 줘",
    "the air feels bad": "공기가 안 좋아", "it smells in this room": "방에서 냄새 나",
    "the air quality is awful": "공기질이 엉망이야",
    "clean the air in here": "여기 공기 좀 정화해 줘",
    "freshen this room up": "방 공기 좀 갈아 줘",
    "the air is too dry": "공기가 너무 건조해", "my throat is dry": "목이 건조해",
    "the windows are fogging up": "창문에 김이 서려",
    "fix the humidity in here": "여기 습도 좀 맞춰 줘",
    "it smells terrible in here": "여기 냄새가 지독해",
    "the fumes are getting bad": "가스 냄새가 심해져",
    "air this place out": "여기 환기해 줘", "get fresh air in here": "바깥 공기 좀 넣어 줘",
    "the floor is dirty": "바닥이 더러워",
    "there are crumbs everywhere": "부스러기가 여기저기 있어",
    "the carpet needs a pass": "카펫 한 번 밀어야겠어",
    "clean up in here": "여기 좀 치워 줘", "tidy the floor": "바닥 정리해 줘",
    "the grass is getting long": "잔디가 길어졌어",
    "the lawn looks rough": "잔디가 지저분해", "deal with the lawn": "잔디 좀 처리해 줘",
    "I need caffeine": "카페인이 필요해", "I am half asleep": "반쯤 자고 있어",
    "get me something hot to drink": "따뜻한 거 좀 만들어 줘",
    "make me a cup": "한 잔 내려 줘",
    "the water is cold": "물이 차가워", "no hot water again": "또 온수가 안 나와",
    "I want a hot shower": "뜨거운 물로 씻고 싶어", "get the water hot": "물 데워 줘",
    "it is too quiet in here": "여기 너무 조용해",
    "I cannot hear the show": "소리가 안 들려", "it is too loud": "너무 시끄러워",
    "put something on": "뭐라도 틀어 줘", "I want some music": "음악 좀 듣고 싶어",
    "turn it down a bit": "소리 좀 줄여 줘",
    "say it out loud": "소리 내서 말해 줘",
    "tell everyone in the house": "집 안에 다 알려 줘", "let me hear it": "들려 줘",
    "I do not feel safe": "불안해", "I am heading out": "나갈 거야",
    "make sure the place is secure": "문단속 좀 해 줘", "lock things up": "다 잠가 줘",
    "I am pulling out": "차 뺄게", "I parked already": "주차 다 했어",
    "close things up out front": "바깥쪽 다 닫아 줘",
    "keep an eye on the place": "집 좀 지켜봐 줘",
    "let me see what is going on": "지금 상황 좀 보여 줘", "record this": "이거 녹화해 줘",
    "scare them off": "쫓아내 줘", "make some noise": "소리 좀 내 줘",
    "raise the alarm": "경보 울려 줘",
    "I am done for the day": "오늘은 여기까지야",
    "nothing needs to be on right now": "지금은 아무것도 안 켜져 있어도 돼",
    "shut everything down in here": "여기 다 꺼 줘",
    "we are wasting electricity": "전기를 낭비하고 있어",
    "let us save some power": "전기 좀 아껴 줘", "cut the standby draw": "대기전력 좀 줄여 줘",
    "is everything alright at home": "집에 별일 없어",
    "how are things in here": "여기 상태 어때",
    "did I leave anything on": "뭐 켜 놓고 나온 거 있어",
    "what is the situation": "지금 상황이 어때",
    "keep me posted": "계속 알려 줘", "tell me if something is off": "뭔가 이상하면 알려 줘",
    "I want to know when it changes": "상태가 바뀌면 알려 줘",
    "remind me in a bit": "조금 있다 알려 줘", "give me a few minutes": "몇 분만 줘",
    "the crops look dry": "작물이 말라 보여", "the soil is parched": "흙이 바싹 말랐어",
    "these plants need water": "이 작물들 물이 필요해",
    "get water to the field": "밭에 물 좀 줘",
    "the plants are not getting enough light": "작물이 빛을 충분히 못 받고 있어",
    "it is dim in the grow room": "재배실이 어두워",
    "give the plants more light": "작물에 빛 좀 더 줘",
    "the animals look hungry": "가축들이 배고파 보여",
    "feeding time is overdue": "급여 시간이 지났어", "feed them": "사료 좀 줘",
    "the tank is running low": "탱크가 비어 가",
    "we need more water in the line": "관에 물이 더 필요해",
    "get the water moving": "물 좀 돌려 줘",
    "something is jammed": "뭔가 걸렸어", "stop the line": "라인 멈춰 줘",
    "hold production": "생산 잠깐 세워 줘",
    "water is going everywhere": "물이 새고 있어", "there is a leak": "누수가 있어",
    "shut the water off": "물 잠가 줘", "stop the flow": "흐름 막아 줘",
    "the air pressure is dropping": "공기압이 떨어지고 있어",
    "build the pressure back up": "압력 다시 올려 줘",
    "show everyone we are running": "가동 중이라고 표시해 줘",
    "flag this line as stopped": "이 라인 정지로 표시해 줘",
    "park the arm": "로봇팔 정위치로 보내 줘", "hold the cell": "셀 정지시켜 줘",
    "the samples are getting warm": "시료가 데워지고 있어",
    "this batch is off temperature": "이 배치가 설정 온도에서 벗어났어",
    "get the samples back on temperature": "시료 온도 다시 맞춰 줘",
}

# ── 시간절 ─────────────────────────────────────────────────────────────
# 한국어에서는 늘 문장 앞에 온다. 영어의 앞/뒤 다양성은 여기서 사라진다.
TRIG_KO = {
    "at sunset": "해 질 때", "when the sun goes down": "해가 지면",
    "as the sun sets": "해가 지기 시작하면", "at sunrise": "해 뜰 때",
    "when the sun comes up": "해가 뜨면", "around sundown": "해 질 무렵",
    "once it gets dark outside": "바깥이 어두워지면",
    "at {time}": "{time}에", "every day at {time}": "매일 {time}에",
    "at {time} on weekdays": "평일 {time}에",
    "every morning at {time_am}": "매일 {time_am}에",
    "every night at {time_pm}": "매일 {time_pm}에",
    "on {weekday} at {time}": "{weekday} {time}에",
    "every {n} minutes": "{n}분마다",
    "after {n} minutes": "{n}분 뒤에", "{n} minutes from now": "지금부터 {n}분 뒤에",
    "after waiting {n} minutes": "{n}분 기다렸다가",
    "once the {n} minute timer runs out": "{n}분 타이머가 끝나면",
    "when the motion sensor picks something up": "동작 감지 센서에 뭔가 잡히면",
    "when {sensor} detects movement": "{sensor}%S 움직임을 감지하면",
    "if motion is detected in the {place}": "{place}에서 움직임이 감지되면",
    "the moment something moves in the {place}": "{place}에서 뭔가 움직이는 순간",
    "when nothing has moved for {n} minutes": "{n}분 동안 아무 움직임도 없으면",
    "while someone is in the {place}": "{place}에 사람이 있는 동안",
    "when the {place} is occupied": "{place}에 사람이 있으면",
    "once the {place} is empty": "{place}%S 비면",
    "while nobody is around": "아무도 없는 동안",
    "when someone shows up in the {place}": "{place}에 누가 나타나면",
    "when I get home": "내가 집에 오면", "as soon as I arrive home": "집에 도착하자마자",
    "when I pull into the driveway": "차를 집 앞에 대면",
    "once I am back home": "내가 집에 돌아오면",
    "when I am close to home": "내가 집 근처에 오면",
    "when I leave home": "내가 집을 나서면", "once everyone has left": "다들 나가고 나면",
    "after I head out": "내가 나간 뒤에", "when I am away from home": "내가 집에 없으면",
    "when the {place} door opens": "{place} 문이 열리면",
    "if a window is left open": "창문이 열린 채로 있으면",
    "when {sensor} says the door is open": "{sensor}%S 문이 열렸다고 알리면",
    "once the door has been open for {n} minutes": "문이 {n}분 동안 열려 있으면",
    "when the door closes": "문이 닫히면",
    "when someone rings the doorbell": "누가 초인종을 누르면",
    "if the doorbell goes off": "초인종이 울리면",
    "when there is somebody at the door": "문 앞에 누가 있으면",
    "when I press the button": "내가 버튼을 누르면",
    "with a single press of {dev_t}": "{dev_t}%O 한 번 누르면",
    "when I double-press {dev_t}": "{dev_t}%S 연속 두 번 눌리면",
    "with one tap on the wall switch": "벽 스위치를 한 번 누르면",
    "when the scene button is pressed": "씬 버튼이 눌리면",
    "when the temperature goes above {deg_hi} degrees": "온도가 {deg_hi}도를 넘으면",
    "if the temperature drops below {deg_lo} degrees": "온도가 {deg_lo}도 아래로 떨어지면",
    "while the temperature stays over {deg_hi} degrees": "온도가 {deg_hi}도를 계속 넘고 있으면",
    "when the humidity climbs over {pct} percent": "습도가 {pct}퍼센트를 넘으면",
    "once the air quality gets worse than {lvl}": "공기질이 {lvl}보다 나빠지면",
    "if {sensor} reads more than {lvl}": "{sensor} 값이 {lvl}보다 크면",
    "once {sensor} goes over {lvl}": "{sensor}%S {lvl}%O 넘으면",
    "if {sensor} falls under {lvl}": "{sensor}%S {lvl} 아래로 내려가면",
    "while {sensor} stays above {lvl}": "{sensor}%S {lvl}%O 계속 넘고 있으면",
    "when it starts raining": "비가 오기 시작하면",
    "if rain is in the forecast": "비 예보가 있으면",
    "when it gets hot outside": "바깥이 더워지면",
    "if the outside temperature drops below {deg_lo}": "바깥 온도가 {deg_lo}도 아래로 떨어지면",
    "when snow is expected": "눈이 올 것 같으면",
    "if the forecast says frost": "서리 예보가 있으면",
    "when a meeting is about to start": "회의가 곧 시작되면",
    "at the start of my next event": "다음 일정이 시작되면",
    "if my calendar says I am busy": "일정상 내가 바쁘면",
    "when today's first event begins": "오늘 첫 일정이 시작되면",
    "when my phone connects to the home wi-fi": "내 폰이 집 와이파이에 붙으면",
    "if my phone battery falls under {pct} percent":
        "내 폰 배터리가 {pct}퍼센트 아래로 떨어지면",
    "when my phone goes into sleep mode": "내 폰이 취침 모드로 들어가면",
    "while I am on a call": "내가 통화 중이면",
    "when the battery drops below {pct} percent": "배터리가 {pct}퍼센트 아래로 떨어지면",
    "if any sensor battery is running low": "센서 배터리가 얼마 안 남으면",
    "once the battery is full": "배터리가 다 차면",
    'when the camera starts recording': '카메라가 녹화를 시작하면',
    'if the camera comes on': '카메라가 켜지면',
    'while the camera is recording': '카메라가 녹화 중인 동안',
    'once the camera goes offline': '카메라 연결이 끊기면',
    'when the smoke detector goes off': '연기 감지기가 울리면',
    'if the smoke alarm sounds': '화재 경보가 울리면',
    'when {sensor} reports smoke': '{sensor}%S 연기를 알리면',
    'when a water leak is detected': '누수가 감지되면',
    'if {sensor} finds water on the floor': '{sensor}%S 바닥의 물을 감지하면',
    'when the leak sensor trips': '누수 센서가 작동하면',
    'when the gas sensor goes over {lvl}': '가스 센서가 {lvl}%O 넘으면',
    'if a gas leak is detected': '가스 누출이 감지되면',
    'when {sensor} reads a dangerous level': '{sensor}%S 위험 수준을 가리키면',
    'when power draw goes over {watt} watts': '전력 사용이 {watt}와트를 넘으면',
    'if the meter reads above {watt}': '계량기가 {watt}%O 넘으면',
    'when energy use spikes': '전력 사용이 급증하면',
    'if power draw stays above {watt} watts': '전력 사용이 {watt}와트를 계속 넘고 있으면',
    'when the washing machine finishes': '세탁기가 끝나면',
    'as soon as the load is finished': '세탁이 끝나자마자',
    'when the wash cycle ends': '세탁 코스가 끝나면',
    'when the machine finishes its cycle': '설비가 한 사이클을 마치면',
    'once the line run is done': '라인 가동이 끝나면',
    'when {dev_t} reports it is done': '{dev_t}%S 끝났다고 알리면',
    'when {dev_t} turns on': '{dev_t}%S 켜지면',
    'if {dev_t} is switched off': '{dev_t}%S 꺼지면',
    'once {dev_t} has been on for {n} minutes': '{dev_t}%S {n}분 동안 켜져 있으면',
    'when {sensor} picks up heavy vibration': '{sensor}%S 큰 진동을 감지하면',
    'if vibration goes over {lvl}': '진동이 {lvl}%O 넘으면',
    'when the machine starts shaking': '설비가 흔들리기 시작하면',
    'when the load tilts past {tilt} degrees': '적재물이 {tilt}도 넘게 기울면',
    'if {sensor} reports a tilt': '{sensor}%S 기울어졌다고 알리면',
    'when something comes within {cm} centimeters': '뭔가 {cm}센티미터 안으로 들어오면',
    'if {sensor} sees an object in the way': '{sensor}%S 앞을 막는 물체를 보면',
    'when the wind picks up past {wind}': '바람이 {wind} 이상으로 세지면',
    'if wind speed goes over {wind}': '풍속이 {wind}%O 넘으면',
    'when the emergency stop is hit': '비상정지가 눌리면',
    'if anyone presses the emergency stop': '누가 비상정지를 누르면',
    'when the safety barrier is broken': '안전 방책이 뚫리면',
    'if someone crosses the light curtain': '누가 광커튼을 통과하면',
}

# ── 조건절 (LOGIC 의 {cond}) ───────────────────────────────────────────
COND_KO = {
    "the room is too warm": "방이 너무 더우면", "nobody is home": "집에 아무도 없으면",
    "the door is open": "문이 열려 있으면",
    "the humidity is over 60 percent": "습도가 60퍼센트를 넘으면",
    "it is dark outside": "바깥이 어두우면",
    "the washing machine is running": "세탁기가 돌고 있으면",
    "someone is in the room": "방에 사람이 있으면",
    "the temperature is under 18 degrees": "온도가 18도 아래면",
    "the window is open": "창문이 열려 있으면",
    "the tank is below half": "탱크가 절반 아래면",
    "the battery is under 20 percent": "배터리가 20퍼센트 아래면",
}
# 같은 조건을 "~일 때" 로 — 앞에 시간절이 있으면 "~면 ~면" 이 되어 어색하다
COND_KO_WHEN = {
    "the room is too warm": "방이 더울 때", "nobody is home": "집에 아무도 없을 때",
    "the door is open": "문이 열려 있을 때",
    "the humidity is over 60 percent": "습도가 60퍼센트를 넘을 때",
    "it is dark outside": "바깥이 어두울 때",
    "the washing machine is running": "세탁기가 돌고 있을 때",
    "someone is in the room": "방에 사람이 있을 때",
    "the temperature is under 18 degrees": "온도가 18도 아래일 때",
    "the window is open": "창문이 열려 있을 때",
    "the tank is below half": "탱크가 절반 아래일 때",
    "the battery is under 20 percent": "배터리가 20퍼센트 아래일 때",
}

# 같은 조건을 "~는지" 로 — 제한시간 대기(D10)에서 "…인지 기다려 본다"
COND_KO_Q = {
    "the room is too warm": "방이 더워지는지", "nobody is home": "집이 비는지",
    "the door is open": "문이 열리는지",
    "the humidity is over 60 percent": "습도가 60퍼센트를 넘는지",
    "it is dark outside": "바깥이 어두워지는지",
    "the washing machine is running": "세탁기가 도는지",
    "someone is in the room": "방에 사람이 오는지",
    "the temperature is under 18 degrees": "온도가 18도 아래로 내려가는지",
    "the window is open": "창문이 열리는지",
    "the tank is below half": "탱크가 절반 아래로 내려가는지",
    "the battery is under 20 percent": "배터리가 20퍼센트 아래로 내려가는지",
}

# 같은 조건을 "~(으)ㄹ 때까지" 로 — 그 조건이 될 때까지 기다리거나 반복하는 자리
COND_KO_UNTIL = {
    "the room is too warm": "방이 더워질 때까지", "nobody is home": "집이 빌 때까지",
    "the door is open": "문이 열릴 때까지",
    "the humidity is over 60 percent": "습도가 60퍼센트를 넘을 때까지",
    "it is dark outside": "바깥이 어두워질 때까지",
    "the washing machine is running": "세탁기가 돌기 시작할 때까지",
    "someone is in the room": "방에 사람이 올 때까지",
    "the temperature is under 18 degrees": "온도가 18도 아래로 내려갈 때까지",
    "the window is open": "창문이 열릴 때까지",
    "the tank is below half": "탱크가 절반 아래로 내려갈 때까지",
    "the battery is under 20 percent": "배터리가 20퍼센트 아래로 내려갈 때까지",
}

# 같은 조건을 "~하는 동안" 으로 써야 하는 자리 (D5·D13)
COND_KO_WHILE = {k: v.replace("으면", "은 동안").replace("면", "는 동안")
                 for k, v in COND_KO.items()}
COND_KO_WHILE.update({
    "the room is too warm": "방이 더운 동안", "nobody is home": "집에 아무도 없는 동안",
    "the door is open": "문이 열려 있는 동안",
    "the humidity is over 60 percent": "습도가 60퍼센트를 넘는 동안",
    "it is dark outside": "바깥이 어두운 동안",
    "the washing machine is running": "세탁기가 도는 동안",
    "someone is in the room": "방에 사람이 있는 동안",
    "the temperature is under 18 degrees": "온도가 18도 아래인 동안",
    "the window is open": "창문이 열려 있는 동안",
    "the tank is below half": "탱크가 절반 아래인 동안",
    "the battery is under 20 percent": "배터리가 20퍼센트 아래인 동안",
})

# ── 집이 아닌 공간용 한국어 (templates.NONHOME 의 새 영어 문형) ──────────
# "집에 아무도 없으면" 이 공장·연구실에 붙던 것을 여기서 갈라 준다.
NONHOME_KO = {
    "nobody is around":                "아무도 없",
    "when I arrive":                   "내가 도착하면",
    "as soon as I arrive":             "내가 도착하자마자",
    "when I pull into the parking lot": "주차장에 차를 대면",
    "once I am back":                  "내가 돌아오면",
    "when I am close by":              "내가 근처에 오면",
    "when I leave":                    "내가 나가면",
    "when I am away":                  "내가 자리에 없으면",
}
TRIG_KO.update({k: v for k, v in NONHOME_KO.items() if k != "nobody is around"})
# 조건절은 어미가 다섯 가지라 뿌리에서 만든다
COND_KO["nobody is around"]       = "아무도 없으면"
COND_KO_WHEN["nobody is around"]  = "아무도 없을 때"
COND_KO_Q["nobody is around"]     = "아무도 없는지"
COND_KO_UNTIL["nobody is around"] = "아무도 없을 때까지"
COND_KO_WHILE["nobody is around"] = "아무도 없는 동안"


# ── 로직 틀 ────────────────────────────────────────────────────────────
# {a} 동작절(반말 어간) · {cond} 조건 · {n},{m} 숫자
LOGIC_KO = {
    # 방아쇠절과 조건절이 나란히 오면 어미를 갈라 준다 — 방아쇠는 "~할 때",
    # 조건은 "~면". 안 그러면 방아쇠가 둘로 보인다 (whisoo 2026-08-25):
    #   "버튼을 누르면 지금 온도가 18도 아래일 때 …"  ← 어느 쪽이 방아쇠인지 모름
    #   "버튼을 누를 때 온도가 18도보다 낮으면 …"      ← 이렇게
    # 아래 TRIG_WHEN_FRAMES 에 적힌 문형이 그 대상이다.
    "if {cond} right now, {a}": "{cond} {a}",
    # "~일 때 그때만" 은 같은 말을 두 번 한다. "~일 때만" 하나면 된다.
    "{a}, but only if {cond}": "{cond_only} {a}",
    "{a}, then {n} minutes later turn it back off": "{a_c}, {n}분 뒤에 다시 꺼",
    "wait {n} minutes and then {a}": "{n}분 기다렸다가 {a}",
    "keep checking and {a} for as long as {cond}": "{cond_while} 계속 {a}",
    "{a} while {cond}, and stop once that changes":
        "{cond_while} {a_c}, 그러다 바뀌면 멈춰",
    "check every {n} minutes and {a} if {cond}": "{n}분마다 확인해서 {cond} {a}",
    "{a} every {n} minutes": "{n}분마다 {a}",
    "{a} every {n} minutes for the next {m} hours": "앞으로 {m}시간 동안 {n}분마다 {a}",
    "repeat this {m} times: {a}, then wait {n} minutes":
        "{a_c} {n}분 쉬는 걸 {m}번 반복해",
    "{a} every {n} minutes until {cond}": "{cond_until} {n}분마다 {a}",
    "once {cond}, {a} every {n} minutes": "{cond} {n}분마다 {a}",
    "wait up to {n} minutes to see if {cond}; if not, {a}":
        "{cond_q} 최대 {n}분 기다려 보고, 그래도 아니면 {a}",
    # 아래 넷은 방아쇠가 읽는 값을 되받는다. "그게" 가 바로 앞 방아쇠절의 값이다
    # ("온도가 10도를 넘을 때 그게 한 시간 전보다 높으면 …").
    # 예전에는 "한 시간 전보다 높으면" / "오늘 그 일이" 라고만 해서 무엇을 견주고
    # 무엇을 세는지가 문장에 없었다.
    "if it is higher than it was an hour ago, {a}": "그게 한 시간 전보다 높으면 {a}",
    "compare it with yesterday at the same time and {a} if it went up":
        "그게 어제 같은 시각보다 올랐으면 {a}",
    "count how many times it happens and {a} once it passes {m}":
        "그 횟수를 세다가 {m}번을 넘으면 {a}",
    "{a} every {n} minutes while {cond}, and stop after {m} hours":
        "{cond_while} {n}분마다 {a_c}, {m}시간 뒤에는 멈춰",
    "wait until {cond}, then {a} every {n} minutes for {m} hours":
        "{cond_until} 기다렸다가 {m}시간 동안 {n}분마다 {a}",
}

# 방아쇠절을 "~할 때" 로 바꿔 쓰는 문형. 뒤에 "~면" 으로 끝나는 절이 곧바로 오는
# 것들이다 — 둘 다 "~면" 이면 방아쇠가 둘로 보인다.
TRIG_WHEN_FRAMES = {
    "if {cond} right now, {a}",
    "if it is higher than it was an hour ago, {a}",
    "compare it with yesterday at the same time and {a} if it went up",
    "count how many times it happens and {a} once it passes {m}",
}

# "~하면" → "~할 때". 어간에 ㄹ 을 붙일 뿐이라 규칙 하나로 끝난다.
#   누르면 → 누를 때 · 넘으면(자음 어간 + 으면) → 넘을 때 · 기울면(이미 ㄹ) → 기울 때
# 규칙으로 안 되는 것만 아래 표에 적는다.
TRIG_WHEN_FIX = {
    "다들 나가고 나면": "다들 나가고 난 뒤에",
}


# 문장이 "~면" 절로 시작하나 ("이상하면 알려 줘", "그게 오늘 3번 넘었으면 …")
_STARTS_MYEON = re.compile(r"^[^,]{0,20}?면 ")


def trig_when(text):
    """방아쇠절의 "~하면" 을 "~할 때" 로. "면" 으로 안 끝나면 그대로 둔다."""
    t = (text or "").strip()
    if t in TRIG_WHEN_FIX:
        return TRIG_WHEN_FIX[t]
    if not t.endswith("면"):
        return t                       # "매일 8시에", "해 질 무렵" 따위
    s = t[:-1]
    if s.endswith("으"):               # 자음 어간 + 으면
        return s[:-1] + "을 때"
    ch = s[-1]
    if "가" <= ch <= "힣":
        code = ord(ch) - 0xAC00
        if code % 28 == 8:             # 어간이 이미 ㄹ 받침 — "기울면"
            return s + " 때"
        if code % 28 == 0:             # 받침 없음 — ㄹ 을 얹는다
            return s[:-1] + chr(0xAC00 + code + 8) + " 때"
    return s + "ㄹ 때"

# ── 말투 ───────────────────────────────────────────────────────────────
# 영어 6종을 그대로 받지만 한국어에서는 존댓말을 크게 줄인다.
# 사람은 비서에게 존댓말을 잘 쓰지 않는다 (whisoo). 영어의 여섯 말투 중
# 존댓말로 가는 것은 `polite` 하나뿐이고, 그마저 절반은 "좀 ~해 줘" 반말로 보낸다.
#   → 존댓말 비중 약 8%. 영어판의 tone 분포는 그대로다 (영어 문장은 안 건드린다).
#
# 동작절은 -아/어 꼴("켜", "닫아", "확인해")이나 "~해 줘" 로 끝난다.
# 보조용언 '주다' 를 붙여 어미만 갈아 끼운다.
AUX_KO = {
    "ask":    "줄래?",         # 반말 의문
    "could":  "줄 수 있어?",   # 반말 의문 (예전엔 "주시겠어요?" — 존댓말이라 바꿨다)
    "wish":   "줬으면 해.",    # 반말 희망
    "polite": "주세요.",       # ★ 유일한 존댓말
}
HONORIFIC = {"polite"}


# 붙어 다니는 동사 — 사이에 '좀' 이 끼면 갈라진다 ("켜 좀 둬", "맞춰 좀 줘")
# 앞 동사에 붙어 다니는 보조용언. '좀' 은 이것들 앞에 오면 안 된다
#   "알려 좀 줘"(x) → "좀 알려 줘"(o) · "켜 좀 둬"(x) → "좀 켜 둬"(o)
_AUX_WORD = {"줘", "주", "주세요", "둬", "놔", "봐", "줄래?", "볼래?",
             "두세요", "놓으세요", "주시겠어요?"}


def _soften(core):
    """'좀' 을 넣어 부드러운 반말로. "거실 조명 켜" → "거실 조명 좀 켜".

    뒤에서부터 보조용언을 건너뛰고, 진짜 동사 앞에 넣는다."""
    if "좀" in core:
        return core
    w = core.split(" ")
    i = len(w) - 1
    while i > 0 and (w[i] in _AUX_WORD or w[i - 1].endswith("다")):
        i -= 1          # "껐다 켜" 는 한 덩이 — 사이에 넣으면 갈라진다
    if i <= 0:
        return "좀 " + core
    return " ".join(w[:i] + ["좀"] + w[i:])


def apply_tone(core, tone, ask=False):
    """ask=True 면 묻는 문장이다 — 마침표가 아니라 물음표로 끝낸다."""
    core = core.rstrip(" .")
    if ask:
        return core + "?"
    if tone == "terse":
        return core
    if tone == "bare":
        return core + "."
    if tone == "polite":
        # 절반만 존댓말. 어느 쪽인지는 문장이 정한다 — 다시 돌려도 같게.
        if sum(map(ord, core)) % 2:
            core = _soften(core)
            return core[:-1] + "줘." if core.endswith("줘") else core + " 줘."
    aux = AUX_KO.get(tone, "주세요.")
    if core.endswith("줘"):        # "알려 줘" → "알려 주세요."
        return core[:-1] + aux
    return core + " " + aux       # "거실 조명 켜" → "거실 조명 켜 주세요."


# ── 문장 조립 ──────────────────────────────────────────────────────────
MISSING = []          # 한국어 틀이 없어서 못 만든 것 — build_korean.py 가 본다


def _slots_ko(text, slots, dev_ko=None, place_tag=None, sensor_cat=None):
    """{n} {time} {color} … 자리를 한국어 값으로 채운다."""
    if dev_ko is not None:
        text = text.replace("{dev}", dev_ko).replace("{dev_t}", dev_ko)
    if "{place}" in text:
        text = text.replace("{place}", place_ko(place_tag))
    if "{sensor}" in text:
        text = text.replace("{sensor}", NOUN_KO.get(sensor_cat, "센서"))
    for k, v in (slots or {}).items():
        key = "{%s}" % k
        if key not in text:
            continue
        if k in ("time", "time_am", "time_pm"):
            v = time_ko(v)
        elif k == "color":
            v = COLOR_KO.get(v, v)
        elif k == "scene":
            v = SCENE_KO.get(v, v)
        elif k == "weekday":
            v = WEEKDAY_KO.get(v, v)
        text = text.replace(key, str(v))
    # 같은 낱말이 붙어 두 번 나오면 하나로 — "거실 거실 로봇청소기" (방이 겹칠 때)
    text = re.sub(r"(?:(?<=^)|(?<=\s))(\S+)\s+\1(?=\s|$)", r"\1", text)
    return text


def body_ko(*, act_tpl, vague_tpl, dev_ko, slots, place_tag, sensor_cat,
            embed=False):
    """동작절 한 덩이. 한국어 틀이 없으면 None.
    embed=True 면 앞에 절이 붙는 자리라 묻는 문장을 '안긴 꼴' 로 바꾼다."""
    if vague_tpl:
        ko = VAGUE_KO.get(vague_tpl)
        if ko is None:
            MISSING.append(("vague", vague_tpl))
            return None
        return ko
    ko = (QUERY_EMBED_KO.get(act_tpl) if embed else None) or ACT_KO.get(act_tpl)
    if ko is None:
        MISSING.append(("act", act_tpl))
        return None
    return _slots_ko(ko, slots, dev_ko, place_tag, sensor_cat)


def conj(body):
    """문장 중간에 오는 동작절 — 종결형을 이음형으로 바꾼다.
    한국어는 한 문장에서 반말과 존댓말을 섞지 않는다. 끝의 어미가 문장 전체의
    말투를 정하므로 중간 절은 '~해 주고' 로 이어야 한다."""
    body = body.rstrip(" .")
    return body[:-1] + "주고" if body.endswith("줘") else body + " 주고"


def sentence_ko(*, act_tpl, vague_tpl, dev_ko, aslots, act_place, sensor_cat,
                trig_tpl, tslots, trig_place, frame, cond_text, lslots, tone,
                dev_t_ko=None, parts_out=None):
    """영어와 같은 순서로 조립하되 한국어 어순을 따른다 — 시간절이 늘 앞이다.

    parts_out 을 주면 조각을 (글, 자리이름) 으로 담아 준다 — 절 라벨을 뽑는 데 쓴다.
    조사·말투는 글자를 바꾸지만 띄어쓰기는 안 건드리므로 단어 개수가 그대로다."""
    # 앞에 시간절·조건절이 붙으면 묻는 문장을 '안긴 꼴' 로 바꾼다
    #   "주방 온도 몇 도야?" → "문이 열리면 주방 온도 알려 줘"
    body = body_ko(act_tpl=act_tpl, vague_tpl=vague_tpl, dev_ko=dev_ko,
                   slots=aslots, place_tag=act_place, sensor_cat=sensor_cat,
                   embed=bool(trig_tpl or frame))
    if body is None:
        return None
    core = body
    if parts_out is not None and not frame:
        parts_out.append((body, "{a}"))
    if frame:
        ko = LOGIC_KO.get(frame)
        if ko is None:
            MISSING.append(("logic", frame))
            return None
        # 시간절이 이미 "~면" 으로 끝나면 조건은 "~일 때" 로 — "~면 ~면" 을 막는다.
        # 다만 TRIG_WHEN_FRAMES 는 거꾸로 간다 — 방아쇠를 "~할 때" 로 돌리고
        # 조건은 "~면" 을 그대로 쓴다 (아래 trig_tpl 자리에서 돌린다).
        # 동작절 자체가 "이상하면 알려 줘" 처럼 "~면" 으로 시작하면 조건은 "~일 때" 로
        # 돌린다 — 조건도 "~면" 이면 "…아래면 바뀌면 알고 싶어" 가 된다.
        flip = frame in TRIG_WHEN_FRAMES and not _STARTS_MYEON.match(body)
        cond_tbl = (COND_KO if flip
                    else COND_KO_WHEN if (trig_tpl or _STARTS_MYEON.match(body))
                    else COND_KO)
        sub = {"{cond_until}": COND_KO_UNTIL.get(cond_text, cond_text),
               "{cond_q}": COND_KO_Q.get(cond_text, cond_text),
               "{a_c}": conj(body), "{a}": body,
               "{cond_while}": COND_KO_WHILE.get(cond_text, cond_text),
               "{cond_only}": COND_KO_WHEN.get(cond_text, cond_text) + "만",
               "{cond_when}": COND_KO_WHEN.get(cond_text, cond_text),
               "{cond}": cond_tbl.get(cond_text, cond_text)}
        core = ko
        for k, v in sub.items():
            core = core.replace(k, v)
        num = {"{n}": str((lslots or {}).get("n", "")), "{m}": str((lslots or {}).get("m", ""))}
        for k, v in num.items():
            core = core.replace(k, v)
        if parts_out is not None:
            # 자리 이름을 붙인 채로 같은 순서로 다시 조립한다 — 글자는 위와 같아야 한다
            for piece in _LOGIC_SPLIT.split(ko):
                if not piece:
                    continue
                t = piece
                for k, v in {**sub, **num}.items():
                    t = t.replace(k, v)
                parts_out.append((t, piece if piece in sub else "글자"))
    if trig_tpl:
        ko = TRIG_KO.get(trig_tpl)
        if ko is None:
            MISSING.append(("trig", trig_tpl))
            return None
        # 방아쇠 뒤에 "~면" 절이 곧바로 오면 방아쇠는 "~할 때" 로 — 안 그러면
        # 방아쇠가 둘로 보인다. 문형이 정한 자리(TRIG_WHEN_FRAMES)와, 동작절
        # 자체가 "이상하면 알려 줘" 처럼 "~면" 으로 시작하는 자리 둘 다에 건다.
        if frame in TRIG_WHEN_FRAMES or _STARTS_MYEON.match(core):
            ko = trig_when(ko)         # "버튼을 누르면" → "버튼을 누를 때"
        tt = _slots_ko(ko, tslots, dev_t_ko or dev_ko, trig_place, sensor_cat)
        if parts_out is not None:
            parts_out.insert(0, (tt, "{trig}"))
        core = f"{tt} {core}"          # 한국어는 시간절이 앞
    # 같은 부사가 절을 건너 두 번 나오면 뒤엣것을 지운다
    #   "계속 넘고 있으면 계속 알려 줘" · "확인해서 … 확인하라고 알려"
    for _w in ("계속", "확인"):
        _i = core.find(_w)
        if _i >= 0:
            _j = core.find(_w + " ", _i + len(_w))
            if _j >= 0:
                core = core[:_j] + core[_j + len(_w) + 1:]
    # 절이 안 붙은 채로 남은 묻는 문장만 물음표를 받는다
    return apply_tone(josa(core), tone,
                      ask=(not trig_tpl and not frame and not vague_tpl
                           and act_tpl in ASK_KO))
