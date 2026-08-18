# -*- coding: utf-8 -*-
"""명사형 증강 효과 + 382 회귀 확인.

1) aug_nominal.json 732문 + 수기 명사형 테스트 20문의 2B 내부표현 추출(캐시 aug_states.npz)
2) 5조각 교차검증(원본 명령 단위 그룹; 합성문은 원본과 같은 조각 — 누출 방지):
   A. 학습 = 원본 train-fold           → 평가: 원본 test-fold / 합성 test-fold / 수기 명사형 20
   B. 학습 = 원본 + 합성 train-fold     → 같은 평가
   경계 head(L2, 직전+현재) P/R/명령 완전일치, 타입 head(L6 ctx_last, PCA256) 정확도.
"""
import json, os, re, sys, collections
import numpy as np, torch
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
T = json.load(open(os.path.join(HERE, "type_labels.json")))
A = json.load(open(os.path.join(HERE, "aug_nominal.json")))

# 수기 명사형 테스트 (데이터셋·합성 규칙과 다른 손 글씨) — words/labels/types
HAND = [
    ("재실 감지 시 거실 조명 점등.", [0, 0, 0, 1, 0, 0], ["TRIG", "ACT"]),
    ("온도 30도 초과 시 에어컨 냉방 모드, 25도 미만 시 에어컨 끔.", [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0], ["COND", "ACT", "COND", "ACT"]),
    ("현관문 열림 시 카메라 촬영 후 스피커 안내.", [0, 0, 0, 1, 0, 0, 1, 0], ["TRIG", "ACT", "ACT"]),
    ("습도 70% 이상인 경우 제습기 가동.", [0, 0, 0, 0, 1, 0], ["COND", "ACT"]),
    ("연기 감지 시 사이렌 화재 모드 작동.", [0, 0, 0, 1, 0, 0, 0], ["TRIG", "ACT"]),
    ("버튼 1 누름 시 침실 조명 최대 밝기로.", [0, 0, 0, 0, 1, 0, 0, 0], ["TRIG", "ACT"]),
    ("매일 아침 7시 블라인드 올리기.", [0, 0, 0, 0, 0], ["ACT"]),
    ("사람 부재 10분 지속 시 사무실 에어컨 끄기.", [0, 0, 0, 0, 0, 1, 0, 0], ["COND", "ACT"]),
    ("누수 감지 시 밸브 잠금 후 1분마다 스피커로 경고 안내.", [0, 0, 0, 1, 0, 0, 1, 0, 0, 0], ["TRIG", "ACT", "ACT"]),
    ("문 열림 상태 5분 지속 시 스피커로 문 닫기 안내.", [0, 0, 0, 0, 0, 0, 1, 0, 0, 0], ["COND", "ACT"]),
    ("주말 오후 3시 로봇청소기 자동 모드 실행.", [0, 0, 0, 0, 0, 0, 0], ["ACT"]),
    ("조도 50 미만 시 조명 켜기, 500 이상 시 조명 끄기.", [0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0], ["COND", "ACT", "COND", "ACT"]),
    ("이산화탄소 1000ppm 초과 시 공기청정기 강풍 및 창문 개방.", [0, 0, 0, 0, 1, 0, 0, 1, 0], ["COND", "ACT", "ACT"]),
    ("움직임 감지 시 3초 후 사진 촬영.", [0, 0, 0, 1, 0, 1, 0], ["TRIG", "DELAY", "ACT"]),
    ("도어락 잠김 시 현관 조명 10초 점등 후 소등.", [0, 0, 0, 1, 0, 0, 0, 0, 1], ["TRIG", "ACT", "ACT"]),
    ("30분마다 온도 확인, 28도 이상 시 에어컨 On, 24도 이하 시 Off.", [0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1], ["TIME", "COND", "ACT", "COND", "ACT"]),
    ("비 시작 시 창문 닫기, 1시간 후 다시 열기.", [0, 0, 0, 1, 0, 1, 0, 1, 0], ["TRIG", "ACT", "DELAY", "ACT"]),
    ("스피커 볼륨 40 이상인 경우 재생 정지.", [0, 0, 0, 0, 0, 1, 0], ["COND", "ACT"]),
    ("전력 5W 미만 10분 지속 시 프린터 플러그 Off.", [0, 0, 0, 0, 0, 0, 1, 0, 0], ["COND", "ACT"]),
    ("멀티버튼 3번 누름 시마다 주방 조명 토글.", [0, 0, 0, 0, 1, 0, 0], ["TRIG", "ACT"]),
]
for t, l, ty in HAND:
    assert len(t.split()) == len(l), t
    assert sum(l) + 1 == len(ty), t

