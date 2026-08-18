"""모델 설정 — 모델은 하나(engine.py 의 단일 vLLM 엔진). 옛 OpenAI 클라이언트/HTTP 서버 경로는 없다."""
from engine import MODEL_ID, get_engine  # noqa: F401


def get_model_id() -> str:
    return MODEL_ID
