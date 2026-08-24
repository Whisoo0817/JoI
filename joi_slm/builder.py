# -*- coding: utf-8 -*-
"""IR 빌더 — 절 목록(타입·mods·텍스트, +매핑 후보) → timeline IR JSON. 모델 생성 없음.
  구조: 상자 규칙(box.py) / 시간·수량 슬롯: slots.py / 서비스 top-1: 매핑 top-5 + 재정렬 규칙(rerank.py) / 인자·조건식: 규칙
입력 매핑(Mapping): 절 j → 서비스 후보 top-5(ranked), 조건 부분 → 값 서비스 후보(parts), 절 텍스트(text).
"""
import re, collections, json
from .box import Box, assemble_tree, MODE_ON_RE, PULSE_RE, TOGGLE_RE, TOGGLE_ONOFF_RE, SPLIT_TOGGLE_RE, SPLIT_TOGGLE2_RE, MODE_TEMP_RE, ELSE_SPLIT
from .catalog import AL, EFF, svc_info, members_of, allowed
from . import slots, rerank
from .graph import normalize as graph_normalize

_ASK = [None, ""]      # [Asker, 전체 문장] — build() 가 채운다. 없으면 규칙만으로 간다.

class Asker:
    """규칙이 못 정한 칸을 2B 1토큰 객관식으로 정한다. 선택지는 카탈로그에서 오므로
    지어낼 길이 없다. 엔진 호출이 실패하면 None — 규칙 결과 그대로 쓴다."""
    def __init__(self, engine): self.engine = engine
    def _choice(self, prompt, letters):
        try: return self.engine.choice(prompt, letters)
        except Exception: return None
    def bool_state(self, cmd, text, svc, desc):
        """조건 절이 가리키는 상황에서 BOOL 값이 참인가 거짓인가. ("내가 집을 나서면" → IsHome 거짓)"""
        p = (f'조건 절: "{text}"\n'
             f'이 절이 가리키는 상황에서 {svc}({desc})의 값은?\n\n'
             f'A. true 인 상황\nB. false 인 상황\n\n답:')
        sc = self._choice(p, "AB")
        return None if sc is None else ("true" if sc[0] > sc[1] else "false")
    def _fill(self, prompt, prefill):
        """빈칸 채우기 한 번 — 답의 첫 낱말. 실패하면 None."""
        try:
            out = self.engine.chat([{"role": "user", "content": prompt}], max_tokens=6, temperature=0, prefill=prefill)[0]
        except Exception:
            return None
        w = re.sub(r'^.*?= ?"?', "", out.strip()).split('"')[0].split()
        return w[0].strip('"., *') if w else None
    def enum_member(self, cmd, text, svc, desc, members):
        """enum 칸에 넣을 멤버 고르기 — 예시 하나 딸린 빈칸 채우기.
        글자 객관식은 선택지가 많으면 2B 가 헤맸고(자연풍→high), 맨몸 질문은 "예보" 같은
        표현에서 무너졌다(비 예보→thunderstorm). 다른 영역의 고정 예시 하나("먼지가 많으면"→dust)를
        붙이니 날씨·선풍기 시험 9/9. ENUM_KO 표는 판정자가 아니라 힌트 — 멤버 옆에 한국어 뜻을 달고,
        답이 한국어로 와도 표를 거꾸로 타서 되받는다."""
        members = [m.split(" - ")[0].strip() for m in members][:20]
        if not members: return None
        def gloss(k):
            ko = slots.ENUM_KO.get(k.lower(), slots.ENUM_KO.get(k, []))
            return f"{k}({ko[0]})" if ko else k
        hint = "세기·모드 말이 없이 그냥 켜거나 돌리라는 문구면 auto.\n" if "auto" in members else ""
        p = (f'문구가 뜻하는 값을 고른다. 값은 다음 중 하나: {", ".join(gloss(m) for m in members)}, 없음\n'
             f'예) "먼지가 많으면" → 값 = "dust"\n{hint}'
             f'문구: "{text}"')
        w = self._fill(p, '→ 값 = "')
        if w in members: return w
        for m in members:                                # 한국어로 답하면 표를 거꾸로 타고 되받는다
            if w and w in slots.ENUM_KO.get(m.lower(), slots.ENUM_KO.get(m, [])): return m
        return None
    def num_value(self, cmd, text, svc, desc):
        """숫자 칸 — 글에 숫자가 없을 때("세탁기가 끝나면" → RemainingTime 0). 못 읽으면 None."""
        p = (f'문구가 가리키는 순간의 값을 쓴다. 숫자 하나만. 모르면 "모름".\n'
             f'예) "배터리가 다 닳으면" + BatteryLevel(배터리 %) → 값 = 0\n'
             f'문구: "{text}" + {svc.split(".")[1]}({desc})')
        w = self._fill(p, '→ 값 = ')
        try: return float(w)
        except (TypeError, ValueError): return None

class Mapping:
    """명령 하나의 매핑 결과. ranked: {j: [svc top-5]}, parts: {j: [{"part": text, "ranked": [값 svc top-5]}]}, texts: {j: 절 텍스트},
    conn: 연결된 기기 카테고리 집합(형제 후보 중 실제로 붙어 있는 것을 고르는 데 쓴다. None 이면 안 거른다),
    sw: 그중 Switch 를 같이 가진 종류(켜기/끄기를 Switch 로 할 수 있는 기기)"""
    def __init__(self, ranked=None, parts=None, texts=None, conn=None, sw=None):
        self.conn = conn; self.sw = sw
        self.r = {int(k): [x for x in v if allowed(x)] for k, v in (ranked or {}).items()}
        self.p = {int(k): v for k, v in (parts or {}).items()}
        self.t = {int(k): v for k, v in (texts or {}).items()}
    def ranked(self, j): return self.r.get(j, [])
    def parts(self, j): return self.p.get(j)
    def text(self, j): return self.t.get(j, "")

