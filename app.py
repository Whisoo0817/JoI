from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

import httpx
import openai

from run_local import generate_joi_code, JoiGenerationError
from schemas import JoiErrorCode, JoiLLMResponse, JoiLog, JoiCodeItem
from warmup import warmup as sllm_warmup

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

class GenerateJOICodeRequest(BaseModel):
    sentence: str
    model: str
    connected_devices: Dict[str, Any]
    current_time: str
    other_params: Optional[List[Dict[str, Any]]] = None

# ── 엔드포인트 ─────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "active"}


@app.post("/warmup")
async def warmup_endpoint():
    """vLLM prefix caching 웜업"""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: sllm_warmup(base_url=SLLM_LOCAL_BASE_URL))
    return {"status": "done"}



def _success_response(result: Dict[str, Any]) -> JoiLLMResponse:
    """generate_joi_code의 성공 dict를 JoiLLMResponse로 변환."""
    raw_code = result.get("code")
    code_field: Optional[Any]
    if isinstance(raw_code, list):
        code_field = [JoiCodeItem(**item) if isinstance(item, dict) else item for item in raw_code]
    else:
        code_field = raw_code

    log_dict = result.get("log") or {}
    return JoiLLMResponse(
        success=True,
        error_code=JoiErrorCode.SUCCESS,
        error_message="",
        code=code_field,
        command=result.get("command"),
        log=JoiLog(**log_dict) if isinstance(log_dict, dict) else None,
    )


def _error_response(
    sentence: str,
    error_code: int,
    error_message: str,
    logs: str = "",
) -> JoiLLMResponse:
    return JoiLLMResponse(
        success=False,
        error_code=error_code,
        error_message=error_message,
        command=sentence,
        log=JoiLog(logs=logs),
    )


def _classify_exception(exc: Exception) -> int:
    """vLLM/네트워크 예외를 ErrorCode로 매핑."""
    if isinstance(exc, (httpx.TimeoutException, openai.APITimeoutError)):
        return JoiErrorCode.VLLM_TIMEOUT
    if isinstance(exc, (httpx.ConnectError, openai.APIConnectionError)):
        return JoiErrorCode.VLLM_UNAVAILABLE
    return JoiErrorCode.INTERNAL_ERROR


@app.post("/generate_joi_code", response_model=JoiLLMResponse)
async def generate_joi_code_endpoint(request: GenerateJOICodeRequest):
    try:
        result = generate_joi_code(
            sentence=request.sentence,
            connected_devices=request.connected_devices,
            other_params=request.other_params,
            base_url=SLLM_LOCAL_BASE_URL
        )
        return _success_response(result)
    except JoiGenerationError as e:
        return _error_response(
            sentence=request.sentence,
            error_code=int(getattr(e, "error_code", JoiErrorCode.INTERNAL_ERROR)),
            error_message=str(e),
            logs=getattr(e, "logs", ""),
        )
    except Exception as e:
        return _error_response(
            sentence=request.sentence,
            error_code=_classify_exception(e),
            error_message=str(e),
            logs=str(e),
        )


@app.post("/re_generate_joi_code", response_model=JoiLLMResponse)
async def re_generate_joi_code_endpoint(request: GenerateJOICodeRequest):
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
            connected_devices={},
            other_params=request.other_params,
            modification=modification_text,
            base_url=SLLM_LOCAL_BASE_URL
        )
        return _success_response(result)
    except JoiGenerationError as e:
        return _error_response(
            sentence=request.sentence,
            error_code=int(getattr(e, "error_code", JoiErrorCode.INTERNAL_ERROR)),
            error_message=str(e),
            logs=getattr(e, "logs", ""),
        )
    except Exception as e:
        return _error_response(
            sentence=request.sentence,
            error_code=_classify_exception(e),
            error_message=str(e),
            logs=str(e),
        )


if __name__ == "__main__":
    print(f"[app] vLLM backend: {SLLM_LOCAL_BASE_URL}")
    uvicorn.run("app:app", host="0.0.0.0", port=49999, reload=True)
