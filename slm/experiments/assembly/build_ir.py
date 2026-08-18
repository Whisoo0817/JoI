# -*- coding: utf-8 -*-
"""IR 빌더 — 상자 기계(구조) + 슬롯 규칙(값) + 매핑 top-1(서비스) → 실제 timeline IR JSON. 모델 생성 없음.
G/G 조건(gold 경계·타입·mods, 매핑은 ranked.json top-1). 출력 ir_pred.json, 계층 평가:
  S 구조(뼈대) → +T 시간 슬롯(cron/period/until/count/duration/for/edge) → +C 조건식 → +V 서비스 → +A 인자(enum·숫자; 문자열 인자는 제외)
"""
import json, os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
sys.path.insert(0, ROOT)
os.environ.setdefault("SLOT", "1")
from box import Box, assemble_tree
from skeleton import skeleton, canon
import slots
from loader import SERVICE_DATA
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
R = json.load(open(os.path.join(HERE, "..", "map", "ranked.json")))
MAP = {(r["cmd"], s["j"]): s["ranked"] for r in R for s in r["segs"]}

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
def cond_expr(cmd, j, text):
    """조건 절 → '속성 op 값' 문자열. 절 안에 접속어미로 묶인 복합 조건이면 부분별로 값 서비스를 배정해 and/or 결합."""
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
    if not vals: return "?"
    W = float(os.environ.get("LEXW", "1.0"))
    best = max(range(len(vals)), key=lambda k: W * _lex_score(text, vals[k]) - k)   # 어휘 중복 + 순위
    return _one_cond(vals[best], text)

def _one_cond(svc, text):
    if not svc: return "?"
    k, spec = svc_info(svc); cat = svc.split(".")[0]
    vt = spec.get("type") if spec else None
    if vt in ("DOUBLE", "INT", "INTEGER", "FLOAT", "LONG"):
        c = slots.comparator(text)
        if c: 
            v = c[1]; v = int(v) if float(v).is_integer() else v
            return f"{svc} {c[0]} {v}"
        return f"{svc} == ?"
    if vt == "BOOL": return f"{svc} == {slots.bool_state(text, 'BOOL', [])}"
    if vt == "ENUM":
        v = slots.bool_state(text, "ENUM", members_of(cat, spec.get("format")))
        return f"{svc} == {v if v else '?'}"
    return f"{svc} == ?"

POS = {"open": r"열|개방|풀|해제", "close": r"닫|잠|차단", "on": r"켜|작동|시작|틀어|가동", "off": r"꺼|끄|중지|멈|정지|소등", "up": r"올리|올려|높이|높여|키워|증가|더", "down": r"내리|내려|낮추|낮춰|줄|감소"}
NAME_POL = {"open": ["Open", "Unlock", "UpOrOpen"], "close": ["Close", "Lock", "DownOrClose"], "on": ["On", "Start", "Play", "TurnOn"], "off": ["Off", "Stop", "Pause", "TurnOff"], "up": ["Up", "Increase", "Raise", "AddMore"], "down": ["Down", "Decrease", "Lower"]}
def pick_function(cmd, j, text):
    """top-5 함수 후보 중 형제 서비스(Open/Close, On/Off, Up/Down, Set vs Step) 극성·숫자 규칙으로 선택."""
    cands = [s_ for s_ in MAP.get((cmd, j), []) if svc_info(s_)[0] == "function"]
    if not cands: return None
    pol = [p for p, rx in POS.items() if re.search(rx, text)]
    has_num = slots.number(text) is not None
    def score(k, s_):
        name = s_.split(".", 1)[1]; sc = -k
        for p in pol:
            if any(name.startswith(w) or name.endswith(w) for w in NAME_POL[p]): sc += 3
            opp = {"open": "close", "close": "open", "on": "off", "off": "on", "up": "down", "down": "up"}[p]
            if any(name.startswith(w) or name.endswith(w) for w in NAME_POL[opp]): sc -= 3
        spec = svc_info(s_)[1]; nargs = [a for a in spec.get("arguments", []) if a.get("type") in ("DOUBLE", "INT", "INTEGER", "FLOAT", "LONG")]
        if has_num and nargs and name.startswith(("Set", "MoveTo")): sc += 2
        if not has_num and name.startswith(("Set", "MoveTo")) and nargs and not spec.get("arguments", [{}])[0].get("type") == "ENUM" and not re.search(r"켜|꺼|끄|최대|최소", text): sc -= 1
        return sc
    return max(enumerate(cands), key=lambda kv: score(*kv))[1]

def call_node(cmd, j, text):
    svc = pick_function(cmd, j, text)
    if not svc: return {"op": "call", "target": "?", "args": {}}
    k, spec = svc_info(svc); cat = svc.split(".")[0]; args = {}
    for a in spec.get("arguments", []):
        aid, at = a["id"], a.get("type")
        if at == "ENUM":
            v = slots.enum_arg(text, members_of(cat, a.get("format")))
            if v: args[aid] = v
        elif at in ("DOUBLE", "INT", "INTEGER", "FLOAT", "LONG"):
            if aid == "Brightness":
                m = re.search(r"(\d+)\s*(%|퍼센트|으로|로|까지)", text)
                if m: v = float(m.group(1))
                elif re.search(r"켜|최대|밝게", text): v = 100.0
                elif re.search(r"꺼|끄|소등", text): v = 0.0
                else: v = None
                if v is not None: args[aid] = v
            elif aid == "Rate": args[aid] = 0.0
            elif aid == "TransitionTime": args[aid] = 0.0
            else:
                n = slots.number(text)
                if n is not None: args[aid] = int(n) if at in ("INT", "INTEGER", "LONG") else float(n)
        else:
            q = slots.quoted(text)
            if q: args[aid] = q
    return {"op": "call", "target": svc, "args": args}

