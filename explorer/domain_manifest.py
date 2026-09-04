"""Freeze finite input domains before a differential evaluation run.

The builder may inspect the IR and candidate source, but it never executes a
pair or reads an Explorer verdict. Its output binds each selected case to the
exact dataset payload and candidate file via SHA-256. A later run can reject
source drift instead of silently recomputing favorable domains.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
from decimal import Decimal, InvalidOperation

from .gate import prepare_pair
from .interp import Unsupported
from .product import check_supported_pair, merge_axes


SCHEMA_VERSION = 1


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return sha256_bytes(raw)


def dataset_payload(row: dict) -> dict:
    """Return only fields that determine pair preparation and execution."""
    return {
        "ir": json.loads(row["ir_gt"]),
        "binding": json.loads(row.get("binding_gt") or "{}"),
        "devices": json.loads(row["connected_devices"]),
    }


def _rows(dataset: str) -> dict[str, dict]:
    out = {}
    with open(dataset, encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            key = f'{row["category_v2"]}_{int(float(row["index"])):03d}'
            out[key] = row
    return out


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def boundary_domains(axes) -> dict[str, list]:
    """Create explicit boundary-neighborhood values, not chosen reps.

    Numeric inputs include two values on either side of every source constant
    plus inter-constant midpoints. Categorical catch-all cells are represented
    by three distinct raw values. Values are serialized into the manifest and
    are not recomputed during the measured run.
    """
    out = {}
    for key, reps in axes.cells.items():
        predicates = axes.cell_preds.get(key, [])
        constants = []
        numeric = bool(predicates)
        for _, raw in predicates:
            number = _number(raw)
            if number is None:
                numeric = False
                break
            constants.append(number)
        if numeric and constants:
            values = set()
            constants = sorted(set(constants))
            for constant in constants:
                values.update({constant - 1, constant - Decimal("0.1"),
                               constant, constant + Decimal("0.1"),
                               constant + 1})
            for left, right in zip(constants, constants[1:]):
                values.add((left + right) / 2)
            out[key] = [
                int(value) if value == value.to_integral() else float(value)
                for value in sorted(values)
            ]
            continue

        values = list(reps)
        if "__other__" in values:
            values = [v for v in values if v != "__other__"]
            values.extend(["__other_a__", "__other_b__", "__other_c__"])
        out[key] = values
    return out


def build_manifest(*, dataset: str, candidates: str, horizon_ticks: int,
                   selection_frozen: bool = False) -> dict:
    rows = _rows(dataset)
    files = sorted(glob.glob(os.path.join(candidates, "*.json")))
    cases = []
    for path in files:
        key = os.path.basename(path)[:-5]
        case = {
            "id": key,
            "selected": True,
            "horizon_ticks": horizon_ticks,
            "candidate_path": os.path.abspath(path),
            "candidate_sha256": sha256_bytes(open(path, "rb").read()),
        }
        row = rows.get(key)
        if row is None:
            case.update(manifest_status="INVALID",
                        reason="dataset row missing")
            cases.append(case)
            continue
        payload = dataset_payload(row)
        case["dataset_payload_sha256"] = canonical_sha256(payload)
        try:
            candidate = json.load(open(path, encoding="utf-8"))
            if candidate.get("status") != "ok" or not isinstance(
                    candidate.get("joi_block"), dict):
                case.update(manifest_status="GENERATION_ERROR",
                            reason=candidate.get("error_code", "no_joi_block"))
                cases.append(case)
                continue
            pair = prepare_pair(payload["ir"], payload["binding"],
                                payload["devices"], candidate["joi_block"])
            axes = merge_axes(pair.ir_runner.axes, pair.code_runner.axes)
            check_supported_pair(pair.ir_runner, pair.code_runner, axes)
            case.update(
                manifest_status="READY",
                input_domains=boundary_domains(axes),
                initial_gv_domains={
                    name: [None, False, True]
                    for name in sorted(axes.mirror_gv)
                },
                period_ms=pair.period_ms,
                preparation_notes=list(pair.notes),
            )
        except Unsupported as exc:
            case.update(manifest_status="UNSUPPORTED", reason=str(exc))
        except Exception as exc:
            case.update(manifest_status="PREPARATION_ERROR",
                        reason=f"{type(exc).__name__}: {exc}")
        cases.append(case)

    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": "Outcome-blind finite input model for differential evaluation",
        "selection_frozen": bool(selection_frozen),
        "selection_rule": "Every JSON candidate present in the declared directory",
        "domain_rule": "Boundary constants and neighborhoods from IR/code source; no execution or verdict access",
        "dataset_path": os.path.abspath(dataset),
        "candidate_directory": os.path.abspath(candidates),
        "horizon_ticks": horizon_ticks,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset.csv")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--horizon", type=int, default=8)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest(
        dataset=args.dataset,
        candidates=args.candidates,
        horizon_ticks=args.horizon,
        selection_frozen=args.freeze,
    )
    with open(args.output, "w", encoding="utf-8") as target:
        json.dump(manifest, target, ensure_ascii=False, indent=2,
                  sort_keys=True)
        target.write("\n")
    counts = {}
    for case in manifest["cases"]:
        status = case["manifest_status"]
        counts[status] = counts.get(status, 0) + 1
    print(json.dumps({"output": os.path.abspath(args.output),
                      "selection_frozen": args.freeze,
                      "selected": len(manifest["cases"]),
                      "statuses": counts},
                     ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
