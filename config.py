import json
import os
import urllib.request

from openai import OpenAI

openai_api_key = "EMPTY"
openai_api_base = os.environ.get("LLM_BASE_URL",
                                "http://localhost:8002/v1")  # 환경 변수 없을 시 기본값

_cached_model_id = None


def get_client(base_url=None):
    return OpenAI(api_key=openai_api_key, base_url=base_url or openai_api_base)


def get_model_id(client):
    global _cached_model_id
    if _cached_model_id is None:
        _cached_model_id = client.models.list().data[0].id
    return _cached_model_id


def count_tokens(text: str, base_url: str = None) -> int:
    """vLLM /tokenize 엔드포인트로 정확한 토큰 수를 반환. 실패 시 -1."""
    try:
        vllm_base = (base_url or openai_api_base).rstrip("/").removesuffix("/v1")
        model = get_model_id(get_client(base_url))
        payload = json.dumps({"model": model, "prompt": text}).encode()
        req = urllib.request.Request(
            f"{vllm_base}/tokenize",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())["count"]
    except Exception:
        return -1
