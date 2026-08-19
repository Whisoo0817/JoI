# -*- coding: utf-8 -*-
"""엔진 서버 — 모델을 한 번만 올려두고 HTTP 로 빌려준다.

한 프로세스에 2B(engine.Engine, 층 2·6 hook 포함)와 임베딩 0.6B 를 올리고 네 가지를 서비스한다.
클라이언트(app.py / run.py / test.py …)는 `JOI_ENGINE_URL` 만 주면 그대로 원격을 쓴다 — 코드 수정 불필요.

  POST /word_states  {text}                        → {words, states(b64), shape}   2B 층 2·6 단어 상태
  POST /chat         {messages, max_tokens, …}     → {text, prompt_tokens, …}      lowering·이름
  POST /choice       {prompt, letters}             → {scores}                      객관식 게이트
  POST /embed        {texts, instruct, batch}      → {vectors(b64), shape}         서비스 매핑 임베딩
  GET  /health                                     → {ok, model, embed_model}

    ~/temp/bin/python engine_server.py                  # 0.0.0.0:49998
    JOI_ENGINE_URL=http://localhost:49998 python test.py C08
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from engine import MODEL_ID, Engine, to_b64

PORT = int(os.environ.get("JOI_ENGINE_PORT", "49998"))

app = FastAPI(title="joi engine")
_M: Dict[str, Any] = {"engine": None, "embedder": None}


def engine() -> Engine:
    if _M["engine"] is None:
        _M["engine"] = Engine()
    return _M["engine"]


def embedder():
    if _M["embedder"] is None:
        from joi_slm.encoder import EMB_ID, Embedder
        _M["embedder"] = Embedder()
        _M["embed_id"] = EMB_ID
    return _M["embedder"]


@app.on_event("startup")
def _preload():
    engine()
    embedder()
    print(f"[engine] ready — {MODEL_ID} + {_M.get('embed_id')} on :{PORT}", flush=True)


# ── 요청 모델 ─────────────────────────────────────────────
class WordStatesIn(BaseModel):
    text: str


class ChatIn(BaseModel):
    messages: List[Dict[str, Any]]
    max_tokens: int = 512
    temperature: float = 0.1
    enable_thinking: bool = False
    prefill: Optional[str] = None


class ChoiceIn(BaseModel):
    prompt: str
    letters: str


class EmbedIn(BaseModel):
    texts: List[str]
    instruct: Optional[str] = None
    batch: int = 32


# ── 엔드포인트 ────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True, "model": MODEL_ID, "embed_model": _M.get("embed_id")}


@app.post("/word_states")
def word_states(req: WordStatesIn):
    words, states = engine().word_states(req.text)
    return {"words": words, "states": to_b64(states), "shape": list(states.shape)}


@app.post("/chat")
def chat(req: ChatIn):
    text, p_tok, c_tok, finish, secs = engine().chat(
        req.messages, max_tokens=req.max_tokens, temperature=req.temperature,
        enable_thinking=req.enable_thinking, prefill=req.prefill)
    return {"text": text, "prompt_tokens": p_tok, "completion_tokens": c_tok,
            "finish_reason": finish, "seconds": secs}


@app.post("/choice")
def choice(req: ChoiceIn):
    return {"scores": engine().choice(req.prompt, req.letters)}


@app.post("/embed")
def embed(req: EmbedIn):
    v = embedder()(req.texts, instruct=req.instruct, batch=req.batch)
    return {"vectors": to_b64(v), "shape": list(v.shape)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
