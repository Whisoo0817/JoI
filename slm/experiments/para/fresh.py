# -*- coding: utf-8 -*-
"""신선 파이프라인(held-out용) — 임의 텍스트 → 경계 head → 타입·mods head → 임베딩 매핑(문서 유사도 + 역할·조인 필터) → 조건 부분 재질의 → build_ir → 완전 IR.
원문(orig)과 패러프레이즈(para)를 같은 파이프라인으로 돌려 표현 변화에 대한 낙폭을 잰다. gold = 원문의 gold IR.
head는 382 전체로 학습(원문은 in-sample, 패러프레이즈는 held-out) — 원문 수치는 상한 참고용."""
import json, os, re, sys, collections
import numpy as np, torch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assembly"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map"))
os.environ.setdefault("MAPPED_ONLY", "1")
import build_ir as B
from skeleton import skeleton
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
HERE = os.path.dirname(os.path.abspath(__file__)); EXP = os.path.join(HERE, "..")
PARA = json.load(open(os.path.join(HERE, os.environ.get("PARA", "para_ok.json"))))
byi = {o["i"]: o for o in B.T}
NORM = os.environ.get("NORM", "1") == "1"
def norm_text(t):
    """생성기 인공물 정규화: 숫자와 단위 사이 공백("6 시"→"6시", "100 lux"→"100lux"), 문장 앞뒤 공백"""
    if not NORM: return t
    t = re.sub(r"(\d)\s+(시|분|초|층|도|번|회|%|퍼센트|lux|럭스|dB|ppm|V|A|W|개|장|번째|주기|간격)(?![가-힣A-Za-z])", r"\1\2", t)
    t = re.sub(r"(\d)\s+(시|분|초|층|도|번|회|퍼센트|럭스|번째)(?=[가-힣])", r"\1\2", t)
    return t.strip()
items = []   # (key, text, orig o)
for x in PARA:
    o = byi[x["i"]]
    items.append(("orig", o["cmd"], o))
    for k, p in enumerate(x["para"]): items.append((f"para{k}", norm_text(p), o))

# ── 1. 은닉 상태 + head (382 전체 학습) ──
H = np.load(os.path.join(EXP, "head", "states.npz")); HX = H["X"]; LAYERS = list(H["layers"]); LB, LT = LAYERS.index(2), LAYERS.index(6)
row_of = {(c, t): i for i, (c, t) in enumerate(zip(H["cmd_idx"], H["word_pos"]))}
MODS = ["time", "read", "every", "sustain", "count", "else", "repeat", "delay", "mixed"]
Xb, yb, Xt, yt, ym = [], [], [], [], []
def add_item(get, labels, types, mods):
    n = len(labels)
    for t in range(1, n): Xb.append(np.concatenate([get(t - 1)[LB], get(t)[LB]])); yb.append(labels[t])
    starts = [k for k, l in enumerate(labels) if l == 1 or k == 0]; ends = starts[1:] + [n]
    for ty, md, e in zip(types, mods, ends): Xt.append(get(e - 1)[LT]); yt.append(ty); ym.append([int(m in md) for m in MODS])
for ci, it in enumerate(B.T):
    add_item(lambda t, ci=ci: HX[row_of[(ci, t)]], it["gold_labels"], [s["type"] for s in it["segments"]], [s["mods"] for s in it["segments"]])
AUG = [a for a in os.environ.get("AUG", "").split(",") if a]      # polite,nominal — 증강 세트를 head 학습에 추가
TI = {o["i"]: o for o in B.T}
for name in AUG:
    A = json.load(open(os.path.join(EXP, "type", f"aug_{name}.json")))
    Z = np.load(os.path.join(EXP, "type", "aug_states.npz" if name == "nominal" else f"aug_{name}_states.npz")); ZX = Z["X"]; zrow = {(c, t): i for i, (c, t) in enumerate(map(tuple, Z["idx"]))}
    for ai, x in enumerate(A):
        mods = x.get("mods") or [s["mods"] for s in TI[x["src"]]["segments"]]
        if len(mods) != len(x["types"]): continue
        add_item(lambda t, ai=ai: ZX[zrow[(ai, t)]].astype(np.float32), x["labels"], x["types"], mods)
    print("증강", name, len(A))
Xb, yb, Xt, yt, ym = map(np.array, (Xb, yb, Xt, yt, ym)); print("경계 학습 행", len(Xb), "절", len(Xt))
scb = StandardScaler().fit(Xb); clf_b = LogisticRegression(max_iter=2000, C=1.0).fit(scb.transform(Xb), yb)
sct = StandardScaler().fit(Xt); pca = PCA(256, random_state=0).fit(sct.transform(Xt)); ft = lambda A: pca.transform(sct.transform(A))
clf_t = LogisticRegression(max_iter=1000, C=0.5).fit(ft(Xt), yt)
clf_m = [LogisticRegression(max_iter=1000, C=0.5).fit(ft(Xt), ym[:, k]) if ym[:, k].sum() else None for k in range(len(MODS))]

