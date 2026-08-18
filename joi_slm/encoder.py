# -*- coding: utf-8 -*-
"""인코더 — (1) 2B 모델의 단어별 은닉 상태(층 2·6, 단어 마지막 토큰; prefill 1회, 생성 없음)  (2) Qwen3-Embedding 문장 임베딩."""
import numpy as np, torch, torch.nn.functional as F
from transformers import AutoConfig, AutoTokenizer, AutoModel, Qwen3_5ForConditionalGeneration

DEV = "cuda" if torch.cuda.is_available() else "cpu"
LM_ID = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
EMB_ID = "Qwen/Qwen3-Embedding-0.6B"
LAYERS = (2, 6)                     # 경계 head = 층 2(직전+현재 단어), 타입·mods·그래프 head = 층 6(절 끝 단어)

class WordEncoder:
    """텍스트 → (words, states[n_words, len(LAYERS), 2048]) — 채팅 템플릿 없이 원문 그대로 통과."""
    def __init__(self, model_id=LM_ID):
        self.tok = AutoTokenizer.from_pretrained(model_id); cfg = AutoConfig.from_pretrained(model_id)
        q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]; cfg.quantization_config = q
        self.model = Qwen3_5ForConditionalGeneration.from_pretrained(model_id, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map=DEV).eval()
    def __call__(self, text):
        words = text.split()
        enc = self.tok(text, return_tensors="pt", return_offsets_mapping=True, add_special_tokens=False)
        offsets = enc.pop("offset_mapping")[0].tolist(); spans, p = [], 0
        for w in words:
            s = text.index(w, p); spans.append((s, s + len(w))); p = s + len(w)
        last = [max((ti for ti, (ts, te) in enumerate(offsets) if te > ts and ts < we and te > ws), default=None) for ws, we in spans]
        with torch.no_grad(): hs = self.model(**{k: v.to(DEV) for k, v in enc.items()}, output_hidden_states=True).hidden_states
        return words, np.stack([hs[L + 1][0, last].float().cpu().numpy() for L in LAYERS], axis=1)

class Embedder:
    """Qwen3-Embedding-0.6B: 마지막 토큰 풀링 + 정규화. instruct가 있으면 질의 형식."""
    def __init__(self, model_id=EMB_ID):
        self.tok = AutoTokenizer.from_pretrained(model_id, padding_side="left")
        self.model = AutoModel.from_pretrained(model_id, dtype=torch.bfloat16).to(DEV).eval()
    def __call__(self, texts, instruct=None, batch=32):
        out = []
        for i in range(0, len(texts), batch):
            chunk = texts[i:i + batch]
            if instruct: chunk = [f"Instruct: {instruct}\nQuery: {t}" for t in chunk]
            enc = self.tok(chunk, padding=True, truncation=True, max_length=256, return_tensors="pt").to(DEV)
            with torch.no_grad(): h = self.model(**enc).last_hidden_state
            out.append(F.normalize(h[:, -1].float(), dim=-1).cpu())
        return torch.cat(out).numpy() if out else np.zeros((0, 1024), np.float32)
