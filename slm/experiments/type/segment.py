# -*- coding: utf-8 -*-
"""1단계: 경계 head로 382개 명령을 실제로 절 분할하고 결과를 저장.

- head/states.npz(2B 내부표현) + head/labels.json(경계 정답)을 읽어
  최고 조합(직전+현재 단어, 얕은 층)으로 5조각 교차검증 예측(oof)을 만든다.
  → 각 명령의 예측 절은 "그 명령을 학습에 안 쓴 head"가 자른 것.
- 저장: segments.json — 명령별 {words, gold_labels, pred_labels, gold_segs, pred_segs,
  match(완전일치 여부), ops, ir_gt}. 이 파일이 2단계(타입 라벨링)의 입력.
"""
import json, os
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
HEAD = os.path.join(HERE, "..", "head")
ROOT = os.path.join(HERE, "..", "..", "..")
LAYER = 2  # 경계 head 최적 층(§9)

D = np.load(os.path.join(HEAD, "states.npz"))
X, cmd_idx, word_pos, y = D["X"].astype(np.float32), D["cmd_idx"], D["word_pos"], D["y"]
LAYERS = list(D["layers"])
li = LAYERS.index(LAYER)
items = json.load(open(os.path.join(HEAD, "labels.json")))
df = pd.read_csv(os.path.join(ROOT, "dataset.csv"))
ir_by_cmd = dict(zip(df["command_kor"], df["ir_gt"]))
idx_by_cmd = dict(zip(df["command_kor"], df["index"]))

row_of = {(c, t): i for i, (c, t) in enumerate(zip(cmd_idx, word_pos))}
samples = [(c, t) for c, t in zip(cmd_idx, word_pos) if t >= 1]
ys = np.array([y[row_of[(c, t)]] for c, t in samples])
groups = np.array([c for c, _ in samples])
Z = np.stack([np.concatenate([X[row_of[(c, t - 1)], li], X[row_of[(c, t)], li]]) for c, t in samples])

oof = np.zeros(len(ys), int); prob = np.zeros(len(ys))
for tr, te in GroupKFold(5).split(Z, ys, groups):
    sc = StandardScaler().fit(Z[tr])
    clf = LogisticRegression(max_iter=2000, C=1.0).fit(sc.transform(Z[tr]), ys[tr])
    oof[te] = clf.predict(sc.transform(Z[te]))
    prob[te] = clf.predict_proba(sc.transform(Z[te]))[:, 1]

pred_by_cmd = {}
for i, (c, t) in enumerate(samples):
    pred_by_cmd.setdefault(c, {})[t] = (int(oof[i]), float(prob[i]))

def cut(words, labels):
    segs, cur = [], []
    for w, l in zip(words, labels):
        if l == 1 and cur:
            segs.append(" ".join(cur)); cur = []
        cur.append(w)
    if cur:
        segs.append(" ".join(cur))
    return segs

out, perfect = [], 0
for ci, it in enumerate(items):
    words = it["words"]
    gold = [0] + [int(x) for x in it["labels"][1:]]
    pred = [0] + [pred_by_cmd[ci][t][0] for t in range(1, len(words))]
    pr = [1.0] + [round(pred_by_cmd[ci][t][1], 3) for t in range(1, len(words))]
    match = gold == pred
    perfect += match
    out.append({
        "i": ci, "index": int(idx_by_cmd.get(it["cmd"], -1)), "cat": it["cat"], "cmd": it["cmd"],
        "words": words, "gold_labels": gold, "pred_labels": pred, "pred_prob": pr,
        "gold_segs": cut(words, gold), "pred_segs": cut(words, pred), "match": match,
        "ops": it.get("ops"), "ir_gt": json.loads(ir_by_cmd[it["cmd"]]) if it["cmd"] in ir_by_cmd else None,
    })

tp = int(((oof == 1) & (ys == 1)).sum()); fp = int(((oof == 1) & (ys == 0)).sum()); fn = int(((oof == 0) & (ys == 1)).sum())
print("경계 head(L%d, 직전+현재) oof: 정밀 %.3f 재현 %.3f, 명령 완전일치 %d/%d" %
      (LAYER, tp / (tp + fp), tp / (tp + fn), perfect, len(items)))
print("gold 절 %d개, 예측 절 %d개, ir_gt 없음 %d" %
      (sum(len(o["gold_segs"]) for o in out), sum(len(o["pred_segs"]) for o in out),
       sum(o["ir_gt"] is None for o in out)))
json.dump(out, open(os.path.join(HERE, "segments.json"), "w"), ensure_ascii=False, indent=1)
print("저장:", os.path.join(HERE, "segments.json"))
