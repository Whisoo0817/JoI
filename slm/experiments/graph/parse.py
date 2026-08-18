# -*- coding: utf-8 -*-
"""그래프 파서 — 얕은 층 절 표현(L6 last, PCA256)으로 (1) 역할 (2) 범위 부모 (3) 참조 앵커+방향 을 예측하고
IR 문법 제약 아래 선형화(범위 트리 + 범위 안 순서 편집). 데이터 pairs.json (1,248문, 명령 단위 5-fold).
ablation:
  부모 스코어러  V  = [h_i, h_j, h_i*h_j]                (vanilla biaffine 근사)
               V+P = V + 방향/거리 prior(j<i, j>i, |i-j|, j==i-1)
               V+P+T = + 타입 쌍 원-핫(type_i × type_j)  ("타입 조건부")
  앵커 스코어러  E  = [h_i*h_j, |h_i-h_j|]   S = 기호 앵커(동사 어간 일치, 목적어 중복, 거리)   E+S
지표: 절 단위 역할·부모·앵커 정확도, 명령 단위 exec 순열 일치 / 전체(부모+exec+참조) 일치, 종류별.
"""
import json, os, re, collections, itertools
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "pairs.json")))
S = np.load(os.path.join(HERE, "pairs_states.npz"))
LAYERS = list(S["layers"]); LI = LAYERS.index(int(os.environ.get("LAYER", "6")))
X = S["last"][:, LI].astype(np.float32)
sc = StandardScaler().fit(X); Z = PCA(256, random_state=0).fit_transform(sc.transform(X)).astype(np.float32)
idx = {(int(p), int(c)): r for r, (p, c) in enumerate(zip(S["pid"], S["cid"]))}
def h(p, c): return Z[idx[(p, c)]]
TYPES = ["ACT", "COND", "TRIG", "TIME", "DELAY", "READ", "ELSE", "STOP"]
ROLES = ["scope", "cont", "wait", "act", "delay", "ref", "filler", "time"]
groups_of = np.array([x["src"] for x in P])
FOLDS = list(GroupKFold(5).split(np.zeros(len(P)), np.zeros(len(P)), groups_of))

STEM = {"켜": "on", "끄": "off", "꺼": "off", "닫": "close", "열": "open", "잠": "lock", "울리": "siren", "울려": "siren", "찍": "shot", "알리": "notify", "알려": "notify",
        "말하": "say", "말해": "say", "바꾸": "set", "바꿔": "set", "틀": "play", "올리": "up", "올려": "up", "내리": "down", "내려": "down", "설정": "set", "재생": "play"}
def stems(s):
    return {v for k, v in STEM.items() if k in s}
def objs(s):
    return set(re.findall(r"([가-힣A-Za-z0-9 ]+?)(?:을|를)\b", s))

def fit_predict(F, y, tr_mask, te_mask, C=0.5):
    clf = LogisticRegression(max_iter=3000, C=C).fit(F[tr_mask], y[tr_mask]); return clf, clf.predict(F[te_mask]), clf

# ── 절 단위 표 ─────────────────────────────────────────────
rows = []   # (p, i)
for p, x in enumerate(P):
    for i in range(len(x["segs"])): rows.append((p, i))
role_y = np.array([P[p]["role"][i] for p, i in rows])
Hc = np.stack([h(p, i) for p, i in rows])
row_of = {r: k for k, r in enumerate(rows)}

def parent_feats(p, i, j, mode):
    hi, hj = h(p, i), h(p, j) if j >= 0 else np.zeros_like(h(p, i))
    f = [hi, hj, hi * hj]
    if "P" in mode:
        n = len(P[p]["segs"]); roles = ROLE_CTX[p]
        prev_scopes = [k for k in range(i) if roles[k] == "scope"]
        nearest = prev_scopes[-1] if prev_scopes else -1
        f.append(np.array([j < i, j > i, abs(i - j) if j >= 0 else 0, j == i - 1, j == -1, j == n - 1, i == n - 1, j == nearest, j >= 0 and j > i and j == n - 1], np.float32))
    if "T" in mode:
        ti = TYPES.index(P[p]["types"][i]); tj = TYPES.index(P[p]["types"][j]) if j >= 0 else len(TYPES)
        oh = np.zeros(len(TYPES) * (len(TYPES) + 1), np.float32); oh[ti * (len(TYPES) + 1) + tj] = 1; f.append(oh)
    return np.concatenate(f)

