from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
import json
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from paper.run_local_ir import generate_joi_code
from pipeline_helpers import JoiGenerationError
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
            # strict=False allows literal newlines inside string values — the
            # pipeline pretty-prints `script` with real newlines, so a multi-line
            # script (any condition/wait/cycle scenario) is otherwise invalid JSON
            # and would parse-fail here → code came back null for those.
            data = json.loads(raw_code, strict=False)
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


# ── 요청 추적 로그 ──────────────────────────────────────────
# connected_devices 덤프 대신, "어떤 명령이 들어와서 어떤 과정을 거쳐 어떤
# 결과/에러를 최종 반환했는지"를 request_log.jsonl 에 한 줄씩 기록한다.
# 최근 _MAX_LOG_ENTRIES 개만 유지한다 (오래된 줄은 버림).
_REQUEST_LOG_PATH = "request_log.jsonl"
_MAX_LOG_ENTRIES = 10


def _trace_request(request: "GenerateJOICodeRequest", response: JoiLLMResponse) -> None:
    try:
        log = response.log
        trace = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "command": request.sentence,          # 들어온 명령어
            "current_time": request.current_time,
            "outcome": "success" if response.success else "error",
            "error_code": int(response.error_code),
            "error_message": getattr(response, "error_message", None),
            "details": getattr(response, "details", None),
            "translated_sentence": getattr(log, "translated_sentence", None) if log else None,
            "process": getattr(log, "logs", None) if log else None,   # 거쳐온 과정
            "code": ([c.model_dump() for c in response.code]
                     if isinstance(response.code, list) else response.code),  # 최종 결과
        }
        # 기존 줄을 읽어 뒤에 새 항목을 붙이고, 최근 N개만 다시 쓴다.
        lines: List[str] = []
        if os.path.exists(_REQUEST_LOG_PATH):
            with open(_REQUEST_LOG_PATH, "r", encoding="utf-8") as _f:
                lines = [ln for ln in _f.read().splitlines() if ln.strip()]
        lines.append(json.dumps(trace, ensure_ascii=False))
        lines = lines[-_MAX_LOG_ENTRIES:]
        with open(_REQUEST_LOG_PATH, "w", encoding="utf-8") as _f:
            _f.write("\n".join(lines) + "\n")
        print(f"[app] /generate_joi_code  outcome={trace['outcome']}  "
              f"code={int(response.error_code)}  sentence={request.sentence!r}  "
              f"-> {_REQUEST_LOG_PATH}")
    except Exception as _e:
        print(f"[app] request trace dump failed: {_e}")


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
    try:
        result = generate_joi_code(
            sentence=request.sentence,
            connected_devices=request.connected_devices,
            other_params=request.other_params,
            base_url=SLLM_LOCAL_BASE_URL
        )
        response = _success_response(result)
    except JoiGenerationError as e:
        raw_code = getattr(e, "error_code", "")
        response = _error_response(
            sentence=request.sentence,
            error_code=int(map_error_code(raw_code)),
            error_message=str(e),
            details=f"stage_code={raw_code}" if raw_code else "",
            logs=getattr(e, "logs", ""),
        )
    except Exception as e:
        response = _error_response(
            sentence=request.sentence,
            error_code=int(_classify_exception(e)),
            error_message=str(e),
            details=type(e).__name__,
            logs=str(e),
        )

    # 명령 → 과정 → 결과/에러를 추적 로그로 남긴다 (connected_devices 덤프 대체).
    _trace_request(request, response)
    return response


if __name__ == "__main__":
    print(f"[app] vLLM backend: {SLLM_LOCAL_BASE_URL}")
    # Watch .md prompts too (not just .py) so editing files/*.md hot-reloads the
    # server. Prompts are loaded once at import (~0.5ms) so a full restart is cheap
    # (~0.24s); without this, .md edits would need a manual restart to take effect.
    uvicorn.run("app:app", host="0.0.0.0", port=49999, reload=True,
                reload_includes=["*.py", "*.md"])