def build(o):
    cmd = o["cmd"]; S = o["segments"]
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
            js.append(k); k += 1
        parts = [cond_expr(cmd, j, S[j]["text"]) for j in js]
        joiner = " or " if any(re.search(r"거나|또는|이거나", S[j]["text"]) for j in js[:-1]) else " and "
        return joiner.join(parts)
    def time_seg():
        for i, s in enumerate(S):
            if "time" in s["mods"] or s["type"] == "TIME": return s["text"]
        return None
    ts = time_seg()
    cr = slots.cron(ts) if ts and not slots.period(ts) else (slots.cron(ts) if ts else None)
    tl = [{"op": "start_at", "anchor": "cron" if cr else "now", **({"cron": cr} if cr else {})}]
    counter = [0]
    def conv(b, out):
        for x in b.items:
            if isinstance(x, Box):
                if x.kind == "IF":
                    if x.seg is not None and S[x.seg]["type"] in ("COND", "TRIG"): cond = merged_text(x.seg)
                    elif x.seg is not None and S[x.seg]["type"] == "STOP": cond = cond_expr(cmd, x.seg, S[x.seg]["text"])
                    else: cond = "?"
                    node = {"op": "if", "cond": cond, "then": [], "else": []}
                    conv(x, node["then"])
                    if x.else_items is not None:
                        tmp = Box("ROOT"); tmp.items = x.else_items; tmp.owner = x.owner; conv(tmp, node["else"])
                    out.append(node)
                elif x.kind == "CYC":
                    txt = S[x.seg]["text"] if x.seg is not None else ""
                    per = slots.period(txt) or ("100 MSEC" if S[x.seg]["type"] == "TRIG" and "every" in S[x.seg]["mods"] else None)
                    # count: 상자 머리 절 또는 STOP/count·ACT/count 절
                    cnt = slots.count(txt)
                    for j, s in enumerate(S):
                        if cnt is None and ("count" in s["mods"] or s["type"] == "STOP"): cnt = slots.count(s["text"])
                    unt = slots.until(txt) or (f"n >= {cnt}" if cnt else None)
                    node = {"op": "cycle", "until": unt, "period": per, "body": []}
                    if cnt: node["count"] = cnt
                    conv(x, node["body"]); out.append(node)
            else:
                j = b.owner[id(x)]; s = S[j]; leaf = str(x)
                if leaf == "CALL": out.append(call_node(cmd, j, s["text"]))
                elif leaf == "READ":
                    counter[0] += 1; out.append({"op": "read", "var": f"v{counter[0]}", "src": top(cmd, j, "value") or "?"})
                elif leaf == "DELAY": out.append({"op": "delay", "duration": slots.duration(s["text"]) or "?"})
                elif leaf.startswith("WAIT"):
                    node = {"op": "wait", "cond": merged_text(j) if s["type"] in ("COND", "TRIG") else "?", "edge": "rising" if "every" in s["mods"] else "none"}
                    if "sustain" in s["mods"]:
                        d = slots.duration(s["text"]); 
                        if d: node["for"] = d
                    out.append(node)
                elif leaf == "BREAK": out.append({"op": "break"})
    conv(root, tl)
    return {"timeline": tl}

# ── 평가 ──
def norm_cond(c, reads):
    if not isinstance(c, str): return c
    for var, src in reads.items(): c = c.replace("$" + var, src).replace(var, src) if var.startswith("$") else c.replace("$" + var, src)
    c = re.sub(r"\s+", " ", c.strip())
    c = re.sub(r"(\d+)\.0\b", r"\1", c)
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
        if MAPPED_ONLY and (o["cmd"], 0) not in MAP: continue
        ir = build(o); out.append({"i": o["i"], "cmd": o["cmd"], "ir_pred": ir, "ir_gt": o["ir_gt"]})
        if skeleton(ir) != skeleton(o["ir_gt"]): continue
        n_struct += 1
        pf, gf = flat(ir["timeline"]), flat(o["ir_gt"]["timeline"])
        if len(pf) != len(gf): continue
        okT = okC = okV = okA = True
        for (po, pd), (go, gd) in zip(pf, gf):
            if po != go: okT = False; continue
            for key in ("cron", "period", "until", "count", "duration", "for", "edge"):
                if key in gd:
                    slot[key][1] += 1; hit = str(pd.get(key)) == str(gd.get(key)); slot[key][0] += hit; okT &= hit
                    if not hit and len(ex_fail[key]) < 6: ex_fail[key].append((o["cmd"], pd.get(key), gd.get(key)))
            if "cond" in gd:
                slot["cond"][1] += 1; hit = pd["cond"] == gd["cond"]; slot["cond"][0] += hit; okC &= hit
                ga = re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", gd["cond"]); pa = re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", pd["cond"])
                if ga:
                    slot["cond.attr"][1] += 1; slot["cond.attr"][0] += (sorted(ga) == sorted(pa))
                    if sorted(ga) == sorted(pa): slot["cond.opval|attr"][1] += 1; slot["cond.opval|attr"][0] += hit
                if not hit and len(ex_fail["cond"]) < 10: ex_fail["cond"].append((o["cmd"], pd["cond"], gd["cond"]))
            if "target" in gd:
                slot["target"][1] += 1; hit = pd["target"] == gd["target"]; slot["target"][0] += hit; okV &= hit
                if hit:
                    a, b = cmp_args(pd["args"], gd["args"], gd["target"]); slot["args"][0] += a; slot["args"][1] += b; okA &= (a == b)
                    if a != b and len(ex_fail["args"]) < 8: ex_fail["args"].append((o["cmd"], pd["args"], gd["args"]))
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