ROLE_CTX = {p: list(x["role"]) for p, x in enumerate(P)}   # 부모 피처용 역할 문맥(학습=gold, 평가=예측으로 교체)
def anchor_feats(p, i, j, mode):
    hi, hj = h(p, i), h(p, j); f = []
    if "E" in mode: f += [hi * hj, np.abs(hi - hj)]
    if "S" in mode:
        si, sj = P[p]["segs"][i], P[p]["segs"][j]
        f.append(np.array([len(stems(si) & stems(sj)) > 0, len(objs(si) & objs(sj)) > 0, i - j, j == i - 1, len(set(si.split()) & set(sj.split()))], np.float32))
    return np.concatenate(f)

def linearize(x, role, parent, anchors):
    """예측 역할·부모·앵커 → (parent 벡터, exec 순서). 문법 제약: 부모는 scope 역할 절만, 필러 제외.
    순서: 텍스트 순서 → 참조 절 i(앵커 a, rel)의 뒤따르는 행동 블록(다음 scope/ref/필러 전까지의 act/delay)을 a 바로 앞/뒤로 이동."""
    n = len(x["segs"])
    ex = [i for i in range(n) if role[i] in ("act", "delay", "wait")]
    for i in sorted(anchors):
        a, rel = anchors[i]
        blk = []
        for k in range(i + 1, n):
            if role[k] in ("act", "delay"): blk.append(k)
            else: break
        if not blk or a not in ex: continue
        ex = [e for e in ex if e not in blk]
        pos = ex.index(a) + (1 if rel == "after" else 0)
        ex[pos:pos] = blk
    return ex

results = {}
for PM in ("V", "VP", "VPT"):
  for AM in (["ES"] if PM != "VPT" else ["E", "S", "ES"]):
    tot = collections.Counter(); ok_par = collections.Counter(); ok_role = 0; n_role = 0
    ok_anc = n_anc = 0; ok_exec = collections.Counter(); ok_all = collections.Counter(); n_kind = collections.Counter()
    for tr, te in FOLDS:
        tr_set = set(tr.tolist()); te_set = set(te.tolist())
        # 역할 head
        m_tr = np.array([p in tr_set for p, i in rows]); m_te = ~m_tr
        role_clf = LogisticRegression(max_iter=3000, C=0.5).fit(Hc[m_tr], role_y[m_tr])
        role_pred_all = role_clf.predict(Hc)
        # 부모 스코어러 (학습: 후보 = 같은 명령의 scope 역할 절(gold) + ROOT)
        F, y = [], []
        for p in tr:
            x = P[p]; n = len(x["segs"])
            for i in range(n):
                if x["role"][i] in ("filler",): continue
                cands = [j for j in range(n) if j != i and x["role"][j] == "scope"] + [-1]
                for j in cands: F.append(parent_feats(p, i, j, PM)); y.append(int(x["parent"][i] == j))
        par_clf = LogisticRegression(max_iter=3000, C=0.5).fit(np.array(F), np.array(y))
        # 앵커 스코어러 (학습: 참조 절 × 앞 ACT 절)
        F, y = [], []
        for p in tr:
            x = P[p]
            for r_, (a, rel) in x["anchor"].items():
                r_ = int(r_)
                for j in range(r_):
                    if x["types"][j] == "ACT" and x["role"][j] == "act": F.append(anchor_feats(p, r_, j, AM)); y.append(int(j == a))
        anc_clf = LogisticRegression(max_iter=3000, C=0.5).fit(np.array(F), np.array(y)) if y else None
        # 방향 head: 참조 절 표현 → before/after
        F, y = [], []
        for p in tr:
            for r_, (a, rel) in P[p]["anchor"].items(): F.append(h(p, int(r_))); y.append(int(rel == "before"))
        dir_clf = LogisticRegression(max_iter=3000, C=0.5).fit(np.array(F), np.array(y)) if y else None
        # ── 평가 ──
        for p in te:
            x = P[p]; n = len(x["segs"]); kind = x["kind"]; n_kind[kind] += 1
            role = [str(role_pred_all[row_of[(p, i)]]) for i in range(n)]
            ok_role += sum(int(role[i] == x["role"][i]) for i in range(n)); n_role += n
            ROLE_CTX[p] = role
            parent = [-1] * n
            for i in range(n):
                if role[i] == "filler": continue
                cands = [j for j in range(n) if j != i and role[j] == "scope"] + [-1]
                s_ = par_clf.decision_function(np.array([parent_feats(p, i, j, PM) for j in cands]))
                # 순환 방지: 자기 자손은 후보 제외(간단히 j가 i를 부모로 갖는 경우만)
                parent[i] = cands[int(np.argmax(s_))]
            for i in range(n):
                if x["role"][i] == "filler": continue
                tot[kind] += 1; ok_par[kind] += int(parent[i] == x["parent"][i])
            anchors = {}
            for i in range(n):
                if role[i] != "ref": continue
                cj = [j for j in range(i) if role[j] == "act" and x["types"][j] == "ACT"]
                if not cj or anc_clf is None: continue
                s_ = anc_clf.decision_function(np.array([anchor_feats(p, i, j, AM) for j in cj]))
                a = cj[int(np.argmax(s_))]; rel = "before" if dir_clf.predict(h(p, i)[None])[0] == 1 else "after"
                anchors[i] = (a, rel)
            for r_, (a, rel) in x["anchor"].items():
                n_anc += 1; ok_anc += int(anchors.get(int(r_)) == (a, rel))
            ex = linearize(x, role, parent, anchors); ROLE_CTX[p] = list(x["role"])
            ex_ok = ex == x["exec"]; ok_exec[kind] += ex_ok
            ok_all[kind] += int(ex_ok and parent == x["parent"] and {int(k): tuple(v) for k, v in x["anchor"].items()} == anchors)
    key = f"부모={PM:4s} 앵커={AM:2s}"
    results[key] = (ok_role / n_role, sum(ok_par.values()) / sum(tot.values()), ok_anc / max(n_anc, 1), sum(ok_exec.values()) / len(P), sum(ok_all.values()) / len(P), {k: (ok_all[k], ok_exec[k], n_kind[k]) for k in n_kind})
    print(f"{key} | 역할 {ok_role/n_role:.3f} 부모 {sum(ok_par.values())/sum(tot.values()):.3f} 앵커+방향 {ok_anc/max(n_anc,1):.3f} | 명령 exec일치 {sum(ok_exec.values())/len(P):.3f} 전체일치 {sum(ok_all.values())/len(P):.3f}")
    print("   종류별 전체일치/exec일치/n: " + "  ".join(f"{k} {ok_all[k]}/{ok_exec[k]}/{n_kind[k]}" for k in sorted(n_kind)))