def top(M, j, want=None):
    """절 j 의 top-1. want 를 주면 그 종류(value/function)만 — 없으면 None(아무거나 돌려주지 않는다)."""
    for s in M.ranked(j):
        k, _ = svc_info(s)
        if want is None or k == want: return s
    if want is not None: return None
    r = M.ranked(j); return r[0] if r else None

# ── 값 서비스 선택 ──
def _bigrams(t):
    t = re.sub(r"[\s.,]", "", t); return {t[i:i + 2] for i in range(len(t) - 1)}
def _lex_score(part, svc):
    cat = svc.split(".")[0]
    return len(_bigrams(part) & _bigrams(" ".join(AL.get(cat, []) + EFF.get(svc, {}).get("ko_triggers", []) + [cat])))
def _choose(cands, sc): return cands[max(range(len(cands)), key=lambda k: sc[k])]
def pick_value(text, vals, norank=False, conn=None):
    """값 서비스 후보(순위순) → 어휘 중복·순위·재정렬 보너스로 top-1. norank: 숫자뿐인 질의(검색 순위 무의미)면 순위 감점 생략"""
    bon, extra = rerank.value_bonus(text, vals, conn)
    vals = list(vals) + [e for e in extra if svc_info(e)[0] == "value" and (conn is None or e.split(".")[0] in conn)]
    if not vals: return None
    return _choose(vals, [_lex_score(text, vals[k]) - (0 if norank else k) + bon.get(vals[k], 0) for k in range(len(vals))])

CONJ_SPLIT = re.compile(r"(?<=[가-힣])(고|거나|이고|이거나|며|이며|는데|은데)[,\s]+(?!있|않|없)")
FILLER_PART = re.compile(r"^(그리고|그리|그렇지 않고|그렇지 않|그렇지 않으면|아니면|아니면서|그게 아니고|그 외에는|그리고 나서|또는|그때부터|그 이후로|그 뒤로|이후)(이면|면)?[,\s]*$")
NUM_ONLY = re.compile(r"^[\d.,%\s]+[가-힣]{0,2}\s*(이상|이하|미만|초과|넘으면|넘게|밑이면|아래면|이면|되면)[가-힣]{0,3}[,.]?$")
def _time_only_part(p):
    """조건 부분이 시각 표현뿐("야간(오후 10시)이 되면")이면 cron으로 이미 처리 → 조건에서 제외"""
    return slots._hour(p) is not None and not re.search(r"(온도|습도|농도|밝기|센서|감지|이상|이하|미만|초과|보다|동안|넘)", p)

def cond_expr(M, j, text, mixed=False):
    if mixed and "," in text: text = text.rsplit(",", 1)[-1].strip()      # COND/mixed("등을 100%로, 500lux 이상이면") → 조건은 쉼표 뒤
    e = _cond_expr(M, j, text)
    if " and " in e or " or " in e: return e
    if re.search(r"(과|와|랑|및) .*(모두|둘 다|전부)", text): return f"{e} and {e}"          # "거실과 침실 모두 X" = 같은 조건 두 기기
    if re.search(r"(이나|나|또는) .*(한 곳이라도|하나라도|중 )", text) or re.search(r"\S+(이나|거나) \S+(이|가|은|는)? ?(열|닫|켜|꺼|잠)", text): return f"{e} or {e}"
    return e

def _no_device_word(part):
    """그 부분에 기기를 가리키는 말이 하나도 없나 — 있으면 그 부분만 보고 값을 고르면 된다."""
    return not any(len(a) >= 2 and a in part for al in AL.values() for a in al)

def _cond_expr(M, j, text):
    """조건 절 → '속성 op 값'. 접속어미로 묶인 복합 조건은 부분별로 값 서비스를 배정해 and/or 결합(부분 재질의 결과 우선)."""
    cp = M.parts(j)
    if cp:
        cp = [x for x in cp if not FILLER_PART.match(x["part"])] or cp     # 접속 부분("그리고")은 조건이 아님
        cp = [x for x in cp if not _time_only_part(x["part"])] or cp
        cp = [{**x, "part": text} if text in x["part"] and x["part"] != text else x for x in cp]   # mixed 절: 잘라낸 조건 텍스트로
        conns = CONJ_SPLIT.findall(text)
        def _ctx(part):   # 무엇을 재는지가 그 부분에 없으면("200 이상이면", "잠겨있지 않으면") 앞의 확인 절에서 가져온다
            check = [k for k in range(j) if re.search(r"체크|확인|측정|모니터|살펴|재서|재고", M.text(k))]
            if NUM_ONLY.match(part.strip()): ks = check or list(range(j))
            elif _no_device_word(part) and check: ks = check      # 기기 이름이 아예 없을 땐 "…를 체크해서" 절이 있을 때만 빌린다
            else: return part
            prev = " ".join(M.text(k) for k in ks)
            return (prev + " " + part) if prev else part
        exprs = [_one_cond(pick_value(_ctx(x["part"]), [s_ for s_ in x["ranked"] if svc_info(s_)[0] == "value"], norank=NUM_ONLY.match(x["part"].strip()) is not None, conn=M.conn), x["part"]) for x in cp]
        out = exprs[0]
        for k, e in enumerate(exprs[1:]): out += (" or " if k < len(conns) and conns[k] in ("거나", "이거나") else " and ") + e
        return out
    parts = [p for p in CONJ_SPLIT.split(text) if p and p not in ("고", "거나", "이고", "이거나", "며", "이며", "는데", "은데")]
    vals = [s_ for s_ in M.ranked(j) if svc_info(s_)[0] == "value"]
    if len(parts) >= 2:
        conns = CONJ_SPLIT.findall(text); used = set(); exprs = []
        for part in parts:
            best = max([s_ for s_ in vals if s_ not in used] or vals or [None], key=lambda s_: _lex_score(part, s_) if s_ else -1)
            if best: used.add(best)
            exprs.append(_one_cond(best, part + ("면" if not re.search(r"(면|때)[,.]?$", part) else "")))
        out = exprs[0]
        for k, e in enumerate(exprs[1:]): out += (" or " if k < len(conns) and conns[k] in ("거나", "이거나") else " and ") + e
        return out
    return _one_cond(pick_value(text, vals, conn=M.conn), text)

