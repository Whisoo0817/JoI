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
