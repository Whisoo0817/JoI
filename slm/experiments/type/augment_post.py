# -*- coding: utf-8 -*-
"""후치 합성 증강 — gold 명령에서 (a) ACT/time 절 앞머리의 시각 표현을 떼어 문장 끝으로 옮긴 판(TIME 절 라벨),
(b) 첫 COND/TRIG 절을 문장 끝으로 옮긴 판(조건 후치). 경계·타입·mods 라벨 계승. 출력 aug_post.json"""
import json, os, re, random
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "type_labels.json"))); random.seed(2)
TIME_PREFIX = re.compile(r"^((?:매일|평일|주말|월요일|화요일|수요일|목요일|금요일|토요일|일요일|크리스마스|새해|정오|자정)?\s*(?:(?:오전|오후|아침|저녁|밤|새벽|낮)\s*)?(?:\d{1,2}\s*시(?:\s*\d{1,2}\s*분|\s*반)?|정오|자정)(?:부터\s*(?:(?:오전|오후|아침|저녁|밤|새벽)\s*)?(?:\d{1,2}\s*시|정오|자정)까지)?(?:에|에는|가 되면|이 되면)?)\s+")
def strip_end(s): return s.strip().rstrip(".,")
out = []
def emit(new, src, kind):
    words, labels, segs, types, mods = [], [], [], [], []
    for k, (txt, ty, md) in enumerate(new):
        txt = strip_end(txt) + ("," if k < len(new) - 1 else ".")
        ws = txt.split(); words += ws; labels += [1 if (k > 0 and i == 0) else 0 for i in range(len(ws))]
        segs.append(" ".join(ws)); types.append(ty); mods.append(md)
    labels[0] = 0
    out.append({"cmd": " ".join(words), "cat": None, "words": words, "labels": labels, "segs": segs, "types": types, "mods": mods, "src": src, "kind": kind})
for o in T:
    S = o["segments"]
    # (a) 시각 후치: 첫 절이 ACT/time이고 앞머리가 시각 표현이면 떼어 뒤로
    s0 = S[0]
    if s0["type"] == "ACT" and "time" in s0["mods"] and len(S) <= 3:
        m = TIME_PREFIX.match(s0["text"])
        if m and len(m.group(1)) >= 3 and not re.search(r"마다|간격", m.group(1)):
            rest = s0["text"][m.end():]
            if rest.strip():
                new = [(rest, "ACT", [x for x in s0["mods"] if x != "time"])] + [(s["text"], s["type"], s["mods"]) for s in S[1:]] + [(m.group(1), "TIME", ["time"])]
                emit(new, o["i"], "time_post")
    # (b) 조건 후치: 첫 절이 COND/TRIG(sustain 제외)이고 나머지가 ACT뿐이면 뒤로
    if S[0]["type"] in ("COND", "TRIG") and len(S) >= 2 and all(s["type"] == "ACT" for s in S[1:]) and "sustain" not in S[0]["mods"] and random.random() < 0.7:
        new = [(s["text"], s["type"], s["mods"]) for s in S[1:]] + [(S[0]["text"], S[0]["type"], S[0]["mods"])]
        emit(new, o["i"], "cond_post")
json.dump(out, open(os.path.join(HERE, "aug_post.json"), "w"), ensure_ascii=False, indent=1)
import collections; print("합성", len(out), collections.Counter(x["kind"] for x in out))
for x in random.sample(out, 8): print("  " + " ‖ ".join(f"[{t}] {s}" for s, t in zip(x["segs"], x["types"])))
