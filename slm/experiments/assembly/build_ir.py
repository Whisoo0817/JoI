# -*- coding: utf-8 -*-
"""IR 빌더 — 상자 기계(구조) + 슬롯 규칙(값) + 매핑 top-1(서비스) → 실제 timeline IR JSON. 모델 생성 없음.
G/G 조건(gold 경계·타입·mods, 매핑은 ranked.json top-1). 출력 ir_pred.json, 계층 평가:
  S 구조(뼈대) → +T 시간 슬롯(cron/period/until/count/duration/for/edge) → +C 조건식 → +V 서비스 → +A 인자(enum·숫자; 문자열 인자는 제외)
"""
import json, os, sys, re, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
sys.path.insert(0, ROOT)
os.environ.setdefault("SLOT", "1")
from box import Box, assemble_tree, MODE_ON_RE, PULSE_RE, TOGGLE_RE, TOGGLE_ONOFF_RE, SPLIT_TOGGLE_RE, SPLIT_TOGGLE2_RE, MODE_TEMP_RE, ELSE_SPLIT
from skeleton import skeleton, canon
import slots
import rerank
from loader import SERVICE_DATA
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
if os.environ.get("EXTRA", "1") == "1":   # paper 재작성 명령 29개(기기 교체분, 직접 라벨) 포함
    T = T + json.load(open(os.path.join(HERE, "..", "type", "type_labels_extra.json")))
R = json.load(open(os.path.join(HERE, "..", "map", "ranked.json")))
NO_CAT = ("ColorControl", "LevelControl", "RotaryControl")   # 사용자 결정: *Control 계열은 연결 기기 카테고리·스킬에서 제외
RC = {r["cmd"] for r in R}
MAP = {(r["cmd"], s["j"]): [x for x in s["ranked"] if x.split(".")[0] not in NO_CAT] for r in R for s in r["segs"]}
import pandas as pd
_P = pd.read_csv(os.path.join(HERE, "..", "map", "dataset_paper.csv"))
PAPER_GT = {r.command_kor: json.loads(r.ir_gt) for r in _P.itertuples() if isinstance(r.ir_gt, str)}   # 카탈로그 정합 gold (매핑과 같은 버전)
import gold_fix
def gold_of(o):
    g = PAPER_GT.get(o["cmd"], o["ir_gt"]) if os.environ.get("GOLD", "paper") == "paper" else o["ir_gt"]
    return gold_fix.fix(o["cmd"], g) if os.environ.get("GOLD_FIX", "1") == "1" else g

def svc_info(svc):
    """서비스 → (kind, spec) — value(values 항목) 또는 function(functions 항목)"""
    if not svc or "." not in svc: return None, None
    cat, name = svc.split(".", 1); d = SERVICE_DATA.get(cat)
    if not d: return None, None
    for v in d.get("values", []):
        if v["id"] == name: return "value", v
    for f in d.get("functions", []):
        if f["id"] == name: return "function", f
    return None, None
def members_of(cat, fmt):
    return SERVICE_DATA.get(cat, {}).get("enums_map", {}).get(fmt, [])

def top(cmd, j, want=None):
    ranked = MAP.get((cmd, j), [])
    for s in ranked:
        k, _ = svc_info(s)
        if want is None or k == want: return s
    return ranked[0] if ranked else None

AL = json.load(open(os.path.join(ROOT, "mapping_v2", "category_aliases.json")))["aliases"]
EFF = {s["svc"]: s for s in json.load(open(os.path.join(ROOT, "mapping_v2", "effects.json")))["services"]}
def _bigrams(t):
    t = re.sub(r"[\s.,]", "", t); return {t[i:i + 2] for i in range(len(t) - 1)}
def _lex_score(part, svc):
    cat = svc.split(".")[0]
    doc = " ".join(AL.get(cat, []) + EFF.get(svc, {}).get("ko_triggers", []) + [cat])
    return len(_bigrams(part) & _bigrams(doc))
CONJ_SPLIT = re.compile(r"(?<=[가-힣])(고|거나|이고|이거나|며|이며|는데|은데)[,\s]+(?!있|않|없)")
CP_PATH = os.path.join(HERE, "..", "map", "cond_parts.json")
CP = json.load(open(CP_PATH)) if os.path.exists(CP_PATH) and os.environ.get("COND_PARTS", "1") == "1" else {}
TRACE = []          # 선택 기록 [(kind, text, cands, chosen, margin)] — 객관식 선택기 실험용
OVERRIDE = {}       # (kind, text) → 강제 선택(객관식 결과 주입)
def _choose(kind, text, cands, sc):
    order = sorted(range(len(cands)), key=lambda k: -sc[k])
    margin = sc[order[0]] - (sc[order[1]] if len(order) > 1 else -99)
    ch = OVERRIDE.get((kind, text), cands[order[0]])
    TRACE.append((kind, text, list(cands), cands[order[0]], margin)); return ch
def pick_value(text, vals, norank=False):
    """값 서비스 후보(순위순) → 어휘 중복·순위·재정렬 보너스로 top-1. norank: 질의에 속성 명사가 없어 검색 순위가 무의미할 때(숫자뿐인 부분) 순위 감점 생략"""
    bon, extra = rerank.value_bonus(text, vals); vals = list(vals) + [e for e in extra if svc_info(e)[0] == "value"]
    if not vals: return None
    W = float(os.environ.get("LEXW", "1.0"))
    return _choose("value", text, vals, [W * _lex_score(text, vals[k]) - (0 if norank else k) + bon.get(vals[k], 0) for k in range(len(vals))])

