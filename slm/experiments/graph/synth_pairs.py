# -*- coding: utf-8 -*-
"""구조 최소쌍 합성 — 정상 명령(gold 배치)에서 abnormal 4종을 만들고 gold 그래프를 자동 부여.
  post   조건 후치: "…행동들, 조건." → 조건이 앞 행동을 포함(범위 역전)
  after  사건 참조(뒤): "…C해줘. C하고 나서 [지연] D."   → D는 C 뒤(앵커 C, rel=after)
  before 사건 참조(앞): "…C해줘. C하기 전에 D."          → D는 C 앞(앵커 C, rel=before) — 순서 재배열
  before0 재언급 없는 역전: "A하고 B해줘" → "B하기 전에 A해줘" (텍스트 [B전에][A], 실행 A→B)
  filler 필러 절 (앞/중간/뒤)
gold 그래프(절 단위): parent[i](범위 부모 절 or -1), role[i] ∈ {scope, act, delay, ref, filler, time},
  anchor[i]=(j, rel) (참조 절만), exec[]: 실행 순서(잎 절만; 참조·필러 제외).
소스: type_labels.json + assembly/box 배치(정상 명령 gold). 출력 pairs.json
"""
import json, os, sys, random, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "assembly"))
from box import assemble_tree, gold_flags, assemble
from skeleton import skeleton
from candidates import tree_to_lines
random.seed(0)
T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))

NOMIN = {"켜줘": "켜기", "꺼줘": "끄기", "닫아줘": "닫기", "열어줘": "열기", "잠궈줘": "잠그기", "잠가줘": "잠그기", "울려줘": "울리기", "찍어줘": "찍기",
         "알려줘": "알리기", "말해줘": "말하기", "바꿔줘": "바꾸기", "틀어줘": "틀기", "올려줘": "올리기", "내려줘": "내리기", "재생해줘": "재생하기",
         "설정해줘": "설정하기", "낮춰줘": "낮추기", "높여줘": "높이기", "멈춰줘": "멈추기", "보내줘": "보내기", "출력해줘": "출력하기", "해줘": "하기"}
CONJ = {"켜줘": "켜고", "꺼줘": "끄고", "닫아줘": "닫고", "열어줘": "열고", "잠궈줘": "잠그고", "잠가줘": "잠그고", "울려줘": "울리고", "찍어줘": "찍고",
        "알려줘": "알리고", "말해줘": "말하고", "바꿔줘": "바꾸고", "틀어줘": "틀고", "올려줘": "올리고", "내려줘": "내리고", "설정해줘": "설정하고", "해줘": "하고"}
FILL_PRE = ["아 맞다,", "그리고 하나 더,", "잠깐만,", "음 그러니까", "저기 부탁인데,", "혹시 가능하면"]
FILL_POST = ["부탁할게.", "고마워요.", "잘 부탁해.", "이상이야.", "알겠지?"]
FILL_MID = ["아 참,", "그러니까 말이야,", "음,"]
DELAYS = ["5분 뒤에", "10분 후에", "30분 뒤에", "1시간 뒤에"]

def nominal(txt, table):
    core = txt.rstrip(".,")
    for e in sorted(table, key=len, reverse=True):
        if core.endswith(e): return core[: -len(e)] + table[e]
    return None

def lines_to_graph(L, segs):
    """줄 목록 → parent/role. 줄 순서 = 실행 순서(잎), 범위 머리는 scope."""
    n = len(segs); parent = [-1] * n; role = ["act"] * n; stack = []   # (seg, depth)
    exec_order = []
    last_scope_at = {}   # depth → 마지막 범위 절 (머리 없는 [아니면]은 그 IF에 귀속)
    for seg, d, mk in L:
        while stack and stack[-1][1] >= d: stack.pop()
        p = stack[-1][0] if stack else -1
        if seg is None:                                   # 머리 없는 [아니면]: 직전 같은 깊이 범위(IF)의 가지
            if mk == "아니면" and d in last_scope_at: stack.append((last_scope_at[d], d))
            continue
        parent[seg] = p
        if mk in ("반복", "조건", "아니면", "시각"):
            role[seg] = "scope" if mk != "시각" else "time"; stack.append((seg, d)); last_scope_at[d] = seg
        else:
            role[seg] = {"지연": "delay", "읽기": "act", "대기": "wait", "참조": "ref", "무시": "filler", "": "act", "종료": "act"}[mk]
            if role[seg] == "act" and segs[seg][0] in ("COND", "TRIG"): role[seg] = "cont"   # 병합 조건의 뒷부분
            if role[seg] in ("act", "delay", "wait"): exec_order.append(seg)
    return parent, role, exec_order