# ── 상태 추출(캐시) ─────────────────────────────────────────────────────
cache = os.path.join(HERE, "aug_states.npz")
texts = [x["cmd"] for x in A] + [h[0] for h in HAND]
if not os.path.exists(cache):
    from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration
    tok = AutoTokenizer.from_pretrained(MODEL)
    cfg = AutoConfig.from_pretrained(MODEL)
    q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]; cfg.quantization_config = q
    model = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map="cuda").eval()
    H0 = np.load(os.path.join(HERE, "..", "head", "states.npz")); LAYERS = list(H0["layers"])
    feats, idx = [], []
    for ci, text in enumerate(texts):
        words = text.split()
        enc = tok(text, return_tensors="pt", return_offsets_mapping=True, add_special_tokens=False)
        offsets = enc.pop("offset_mapping")[0].tolist()
        spans, p = [], 0
        for w in words:
            s = text.index(w, p); spans.append((s, s + len(w))); p = s + len(w)
        last = []
        for ws, we in spans:
            l = None
            for ti, (ts, te) in enumerate(offsets):
                if te > ts and ts < we and te > ws: l = ti
            last.append(l)
        with torch.no_grad():
            hs = model(**{k: v.to("cuda") for k, v in enc.items()}, output_hidden_states=True).hidden_states
        feats.append(np.stack([hs[L + 1][0, last].float().cpu().numpy() for L in LAYERS], axis=1).astype(np.float16))
        idx += [(ci, t) for t in range(len(words))]
    np.savez_compressed(cache, X=np.concatenate(feats), idx=np.array(idx), layers=np.array(LAYERS))
    del model; torch.cuda.empty_cache()
AS = np.load(cache); AX = AS["X"]; LAYERS = list(AS["layers"])
arow = {(c, t): i for i, (c, t) in enumerate(map(tuple, AS["idx"]))}
H = np.load(os.path.join(HERE, "..", "head", "states.npz")); HX = H["X"]
hrow = {(c, t): i for i, (c, t) in enumerate(zip(H["cmd_idx"], H["word_pos"]))}
LB, LT = LAYERS.index(2), LAYERS.index(6)

# ── 항목 통일: (X 접근자, words, labels, types, group) ───────────────
def item_orig(ci):
    o = T[ci]; return dict(get=lambda t: HX[hrow[(ci, t)]], words=o["words"], labels=o["gold_labels"], types=[s["type"] for s in o["segments"]], group=ci)
def item_aug(ai):
    a = A[ai]; return dict(get=lambda t: AX[arow[(ai, t)]], words=a["words"], labels=a["labels"], types=a["types"], group=a["src"])
def item_hand(hi):
    t, l, ty = HAND[hi]; ci = len(A) + hi
    return dict(get=lambda t_: AX[arow[(ci, t_)]], words=t.split(), labels=l, types=ty, group=-1)
ORIG = [item_orig(i) for i in range(len(T))]; AUG = [item_aug(i) for i in range(len(A))]; HANDI = [item_hand(i) for i in range(len(HAND))]