FILLER_PART = re.compile(r"^(그리고|그리|그렇지 않고|그렇지 않|그렇지 않으면|아니면|아니면서|그게 아니고|그 외에는|그리고 나서|또는|그때부터|그 이후로|그 뒤로|이후)(이면|면)?[,\s]*$")
def cond_expr(cmd, j, text, mixed=False):
    if mixed and "," in text: text = text.rsplit(",", 1)[-1].strip()      # COND/mixed("등을 100%로, 500lux 이상이면") → 조건은 쉼표 뒤
    e = _cond_expr(cmd, j, text)
    if " and " in e or " or " in e or not rerank.ON: return e
    if re.search(r"(과|와|랑|및) .*(모두|둘 다|전부)", text): return f"{e} and {e}"          # "거실과 침실 모두 X" = 같은 조건 두 기기
    if re.search(r"(이나|나|또는) .*(한 곳이라도|하나라도|중 )", text) or re.search(r"\S+(이나|거나) \S+(이|가|은|는)? ?(열|닫|켜|꺼|잠)", text): return f"{e} or {e}"
    return e
SEGTXT = {(o["cmd"], s["j"]): s["text"] for o in T for s in o["segments"]}
NUM_ONLY = re.compile(r"^[\d.,%\s]+[가-힣]{0,2}\s*(이상|이하|미만|초과|넘으면|넘게|밑이면|아래면|이면|되면)[가-힣]{0,3}[,.]?$")
def _time_only_part(p):
    """조건 부분이 시각 표현뿐("야간(오후 10시)이 되면")이면 cron으로 이미 처리 → 조건에서 제외"""
    return slots._hour(p) is not None and not re.search(r"(온도|습도|농도|밝기|센서|감지|이상|이하|미만|초과|보다|동안|넘)", p)
def _cond_expr(cmd, j, text):
    """조건 절 → '속성 op 값' 문자열. 절 안에 접속어미로 묶인 복합 조건이면 부분별로 값 서비스를 배정해 and/or 결합.
    COND_PARTS=1이면 부분 단위 재질의 결과(cond_parts.json: 조인 필터 + 조건 지시문)를 값 서비스로 사용."""
    cp = CP.get(cmd, {}).get(str(j))
    if cp:
        cp = [x for x in cp if not FILLER_PART.match(x["part"])] or cp     # "그리고"/"그렇지 않고" 같은 접속 부분은 조건이 아님
        cp = [x for x in cp if not _time_only_part(x["part"])] or cp
        cp = [{**x, "part": text} if text in x["part"] and x["part"] != text else x for x in cp]   # mixed 절: 부분 텍스트를 잘라낸 조건으로
        conns = CONJ_SPLIT.findall(text)
        def _ctx(part):   # 부분이 숫자 비교뿐("200 이상이면")이면 속성 명사는 앞 절("미세먼지 농도를 체크해서")에 있음 → 앞 절 텍스트를 선택 문맥으로
            if not NUM_ONLY.match(part.strip()): return part
            ks = [k for k in range(j) if re.search(r"체크|확인|측정|모니터|살펴|재서|재고", SEGTXT.get((cmd, k), ""))] or list(range(j))
            prev = " ".join(SEGTXT.get((cmd, k), "") for k in ks)
            return (prev + " " + part) if prev else part
        exprs = [_one_cond(pick_value(_ctx(x["part"]), [s_ for s_ in x["ranked"] if svc_info(s_)[0] == "value"], norank=NUM_ONLY.match(x["part"].strip()) is not None), x["part"]) for x in cp]
        out = exprs[0]
        for k, e in enumerate(exprs[1:]):
            out += (" or " if k < len(conns) and conns[k] in ("거나", "이거나") else " and ") + e
        return out
    parts = [p for p in CONJ_SPLIT.split(text) if p and p not in ("고", "거나", "이고", "이거나", "며", "이며", "는데", "은데")]
    if len(parts) >= 2:
        conns = CONJ_SPLIT.findall(text)
        vals = [s_ for s_ in MAP.get((cmd, j), []) if svc_info(s_)[0] == "value"]
        used = set(); exprs = []
        for k, part in enumerate(parts):
            best = max([s_ for s_ in vals if s_ not in used] or vals or [None], key=lambda s_: _lex_score(part, s_) if s_ else -1)
            if best: used.add(best)
            exprs.append(_one_cond(best, part + ("면" if not re.search(r"(면|때)[,.]?$", part) else "")))
        out = exprs[0]
        for k, e in enumerate(exprs[1:]):
            out += (" or " if k < len(conns) and conns[k] in ("거나", "이거나") else " and ") + e
        return out
    vals = [s_ for s_ in MAP.get((cmd, j), []) if svc_info(s_)[0] == "value"]
    return _one_cond(pick_value(text, vals), text)

def _one_cond(svc, text):
    if not svc: return "?"
    k, spec = svc_info(svc); cat = svc.split(".")[0]
    vt = spec.get("type") if spec else None
    cv = rerank.value_conv(svc, text)
    if cv and (vt not in ("DOUBLE", "INT", "INTEGER", "FLOAT", "LONG") or slots.comparator(text) is None
               or not re.search(r"이상|이하|미만|초과|넘|보다|떨어|올라|아래|밑", text)): return f"{svc} {cv}"
    if vt in ("DOUBLE", "INT", "INTEGER", "FLOAT", "LONG"):
        c = slots.comparator(text)
        if c: 
            v = rerank.unit_scale(svc, text, c[1]); v = int(v) if float(v).is_integer() else v
            r = slots.range_comparator(text)                          # "20도 이상, 30도 미만이면" → 두 비교의 and
            if r: return " and ".join(f"{svc} {op} {int(x) if float(x).is_integer() else x}" for op, x in r)
            return f"{svc} {c[0]} {v}"
        return f"{svc} == ?"
    if vt == "BOOL": return f"{svc} == {slots.bool_state(text, 'BOOL', [])}"
    if vt == "ENUM":
        v = slots.bool_state(text, "ENUM", members_of(cat, spec.get("format")))
        return f"{svc} == {v if v else '?'}"
    if vt == "STRING":                                                # 문자열 값 조건: 따옴표 값 → 관례 영문(가족→family) 또는 그대로
        q = slots.quoted(text)
        if q: return f'{svc} == "{slots.STRING_KO.get(q.strip(), q.strip())}"'
    return f"{svc} == ?"

