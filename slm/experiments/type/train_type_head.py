# -*- coding: utf-8 -*-
"""절 타입 head(8지선다) + mods(다중라벨) — 로지스틱, 명령 단위 5조각 교차검증.

절 표현 후보:
  ctx_last  문맥 속 절 마지막 단어의 표현 (head/states.npz — 문장 통째 prefill 1회, 추가 비용 0)
  ctx_first+last  문맥 속 절 첫 단어 + 마지막 단어 표현 연결
  solo_last 절만 떼어 재인코딩한 마지막 토큰 표현 (seg_states.npz)
  solo_mean 절만 떼어 재인코딩, 토큰 평균
"""
import json, os, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import f1_score

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "type_labels.json")))
H = np.load(os.path.join(HERE, "..", "head", "states.npz"))
S = np.load(os.path.join(HERE, "seg_states.npz"))
LAYERS = list(H["layers"]); assert LAYERS == list(S["layers"])
HX = H["X"]; S_last = S["last"]; S_mean = S["mean"]  # npz는 접근마다 압축을 푸므로 한 번만 꺼내 둔다
row_of = {(c, t): i for i, (c, t) in enumerate(zip(H["cmd_idx"], H["word_pos"]))}

# 절 → 문맥 속 단어 범위
segs = []
for o in T:
    starts = [k for k, l in enumerate(o["gold_labels"]) if l == 1 or k == 0]
    ends = starts[1:] + [len(o["words"])]
    for s, (a, b) in zip(o["segments"], zip(starts, ends)):
        segs.append(dict(cmd=o["i"], j=s["j"], a=a, b=b - 1, type=s["type"], mods=s["mods"]))
assert len(segs) == len(S["cmd"])
groups = np.array([s["cmd"] for s in segs])
y = np.array([s["type"] for s in segs])
TYPES = sorted(set(y))
MODS = ["time", "read", "every", "sustain", "count", "else", "repeat"]
Y_mods = {m: np.array([m in s["mods"] for s in segs], int) for m in MODS}

def feat(kind, li):
    if kind == "ctx_last":
        return np.stack([HX[row_of[(s["cmd"], s["b"])], li] for s in segs]).astype(np.float32)
    if kind == "ctx_first+last":
        return np.stack([np.concatenate([HX[row_of[(s["cmd"], s["a"])], li], HX[row_of[(s["cmd"], s["b"])], li]]) for s in segs]).astype(np.float32)
    if kind == "solo_last":
        return S_last[:, li].astype(np.float32)
    if kind == "solo_mean":
        return S_mean[:, li].astype(np.float32)

def cv(Z, yy, C=0.5):
    oof = np.empty(len(yy), dtype=object) if yy.dtype.kind in "OU" else np.zeros(len(yy), int)
    for tr, te in GroupKFold(5).split(Z, yy, groups):
        sc = StandardScaler().fit(Z[tr]); pca = PCA(256, random_state=0).fit(sc.transform(Z[tr]))
        f = lambda A: pca.transform(sc.transform(A))
        clf = LogisticRegression(max_iter=1000, C=C).fit(f(Z[tr]), yy[tr])
        oof[te] = clf.predict(f(Z[te]))
    return oof

print("절 %d개, 타입 분포 %s" % (len(segs), dict(collections.Counter(y))))
print("\n== 타입 8지선다: 정확도 / macro-F1 (층별) ==")
best = None
for kind in ("ctx_last", "ctx_first+last", "solo_last", "solo_mean"):
    row = []
    for li, L in enumerate(LAYERS):
        if L not in (2, 6, 12):
            continue
        oof = cv(feat(kind, li), y)
        acc = (oof == y).mean(); mf = f1_score(y, oof, average="macro")
        row.append("L%d %.3f/%.3f" % (L, acc, mf))
        if best is None or acc > best[0]:
            best = (acc, kind, L, oof)
    print("%-15s " % kind + "  ".join(row))

acc, kind, L, oof = best
print("\n최고: %s L%d 정확도 %.3f" % (kind, L, acc))
print("클래스별 (정답 n / 재현율 / 정밀도):")
for t in TYPES:
    m = y == t; p = oof == t
    print("  %-5s n=%3d  재현 %.3f  정밀 %.3f" % (t, m.sum(), (oof[m] == t).mean(), (y[p] == t).mean() if p.sum() else float("nan")))
conf = collections.Counter((a, b) for a, b in zip(y, oof) if a != b)
print("혼동 상위:", conf.most_common(10))
print("\n틀린 절 (최고 조합):")
for s, a, b in zip(segs, y, oof):
    if a != b:
        print("  %s→%s  %s" % (a, b, T[s["cmd"]]["segments"][s["j"]]["text"]))

print("\n== mods 이진 head (%s L%d 표현): F1 ==" % (kind, L))
Z = feat(kind, LAYERS.index(L))
for m in MODS:
    yy = Y_mods[m]
    oof_m = cv(Z, yy)
    print("  %-8s n=%3d  F1 %.3f  (놓침 %d, 과잉 %d)" % (m, yy.sum(), f1_score(yy, oof_m), int(((oof_m == 0) & (yy == 1)).sum()), int(((oof_m == 1) & (yy == 0)).sum())))
