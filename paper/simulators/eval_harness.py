"""Evaluation harness: dataset row → pipeline → simulators → compare.

Reads `dataset.csv`, filters by category, calls
`generate_joi_code_ir` (cached to disk), runs both IR and JoI simulators,
compares traces, classifies the result.

Result classification (per locked design):
- `pass`              — traces equivalent
- `trace_mismatch`    — both sims ran, traces differ → real lowering bug
- `parse_fail_ir`     — IR didn't validate (extractor bug, not lowering)
- `parse_fail_joi`    — JoI script failed to parse → lowering syntax bug
- `unknown_op`        — sim hit an op/cond pattern not yet supported
                        (sim limit, NOT a lowering bug — segregated)
- `timeout`           — virtual clock or trace cap hit anomalously
- `pipeline_error`    — generate_joi_code_ir raised before producing IR/JoI

Cache layout:
    paper/simulators/cache/{index}.json   # {ir, joi_block, command_eng,
                                              connected_devices, error?}

CLI:
    python -m paper.simulators.eval_harness                 # all C01-C07
    python -m paper.simulators.eval_harness --cat C01       # one category
    python -m paper.simulators.eval_harness --limit 5       # first 5 per cat
    python -m paper.simulators.eval_harness --no-cache      # force LLM re-run
    python -m paper.simulators.eval_harness -v              # verbose diffs
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import traceback
from collections import Counter, defaultdict
from typing import Optional

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = os.path.join(_BASE_DIR, "cache")
_DATASET_PATH = os.path.abspath(os.path.join(_BASE_DIR, "..", "..",
                                             "dataset.csv"))

# Add paper/ to sys.path so `from run_local_ir import ...` works
_PAPER_DIR = os.path.abspath(os.path.join(_BASE_DIR, ".."))
if _PAPER_DIR not in sys.path:
    sys.path.insert(0, _PAPER_DIR)

from .catalog import load_catalog
from .comparator import compare_traces
from .event_synth import synthesize_scenarios
from .ir_simulator import run_ir_simulation
from .joi_simulator import run_joi_simulation


# ── Result classification ───────────────────────────────────────────────────

CLASSES = (
    "pass", "trace_mismatch",
    "parse_fail_ir", "parse_fail_joi",
    "unknown_op", "timeout",
    "pipeline_error",
)


# ── Cache ───────────────────────────────────────────────────────────────────

def _cache_path(category: str, index: int) -> str:
    return os.path.join(_CACHE_DIR, f"{category}_{index:03d}.json")


def _load_cached(category: str, index: int) -> Optional[dict]:
    path = _cache_path(category, index)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cached(category: str, index: int, payload: dict) -> None:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    path = _cache_path(category, index)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ── Pipeline call ───────────────────────────────────────────────────────────

def _run_pipeline(command_eng: str, connected_devices: dict) -> dict:
    """Call generate_joi_code_ir and extract {ir, joi_block, code_pretty}.

    Returns either {"ir": ..., "joi_block": ..., "code": ...}
    or {"error": "...", "stage": "...", "raw": "..."}.
    """
    try:
        from run_local_ir import generate_joi_code_ir
    except Exception as e:
        return {"error": f"import fail: {e}", "stage": "import"}

    try:
        result = generate_joi_code_ir(command_eng, connected_devices, {})
    except Exception as e:
        return {"error": str(e), "stage": "generate", "trace": traceback.format_exc()}

    ir = result.get("ir")
    code_pretty = result.get("code", "")
    # `code` is a pretty-printed JoI JSON string with embedded newlines in `script`.
    # Parse it back to a dict (need raw JSON, so undo the newline rendering on script).
    joi_block = None
    try:
        # The pretty-printed code has REAL newlines inside the script string,
        # which is invalid JSON. Rebuild by re-escaping.
        joi_block = _parse_pretty_joi(code_pretty)
    except Exception as e:
        return {"error": f"joi parse: {e}", "stage": "joi_parse",
                "ir": ir, "code": code_pretty}

    return {"ir": ir, "joi_block": joi_block, "code": code_pretty}


def _parse_pretty_joi(code: str) -> dict:
    """Parse the pipeline's pretty-printed JoI back into a dict.

    The pipeline replaces `\\n` inside the script field with real newlines for
    readability — that's invalid JSON. We reverse it.
    """
    import re
    # Find "script": "..." (greedy across newlines) and re-escape interior newlines
    def _re_escape(m):
        prefix, body, suffix = m.group(1), m.group(2), m.group(3)
        return prefix + body.replace("\n", "\\n").replace("\r", "") + suffix
    fixed = re.sub(
        r'("script"\s*:\s*")(.*?)(")',
        _re_escape,
        code,
        count=1,
        flags=re.DOTALL,
    )
    return json.loads(fixed)


# ── Per-row evaluation ──────────────────────────────────────────────────────

def evaluate_row(
    category: str,
    index: int,
    command_eng: str,
    connected_devices: dict,
    catalog: dict,
    use_cache: bool = True,
    verbose: bool = False,
) -> dict:
    """Run a single dataset row through the pipeline + sims. Return a result record."""

    # 1. Pipeline (cached)
    cached = _load_cached(category, index) if use_cache else None
    if cached is not None and "error" not in cached:
        ir = cached["ir"]
        joi_block = cached["joi_block"]
    else:
        out = _run_pipeline(command_eng, connected_devices)
        if "error" in out:
            _save_cached(category, index, {
                "command_eng": command_eng, "error": out["error"], "stage": out.get("stage"),
            })
            return {"index": index, "class": "pipeline_error",
                    "detail": f"{out.get('stage')}: {out['error']}"}
        ir = out["ir"]
        joi_block = out["joi_block"]
        _save_cached(category, index, {
            "command_eng": command_eng,
            "connected_devices": connected_devices,
            "ir": ir,
            "joi_block": joi_block,
            "code": out.get("code", ""),
        })

    # 1a. IR validation (extractor reject path)
    if not isinstance(ir, dict) or "timeline" not in ir or "error" in ir:
        return {"index": index, "class": "parse_fail_ir",
                "detail": str(ir)[:200]}

    # 2. Synthesize scenario
    try:
        scenario = synthesize_scenarios(ir)[0]
    except NotImplementedError as e:
        return {"index": index, "class": "unknown_op",
                "detail": f"synth: {e}"}
    except Exception as e:
        return {"index": index, "class": "unknown_op",
                "detail": f"synth: {type(e).__name__}: {e}"}

    # 3. IR simulator
    try:
        trace_ir = run_ir_simulation(ir, scenario, catalog)
    except NotImplementedError as e:
        return {"index": index, "class": "unknown_op",
                "detail": f"ir_sim: {e}"}
    except Exception as e:
        return {"index": index, "class": "unknown_op",
                "detail": f"ir_sim: {type(e).__name__}: {e}"}

    # 4. JoI simulator
    try:
        trace_joi = run_joi_simulation(joi_block, scenario, catalog)
    except Exception as e:
        msg = str(e)
        if "expected" in msg or "unrecognized token" in msg or "unexpected" in msg:
            cls = "parse_fail_joi"
        else:
            cls = "unknown_op"
        return {"index": index, "class": cls,
                "detail": f"joi_sim: {type(e).__name__}: {e}"}

    # 5. Compare. If either sim saturated MAX_TRACE, the last group may be
    # mid-emit-truncated, so retry in prefix-mode (drop last + trim to common
    # prefix). Pass on prefix-mode match counts as equivalent on the observed
    # unbounded-cycle window; mismatch in prefix is still classified `timeout`
    # to flag it for review.
    from .ir_simulator import MAX_TRACE
    saturated = (trace_ir.group_count >= MAX_TRACE
                 or trace_joi.group_count >= MAX_TRACE)
    result = compare_traces(trace_ir, trace_joi, prefix_mode=saturated)
    if result.equivalent:
        cls = "pass"
        return {"index": index, "class": cls,
                "ir_records": len(trace_ir), "joi_records": len(trace_joi),
                "detail": "prefix-mode" if saturated else ""}
    else:
        cls = "timeout" if saturated else "trace_mismatch"
        detail = result.diff_summary
        if not verbose:
            detail = detail.split("\n")[0][:300]
        return {"index": index, "class": cls,
                "detail": detail,
                "ir_records": len(trace_ir), "joi_records": len(trace_joi)}


# ── Dataset reader ──────────────────────────────────────────────────────────

def _read_dataset(path: str = _DATASET_PATH, categories=None, limit=None) -> list[dict]:
    rows = []
    cat_count: dict = defaultdict(int)
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = row.get("category_v2", "")
            if categories and cat not in categories:
                continue
            if limit is not None and cat_count[cat] >= limit:
                continue
            cat_count[cat] += 1
            try:
                connected = json.loads(row.get("connected_devices", "{}") or "{}")
            except json.JSONDecodeError:
                connected = {}
            rows.append({
                "index": int(row["index"]),
                "category": cat,
                "command_eng": row.get("command_eng", ""),
                "connected_devices": connected,
            })
    return rows


# ── Main ────────────────────────────────────────────────────────────────────

def run_eval(
    categories: list[str] | None = None,
    limit: int | None = None,
    use_cache: bool = True,
    verbose: bool = False,
) -> dict:
    catalog = load_catalog()
    rows = _read_dataset(categories=categories, limit=limit)
    print(f"Loaded {len(rows)} rows. cache={'on' if use_cache else 'off'}.")

    by_class_total: Counter = Counter()
    by_class_per_cat: dict[str, Counter] = defaultdict(Counter)
    failures: list[dict] = []
    t_start = time.time()

    for i, row in enumerate(rows):
        t0 = time.time()
        result = evaluate_row(
            row["category"], row["index"], row["command_eng"], row["connected_devices"],
            catalog, use_cache=use_cache, verbose=verbose,
        )
        dt = time.time() - t0
        cls = result["class"]
        by_class_total[cls] += 1
        by_class_per_cat[row["category"]][cls] += 1

        mark = "✓" if cls == "pass" else "✗"
        line = f"  {mark} [{row['category']} #{row['index']:>3}] {cls:18s} ({dt:5.1f}s)  {row['command_eng'][:60]}"
        if cls != "pass":
            line += f"\n      → {result.get('detail', '')[:200]}"
            failures.append({**row, **result})
        print(line)

    total_time = time.time() - t_start

    # Summary
    print()
    print(f"=== Summary ({len(rows)} rows, {total_time:.1f}s) ===")
    print()
    print("By class:")
    for cls in CLASSES:
        n = by_class_total.get(cls, 0)
        if n:
            pct = 100 * n / len(rows)
            print(f"  {cls:18s} {n:4d}  ({pct:5.1f}%)")
    print()
    print("By category:")
    cats = sorted(by_class_per_cat.keys())
    print(f"  {'cat':5s} | " + " ".join(f"{c[:10]:>10}" for c in CLASSES))
    for cat in cats:
        cnt = by_class_per_cat[cat]
        total = sum(cnt.values())
        line = f"  {cat:5s} | " + " ".join(f"{cnt.get(c, 0):>10}" for c in CLASSES) + f"  (n={total})"
        print(line)

    return {
        "total": len(rows),
        "by_class": dict(by_class_total),
        "by_category": {k: dict(v) for k, v in by_class_per_cat.items()},
        "failures": failures,
        "elapsed_sec": total_time,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IR/JoI simulator evaluation harness.")
    parser.add_argument("--cat", action="append", help="Limit to category (repeatable). Default: C01-C07.")
    parser.add_argument("--limit", type=int, default=None, help="Max rows per category.")
    parser.add_argument("--no-cache", action="store_true", help="Force LLM re-run (overwrites cache).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose failure detail.")
    args = parser.parse_args(argv)

    categories = args.cat if args.cat else ["C01", "C02", "C03", "C04", "C05", "C06", "C07"]
    run_eval(categories=categories, limit=args.limit,
             use_cache=not args.no_cache, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