NUM_T = ("DOUBLE", "INT", "INTEGER", "FLOAT", "LONG")

_HUB = [None]
def hub():
    """허브 설정(files/hub_config.json) — 색·장면·기준값 같은 사용자 설정. 정답지가 아니라 입력이다. 없으면 빈 dict."""
    if _HUB[0] is None:
        import os
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files", "hub_config.json")
        try: _HUB[0] = json.load(open(f, encoding="utf-8"))
        except Exception: _HUB[0] = {}
    return _HUB[0]
def _one_cond(svc, text):
    if not svc: return "?"
    k, spec = svc_info(svc); cat = svc.split(".")[0]; vt = spec.get("type") if spec else None
    cv = rerank.value_conv(svc, text)
    if cv and (vt not in NUM_T or slots.comparator(text) is None or not re.search(r"이상|이하|미만|초과|넘|보다|떨어|올라|아래|밑", text)): return f"{svc} {cv}"
    if vt in NUM_T:
        c = slots.comparator(text)
        if not c:
            n = _ASK[0].num_value(_ASK[1], text, svc, spec.get("descriptor", "")) if _ASK[0] else None
            if n is not None: return f"{svc} == {int(n) if float(n).is_integer() else n}"
            return f"{svc} == ?"
        v = rerank.unit_scale(svc, text, c[1]); v = int(v) if float(v).is_integer() else v
        r = slots.range_comparator(text)                          # "20도 이상, 30도 미만이면" → and
        if r: return " and ".join(f"{svc} {op} {int(x) if float(x).is_integer() else x}" for op, x in r)
        return f"{svc} {c[0]} {v}"
    if vt == "BOOL":
        # 참/거짓은 항상 2B 가 정한다. "부정어 있으면 false" 규칙은 "집을 나서면"(부정어 없음, 답은 false)을 못 본다.
        a = _ASK[0].bool_state(_ASK[1], text, svc, spec.get("descriptor", "")) if _ASK[0] else None
        return f"{svc} == {a or slots.bool_state(text, 'BOOL', [])}"
    if vt == "ENUM":
        v = slots.bool_state(text, "ENUM", members_of(cat, spec.get("format")))
        if not v and _ASK[0]:
            m = _ASK[0].enum_member(_ASK[1], text, svc, spec.get("descriptor", ""), members_of(cat, spec.get("format")))
            if m: v = f'"{m}"'
        return f"{svc} == {v if v else '?'}"
    if vt == "STRING":
        q = slots.quoted(text)
        if q: return f'{svc} == "{slots.STRING_KO.get(q.strip(), q.strip())}"'
    return f"{svc} == ?"

# ── 함수 서비스 선택 + 인자 ──
POS = {"open": r"열|개방|풀|해제", "close": r"닫|잠|차단", "on": r"켜|작동|시작|틀어|가동", "off": r"꺼|끄|중지|멈|정지|소등", "up": r"올리|올려|높이|높여|키워|증가|늘려|늘리|연장|더", "down": r"내리|내려|낮추|낮춰|줄|감소"}
NAME_POL = {"open": ["Open", "Unlock", "UpOrOpen"], "close": ["Close", "Lock", "DownOrClose"], "on": ["On", "Start", "Play", "TurnOn"], "off": ["Off", "Stop", "Pause", "TurnOff"], "up": ["Up", "Increase", "Raise", "AddMore"], "down": ["Down", "Decrease", "Lower"]}
OPP = {"open": "close", "close": "open", "on": "off", "off": "on", "up": "down", "down": "up"}
def pick_function(M, j, text, avoid=()):
    """top-5 함수 후보 중 형제(Open/Close, On/Off, Up/Down, Set vs Step)를 극성·숫자·모드 enum 규칙으로 선택.
    avoid: 같은 절에서 이미 쓴 서비스(한 절이 두 가지 동작을 시킬 때 같은 걸 두 번 고르지 않게)."""
    cands = [s_ for s_ in M.ranked(j) if svc_info(s_)[0] == "function"]
    for jj in list(range(j - 1, -1, -1)) + list(range(j + 1, j + 4)):      # 후보 없는 절(mixed·else 분기)은 이웃 절 후보를 빌림
        if cands: break
        cands = [s_ for s_ in M.ranked(jj) if svc_info(s_)[0] == "function"]
    bon, extra = rerank.func_bonus(text, cands, M.conn, M.sw); n0 = len(cands)
    cands = cands + [e for e in extra if svc_info(e)[0] == "function" and (M.conn is None or e.split(".")[0] in M.conn)]
    if avoid:
        keep = [c for c in cands if c not in avoid]
        n0 = len([c for c in cands[:n0] if c not in avoid]); cands = keep
    if not cands: return None
    pol = [p for p, rx in POS.items() if re.search(rx, text)]; has_num = slots.number_arg(text) is not None
    def score(k, s_):
        name = s_.split(".", 1)[1]; sc = -(k if k < n0 else 1) + bon.get(s_, 0)      # 규칙 추가 후보는 순위 벌점 1
        for p in pol:
            if any(name.startswith(w) or name.endswith(w) for w in NAME_POL[p]): sc += 3
            if any(name.startswith(w) or name.endswith(w) for w in NAME_POL[OPP[p]]): sc -= 3
        spec = svc_info(s_)[1]; nargs = [a for a in spec.get("arguments", []) if a.get("type") in NUM_T]
        if has_num and nargs and name.startswith(("Set", "MoveTo")): sc += 2
        if "Mode" in name or any(a.get("type") == "ENUM" for a in spec.get("arguments", [])):   # A14: 해당 enum 멤버가 있는 모드 설정 함수 우선
            for a in spec.get("arguments", []):
                if a.get("type") == "ENUM": sc += 2 if slots.enum_arg(text, members_of(s_.split(".")[0], a.get("format"))) else -1
        if rerank.sets_mode(s_) and nargs and not has_num: sc -= 3   # 모드만 말한 명령에 시간까지 달라는 함수는 뒤로
        if not has_num and name.startswith(("Set", "MoveTo")) and nargs and not spec.get("arguments", [{}])[0].get("type") == "ENUM" and not re.search(r"켜|꺼|끄|최대|최소", text): sc -= 1
        return sc
    return _choose(cands, [score(k, s_) for k, s_ in enumerate(cands)])