def base_items():
    out = []
    for o in T:
        if not o["ir_gt"]: continue
        segs = [(s["type"], s["mods"], s["text"]) for s in o["segments"]]
        cron, cyc = gold_flags(o["ir_gt"])
        if assemble(segs, cron, cyc) != skeleton(o["ir_gt"]): continue
        L = tree_to_lines(assemble_tree(segs, cron, cyc), segs)
        parent, role, ex = lines_to_graph(L, segs)
        out.append(dict(src=o["i"], kind="normal", segs=[s[2] for s in segs], types=[s[0] for s in segs], mods=[s[1] for s in segs], parent=parent, role=role, anchor={}, exec=ex, lines=L))
    return out

def mk(src, kind, segs, types, parent, role, anchor, ex, mods=None):
    mods = mods if mods is not None else [[] for _ in segs]
    return dict(src=src, kind=kind, segs=segs, types=types, mods=mods, parent=parent, role=role, anchor={str(k): v for k, v in anchor.items()}, exec=ex, cmd=" ".join(segs))

def synth_post(it):
    # 조건 절이 첫 절이고 나머지가 그 자식 잎들뿐
    if it["role"][0] != "scope" or it["types"][0] != "COND": return None
    if any(p != 0 for p in it["parent"][1:]) or any(r not in ("act", "delay") for r in it["role"][1:]): return None
    cond = it["segs"][0].rstrip(".,") + "."; acts = list(it["segs"][1:]); acts[-1] = acts[-1].rstrip(".") + ","
    segs = acts + [cond]; n = len(segs)
    parent = [n - 1] * (n - 1) + [-1]; role = it["role"][1:] + ["scope"]; types = it["types"][1:] + ["COND"]; mods = it["mods"][1:] + [it["mods"][0]]
    return mk(it["src"], "post", segs, types, parent, role, {}, list(range(n - 1)), mods)

def _last_act(it):
    """앵커 = 최상위 행동 절 중 무작위(직전 절 편향 제거). 명사화 가능한 것만."""
    cands = [c for c in it["exec"] if it["types"][c] == "ACT" and it["parent"][c] == -1 and it["role"][c] == "act" and nominal(it["segs"][c], NOMIN) and nominal(it["segs"][c], CONJ)]
    return random.choice(cands) if cands else None

def synth_after(it, pool):
    c = _last_act(it)
    if c is None: return None
    ref = nominal(it["segs"][c], CONJ)
    if not ref: return None
    ref += " 나서"
    segs = list(it["segs"]) + [ref]; types = it["types"] + ["ACT"]; parent = it["parent"] + [-1]; role = it["role"] + ["ref"]; mods = it["mods"] + [[]]
    anchor = {len(segs) - 1: [c, "after"]}; ex = list(it["exec"]); ins = []
    if random.random() < 0.6:
        segs.append(random.choice(DELAYS)); types.append("DELAY"); parent.append(-1); role.append("delay"); ins.append(len(segs) - 1); mods.append([])
    segs.append(random.choice(pool)); types.append("ACT"); parent.append(-1); role.append("act"); ins.append(len(segs) - 1); mods.append([])
    k = ex.index(c) + 1; ex[k:k] = ins                     # 앵커 바로 뒤에 삽입
    return mk(it["src"], "after", segs, types, parent, role, anchor, ex, mods)

def synth_before(it, pool):
    c = _last_act(it)
    if c is None: return None
    ref = nominal(it["segs"][c], NOMIN)
    if not ref: return None
    ref += " 전에"
    segs = list(it["segs"]) + [ref]; types = it["types"] + ["ACT"]; parent = it["parent"] + [-1]; role = it["role"] + ["ref"]; mods = it["mods"] + [[]]
    anchor = {len(segs) - 1: [c, "before"]}
    segs.append(random.choice(pool)); types.append("ACT"); parent.append(-1); role.append("act"); mods.append([])
    d = len(segs) - 1; ex = list(it["exec"]); ex.insert(ex.index(c), d)          # D를 C 앞에
    return mk(it["src"], "before", segs, types, parent, role, anchor, ex, mods)

def synth_before0(it):
    # 형태 "A하고 B해줘" (ACT ACT, 최상위) → "B하기 전에 A해줘"
    if it["types"] != ["ACT", "ACT"] or it["parent"] != [-1, -1]: return None
    a, b = it["segs"]
    A = nominal(a, {"하고": "해줘", "켜고": "켜줘", "끄고": "꺼줘", "닫고": "닫아줘", "열고": "열어줘", "잠그고": "잠궈줘", "울리고": "울려줘", "찍고": "찍어줘",
                    "설정하고": "설정해줘", "바꾸고": "바꿔줘", "올리고": "올려줘", "내리고": "내려줘"})
    B = nominal(b, NOMIN)
    if not A or not B: return None
    segs = [B + " 전에", A + "."]; types = ["ACT", "ACT"]; parent = [-1, -1]; role = ["ref", "act"]
    # 첫 절은 B의 (유일한) 언급이자 앵커: 실행 [A][B] — B는 참조 절 자체가 사건이므로 role을 act로 두고 exec 역전
    role = ["act", "act"]
    return mk(it["src"], "before0", segs, types, parent, role, {}, [1, 0])

