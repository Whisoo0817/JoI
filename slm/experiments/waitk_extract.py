# -*- coding: utf-8 -*-
"""Extract per-word hidden states from Qwen3.5-2B-AWQ, causal vs full-context.

Input text = "<cmd> ### <cmd>" (echo). Word states from copy 1 see only the left
prefix (causal); word states from copy 2 see the entire command (full context).
Feature per word = hidden state of its LAST subword token, at selected layers.
"""
import csv, json
import numpy as np
import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
from transformers.utils.quantization_config import CompressedTensorsConfig

torch.set_num_threads(28)
MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
DATA = "/home/ikess/joi-llm/joi_new/dataset.csv"
OUT = "waitk_states.npz"
SEP = " ### "

rows = list(csv.DictReader(open(DATA)))
seen, cmds = set(), []
for r in rows:
    c = (r["command_kor"] or "").strip()
    if c and c not in seen and 4 <= len(c.split()) <= 25:
        seen.add(c); cmds.append(c)
print("commands:", len(cmds), flush=True)

tok = AutoTokenizer.from_pretrained(MODEL)
cfg = AutoConfig.from_pretrained(MODEL)
q = dict(cfg.quantization_config)
q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]
cfg.quantization_config = q
model = AutoModelForCausalLM.from_pretrained(
    MODEL, config=cfg, dtype=torch.bfloat16, attn_implementation="eager",
    device_map="cpu", quantization_config=CompressedTensorsConfig(run_compressed=True),
)
model.eval()
NL = model.config.num_hidden_layers
LAYERS = sorted(set([2, NL // 4, NL // 2, (3 * NL) // 4, NL - 1]))
print("num_hidden_layers:", NL, "-> probing layers", LAYERS, flush=True)

def word_last_token(text, words, base, offsets):
    """index of last token of each word, for the copy starting at char `base`."""
    spans, p = [], base
    for w in words:
        s = text.index(w, p)
        spans.append((s, s + len(w)))
        p = s + len(w)
    idxs = []
    for ws, we in spans:
        last = None
        for ti, (ts, te) in enumerate(offsets):
            if te > ts and ts < we and te > ws:
                last = ti
        idxs.append(last)
    return idxs

X1, X2, cmd_idx, word_pos, words_all = [], [], [], [], []
for ci, cmd in enumerate(cmds):
    words = cmd.split()
    n = len(words)
    text = cmd + SEP + cmd
    enc = tok(text, return_tensors="pt", return_offsets_mapping=True, add_special_tokens=False)
    offsets = enc.pop("offset_mapping")[0].tolist()
    idx1 = word_last_token(text, words, 0, offsets)
    idx2 = word_last_token(text, words, len(cmd) + len(SEP), offsets)
    if any(i is None for i in idx1 + idx2):
        print("skip (token map fail):", cmd, flush=True); continue
    with torch.no_grad():
        out = model(**enc, output_hidden_states=True)
    hs = out.hidden_states  # tuple (NL+1) of (1, T, d); hs[L+1] = output of layer L
    f1 = np.stack([hs[L + 1][0, idx1].float().numpy() for L in LAYERS], axis=1)  # (n, nlay, d)
    f2 = np.stack([hs[L + 1][0, idx2].float().numpy() for L in LAYERS], axis=1)
    del out, hs
    X1.append(f1.astype(np.float16)); X2.append(f2.astype(np.float16))
    cmd_idx += [ci] * n
    word_pos += list(range(n))
    words_all += words
    if (ci + 1) % 20 == 0:
        print(f"{ci+1}/{len(cmds)}", flush=True)

np.savez_compressed(
    OUT,
    X1=np.concatenate(X1), X2=np.concatenate(X2),
    cmd_idx=np.array(cmd_idx), word_pos=np.array(word_pos),
    layers=np.array(LAYERS),
)
json.dump({"cmds": cmds, "words": words_all}, open("waitk_meta.json", "w"), ensure_ascii=False)
print("saved", OUT, flush=True)