UNIT_SEC = {"seconds": 1, "minutes": 60}                     # 카탈로그 시간 단위 → 초
KO_SEC = {"초": 1, "분": 60, "시간": 3600}                   # 말한 단위 → 초
STEP_ATTR = {"Brightness": "Light.CurrentBrightness", "Volume": "Speaker.Volume", "TargetTemperature": "AirConditioner.TargetTemperature", "Temperature": "AirConditioner.TargetTemperature", "Level": "WindowCovering.CurrentPosition"}
COLOR_XY = {"red": (0.675, 0.322), "blue": (0.167, 0.04), "green": (0.409, 0.518), "white": (0.3127, 0.329), "yellow": (0.444, 0.517), "orange": (0.556, 0.408), "purple": (0.272, 0.109), "pink": (0.38, 0.19)}
TOGGLE_VERB = {r"열었다|열고 닫|개방": ("열어줘", "닫아줘"), r"올렸다|올리고 내": ("올려줘", "내려줘"), r"잠갔다|잠궜다": ("잠가줘", "열어줘"), r"켰다|켜고 끄": ("켜줘", "꺼줘")}
STEP_RE = re.compile(r"(\d+)\s*(도|%)?\s*(씩|만큼|단위씩|단위로|)\s*(높여|올려|키워|낮춰|내려|줄여|늘려|늘리|올리|증가|줄이|감소|밝게|어둡게|키우|낮추|내리|높이)")
UP_WORDS = ("높여", "올려", "키워", "늘려", "늘리", "올리", "증가", "밝게", "키우", "높이")
def call_node(M, j, text, force=None, avoid=()):
    svc = force or pick_function(M, j, text, avoid or ())
    if not svc: return {"op": "call", "target": "?", "args": {}}
    k, spec = svc_info(svc); cat = svc.split(".")[0]; args = {}
    for a in spec.get("arguments", []):
        aid, at = a["id"], a.get("type")
        if at == "ENUM":
            v = slots.enum_arg(text, members_of(cat, a.get("format")))
            if not v and _ASK[0]:
                v = _ASK[0].enum_member(_ASK[1], text, svc, a.get("descriptor") or spec.get("descriptor", ""),
                                        members_of(cat, a.get("format")))
            if v: args[aid] = v
        elif at in NUM_T:
            st = STEP_RE.search(text); lim = re.search(r"(최대|최소|최저|최고)\s*(\d+)", text)
            if re.search(r"최대 밝기", text) and st: lim = re.match(r"(최대)\s*(100)", "최대 100")
            if st and aid in STEP_ATTR:                       # A11: "10씩 높여줘. 최대 100까지" → min($Light.CurrentBrightness + 10, 100)
                up = st.group(4) in UP_WORDS; n_ = st.group(1); attr = STEP_ATTR[aid]
                args[aid] = f"{'min' if up else 'max'}(${attr} {'+' if up else '-'} {n_}, {lim.group(2)})" if lim else f"${attr} {'+' if up else '-'} {n_}"
                continue
            if aid == "Brightness":
                m = re.search(r"(\d+)\s*(%|퍼센트|으로|로|까지)", text)
                v = float(m.group(1)) if m else 100.0 if re.search(r"켜|최대|밝게", text) else 0.0 if re.search(r"꺼|끄|소등", text) else None
                if v is not None: args[aid] = v
            elif aid in ("Hue", "Saturation"):
                m = re.search(("색조" if aid == "Hue" else "채도") + r"\D{0,6}(\d+)", text)
                if m: args[aid] = int(m.group(1))
                else:
                    C = hub().get("색상", {})                     # 색 이름("분홍")이면 허브 색상 표의 각도
                    col = slots.enum_arg(text, [f"{c} - " for c in C])
                    if col: args[aid] = float(C[col]) if aid == "Hue" else 100.0   # 채도는 이름 색이면 100 (허브 관례)
            elif aid in ("ColorX", "ColorY"):
                col = slots.enum_arg(text, [f"{c} - " for c in COLOR_XY])
                if col: args[aid] = COLOR_XY[col][0 if aid == "ColorX" else 1]
            elif aid in ("Rate", "TransitionTime"): args[aid] = 0.0
            else:
                n = slots.number(text)
                if n is None and aid == "Volume": n = 100 if re.search(r"최대|끝까지", text) else 0 if re.search(r"최소|음소거", text) else None
                if n is not None and a.get("unit") in UNIT_SEC:            # 카탈로그 시간 단위에 맞춰 환산: "1시간"→60(minutes), "5분"→300(seconds)
                    mu = re.search(rf"{int(n) if float(n).is_integer() else n}\s*(초|분|시간)", text)
                    if mu: n = n * KO_SEC[mu.group(1)] / UNIT_SEC[a["unit"]]
                if n is not None: args[aid] = int(n) if at in ("INT", "INTEGER", "LONG") else float(n)
        elif at == "STRING":
            v = slots.string_arg(aid, text)
            if v is not None: args[aid] = v
    return {"op": "call", "target": svc, "args": args, "_text": text}

