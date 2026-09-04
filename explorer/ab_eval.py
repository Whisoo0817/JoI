"""Manifest-driven false-accept/false-reject evaluation.

The exact tick oracle and optimized Behavioral Explorer answer the same
bounded IR/code question.  Every selected case is retained in the output;
unsupported, incomplete, invalid, and gold-mismatch outcomes never disappear
from the denominator accounting.

Run a development manifest::

    python -m explorer.ab_eval \
      --manifest explorer/eval/ab_development_manifest.json \
      --output-dir skill_result/05_experiment_plan/results/E3/development
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from collections import Counter
from dataclasses import asdict

from .exact_tick import exact_tick_product
from .gate import prepare_pair
from .interp import Unsupported
from .product import merge_axes, product_runners, replay_divergence


SCHEMA_VERSION = 1
Z_95 = 1.959963984540054


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[index]


def _manifest_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def wilson_interval(events: int, total: int,
                    z: float = Z_95) -> dict | None:
    """Two-sided Wilson interval for a binomial event rate.

    In particular, this keeps a zero observed error count from being reported
    as evidence of a zero population error probability.
    """
    if total <= 0:
        return None
    if not 0 <= events <= total:
        raise ValueError("events must be between zero and total")
    rate = events / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (rate + z2 / (2.0 * total)) / denominator
    radius = (z / denominator) * math.sqrt(
        rate * (1.0 - rate) / total + z2 / (4.0 * total * total))
    return {
        "events": events,
        "denominator": total,
        "rate": rate,
        "lower_95": (0.0 if events == 0
                     else max(0.0, center - radius)),
        "upper_95": (1.0 if events == total
                     else min(1.0, center + radius)),
    }


def _validate_case(case: dict) -> None:
    required = {
        "id", "split", "gold_label", "gold_provenance", "ir", "binding",
        "devices", "joi_block", "input_domains", "horizon_ticks",
    }
    missing = sorted(required - set(case))
    if missing:
        raise ValueError(f"{case.get('id', '<unknown>')}: missing {missing}")
    if case["gold_label"] not in {"EQUIV", "DIVERGE"}:
        raise ValueError(f"{case['id']}: invalid gold_label")
    if not case["gold_provenance"].strip():
        raise ValueError(f"{case['id']}: empty gold_provenance")
    if int(case["horizon_ticks"]) <= 0:
        raise ValueError(f"{case['id']}: horizon_ticks must be positive")


def evaluate_case(case: dict) -> dict:
    started = time.perf_counter()
    row = {
        "case_id": case.get("id", "<unknown>"),
        "split": case.get("split"),
        "gold_label": case.get("gold_label"),
        "status": "INVALID",
        "error_class": None,
    }
    try:
        _validate_case(case)
        pair = prepare_pair(case["ir"], case["binding"], case["devices"],
                            case["joi_block"])
        inferred = merge_axes(pair.ir_runner.axes, pair.code_runner.axes).cells
        explicit = case["input_domains"]
        if set(inferred) != set(explicit):
            raise ValueError(
                f"input keys differ: inferred={sorted(inferred)}, "
                f"manifest={sorted(explicit)}")

        caps = case.get("caps") or {}
        exact = exact_tick_product(
            pair.ir_runner,
            pair.code_runner,
            period_ms=pair.period_ms,
            input_domains=explicit,
            horizon_ticks=int(case["horizon_ticks"]),
            initial_gv_domains=case.get("initial_gv_domains"),
            max_states=int(caps.get("exact_max_states", 1_000_000)),
            max_transitions=int(caps.get("exact_max_transitions", 5_000_000)),
            max_input_combinations=int(
                caps.get("exact_max_input_combinations", 100_000)),
        )
        row["exact"] = asdict(exact)
        if exact.verdict == "INCOMPLETE":
            row["status"] = "EXACT_INCOMPLETE"
            return row

        oracle_label = ("EQUIV" if exact.verdict == "EQUIV_BOUNDED"
                        else "DIVERGE")
        row["oracle_label"] = oracle_label
        if oracle_label != case["gold_label"]:
            row["status"] = "GOLD_MISMATCH"
            return row

        explorer = product_runners(
            pair.ir_runner,
            pair.code_runner,
            pair.period_ms,
            max_diverge=1,
            max_ticks=int(case["horizon_ticks"]),
        )
        explorer_label = explorer.verdict
        replay_confirmed = None
        if explorer.verdict == "DIVERGE":
            replays = [replay_divergence(pair.ir_runner, pair.code_runner, d)
                       for d in explorer.divergences]
            replay_confirmed = any(r.confirmed for r in replays)
            if not replay_confirmed:
                explorer_label = "UNKNOWN"
        row["explorer"] = {
            "verdict": explorer.verdict,
            "effective_label": explorer_label,
            "closed": explorer.closed,
            "bounded_horizon_ticks": explorer.bounded_horizon_ticks,
            "states": explorer.n_states,
            # product.n_steps counts individual runner calls; two calls form
            # one pair-transition evaluation.
            "pair_transition_evaluations": explorer.n_steps // 2,
            "seconds": explorer.seconds,
            "replay_confirmed": replay_confirmed,
            "notes": list(explorer.notes) + list(pair.notes),
        }
        if explorer_label == "UNKNOWN":
            row["status"] = "EXPLORER_INCOMPLETE"
            return row

        if case["gold_label"] == "DIVERGE" and explorer_label == "EQUIV":
            row["status"] = "COMPLETED"
            row["error_class"] = "FALSE_ACCEPT"
        elif case["gold_label"] == "EQUIV" and explorer_label == "DIVERGE":
            row["status"] = "COMPLETED"
            row["error_class"] = "FALSE_REJECT"
        else:
            row["status"] = "COMPLETED"

        exact_transitions = exact.n_transitions
        explorer_transitions = explorer.n_steps // 2
        row["transition_reduction_percent"] = (
            100.0 * (exact_transitions - explorer_transitions)
            / exact_transitions if exact_transitions else None
        )
        return row
    except Unsupported as exc:
        row["status"] = "UNSUPPORTED"
        row["reason"] = str(exc)
        return row
    except Exception as exc:
        row["status"] = "INVALID"
        row["reason"] = f"{type(exc).__name__}: {exc}"
        return row
    finally:
        row["wall_seconds"] = time.perf_counter() - started


def summarize(rows: list[dict], manifest_sha256: str) -> dict:
    outcomes = Counter(r["status"] for r in rows)
    errors = Counter(r.get("error_class") for r in rows
                     if r.get("error_class"))
    completed = [r for r in rows if r["status"] == "COMPLETED"]
    eq = [r for r in completed if r["gold_label"] == "EQUIV"]
    div = [r for r in completed if r["gold_label"] == "DIVERGE"]
    # Search-size reduction is meaningful only when both methods complete the
    # whole bounded space.  Divergent cases stop at traversal-order-dependent
    # first counterexamples and are therefore excluded from R.
    full_space = [r for r in eq if r.get("error_class") is None]
    exact_transitions = sum(r["exact"]["n_transitions"] for r in full_space)
    explorer_transitions = sum(
        r["explorer"]["pair_transition_evaluations"] for r in full_space)
    latencies = [r["explorer"]["seconds"] for r in completed]
    false_accepts = errors["FALSE_ACCEPT"]
    false_rejects = errors["FALSE_REJECT"]
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_sha256": manifest_sha256,
        "selected_cases": len(rows),
        "completed_cases": len(completed),
        "completion_rate": len(completed) / len(rows) if rows else 0.0,
        "outcomes": dict(sorted(outcomes.items())),
        "gold_denominators": {
            "equivalent": len(eq),
            "divergent": len(div),
        },
        "false_accepts_A": false_accepts,
        "false_rejects_B": false_rejects,
        "false_accept_rate": (false_accepts / len(div) if div else None),
        "false_reject_rate": (false_rejects / len(eq) if eq else None),
        "false_accept_wilson_95": wilson_interval(false_accepts, len(div)),
        "false_reject_wilson_95": wilson_interval(false_rejects, len(eq)),
        "transitions": {
            "full_space_equivalent_cases": len(full_space),
            "exact_tick": exact_transitions,
            "behavioral_explorer": explorer_transitions,
            "reduction_percent": (
                100.0 * (exact_transitions - explorer_transitions)
                / exact_transitions if exact_transitions else None
            ),
        },
        "explorer_latency_seconds": {
            "median": statistics.median(latencies) if latencies else None,
            "p95": percentile(latencies, 0.95),
            "max": max(latencies) if latencies else None,
        },
    }


def run(manifest_path: str, output_dir: str, split: str | None = None) -> dict:
    raw = open(manifest_path, "rb").read()
    manifest = json.loads(raw)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported manifest schema_version")
    cases = manifest.get("cases") or []
    if split:
        cases = [case for case in cases if case.get("split") == split]
    if not cases:
        raise ValueError("manifest selects no cases")

    rows = [evaluate_case(case) for case in cases]
    summary = summarize(rows, _manifest_digest(raw))
    summary["manifest_path"] = os.path.abspath(manifest_path)
    summary["split"] = split

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "case_outcomes.jsonl"), "w",
              encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, sort_keys=True)
                      + "\n")
    with open(os.path.join(output_dir, "summary.json"), "w",
              encoding="utf-8") as out:
        json.dump(summary, out, ensure_ascii=False, indent=2, sort_keys=True)
        out.write("\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--split", default=None)
    args = parser.parse_args()
    summary = run(args.manifest, args.output_dir, args.split)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
