# -*- coding: utf-8 -*-
"""존댓말·격식·'경우/때' 종결 합성 증강 — gold 절(type_labels.json)의 어미를 규칙으로 바꿔 새 명령을 만든다(경계·타입·mods 계승).
§27 패러프레이즈 실패(경계 29·타입 14)가 "-줘" 편중에서 온다는 진단에 대한 처치. 명령당 VAR개 변형. 출력 aug_polite.json (aug_nominal.json 스키마 + mods)."""
import json, os, re, random
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "type_labels.json")))
random.seed(1); VAR = int(os.environ.get("VAR", "2"))
ACT_END = [  # (정규식, 대체 후보들) — 절 끝(마침표 제거 후)
    (r"해줘$", ["해 주세요", "해주세요", "해 주십시오", "해 줄래?", "해줘요", "하도록 해줘", "하게 해 주세요", "해 주시겠어요?", "해 주시길 바랍니다", "하세요"]),
    (r"해주고,?$", ["해 주시고,", "하시고,", "한 다음,", "한 뒤에,"]),
    (r"켜줘$", ["켜 주세요", "켜주십시오", "켜 줄래?", "틀어줘", "틀어 주세요", "켜주세요", "켜 주시겠어요?", "켜라"]),
    (r"꺼줘$", ["꺼 주세요", "꺼주십시오", "꺼 줄래?", "끄세요", "꺼주세요", "꺼 주시겠어요?", "꺼라"]),
    (r"(아|어|여|워|줘|려|해|워)줘$", [r"\1 주세요", r"\1주세요", r"\1 주십시오", r"\1 줄래?", r"\1줘요", r"\1 주시겠어요?"]),
    (r"(고|주고),?$", [r"\1 나서,", r"\1,", r"\1 난 다음,"]),
]
COND_END = [
    (r"되면,?$", ["될 경우,", "되는 경우,", "될 때,", "될 때는,", "되면요,", "되는 경우에는,"]),
    (r"감지되면,?$", ["감지될 경우,", "감지될 때,", "감지되는 경우,", "감지된다면,", "감지되었을 때,"]),
    (r"눌리면,?$", ["눌릴 경우,", "눌릴 때,", "눌린다면,", "눌렸을 때,"]),
    (r"열리면,?$", ["열릴 경우,", "열릴 때,", "열린다면,", "열렸을 때,"]),
    (r"닫히면,?$", ["닫힐 경우,", "닫힐 때,", "닫힌다면,"]),
    (r"이면,?$", ["인 경우,", "일 때,", "일 경우에는,", "이라면,", "인 상황이면,"]),
    (r"있으면,?$", ["있을 경우,", "있을 때,", "있다면,", "있는 경우,"]),
    (r"없으면,?$", ["없을 경우,", "없을 때,", "없다면,", "없는 경우,"]),
    (r"않으면,?$", ["않을 경우,", "않을 때,", "않는다면,", "않는 경우,"]),
    (r"넘으면,?$", ["넘을 경우,", "넘을 때,", "넘는다면,", "넘어서면,"]),
    (r"지면,?$", ["질 경우,", "질 때,", "진다면,"]),
    (r"오면,?$", ["올 경우,", "올 때,", "온다면,"]),
    (r"면,?$", ["면요,", "면,"]),
]
def strip_end(s): return s.strip().rstrip(".,")
def transform(seg):
    t, s = seg["type"], strip_end(seg["text"])
    rules = ACT_END if t == "ACT" else COND_END if t in ("COND", "TRIG", "STOP") else []
    for pat, reps in rules:
        if re.search(pat, s):
            return re.sub(pat, random.choice(reps), s)
    return None
out = []
for o in T:
    for v in range(VAR):
        new, changed = [], 0
        for sg in o["segments"]:
            n = transform(sg)
            if n and n != strip_end(sg["text"]): new.append((n, sg["type"], sg["mods"])); changed += 1
            else: new.append((strip_end(sg["text"]), sg["type"], sg["mods"]))
        if not changed: continue
        # 절 사이 공백/쉼표 유지: 원문처럼 쉼표로 끝난 절은 쉼표 그대로, 마지막 절 마침표
        words, labels, segs, types, mods = [], [], [], [], []
        for k, (txt, ty, md) in enumerate(new):
            txt = txt.rstrip(",") + ("," if k < len(new) - 1 and random.random() < 0.5 else "") if k < len(new) - 1 else txt.rstrip(",") + "."
            ws = txt.split(); words += ws; labels += [1 if (k > 0 and i == 0) else 0 for i in range(len(ws))]
            segs.append(" ".join(ws)); types.append(ty); mods.append(md)
        labels[0] = 0
        cmd = " ".join(words)
        if any(x["cmd"] == cmd for x in out): continue
        out.append({"cmd": cmd, "cat": o["cat"], "words": words, "labels": labels, "segs": segs, "types": types, "mods": mods, "src": o["i"]})
json.dump(out, open(os.path.join(HERE, "aug_polite.json"), "w"), ensure_ascii=False, indent=1)
print("합성 명령", len(out), "원본", len({x["src"] for x in out}))
for x in random.sample(out, 10): print("  " + " ‖ ".join(f"[{t}] {s}" for s, t in zip(x["segs"], x["types"])))
