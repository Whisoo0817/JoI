# -*- coding: utf-8 -*-
"""평가 — 계층 채점 S(구조)→T(시간 슬롯)→C(조건식)→V(서비스)→A(인자), gold 관례 정규화·동치, gold 정정(사용자 검토 결정, README §26.1·§28)."""
import copy, re
from .skeleton import skeleton
from .catalog import svc_info

# ── gold 정정 (사용자 결정; 명령별 편집은 명시적으로 나열) ──
def _replace_call(nodes, old, new_calls):
    out = []
    for n in nodes:
        for k in ("then", "else", "body"):
            if n.get(k): n[k] = _replace_call(n[k], old, new_calls)
        out.extend(copy.deepcopy(new_calls) if n.get("op") == "call" and n["target"] == old else [n])
    return out
_call = lambda t, **a: {"op": "call", "target": t, "args": a}
EDITS = {
    "주방 조명을 켜고 10초 뒤에 주방 제습기를 켜줘.": lambda tl: _replace_call(tl, "Dehumidifier.SetDehumidifierMode", [_call("Switch.On")]),                                   # A3 기기 켜기 = Switch.On
    "TV 채널을 하나 내려줘.": lambda tl: _replace_call(tl, "Television.SetChannel", [_call("Television.ChannelDown")]),                                                             # A8
    "서버실 온도가 30도 이상이고 에어컨이 꺼져 있으면, 에어컨을 냉방 모드로 켜고 메인 사이렌을 긴급 모드로 울려줘.": lambda tl: _replace_call(tl, "Switch.On", [_call("Switch.On"), _call("AirConditioner.SetAirConditionerMode", Mode="cool")]),   # A4
    "이산화탄소가 1500ppm 이상이고 블라인드가 닫혀있으면, 공기청정기를 자동 모드로 켜고 블라인드를 올려줘.": lambda tl: _replace_call(tl, "AirPurifier.SetAirPurifierMode", [_call("Switch.On"), _call("AirPurifier.SetAirPurifierMode", Mode="auto")]),
    "20초마다 부엌 라이트를 toggle 해줘. 8번만.": lambda tl: _replace_call(tl, "Light.MoveToBrightness", [_call("Switch.Toggle")]),                                                # 토글 = Switch.Toggle
    "비가 오고 문이 잠겨 있지 않으면, 문을 잠그고 제습기를 건조 모드로 설정해줘.": lambda tl: _replace_call(tl, "Dehumidifier.SetDehumidifierMode", [_call("Dehumidifier.SetDehumidifierMode", Mode="drying")]),   # 건조 = drying
    "오후 1시부터 3시까지 5분마다 벨브를 열었다 닫았다 반복해줘.": lambda tl: [tl[0], {**tl[1], "body": [{"op": "if", "cond": "n % 2 == 0", "then": [tl[1]["body"][0]], "else": [tl[1]["body"][1]]}]}],   # 토글 n%2
    "멀티버튼의 버튼3이 눌릴 때마다 주방 조명을 켜고 끄는 것을 반복해줘.": lambda tl: [tl[0], {**tl[1], "body": [tl[1]["body"][0], _call("Switch.Toggle")]}],
}
PERIOD_EDITS = {"오후 6시부터 8시까지 1층에 사람이 감지되면 1층 불을 다 켜줘.": "100 MSEC"}      # 주기 표현 없는 시간창 감시 = 폴링 기본
COND_EDITS = {'Siren.SirenMode != "emergency"': "Switch.Switch == false", "Light.CurrentBrightness > 0": "Switch.Switch == true", "Light.CurrentBrightness == 0": "Switch.Switch == false",   # B3/B4
              "not (PresenceSensor.Presence == true) or PresenceSensor.Presence == false": "PresenceSensor.Presence == false and PresenceSensor.Presence == false",   # "모두 감지되지 않으면" = and
              "WeatherProvider.Pm25Weather >= 2000": "WeatherProvider.Pm10Weather >= 2000"}      # B8 외부 미세먼지 = Pm10
LEVEL_MAP = {"LevelControl.MoveToLevel": "Light.MoveToBrightness", "LevelControl.CurrentLevel": "Light.CurrentBrightness", "ColorControl.SetColor": "Light.MoveToColor"}
def _walk(nodes, fn):
    for n in nodes:
        fn(n)
        for k in ("then", "else", "body"):
            if n.get(k): _walk(n[k], fn)
