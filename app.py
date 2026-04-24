from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from run_local import generate_joi_code, JoiGenerationError
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

                "logs": str(e)
            },
            "error": str(e)
        }


if __name__ == "__main__":
    print(f"[app] vLLM backend: {SLLM_LOCAL_BASE_URL}")
    uvicorn.run("app:app", host="0.0.0.0", port=49999, reload=True)
