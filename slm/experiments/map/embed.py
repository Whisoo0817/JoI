# -*- coding: utf-8 -*-
"""임베더 — Qwen3-Embedding-0.6B (transformers 직접, 마지막 토큰 풀링 + 정규화)."""
import torch, torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel

MODEL = "Qwen/Qwen3-Embedding-0.6B"
_tok = _model = None
DEV = "cuda" if torch.cuda.is_available() else "cpu"

def _load():
    global _tok, _model
    if _model is None:
        _tok = AutoTokenizer.from_pretrained(MODEL, padding_side="left")
        _model = AutoModel.from_pretrained(MODEL, dtype=torch.bfloat16).to(DEV).eval()

def embed(texts, instruct=None, batch=32):
    """instruct가 있으면 질의용 'Instruct: …\\nQuery: …' 형식(Qwen3 권장). 문서는 원문 그대로."""
    _load()
    out = []
    for i in range(0, len(texts), batch):
        chunk = texts[i:i + batch]
        if instruct:
            chunk = [f"Instruct: {instruct}\nQuery: {t}" for t in chunk]
        enc = _tok(chunk, padding=True, truncation=True, max_length=256, return_tensors="pt").to(DEV)
        with torch.no_grad():
            h = _model(**enc).last_hidden_state
        v = h[:, -1]                       # left padding → 마지막 토큰이 EOS 자리
        out.append(F.normalize(v.float(), dim=-1).cpu())
    return torch.cat(out).numpy()
