# -*- coding: utf-8 -*-
"""gold 정정(사용자 검토 결정, §26.1) — build_ir.gold_of가 paper gold에 적용. 명령별 편집은 명시적으로 나열.
결정: A3 기기 켜기=Switch.On / A4 "모드로 켜고"=Switch.On+SetMode 두 호출 / A8 "채널 하나 내려"=ChannelDown / B3·B4 켜짐·꺼짐 상태=Switch.Switch / B12 count는 숫자."""
import copy, re, json

def _walk(nodes, fn):
    for n in nodes:
        fn(n)
        for k in ("then", "else", "body"):
            if n.get(k): _walk(n[k], fn)

def _replace_call(nodes, old, new_calls):
    """target==old인 call 노드를 new_calls(list)로 치환(제자리 확장)"""
    out = []
    for n in nodes:
        for k in ("then", "else", "body"):
            if n.get(k): n[k] = _replace_call(n[k], old, new_calls)
        if n.get("op") == "call" and n["target"] == old: out.extend(copy.deepcopy(new_calls))
        else: out.append(n)
    return out

EDITS = {
    "주방 조명을 켜고 10초 뒤에 주방 제습기를 켜줘.": lambda tl: _replace_call(tl, "Dehumidifier.SetDehumidifierMode", [{"op": "call", "target": "Switch.On", "args": {}}]),
    "TV 채널을 하나 내려줘.": lambda tl: _replace_call(tl, "Television.SetChannel", [{"op": "call", "target": "Television.ChannelDown", "args": {}}]),
    "서버실 온도가 30도 이상이고 에어컨이 꺼져 있으면, 에어컨을 냉방 모드로 켜고 메인 사이렌을 긴급 모드로 울려줘.":
        lambda tl: _replace_call(tl, "Switch.On", [{"op": "call", "target": "Switch.On", "args": {}}, {"op": "call", "target": "AirConditioner.SetAirConditionerMode", "args": {"Mode": "cool"}}]),
    "이산화탄소가 1500ppm 이상이고 블라인드가 닫혀있으면, 공기청정기를 자동 모드로 켜고 블라인드를 올려줘.":
        lambda tl: _replace_call(tl, "AirPurifier.SetAirPurifierMode", [{"op": "call", "target": "Switch.On", "args": {}}, {"op": "call", "target": "AirPurifier.SetAirPurifierMode", "args": {"Mode": "auto"}}]),
}
EDITS["20초마다 부엌 라이트를 toggle 해줘. 8번만."] = lambda tl: _replace_call(tl, "Light.MoveToBrightness", [{"op": "call", "target": "Switch.Toggle", "args": {}}])   # "toggle" = Switch.Toggle (gold의 켜기 100은 표기 잔여)
EDITS["비가 오고 문이 잠겨 있지 않으면, 문을 잠그고 제습기를 건조 모드로 설정해줘."] = lambda tl: _replace_call(tl, "Dehumidifier.SetDehumidifierMode", [{"op": "call", "target": "Dehumidifier.SetDehumidifierMode", "args": {"Mode": "drying"}}])   # "건조 모드" = drying (gold internalCare는 재작성 전 잔여)
EDITS["오후 1시부터 3시까지 5분마다 벨브를 열었다 닫았다 반복해줘."] = lambda tl: [tl[0], {**tl[1], "body": [{"op": "if", "cond": "n % 2 == 0", "then": [tl[1]["body"][0]], "else": [tl[1]["body"][1]]}]}]   # 토글 = n%2 (사용자 결정; Toggle 함수 없는 밸브)
EDITS["멀티버튼의 버튼3이 눌릴 때마다 주방 조명을 켜고 끄는 것을 반복해줘."] = lambda tl: [tl[0], {**tl[1], "body": [tl[1]["body"][0], {"op": "call", "target": "Switch.Toggle", "args": {}}]}]   # 켜고 끄기 = Switch.Toggle 한 호출(사용자 결정)
EDITS["멀티버튼의 버튼4가 눌리면 모든 조명을 야간 모드(밝기 10%)로 설정해줘."] = lambda tl: [n for n in tl if not (n.get("op") == "call" and n["target"] == "Light.MoveToColor")]   # "야간 모드(밝기 10%)" = 밝기 10 한 호출 (gold의 빨간색은 근거 없음; 명령문 괄호 표기는 데이터셋에서 수정 권장)
PERIOD_EDITS = {   # C1: 시간창 안 상태 감시 명령에 주기 표현이 없으면 폴링 기본 100 MSEC (gold "1 HOUR"는 임의값)
    "오후 6시부터 8시까지 1층에 사람이 감지되면 1층 불을 다 켜줘.": "100 MSEC",
}
COND_EDITS = {   # 부분 문자열 치환 (cond 안)
    "WeatherProvider.Pm25Weather >= 2000": "WeatherProvider.Pm10Weather >= 2000",   # B8: "외부 미세먼지" = Pm10 (초미세 = Pm25); 다른 gold와 일관되게
    "not (PresenceSensor.Presence == true) or PresenceSensor.Presence == false": "PresenceSensor.Presence == false and PresenceSensor.Presence == false",   # "거실과 침실에 모두 감지되지 않으면" = 둘 다 부재(and); gold의 or는 오류
    'Siren.SirenMode != "emergency"': "Switch.Switch == false",
    "Light.CurrentBrightness > 0": "Switch.Switch == true",
    "Light.CurrentBrightness == 0": "Switch.Switch == false",
}

LEVEL_MAP = {"LevelControl.MoveToLevel": "Light.MoveToBrightness", "LevelControl.CurrentLevel": "Light.CurrentBrightness", "ColorControl.SetColor": "Light.MoveToColor"}
def _no_control(n):
    """사용자 결정: *Control 계열 서비스는 쓰지 않음 → 조명 서비스로 정규화(Level→Brightness)"""
    if n.get("op") == "call" and n["target"] in LEVEL_MAP:
        n["target"] = LEVEL_MAP[n["target"]]
        if "Level" in n.get("args", {}): n["args"]["Brightness"] = n["args"].pop("Level")
        n["args"] = {k: (v.replace("LevelControl.CurrentLevel", "Light.CurrentBrightness") if isinstance(v, str) else v) for k, v in n.get("args", {}).items()}
    if n.get("op") == "read" and n.get("src") in LEVEL_MAP: n["src"] = LEVEL_MAP[n["src"]]
    if n.get("op") in ("if", "wait") and isinstance(n.get("cond"), str):
        for a, b in LEVEL_MAP.items(): n["cond"] = n["cond"].replace(a, b)
def fix(cmd, ir):
    ir = copy.deepcopy(ir); tl = ir["timeline"]
    _walk(tl, _no_control)
    if cmd in EDITS: tl = EDITS[cmd](tl)
    def f(n):
        if n.get("op") in ("if", "wait") and isinstance(n.get("cond"), str):
            for a, b in COND_EDITS.items(): n["cond"] = n["cond"].replace(a, b)
        if n.get("op") == "cycle" and n.get("count") == "n":          # B12: count는 숫자
            m = re.match(r"n >= (\d+)", str(n.get("until") or ""))
            if m: n["count"] = int(m.group(1))
    if cmd in PERIOD_EDITS: _walk(tl, lambda n: n.update(period=PERIOD_EDITS[cmd]) if n.get("op") == "cycle" else None)
    _walk(tl, f); ir["timeline"] = tl
    return ir