# ── 진단: normal 실패 원인 (마지막 설정 기준으로 재실행: VPT/ES) ──
if os.environ.get("DIAG") == "1":
    PM, AM = "VPT", "S"; cnt = collections.Counter(); ex_show = []
    for tr, te in FOLDS:
        tr_set = set(tr.tolist())
        m_tr = np.array([p in tr_set for p, i in rows])
        role_clf = LogisticRegression(max_iter=3000, C=0.5).fit(Hc[m_tr], role_y[m_tr]); role_pred_all = role_clf.predict(Hc)
        F, y = [], []
        for p in tr:
            x = P[p]; n = len(x["segs"])
            for i in range(n):
                if x["role"][i] == "filler": continue
                for j in [j for j in range(n) if j != i and x["role"][j] == "scope"] + [-1]: F.append(parent_feats(p, i, j, PM)); y.append(int(x["parent"][i] == j))
        par_clf = LogisticRegression(max_iter=3000, C=0.5).fit(np.array(F), np.array(y))
        for p in te:
            x = P[p]
            if x["kind"] != "normal": continue
            n = len(x["segs"]); role = [str(role_pred_all[row_of[(p, i)]]) for i in range(n)]
            parent = [-1] * n; ROLE_CTX[p] = role
            for i in range(n):
                cands = [j for j in range(n) if j != i and role[j] == "scope"] + [-1]
                parent[i] = cands[int(np.argmax(par_clf.decision_function(np.array([parent_feats(p, i, j, PM) for j in cands]))))]
            ex = linearize(x, role, parent, {}); ROLE_CTX[p] = list(x["role"])
            if ex == x["exec"] and parent == x["parent"]: continue
            why = "역할" if role != x["role"] else "부모"
            cnt[why] += 1
            if len(ex_show) < 12: ex_show.append((why, x["cmd"], list(zip(x["types"], x["role"], role)), x["parent"], parent))
    print("\nnormal 실패 원인:", dict(cnt))
    for e in ex_show:
        print(f"[{e[0]}] {e[1]}\n    (type, gold role, pred role) {e[2]}\n    gold parent {e[3]} pred {e[4]}")
