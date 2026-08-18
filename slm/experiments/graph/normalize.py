# -*- coding: utf-8 -*-
"""그래프 정규화기 — §23–24 파서 head(역할·범위 부모·앵커·방향)를 build_ir 앞단에 붙여 절 목록을 "단조 순서"로 고쳐 준다.
입력: 절 목록 [{text, type, mods, h6(L6 절 끝 은닉 상태 2048)}]  → 출력: 재배열·필터된 절 목록(원래 j 유지) + 진단.
  필러(role=filler, p>=TAU_F) 탈락 / 참조 절(role=ref) 탈락 + 뒤따르는 행동 블록을 앵커 앞·뒤로 이동 /
  뒤→앞 범위 부모(후치: 조건·시각 절이 자기 자식 뒤에 있음) → 범위 절을 첫 자식 앞으로 이동.
학습: pairs.json 1,233문 전체(pairs_words.npz L6, StandardScaler+PCA256). 첫 호출 때 학습·캐시(normalize_heads.pkl).
"""
import json, os, re, pickle
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
HERE = os.path.dirname(os.path.abspath(__file__))
TYPES = ["ACT", "COND", "TRIG", "TIME", "DELAY", "READ", "ELSE", "STOP"]
STEM = {"켜": "on", "끄": "off", "꺼": "off", "닫": "close", "열": "open", "잠": "lock", "울리": "siren", "울려": "siren", "찍": "shot", "알리": "notify", "알려": "notify",
        "말하": "say", "말해": "say", "바꾸": "set", "바꿔": "set", "틀": "play", "올리": "up", "올려": "up", "내리": "down", "내려": "down", "설정": "set", "재생": "play"}
def stems(s): return {v for k, v in STEM.items() if k in s}
def objs(s): return set(re.findall(r"([가-힣A-Za-z0-9 ]+?)(?:을|를)\b", s))
def parent_feats(hi, hj, i, j, n, roles, ti, tj):
    prev_scopes = [k for k in range(i) if roles[k] == "scope"]; nearest = prev_scopes[-1] if prev_scopes else -1
    pri = np.array([j < i, j > i, abs(i - j) if j >= 0 else 0, j == i - 1, j == -1, j == n - 1, i == n - 1, j == nearest, j >= 0 and j > i and j == n - 1], np.float32)
    oh = np.zeros(len(TYPES) * (len(TYPES) + 1), np.float32); oh[TYPES.index(ti) * (len(TYPES) + 1) + (TYPES.index(tj) if tj else len(TYPES))] = 1
    return np.concatenate([hi, hj, hi * hj, pri, oh])
def anchor_feats(si, sj, i, j):
    return np.array([len(stems(si) & stems(sj)) > 0, len(objs(si) & objs(sj)) > 0, i - j, j == i - 1, len(set(si.split()) & set(sj.split()))], np.float32)

_H = None
def heads():
    """(scaler, pca, role_clf, parent_clf, anchor_clf, dir_clf) — 캐시 파일이 있으면 적재"""
    global _H
    if _H is not None: return _H
    pk = os.path.join(HERE, "normalize_heads.pkl")
    if os.path.exists(pk): _H = pickle.load(open(pk, "rb")); return _H
    P = json.load(open(os.path.join(HERE, "pairs.json"))); W = np.load(os.path.join(HERE, "pairs_words.npz"))
    WX = W["X"][:, 1].astype(np.float32); widx = {(int(p), int(w)): r for r, (p, w) in enumerate(zip(W["pid"], W["wpos"]))}
    sc = StandardScaler().fit(WX); pca = PCA(256, random_state=0).fit(sc.transform(WX[::3]))
    def spans_of(x):
        k = 0; out = []
        for s in x["segs"]: n = len(s.split()); out.append((k, k + n - 1)); k += n
        return out
    Z = {}
    def h6(p, w):
        if (p, w) not in Z: Z[(p, w)] = pca.transform(sc.transform(WX[widx[(p, w)]][None]))[0].astype(np.float32)
        return Z[(p, w)]
    F, yr, Fp, yp, Fa, ya, Fd, yd = [], [], [], [], [], [], [], []
    for p, x in enumerate(P):
        n = len(x["segs"]); sp = spans_of(x); H = [h6(p, b) for a, b in sp]
        for i in range(n): F.append(H[i]); yr.append(x["role"][i])
        for i in range(n):
            if x["role"][i] == "filler": continue
            for j in [j for j in range(n) if j != i and x["role"][j] == "scope"] + [-1]:
                Fp.append(parent_feats(H[i], H[j] if j >= 0 else np.zeros(256, np.float32), i, j, n, x["role"], x["types"][i], x["types"][j] if j >= 0 else None)); yp.append(int(x["parent"][i] == j))
        for r_, (a, rel) in x["anchor"].items():
            r_ = int(r_)
            for j in range(r_):
                if x["types"][j] == "ACT" and x["role"][j] == "act": Fa.append(anchor_feats(x["segs"][r_], x["segs"][j], r_, j)); ya.append(int(j == a))
            Fd.append(H[r_]); yd.append(int(rel == "before"))
    rclf = LogisticRegression(max_iter=3000, C=0.5).fit(np.array(F), yr)
    pclf = LogisticRegression(max_iter=3000, C=0.5).fit(np.array(Fp), yp)
    aclf = LogisticRegression(max_iter=2000, C=0.5).fit(np.array(Fa), ya)
    dclf = LogisticRegression(max_iter=2000, C=0.5).fit(np.array(Fd), yd)
    _H = (sc, pca, rclf, pclf, aclf, dclf); pickle.dump(_H, open(pk, "wb")); return _H

