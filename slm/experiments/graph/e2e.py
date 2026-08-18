# -*- coding: utf-8 -*-
"""종단 평가 — 텍스트만 입력: 경계 head(L2) → 타입·mods head(L6) → 역할/부모/앵커 head(L6) → 선형화; 하이브리드(abnormal 신호 없으면 상자 규칙).
상류 조건: G/G(gold 경계·타입·mods) / P/P(전부 예측). 데이터 pairs.json, 명령(src) 단위 5-fold. 지표: 분할 완전일치, 구조 전체일치(부모+실행순서+참조), 종류별.
"""
import json, os, sys, re, collections
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "assembly"))
os.environ.setdefault("SLOT", "1")
from box import assemble_tree
from candidates import tree_to_lines
from synth_pairs import lines_to_graph
P = json.load(open(os.path.join(HERE, "pairs.json")))
W = np.load(os.path.join(HERE, "pairs_words.npz"))
WX = W["X"].astype(np.float32); LI2, LI6 = 0, 1
widx = {}
for r, (p, w) in enumerate(zip(W["pid"], W["wpos"])): widx[(int(p), int(w))] = r
def hw(p, w, li): return WX[widx[(p, w)], li]
# PCA256 for L6 clause vectors (unsupervised, all words)
sc6 = StandardScaler().fit(WX[:, LI6]); pca6 = PCA(256, random_state=0).fit(sc6.transform(WX[:, LI6][::3]))
def z6(p, w): return pca6.transform(sc6.transform(hw(p, w, LI6)[None]))[0].astype(np.float32)
Z6 = {k: None for k in widx}
def h6(p, w):
    if Z6[(p, w)] is None: Z6[(p, w)] = z6(p, w)
    return Z6[(p, w)]
TYPES = ["ACT", "COND", "TRIG", "TIME", "DELAY", "READ", "ELSE", "STOP"]; MODS = ["time", "read", "every", "sustain", "count", "else", "repeat", "delay", "mixed"]
STEM = {"켜": "on", "끄": "off", "꺼": "off", "닫": "close", "열": "open", "잠": "lock", "울리": "siren", "울려": "siren", "찍": "shot", "알리": "notify", "알려": "notify",
        "말하": "say", "말해": "say", "바꾸": "set", "바꿔": "set", "틀": "play", "올리": "up", "올려": "up", "내리": "down", "내려": "down", "설정": "set", "재생": "play"}
def stems(s): return {v for k, v in STEM.items() if k in s}
def objs(s): return set(re.findall(r"([가-힣A-Za-z0-9 ]+?)(?:을|를)\b", s))

def spans_of(x):
    k = 0; out = []
    for s in x["segs"]:
        n = len(s.split()); out.append((k, k + n - 1)); k += n
    return out
def spans_from_labels(lab):
    starts = [i for i, l in enumerate(lab) if l == 1 or i == 0]; ends = starts[1:] + [len(lab)]
    return list(zip(starts, [e - 1 for e in ends]))

def parent_feats(hi, hj, i, j, n, roles, ti, tj):
    prev_scopes = [k for k in range(i) if roles[k] == "scope"]; nearest = prev_scopes[-1] if prev_scopes else -1
    pri = np.array([j < i, j > i, abs(i - j) if j >= 0 else 0, j == i - 1, j == -1, j == n - 1, i == n - 1, j == nearest, j >= 0 and j > i and j == n - 1], np.float32)
    oh = np.zeros(len(TYPES) * (len(TYPES) + 1), np.float32); oh[TYPES.index(ti) * (len(TYPES) + 1) + (TYPES.index(tj) if tj else len(TYPES))] = 1
    return np.concatenate([hi, hj, hi * hj, pri, oh])
def anchor_feats(si, sj, i, j):
    return np.array([len(stems(si) & stems(sj)) > 0, len(objs(si) & objs(sj)) > 0, i - j, j == i - 1, len(set(si.split()) & set(sj.split()))], np.float32)