# ── 절 전처리: 슬롯 주도 mods, 표면 규칙 일반형, 관용구 ──
def slot_mods(t, text, mods):
    """슬롯 주도 mods 보강: time(시각·주기·시간창), sustain, every, repeat, count"""
    m = set(mods)
    if t != "STOP" and (slots.cron(text) or slots.period(text) or slots.until(text)): m.add("time")
    if t in ("COND", "TRIG") and re.search(r"\d+\s*(초|분|시간)\s*(이상|넘게|동안|째)", text): m.add("sustain")
    if t == "TRIG" and re.search(r"때마다", text): m.add("every")
    if t == "ACT" and (TOGGLE_RE.search(text) or re.search(r"반복", text)): m.add("repeat")
    if t in ("ACT", "STOP") and slots.count(text) is not None: m.add("count")
    return sorted(m)

COUNT_ONLY = re.compile(r"^(그리고 |그렇게 |이걸 )?(모두|전부|총|딱|최대)?\s*(\d+|[일이삼사오육칠팔구십]+)\s*(번|회|차례)\s*(만|까지|까지만|반복)?(요|만요|이요|해줘|이야|이에요)?[.!]?$")
SPLIT_TG1 = re.compile(r"(켜고|열고|올리고|내리고|닫고|잠그고)[,.]?\s*$"); SPLIT_TG2 = re.compile(r"^(끄|닫|내리|올리|열|잠그)(는|기)\s*(것을|걸|를)?\s*(반복|번갈아)")
SUSTAIN_ONLY = re.compile(r"^(그\s*상태로|그대로|그 상태가)?\s*(\d+|[일이삼사오육칠팔구십한두세네]+)\s*(초|분|시간)\s*(이상|넘게|넘도록|동안|째)\s*(이어지면|지속되면|계속되면|유지되면|계속이면|간다면|가면|지나면|되면)[.,]?$")
TIME_TOK = re.compile(r"(오전|오후|아침|저녁|밤|새벽|낮|정오|자정|야간|매일|평일|주말|월요일|화요일|수요일|목요일|금요일|토요일|일요일|\d+\s*시(\s*\d+\s*분)?|\d+\s*분|\d+\s*초|한|두|세|부터|까지|사이에|에는|에서|에|가|이|되면|됐을|되었을|될|때|이면|면|\(|\)|,|\.)")
def _time_only_seg(t): return slots._hour(t) is not None and TIME_TOK.sub("", t).strip() == ""
TWO_READ = re.compile(r"^(?P<r1>(지금\s+)?\S+(\s+\S+){0,3}?\s*(재고|보고|확인하고|측정하고|체크하고|읽고))\s+(?P<d>(\d+|한|두|세|네|반)\s*(분|시간|초)\s*(뒤에|후에|후|뒤|지나서|지나고|있다가))\s+(?P<r2>(다시|또|한 번 더|재차)\s*(\S+\s+)?(재서|봐서|확인해서|측정해서|체크해서|읽어서|재고|보고|확인하고)[, ]*)\s*(?P<c>\S+(\s+\S+){0,3}?\s*(올라갔으면|내려갔으면|올랐으면|떨어졌으면|차이가 나면|차이 나면|변했으면|달라졌으면|올라가면|내려가면|높아졌으면|낮아졌으면)[, ]*)\s*(?P<a>.+)$")
def _two_read(S):
    """"X를 재고 T 뒤에 다시 재서 D 이상 올라갔으면 A" 관용구 → READ DELAY READ COND + 나머지 (경계·타입 head가 흔들리는 자리)"""
    full = " ".join(s["text"] for s in S); m = TWO_READ.match(full)
    if not m: return S
    j0 = S[0].get("j", 0); pos = 0; tail = []
    for s in S:
        if pos >= m.start("a"): tail.append(s)
        pos += len(s["text"]) + 1
    if not tail or " ".join(t["text"] for t in tail) != m.group("a"): tail = [{"j": S[-1].get("j", len(S) - 1), "text": m.group("a"), "type": "ACT", "mods": []}]
    return [{"j": j0, "text": m.group("r1").strip(), "type": "READ", "mods": ["read"]}, {"j": j0, "text": m.group("d").strip(), "type": "DELAY", "mods": []},
            {"j": j0, "text": m.group("r2").strip(), "type": "READ", "mods": ["read"]}, {"j": j0, "text": m.group("c").strip(), "type": "COND", "mods": []}] + tail
