# -*- coding: utf-8 -*-
"""절 분할 head — 경계(층 2, 직전+현재 단어, 표준화+로지스틱) / 타입·mods(층 6 절 끝 단어, PCA256+로지스틱).
학습 데이터: experiments/head/states.npz + type/type_labels.json (+ 증강 aug_*.json/npz). 결과: assets/seg_heads.pkl"""
import json, os, pickle
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "seg_heads.pkl")
TYPES = ["ACT", "COND", "TRIG", "TIME", "DELAY", "READ", "ELSE", "STOP"]
MODS = ["time", "read", "every", "sustain", "count", "else", "repeat", "delay", "mixed", "state"]

class SegHeads:
    def __init__(self, scb, clf_b, sct, pca, clf_t, clf_m):
        self.scb, self.clf_b, self.sct, self.pca, self.clf_t, self.clf_m = scb, clf_b, sct, pca, clf_t, clf_m
    @classmethod
    def load(cls, path=ASSET): return cls(*pickle.load(open(path, "rb")))
    def save(self, path=ASSET): pickle.dump((self.scb, self.clf_b, self.sct, self.pca, self.clf_t, self.clf_m), open(path, "wb"))
    def boundary_proba(self, F2):
        """F2[n_words, 2048](층 2) → 각 단어가 새 절의 시작일 확률(첫 단어 1.0)"""
        if len(F2) == 1: return np.array([1.0])
        X = self.scb.transform(np.concatenate([F2[:-1], F2[1:]], 1))
        return np.concatenate([[1.0], self.clf_b.predict_proba(X)[:, 1]])
    def types(self, F6):
        """F6[n_segs, 2048](층 6 절 끝) → (types, p_max, mods 목록)"""
        V = self.pca.transform(self.sct.transform(F6)); pr = self.clf_t.predict_proba(V)
        ty = [str(self.clf_t.classes_[k]) for k in pr.argmax(1)]
        md = [[MODS[k] for k, m in enumerate(self.clf_m) if m is not None and m.predict(V[r:r + 1])[0] == 1] for r in range(len(V))]
        return ty, pr.max(1), md

def train_seg_heads(exp_dir, aug=("polite", "nominal", "post"), out=ASSET):
    """exp_dir = slm/experiments. 원본 382(states.npz, gold 경계·타입·mods) + 증강 세트(aug_<name>.json + 상태 npz)."""
    T = json.load(open(os.path.join(exp_dir, "type", "type_labels.json"))); TI = {o["i"]: o for o in T}
    H = np.load(os.path.join(exp_dir, "head", "states.npz")); HX = H["X"]; L = list(H["layers"]); LB, LT = L.index(2), L.index(6)
    row = {(int(c), int(t)): i for i, (c, t) in enumerate(zip(H["cmd_idx"], H["word_pos"]))}
    Xb, yb, Xt, yt, ym = [], [], [], [], []
    def add(get, labels, types, mods):
        n = len(labels)
        for t in range(1, n): Xb.append(np.concatenate([get(t - 1)[LB], get(t)[LB]])); yb.append(labels[t])
        starts = [k for k, l in enumerate(labels) if l == 1 or k == 0]; ends = starts[1:] + [n]
        for ty, md, e in zip(types, mods, ends): Xt.append(get(e - 1)[LT]); yt.append(ty); ym.append([int(m in md) for m in MODS])
    for ci, it in enumerate(T):
        add(lambda t, ci=ci: HX[row[(ci, t)]], it["gold_labels"], [s["type"] for s in it["segments"]], [s["mods"] for s in it["segments"]])
    for name in aug:
        A = json.load(open(os.path.join(exp_dir, "type", f"aug_{name}.json")))
        Z = np.load(os.path.join(exp_dir, "type", "aug_states.npz" if name == "nominal" else f"aug_{name}_states.npz")); ZX = Z["X"]
        zrow = {tuple(map(int, k)): i for i, k in enumerate(Z["idx"])}
        for ai, x in enumerate(A):
            mods = x.get("mods") or [s["mods"] for s in TI[x["src"]]["segments"]]
            if len(mods) == len(x["types"]): add(lambda t, ai=ai: ZX[zrow[(ai, t)]].astype(np.float32), x["labels"], x["types"], mods)
    Xb, yb, Xt, yt, ym = map(np.array, (Xb, yb, Xt, yt, ym))
    scb = StandardScaler().fit(Xb); clf_b = LogisticRegression(max_iter=2000, C=1.0).fit(scb.transform(Xb), yb)
    sct = StandardScaler().fit(Xt); pca = PCA(256, random_state=0).fit(sct.transform(Xt)); V = pca.transform(sct.transform(Xt))
    clf_t = LogisticRegression(max_iter=1000, C=0.5).fit(V, yt)
    clf_m = [LogisticRegression(max_iter=1000, C=0.5).fit(V, ym[:, k]) if ym[:, k].sum() else None for k in range(len(MODS))]
    h = SegHeads(scb, clf_b, sct, pca, clf_t, clf_m); h.save(out); return h, (len(Xb), len(Xt))
