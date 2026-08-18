# -*- coding: utf-8 -*-
"""층별 프로빙 — 구조 정보가 2B의 어느 깊이에 있나.
 (a) 범위 부모: 절 i의 부모가 절 j인가 (쌍 분류 → argmax 부모 정확도), 정상 vs 조건 후치(뒤→앞 부모) 분리 보고
 (b) 선후 방향: after/before 항목의 새 행동 절 D 표현 → "앵커보다 먼저 실행"인가 (D는 접속어미를 갖지 않음 → 문맥에서 와야 함)
 (c) 선행사: 참조 절 → 앞 행동 절 중 앵커 (cos 제로샷 acc@1 / 쌍 로지스틱), 어휘 중복 기준선; 후보 ≥2 항목만
 (d) 필러: 절 표현 → 필러인가
 (e) 실행 순서 역전 쌍: (D, C) 쌍 표현 → D가 C보다 먼저인가 (before) / 뒤인가 (after·normal 인접쌍)
GroupKFold(src) 5조각, PCA256(층별, 비지도) + 로지스틱.
"""
import json, os, sys, collections, re
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "pairs.json")))
S = np.load(os.path.join(HERE, "pairs_states.npz"))
LAYERS = list(S["layers"]); XL = S["last"].astype(np.float32); XF = S["first"].astype(np.float32)
idx = {}
for r, (p, c) in enumerate(zip(S["pid"], S["cid"])): idx[(int(p), int(c))] = r
REP = os.environ.get("REP", "last"); X = XL if REP == "last" else XF
Z = {}   # 층별 PCA256
for li, L in enumerate(LAYERS):
    sc = StandardScaler().fit(X[:, li]); Z[L] = PCA(256, random_state=0).fit_transform(sc.transform(X[:, li])).astype(np.float32)
def h(L, p, c): return Z[L][idx[(p, c)]]

def cv_acc(F, y, g, C=0.5):
    F = np.array(F, np.float32); y = np.array(y); g = np.array(g); oof = np.zeros(len(y), int)
    for tr, te in GroupKFold(5).split(F, y, g):
        clf = LogisticRegression(max_iter=2000, C=C).fit(F[tr], y[tr]); oof[te] = clf.predict(F[te])
    return oof

def cv_scores(F, y, g, C=0.5):
    F = np.array(F, np.float32); y = np.array(y); g = np.array(g); oof = np.zeros(len(y))
    for tr, te in GroupKFold(5).split(F, y, g):
        clf = LogisticRegression(max_iter=2000, C=C).fit(F[tr], y[tr]); oof[te] = clf.decision_function(F[te])
    return oof

def words(s): return set(re.sub(r"[.,\"']", "", s).split())

print(f"표현: 절 {REP} 토큰 | 층 {LAYERS}")
# ── (a) 범위 부모 ─────────────────────────────────────────────
print("\n(a) 범위 부모 argmax 정확도 (부모 있는 절만; 후보 = 같은 명령의 다른 절 + ROOT)")
for L in LAYERS:
    F, y, g, meta = [], [], [], []
    for p, x in enumerate(P):
        if x["kind"] not in ("normal", "post"): continue
        n = len(x["segs"])
        for i in range(n):
            if x["role"][i] == "filler": continue
            for j in range(n):
                if j == i: continue
                hi, hj = h(L, p, i), h(L, p, j)
                F.append(np.concatenate([hi, hj, hi * hj])); y.append(int(x["parent"][i] == j)); g.append(x["src"]); meta.append((p, i, j))
    sc = cv_scores(F, y, g)
    # argmax per (p,i) among j (ROOT = 임계 0 미만 전부)
    best = {}
    for s_, (p, i, j) in zip(sc, meta):
        if (p, i) not in best or s_ > best[(p, i)][0]: best[(p, i)] = (s_, j)
    res = collections.defaultdict(lambda: [0, 0])
    for (p, i), (s_, j) in best.items():
        x = P[p]; gold = x["parent"][i]
        pred = j if s_ > 0 else -1
        k = x["kind"] + ("(뒤→앞)" if x["kind"] == "post" and gold > i else "")
        res[k][1] += 1; res[k][0] += int(pred == gold)
    print(f"  L{L:2d}: " + "  ".join(f"{k} {v[0]}/{v[1]}={v[0]/v[1]:.3f}" for k, v in sorted(res.items())))

