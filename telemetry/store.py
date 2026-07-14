"""SQLite 저장소: app.py 의 요청 추적(trace dict)을 data/requests.db 에 기록한다."""

import json
import os
import sqlite3
from typing import Any, Dict

# 프로젝트 루트 기준 고정 경로 (실행 cwd 와 무관)
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "requests.db"
)

# trace dict 의 키와 1:1 대응 (current_time 은 SQLite 예약어라 쿼리 시 따옴표 필요)
COLUMNS = (
    "timestamp", "command", "current_time", "extra_fields", "other_params",
    "outcome", "error_code", "error_message", "details",
    "translated_sentence", "process", "code",
)

# dict/list 값이라 JSON 문자열로 직렬화해서 넣는 컬럼
_JSON_COLUMNS = ("extra_fields", "other_params", "process", "code")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           TEXT NOT NULL,
    command             TEXT,
    "current_time"      TEXT,
    extra_fields        TEXT,
    other_params        TEXT,
    outcome             TEXT,
    error_code          INTEGER,
    error_message       TEXT,
    details             TEXT,
    translated_sentence TEXT,
    process             TEXT,
    code                TEXT
);
"""


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def record(trace: Dict[str, Any]) -> None:
    """trace 한 건을 requests 테이블에 insert 한다."""
    row = {k: trace.get(k) for k in COLUMNS}
    for k in _JSON_COLUMNS:
        if row[k] is not None:
            row[k] = json.dumps(row[k], ensure_ascii=False)
    cols = ", ".join(f'"{c}"' for c in COLUMNS)
    marks = ", ".join(f":{c}" for c in COLUMNS)
    with connect() as conn:
        conn.execute(f"INSERT INTO requests ({cols}) VALUES ({marks})", row)
    conn.close()
