#!/usr/bin/env python3
"""E1 reporter: re-print the aggregate table from results.json + the biggest
per-item fact_recall gaps between arms.

Standalone: needs only results.json (no server, no seg/score/prompts).

Usage
  /home/ikess/joi-llm/venv_llama/bin/python report.py
  /home/ikess/joi-llm/venv_llama/bin/python report.py --results results.json --top 10
  /home/ikess/joi-llm/venv_llama/bin/python report.py --selftest
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from common_e1 import (  # noqa: E402
    ALL_ARMS,
    aggregate,
    as_float,
    format_comparisons,
    format_extra_table,
    format_table,
    is_num,
    metric_of,
    op_seq,
)

DEFAULT_RESULTS = os.path.join(HERE, "results.json")


def load_results(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        data = {"items": data, "meta": {}, "aggregate": None}
    data.setdefault("items", [])
    data.setdefault("meta", {})
    return data


def arms_in(items):
    seen = []
    for it in items:
        for a in (it.get("arms") or {}):
            if a not in seen:
                seen.append(a)
    return [a for a in ALL_ARMS if a in seen] + [a for a in seen if a not in ALL_ARMS]


def gap_rows(items, arms):
    """Per-item spread of fact_recall across arms (only items covered by >=2 arms)."""
    rows = []
    for it in items:
        vals = {}
        for arm in arms:
            rec = (it.get("arms") or {}).get(arm)
            if not isinstance(rec, dict):
                continue
            v = as_float(metric_of(rec, "fact_recall"))
            if is_num(v):
                vals[arm] = v
        if len(vals) < 2:
            continue
        hi_arm = max(vals, key=lambda a: vals[a])
        lo_arm = min(vals, key=lambda a: vals[a])
        rows.append({
            "item": it,
            "vals": vals,
            "gap": vals[hi_arm] - vals[lo_arm],
            "best": hi_arm,
            "worst": lo_arm,
        })
    rows.sort(key=lambda r: (-r["gap"], str(r["item"].get("idx"))))
    return rows


def pred_ops_of(rec):
    if not isinstance(rec, dict):
        return None
    ops = rec.get("pred_ops")
    if isinstance(ops, list) and ops:
        return ops
    return op_seq(rec.get("pred_ir"))


def format_ops(ops, indent="        "):
    if not ops:
        return indent + "(empty)"
    return "\n".join(indent + ("%2d. " % (i + 1)) + str(o) for i, o in enumerate(ops))


def format_gap_item(row, arms, rank):
    it = row["item"]
    out = []
    out.append("#%d  gap=%.3f  idx=%s  [%s]  best=%s worst=%s"
               % (rank, row["gap"], it.get("idx"), it.get("category_v2") or "-",
                  row["best"], row["worst"]))
    out.append("    cmd: %s" % (it.get("cmd") or ""))
    clauses = it.get("clauses") or []
    out.append("    clauses (%d):" % len(clauses))
    for i, c in enumerate(clauses, 1):
        out.append("        [%d] %s" % (i, c))
    gt_ops = it.get("gt_ops") or op_seq(it.get("ir_gt"))
    out.append("    GOLD ops (%d):" % len(gt_ops))
    out.append(format_ops(gt_ops))
    for arm in arms:
        rec = (it.get("arms") or {}).get(arm)
        if not isinstance(rec, dict):
            continue
        ops = pred_ops_of(rec)
        fr = as_float(metric_of(rec, "fact_recall"))
        flags = []
        if rec.get("parse_failures"):
            flags.append("parse_fail=%s" % rec["parse_failures"])
        if rec.get("http_errors"):
            flags.append("http_err=%s" % rec["http_errors"])
        if rec.get("reasoning_fallbacks"):
            flags.append("reasoning_fb=%s" % rec["reasoning_fallbacks"])
        if rec.get("errors"):
            flags.append("err=%s" % str(rec["errors"][0])[:70])
        out.append("    %-11s fact_recall=%s  calls=%s  ops(%d)%s"
                   % (arm,
                      ("%.3f" % fr) if is_num(fr) else "n/a",
                      rec.get("num_calls"),
                      len(ops or []),
                      ("  [" + "; ".join(flags) + "]") if flags else ""))
        out.append(format_ops(ops))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="E1 report from results.json")
    ap.add_argument("--results", default=DEFAULT_RESULTS)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--arms", default="", help="comma list; default = whatever is in the file")
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cached", action="store_true",
                    help="use the aggregate stored in results.json instead of recomputing")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    if not os.path.exists(args.results):
        raise SystemExit("no results file: %s" % args.results)
    data = load_results(args.results)
    items = data.get("items") or []
    arms = [a.strip() for a in args.arms.split(",") if a.strip()] or arms_in(items)

    meta = data.get("meta") or {}
    print("=" * 100)
    print("E1 results: %s" % os.path.abspath(args.results))
    print("model=%s  items=%d  arms=%s  started=%s  finished=%s%s"
          % (meta.get("model"), len(items), ",".join(arms), meta.get("started_at"),
             meta.get("finished_at"), "  [INTERRUPTED]" if meta.get("interrupted") else ""))
    if meta.get("total_llm_calls") is not None:
        print("llm calls=%s  reasoning-field fallbacks=%s  http errors=%s"
              % (meta.get("total_llm_calls"), meta.get("total_reasoning_fallbacks"),
                 meta.get("total_http_errors")))
    print("=" * 100)
    print()

    agg = data.get("aggregate") if (args.cached and data.get("aggregate")) else \
        aggregate(items, arms=arms, n_resamples=args.bootstrap, seed=args.seed)
    print(format_table(agg))
    print()
    extra = format_extra_table(agg)
    if extra:
        print(extra)
        print()
    print(format_comparisons(agg))
    print()

    rows = gap_rows(items, arms)
    n = min(args.top, len(rows))
    print("=" * 100)
    print("TOP %d ITEMS BY fact_recall GAP BETWEEN ARMS  (of %d comparable items)" % (n, len(rows)))
    print("=" * 100)
    for i, row in enumerate(rows[:n], 1):
        print()
        print(format_gap_item(row, arms, i))
    if not rows:
        print("(no item is covered by two or more arms)")
    print()
    return 0


# --------------------------------------------------------------------------
def selftest():
    import tempfile

    def rec(fr, ops, calls=1, pf=0):
        return {
            "metrics": {"fact_recall": fr, "omission": 1 - fr, "distortion": 0.1,
                        "op_recall": fr, "op_seq_match": 1.0 if fr > 0.9 else 0.0,
                        "num_copy_recall": fr, "valid": 1.0},
            "pred_ir": {"timeline": ops}, "pred_ops": None,
            "latency_sec": 1.0, "num_calls": calls, "parse_failures": pf,
            "reasoning_fallbacks": 0, "http_errors": 0, "errors": [],
        }

    steps = [{"op": "start_at", "anchor": "now"}, {"op": "call", "target": "Light.On", "args": {}}]
    items = []
    for i in range(4):
        items.append({
            "idx": i, "cmd": "명령%d" % i, "clauses": ["절1", "절2"], "category_v2": "C0%d" % i,
            "ir_gt": {"timeline": steps},
            "gt_ops": ["start_at(now)", "call(Light.On)"],
            "arms": {
                "batch": rec(0.4 + 0.1 * i, steps[:1]),
                "marked": rec(0.6, steps),
                "interleave": rec(0.9, steps, calls=2, pf=(1 if i == 0 else 0)),
            },
        })
    payload = {"meta": {"model": "test", "started_at": "x", "finished_at": "y",
                        "total_llm_calls": 16, "total_reasoning_fallbacks": 0,
                        "total_http_errors": 0},
               "items": items, "aggregate": None}
    d = tempfile.mkdtemp(prefix="e1report")
    p = os.path.join(d, "results.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    rc = main(["--results", p, "--top", "3", "--bootstrap", "200"])
    rows = gap_rows(items, ALL_ARMS)
    ok = (rc == 0 and len(rows) == 4 and rows[0]["item"]["idx"] == 0
          and abs(rows[0]["gap"] - 0.5) < 1e-9 and rows[0]["best"] == "interleave")
    ops = pred_ops_of(items[0]["arms"]["batch"])
    ok = ok and ops == ["start_at(now)"]
    print("SELFTEST %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