POS = {"open": r"열|개방|풀|해제", "close": r"닫|잠|차단", "on": r"켜|작동|시작|틀어|가동", "off": r"꺼|끄|중지|멈|정지|소등", "up": r"올리|올려|높이|높여|키워|증가|더", "down": r"내리|내려|낮추|낮춰|줄|감소"}
NAME_POL = {"open": ["Open", "Unlock", "UpOrOpen"], "close": ["Close", "Lock", "DownOrClose"], "on": ["On", "Start", "Play", "TurnOn"], "off": ["Off", "Stop", "Pause", "TurnOff"], "up": ["Up", "Increase", "Raise", "AddMore"], "down": ["Down", "Decrease", "Lower"]}
def cat_of(s_): return s_.split(".")[0]
def pick_function(cmd, j, text):
    """top-5 함수 후보 중 형제 서비스(Open/Close, On/Off, Up/Down, Set vs Step) 극성·숫자 규칙으로 선택."""
    cands = [s_ for s_ in MAP.get((cmd, j), []) if svc_info(s_)[0] == "function"]
    for jj in list(range(j - 1, -1, -1)) + list(range(j + 1, j + 4)):      # 절에 함수 후보가 없으면(mixed·else 분기 절) 이웃 절 후보를 빌림
        if cands: break
        cands = [s_ for s_ in MAP.get((cmd, jj), []) if svc_info(s_)[0] == "function"]
    bon, extra = rerank.func_bonus(text, cands); n0 = len(cands); cands = cands + [e for e in extra if svc_info(e)[0] == "function"]
    if not cands: return None
    pol = [p for p, rx in POS.items() if re.search(rx, text)]
    has_num = slots.number(text) is not None
    def score(k, s_):
        name = s_.split(".", 1)[1]; sc = -(k if k < n0 else 1) + bon.get(s_, 0)      # 규칙 추가 후보는 순위 벌점 1
        for p in pol:
            if any(name.startswith(w) or name.endswith(w) for w in NAME_POL[p]): sc += 3
            opp = {"open": "close", "close": "open", "on": "off", "off": "on", "up": "down", "down": "up"}[p]
            if any(name.startswith(w) or name.endswith(w) for w in NAME_POL[opp]): sc -= 3
        spec = svc_info(s_)[1]; nargs = [a for a in spec.get("arguments", []) if a.get("type") in ("DOUBLE", "INT", "INTEGER", "FLOAT", "LONG")]
        if has_num and nargs and name.startswith(("Set", "MoveTo")): sc += 2
        if "Mode" in name and rerank.ON:                                     # A14: 해당 enum 멤버가 있는 Mode 함수 우선
            for a in spec.get("arguments", []):
                if a.get("type") == "ENUM": sc += 2 if slots.enum_arg(text, members_of(cat_of(s_), a.get("format"))) else -1
        if not has_num and name.startswith(("Set", "MoveTo")) and nargs and not spec.get("arguments", [{}])[0].get("type") == "ENUM" and not re.search(r"켜|꺼|끄|최대|최소", text): sc -= 1
        return sc
    return _choose("func", text, cands, [score(k, s_) for k, s_ in enumerate(cands)])

STEP_ATTR = {"Brightness": "Light.CurrentBrightness", "Volume": "Speaker.Volume", "TargetTemperature": "AirConditioner.TargetTemperature", "Temperature": "AirConditioner.TargetTemperature", "Level": "WindowCovering.CurrentPosition"}
COLOR_XY = {"red": (0.675, 0.322), "blue": (0.167, 0.04), "green": (0.409, 0.518), "white": (0.3127, 0.329), "yellow": (0.444, 0.517), "orange": (0.556, 0.408), "purple": (0.272, 0.109), "pink": (0.38, 0.19)}   # gold 관례(빨강·파랑 gold 값, 나머지 CIE 근사)
TOGGLE_VERB = {r"열었다|열고 닫|개방": ("열어줘", "닫아줘"), r"올렸다|올리고 내": ("올려줘", "내려줘"), r"잠갔다|잠궜다": ("잠가줘", "열어줘"), r"켰다|켜고 끄": ("켜줘", "꺼줘")}
def call_node(cmd, j, text, force=None, hint=None):
    if hint == "on": text = text + " 켜줘"          # 토글 첫 호출 = 켜기, 둘째 = 끄기 (극성 힌트)
    if hint == "off": text = text + " 꺼줘"
    svc = force or pick_function(cmd, j, text)
    if not svc: return {"op": "call", "target": "?", "args": {}}
    k, spec = svc_info(svc); cat = svc.split(".")[0]; args = {}
    for a in spec.get("arguments", []):
        aid, at = a["id"], a.get("type")
        if at == "ENUM":
            v = slots.enum_arg(text, members_of(cat, a.get("format")))
            if v: args[aid] = v
        elif at in ("DOUBLE", "INT", "INTEGER", "FLOAT", "LONG"):
            st = re.search(r"(\d+)\s*(도|%)?\s*(씩|만큼|단위씩|단위로|)\s*(높여|올려|키워|낮춰|내려|줄여|늘려|늘리|올리|증가|줄이|감소|밝게|어둡게|키우|낮추|내리|높이)", text); lim = re.search(r"(최대|최소|최저|최고)\s*(\d+)", text)   # "2도 낮춰줘"(씩 없이 상대 동사)도 단계
            if re.search(r"최대 밝기", text) and st: lim = re.match(r"(최대)\s*(100)", "최대 100")
            if st and rerank.ON and aid in STEP_ATTR:            # A11: "10씩 높여줘. 최대 100까지" → min($Light.CurrentBrightness + 10, 100)
                up = st.group(4) in ("높여", "올려", "키워", "늘려", "늘리", "올리", "증가", "밝게", "키우", "높이"); n_ = st.group(1); attr = STEP_ATTR[aid]
                if lim: args[aid] = f"{'min' if up else 'max'}(${attr} {'+' if up else '-'} {n_}, {lim.group(2)})"
                else: args[aid] = f"${attr} {'+' if up else '-'} {n_}"
                continue
            if aid == "Brightness":
                m = re.search(r"(\d+)\s*(%|퍼센트|으로|로|까지)", text)
                if m: v = float(m.group(1))
                elif re.search(r"켜|최대|밝게", text): v = 100.0
                elif re.search(r"꺼|끄|소등", text): v = 0.0
                else: v = None
                if v is not None: args[aid] = v
            elif aid == "Hue":
                m = re.search(r"색조\D{0,6}(\d+)", text)
                if m: args[aid] = int(m.group(1))
            elif aid == "Saturation":
                m = re.search(r"채도\D{0,6}(\d+)", text)
                if m: args[aid] = int(m.group(1))
            elif aid in ("ColorX", "ColorY"):
                col = slots.enum_arg(text, [f"{k} - " for k in COLOR_XY])
                if col: args[aid] = COLOR_XY[col][0 if aid == "ColorX" else 1]
            elif aid == "Rate": args[aid] = 0.0
            elif aid == "TransitionTime": args[aid] = 0.0
            else:
                n = slots.number(text)
                if n is None and aid == "Volume" and re.search(r"최대|끝까지", text): n = 100
                if n is None and aid == "Volume" and re.search(r"최소|음소거", text): n = 0
                if n is not None and aid == "Duration":                    # Duration은 초 단위: "5분짜리" → 300
                    mu = re.search(rf"{int(n) if float(n).is_integer() else n}\s*(분|시간)", text)
                    if mu: n = n * (60 if mu.group(1) == "분" else 3600)
                if n is not None: args[aid] = int(n) if at in ("INT", "INTEGER", "LONG") else float(n)
        else:
            q = slots.quoted(text)
            if q: args[aid] = q
    return {"op": "call", "target": svc, "args": args}

