"""R4 preflight for the remediated E3 contract; performs no model calls."""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from explorer.eval.e3 import load_rows, key_of, payload_sha256, row_payload, E3_EXPECTED_CASES, E3_SELECTION_RULE
from explorer.eval.validate_e3_contract import _function_specs, validate_row
from lowering.confirmed_inputs import pipeline_contract
from timeline_ir.catalog import value_domains


ROOT = Path(__file__).resolve().parents[2]
PROBES = (
    ("unittest", "explorer.tests.test_confirmed_service_prefix"),
    ("unittest", "explorer.tests.test_d3_blocking_edge"),
    ("unittest", "explorer.tests.test_exact_arithmetic_actions"),
    ("module", "explorer.tests.test_binding_decision"),
    ("unittest", "explorer.tests.test_symbolic_value_flow.SymbolicValueFlowTests.test_chat_string_identity_forwarding_and_seeded_fault"),
)
OUTCOME_TAXONOMY = (
    "REFERENCE_ERROR", "GENERATION_ERROR", "INVALID_CANDIDATE",
    "EXPLORER_REFUSED", "RESOURCE_FAILURE", "EQUIV-FIXPOINT",
    "DIVERGE_CONFIRMED", "REPLAY_UNCONFIRMED",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    rows = sorted(load_rows(), key=key_of)
    functions, domains = _function_specs(), value_domains()
    cases, payload_hashes = [], {}
    errors = []
    for row in rows:
        key = key_of(row)
        static = validate_row(row, functions, domains)
        try:
            payload = row_payload(row)
            contract = pipeline_contract(payload["ir"], payload["binding"],
                                         payload["connected_devices"])
            digest = payload_sha256(payload)
            payload_hashes[key] = digest
            entry = {
                "id": key,
                "payload_sha256": digest,
                "mapping_mode": "confirmed_binding",
                "mapping_llm_calls": 0,
                "selected_services": len(contract["selected_services"]),
                "static_errors": static["errors"],
                "declared_limitations": static["limitations"],
            }
            if static["errors"]:
                errors.append(f"{key}: static contract error")
        except Exception as exc:
            entry = {"id": key, "preparation_error": f"{type(exc).__name__}: {exc}"}
            errors.append(f"{key}: {entry['preparation_error']}")
        cases.append(entry)

    if len(payload_hashes) != len(rows):
        errors.append("not every row produced a payload hash")
    if len(set(payload_hashes)) != len(payload_hashes):
        errors.append("duplicate full-row payload hashes")

    probes = []
    for mode, module in PROBES:
        command = ([sys.executable, "-m", "unittest", module] if mode == "unittest"
                   else [sys.executable, "-m", module])
        proc = subprocess.run(command,
                              cwd=ROOT, text=True, capture_output=True)
        probes.append({
            "module": module,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-1000:],
            "stderr_tail": proc.stderr[-1000:],
        })
        if proc.returncode:
            errors.append(f"probe failed: {module}")

    report = {
        "schema": "e3-r4-preflight-v1",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_calls": 0,
        "row_count": len(rows),
        "mapping_modes": dict(Counter(c.get("mapping_mode", "error") for c in cases)),
        "mapping_llm_calls": sum(c.get("mapping_llm_calls", 0) for c in cases),
        "payload_hash_count": len(payload_hashes),
        "payload_manifest_sha256": hashlib.sha256(json.dumps(
            payload_hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "outcome_taxonomy": list(OUTCOME_TAXONOMY),
        "probes": probes,
        "errors": errors,
        "selection_rule": E3_SELECTION_RULE,
        "passed": not errors and len(rows) == E3_EXPECTED_CASES,
        "elapsed_seconds": time.perf_counter() - started,
        "inputs": {
            "dataset_sha256": sha(ROOT / "dataset.csv"),
            "known_limitations_sha256": sha(ROOT / "PerCom/6_Evaluation/E3_application/E3_KNOWN_LIMITATIONS.json"),
        },
        "cases": cases,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in (
        "row_count", "mapping_modes", "mapping_llm_calls",
        "payload_hash_count", "passed", "errors", "elapsed_seconds")},
        ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
