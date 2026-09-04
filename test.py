"""Run the current JoI pipeline over rows in dataset.csv.

Examples:
    python test.py --limit 3
    python test.py --category C01,C03 --index 1,2
    python test.py --gt-ir --category C20 --output /tmp/c20.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import time
from pathlib import Path

from lowering.run_local_ir import generate_joi_code

ROOT = Path(__file__).resolve().parent


def _set(value: str) -> set[str]:
    return {x.strip() for x in value.split(",") if x.strip()}


def load_rows(categories: set[str], indices: set[str], limit: int) -> list[dict]:
    with (ROOT / "dataset.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if categories:
        rows = [r for r in rows if r["category_v2"] in categories]
    if indices:
        rows = [r for r in rows if r["index"] in indices]
    return rows[:limit] if limit else rows


def run_row(row: dict, use_gt_ir: bool) -> dict:
    key = f'{row["category_v2"]}_{int(float(row["index"])):03d}'
    devices = json.loads(row["connected_devices"])
    gt_path = None
    started = time.perf_counter()
    try:
        if use_gt_ir:
            if not row.get("ir_gt", "").strip():
                raise ValueError("ir_gt is empty")
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                             encoding="utf-8") as f:
                json.dump(json.loads(row["ir_gt"]), f, ensure_ascii=False)
                gt_path = f.name
            os.environ["JOI_GT_IR_PATH"] = gt_path
        else:
            os.environ.pop("JOI_GT_IR_PATH", None)

        result = generate_joi_code(row["command_kor"], devices, {})
        return {
            "key": key,
            "mode": "gt_ir" if use_gt_ir else "nl",
            "status": "ok",
            "elapsed_sec": round(time.perf_counter() - started, 3),
            "command_kor": row["command_kor"],
            **result,
        }
    except Exception as e:
        return {
            "key": key,
            "mode": "gt_ir" if use_gt_ir else "nl",
            "status": "error",
            "elapsed_sec": round(time.perf_counter() - started, 3),
            "command_kor": row["command_kor"],
            "error_code": getattr(e, "error_code", type(e).__name__),
            "error": str(e),
            "logs": getattr(e, "logs", ""),
        }
    finally:
        os.environ.pop("JOI_GT_IR_PATH", None)
        if gt_path:
            Path(gt_path).unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gt-ir", action="store_true",
                    help="inject each row's ir_gt instead of extracting IR")
    ap.add_argument("-c", "--category", default="", help="comma-separated categories")
    ap.add_argument("-i", "--index", default="", help="comma-separated row indices")
    ap.add_argument("-n", "--limit", type=int, default=0)
    ap.add_argument("-o", "--output", type=Path, help="optional JSONL result path")
    args = ap.parse_args()

    rows = load_rows(_set(args.category), _set(args.index), args.limit)
    if not rows:
        ap.error("no dataset rows matched")

    out = None
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        out = args.output.open("w", encoding="utf-8")
    try:
        for pos, row in enumerate(rows, 1):
            result = run_row(row, args.gt_ir)
            gate = result.get("gate", {}).get("verdict", "-")
            print(f'[{pos}/{len(rows)}] {result["key"]}: '
                  f'{result["status"]} gate={gate} ({result["elapsed_sec"]}s)', flush=True)
            if out:
                out.write(json.dumps(result, ensure_ascii=False) + "\n")
                out.flush()
    finally:
        if out:
            out.close()


if __name__ == "__main__":
    main()