def slot_mods(t, text, mods):
    """슬롯 주도 mods 보강(예측 mods 누락 대비): time(시각·주기·시간창), sustain(N분 이상 지속), every(때마다), repeat(토글/반복), count(N번)"""
    m = set(mods)
    if t != "STOP" and (slots.cron(text) or slots.period(text) or slots.until(text)): m.add("time")
    if t in ("COND", "TRIG") and re.search(r"\d+\s*(초|분|시간)\s*(이상|넘게|동안|째)", text) and "sustain" not in m: m.add("sustain")
    if t == "TRIG" and re.search(r"때마다", text): m.add("every")
    if t == "ACT" and (TOGGLE_RE.search(text) or re.search(r"반복", text)): m.add("repeat")
    if t in ("ACT", "STOP") and slots.count(text) is not None: m.add("count")
    return sorted(m)
sys.path.insert(0, os.path.join(HERE, "..", "graph"))
from normalize import normalize as graph_normalize
LAST_GRAPH = {}
_HS = {}
def _attach_h6(o, S):
    """원본 382 명령은 head/states.npz(층 6, 절 끝 단어)에서 절 벡터를 붙임. 이미 h6가 있으면 그대로."""
    if all("h6" in s for s in S): return S
    if "X" not in _HS:
        try:
            H = np.load(os.path.join(HERE, "..", "head", "states.npz")); _HS["X"] = H["X"]; _HS["L"] = list(H["layers"]).index(6)
            _HS["row"] = {(int(c), int(w)): r for r, (c, w) in enumerate(zip(H["cmd_idx"], H["word_pos"]))}
        except Exception: _HS["X"] = None
    if _HS["X"] is None or o.get("source"): return S
    out = []; k = 0
    for s in S:
        k += len(s["text"].split()); r = _HS["row"].get((o["i"], k - 1))
        if r is None: return S
        out.append({**s, "h6": _HS["X"][r, _HS["L"]].astype(np.float32).tolist()})
    return out
COUNT_ONLY = re.compile(r"^(그리고 |그렇게 |이걸 )?(모두|전부|총|딱|최대)?\s*(\d+|[일이삼사오육칠팔구십]+)\s*(번|회|차례)\s*(만|까지|까지만|반복)?(요|만요|이요|해줘|이야|이에요)?[.!]?$")
SPLIT_TG1 = re.compile(r"(켜고|열고|올리고|내리고|닫고|잠그고)[,.]?\s*$"); SPLIT_TG2 = re.compile(r"^(끄|닫|내리|올리|열|잠그)(는|기)\s*(것을|걸|를)?\s*(반복|번갈아)")
SUSTAIN_ONLY = re.compile(r"^(그\s*상태로|그대로|그 상태가)?\s*(\d+|[일이삼사오육칠팔구십한두세네]+)\s*(초|분|시간)\s*(이상|넘게|넘도록|동안|째)\s*(이어지면|지속되면|계속되면|유지되면|계속이면|간다면|가면|지나면|되면)[.,]?$")
TIME_TOK = re.compile(r"(오전|오후|아침|저녁|밤|새벽|낮|정오|자정|야간|매일|평일|주말|월요일|화요일|수요일|목요일|금요일|토요일|일요일|\d+\s*시(\s*\d+\s*분)?|\d+\s*분|\d+\s*초|한|두|세|부터|까지|사이에|에는|에서|에|가|이|되면|됐을|되었을|될|때|이면|면|\(|\)|,|\.)")
def _time_only_seg(t):
    """시각 표현·조사·"되면/때"만 남는 절 ("오후 10시가 됐을 때", "밤 10시에")"""
    return slots._hour(t) is not None and TIME_TOK.sub("", t).strip() == ""
