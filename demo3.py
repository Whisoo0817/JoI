from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import json, os
import logging
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def _session_log_path(session_id: str) -> str:
    safe = session_id.replace("/", "_").replace("..", "_")
    return os.path.join(LOG_DIR, f"{safe}.log")

def _write_session_log(session_id: str, content: str):
    path = _session_log_path(session_id)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)

# joi_new backend
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'joi_new'))
from warmup import warmup as sllm_warmup
from agent import agent_chat, agent_chat_stream

import uvicorn

# ── vLLM 엔드포인트 ──────────────────────────────────────
SLLM_LOCAL_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8002/v1")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("uvicorn")


# ── 요청 모델 ──────────────────────────────────────────────

class AgentRequest(BaseModel):
    sentence: str
    connected_devices: Optional[Dict[str, Any]] = None
    session_id: str = "default"


# ── 전역 상태 ──────────────────────────────────────────────
print("현재 작업 디렉토리:", os.getcwd())
things_path = "./datasets/things.json"
if os.path.isfile(things_path):
    with open(things_path, "r", encoding="utf-8") as f:
        DEFAULT_CONNECTED_DEVICES = json.load(f)
else:
    print(f"파일 {things_path} 이(가) 존재하지 않습니다. 빈 dict를 사용합니다.")
    DEFAULT_CONNECTED_DEVICES = {}


# ── 모델 리스트 ────────────────────────────────────────────
AVAILABLE_MODELS = ["SLLM_Qwen3_5090"]


# ── 엔드포인트 ─────────────────────────────────────────────
@app.get("/get_model_list")
async def get_model_list():
    print("Send model list: ", AVAILABLE_MODELS)
    return {"models": AVAILABLE_MODELS}


@app.get("/health")
async def health_check():
    return {"status": "active", "timestamp": datetime.now().isoformat()}


@app.post("/warmup")
async def warmup_endpoint():
    """vLLM prefix caching 웜업"""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: sllm_warmup(base_url=SLLM_LOCAL_BASE_URL))
    return {"status": "done"}



@app.post("/chat")
async def chat_endpoint(request: AgentRequest):
    """Qwen3 Agent 모드: 서버 측 DB 세션을 통해 대화 맥락 자율 유지"""
    import asyncio

    devices = request.connected_devices or DEFAULT_CONNECTED_DEVICES
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 요청 로그
    _write_session_log(request.session_id, (
        f"\n{'='*60}\n"
        f"[{ts}] REQUEST\n"
        f"  sentence : {request.sentence}\n"
        f"  session  : {request.session_id}\n"
        f"  devices  : {json.dumps(devices, ensure_ascii=False)[:300]}\n"
    ))

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: agent_chat(
        user_message=request.sentence,
        session_id=request.session_id,
        connected_devices=devices,
        base_url=SLLM_LOCAL_BASE_URL,
    ))

    lr = result.get("last_result") or {}
    ts2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tool_logs = result.get("tool_logs", "")

    # 응답 로그
    _write_session_log(request.session_id, (
        f"[{ts2}] TOOL LOGS\n{tool_logs}\n"
        f"[{ts2}] RESPONSE\n"
        f"  response   : {result['response']}\n"
        f"  translated : {lr.get('log', {}).get('translated_sentence', '')}\n"
        f"  code       : {lr.get('code', '')}\n"
        f"  status     : {lr.get('status', '')}\n"
    ))

    return {
        "response": result["response"],
        "last_result": result.get("last_result")
    }


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args:
        # CLI 모드: python demo2.py "문장"
        sentence = " ".join(args)
        print(f"[CLI] Starting agent for: {sentence}")
        context = {"connected_devices": DEFAULT_CONNECTED_DEVICES}
        result = agent_chat(
            user_message=sentence,
            context=context,
            base_url=SLLM_LOCAL_BASE_URL,
        )
        lr = context.get("last_result")
        if lr and lr.get("code"):
            print(f"\n  [code]\n{lr['code']}")
            print(f"  [translated] {lr.get('log', {}).get('translated_sentence', '')}")
            print(f"  [time] {lr.get('log', {}).get('response_time', '')}")
    else:
        print(f"[demo2] vLLM backend: {SLLM_LOCAL_BASE_URL}")
        uvicorn.run("demo3:app", host="0.0.0.0", port=49999, reload=True)