def bfeat(it, t): return np.concatenate([it["get"](t - 1)[LB], it["get"](t)[LB]])
def seg_ends(labels):
    starts = [k for k, l in enumerate(labels) if l == 1 or k == 0]
    return [s - 1 for s in starts[1:]] + [len(labels) - 1]
def tfeat(it, e): return it["get"](e)[LT]

def fit(train):
    Xb = np.array([bfeat(it, t) for it in train for t in range(1, len(it["words"]))], np.float32)
    yb = np.array([it["labels"][t] for it in train for t in range(1, len(it["words"]))])
    scb = StandardScaler().fit(Xb); cb = LogisticRegression(max_iter=1000, C=1.0).fit(scb.transform(Xb), yb)
    Xt = np.array([tfeat(it, e) for it in train for e in seg_ends(it["labels"])], np.float32)
    yt = np.array([ty for it in train for ty in it["types"]])
    sct = StandardScaler().fit(Xt); pca = PCA(256, random_state=0).fit(sct.transform(Xt))
    ct = LogisticRegression(max_iter=1000, C=0.5).fit(pca.transform(sct.transform(Xt)), yt)
    return (scb, cb, sct, pca, ct)

def evaluate(models, test, acc):
    scb, cb, sct, pca, ct = models
    for it in test:
        n = len(it["words"])
        if n > 1:
            pred = cb.predict(scb.transform(np.array([bfeat(it, t) for t in range(1, n)], np.float32)))
        else:
            pred = np.array([], int)
        gold = np.array(it["labels"][1:])
        acc["tp"] += int(((pred == 1) & (gold == 1)).sum()); acc["fp"] += int(((pred == 1) & (gold == 0)).sum()); acc["fn"] += int(((pred == 0) & (gold == 1)).sum())
        acc["exact"] += int((pred == gold).all()); acc["n"] += 1
        # 타입: gold 경계 기준 절 끝 단어
        ends = seg_ends(it["labels"])
        tp_ = ct.predict(pca.transform(sct.transform(np.array([tfeat(it, e) for e in ends], np.float32))))
        acc["t_ok"] += int((tp_ == np.array(it["types"])).sum()); acc["t_n"] += len(ends)
        # 종단: 예측 경계로 자르고 예측 타입까지 맞아야
        pend = seg_ends([0] + list(pred))
        if pend == ends:
            tp2 = ct.predict(pca.transform(sct.transform(np.array([tfeat(it, e) for e in pend], np.float32))))
            acc["e2e"] += int((tp2 == np.array(it["types"])).all())

def show(name, a):
    p = a["tp"] / max(a["tp"] + a["fp"], 1); r = a["tp"] / max(a["tp"] + a["fn"], 1)
    print(f"  {name:12s} 경계 P {p:.3f} R {r:.3f} 완전일치 {a['exact']/a['n']:.3f} | 타입 정확 {a['t_ok']/a['t_n']:.3f} | 종단(분할+타입 전부) {a['e2e']/a['n']:.3f}  (n={a['n']})")

groups = np.array([it["group"] for it in ORIG])
for mode in ("A: 원본만 학습", "B: 원본+합성 학습"):
    accs = {k: collections.Counter() for k in ("orig", "aug", "hand")}
    for tr, te in GroupKFold(5).split(ORIG, groups=groups):
        trg = set(groups[tr])
        train = [ORIG[i] for i in tr] + ([it for it in AUG if it["group"] in trg] if mode.startswith("B") else [])
        m = fit(train)
        evaluate(m, [ORIG[i] for i in te], accs["orig"])
        evaluate(m, [it for it in AUG if it["group"] not in trg], accs["aug"])
    # 수기 20: 전체 학습
    m = fit(ORIG + (AUG if mode.startswith("B") else []))
    evaluate(m, HANDI, accs["hand"])
    print(mode)
    show("원본 382 CV", accs["orig"]); show("합성 732 CV", accs["aug"]); show("수기 명사형 20", accs["hand"])