def seg_fix(S):
    """표면 규칙 일반형: 수량만 있는 꼬리 절→STOP/count, 시각뿐인 COND/TRIG→TIME, 조건+"N분 넘게 이어지면"→sustain 병합, "…올리고 ‖ 내리기를 반복"→한 토글 절"""
    out = []
    for s in _two_read(S):
        t = s["text"].strip()
        if s["type"] == "ACT" and COUNT_ONLY.match(t): out.append({**s, "type": "STOP", "mods": sorted(set(s["mods"]) | {"count"})}); continue
        if s["type"] in ("COND", "TRIG") and _time_only_seg(t): out.append({**s, "type": "TIME", "mods": sorted(set(s["mods"]) | {"time"})}); continue
        if out and s["type"] == "COND" and SUSTAIN_ONLY.match(t) and out[-1]["type"] in ("COND", "TRIG"):
            p = out[-1]; out[-1] = {**p, "text": p["text"].rstrip(",. ") + " " + t, "mods": sorted(set(p["mods"]) | {"sustain"})}; continue
        if out and s["type"] == "ACT" and out[-1]["type"] == "ACT" and SPLIT_TG1.search(out[-1]["text"]) and SPLIT_TG2.match(t):
            p = out[-1]; out[-1] = {**p, "text": p["text"].rstrip(", ") + " " + t, "mods": sorted(set(p["mods"]) | set(s["mods"]) | {"repeat"})}; continue
        out.append(s)
    return out

def _merge_time_act(S):
    """시각창만 있는 TIME 절 뒤에 주기 있는 ACT 절("밤 10시부터 자정까지 ‖ 10분마다 사이렌을 울려줘") → 한 ACT/time 절 (cycle 하나)"""
    out = []
    for s in S:
        if out and out[-1]["type"] == "TIME" and s["type"] == "ACT" and slots.period(s["text"]) and not slots.period(out[-1]["text"]) and (slots.until(out[-1]["text"]) or slots.cron(out[-1]["text"])):
            p = out[-1]; out[-1] = {**s, "text": p["text"].rstrip(".,") + " " + s["text"], "mods": sorted(set(s["mods"]) | {"time"})}; continue
        out.append(s)
    return out

