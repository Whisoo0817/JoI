# -*- coding: utf-8 -*-
"""절 단독 재인코딩: gold 절 텍스트만 2B에 넣고 마지막 토큰(및 평균) 표현을 저장.
(문맥 속 마지막 단어 표현은 head/states.npz에서 바로 뽑을 수 있으므로 여기선 단독 인코딩만.)
"""
import json, os
import numpy as np, torch
from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
T = json.load(open(os.path.join(HERE, "type_labels.json")))
tok = AutoTokenizer.from_pretrained(MODEL)
cfg = AutoConfig.from_pretrained(MODEL)
q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]
cfg.quantization_config = q
DEV = "cuda" if torch.cuda.is_available() else "cpu"
model = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, config=cfg, dtype=torch.bfloat16,
                                                        attn_implementation="eager", device_map=DEV).eval()
NL = model.config.text_config.num_hidden_layers
LAYERS = sorted(set([2, NL // 4, NL // 2, (3 * NL) // 4, NL - 1]))
last, mean, cmd, segj = [], [], [], []
for o in T:
    for s in o["segments"]:
        enc = tok(s["text"], return_tensors="pt", add_special_tokens=False)
        with torch.no_grad():
            hs = model(**{k: v.to(DEV) for k, v in enc.items()}, output_hidden_states=True).hidden_states
        last.append(np.stack([hs[L + 1][0, -1].float().cpu().numpy() for L in LAYERS]))
        mean.append(np.stack([hs[L + 1][0].float().mean(0).cpu().numpy() for L in LAYERS]))
        cmd.append(o["i"]); segj.append(s["j"])
np.savez_compressed(os.path.join(HERE, "seg_states.npz"), last=np.array(last, np.float16),
                    mean=np.array(mean, np.float16), cmd=np.array(cmd), j=np.array(segj), layers=np.array(LAYERS))
print("절", len(cmd), "층", LAYERS, "저장 seg_states.npz")
