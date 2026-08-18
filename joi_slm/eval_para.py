# -*- coding: utf-8 -*-
"""텍스트만 입력하는 종단 평가 — 원문 80 + 직접 작성 패러프레이즈 160(experiments/para/para_claude.json), 매핑 예문은 같은 원본 명령 제외(held-out).
    python -m joi_slm.eval_para [--no-gates]     (리포 루트에서; 게이트는 vLLM 9B 필요)"""
import os, sys, json, collections
from .train import EXP, labels
from .pipeline import CommandToIR
from .evaluate import grade, gold_fix
if __name__ == "__main__":
    import pandas as pd
    T, G = labels(); byi = {o["i"]: o for o in T}
    P = pd.read_csv(os.path.join(EXP, "map", "dataset_paper.csv")); DEV = {r.command_kor: json.loads(r.connected_devices) for r in P.itertuples()}
    para = json.load(open(os.path.join(EXP, "para", "para_claude.json")))
    pipe = CommandToIR(gates="--no-gates" not in sys.argv)
    res = collections.defaultdict(collections.Counter); out = []
    for x in para:
        o = byi[x["i"]]; gold = gold_fix(o["cmd"], G[o["cmd"]])
        for grp, text in [("orig", o["cmd"])] + [("para", p) for p in x["para"]]:
            r = pipe(text, DEV.get(o["cmd"]), exclude={o["i"]}); g, _ = grade(r["ir"], gold, o["cmd"]); res[grp][g] += 1
            out.append({"grp": grp, "i": o["i"], "text": text, "result": g, "segments": r["segments"], "graph": r["graph"], "ir": r["ir"]})
    for grp, c in res.items():
        n = sum(c.values()); print(f"{grp} n={n}  완전 IR {c['OK']}/{n} = {c['OK']/n:.3f}  {dict(c)}")
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_para_out.json"), "w"), ensure_ascii=False, indent=1)