# ── 조립 ──
def build(segments, M, graph=True, ask=None):
    """segments: [{j, text, type, mods, (h6)}] (원문 순서), M: Mapping → {"timeline": [...]}. 진단은 build.last.
    ask: Asker — 규칙이 못 정한 칸(참/거짓, enum)을 2B 객관식으로 정한다. None 이면 규칙만."""
    _ASK[0], _ASK[1] = ask, " ".join(s["text"] for s in segments)
    S = [{**s, "j": s.get("j", k), "mods": slot_mods(s["type"], s["text"], s["mods"])} for k, s in enumerate(segments)]
    GD = None
    if len(S) >= 2:
        S = seg_fix(S)
        if graph: S, GD = graph_normalize(S)                        # 파서 head: 필러 탈락·참조 이동·후치 범위 절 앞으로
        if not (GD and (GD["moved"] or GD["drop"])):                # 간이 후치: 마지막 ACT 뒤 COND/TRIG/TIME만 있으면 앞으로
            last_act = max((i for i, s in enumerate(S) if s["type"] == "ACT"), default=-1)
            tail = [s for s in S[last_act + 1:] if s["type"] in ("COND", "TRIG", "TIME")] if last_act >= 0 else []
            if tail and len(tail) == len(S) - last_act - 1 and not any(s["type"] in ("COND", "TRIG", "TIME") for s in S[:last_act + 1]): S = tail + S[:last_act + 1]
    S = _merge_time_act(S)
    build.last = {"segments": S, "graph": GD}
    OJ = [s["j"] for s in S]                                          # 재배열 후에도 매핑은 원래 절 번호로
    root = assemble_tree([(s["type"], s["mods"], s["text"]) for s in S], False, [])
    placed = set()
    def collect(b):
        if b.seg is not None: placed.add(b.seg)
        for x in b.items + (b.else_items or []):
            if isinstance(x, Box): collect(x)
            else: placed.add(b.owner[id(x)])
    collect(root)
    def merged_text(seg):
        """조건 상자 머리 절 + 뒤따르는 미배치 COND/TRIG 절 → 조건식"""
        js = [seg]; k = seg + 1
        while k < len(S) and S[k]["type"] in ("COND", "TRIG") and k not in placed and "sustain" not in S[k]["mods"]:
            if not FILLER_PART.match(S[k]["text"].strip()): js.append(k)
            k += 1
        parts = [cond_expr(M, OJ[j], S[j]["text"], mixed="mixed" in S[j]["mods"]) for j in js]
        return (" or " if any(re.search(r"거나|또는|이거나", S[j]["text"]) for j in js[:-1]) else " and ").join(parts)
    cr = None                                                          # 시각(cron): 시각이 있는 절 우선, 그다음 요일·날짜만
    for s in S:
        c = slots.cron(s["text"]) if s["type"] != "STOP" else None
        if c and (slots._hour(s["text"]) or re.search(r"크리스마스|새해|정오|자정", s["text"])): cr = c; break
    if cr is None: cr = next((slots.cron(s["text"]) for s in S if s["type"] != "STOP" and slots.cron(s["text"])), None)
    tl = [{"op": "start_at", "anchor": "cron" if cr else "now", **({"cron": cr} if cr else {})}]
    counter = [0]; ncall = collections.Counter(); usedf = collections.defaultdict(set)
    def conv(b, out):
        for x in b.items:
            if isinstance(x, Box):
                if x.kind == "IF":
                    sx = S[x.seg] if x.seg is not None else None
                    if sx and sx["type"] in ("COND", "TRIG"): cond = merged_text(x.seg)
                    elif sx and sx["type"] == "STOP": cond = cond_expr(M, OJ[x.seg], sx["text"])
                    elif sx and sx["type"] == "ACT" and TOGGLE_RE.search(sx["text"]): cond = "n % 2 == 0"
                    elif sx and sx["type"] == "ACT" and "mixed" in sx["mods"]:            # ACT/mixed + STOP: "최대 밝기가 되면 그만" → 절 뒷부분 조건
                        tail = re.split(r"[.!] ", sx["text"])[-1]
                        cond = "Light.CurrentBrightness >= 100" if "최대 밝기" in tail else "Light.CurrentBrightness <= 0" if "최소 밝기" in tail else _cond_expr(M, OJ[x.seg], tail)
                    else: cond = "?"
                    if sx and re.search(r"(떨어졌|올랐|내려갔|올라갔|변했|차이)", sx["text"]) and any(n.get("op") == "read" for n in out):
                        prev = [n for n in out if n.get("op") == "read"][-1]; counter[0] += 1; v2 = f"v{counter[0]}"   # 두 번 읽기 → 차이 조건
                        out.append({"op": "read", "var": v2, "src": prev["src"]})
                        c = slots.comparator(sx["text"]); op_, val = (c[0], c[1]) if c else (">=", "?")
                        val = int(val) if isinstance(val, float) and val.is_integer() else val
                        if "차이" in sx["text"]: cond = f"abs(${prev['var']} - ${v2}) {op_} {val}"
                        else: cond = f"${prev['var']} - ${v2} {op_} {val}" if re.search(r"떨어졌|내려갔", sx["text"]) else f"${v2} - ${prev['var']} {op_} {val}"
                    node = {"op": "if", "cond": cond, "then": [], "else": []}
                    conv(x, node["then"])
                    if x.else_items is not None:
                        tmp = Box("ROOT"); tmp.items = x.else_items; tmp.owner = x.owner; conv(tmp, node["else"])
                    out.append(node)
                elif x.kind == "CYC":
                    txt = S[x.seg]["text"] if x.seg is not None else ""
                    if cr and re.match(r"^\d+ (\*|\*/\d+) ", cr) and slots.period(txt) and "시간" in txt: conv(x, out); continue   # cron 시 step이 주기를 흡수
                    per = slots.period(txt) or ("100 MSEC" if S[x.seg]["type"] == "TRIG" and "every" in S[x.seg]["mods"] else None)
                    cnt = slots.count(txt)
                    for s in S:
                        if cnt is None and ("count" in s["mods"] or s["type"] == "STOP"): cnt = slots.count(s["text"])
                    unt = slots.until(txt) or (f"n >= {cnt}" if cnt else None)
                    if per is None and unt and any(isinstance(y, Box) and y.kind == "IF" for y in x.items): per = "100 MSEC"   # 시간창 + 조건 = 폴링
                    node = {"op": "cycle", "until": unt, "period": per, "body": []}
                    if cnt: node["count"] = "n"                                                          # count 칸은 횟수가 아니라 반복 변수 이름(횟수는 until 에 들어간다)
                    elif unt is None and any(isinstance(y, Box) and y.kind == "IF" and y.seg is not None and S[y.seg]["type"] == "ACT" and TOGGLE_RE.search(S[y.seg]["text"]) for y in x.items): node["count"] = "n"
                    conv(x, node["body"])
                    if "count" not in node and re.search(r"\bn\b", json.dumps(node, ensure_ascii=False)): node["count"] = "n"
                    out.append(node)
            else:
                j = b.owner[id(x)]; s = S[j]; leaf = str(x)
                if leaf == "CALL":
                    ncall[j] += 1; force = None; txt = s["text"]; same_svc = False
                    if MODE_ON_RE.search(txt) and ncall[j] == 1 and rerank.switchable(txt, M.sw): force = "Switch.On"   # A4: "모드로 켜고" 첫 호출 = 켜기(스위치 달린 기기일 때)
                    elif MODE_TEMP_RE.search(txt):                                                          # "냉방 모드로 18도로": 1=Mode 2=Temperature
                        fs = [f for f in M.ranked(OJ[j]) if svc_info(f)[0] == "function"]
                        want = [f for f in fs if ("Mode" in f) == (ncall[j] == 1) and ("Temperature" in f) == (ncall[j] == 2)]
                        if want: force = want[0]
                    elif PULSE_RE.search(txt) and ncall[j] == 2: force = "Switch.Off"                        # 펄스 두 번째 호출 = 끄기
                    if TOGGLE_RE.search(txt) and TOGGLE_ONOFF_RE.search(txt) and rerank.switchable(txt, M.sw): force = "Switch.Toggle"   # 켜고 끄기 = Switch.Toggle 한 호출
                    elif SPLIT_TOGGLE_RE.search(txt) and j + 1 < len(S) and SPLIT_TOGGLE2_RE.match(S[j + 1]["text"]) and rerank.switchable(txt, M.sw): force = "Switch.Toggle"
                    elif TOGGLE_RE.search(txt):
                        mm = re.search(r"(\S+?)(와|과|이랑|랑) (\S+?)(을|를|으로|로)? ?(사이에서|번갈아)", txt)
                        same_svc = True
                        if mm: txt = txt[:mm.start()] + (mm.group(1) if ncall[j] == 1 else mm.group(3)) + "으로 " + txt[mm.end():]   # "A와 B 사이에서 전환"
                        else:
                            pair = next((v for k_, v in TOGGLE_VERB.items() if re.search(k_, txt)), ("켜줘", "꺼줘"))
                            txt = re.sub(r"\d+\s*(초|분|시간)\s*(마다|간격으로|씩)", "", TOGGLE_RE.sub("", txt)) + " " + pair[0 if ncall[j] == 1 else 1]   # "열었다 닫았다" → 열어줘 / 닫아줘
                    elif "else" in s["mods"] and ELSE_SPLIT.search(txt):
                        same_svc = True
                        parts = re.split(r"[,\s](?:그 외에는|그 외에|아니면|그렇지 않으면) ", txt, maxsplit=1)
                        txt = parts[min(ncall[j] - 1, len(parts) - 1)] + (" 설정해줘" if ncall[j] == 1 else "")
                    node = call_node(M, OJ[j], txt, force=force, avoid=() if (force or same_svc) else usedf[j])
                    if node["target"] == "?" and out and out[-1].get("op") == "call":
                        out[-1]["args"].update(node["args"])                     # 더 고를 서비스가 없으면 한 호출의 인자였던 셈
                    else:
                        usedf[j].add(node["target"]); out.append(node)
                elif leaf == "READ":
                    getf = next((f for f in M.ranked(OJ[j]) if svc_info(f)[0] == "function" and not f.startswith("Speaker.")), None)
                    param = re.search(r'\d+\s*동|식당|["“]', s["text"]) is not None      # 인자가 필요한 조회("301동 점심 메뉴")
                    if getf and (top(M, OJ[j], "value") is None or param) and not re.search(r"온도|습도|조도|농도|상태|값|수치", s["text"]):
                        out.append(call_node(M, OJ[j], s["text"], force=getf))            # 값 서비스가 없거나 인자 필요 → 함수 call
                    else:
                        counter[0] += 1; out.append({"op": "read", "var": f"v{counter[0]}", "src": top(M, OJ[j], "value") or pick_value(s["text"], [], conn=M.conn) or "?"})
                elif leaf == "DELAY": out.append({"op": "delay", "duration": slots.duration(s["text"]) or "?"})
                elif leaf.startswith("WAIT"):
                    # 기다림은 **그 일이 벌어지는 순간**(rising)이 기본이다.
                    # "문이 열리면 잠가" 를 edge none 으로 두면 이미 열려 있을 때 바로 잠근다 — 뜻이 다르다.
                    # "창문이 열린 채로 있으면" 처럼 이미 그런 상태를 가리키는 절만 none 이고,
                    # 그건 절 타입 head 가 붙이는 state 표시로 안다.
                    node = {"op": "wait", "cond": merged_text(j) if s["type"] in ("COND", "TRIG") else "?", "edge": "none" if "state" in s["mods"] else "rising"}
                    if "sustain" in s["mods"] and slots.duration(s["text"]): node["for"] = slots.duration(s["text"])
                    out.append(node)
                elif leaf == "BREAK": out.append({"op": "break"})
    conv(root, tl)
    _fill_message(tl)
    _walk(tl, _collapse_complement)
    if "주말" in " ".join(s["text"] for s in S) and tl[0].get("cron", "").endswith("* * 6,7") and len(tl) > 1 and tl[1].get("op") == "cycle" and tl[1].get("until") is None:
        tl[0]["cron"] = tl[0]["cron"][:-3] + "6"; tl[1]["until"] = 'Clock.Weekday == "monday"'          # "주말 동안 N마다" = 토 0시 시작 + 월요일까지
    return {"timeline": tl}
