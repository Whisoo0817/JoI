from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import json, os
from datetime import datetime
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from run_local import generate_joi_code, JoiGenerationError

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
from agent import agent_chat_stream

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


# ── 요청 모델 ──────────────────────────────────────────────

class AgentRequest(BaseModel):
    sentence: str
    connected_devices: Optional[Dict[str, Any]] = None
    session_id: str = "default"

class GenerateJOICodeRequest(BaseModel):
    sentence: str
    model: str
    connected_devices: Dict[str, Any]
    current_time: str
    other_params: Optional[List[Dict[str, Any]]] = None

# ── 전역 상태 ──────────────────────────────────────────────
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
    return {"status": "active", "timestamp": datetime.now(_KST).isoformat()}


@app.post("/warmup")
async def warmup_endpoint():
    """vLLM prefix caching 웜업"""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: sllm_warmup(base_url=SLLM_LOCAL_BASE_URL))
    return {"status": "done"}



@app.post("/chat")
async def chat_endpoint(request: AgentRequest):
    """Qwen3 Agent 모드: SSE 스트리밍으로 토큰 단위 응답 반환"""
    devices = request.connected_devices or DEFAULT_CONNECTED_DEVICES
    ts = datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S")

    # 요청 로그
    _write_session_log(request.session_id, (
        f"\n{'='*60}\n"
        f"[{ts}] REQUEST\n"
        f"  sentence : {request.sentence}\n"
        f"  session  : {request.session_id}\n"
        f"  devices  : {json.dumps(devices, ensure_ascii=False)[:300]}\n"
    ))

    def on_tool_call(name, args, result):
        ts_tool = datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S")
        stage_logs = result.get('logs', '') if isinstance(result, dict) else ''
        _write_session_log(request.session_id, (
            f"[{ts_tool}] TOOL CALL: {name}\n"
            f"  args   : {json.dumps(args, ensure_ascii=False)}\n"
            f"  result : {json.dumps(result, ensure_ascii=False)[:300]}\n"
            + (f"  logs   :\n{stage_logs}\n" if stage_logs else "")
        ))

    def on_complete(message, last_result):
        ts2 = datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts2}] RESPONSE (stream complete)\n  message    : {message}\n"
        if last_result:
            lr = last_result
            entry += (
                f"  translated : {lr.get('log', {}).get('translated_sentence', '')}\n"
                f"  code       : {lr.get('code', '')}\n"
                f"  status     : {lr.get('status', '')}\n"
            )
        _write_session_log(request.session_id, entry)

    def generate():
        for chunk in agent_chat_stream(
            user_message=request.sentence,
            session_id=request.session_id,
            connected_devices=devices,
            base_url=SLLM_LOCAL_BASE_URL,
            on_complete=on_complete,
            on_tool_call=on_tool_call,
        ):
            yield chunk

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/generate_joi_code")
async def generate_joi_code_endpoint(request: GenerateJOICodeRequest):
    try:
        result = generate_joi_code(
            sentence=request.sentence,
            connected_devices=request.connected_devices,
            other_params=request.other_params,
            base_url=SLLM_LOCAL_BASE_URL
        )
        return result
    except JoiGenerationError as e:
        return {
            "code": "",
            "merged_command": request.sentence,
            "log": {
                "translated_sentence": "입력된 JOI Lang 코드가 없습니다. " + str(e),
                "mapped_devices": {},
                "logs": getattr(e, 'logs', '')
            },
            "error": str(e),
            "error_code": getattr(e, 'error_code', 'unknown')
        }
    except Exception as e:
        return {
            "code": "",
            "merged_command": request.sentence,
            "log": {
                "translated_sentence": "코드를 제공해 주시면 파싱해 드리겠습니다. (내부 에러 발생)",
                "mapped_devices": {},
                "logs": str(e)
            },
            "error": str(e)
        }

@app.post("/re_generate_joi_code")
async def re_generate_joi_code_endpoint(request: GenerateJOICodeRequest):
    # Extract modification feedback from other_params
    modification_text = None
    if request.other_params:
        for param in request.other_params:
            if "user_feedback" in param and param["user_feedback"]:
                mod = param["user_feedback"][0]
                if mod != "retry":
                    modification_text = mod.replace("extra:", "").strip()
                break
                
    try:
        result = generate_joi_code(
            sentence=request.sentence,
            connected_devices={}, # Can be inferred or cached, but run_local logic handles dictionary missing
            other_params=request.other_params,
            modification=modification_text,
            base_url=SLLM_LOCAL_BASE_URL
        )
        return result
    except JoiGenerationError as e:
        return {
            "code": "",
            "merged_command": request.sentence,
            "log": {
                "translated_sentence": "입력된 JOI Lang 코드가 없습니다. " + str(e),
                "mapped_devices": {},
                "logs": getattr(e, 'logs', '')
            },
            "error": str(e),
            "error_code": getattr(e, 'error_code', 'unknown')
        }
    except Exception as e:
        return {
            "code": "",
            "merged_command": request.sentence,
            "log": {
                "translated_sentence": "코드를 제공해 주시면 파싱해 드리겠습니다. (내부 에러 발생)",
                "mapped_devices": {},
                "logs": str(e)
            },
            "error": str(e)
        }


if __name__ == "__main__":
    print(f"[app] vLLM backend: {SLLM_LOCAL_BASE_URL}")
    uvicorn.run("app:app", host="0.0.0.0", port=49999, reload=True)
