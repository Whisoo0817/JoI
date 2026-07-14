"""요청 추적 저장/조회.

- 저장: app.py 가 요청마다 telemetry.record(trace) 호출 → data/requests.db (SQLite, 손실 없음)
- 조회: python -m telemetry.query --help
"""

from telemetry.store import record, DB_PATH

__all__ = ["record", "DB_PATH"]
