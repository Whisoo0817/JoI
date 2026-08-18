# -*- coding: utf-8 -*-
"""분포 밖 말투 프로브 — 데이터셋에 없는 문체 30개에 경계 head + 타입 head(382개 전체로 학습)를 통과시켜
분할·타입 결과를 출력(사람 눈으로 판정). 말투 종류: 메타 발화("~하는 시나리오 만들어줘"), 존댓말/격식,
명사형·체언 종결, 구어·축약, 영어 섞임, 조건 후치(단조성 위반), 장문.
"""
import json, os, re, sys
import numpy as np, torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"

CASES = [
    # 메타 발화 / 시나리오형
    "밤 12시 이후에 사람이 감지되면 조명이 모두 꺼지는 시나리오를 만들어줘.",
    "온도가 28도를 넘으면 에어컨이 자동으로 켜지도록 자동화 하나 만들어 줄래?",
    "현관문이 열리면 거실 조명이 켜지고 5분 뒤에 꺼지는 규칙을 등록해줘.",
    "습도가 70%를 넘을 때마다 제습기가 돌아가게 설정해줘.",
    "매일 아침 7시에 블라인드가 올라가는 루틴이 필요해.",
    # 존댓말 / 격식
    "연기가 감지되면 사이렌을 울려 주시겠어요?",
    "거실 온도가 26도 이상이면 에어컨을 켜 주십시오.",
    "버튼이 눌리면 침실 조명을 최대 밝기로 켜 주세요.",
    # 명사형 / 체언 종결
    "재실 감지 시 거실 조명 점등.",
    "온도 30도 초과 시 에어컨 냉방 모드, 25도 미만 시 에어컨 끔.",
    "매 10분 온도 확인, 30도 이상이면 에어컨 쿨모드.",
    # 구어 / 축약
    "누구 들어오면 불 좀 켜줘.",
    "습도 높으면 제습기 돌려.",
    "문 열리면 사진 찍고 나한테 스피커로 말해줘.",
    "비 오면 창문 닫아주고 한 시간 있다가 다시 열어.",
    # 영어/외래어 섞임
    "living room 온도가 28도 이상이면 AC 켜줘.",
    "모션 센서 트리거되면 카메라로 스냅샷 찍어줘.",
    # 조건 후치 (단조성 위반)
    "조명을 모두 꺼줘, 밤 12시 이후에 사람이 감지되면.",
    "에어컨을 켜줘, 온도가 28도 이상일 때만.",
    "사이렌을 울려줘 연기가 감지되는 경우에.",
    # 장문 / 복합
    "평일 오전 8시부터 오후 6시까지는 30분마다 온도를 확인해서 28도 이상이면 에어컨을 켜고 24도 이하로 떨어지면 다시 꺼줘.",
    "문이 열린 채로 5분이 지나면 스피커로 문을 닫아달라고 말하고, 그래도 안 닫히면 10분 뒤에 한 번 더 말해줘.",
    "사람이 없고 조명이 켜져 있으면 조명을 끄고, 사람이 있고 조도가 낮으면 조명을 켜줘.",
    # 시간 표현 변형
    "삼십 분 후에 가습기 꺼줘.",
    "한 시간 반 뒤에 에어컨 끄고 창문 열어줘.",
    "이따가 저녁 8시 되면 커튼 닫아줘.",
    # 부정/예외
    "주말에는 아침 알람 스피커 켜지 마.",
    "사람이 감지되지 않는 동안에는 조명을 꺼 둬.",
    # 질문형 요청
    "온도가 30도 넘으면 알려줄 수 있어?",
    "문 열리면 사진 찍어서 메일로 보내줄래?",
]

# ── 학습 데이터(382 전체) ─────────────────────────────────────────────
H = np.load(os.path.join(HERE, "..", "head", "states.npz"))
HX = H["X"]; LAYERS = list(H["layers"])
T = json.load(open(os.path.join(HERE, "type_labels.json")))
row_of = {(c, t): i for i, (c, t) in enumerate(zip(H["cmd_idx"], H["word_pos"]))}
LB, LT = LAYERS.index(2), LAYERS.index(6)
# 경계 head: 직전+현재, L2
Xb, yb = [], []
for ci, it in enumerate(T):
    for t in range(1, len(it["words"])):
        Xb.append(np.concatenate([HX[row_of[(ci, t - 1)], LB], HX[row_of[(ci, t)], LB]])); yb.append(it["gold_labels"][t])
Xb, yb = np.array(Xb, np.float32), np.array(yb)
scb = StandardScaler().fit(Xb); clf_b = LogisticRegression(max_iter=2000, C=1.0).fit(scb.transform(Xb), yb)
# 타입 head: 절 마지막 단어 ctx_last, L6, PCA256
Xt, yt = [], []
for ci, it in enumerate(T):
    starts = [k for k, l in enumerate(it["gold_labels"]) if l == 1 or k == 0]
    ends = starts[1:] + [len(it["words"])]
    for s, (a, b) in zip(it["segments"], zip(starts, ends)):
        Xt.append(HX[row_of[(ci, b - 1)], LT]); yt.append(s["type"])
Xt = np.array(Xt, np.float32); yt = np.array(yt)
sct = StandardScaler().fit(Xt); pca = PCA(256, random_state=0).fit(sct.transform(Xt))
clf_t = LogisticRegression(max_iter=1000, C=0.5).fit(pca.transform(sct.transform(Xt)), yt)

# ── 모델 ──
tok = AutoTokenizer.from_pretrained(MODEL)
cfg = AutoConfig.from_pretrained(MODEL)
q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]; cfg.quantization_config = q
model = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map="cuda").eval()

def states(text):
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
    f = np.stack([hs[L + 1][0, last].float().cpu().numpy() for L in LAYERS], axis=1)
    return words, f

out = []
for text in CASES:
    words, F = states(text)
    lab = [1] + [int(clf_b.predict(scb.transform(np.concatenate([F[t - 1, LB], F[t, LB]])[None]))[0]) for t in range(1, len(words))]
    pb = [1.0] + [float(clf_b.predict_proba(scb.transform(np.concatenate([F[t - 1, LB], F[t, LB]])[None]))[0, 1]) for t in range(1, len(words))]
    segs, cur, ends = [], [], []
    for i, (w, l) in enumerate(zip(words, lab)):
        if l == 1 and cur:
            segs.append(" ".join(cur)); ends.append(i - 1); cur = []
        cur.append(w)
    segs.append(" ".join(cur)); ends.append(len(words) - 1)
    types = [str(clf_t.predict(pca.transform(sct.transform(F[e, LT][None])))[0]) for e in ends]
    out.append({"text": text, "segs": segs, "types": types, "prob": [round(x, 2) for x in pb]})
    print(text)
    print("   " + " ‖ ".join(f"[{t}] {s}" for s, t in zip(segs, types)))
json.dump(out, open(os.path.join(HERE, "ood_probe.json"), "w"), ensure_ascii=False, indent=1)
