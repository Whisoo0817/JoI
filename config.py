import os
from openai import OpenAI

openai_api_key = "EMPTY"
openai_api_base = os.environ.get("LLM_BASE_URL", 
                                "http://localhost:8002/v1") # 환경 변수 없을 시 기본값

_cached_model_id = None


def get_client(base_url=None):
    return OpenAI(api_key=openai_api_key, base_url=base_url or openai_api_base)

# vLLM loaded model list (only 1)
def get_model_id(client):
    global _cached_model_id
    if _cached_model_id is None:
        _cached_model_id = client.models.list().data[0].id
    return _cached_model_id
