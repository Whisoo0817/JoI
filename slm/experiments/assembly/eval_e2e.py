# -*- coding: utf-8 -*-
"""조립 종단 평가 — 상류 조건 3단계:
  G/G  gold 경계 + gold 타입·mods            (상자 규칙 자체의 상한)
  G/P  gold 경계 + 예측 타입·mods (OOF)
  P/P  예측 경계 + 예측 타입·mods (OOF)      (텍스트만 입력, 슬롯 플래그만 gold)
지표: 뼈대 완전일치 / 관대 일치(잎 다중도·WAIT↔IF 혼용 무시)
"""
import json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from box import assemble, gold_flags, lenient
from skeleton import skeleton
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
P = json.load(open(os.path.join(HERE, "pred_types.json")))
res = {}
for name in ("G/G", "G/P", "P/P"):
    tot = ok = okl = 0; fails = collections.Counter(); ex = []
    for o in T:
        if not o["ir_gt"]: continue
        if name == "G/G": segs = [(s["type"], s["mods"], s["text"]) for s in o["segments"]]
        elif name == "G/P": segs = [(s["type"], s["mods"], s["text"]) for s in P[str(o["i"])]["gold"]]
        else: segs = [(s["type"], s["mods"], s["text"]) for s in P[str(o["i"])]["pred"]]
        cron, cyc = gold_flags(o["ir_gt"])
        pred = assemble(segs, cron, cyc); gold = skeleton(o["ir_gt"])
        tot += 1
        if pred == gold: ok += 1; okl += 1
        elif lenient(pred) == lenient(gold): okl += 1
        else:
            gsig = " ".join(s["type"] + ("/" + ",".join(sorted(s["mods"])) if s["mods"] else "") for s in o["segments"])
            psig = " ".join(t + ("/" + ",".join(sorted(m)) if m else "") for t, m, _ in segs)
            why = "상자규칙" if gsig == psig else ("경계" if not o["seg_match"] and name == "P/P" else "타입/mods")
            fails[why] += 1; ex.append((why, o["cmd"], gsig, psig, gold, pred))
    res[name] = (ok, okl, tot)
    print(f"{name}: 완전일치 {ok}/{tot} ({ok/tot:.3f})  관대 {okl}/{tot} ({okl/tot:.3f})  실패 원인 {dict(fails)}")
    if name != "G/G":
        for e in ex:
            if e[0] != "상자규칙":
                print(f"   [{e[0]}] {e[1]}\n      gold {e[2]}\n      pred {e[3]}\n      {e[4]}  vs  {e[5]}")
