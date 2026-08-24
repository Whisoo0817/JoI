# -*- coding: utf-8 -*-
"""5k 학습 몫 명령을 2B 모델에 통과시켜 단어별 내부 표현(hidden state)을 저장.

원본은 slm/experiments/head/extract_states.py — 읽는 곳만 이 폴더로 바꿨다.

- 입력은 명령어 원문 그대로 (채팅 템플릿 없음 — completion 실험에서 배운 교훈)
- 단어의 마지막 토큰 위치의 벡터를 그 단어의 표현으로 사용 (한국어 어미가 단어 끝에 있으므로)
- 여러 층에서 저장해서 어느 층이 절 경계 정보를 제일 잘 담는지 비교
"""
import json, os
import numpy as np
import torch
from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration

torch.set_num_threads(28)
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "cyankiwi/Qwen3.5-2B-AWQ-4bit"

items = json.load(open(os.path.join(HERE, "labels.json")))
print("명령:", len(items))

tok = AutoTokenizer.from_pretrained(MODEL)
cfg = AutoConfig.from_pretrained(MODEL)
q = dict(cfg.quantization_config)
q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]
cfg.quantization_config = q
# Qwen3.5는 복합(vision+text) 모델이라 AutoModelForCausalLM은 text_config만 받아
# quantization_config를 잃는다(패킹 가중치 미적재) → 전체 클래스로 적재해야 압축 해제가 걸린다.
DEV = "cuda" if torch.cuda.is_available() else "cpu"
model = Qwen3_5ForConditionalGeneration.from_pretrained(
    MODEL, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map=DEV)
model.eval()
NL = model.config.text_config.num_hidden_layers
LAYERS = sorted(set([2, NL // 4, NL // 2, (3 * NL) // 4, NL - 1]))
print("층 수:", NL, "→ 저장 층:", LAYERS)

X, cmd_idx, word_pos, ys = [], [], [], []
for ci, it in enumerate(items):
    text = it["cmd"]
    words = it["words"]
    enc = tok(text, return_tensors="pt", return_offsets_mapping=True, add_special_tokens=False)
    offsets = enc.pop("offset_mapping")[0].tolist()
    spans, p = [], 0
    for w in words:
        s = text.index(w, p)
        spans.append((s, s + len(w)))
        p = s + len(w)
    last_tok = []
    for ws, we in spans:
        last = None
        for ti, (ts, te) in enumerate(offsets):
            if te > ts and ts < we and te > ws:
                last = ti
        last_tok.append(last)
    if any(t is None for t in last_tok):
        print("skip:", text)
        continue
    with torch.no_grad():
        out = model(**{k: v.to(DEV) for k, v in enc.items()}, output_hidden_states=True)
    hs = out.hidden_states
    f = np.stack([hs[L + 1][0, last_tok].float().cpu().numpy() for L in LAYERS], axis=1)
    del out, hs
    X.append(f.astype(np.float16))
    cmd_idx += [ci] * len(words)
    word_pos += list(range(len(words)))
    ys += it["labels"]
    if (ci + 1) % 200 == 0:
        print(f"{ci+1}/{len(items)}", flush=True)

np.savez_compressed(os.path.join(HERE, "states.npz"),
                    X=np.concatenate(X), cmd_idx=np.array(cmd_idx),
                    word_pos=np.array(word_pos), y=np.array(ys),
                    layers=np.array(LAYERS))
print("저장 완료: states.npz")