DEVS = ["거실 조명", "침실 조명", "주방 조명", "복도 조명", "현관 조명", "에어컨", "가습기", "제습기", "공기청정기", "TV", "스피커", "선풍기 플러그", "히터 플러그", "커튼", "블라인드", "창문", "현관문", "밸브", "도어락", "사이렌"]
ONOFF = [("켜줘", "켜고", "켜기"), ("꺼줘", "끄고", "끄기")]
OPEN = [("열어줘", "열고", "열기"), ("닫아줘", "닫고", "닫기")]
def obj(w):
    ch = w[-1]; return w + ("을" if (ord(ch) - 0xAC00) % 28 else "를")
def synth_event(pool):
    """같은 기기·다른 동작 방해자: 'X를 켜고 [지연] X를 꺼줘. X를 (켜고|끄고) 나서 D' / '… 전에 D'  — 앵커 = 동사 일치 절."""
    dev = random.choice(DEVS); verbs = OPEN if dev in ("커튼", "블라인드", "창문", "현관문", "밸브", "도어락") else ONOFF
    v1, v2 = verbs if random.random() < 0.5 else verbs[::-1]
    a1 = f"{obj(dev)} {v1[1]}"; dl = random.choice(DELAYS); a2 = f"{obj(dev)} {v2[0]}."
    tgt = random.choice([0, 1]); rel = random.choice(["after", "before"])
    v = (v1 if tgt == 0 else v2)
    ref = f"{obj(dev)} {v[1]} 나서" if rel == "after" else f"{obj(dev)} {v[2]} 전에"
    D = random.choice(pool)
    segs = [a1, dl, a2, ref, D]; types = ["ACT", "DELAY", "ACT", "ACT", "ACT"]; parent = [-1] * 5; role = ["act", "delay", "act", "ref", "act"]
    a = 0 if tgt == 0 else 2; ex = [0, 1, 2]
    ex.insert(ex.index(a) + (1 if rel == "after" else 0), 4)
    return mk(-1, "event", segs, types, parent, role, {3: [a, rel]}, ex)

def synth_filler(it):
    kind = random.choice(["pre", "post", "mid", "both"])
    if kind == "mid" and len(it["segs"]) < 2: kind = "pre"
    segs = list(it["segs"]); types = list(it["types"]); parent = list(it["parent"]); role = list(it["role"]); ex = list(it["exec"]); mods = list(it["mods"])
    def shift(k):
        nonlocal parent, ex
        parent = [p + 1 if p >= k else p for p in parent]; ex = [e + 1 if e >= k else e for e in ex]
    if kind in ("pre", "both"):
        segs.insert(0, random.choice(FILL_PRE)); types.insert(0, "ACT"); shift(0); parent.insert(0, -1); role.insert(0, "filler"); mods.insert(0, [])
    if kind == "mid" and len(segs) >= 2:
        pos = random.randrange(1, len(segs)); segs.insert(pos, random.choice(FILL_MID)); types.insert(pos, "ACT"); shift(pos); parent.insert(pos, -1); role.insert(pos, "filler"); mods.insert(pos, [])
    if kind in ("post", "both"):
        segs.append(random.choice(FILL_POST)); types.append("ACT"); parent.append(-1); role.append("filler"); mods.append([])
    return mk(it["src"], "filler", segs, types, parent, role, {}, ex, mods)

if __name__ == "__main__":
    base = base_items()
    pool = [it["segs"][0] for it in base if len(it["segs"]) == 1 and it["types"] == ["ACT"] and not re.search(r"\d+\s*시|마다|매일|주말|오전|오후|정오|자정", it["segs"][0])]
    out = []
    for it in base:
        out.append(mk(it["src"], "normal", it["segs"], it["types"], it["parent"], it["role"], {}, it["exec"], it["mods"]))
        for f in (synth_post, lambda x: synth_after(x, pool), lambda x: synth_before(x, pool), synth_before0, synth_filler):
            r = f(it)
            if r: out.append(r)
    for k in range(160):
        e = synth_event(pool); e["src"] = 100000 + k; out.append(e)
    json.dump(out, open(os.path.join(HERE, "pairs.json"), "w"), ensure_ascii=False, indent=1)
    import collections
    print(collections.Counter(x["kind"] for x in out))
    for k in ("post", "after", "before", "before0", "filler"):
        x = next(x for x in out if x["kind"] == k)
        print(f"[{k}] {x['cmd']}\n   parent={x['parent']} role={x['role']} anchor={x['anchor']} exec={x['exec']}")
