# -*- coding: utf-8 -*-
"""인코더 — (1) 2B 모델의 단어별 은닉 상태(층 2·6, 단어 마지막 토큰; prefill 1회, 생성 없음) — 단일 vLLM 엔진의 hook  (2) Qwen3-Embedding 문장 임베딩."""
import os, sys
import numpy as np, torch, torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path: sys.path.insert(0, _ROOT)

DEV = "cuda" if torch.cuda.is_available() else "cpu"
EMB_ID = "Qwen/Qwen3-Embedding-0.6B"
LAYERS = (2, 6)                     # 경계 head = 층 2(직전+현재 단어), 타입·mods·그래프 head = 층 6(절 끝 단어) — engine.LAYERS 와 같아야 함

class WordEncoder:
    """텍스트 → (words, states[n_words, len(LAYERS), 2048]) — 단일 엔진(engine.Engine)의 층 2·6 hook 으로 얻는다.
    채팅 템플릿 없이 원문 그대로, 단어 마지막 토큰. (학습 때 HF transformers 로 뽑은 상태와 cos≈0.9999 동일)"""
    def __init__(self, engine=None):
        if engine is None:
            from engine import get_engine
            engine = get_engine()
        self.engine = engine
    def __call__(self, text):
        return self.engine.word_states(text)

class RemoteEmbedder:
    """엔진 서버(engine_server.py)의 /embed 프록시 — Embedder 와 호출 모양이 같다."""
    def __init__(self, url):
        import requests
        self.url = url.rstrip("/")
        self.http = requests.Session()
    def __call__(self, texts, instruct=None, batch=32):
        from engine import from_b64
        texts = list(texts)
        if not texts: return np.zeros((0, 1024), np.float32)
        r = self.http.post(self.url + "/embed",
                           json={"texts": texts, "instruct": instruct, "batch": batch}, timeout=600)
        r.raise_for_status()
        o = r.json()
        return from_b64(o["vectors"], o["shape"])

def make_embedder(model_id=None):
    """JOI_ENGINE_URL 이 있으면 서버 임베딩, 없으면 이 프로세스에 0.6B 적재."""
    url = os.environ.get("JOI_ENGINE_URL")
    return RemoteEmbedder(url) if url else Embedder(model_id or EMB_ID)

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
