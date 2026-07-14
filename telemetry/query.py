"""요청 추적 로그 조회 CLI.

    python -m telemetry.query                  # 최근 20건 요약
    python -m telemetry.query --last 50        # 최근 50건
    python -m telemetry.query --errors         # 실패 건만
    python -m telemetry.query --since 7d       # 최근 7일 (또는 2026-07-01 형식)
    python -m telemetry.query --grep 에어컨     # command/error_message 부분 검색
    python -m telemetry.query --id 12          # 해당 건 전체(JSON) 출력
    python -m telemetry.query --stats          # outcome / error_code 별 집계
"""

import argparse
import json
import re
import sqlite3
from datetime import datetime, timedelta

from telemetry.store import DB_PATH, connect, _JSON_COLUMNS


def _parse_since(value: str) -> str:
    """'7d' / '12h' / 'YYYY-MM-DD' → timestamp 비교용 ISO 문자열."""
    m = re.fullmatch(r"(\d+)([dh])", value)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = timedelta(days=n) if unit == "d" else timedelta(hours=n)
        return (datetime.now() - delta).isoformat(timespec="seconds")
    return value  # ISO 날짜 문자열은 그대로 사전순 비교


def _summary_line(row: sqlite3.Row) -> str:
    mark = "ok " if row["outcome"] == "success" else f"E{row['error_code']:<4}"
    line = f"{row['id']:>5}  {row['timestamp']}  {mark}  {row['command']}"
    if row["outcome"] != "success" and row["error_message"]:
        line += f"  | {row['error_message']}"
    return line


def _print_full(row: sqlite3.Row) -> None:
    rec = dict(row)
    for k in _JSON_COLUMNS:
        if rec.get(k):
            rec[k] = json.loads(rec[k])
    print(json.dumps(rec, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="요청 추적 로그 조회 (data/requests.db)")
    ap.add_argument("--last", type=int, default=20, help="최근 N건 (기본 20)")
    ap.add_argument("--errors", action="store_true", help="실패 건만")
    ap.add_argument("--since", help="기간: 7d, 12h 또는 YYYY-MM-DD")
    ap.add_argument("--grep", help="command/error_message 부분 문자열 검색")
    ap.add_argument("--id", type=int, help="해당 id 한 건을 전체(JSON)로 출력")
    ap.add_argument("--full", action="store_true", help="요약 대신 전체(JSON)로 출력")
    ap.add_argument("--stats", action="store_true", help="outcome / error_code 별 건수 집계")
    args = ap.parse_args()

    conn = connect()
    conn.row_factory = sqlite3.Row

    if args.id is not None:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (args.id,)).fetchone()
        if row is None:
            print(f"id={args.id} 없음")
        else:
            _print_full(row)
        return

    if args.stats:
        print(f"[{DB_PATH}]")
        for row in conn.execute(
            "SELECT outcome, error_code, COUNT(*) AS n FROM requests"
            " GROUP BY outcome, error_code ORDER BY n DESC"
        ):
            label = "success" if row["outcome"] == "success" else f"error {row['error_code']}"
            print(f"  {row['n']:>5}  {label}")
        total = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        print(f"  total {total}")
        return

    where, params = [], []
    if args.errors:
        where.append("outcome != 'success'")
    if args.since:
        where.append("timestamp >= ?")
        params.append(_parse_since(args.since))
    if args.grep:
        where.append("(command LIKE ? OR error_message LIKE ?)")
        params += [f"%{args.grep}%"] * 2
    sql = "SELECT * FROM requests"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(args.last)

    rows = conn.execute(sql, params).fetchall()
    for row in reversed(rows):  # 시간순 출력
        if args.full:
            _print_full(row)
        else:
            print(_summary_line(row))
    if not rows:
        print("(조건에 맞는 기록 없음)")


if __name__ == "__main__":
    main()