build.last = None

MSG_ARGS = ("Text", "Prompt", "Title", "Body", "Message", "Command")     # 사람이 읽을 문구가 들어가는 자리
def _fill_message(tl):
    """말하기·알림 호출의 문구 자리를 비워 두지 않는다.
    바로 앞에서 값을 읽었으면 그 값을 말하는 것으로 보고 "$변수", 아니면 그 절의 말을 그대로 쓴다."""
    last_read = [None]
    def go(nodes):
        for n in nodes:
            if n.get("op") == "read" and n.get("var"): last_read[0] = n["var"]
            if n.get("op") == "call":
                text = n.pop("_text", "")
                spec = svc_info(n.get("target"))[1] or {}
                for a in spec.get("arguments", []):
                    if a["id"] in MSG_ARGS and a.get("type") == "STRING" and a["id"] not in n["args"]:
                        n["args"][a["id"]] = f"${last_read[0]}" if last_read[0] else slots.message(text)
            n.pop("_text", None)
            for k in ("then", "else", "body"):
                if n.get(k): go(n[k])
    go(tl)

_CMP_INV = {">=": "<", "<": ">=", ">": "<=", "<=": ">"}
def _complement(a, b):
    ma = re.fullmatch(r"(\S+) (>=|<=|>|<|==|!=) (\S+)", a or ""); mb = re.fullmatch(r"(\S+) (>=|<=|>|<|==|!=) (\S+)", b or "")
    if not ma or not mb or ma.group(1) != mb.group(1): return False
    if ma.group(3) == mb.group(3) and _CMP_INV.get(ma.group(2)) == mb.group(2): return True
    return ma.group(2) == mb.group(2) == "==" and {ma.group(3), mb.group(3)} == {"true", "false"}
def _walk(nodes, fn):
    for n in nodes:
        fn(n)
        for k in ("then", "else", "body"):
            if n.get(k): _walk(n[k], fn)
def _collapse_complement(n):
    """if A {X} else { if ¬A {Y} } → if A {X} else {Y} (상보 조건은 ELSE)"""
    if n.get("op") == "if" and len(n.get("else", [])) == 1 and n["else"][0].get("op") == "if" and not n["else"][0].get("else") and _complement(n["cond"], n["else"][0]["cond"]):
        n["else"] = n["else"][0]["then"]
