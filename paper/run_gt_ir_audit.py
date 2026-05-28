#!/usr/bin/env python3
"""C1 — GT IR value-correctness audit (dump stage).

Foundation audit: every experiment number depends on `ir_gt` being a faithful
realization of `command_eng`. enum/arg audits already cover (a) enum validity
and (b) arg completeness/type. They do NOT catch the VALUE-ERROR class: a value
that is individually valid but wrong *with respect to the command* — e.g.
"X then Y" lowered as "X then X", a brightness of 80 where the command said 50,
`>` where the command implies `>=`, swapped then/else branch values, a 5-min
period written as 50 min, or a phase placed outside the cycle it belongs to.

This script does NOT judge. It dumps each dataset row into compact, chunked
JSON units for an Opus subagent to adjudicate (judge = highest available, no
self-audit by the 9B that generated the IR). The subagent returns per-row
verdicts; aggregation happens in `summarize` mode.

Usage:
  python3 paper/run_gt_ir_audit.py dump   [--chunk 40] [--out /tmp/gt_audit]
  python3 paper/run_gt_ir_audit.py summarize --verdicts /tmp/gt_audit/verdicts.jsonl
"""
import argparse
import csv
import json
import os
import sys

CSV_PATH = os.environ.get(
    "GT_AUDIT_CSV",
    os.path.join(os.path.dirname(__file__), "..", "dataset.csv"),
)


def _load_rows():
    with open(CSV_PATH, newline="") as f:
        return list(csv.DictReader(f))


def _unit(row):
    """Compact judging unit. Raw ir_gt is kept verbatim (the judge reads the
    9-op JSON directly); we do not pre-render to avoid hiding errors behind a
    lossy projection."""
    return {
        "index": row["index"],
        "category_v2": row["category_v2"],
        "command_eng": row["command_eng"],
        "ir_gt": row["ir_gt"],
        "connected_devices": row.get("connected_devices", ""),
    }


def dump(chunk_size, out_dir, categories):
    rows = _load_rows()
    if categories:
        cats = set(categories.split(","))
        rows = [r for r in rows if r["category_v2"] in cats]
    os.makedirs(out_dir, exist_ok=True)
    units = [_unit(r) for r in rows]
    n_chunks = 0
    for i in range(0, len(units), chunk_size):
        chunk = units[i : i + chunk_size]
        path = os.path.join(out_dir, f"chunk_{i // chunk_size:02d}.json")
        with open(path, "w") as f:
            json.dump(chunk, f, ensure_ascii=False, indent=1)
        n_chunks += 1
    print(f"[dump] {len(units)} rows -> {n_chunks} chunks (size {chunk_size}) in {out_dir}")
    print(f"[dump] categories: {sorted(set(u['category_v2'] for u in units))}")


def summarize(verdicts_path):
    """Aggregate subagent verdicts. Each line: {index, category_v2, verdict,
    severity, issue}. verdict in {CLEAR_PASS, SUSPICIOUS, CLEAR_FAIL}."""
    by_verdict = {"CLEAR_PASS": 0, "SUSPICIOUS": 0, "CLEAR_FAIL": 0}
    flagged = []
    with open(verdicts_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            v = json.loads(line)
            verdict = v.get("verdict", "?")
            by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
            if verdict in ("SUSPICIOUS", "CLEAR_FAIL"):
                flagged.append(v)
    total = sum(by_verdict.values())
    print(f"=== GT IR value-audit summary ({total} rows) ===")
    for k in ("CLEAR_PASS", "SUSPICIOUS", "CLEAR_FAIL"):
        print(f"  {k:12s} {by_verdict.get(k, 0)}")
    print(f"\n--- {len(flagged)} flagged rows (review) ---")
    flagged.sort(key=lambda x: (x.get("verdict"), x.get("category_v2", ""), x.get("index", "")))
    for v in flagged:
        print(f"[{v.get('verdict')}] {v.get('category_v2')} idx={v.get('index')} "
              f"({v.get('issue_class','?')}): {v.get('issue','')}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    d = sub.add_parser("dump")
    d.add_argument("--chunk", type=int, default=40)
    d.add_argument("--out", default="/tmp/gt_audit")
    d.add_argument("--categories", default="", help="comma-separated, e.g. C01,C02")
    s = sub.add_parser("summarize")
    s.add_argument("--verdicts", required=True)
    args = ap.parse_args()
    if args.mode == "dump":
        dump(args.chunk, args.out, args.categories)
    elif args.mode == "summarize":
        summarize(args.verdicts)


if __name__ == "__main__":
    main()
