"""joi_slm — 한국어 IoT 명령어 → Timeline IR (선형 head + 규칙 조립, 모델 생성 없음). 사용법은 README.md."""
from .pipeline import CommandToIR
from .builder import build, Mapping
from .evaluate import grade, gold_fix
