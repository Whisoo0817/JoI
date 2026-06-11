from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
import json
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from run_local import generate_joi_code, JoiGenerationError
from schemas import (
    JoiErrorCode, JoiLLMResponse, JoiLog, JoiCodeItem, map_error_code,
)
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



def _code_item(raw_code: Any) -> Optional[JoiCodeItem]:
    """Parse the pipeline's `code` (a JSON string of {name,cron,period,script})
    into a typed JoiCodeItem. Returns None if empty/unparseable."""
    if not raw_code:
        return None
    if isinstance(raw_code, JoiCodeItem):
        return raw_code
    data = raw_code
    if isinstance(raw_code, str):
        try:
            data = json.loads(raw_code)
        except Exception:
            return None
    if isinstance(data, dict):
        return JoiCodeItem(
            name=str(data.get("name", "Scenario")),
            cron=str(data.get("cron", "")),
            period=int(data.get("period", -1)) if str(data.get("period", "")).lstrip("-").isdigit() else -1,
            code=str(data.get("script", "")),
        )
    return None


def _success_response(result: Dict[str, Any]) -> JoiLLMResponse:
    log_dict = result.get("log") or {}
    return JoiLLMResponse(
        success=True,
        error_code=JoiErrorCode.SUCCESS,
        # Emit as a list to match the joi-agent proxy schema (Union[List, str]).
        code=([item] if (item := _code_item(result.get("code"))) is not None else None),
        log=JoiLog(**{k: log_dict[k] for k in ("response_time", "translated_sentence", "logs") if k in log_dict})
            if isinstance(log_dict, dict) else None,
    )


def _error_response(sentence: str, error_code: int, error_message: str,
                    details: str = "", logs: str = "") -> JoiLLMResponse:
    return JoiLLMResponse(
        success=False,
        error_code=error_code,
        error_message=error_message,
        details=details,
        command=sentence,
        log=JoiLog(logs=logs),
    )


def _classify_exception(exc: Exception) -> int:
    """Map an unexpected exception (network / vLLM) to a public code."""
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return JoiErrorCode.VLLM_TIMEOUT
    if "connect" in name or "unavailable" in name:
        return JoiErrorCode.VLLM_UNAVAILABLE
    return JoiErrorCode.INTERNAL_ERROR


@app.post("/generate_joi_code", response_model=JoiLLMResponse)
async def generate_joi_code_endpoint(request: GenerateJOICodeRequest):
    # 디버그: 실제로 받은 connected_devices를 파일로 덤프해 둔다. 서버 재시작
    # 사이에도 마지막 요청을 확인할 수 있게 항상 같은 경로에 덮어쓴다.
    try:
        _dbg = {
            "sentence": request.sentence,
            "current_time": request.current_time,
            "connected_devices": request.connected_devices,
        }
        with open("last_connected_devices.json", "w", encoding="utf-8") as _f:
            json.dump(_dbg, _f, ensure_ascii=False, indent=2)
        print(f"[app] /generate_joi_code  devices={len(request.connected_devices)}  "
              f"sentence={request.sentence!r}  -> last_connected_devices.json")
    except Exception as _e:
        print(f"[app] connected_devices dump failed: {_e}")
    try:
        result = generate_joi_code(
            sentence=request.sentence,
            connected_devices=request.connected_devices,
            other_params=request.other_params,
            base_url=SLLM_LOCAL_BASE_URL
        )
        return _success_response(result)
    except JoiGenerationError as e:
        raw_code = getattr(e, "error_code", "")
        return _error_response(
            sentence=request.sentence,
            error_code=int(map_error_code(raw_code)),
            error_message=str(e),
            details=f"stage_code={raw_code}" if raw_code else "",
            logs=getattr(e, "logs", ""),
        )
    except Exception as e:
        return _error_response(
            sentence=request.sentence,
            error_code=int(_classify_exception(e)),
            error_message=str(e),
            details=type(e).__name__,
            logs=str(e),
        )


if __name__ == "__main__":
    print(f"[app] vLLM backend: {SLLM_LOCAL_BASE_URL}")
    # Watch .md prompts too (not just .py) so editing files/*.md hot-reloads the
    # server. Prompts are loaded once at import (~0.5ms) so a full restart is cheap
    # (~0.24s); without this, .md edits would need a manual restart to take effect.
    uvicorn.run("app:app", host="0.0.0.0", port=49999, reload=True,
                reload_includes=["*.py", "*.md"])