from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration
MID = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
tok = AutoTokenizer.from_pretrained(MID); cfg = AutoConfig.from_pretrained(MID)
q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]; cfg.quantization_config = q
model = Qwen3_5ForConditionalGeneration.from_pretrained(MID, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map="cuda").eval()
def states(text):
    words = text.split()
    enc = tok(text, return_tensors="pt", return_offsets_mapping=True, add_special_tokens=False)
    offsets = enc.pop("offset_mapping")[0].tolist(); spans, p = [], 0
    for w in words:
        s = text.index(w, p); spans.append((s, s + len(w))); p = s + len(w)
    last = []
    for ws, we in spans:
        l = None
        for ti, (ts, te) in enumerate(offsets):
            if te > ts and ts < we and te > ws: l = ti
        last.append(l)
    with torch.no_grad(): hs = model(**{k: v.to("cuda") for k, v in enc.items()}, output_hidden_states=True).hidden_states
    return words, np.stack([hs[L + 1][0, last].float().cpu().numpy() for L in LAYERS], axis=1)
def segment(text):
    words, F = states(text)
    lab = [1] + [int(clf_b.predict(scb.transform(np.concatenate([F[t - 1, LB], F[t, LB]])[None]))[0]) for t in range(1, len(words))]
    segs, cur, ends = [], [], []
    for i, (w, l) in enumerate(zip(words, lab)):
        if l == 1 and cur: segs.append(" ".join(cur)); ends.append(i - 1); cur = []
        cur.append(w)
    segs.append(" ".join(cur)); ends.append(len(words) - 1)
    V = ft(F[ends, LT]); ty = clf_t.predict(V)
    md = np.stack([m.predict(V) if m is not None else np.zeros(len(V), int) for m in clf_m], 1)
    return [{"text": s, "type": str(t), "mods": [MODS[k] for k in range(len(MODS)) if md[r, k]]} for r, (s, t) in enumerate(zip(segs, ty))]
SEG = {}
for key, text, o in items: SEG[(key, o["i"])] = segment(text)
del model; torch.cuda.empty_cache()

# ── 2. 매핑 (문서 유사도 + 역할·조인 필터) + 조건 부분 재질의 ──
from embed import embed
import pandas as pd
E = json.load(open(os.path.join(B.ROOT, "mapping_v2", "effects.json")))["services"]
D = np.load(os.path.join(EXP, "map", "svc_docs.npy"))
SVCS = [s["svc"] for s in E]; ROLE = {s["svc"]: s["role"] for s in E}; ES = {s["svc"]: s for s in E}
OK = {"ACT": {"action", "read_action"}, "COND": {"read", "read_action"}, "TRIG": {"read", "read_action"}, "READ": {"read", "read_action"}}
P = pd.read_csv(os.path.join(EXP, "map", "dataset_paper.csv")); prow = {r.command_kor: r for r in P.itertuples()}
INSTRUCT = "주어진 스마트홈 명령의 절에 해당하는 IoT 서비스(기기 기능 또는 센서 값)를 찾아라"
CINSTRUCT = "이 한국어 조건 표현이 가리키는 IoT 센서 값 또는 기기 상태 값을 찾아라"
CONJ_SPLIT = re.compile(r"(?<=[가-힣])((?<=[있없되하이않크작높낮많적리히지오가주시밝덥춥])고|거나|이거나|며|이며|는데|은데)[,\s]+(?!있|않|없)")
TOKS = {"고", "거나", "이고", "이거나", "며", "이며", "는데", "은데"}
def parts_of(text):
    ps = [p for p in CONJ_SPLIT.split(text) if p and p not in TOKS]
    return [p + ("이면" if not re.search(r"(면|때|경우)[,.]?$", p) else "") for p in ps] if len(ps) >= 2 else [text]
def _bg(t): t = re.sub(r"[\s.,]", "", t); return {t[i:i + 2] for i in range(len(t) - 1)}
def lex(part, s):
    cat = s["svc"].split(".")[0]; return len(_bg(part) & _bg(" ".join(B.AL.get(cat, []) + s.get("ko_triggers", []) + [cat])))
def alias_hit(part, s):
    cat = s["svc"].split(".")[0]; best = 0
    for w in B.AL.get(cat, []) + s.get("ko_triggers", []):
        w = w.strip()
        if len(w) >= 2 and w in part: best = max(best, len(w))
    return best
def conn_of(o):
    r = prow.get(o["cmd"]); return {c for d in json.loads(r.connected_devices).values() for c in d["category"] if not c.endswith("Control")} if r is not None else None
