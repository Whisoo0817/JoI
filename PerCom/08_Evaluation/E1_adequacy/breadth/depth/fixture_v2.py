"""E1-local fixture catalog, v2: the v1 stubs (fixture.py, unchanged) plus a daylight environment input.

Added for E1-072 v2 (author adjudication 2026-09-13): the automation reads a platform-provided daylight flag
instead of hard-coded 06:00/18:00. The global catalog has no sunrise/sunset/daylight value, so it is an E1 stub.
Sun-position computation stays the platform's responsibility; a history supplies the flag's values.
Output: depth/runs/fixture_catalog_v2.json (v1's fixture_catalog.json is not touched).
"""
import hashlib
import json
from pathlib import Path

import fixture

HERE = Path(__file__).resolve().parent
OUT = HERE / "runs" / "fixture_catalog_v2.json"

STUBS_V2 = fixture.STUBS + [
    fixture._skill("Sun", "platform daylight environment input (sunrise/sunset computed by the platform)",
                   values=[fixture._value("IsDaylight", "BOOL", "true between sunrise and sunset")]),
]


def build():
    base = json.loads(fixture.BASE.read_text(encoding="utf-8"))
    ids = {s["id"].lower() for s in base["skills"]}
    clash = [s["id"] for s in STUBS_V2 if s["id"].lower() in ids]
    if clash:
        raise SystemExit(f"stub ids collide with the global catalog: {clash}")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"skills": base["skills"] + STUBS_V2}, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(OUT), hashlib.sha256(OUT.read_bytes()).hexdigest()


if __name__ == "__main__":
    print(*build())