TAU_F = float(os.environ.get("GRAPH_TAU_F", "0.9"))    # 필러 탈락 확신 문턱
TAU_R = float(os.environ.get("GRAPH_TAU_R", "0.9"))    # 참조 절 확신 문턱

def analyze(segs):
    """절 목록 → dict(role, p_role, parent, anchors). h6 없는 절이 있으면 None."""
    if any("h6" not in s for s in segs) or not segs: return None
    sc, pca, rclf, pclf, aclf, dclf = heads()
    n = len(segs); H = pca.transform(sc.transform(np.array([s["h6"] for s in segs], np.float32))).astype(np.float32)
    types = [s["type"] for s in segs]; texts = [s["text"] for s in segs]
    pr = rclf.predict_proba(H); cls = list(rclf.classes_)
    role = [str(cls[int(np.argmax(pr[i]))]) for i in range(n)]; prole = [float(pr[i].max()) for i in range(n)]
    parent = [-1] * n
    for i in range(n):
        if role[i] == "filler": continue
        cands = [j for j in range(n) if j != i and role[j] == "scope"] + [-1]
        s_ = pclf.decision_function(np.array([parent_feats(H[i], H[j] if j >= 0 else np.zeros(256, np.float32), i, j, n, role, types[i], types[j] if j >= 0 else None) for j in cands]))
        parent[i] = cands[int(np.argmax(s_))]
    anchors = {}
    for i in range(n):
        if role[i] != "ref" or prole[i] < TAU_R: continue
        cj = [j for j in range(i) if role[j] == "act" and types[j] == "ACT"]
        if not cj: continue
        a = cj[int(np.argmax(aclf.decision_function(np.array([anchor_feats(texts[i], texts[j], i, j) for j in cj]))))]
        anchors[i] = (a, "before" if dclf.predict(H[i][None])[0] == 1 else "after")
    return {"role": role, "p": prole, "parent": parent, "anchors": anchors}

def normalize(segs):
    """→ (재배열된 절 목록, 진단 dict). 절 dict는 그대로(원래 j 유지)."""
    A = analyze(segs)
    if A is None: return segs, None
    n = len(segs); role, prole, parent, anchors = A["role"], A["p"], A["parent"], A["anchors"]
    order = list(range(n)); drop = set()
    for i in range(n):
        if role[i] == "filler" and prole[i] >= TAU_F and segs[i]["type"] not in ("STOP", "ELSE"): drop.add(i)
    for i in anchors: drop.add(i)
    # 참조 블록 이동: 참조 절 뒤 연속 act/delay 블록을 앵커 앞/뒤로
    for i in sorted(anchors):
        a, rel = anchors[i]; blk = []
        for k in range(i + 1, n):
            if role[k] in ("act", "delay") and k not in drop: blk.append(k)
            else: break
        if not blk or a not in order: continue
        order = [e for e in order if e not in blk]; pos = order.index(a) + (1 if rel == "after" else 0); order[pos:pos] = blk
    # 후치: 범위 절 s의 자식 중 s보다 앞에 있는 것이 있으면 s(와 s 뒤에 연달아 오는 다른 범위 절)를 첫 자식 앞으로
    moved = []
    SCOPE_T = ("COND", "TRIG", "TIME", "DELAY", "ELSE")
    for s in range(n):
        if role[s] != "scope" or s in drop or segs[s]["type"] not in SCOPE_T: continue        # 행동 절(ACT)은 후치 범위로 안 옮김
        kids = [i for i in range(n) if parent[i] == s and i < s and role[i] in ("act", "delay", "wait")]
        if not kids or s not in order or s in moved: continue
        first = min(kids)
        if order.index(first) > order.index(s): continue
        blk = [s]                                                                            # s와 이어진 범위 절 묶음("…이거나 ‖ …이면")을 통째로
        k = s - 1
        while k > max(kids) and role[k] == "scope" and segs[k]["type"] in SCOPE_T and k not in drop: blk.insert(0, k); k -= 1
        k = s + 1
        while k < n and role[k] == "scope" and segs[k]["type"] in SCOPE_T and k not in drop: blk.append(k); k += 1
        order = [e for e in order if e not in blk]; pos = order.index(first); order[pos:pos] = blk; moved.extend(blk)
    out = [segs[i] for i in order if i not in drop]
    return out, {"role": role, "p": [round(x, 2) for x in prole], "parent": parent, "anchors": anchors, "drop": sorted(drop), "moved": moved, "order": [i for i in order if i not in drop]}
