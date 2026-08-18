# -*- coding: utf-8 -*-
"""증강 json(cmd/words/labels/segs/types[/mods]) → 2B 은닉 상태 npz (X[n_words, layers, 2048] fp16, idx=(cmd_i, word_pos)). 사용: python extract_aug.py aug_polite.json"""
import json, os, sys, numpy as np, torch
from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration
HERE = os.path.dirname(os.path.abspath(__file__)); MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
src = sys.argv[1]; A = json.load(open(os.path.join(HERE, src))); cache = os.path.join(HERE, src.replace(".json", "_states.npz"))
tok = AutoTokenizer.from_pretrained(MODEL); cfg = AutoConfig.from_pretrained(MODEL)
q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]; cfg.quantization_config = q
model = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map="cuda").eval()
LAYERS = list(np.load(os.path.join(HERE, "..", "head", "states.npz"))["layers"])
feats, idx = [], []
for ci, x in enumerate(A):
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
    with torch.no_grad(): hs = model(**{k: v.to("cuda") for k, v in enc.items()}, output_hidden_states=True).hidden_states
    feats.append(np.stack([hs[L + 1][0, last].float().cpu().numpy() for L in LAYERS], axis=1).astype(np.float16)); idx += [(ci, t) for t in range(len(words))]
np.savez_compressed(cache, X=np.concatenate(feats), idx=np.array(idx), layers=np.array(LAYERS)); print("저장", cache, np.concatenate(feats).shape)
