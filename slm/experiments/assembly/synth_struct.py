# -*- coding: utf-8 -*-
"""구조 합성 — 학습 분할(i%5!=0) 명령의 gold 배치에서 필러 / REF 재언급 / 조건 후치 예를 만든다.
각 예 = (cmd_text, lines, segs). challenge 문장과 겹치지 않는 표현 사용.
"""
import random, re
FILLERS_PRE = ["아 맞다,", "그리고 하나 더,", "잠깐만,", "음 그러니까", "이건 꼭 해줘,", "저기 부탁인데,"]
FILLERS_POST = ["부탁할게.", "고마워요.", "잘 부탁해.", "이상이야.", "알겠지?"]
FILLERS_MID = ["아 참,", "그러니까 말이야,", "음,"]
REF_END = {"켜줘": "켜고 나서", "꺼줘": "끄고 나서", "닫아줘": "닫고 나서", "열어줘": "열고 나서", "잠궈줘": "잠그고 나서", "잠가줘": "잠그고 나서",
           "울려줘": "울리고 나서", "찍어줘": "찍고 나서", "알려줘": "알리고 나서", "말해줘": "말하고 나서", "바꿔줘": "바꾸고 나서", "틀어줘": "틀고 나서",
           "올려줘": "올리고 나서", "내려줘": "내리고 나서", "재생해줘": "재생하고 나서", "해줘": "하고 나서"}
DELAYS = ["5분 뒤에", "10분 후에", "30분 뒤에", "1시간 뒤에", "20분 후에"]

def _renum(lines, mapping):
    return [(mapping.get(s, s) if s is not None else None, d, m) for s, d, m in lines]

def fillers(items, rnd):
    out = []
    for i, cmd, L, segs in items:
        kind = rnd.choice(["pre", "post", "mid", "both"])
        segs2 = list(segs); L2 = list(L)
        if kind in ("pre", "both"):
            f = rnd.choice(FILLERS_PRE)
            segs2 = [("ACT", [], f)] + segs2; L2 = [(0, 0, "무시")] + _renum(L2, {k: k + 1 for k in range(len(segs))})
        if kind in ("post", "both"):
            f = rnd.choice(FILLERS_POST)
            segs2 = segs2 + [("ACT", [], f)]; L2 = L2 + [(len(segs2) - 1, 0, "무시")]
        if kind == "mid" and len(segs) >= 2:
            f = rnd.choice(FILLERS_MID); pos = rnd.randrange(1, len(segs))
            segs2 = segs[:pos] + [("ACT", [], f)] + segs[pos:]
            L2 = []
            for s, d, m in L:
                if s is not None and s >= pos: s = s + 1
                L2.append((s, d, m))
            # 필러 줄: 원문 순서상 pos 자리 = 절 pos-1 줄 바로 뒤, 같은 깊이
            k = next((j for j, (s, d, m) in enumerate(L2) if s == pos - 1), None)
            dep = L2[k][1] if k is not None else 0
            L2 = L2[:k + 1] + [(pos, dep, "무시")] + L2[k + 1:] if k is not None else L2 + [(pos, 0, "무시")]
        out.append((" ".join(x[2] for x in segs2), L2, segs2))
    return out

def refs(items, act_pool, rnd):
    out = []
    for i, cmd, L, segs in items:
        # 마지막 줄이 깊이 0의 행동 절이고 어미가 사전에 있으면
        s, d, m = L[-1]
        if s is None or m != "" or d != 0 or segs[s][0] != "ACT": continue
        txt = segs[s][2].rstrip(".,")
        end = next((e for e in sorted(REF_END, key=len, reverse=True) if txt.endswith(e)), None)
        if not end: continue
        ref = txt[: -len(end)] + REF_END[end]
        # 목적어까지 포함된 재언급이 자연스러움: "거실 조명을 켜고 나서"
        new_act = rnd.choice(act_pool)
        segs2 = list(segs) + [("ACT", [], ref)]
        L2 = list(L) + [(len(segs2) - 1, 0, "참조")]
        if rnd.random() < 0.7:
            dl = rnd.choice(DELAYS); segs2.append(("DELAY", [], dl)); L2.append((len(segs2) - 1, 0, "지연"))
        segs2.append(("ACT", [], new_act)); L2.append((len(segs2) - 1, 0, ""))
        out.append((" ".join(x[2] for x in segs2), L2, segs2))
    return out

def postposed(items, rnd):
    out = []
    for i, cmd, L, segs in items:
        # 형태: [조건 s0 d0] + 자식들(깊이1, 잎만) 만으로 구성 (다른 줄 없음)
        if len(L) < 2 or L[0][2] != "조건" or L[0][0] is None: continue
        if any(d != 1 or m in ("조건", "아니면", "반복") for _, d, m in L[1:]): continue
        c = L[0][0]; cond = segs[c][2].rstrip(".,")
        acts = [segs[s][2] for s, _, _ in L[1:]]
        acts[-1] = acts[-1].rstrip(".") + ","
        order = [s for s, _, _ in L[1:]] + [c]
        segs2 = [segs[s] if s != c else ("COND", [], cond + ".") for s in order]
        segs2 = [(segs[s][0], segs[s][1], acts[k]) if k < len(acts) else segs2[k] for k, s in enumerate(order)]
        mp = {s: k for k, s in enumerate(order)}
        L2 = [(mp[c], 0, "조건")] + [(mp[s], 1, m) for s, _, m in L[1:]]
        out.append((" ".join(x[2] for x in segs2), L2, segs2))
    return out

def build(train_items, seed=0):
    rnd = random.Random(seed)
    act_pool = [segs[0][2] for _, _, L, segs in train_items if len(segs) == 1 and segs[0][0] == "ACT"]
    if not act_pool: act_pool = ["스피커로 알려줘.", "거실 조명을 꺼줘.", "창문을 열어줘."]
    f = fillers(rnd.sample(train_items, min(120, len(train_items))), rnd)
    r = refs(train_items, act_pool, rnd); rnd.shuffle(r); r = r[:100]
    p = postposed(train_items, rnd); rnd.shuffle(p); p = p[:80]
    return f, r, p

if __name__ == "__main__":
    import sys, os, json
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from candidates import render
    from box import assemble_tree, gold_flags, assemble
    from skeleton import skeleton
    from candidates import tree_to_lines
    T = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "type", "type_labels.json")))
    items = []
    for o in T:
        if not o["ir_gt"]: continue
        segs = [(s["type"], s["mods"], s["text"]) for s in o["segments"]]
        cron, cyc = gold_flags(o["ir_gt"])
        if assemble(segs, cron, cyc) != skeleton(o["ir_gt"]): continue
        items.append((o["i"], o["cmd"], tree_to_lines(assemble_tree(segs, cron, cyc), segs), segs))
    train = [it for it in items if it[0] % 5 != 0]
    f, r, p = build(train)
    print("필러", len(f), "REF", len(r), "후치", len(p))
    for grp in (f[:3], r[:3], p[:3]):
        for cmd, L, segs in grp:
            print("-" * 40); print(cmd); print(render(L, segs))
