"""Development sweep: exact ticks versus bounded Behavioral Explorer.

This is deliberately outcome-visible development work, not the held-out A/B
experiment.  It searches the existing generated-code corpus for discrepancies
between the two search algorithms so that any Explorer bug can be repaired
before the supported fragment and confirmatory manifest are frozen.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import statistics
import time
from collections import Counter

from .ab_eval import percentile, wilson_interval
from .domain_manifest import (SCHEMA_VERSION as DOMAIN_SCHEMA_VERSION,
                              boundary_domains, canonical_sha256,
                              dataset_payload, sha256_bytes)
from .exact_tick import exact_tick_product
from .gate import prepare_pair
from .interp import Unsupported
from .product import merge_axes, product_runners


def _rows() -> dict[str, dict]:
    out = {}
    with open("dataset.csv", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            key = f'{row["category_v2"]}_{int(float(row["index"])):03d}'
            out[key] = row
    return out


def stress_domains(axes) -> dict[str, list]:
    """Finite boundary-neighborhood model independent of chosen reps.

    For numeric predicates, enumerate the exact constant, two values on each
    side, and midpoints between constants.  For equality-like categorical
    partitions, retain all mentioned values and three distinct representatives
    of the catch-all region.  This makes the exact oracle execute multiple raw
    values that Behavioral Explorer intentionally collapses into one cell.
    """
    return boundary_domains(axes)


def _one(key: str, row: dict, candidate: dict, args,
         manifest_case: dict | None = None) -> dict:
    started = time.perf_counter()
    out = {"case_id": key, "status": "INVALID"}
    try:
        if manifest_case is not None:
            payload_digest = canonical_sha256(dataset_payload(row))
            if payload_digest != manifest_case.get("dataset_payload_sha256"):
                out.update(status="MANIFEST_MISMATCH",
                           reason="dataset payload SHA-256 differs")
                return out
            source_path = os.path.join(args.candidates, key + ".json")
            source_digest = sha256_bytes(open(source_path, "rb").read())
            if source_digest != manifest_case.get("candidate_sha256"):
                out.update(status="MANIFEST_MISMATCH",
                           reason="candidate SHA-256 differs")
                return out
            frozen_status = manifest_case.get("manifest_status")
            if frozen_status != "READY":
                out.update(status=frozen_status or "INVALID",
                           reason=manifest_case.get(
                               "reason", "not ready in domain manifest"))
                return out
        if candidate.get("status") != "ok" \
                or not isinstance(candidate.get("joi_block"), dict):
            out.update(status="GENERATION_ERROR",
                       reason=candidate.get("error_code", "no_joi_block"))
            return out
        pair = prepare_pair(
            json.loads(row["ir_gt"]),
            json.loads(row.get("binding_gt") or "{}"),
            json.loads(row["connected_devices"]),
            candidate["joi_block"],
        )
        axes = merge_axes(pair.ir_runner.axes, pair.code_runner.axes)
        if manifest_case is not None:
            exact_domains = manifest_case["input_domains"]
            gv_domains = manifest_case.get("initial_gv_domains") or {}
            if set(exact_domains) != set(axes.cells):
                out.update(
                    status="MANIFEST_MISMATCH",
                    reason=(f"input keys differ: manifest="
                            f"{sorted(exact_domains)}, source="
                            f"{sorted(axes.cells)}"),
                )
                return out
            if int(manifest_case.get("period_ms", -1)) != pair.period_ms:
                out.update(status="MANIFEST_MISMATCH",
                           reason="prepared period differs from manifest")
                return out
        else:
            gv_domains = {name: [None, False, True]
                          for name in axes.mirror_gv}
            exact_domains = (stress_domains(axes) if args.stress_domain
                             else axes.cells)
        exact = exact_tick_product(
            pair.ir_runner,
            pair.code_runner,
            period_ms=pair.period_ms,
            input_domains=exact_domains,
            initial_gv_domains=gv_domains,
            horizon_ticks=args.horizon,
            max_states=args.max_states,
            max_transitions=args.max_transitions,
            max_input_combinations=args.max_input_combinations,
        )
        out["exact"] = {
            "verdict": exact.verdict,
            "states": exact.n_states,
            "transitions": exact.n_transitions,
            "max_frontier": exact.max_frontier,
            "completed_ticks": exact.completed_ticks,
            "seconds": exact.seconds,
            "notes": exact.notes,
            "input_domain_sizes": {k: len(v)
                                   for k, v in exact_domains.items()},
        }
        if exact.verdict == "INCOMPLETE":
            out["status"] = "EXACT_INCOMPLETE"
            return out

        explorer = product_runners(
            pair.ir_runner, pair.code_runner, pair.period_ms,
            max_diverge=1, max_ticks=args.horizon,
        )
        out["explorer"] = {
            "verdict": explorer.verdict,
            "states": explorer.n_states,
            "pair_transition_evaluations": explorer.n_steps // 2,
            "seconds": explorer.seconds,
            "notes": explorer.notes + pair.notes,
        }
        exact_label = ("EQUIV" if exact.verdict == "EQUIV_BOUNDED"
                       else "DIVERGE")
        out["oracle_label"] = exact_label
        out["explorer_label"] = explorer.verdict
        if explorer.verdict == "UNKNOWN":
            out["status"] = "EXPLORER_INCOMPLETE"
        elif exact_label == explorer.verdict:
            out["status"] = "AGREE"
        elif exact_label == "DIVERGE" and explorer.verdict == "EQUIV":
            out["status"] = "DISAGREE_FALSE_ACCEPT_CANDIDATE"
            out["error_class"] = "FALSE_ACCEPT"
        else:
            out["status"] = "DISAGREE_FALSE_REJECT_CANDIDATE"
            out["error_class"] = "FALSE_REJECT"
        return out
    except Unsupported as exc:
        out.update(status="UNSUPPORTED", reason=str(exc))
        return out
    except ValueError as exc:
        out.update(status="PREPARATION_ERROR",
                   reason=f"ValueError: {exc}")
        return out
    except Exception as exc:
        out.update(status="INVALID", reason=f"{type(exc).__name__}: {exc}")
        return out
    finally:
        out["wall_seconds"] = time.perf_counter() - started


def run(args) -> dict:
    rows = _rows()
    all_files = sorted(glob.glob(os.path.join(args.candidates, "*.json")))
    manifest = None
    manifest_digest = None
    manifest_cases = None
    if args.domain_manifest:
        raw = open(args.domain_manifest, "rb").read()
        manifest_digest = hashlib.sha256(raw).hexdigest()
        manifest = json.loads(raw)
        if manifest.get("schema_version") != DOMAIN_SCHEMA_VERSION:
            raise ValueError("unsupported domain manifest schema_version")
        if args.require_frozen and not manifest.get("selection_frozen"):
            raise ValueError("domain manifest is not frozen")
        if args.stress_domain:
            raise ValueError("--stress-domain cannot recompute a frozen manifest")
        manifest_cases = {case["id"]: case for case in manifest["cases"]
                          if case.get("selected", True)}
        expected = set(manifest_cases)
        present = {os.path.basename(path)[:-5] for path in all_files}
        missing, extra = sorted(expected - present), sorted(present - expected)
        if manifest.get("selection_frozen") and (missing or extra):
            raise ValueError(
                f"frozen candidate set drift: missing={missing}, extra={extra}")
        files = [os.path.join(args.candidates, key + ".json")
                 for key in sorted(expected) if key in present]
        manifest_horizon = int(manifest["horizon_ticks"])
        if args.horizon is not None and args.horizon != manifest_horizon:
            raise ValueError(
                f"horizon differs: cli={args.horizon}, "
                f"manifest={manifest_horizon}")
        args.horizon = manifest_horizon
    else:
        files = all_files
        args.horizon = 4 if args.horizon is None else args.horizon
    if args.limit:
        files = files[:args.limit]
    outcomes = []
    for index, path in enumerate(files, 1):
        key = os.path.basename(path)[:-5]
        if key not in rows:
            outcomes.append({"case_id": key, "status": "INVALID",
                             "reason": "dataset row missing"})
            continue
        with open(path, encoding="utf-8") as source:
            candidate = json.load(source)
        result = _one(key, rows[key], candidate, args,
                      manifest_cases.get(key) if manifest_cases else None)
        outcomes.append(result)
        if args.progress and (index % args.progress == 0 or index == len(files)):
            counts = Counter(item["status"] for item in outcomes)
            print(f"[{index}/{len(files)}] {dict(counts)}", flush=True)

    counts = Counter(item["status"] for item in outcomes)
    compared = [item for item in outcomes if item["status"].startswith(
        ("AGREE", "DISAGREE"))]
    equivalent = [item for item in compared
                  if item.get("oracle_label") == "EQUIV"]
    divergent = [item for item in compared
                 if item.get("oracle_label") == "DIVERGE"]
    false_accepts = sum(item.get("error_class") == "FALSE_ACCEPT"
                        for item in compared)
    false_rejects = sum(item.get("error_class") == "FALSE_REJECT"
                        for item in compared)
    full_space = [item for item in compared
                  if item["exact"]["verdict"] == "EQUIV_BOUNDED"
                  and item["explorer"]["verdict"] == "EQUIV"]
    exact_transitions = sum(item["exact"]["transitions"]
                            for item in full_space)
    explorer_transitions = sum(
        item["explorer"]["pair_transition_evaluations"]
        for item in full_space)
    latencies = [item["explorer"]["seconds"] for item in compared]
    ready_cases = (sum(case.get("manifest_status") == "READY"
                       for case in manifest_cases.values())
                   if manifest_cases else len(compared))
    summary = {
        "evidence_class": ("confirmatory-candidate"
                           if manifest and manifest.get("selection_frozen")
                           and args.require_frozen else "development-only"),
        "candidate_directory": os.path.abspath(args.candidates),
        "horizon_ticks": args.horizon,
        "stress_domain": args.stress_domain,
        "domain_manifest": (os.path.abspath(args.domain_manifest)
                            if args.domain_manifest else None),
        "domain_manifest_sha256": manifest_digest,
        "selection_frozen": (manifest.get("selection_frozen")
                             if manifest else False),
        "selected": len(files),
        "evaluable_pairs": ready_cases,
        "verifier_completed_pairs": len(compared),
        "verifier_completion_rate": (
            len(compared) / ready_cases if ready_cases else None),
        "end_to_end_evaluable_rate": (
            len(compared) / len(files) if files else 0.0),
        "outcomes": dict(sorted(counts.items())),
        "compared": len(compared),
        "oracle_denominators": {
            "equivalent": len(equivalent),
            "divergent": len(divergent),
        },
        "false_accepts_A": false_accepts,
        "false_rejects_B": false_rejects,
        "false_accept_wilson_95": wilson_interval(
            false_accepts, len(divergent)),
        "false_reject_wilson_95": wilson_interval(
            false_rejects, len(equivalent)),
        "full_space_equivalent_cases_for_reduction": len(full_space),
        "exact_tick_transitions": exact_transitions,
        "explorer_pair_transition_evaluations": explorer_transitions,
        "transition_reduction_percent": (
            100.0 * (exact_transitions - explorer_transitions)
            / exact_transitions if exact_transitions else None),
        "explorer_latency_seconds": {
            "median": statistics.median(latencies) if latencies else None,
            "p95": percentile(latencies, 0.95),
            "max": max(latencies) if latencies else None,
        },
    }
    os.makedirs(args.output_dir, exist_ok=True)
    with open(os.path.join(args.output_dir, "case_outcomes.jsonl"), "w",
              encoding="utf-8") as target:
        for item in outcomes:
            target.write(json.dumps(item, ensure_ascii=False, sort_keys=True)
                         + "\n")
    with open(os.path.join(args.output_dir, "summary.json"), "w",
              encoding="utf-8") as target:
        json.dump(summary, target, ensure_ascii=False, indent=2,
                  sort_keys=True)
        target.write("\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--horizon", type=int, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--max-transitions", type=int, default=500_000)
    parser.add_argument("--max-input-combinations", type=int, default=20_000)
    parser.add_argument("--progress", type=int, default=25)
    parser.add_argument("--stress-domain", action="store_true")
    parser.add_argument("--domain-manifest", default=None)
    parser.add_argument("--require-frozen", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