# ── (b) 선후 방향 (D 절) ─────────────────────────────────────
print("\n(b) 새 행동 절 D의 표현 → 앵커보다 먼저 실행? (before=1 / after=0)")
for L in LAYERS:
    F, y, g = [], [], []
    for p, x in enumerate(P):
        if x["kind"] not in ("after", "before"): continue
        d = len(x["segs"]) - 1
        F.append(h(L, p, d)); y.append(int(x["kind"] == "before")); g.append(x["src"])
    oof = cv_acc(F, y, g); print(f"  L{L:2d}: acc {np.mean(oof == np.array(y)):.3f}  (n={len(y)})")

# ── (c) 선행사 ───────────────────────────────────────────────
print("\n(c) 참조 절의 선행사 (앞 행동 절 ≥2인 항목만): cos 제로샷 acc@1 / 쌍 로지스틱 acc@1 / 어휘중복 기준선 / 직전절 기준선")
for KINDS in (("after", "before"), ("event",)):
  print("  종류", KINDS)
  for L in LAYERS:
      zs = lg = lex = adj = 0; n = 0; F, y, g, meta = [], [], [], []
      for p, x in enumerate(P):
          if x["kind"] not in KINDS: continue
          r = next(int(k) for k in x["anchor"]); a = x["anchor"][str(r)][0]
          cands = [j for j in range(r) if x["role"][j] == "act" and x["types"][j] == "ACT"]
          if len(cands) < 2: continue
          n += 1; adj += int(a == cands[-1])
          hr = h(L, p, r); cs = [float(hr @ h(L, p, j) / (np.linalg.norm(hr) * np.linalg.norm(h(L, p, j)) + 1e-6)) for j in cands]
          zs += int(cands[int(np.argmax(cs))] == a)
          ov = [len(words(x["segs"][r]) & words(x["segs"][j])) for j in cands]; lex += int(cands[int(np.argmax(ov))] == a)
          for j in cands:
              hj = h(L, p, j); F.append(np.concatenate([hr * hj, np.abs(hr - hj)])); y.append(int(j == a)); g.append(x["src"]); meta.append((p, r, j))
      sc = cv_scores(F, y, g); best = {}
      for s_, (p, r, j) in zip(sc, meta):
          if (p, r) not in best or s_ > best[(p, r)][0]: best[(p, r)] = (s_, j)
      lg = sum(int(j == P[p]["anchor"][str(r)][0]) for (p, r), (s_, j) in best.items())
      print(f"  L{L:2d}: cos {zs}/{n}={zs/n:.3f}  로지스틱 {lg}/{n}={lg/n:.3f}  어휘 {lex}/{n}={lex/n:.3f}  직전절 {adj}/{n}={adj/n:.3f}")

# ── (d) 필러 ─────────────────────────────────────────────────
print("\n(d) 필러 절 판별 (filler 항목의 모든 절)")
for L in LAYERS:
    F, y, g = [], [], []
    for p, x in enumerate(P):
        if x["kind"] != "filler": continue
        for i in range(len(x["segs"])): F.append(h(L, p, i)); y.append(int(x["role"][i] == "filler")); g.append(x["src"])
    oof = cv_acc(F, y, g); y = np.array(y)
    tp = ((oof == 1) & (y == 1)).sum(); print(f"  L{L:2d}: acc {np.mean(oof == y):.3f}  필러 재현 {tp/(y==1).sum():.3f} 정밀 {tp/max((oof==1).sum(),1):.3f}")

# ── (e) 역전 쌍 ──────────────────────────────────────────────
print("\n(e) (D, 앵커 C) 쌍 표현 → D가 C보다 먼저? before=1 vs after=0 (+ normal 인접 행동쌍은 0)")
for L in LAYERS:
    F, y, g = [], [], []
    for p, x in enumerate(P):
        if x["kind"] in ("after", "before"):
            r = next(int(k) for k in x["anchor"]); a = x["anchor"][str(r)][0]; d = len(x["segs"]) - 1
            hd, hc = h(L, p, d), h(L, p, a); F.append(np.concatenate([hd, hc, hd * hc])); y.append(int(x["kind"] == "before")); g.append(x["src"])
        elif x["kind"] == "normal":
            ex = x["exec"]
            for u, v in zip(ex, ex[1:]):
                if x["role"][u] == "act" and x["role"][v] == "act":
                    hd, hc = h(L, p, v), h(L, p, u); F.append(np.concatenate([hd, hc, hd * hc])); y.append(0); g.append(x["src"])
    oof = cv_acc(F, y, g); y = np.array(y)
    print(f"  L{L:2d}: acc {np.mean(oof == y):.3f}  before 재현 {((oof==1)&(y==1)).sum()/(y==1).sum():.3f}  (n={len(y)}, before {int((y==1).sum())})")
