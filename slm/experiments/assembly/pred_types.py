# -*- coding: utf-8 -*-
"""타입·mods head OOF 예측 저장 (ctx_last L6, PCA256, 명령 단위 5-fold).
gold 경계의 절과 경계 head 예측 경계(pred_segs)의 절 둘 다에 대해 예측 → pred_types.json
"""
import json, os, re, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
H = np.load(os.path.join(HERE, "..", "head", "states.npz"))
LAYERS = list(H["layers"]); LI = LAYERS.index(6)
HX = H["X"][:, LI].astype(np.float32)
row_of = {(c, t): i for i, (c, t) in enumerate(zip(H["cmd_idx"], H["word_pos"]))}
MODS = ["time", "read", "every", "sustain", "count", "else", "repeat", "delay", "mixed"]

def spans(labels):
    starts = [k for k, l in enumerate(labels) if l == 1 or k == 0]
    return list(zip(starts, starts[1:] + [len(labels)]))

X, y, ym, grp, keys = [], [], [], [], []
for o in T:
    for s, (a, b) in zip(o["segments"], spans(o["gold_labels"])):
        X.append(HX[row_of[(o["i"], b - 1)]]); y.append(s["type"]); ym.append([int(m in s["mods"]) for m in MODS]); grp.append(o["i"])
X = np.array(X); y = np.array(y); ym = np.array(ym); grp = np.array(grp)
out = {o["i"]: {"gold": [], "pred": []} for o in T}
for tr, te in GroupKFold(5).split(X, y, grp):
    sc = StandardScaler().fit(X[tr]); pca = PCA(256, random_state=0).fit(sc.transform(X[tr]))
    f = lambda A: pca.transform(sc.transform(A))
    clf = LogisticRegression(max_iter=1000, C=0.5).fit(f(X[tr]), y[tr])
    mclf = [LogisticRegression(max_iter=1000, C=0.5).fit(f(X[tr]), ym[tr, k]) if ym[tr, k].sum() else None for k in range(len(MODS))]
    for ci in sorted(set(grp[te])):
        o = T[ci]
        for key, labels, texts in (("gold", o["gold_labels"], [s["text"] for s in o["segments"]]),
                                   ("pred", o["pred_labels"], o["pred_segs"])):
            sp = spans(labels)
            V = np.stack([HX[row_of[(ci, b - 1)]] for a, b in sp])
            ty = clf.predict(f(V))
            md = np.stack([m.predict(f(V)) if m is not None else np.zeros(len(V), int) for m in mclf], 1)
            out[ci][key] = [{"text": t, "type": str(tt), "mods": [MODS[k] for k in range(len(MODS)) if md[r, k]]}
                            for r, (t, tt) in enumerate(zip(texts, ty))]
json.dump(out, open(os.path.join(HERE, "pred_types.json"), "w"), ensure_ascii=False, indent=1)
acc = np.mean([p["type"] == s["type"] for o in T for p, s in zip(out[o["i"]]["gold"], o["segments"])])
macc = np.mean([set(p["mods"]) == set(s["mods"]) for o in T for p, s in zip(out[o["i"]]["gold"], o["segments"])])
print("gold 경계 절 타입 OOF 정확도 %.3f, mods 집합 완전일치 %.3f" % (acc, macc))
