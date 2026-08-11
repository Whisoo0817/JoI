# -*- coding: utf-8 -*-
"""절 경계 분류기(head) 학습 + 교차검증 평가.

- 판단: 단어 t가 새 절의 시작인가 (1/0)
- 입력 후보 3가지: 현재 단어의 내부표현만 / 직전+현재 / 직전+현재+다음(한 단어 미리보기)
- 평가는 5조각 교차검증, 조각은 '명령 단위'로 나눠서 같은 명령이 학습과 평가에
  동시에 들어가는 일이 없게 함
"""
import json, os
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
D = np.load(os.path.join(HERE, "states.npz"))
X, cmd_idx, word_pos, y = D["X"].astype(np.float32), D["cmd_idx"], D["word_pos"], D["y"]
LAYERS = list(D["layers"])
n, nlay, dim = X.shape
print("단어 %d개, 저장 층 %s, 벡터 %d차원" % (n, LAYERS, dim))

# 명령별 행 범위
row_of = {}
for i, (c, t) in enumerate(zip(cmd_idx, word_pos)):
    row_of[(c, t)] = i
n_words = {}
for c, t in zip(cmd_idx, word_pos):
    n_words[c] = max(n_words.get(c, 0), t + 1)

# 판단 대상: t >= 1 (첫 단어는 정의상 절 시작)
samples = [(c, t) for c, t in zip(cmd_idx, word_pos) if t >= 1]
ys = np.array([y[row_of[(c, t)]] for c, t in samples])
groups = np.array([c for c, _ in samples])
print("판단 대상 단어 %d개, 그중 경계 %d개 (%.1f%%)"
      % (len(ys), ys.sum(), 100 * ys.mean()))

def feats(li, mode):
    Z = np.zeros((len(samples), dim * (1 if mode == "cur" else 2 if mode == "prev" else 3)),
                 np.float32)
    for i, (c, t) in enumerate(samples):
        cur = X[row_of[(c, t)], li]
        if mode == "cur":
            Z[i] = cur; continue
        prv = X[row_of[(c, t - 1)], li]
        if mode == "prev":
            Z[i] = np.concatenate([prv, cur]); continue
        nxt = X[row_of[(c, t + 1)], li] if t + 1 < n_words[c] else np.zeros(dim, np.float32)
        Z[i] = np.concatenate([prv, cur, nxt])
    return Z

def evaluate(li, mode):
    Z = feats(li, mode)
    oof = np.zeros(len(ys), int)
    prob = np.zeros(len(ys))
    for tr, te in GroupKFold(5).split(Z, ys, groups):
        sc = StandardScaler().fit(Z[tr])
        clf = LogisticRegression(max_iter=2000, C=1.0).fit(sc.transform(Z[tr]), ys[tr])
        oof[te] = clf.predict(sc.transform(Z[te]))
        prob[te] = clf.predict_proba(sc.transform(Z[te]))[:, 1]
    tp = int(((oof == 1) & (ys == 1)).sum())
    fp = int(((oof == 1) & (ys == 0)).sum())
    fn = int(((oof == 0) & (ys == 1)).sum())
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    # 명령 단위 완전 일치
    perfect, total = 0, 0
    by_cmd = {}
    for i, (c, t) in enumerate(samples):
        by_cmd.setdefault(c, []).append(i)
    for c, idxs in by_cmd.items():
        total += 1
        if all(oof[i] == ys[i] for i in idxs):
            perfect += 1
    return prec, rec, f1, perfect / total, oof, prob

print("\n%-6s %-14s %8s %8s %8s %10s" % ("층", "입력", "정밀도", "재현율", "F1", "명령완전일치"))
best = None
for li, L in enumerate(LAYERS):
    for mode, name in (("cur", "현재만"), ("prev", "직전+현재"), ("next", "직전+현재+다음")):
        prec, rec, f1, pf, oof, prob = evaluate(li, mode)
        print("L%-5d %-14s %8.3f %8.3f %8.3f %10.3f" % (L, name, prec, rec, f1, pf))
        if best is None or f1 > best[0]:
            best = (f1, L, name, oof, prob)

f1, L, name, oof, prob = best
print("\n최고 조합: 층 L%d, 입력=%s (F1 %.3f)" % (L, name, f1))

# 최고 조합의 틀린 예 몇 개 저장/출력
items = json.load(open(os.path.join(HERE, "labels.json")))
print("\n== 틀린 판단 예시 (최고 조합, 교차검증 예측 기준) ==")
shown = 0
for i, (c, t) in enumerate(samples):
    if oof[i] != ys[i] and shown < 10:
        it = items[c]
        w = it["words"]
        mark = " ".join(("[" + x + "]") if j == t else x for j, x in enumerate(w))
        kind = "놓침(정답은 경계)" if ys[i] == 1 else "과잉(정답은 계속)"
        print("  %s  p=%.2f  %s" % (kind, prob[i], mark[:90]))
        shown += 1
