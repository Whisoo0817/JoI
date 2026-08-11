# -*- coding: utf-8 -*-
"""Does right context help or hurt word-level judgments on the 2B model?

Conditions per word t:
  pos    : position fraction only (sanity baseline)
  C0     : causal state of word t                     (k=0, left-only)
  C1     : C0 + causal state of word t+1              (wait-1)
  C2     : C1 + t+2                                   (wait-2)
  C4     : C2 + t+3 + t+4                             (wait-4)
  CF     : C0 + full-context (echo) state of word t   (causal + everything)
  Fonly  : full-context state alone
Tasks:
  A boundary  : is there a clause boundary right after word t? (suffix-derived)
  B go-role   : word ends in -고: condition-side (a later word ends -면) vs action-side
"""
import json, re
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

D = np.load("waitk_states.npz")
meta = json.load(open("waitk_meta.json"))
X1, X2 = D["X1"].astype(np.float32), D["X2"].astype(np.float32)
cmd_idx, word_pos, LAYERS = D["cmd_idx"], D["word_pos"], list(D["layers"])
words = meta["words"]

# per-command row ranges
n_words = {}
for i, c in enumerate(cmd_idx):
    n_words[c] = max(n_words.get(c, 0), word_pos[i] + 1)
row_of = {(c, t): i for i, (c, t) in enumerate(zip(cmd_idx, word_pos))}

BOUND = re.compile(r"(면|고|서|거나|는데|후에|때|자마자|다음에?)[,]?$")
GO = re.compile(r"고[,]?$")
MYEON = re.compile(r"면[,]?$")

samples_A, samples_B = [], []
for c, n in n_words.items():
    ws = [words[row_of[(c, t)]] for t in range(n)]
    for t in range(n - 1):
        samples_A.append((c, t, n, int(bool(BOUND.search(ws[t])))))
        if GO.search(ws[t]):
            y = int(any(MYEON.search(ws[j]) for j in range(t + 1, n)))
            samples_B.append((c, t, n, y))

def feats(sm, li, cond):
    Z = []
    d = X1.shape[2]
    for c, t, n, _ in sm:
        def s1(tt):
            return X1[row_of[(c, tt)], li] if tt < n else np.zeros(d, np.float32)
        v = {"pos": np.array([t / (n - 1)], np.float32),
             "C0": s1(t),
             "C1": np.concatenate([s1(t), s1(t + 1)]),
             "C2": np.concatenate([s1(t), s1(t + 1), s1(t + 2)]),
             "C4": np.concatenate([s1(t), s1(t + 1), s1(t + 2), s1(t + 3), s1(t + 4)]),
             "CF": np.concatenate([s1(t), X2[row_of[(c, t)], li]]),
             "Fonly": X2[row_of[(c, t)], li]}[cond]
        Z.append(v)
    return np.stack(Z)

def run(sm, li, cond):
    y = np.array([s[3] for s in sm])
    g = np.array([s[0] for s in sm])
    X = feats(sm, li, cond)
    oof = np.zeros(len(y), int)
    for tr, te in GroupKFold(n_splits=5).split(X, y, g):
        sc = StandardScaler().fit(X[tr])
        clf = LogisticRegression(max_iter=3000, C=1.0).fit(sc.transform(X[tr]), y[tr])
        oof[te] = clf.predict(sc.transform(X[te]))
    acc = (oof == y).mean()
    tp = ((oof == 1) & (y == 1)).sum()
    f1 = 2 * tp / max((oof == 1).sum() + (y == 1).sum(), 1)
    return acc, f1

CONDS = ["pos", "C0", "C1", "C2", "C4", "CF", "Fonly"]
for name, sm in [("A:boundary", samples_A), ("B:go-role", samples_B)]:
    y = np.array([s[3] for s in sm])
    print(f"\n=== Task {name}  n={len(sm)}  pos-rate={y.mean():.3f}  (majority acc={max(y.mean(),1-y.mean()):.3f}) ===")
    print(f"{'layer':>6} | " + " | ".join(f"{c:>11}" for c in CONDS) + "   (acc/F1)")
    for li, L in enumerate(LAYERS):
        cells = []
        for cond in CONDS:
            acc, f1 = run(sm, li, cond)
            cells.append(f"{acc:.3f}/{f1:.3f}")
        print(f"L{L:>5} | " + " | ".join(f"{c:>11}" for c in cells))