def linearize(n, role, anchors):
    ex = [i for i in range(n) if role[i] in ("act", "delay", "wait")]
    for i in sorted(anchors):
        a, rel = anchors[i]; blk = []
        for k in range(i + 1, n):
            if role[k] in ("act", "delay"): blk.append(k)
            else: break
        if not blk or a not in ex: continue
        ex = [e for e in ex if e not in blk]; pos = ex.index(a) + (1 if rel == "after" else 0); ex[pos:pos] = blk
    return ex

groups = np.array([x["src"] for x in P])
res = collections.defaultdict(collections.Counter)   # setting → counters
for fold, (tr, te) in enumerate(GroupKFold(5).split(np.zeros(len(P)), np.zeros(len(P)), groups)):
    tr = tr.tolist(); te = te.tolist()
    # ── 경계 head (L2, 직전+현재) ──
    F, y = [], []
    for p in tr:
        x = P[p]; lab = [0] * len(x["cmd"].split()); 
        for a, b in spans_of(x)[1:]: lab[a] = 1
        for t in range(1, len(lab)): F.append(np.concatenate([hw(p, t - 1, LI2), hw(p, t, LI2)])); y.append(lab[t])
    scb = StandardScaler().fit(np.array(F)); bclf = LogisticRegression(max_iter=2000, C=1.0).fit(scb.transform(np.array(F)), y)
    # ── 타입·mods·역할 head (절 끝 L6) ──
    F, yt, ym, yr = [], [], [], []
    for p in tr:
        x = P[p]
        for i, (a, b) in enumerate(spans_of(x)):
            F.append(h6(p, b)); yt.append(x["types"][i]); ym.append([int(m in x["mods"][i]) for m in MODS]); yr.append(x["role"][i])
    F = np.array(F); ym = np.array(ym)
    tclf = LogisticRegression(max_iter=2000, C=0.5).fit(F, yt); rclf = LogisticRegression(max_iter=2000, C=0.5).fit(F, yr)
    mclf = [LogisticRegression(max_iter=2000, C=0.5).fit(F, ym[:, k]) if ym[:, k].sum() else None for k in range(len(MODS))]
    # ── 부모·앵커·방향 ──
    Fp, yp, Fa, ya, Fd, yd = [], [], [], [], [], []
    for p in tr:
        x = P[p]; n = len(x["segs"]); sp = spans_of(x); H = [h6(p, b) for a, b in sp]
        for i in range(n):
            if x["role"][i] == "filler": continue
            for j in [j for j in range(n) if j != i and x["role"][j] == "scope"] + [-1]:
                Fp.append(parent_feats(H[i], H[j] if j >= 0 else np.zeros(256, np.float32), i, j, n, x["role"], x["types"][i], x["types"][j] if j >= 0 else None)); yp.append(int(x["parent"][i] == j))
        for r_, (a, rel) in x["anchor"].items():
            r_ = int(r_)
            for j in range(r_):
                if x["types"][j] == "ACT" and x["role"][j] == "act": Fa.append(anchor_feats(x["segs"][r_], x["segs"][j], r_, j)); ya.append(int(j == a))
            Fd.append(H[r_]); yd.append(int(rel == "before"))
    pclf = LogisticRegression(max_iter=3000, C=0.5).fit(np.array(Fp), yp); aclf = LogisticRegression(max_iter=2000, C=0.5).fit(np.array(Fa), ya); dclf = LogisticRegression(max_iter=2000, C=0.5).fit(np.array(Fd), yd)

    def run(p, sp, types, mods, texts, setting):
        """예측(또는 gold) 절 정보로 파서/하이브리드 → 결과 기록"""
        x = P[p]; n = len(sp); kind = x["kind"]
        H = [h6(p, b) for a, b in sp]
        role = [str(r) for r in rclf.predict(np.array(H))]
        parent = [-1] * n
        for i in range(n):
            if role[i] == "filler": continue
            cands = [j for j in range(n) if j != i and role[j] == "scope"] + [-1]
            s_ = pclf.decision_function(np.array([parent_feats(H[i], H[j] if j >= 0 else np.zeros(256, np.float32), i, j, n, role, types[i], types[j] if j >= 0 else None) for j in cands]))
            parent[i] = cands[int(np.argmax(s_))]
        anchors = {}
        for i in range(n):
            if role[i] != "ref": continue
            cj = [j for j in range(i) if role[j] == "act" and types[j] == "ACT"]
            if not cj: continue
            a = cj[int(np.argmax(aclf.decision_function(np.array([anchor_feats(texts[i], texts[j], i, j) for j in cj]))))]
            anchors[i] = (a, "before" if dclf.predict(H[i][None])[0] == 1 else "after")
        ex = linearize(n, role, anchors)
        seg_ok = sp == spans_of(x)
        gold_anc = {int(k): tuple(v) for k, v in x["anchor"].items()}
        parser_ok = seg_ok and parent == x["parent"] and ex == x["exec"] and anchors == gold_anc
        # 하이브리드 v2: 뒤→앞 부모(후치)만 파서. 아니면 필러·참조 절을 뺀 나머지에 상자 규칙 → 앵커 이동 적용
        abnormal = any(parent[i] > i for i in range(n))
        if abnormal:
            hyb_ok = parser_ok
        else:
            keep = [i for i in range(n) if role[i] not in ("ref", "filler")]
            segs3 = [(types[i], mods[i], texts[i]) for i in keep]
            try:
                L = tree_to_lines(assemble_tree(segs3, False, []), segs3); bp, br, bex = lines_to_graph(L, segs3)
                hp = [-1] * n
                for k, i in enumerate(keep): hp[i] = keep[bp[k]] if bp[k] >= 0 else -1
                hex_ = [keep[k] for k in bex]
                for i in sorted(anchors):                       # 참조 블록 이동 (linearize와 동일)
                    a, rel = anchors[i]; blk = []
                    for k in range(i + 1, n):
                        if role[k] in ("act", "delay"): blk.append(k)
                        else: break
                    if not blk or a not in hex_: continue
                    hex_ = [e for e in hex_ if e not in blk]; pos = hex_.index(a) + (1 if rel == "after" else 0); hex_[pos:pos] = blk
                hyb_ok = seg_ok and hp == x["parent"] and hex_ == x["exec"] and anchors == gold_anc
            except Exception:
                hyb_ok = False
        c = res[setting]; c["n"] += 1; c["seg"] += seg_ok; c["parser"] += parser_ok; c["hybrid"] += hyb_ok
        c[f"{kind}/n"] += 1; c[f"{kind}/parser"] += parser_ok; c[f"{kind}/hybrid"] += hyb_ok; c[f"{kind}/seg"] += seg_ok
        c["abn_flag"] += abnormal; c[f"{kind}/abn_flag"] += abnormal

    for p in te:
        x = P[p]; words = x["cmd"].split(); T_ = len(words)
        # G/G
        run(p, spans_of(x), x["types"], x["mods"], x["segs"], "G/G")
        # P/P
        lab = [1] + [int(bclf.predict(scb.transform(np.concatenate([hw(p, t - 1, LI2), hw(p, t, LI2)])[None]))[0]) for t in range(1, T_)]
        sp = spans_from_labels(lab); texts = [" ".join(words[a:b + 1]) for a, b in sp]
        H = np.array([h6(p, b) for a, b in sp])
        types = [str(t) for t in tclf.predict(H)]
        mods = [[MODS[k] for k in range(len(MODS)) if mclf[k] is not None and mclf[k].predict(H[i][None])[0] == 1] for i in range(len(sp))]
        run(p, sp, types, mods, texts, "P/P")
    print(f"fold {fold} 완료", flush=True)

for setting in ("G/G", "P/P"):
    c = res[setting]; n = c["n"]
    print(f"\n[{setting}] n={n}  분할 완전일치 {c['seg']/n:.3f}  파서 전체일치 {c['parser']/n:.3f}  하이브리드 전체일치 {c['hybrid']/n:.3f}  (abnormal 판정률 {c['abn_flag']/n:.3f})")
    for k in ("normal", "filler", "post", "after", "before", "event", "before0"):
        if c[f"{k}/n"]: print(f"   {k:8s} n={c[k+'/n']:3d}  분할 {c[k+'/seg']/c[k+'/n']:.3f}  파서 {c[k+'/parser']/c[k+'/n']:.3f}  하이브리드 {c[k+'/hybrid']/c[k+'/n']:.3f}  abn판정 {c[k+'/abn_flag']/c[k+'/n']:.3f}")