def seg_fix(S):
    """표면 규칙 일반형(§28.2): (a) 수량만 있는 꼬리 절("모두 5번만요")은 STOP/count로 (b) 시각뿐인 COND/TRIG("오후 10시가 됐을 때")는 TIME으로
    (c) 조건 절 + "N분 넘게 이어지면"(지속만) 두 절 → 한 조건 절(sustain) (d) "…올리고 ‖ 내리기를 반복" 두 행동 절 → 한 토글 절"""
    out = []
    for s in S:
        t = s["text"].strip()
        if s["type"] == "ACT" and COUNT_ONLY.match(t): out.append({**s, "type": "STOP", "mods": sorted(set(s["mods"]) | {"count"})}); continue
        if s["type"] in ("COND", "TRIG") and _time_only_seg(t): out.append({**s, "type": "TIME", "mods": sorted(set(s["mods"]) | {"time"})}); continue
        if out and s["type"] == "COND" and SUSTAIN_ONLY.match(t) and out[-1]["type"] in ("COND", "TRIG"):
            p = out[-1]; out[-1] = {**p, "text": p["text"].rstrip(",. ") + " " + t, "mods": sorted(set(p["mods"]) | {"sustain"})}; continue
        if out and s["type"] == "ACT" and out[-1]["type"] == "ACT" and SPLIT_TG1.search(out[-1]["text"]) and SPLIT_TG2.match(t):
            p = out[-1]; out[-1] = {**p, "text": p["text"].rstrip(", ") + " " + t, "mods": sorted(set(p["mods"]) | set(s["mods"]) | {"repeat"})}; continue
        out.append(s)
    return out