queries, meta = [], []
for (key, i), segs in SEG.items():
    o = byi[i]
    for j, s in enumerate(segs):
        if s["type"] in OK: queries.append((s["text"], INSTRUCT)); meta.append(("seg", key, i, j, s["type"]))
        if s["type"] in ("COND", "TRIG"):
            for p in parts_of(s["text"]): queries.append((p, CINSTRUCT)); meta.append(("part", key, i, j, p))
Q1 = embed([t for t, ins in queries if ins == INSTRUCT], instruct=INSTRUCT); Q2 = embed([t for t, ins in queries if ins == CINSTRUCT], instruct=CINSTRUCT)
S1, S2 = Q1 @ D.T, Q2 @ D.T
i1 = i2 = 0
CP2 = collections.defaultdict(lambda: collections.defaultdict(list)); MAP2 = {}
for (t, ins), m in zip(queries, meta):
    o = byi[m[2]]; conn = conn_of(o)
    if m[0] == "seg":
        sc = S1[i1]; i1 += 1; order = np.argsort(-sc)
        MAP2[(m[1], m[2], m[3])] = [SVCS[k] for k in order if ROLE[SVCS[k]] in OK[m[4]] and (conn is None or SVCS[k].split(".")[0] in conn) and not SVCS[k].split(".")[0].endswith("Control")][:5]
    else:
        sc = S2[i2].copy(); i2 += 1
        for k, sv in enumerate(SVCS):
            if ROLE[sv] != "read" or (conn is not None and sv.split(".")[0] not in conn) or sv.split(".")[0].endswith("Control"): sc[k] = -9
            else: sc[k] += 0.02 * lex(m[4], ES[sv]) + 0.08 * alias_hit(m[4], ES[sv])
        CP2[(m[1], m[2])][str(m[3])].append({"part": m[4], "ranked": [SVCS[k] for k in np.argsort(-sc)[:5]]})

# ── 3. IR 조립 + 평가 ──
def evaluate(o, o2, G):
    ir = B.build(o2)
    if os.environ.get("LENIENT", "1") == "1": ir, G = B.canon_ir(ir), B.canon_ir(G)
    if skeleton(ir) != skeleton(G): return "S", ir
    pf, gf = B.flat(ir["timeline"]), B.flat(G["timeline"])
    if len(pf) != len(gf): return "S", ir
    okT = okC = okV = okA = True
    for (po, pd), (go, gd) in zip(pf, gf):
        if po != go: return "S", ir
        for key in ("cron", "period", "until", "count", "duration", "for", "edge"):
            if key in gd: okT &= str(pd.get(key)) == str(gd.get(key))
        if "cond" in gd: okC &= B.cond_ok(pd["cond"], gd["cond"], o["cmd"])
        if "target" in gd:
            v_, a_ = B.call_ok(pd, gd); okV &= v_; okA &= a_
    return ("T" if not okT else "C" if not okC else "V" if not okV else "A" if not okA else "OK"), ir
res = collections.defaultdict(collections.Counter); fails = []; out = []
for key, text, o in items:
    segs = SEG[(key, o["i"])]; ck = f"{key}#{o['i']}"
    for j in range(len(segs)): B.MAP[(ck, j)] = MAP2.get((key, o["i"], j), [])
    B.CP[ck] = dict(CP2.get((key, o["i"]), {}))
    o2 = {"i": o["i"], "cmd": ck, "ir_gt": o["ir_gt"], "segments": segs}
    r, ir = evaluate(o, o2, B.gold_of(o)); grp = "orig" if key == "orig" else "para"; res[grp][r] += 1
    out.append({"grp": grp, "i": o["i"], "text": text, "segs": segs, "result": r, "ir": ir})
    if grp == "para" and r != "OK": fails.append((r, text, " ‖ ".join(f"[{s['type']}{'/'+'+'.join(s['mods']) if s['mods'] else ''}] {s['text']}" for s in segs)))
json.dump(out, open(os.path.join(HERE, f"fresh_out{'_' + '_'.join(AUG) if AUG else ''}.json"), "w"), ensure_ascii=False, indent=1)
def cum(c):
    n = sum(c.values()); okS = n - c["S"]; okT = okS - c["T"]; okC = okT - c["C"]; okV = okC - c["V"]; okA = okV - c["A"]
    return f"n={n}  S {okS/n:.3f}  S+T {okT/n:.3f}  S+T+C {okC/n:.3f}  S+T+C+V {okV/n:.3f}  완전 {okA/n:.3f}"
for g in ("orig", "para"): print(g, cum(res[g]), dict(res[g]))
# 원문이 맞은 명령에서의 패러프레이즈 성적(표현 변화 순수 효과)
okI = {x["i"] for x in out if x["grp"] == "orig" and x["result"] == "OK"}
sub = collections.Counter(x["result"] for x in out if x["grp"] == "para" and x["i"] in okI)
print("para|orig OK", cum(sub))
print("\n[para 실패 예]")
for r, t, s in fails[:40]: print(" ", r, t); print("     ", s)
