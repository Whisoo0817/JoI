# -*- coding: utf-8 -*-
"""pairs.json 문장의 2B hidden state — 절 끝 단어(last)·절 첫 단어(first) 표현, 층 [2,6,12,18,23] → pairs_states.npz"""
import json, os, sys, numpy as np, torch
from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
P = json.load(open(os.path.join(HERE, "pairs.json")))
tok = AutoTokenizer.from_pretrained(MODEL); cfg = AutoConfig.from_pretrained(MODEL)
q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]; cfg.quantization_config = q
model = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map="cuda").eval()
NL = model.config.text_config.num_hidden_layers; LAYERS = sorted(set([2, NL // 4, NL // 2, (3 * NL) // 4, NL - 1]))

def states(text):
    words = text.split()
    enc = tok(text, return_tensors="pt", return_offsets_mapping=True, add_special_tokens=False)
    offsets = enc.pop("offset_mapping")[0].tolist()
    spans, p = [], 0
    for w in words:
        s = text.index(w, p); spans.append((s, s + len(w))); p = s + len(w)
    last, first = [], []
    for ws, we in spans:
        l = None; f = None
        for ti, (ts, te) in enumerate(offsets):
            if te > ts and ts < we and te > ws:
                l = ti; f = ti if f is None else f
        last.append(l); first.append(f)
    with torch.no_grad():
        hs = model(**{k: v.to("cuda") for k, v in enc.items()}, output_hidden_states=True).hidden_states
    L = np.stack([hs[l + 1][0, last].float().cpu().numpy() for l in LAYERS], 1)
    F = np.stack([hs[l + 1][0, first].float().cpu().numpy() for l in LAYERS], 1)
    return words, L, F

XL, XF, pid, cid = [], [], [], []
for i, x in enumerate(P):
    words, L, F = states(x["cmd"])
    # 절 경계: segs를 순서대로 단어 수로 자름
    k = 0
    for j, s in enumerate(x["segs"]):
        n = len(s.split()); a, b = k, k + n - 1; k += n
        assert " ".join(words[a:b + 1]) == s, (x["cmd"], s)
        XL.append(L[b]); XF.append(F[a]); pid.append(i); cid.append(j)
    if i % 200 == 0: print(i, flush=True)
np.savez_compressed(os.path.join(HERE, "pairs_states.npz"), last=np.array(XL, np.float16), first=np.array(XF, np.float16), pid=np.array(pid), cid=np.array(cid), layers=np.array(LAYERS))
print("절", len(XL))