def build(o):
    cmd = o["cmd"]; S = o["segments"]
    if os.environ.get("SLOT_MODS", "1") == "1":
        S = [{**s, "mods": slot_mods(s["type"], s["text"], s["mods"])} for s in S]
    if os.environ.get("SEGFIX", "1") == "1" and len(S) >= 2: S = seg_fix(S)
    GD = None
    if os.environ.get("GRAPH", "1") == "1" and len(S) >= 2:
        S = _attach_h6(o, S)
        S, GD = graph_normalize(S)                                # §23–24 파서 head: 필러 탈락·참조 이동·후치 범위 절 앞으로
        if GD: LAST_GRAPH[cmd] = GD
    if os.environ.get("POSTPOSE", "1") == "1" and len(S) >= 2 and not (GD and (GD["moved"] or GD["drop"])):
        # 후치 절 이동: 마지막 ACT 뒤에 오는 COND/TRIG/TIME 절("…해줘, …이면.")은 문두 위치의 조건·시각 → 앞으로 옮김(그래프 파서의 후치 처리 간이판)
        last_act = max((i for i, s in enumerate(S) if s["type"] == "ACT"), default=-1)
        tail = [s for s in S[last_act + 1:] if s["type"] in ("COND", "TRIG", "TIME")] if last_act >= 0 else []
        if tail and len(tail) == len(S) - last_act - 1 and any(s["type"] in ("COND", "TRIG", "TIME") for s in S[:last_act + 1]) is False:
            S = tail + S[:last_act + 1]
    OJ = [s.get("j", k) for k, s in enumerate(S)]           # 재배열 후에도 매핑(MAP/CP)은 원래 절 번호로 조회
    segs3 = [(s["type"], s["mods"], s["text"]) for s in S]
    root = assemble_tree(segs3, False, [])
    # 배치된 절 집합(상자 머리 + 잎 소유자)
    placed = set()
    def collect(b):
        if b.seg is not None: placed.add(b.seg)
        for x in b.items + (b.else_items or []):
            if isinstance(x, Box): collect(x)
            else: placed.add(b.owner[id(x)])
    collect(root)
    def merged_text(seg):
        """조건 상자 머리 절 + 뒤따르는 미배치 COND/TRIG 절 → (표현, 절 목록)"""
        js = [seg]; k = seg + 1
        while k < len(S) and S[k]["type"] in ("COND", "TRIG") and k not in placed and "sustain" not in S[k]["mods"]:
            if not FILLER_PART.match(S[k]["text"].strip()): js.append(k)
            k += 1
        parts = [cond_expr(cmd, OJ[j], S[j]["text"], mixed="mixed" in S[j]["mods"]) for j in js]
        joiner = " or " if any(re.search(r"거나|또는|이거나", S[j]["text"]) for j in js[:-1]) else " and "
        return joiner.join(parts)
    # 시각(cron)은 모든 절에서 찾는다(첫 time 절만 보던 규칙 폐기): 시각이 있는 절 우선, 그다음 요일·날짜만 있는 절
    cr = None
    for s in S:
        if s["type"] == "STOP": continue
        c = slots.cron(s["text"])
        if c and (slots._hour(s["text"]) or re.search(r"크리스마스|새해|정오|자정", s["text"])): cr = c; break
    if cr is None:
        for s in S:
            c = slots.cron(s["text"]) if s["type"] != "STOP" else None
            if c: cr = c; break
    tl = [{"op": "start_at", "anchor": "cron" if cr else "now", **({"cron": cr} if cr else {})}]
    counter = [0]; ncall = collections.Counter()
    def conv(b, out):
        for x in b.items:
            if isinstance(x, Box):
                if x.kind == "IF":
                    if x.seg is not None and S[x.seg]["type"] in ("COND", "TRIG"): cond = merged_text(x.seg)
                    elif x.seg is not None and S[x.seg]["type"] == "STOP": cond = cond_expr(cmd, OJ[x.seg], S[x.seg]["text"])
                    elif x.seg is not None and S[x.seg]["type"] == "ACT" and TOGGLE_RE.search(S[x.seg]["text"]) and rerank.ON: cond = "n % 2 == 0"
                    elif x.seg is not None and S[x.seg]["type"] == "ACT" and "mixed" in S[x.seg]["mods"] and rerank.ON:
                        # ACT/mixed 뒤 STOP: "최대 밝기가 되면 그만해" → 절 뒷부분 조건 (값 서비스는 그 절의 후보에서)
                        tail = re.split(r"[.!] ", S[x.seg]["text"])[-1]
                        if re.search(r"최대 밝기", tail): cond = "Light.CurrentBrightness >= 100"
                        elif re.search(r"최소 밝기", tail): cond = "Light.CurrentBrightness <= 0"
                        else: cond = _cond_expr(cmd, OJ[x.seg], tail)
                    else: cond = "?"
                    if x.seg is not None and rerank.ON and re.search(r"(떨어졌|올랐|내려갔|올라갔|변했|차이)", S[x.seg]["text"]) and any(n.get("op") == "read" for n in out):
                        # B14: "확인하고 … 다시 확인해서 M 이상 떨어졌으면" → 두 번째 읽기 + 차이 조건
                        prev = [n for n in out if n.get("op") == "read"][-1]; counter[0] += 1; v2 = f"v{counter[0]}"
                        out.append({"op": "read", "var": v2, "src": prev["src"]})
                        c = slots.comparator(S[x.seg]["text"]); op_, val = (c[0], c[1]) if c else (">=", "?")
                        val = int(val) if isinstance(val, float) and val.is_integer() else val
                        down = re.search(r"떨어졌|내려갔", S[x.seg]["text"])
                        if re.search(r"차이", S[x.seg]["text"]): cond = f"abs(${prev['var']} - ${v2}) {op_} {val}"
                        else: cond = f"${prev['var']} - ${v2} {op_} {val}" if down else f"${v2} - ${prev['var']} {op_} {val}"
                    node = {"op": "if", "cond": cond, "then": [], "else": []}
                    conv(x, node["then"])
                    if x.else_items is not None:
                        tmp = Box("ROOT"); tmp.items = x.else_items; tmp.owner = x.owner; conv(tmp, node["else"])
                    out.append(node)
                elif x.kind == "CYC":
                    txt = S[x.seg]["text"] if x.seg is not None else ""
                    if rerank.ON and cr and re.match(r"^\d+ (\*|\*/\d+) ", cr) and slots.period(txt) and "시간" in txt:
                        conv(x, out); continue                        # "주말에 2시간마다" = cron 시 step이 주기를 흡수 → cycle 없음
                    per = slots.period(txt) or ("100 MSEC" if S[x.seg]["type"] == "TRIG" and "every" in S[x.seg]["mods"] else None)
                    # count: 상자 머리 절 또는 STOP/count·ACT/count 절
                    cnt = slots.count(txt)
                    for j, s in enumerate(S):
                        if cnt is None and ("count" in s["mods"] or s["type"] == "STOP"): cnt = slots.count(s["text"])
                    unt = slots.until(txt) or (f"n >= {cnt}" if cnt else None)
                    if rerank.ON and per is None and unt and any(isinstance(y, Box) and y.kind == "IF" for y in x.items): per = "100 MSEC"   # 시간창 + 조건 = 폴링
                    node = {"op": "cycle", "until": unt, "period": per, "body": []}
                    if cnt: node["count"] = cnt
                    elif rerank.ON and unt is None and any(isinstance(y, Box) and y.kind == "IF" and y.seg is not None and S[y.seg]["type"] == "ACT" and TOGGLE_RE.search(S[y.seg]["text"]) for y in x.items): node["count"] = "n"   # 토글: n%2 (until 있으면 count 생략 = gold 표기)
                    conv(x, node["body"]); out.append(node)
            else:
                j = b.owner[id(x)]; s = S[j]; leaf = str(x)
                if leaf == "CALL":
                    ncall[j] += 1
                    force = None
                    if rerank.ON and MODE_ON_RE.search(s["text"]) and ncall[j] == 1: force = "Switch.On"          # A4 첫 호출 = 켜기
                    elif rerank.ON and MODE_TEMP_RE.search(s["text"]):                                          # "냉방 모드로 18도로": 1=Mode 2=TargetTemperature
                        fs = [f for f in MAP.get((cmd, OJ[j]), []) if svc_info(f)[0] == "function"]
                        want = [f for f in fs if ("Mode" in f) == (ncall[j] == 1) and ("Temperature" in f) == (ncall[j] == 2)]
                        if want: force = want[0]
                    elif rerank.ON and PULSE_RE.search(s["text"]) and ncall[j] == 2: force = "Switch.Off"          # 펄스 두 번째 CALL = 끄기
                    hint = None; txt = s["text"]
                    if rerank.ON and TOGGLE_RE.search(txt) and TOGGLE_ONOFF_RE.search(txt): force = "Switch.Toggle"     # 켜고 끄기 = Switch.Toggle 한 호출
                    elif rerank.ON and SPLIT_TOGGLE_RE.search(txt) and j + 1 < len(S) and SPLIT_TOGGLE2_RE.match(S[j + 1]["text"]): force = "Switch.Toggle"
                    elif rerank.ON and TOGGLE_RE.search(txt):
                        mm = re.search(r"(\S+?)(와|과|이랑|랑) (\S+?)(을|를|으로|로)? ?(사이에서|번갈아)", txt)
                        if mm: txt = txt[:mm.start()] + (mm.group(1) if ncall[j] == 1 else mm.group(3)) + "으로 " + txt[mm.end():]   # "A와 B 사이에서 전환" → 1번째 A, 2번째 B
                        else:
                            pair = next((v for k_, v in TOGGLE_VERB.items() if re.search(k_, txt)), ("켜줘", "꺼줘"))
                            txt = re.sub(r"\d+\s*(초|분|시간)\s*(마다|간격으로|씩)", "", TOGGLE_RE.sub("", txt)) + " " + pair[0 if ncall[j] == 1 else 1]        # "열었다 닫았다" → 열어줘 / 닫아줘 (주기 숫자는 제거: Set* 오선택 방지)
                    elif rerank.ON and "else" in s["mods"] and ELSE_SPLIT.search(txt):
                        parts = re.split(r"[,\s](?:그 외에는|그 외에|아니면|그렇지 않으면) ", txt, maxsplit=1)
                        txt = parts[min(ncall[j] - 1, len(parts) - 1)] + (" 설정해줘" if ncall[j] == 1 else "")
                    out.append(call_node(cmd, OJ[j], txt, force=force, hint=hint))
                elif leaf == "READ":
                    getf = next((f for f in MAP.get((cmd, OJ[j]), []) if svc_info(f)[0] == "function" and not f.startswith("Speaker.")), None)
                    hasv = top(cmd, OJ[j], "value") is not None
                    param = re.search(r'\d+\s*동|식당|["“]', s["text"]) is not None      # "301동 점심 메뉴"처럼 인자가 필요한 조회
                    if rerank.ON and getf and (not hasv or param) and not re.search(r"온도|습도|조도|농도|상태|값|수치", s["text"]):   # 값 서비스가 있으면 read, 없거나 인자 필요하면 함수 call (사용자 결정: 서비스 종류 따라)
                        out.append(call_node(cmd, OJ[j], s["text"], force=getf))
                    else:
                        counter[0] += 1; out.append({"op": "read", "var": f"v{counter[0]}", "src": top(cmd, OJ[j], "value") or "?"})
                elif leaf == "DELAY": out.append({"op": "delay", "duration": slots.duration(s["text"]) or "?"})
                elif leaf.startswith("WAIT"):
                    node = {"op": "wait", "cond": merged_text(j) if s["type"] in ("COND", "TRIG") else "?", "edge": "rising" if "every" in s["mods"] else "none"}
                    if "sustain" in s["mods"]:
                        d = slots.duration(s["text"]); 
                        if d: node["for"] = d
                    out.append(node)
                elif leaf == "BREAK": out.append({"op": "break"})
    conv(root, tl)
    if rerank.ON:
        _walk_nodes(tl, _collapse_complement)
        if "주말" in " ".join(s["text"] for s in S) and tl and tl[0].get("cron", "").endswith("* * 6,7") and len(tl) > 1 and tl[1].get("op") == "cycle" and tl[1].get("until") is None:
            tl[0]["cron"] = tl[0]["cron"][:-3] + "6"; tl[1]["until"] = 'Clock.Weekday == "monday"'          # "주말 동안/에 N마다" = 토요일 0시 시작, 월요일까지(사용자 결정: 기간은 start+until)
    return {"timeline": tl}