def gold_fix(cmd, ir):
    """paper gold → 사용자 결정 관례로 정정한 gold"""
    ir = copy.deepcopy(ir); tl = ir["timeline"]
    def no_control(n):                                       # *Control 계열 → 조명 서비스
        if n.get("op") == "call" and n["target"] in LEVEL_MAP:
            n["target"] = LEVEL_MAP[n["target"]]
            if "Level" in n.get("args", {}): n["args"]["Brightness"] = n["args"].pop("Level")
            n["args"] = {k: (v.replace("LevelControl.CurrentLevel", "Light.CurrentBrightness") if isinstance(v, str) else v) for k, v in n.get("args", {}).items()}
        if n.get("op") == "read" and n.get("src") in LEVEL_MAP: n["src"] = LEVEL_MAP[n["src"]]
        if n.get("op") in ("if", "wait") and isinstance(n.get("cond"), str):
            for a, b in LEVEL_MAP.items(): n["cond"] = n["cond"].replace(a, b)
    _walk(tl, no_control)
    if cmd in EDITS: tl = EDITS[cmd](tl)
    def f(n):
        if n.get("op") in ("if", "wait") and isinstance(n.get("cond"), str):
            for a, b in COND_EDITS.items(): n["cond"] = n["cond"].replace(a, b)
        if n.get("op") == "cycle" and n.get("count") == "n":                 # B12: count는 숫자
            m = re.match(r"n >= (\d+)", str(n.get("until") or ""))
            if m: n["count"] = int(m.group(1))
        if cmd in PERIOD_EDITS and n.get("op") == "cycle": n["period"] = PERIOD_EDITS[cmd]
    _walk(tl, f); ir["timeline"] = tl
    return ir

# ── 관례 정규화·동치 ──
EQ_VALUE = {"CarbonDioxideSensor.CarbonDioxide": "AirQualitySensor.CarbonDioxide"}
EQ_COND = {'RobotVacuumCleaner.RobotVacuumCleanerRunMode == "idle"': 'RobotVacuumCleaner.RobotVacuumCleanerCleaningMode == "stop"',
           'DoorLock.DoorLockState != "closed"': 'DoorLock.DoorLockState == "open"', 'DoorLock.DoorLockState != "open"': 'DoorLock.DoorLockState == "closed"'}
def canon_ir(ir):
    """최상위 첫 노드가 wait(edge none, for 없음)이면 if{then: 나머지}와 동치(gold 혼용)"""
    tl = ir["timeline"]
    if len(tl) >= 2 and tl[1].get("op") == "wait" and tl[1].get("edge", "none") == "none" and not tl[1].get("for"):
        return {"timeline": [tl[0], {"op": "if", "cond": tl[1]["cond"], "then": tl[2:], "else": []}]}
    return ir
def norm_cond(c, reads):
    if not isinstance(c, str): return c
    for var, src in reads.items():
        c = c.replace("$" + var, src)
        if var.startswith("$"): c = c.replace(var, src)
        else: c = re.sub(r"(?<![\w.$])" + re.escape(var) + r"(?![\w.])", src, c)          # gold: read 변수를 $ 없이 씀
    c = re.sub(r"\s+", " ", c.strip())
    c = re.sub(r"\bnot\s+\(([A-Z][A-Za-z]+\.[A-Za-z0-9]+) == true\)", r"\1 == false", c)
    c = re.sub(r"\bnot\s+\(([A-Z][A-Za-z]+\.[A-Za-z0-9]+) == false\)", r"\1 == true", c)
    c = re.sub(r"\bnot\s+([A-Z][A-Za-z]+\.[A-Za-z0-9]+)(?![\w.]|\s*[=<>!])", r"\1 == false", c)
    c = re.sub(r"(\d+)\.0\b", r"\1", c)
    for a, b in EQ_VALUE.items(): c = c.replace(a, b)
    return re.sub(r"^\((\S+ - \S+)\)", r"\1", c)
