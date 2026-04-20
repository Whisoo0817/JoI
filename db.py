import json
import os
import sqlite3
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
os.makedirs(_DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(_DATA_DIR, "joi.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                command     TEXT NOT NULL,
                translated  TEXT,
                code        TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id          TEXT PRIMARY KEY,
                chat_history        TEXT NOT NULL DEFAULT '[]',
                last_result         TEXT,
                connected_devices   TEXT NOT NULL DEFAULT '{}',
                last_prompt_tokens  INTEGER NOT NULL DEFAULT 0,
                updated_at          TEXT NOT NULL
            )
        """)
        # 기존 DB에 컬럼이 없으면 추가
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN last_prompt_tokens INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass

_init_db()


def save_scenario(session_id: str, command: str, code: str, translated: str = ""):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO scenarios (session_id, command, translated, code, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, command, translated, code, datetime.utcnow().isoformat())
        )

def delete_scenario(scenario_id: int):
    with _get_conn() as conn:
        conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))

def get_scenarios(session_id: str):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, command, translated, code, created_at FROM scenarios WHERE session_id = ? ORDER BY id",
            (session_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Session Management ─────────────────────────────────────

def load_session(session_id: str) -> dict:
    """Load session state from DB. Returns default state if not found."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT chat_history, last_result, connected_devices FROM sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()
    if row:
        return {
            "chat_history": json.loads(row["chat_history"]),
            "last_result": json.loads(row["last_result"]) if row["last_result"] else None,
            "connected_devices": json.loads(row["connected_devices"]),
        }
    return {"chat_history": [], "last_result": None, "connected_devices": {}}


def save_session(session_id: str, chat_history: list, last_result, connected_devices):
    """Upsert session state to DB."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO sessions (session_id, chat_history, last_result, connected_devices, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                   chat_history = excluded.chat_history,
                   last_result = excluded.last_result,
                   connected_devices = excluded.connected_devices,
                   updated_at = excluded.updated_at""",
            (
                session_id,
                json.dumps(chat_history, ensure_ascii=False),
                json.dumps(last_result, ensure_ascii=False) if last_result else None,
                json.dumps(connected_devices, ensure_ascii=False) if isinstance(connected_devices, dict) else str(connected_devices),
                datetime.utcnow().isoformat(),
            )
        )

