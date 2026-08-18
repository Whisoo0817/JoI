# -*- coding: utf-8 -*-
"""pairs.json 문장의 단어별 hidden state (L2, L6; 각 단어 마지막 토큰) → pairs_words.npz  (종단 평가용: 경계·타입·역할 head를 예측 경계 위에서)"""
import json, os, numpy as np, torch
from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
P = json.load(open(os.path.join(HERE, "pairs.json")))
tok = AutoTokenizer.from_pretrained(MODEL); cfg = AutoConfig.from_pretrained(MODEL)
q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]; cfg.quantization_config = q
model = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map="cuda").eval()
LAYERS = [2, 6]
X, pid, wpos = [], [], []
for i, x in enumerate(P):
    text = x["cmd"]; words = text.split()
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
    with torch.no_grad():
        hs = model(**{k: v.to("cuda") for k, v in enc.items()}, output_hidden_states=True).hidden_states
    F = np.stack([hs[l + 1][0, last].float().cpu().numpy() for l in LAYERS], 1)
    for w in range(len(words)): X.append(F[w]); pid.append(i); wpos.append(w)
np.savez_compressed(os.path.join(HERE, "pairs_words.npz"), X=np.array(X, np.float16), pid=np.array(pid), wpos=np.array(wpos), layers=np.array(LAYERS))
print("단어", len(X))
