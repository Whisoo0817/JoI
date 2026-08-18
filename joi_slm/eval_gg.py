# -*- coding: utf-8 -*-
"""G/G 평가 — gold 경계·타입·mods + experiments 매핑(ranked.json·cond_parts.json, 5-fold 예문 확장) → 380 명령 계층 채점.
    python -m joi_slm.eval_gg      (리포 루트에서)"""
import os, json, collections
import numpy as np
from .train import EXP, labels
from .builder import build, Mapping
from .evaluate import grade, gold_fix
def h6_of():
    H = np.load(os.path.join(EXP, "head", "states.npz")); L = list(H["layers"]).index(6)
    row = {(int(c), int(w)): r for r, (c, w) in enumerate(zip(H["cmd_idx"], H["word_pos"]))}
    return lambda i, w: H["X"][row[(i, w)], L].astype(np.float32).tolist() if (i, w) in row else None
if __name__ == "__main__":
    T, G = labels(); R = {r["cmd"]: r for r in json.load(open(os.path.join(EXP, "map", "ranked.json")))}
    CP = json.load(open(os.path.join(EXP, "map", "cond_parts.json"))); h6 = h6_of()
    res = collections.Counter(); slot = collections.defaultdict(list); fails = []
    for o in T:
        if o["cmd"] not in R or o["cmd"] not in G: continue
        segs, k = [], 0
        for s in o["segments"]:
            k += len(s["text"].split()); v = h6(o["i"], k - 1)
            segs.append({**s, **({"h6": v} if v is not None else {})})
        M = Mapping({s["j"]: s["ranked"] for s in R[o["cmd"]]["segs"]}, CP.get(o["cmd"], {}), {s["j"]: s["text"] for s in o["segments"]})
        r, sl = grade(build(segs, M), gold_fix(o["cmd"], G[o["cmd"]]), o["cmd"]); res[r] += 1
        for kk, v in sl.items(): slot[kk] += v
        if r != "OK": fails.append((r, o["cmd"]))
    n = sum(res.values()); ok = res["OK"]
    print(f"명령 {n}: 완전 IR {ok}/{n} = {ok/n:.3f}  실패 {dict(res)}")
    for kk, v in slot.items(): print(f"  {kk:8s} {sum(v)}/{len(v)} = {sum(v)/len(v):.3f}")
    for f in fails: print("  ", f)
