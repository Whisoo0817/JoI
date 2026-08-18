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
COND_EDITS = {   # 부분 문자열 치환 (cond 안)
    'Siren.SirenMode != "emergency"': "Switch.Switch == false",
    "Light.CurrentBrightness > 0": "Switch.Switch == true",
    "Light.CurrentBrightness == 0": "Switch.Switch == false",
}

def fix(cmd, ir):
    ir = copy.deepcopy(ir); tl = ir["timeline"]
    if cmd in EDITS: tl = EDITS[cmd](tl)
    def f(n):
        if n.get("op") in ("if", "wait") and isinstance(n.get("cond"), str):
            for a, b in COND_EDITS.items(): n["cond"] = n["cond"].replace(a, b)
        if n.get("op") == "cycle" and n.get("count") == "n":          # B12: count는 숫자
            m = re.match(r"n >= (\d+)", str(n.get("until") or ""))
            if m: n["count"] = int(m.group(1))
    _walk(tl, f); ir["timeline"] = tl
    return ir