_CMP_INV = {">=": "<", "<": ">=", ">": "<=", "<=": ">"}
def _complement(a, b):
    """같은 속성의 상보 조건: (>= v, < v), (== true, == false) 등"""
    ma = re.fullmatch(r"(\S+) (>=|<=|>|<|==|!=) (\S+)", a or ""); mb = re.fullmatch(r"(\S+) (>=|<=|>|<|==|!=) (\S+)", b or "")
    if not ma or not mb or ma.group(1) != mb.group(1): return False
    if ma.group(3) == mb.group(3) and _CMP_INV.get(ma.group(2)) == mb.group(2): return True
    if ma.group(2) == mb.group(2) == "==" and {ma.group(3), mb.group(3)} == {"true", "false"}: return True
    return False
def _walk_nodes(nodes, fn):
    for n in nodes:
        fn(n)
        for k in ("then", "else", "body"):
            if n.get(k): _walk_nodes(n[k], fn)
def _collapse_complement(n):
    """if A {X} else { if ¬A {Y} } → if A {X} else {Y} (사용자 결정: 상보 조건은 ELSE)"""
    if n.get("op") == "if" and len(n.get("else", [])) == 1 and n["else"][0].get("op") == "if" and not n["else"][0].get("else") and _complement(n["cond"], n["else"][0]["cond"]):
        n["else"] = n["else"][0]["then"]

# ── 평가 ──
def canon_ir(ir):
    """관례 정규화(§20 lenient): 최상위 첫 노드가 wait(edge none, for 없음)이면 if{then: 나머지}와 동치 (gold가 두 표기를 섞어 씀)."""
    tl = ir["timeline"]
    if len(tl) >= 2 and tl[1].get("op") == "wait" and tl[1].get("edge", "none") == "none" and not tl[1].get("for"):
        return {"timeline": [tl[0], {"op": "if", "cond": tl[1]["cond"], "then": tl[2:], "else": []}]}
    return ir
def norm_cond(c, reads):
    if not isinstance(c, str): return c
    for var, src in reads.items(): c = c.replace("$" + var, src).replace(var, src) if var.startswith("$") else c.replace("$" + var, src)
    for var, src in reads.items():                                     # gold 표기 잔여: read 변수를 $ 없이 씀 ("temp >= 30", "h < 50", "currentMode == ...")
        if not var.startswith("$"): c = re.sub(r"(?<![\w.$])" + re.escape(var) + r"(?![\w.])", src, c)
    c = re.sub(r"\s+", " ", c.strip())
    c = re.sub(r"\bnot\s+\(([A-Z][A-Za-z]+\.[A-Za-z0-9]+) == true\)", r"\1 == false", c)                # gold 표기 잔여: "not (X == true)" ≡ "X == false"
    c = re.sub(r"\bnot\s+\(([A-Z][A-Za-z]+\.[A-Za-z0-9]+) == false\)", r"\1 == true", c)
    c = re.sub(r"\bnot\s+([A-Z][A-Za-z]+\.[A-Za-z0-9]+)(?![\w.]|\s*[=<>!])", r"\1 == false", c)          # "not X" ≡ "X == false" (BOOL)
    c = re.sub(r"(\d+)\.0\b", r"\1", c)
    for a, b in EQ_VALUE.items(): c = c.replace(a, b)
    c = re.sub(r"^\((\S+ - \S+)\)", r"\1", c)          # gold 괄호 표기 비일관: "(a - b) >= n" ≡ "a - b >= n"
    return c
def flat(nodes, reads=None, acc=None):
    """비교용 평탄화: (op, 슬롯 dict) 목록 (구조는 이미 뼈대로 비교됨)"""
    reads = reads if reads is not None else {}; acc = acc if acc is not None else []
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

EQ_VALUE = {"CarbonDioxideSensor.CarbonDioxide": "AirQualitySensor.CarbonDioxide"}   # B8: 둘 다 실내 CO2 → 동치
def _onoff(t, args):
    if t == "Switch.On": return "ON"
    if t == "Switch.Off": return "OFF"
    if t == "Light.MoveToBrightness":
        b = args.get("Brightness")
        try: b = float(b)
        except Exception: return t
        return "ON" if b == 100 else ("OFF" if b == 0 else t)
    return t