def flat(nodes, reads=None, acc=None):
    """비교용 평탄화: (op, 슬롯 dict) 목록"""
    reads = {} if reads is None else reads; acc = [] if acc is None else acc
    for n in nodes:
        op = n["op"]
        if op == "read": reads[n["var"]] = n["src"]; continue
        d = {}
        if op == "start_at": d["cron"] = n.get("cron")
        elif op == "call": d["target"] = n["target"]; d["args"] = n.get("args", {})
        elif op == "wait": d["cond"] = norm_cond(n["cond"], reads); d["edge"] = n.get("edge", "none"); d["for"] = n.get("for")
        elif op == "if": d["cond"] = norm_cond(n["cond"], reads)
        elif op == "cycle": d["period"] = n.get("period"); d["until"] = n.get("until"); d["count"] = n.get("count")
        elif op == "delay": d["duration"] = n["duration"]
        acc.append((op, d))
        if op == "if": flat(n["then"], reads, acc); flat(n["else"], reads, acc)
        if op == "cycle": flat(n["body"], reads, acc)
    return acc
def _onoff(t, args):
    if t in ("Switch.On", "Switch.Off"): return t[7:].upper()
    if t == "Light.MoveToBrightness":
        try: b = float(args.get("Brightness"))
        except Exception: return t
        return "ON" if b == 100 else "OFF" if b == 0 else t
    return t
def cmp_args(pa, ga, svc):
    """enum·숫자 인자만 비교(문자열 인자 제외) → (맞은 수, 비교 수)"""
    _, spec = svc_info(svc); ok = tot = 0
    for a in (spec or {}).get("arguments", []):
        if a.get("type") in ("STRING", "BINARY") or a["id"] not in ga: continue
        tot += 1; pv, gv = pa.get(a["id"]), ga[a["id"]]
        try: ok += int(pv is not None and (float(pv) == float(gv) if not isinstance(gv, str) else str(pv) == str(gv)))
        except Exception: ok += int(str(pv) == str(gv))
    return ok, tot
def call_ok(pd, gd):
    """(target 일치, 인자 일치). 동치: 조명 켜기 Switch.On≡MoveToBrightness(100)/끄기≡(0); 같은 카테고리 *Mode 함수 + 같은 enum"""
    pt, gt = pd["target"], gd["target"]
    if pt == gt:
        a, b = cmp_args(pd.get("args", {}), gd.get("args", {}), gt); return True, a == b
    if _onoff(gt, gd.get("args", {})) in ("ON", "OFF") and _onoff(pt, pd.get("args", {})) == _onoff(gt, gd.get("args", {})): return True, True
    if pt.split(".")[0] == gt.split(".")[0] and "Mode" in pt and "Mode" in gt and pd.get("args", {}).get("Mode") is not None and pd["args"].get("Mode") == gd.get("args", {}).get("Mode"): return True, True
    return False, False
def cond_ok(pc, gc, cmd=""):
    for a, b in EQ_COND.items(): pc, gc = pc.replace(a, b), gc.replace(a, b)
    if pc == gc: return True
    if "사람" in cmd:                                                             # Presence ≡ Motion
        f = lambda c: c.replace("MotionSensor.Motion", "PresenceSensor.Presence"); return f(pc) == f(gc)
    return False

def grade(ir, gold, cmd=""):
    """→ ("OK" | 실패 단계 "S"/"T"/"C"/"V"/"A", 슬롯 적중 dict). 구조는 뼈대(skeleton) 비교, 이후 평탄화 노드 짝 비교."""
    ir, gold = canon_ir(ir), canon_ir(gold)
    if skeleton(ir) != skeleton(gold): return "S", {}
    pf, gf = flat(ir["timeline"]), flat(gold["timeline"])
    if len(pf) != len(gf): return "S", {}
    okT = okC = okV = okA = True; slot = {}
    for (po, pd), (go, gd) in zip(pf, gf):
        if po != go: okT = False; continue
        for key in ("cron", "period", "until", "count", "duration", "for", "edge"):
            if key in gd: h = str(pd.get(key)) == str(gd.get(key)); slot.setdefault(key, []).append(h); okT &= h
        if "cond" in gd: h = cond_ok(pd["cond"], gd["cond"], cmd); slot.setdefault("cond", []).append(h); okC &= h
        if "target" in gd:
            h, ah = call_ok(pd, gd); slot.setdefault("target", []).append(h); okV &= h
            if h: slot.setdefault("args", []).append(ah); okA &= ah
    return ("T" if not okT else "C" if not okC else "V" if not okV else "A" if not okA else "OK"), slot