def call_ok(pd, gd):
    """(target 일치, 인자 일치). 동치: A1/A2 조명 켜기=Switch.On≡MoveToBrightness(100), 끄기=Switch.Off≡MoveToBrightness(0);
    A14 같은 카테고리 *Mode 함수에 같은 enum 값이면 동치."""
    pt, gt = pd["target"], gd["target"]
    if pt == gt:
        a, b = cmp_args(pd.get("args", {}), gd.get("args", {}), gt); return True, a == b
    if _onoff(pt, pd.get("args", {})) == _onoff(gt, gd.get("args", {})) and _onoff(gt, gd.get("args", {})) in ("ON", "OFF"): return True, True
    if pt.split(".")[0] == gt.split(".")[0] and "Mode" in pt and "Mode" in gt and pd.get("args", {}).get("Mode") is not None and pd["args"].get("Mode") == gd.get("args", {}).get("Mode"): return True, True
    return False, False

EQ_COND = {'RobotVacuumCleaner.RobotVacuumCleanerRunMode == "idle"': 'RobotVacuumCleaner.RobotVacuumCleanerCleaningMode == "stop"',   # "멈춰있으면": 두 상태 속성 모두 정답
           'DoorLock.DoorLockState != "closed"': 'DoorLock.DoorLockState == "open"', 'DoorLock.DoorLockState != "open"': 'DoorLock.DoorLockState == "closed"'}   # "잠겨 있지 않으면": 두 표기 동치
def cond_ok(pc, gc, cmd=""):
    """조건식 일치. 사용자 결정: "사람이 감지" 류는 PresenceSensor.Presence ≡ MotionSensor.Motion 둘 다 정답."""
    for a, b in EQ_COND.items(): pc, gc = pc.replace(a, b), gc.replace(a, b)
    if pc == gc: return True
    if "사람" in cmd:
        f = lambda c: c.replace("MotionSensor.Motion", "PresenceSensor.Presence")
        return f(pc) == f(gc)
    return False

def cmp_args(pa, ga, svc):
    """enum·숫자 인자만 비교(문자열 인자 제외). 반환 (맞은 수, 비교 수)"""
    k, spec = svc_info(svc); ok = tot = 0
    for a in (spec or {}).get("arguments", []):
        if a.get("type") in ("STRING", "BINARY"): continue
        if a["id"] not in ga: continue
        tot += 1; pv, gv = pa.get(a["id"]), ga[a["id"]]
        try: ok += int(pv is not None and (float(pv) == float(gv) if not isinstance(gv, str) else str(pv) == str(gv)))
        except Exception: ok += int(str(pv) == str(gv))
    return ok, tot

if __name__ == "__main__":
    out = []; lvl = collections.Counter(); slot = collections.defaultdict(lambda: [0, 0]); n_struct = 0; ex_fail = collections.defaultdict(list)
    MAPPED_ONLY = os.environ.get("MAPPED_ONLY", "0") == "1"
    for o in T:
        if not o["ir_gt"]: continue
        if MAPPED_ONLY and o["cmd"] not in RC: continue
        G = gold_of(o)
        ir = build(o); out.append({"i": o["i"], "cmd": o["cmd"], "ir_pred": ir, "ir_gt": G})
        if os.environ.get("LENIENT", "1") == "1": ir, G = canon_ir(ir), canon_ir(G)
        if skeleton(ir) != skeleton(G): continue
        n_struct += 1
        pf, gf = flat(ir["timeline"]), flat(G["timeline"])
        if len(pf) != len(gf): continue
        okT = okC = okV = okA = True
        for (po, pd), (go, gd) in zip(pf, gf):
            if po != go: okT = False; continue
            for key in ("cron", "period", "until", "count", "duration", "for", "edge"):
                if key in gd:
                    slot[key][1] += 1; hit = str(pd.get(key)) == str(gd.get(key)); slot[key][0] += hit; okT &= hit
                    if not hit and len(ex_fail[key]) < 6: ex_fail[key].append((o["cmd"], pd.get(key), gd.get(key)))
            if "cond" in gd:
                slot["cond"][1] += 1; hit = cond_ok(pd["cond"], gd["cond"], o["cmd"]); slot["cond"][0] += hit; okC &= hit
                ga = re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", gd["cond"]); pa = re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", pd["cond"])
                if ga:
                    slot["cond.attr"][1] += 1; slot["cond.attr"][0] += (sorted(ga) == sorted(pa))
                    if sorted(ga) == sorted(pa): slot["cond.opval|attr"][1] += 1; slot["cond.opval|attr"][0] += hit
                if not hit and len(ex_fail["cond"]) < 10: ex_fail["cond"].append((o["cmd"], pd["cond"], gd["cond"]))
            if "target" in gd:
                slot["target"][1] += 1; hit, ahit = call_ok(pd, gd); slot["target"][0] += hit; okV &= hit
                if hit:
                    slot["args"][0] += ahit; slot["args"][1] += 1; okA &= ahit
                    if not ahit and len(ex_fail["args"]) < 8: ex_fail["args"].append((o["cmd"], pd["args"], gd["args"]))
                elif len(ex_fail["target"]) < 8: ex_fail["target"].append((o["cmd"], pd["target"], gd["target"]))
        lvl["S"] += 1; lvl["S+T"] += okT; lvl["S+T+C"] += okT and okC; lvl["S+T+C+V"] += okT and okC and okV; lvl["S+T+C+V+A"] += okT and okC and okV and okA
    json.dump(out, open(os.path.join(HERE, "ir_pred.json"), "w"), ensure_ascii=False, indent=1)
    N = len(out)
    print(f"명령 {N}: 구조 일치 {n_struct} ({n_struct/N:.3f})")
    for k in ("S", "S+T", "S+T+C", "S+T+C+V", "S+T+C+V+A"): print(f"  누적 완전일치 {k:10s} {lvl[k]:3d}/{N} = {lvl[k]/N:.3f}")
    print("슬롯별 정확도(구조 일치 명령 내):")
    for k, (a, b) in slot.items(): print(f"  {k:8s} {a}/{b} = {a/max(b,1):.3f}")
    for k, v in ex_fail.items():
        print(f"\n[{k} 실패 예]")
        for e in v: print("  ", e)
