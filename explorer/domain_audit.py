"""Independent static read audit for a serialized input-domain manifest.

This checker deliberately does not read ``runner.axes`` or call
``derive_axes``. It walks grounded JoI AST dataflow and compiled IR
instructions, then verifies that every behavior-relevant external read has a
domain in the frozen manifest. It shares parsing/grounding with the adapter,
so it is an independent axis audit, not a fully independent frontend.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from dataclasses import fields, is_dataclass

from . import expr as ex
from . import joi_parser as jp
from .domain_manifest import canonical_sha256, dataset_payload, sha256_bytes
from .expr import canonical_key
from .gate import prepare_pair
from .interp import world_key
from .predicates import walk_stmts


def _rows(dataset: str) -> dict[str, dict]:
    out = {}
    with open(dataset, encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            key = f'{row["category_v2"]}_{int(float(row["index"])):03d}'
            out[key] = row
    return out


def _unwrap_stmts(runner):
    seen = set()
    while runner is not None and id(runner) not in seen:
        seen.add(id(runner))
        if hasattr(runner, "stmts"):
            return runner.stmts
        runner = getattr(runner, "inner", None)
    return None


def _literal_query_key(node: jp.CallExpr) -> str | None:
    service, method = canonical_key(node.service, node.method)
    if service == "globalvariable":
        if method.startswith("get") and node.args \
                and isinstance(node.args[0], ex.Lit):
            return "@gv:" + str(node.args[0].value)
        return None
    if service == "clock":
        return None
    base = world_key(node.tags, node.service, node.method)
    if node.args is None:
        return base
    if all(isinstance(arg, ex.Lit) for arg in node.args):
        return f"{base}({','.join(repr(arg.value) for arg in node.args)})"
    return None


def code_behavior_reads(runner) -> tuple[set[str], list[str]]:
    """Trace reads through variable definitions from guards/action arguments."""
    stmts = _unwrap_stmts(runner)
    if stmts is None:
        return set(), ["runner exposes no statements"]
    definitions = {}
    for statement in walk_stmts(stmts):
        if isinstance(statement, jp.Assign):
            definitions.setdefault(statement.name, []).append(statement.rhs)

    reads: set[str] = set()
    unresolved: list[str] = []
    visiting: set[str] = set()

    def visit(node) -> None:
        if node is None:
            return
        if isinstance(node, ex.VarRef):
            if node.name in visiting:
                return
            visiting.add(node.name)
            for definition in definitions.get(node.name, []):
                visit(definition)
            visiting.remove(node.name)
            return
        if isinstance(node, jp.CallExpr):
            key = _literal_query_key(node)
            if key is not None:
                reads.add(key)
            elif node.args is not None:
                service, method = canonical_key(node.service, node.method)
                if service not in ("globalvariable", "clock"):
                    unresolved.append(f"{service}.{method}(dynamic)")
            for arg in node.args or []:
                visit(arg)
            return
        if isinstance(node, ex.QuantRef):
            if node.key.startswith("clock."):
                return
            service = node.tags[-1] if node.tags else ""
            reads.add(world_key(node.tags, service, node.member))
            return
        if isinstance(node, ex.DeviceRef):
            if not node.key.startswith("clock."):
                reads.add(node.key)
            return
        if isinstance(node, ex.ClockRef):
            return
        if is_dataclass(node):
            for field in fields(node):
                visit(getattr(node, field.name))
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                visit(item)

    for statement in walk_stmts(stmts):
        if isinstance(statement, (jp.IfStmt, jp.WaitUntil, jp.Loop)):
            visit(statement.cond)
        elif isinstance(statement, jp.ForEach):
            visit(statement.source)
        elif isinstance(statement, jp.CallStmt):
            for argument in statement.call.args or []:
                visit(argument)
        # Assignment calls whose values matter are reached from VarRef dataflow.
    return reads, sorted(set(unresolved))


def ir_behavior_reads(runner) -> tuple[set[str], list[str]]:
    """Collect reads from compiled instructions without consulting IR axes."""
    program = getattr(runner, "prog", None)
    if program is None:
        return set(), ["runner exposes no compiled IR program"]
    reads: set[str] = set()
    unresolved: list[str] = []

    def visit(node) -> None:
        if not isinstance(node, (tuple, list)) or not node:
            return
        if node[0] == "read" and len(node) > 1:
            if not str(node[1]).startswith("clock."):
                reads.add(str(node[1]))
            return
        for item in node[1:]:
            visit(item)

    for instruction in program.ins:
        if instruction.kind == "READ":
            if not instruction.key.startswith("clock."):
                reads.add(instruction.key)
        if instruction.cond is not None:
            visit(instruction.cond)
        for argument in instruction.args:
            visit(argument)
        if instruction.kind == "CALL" and instruction.var:
            literal_args = []
            for argument in instruction.args:
                if argument and argument[0] == "lit":
                    literal_args.append(argument[1])
                else:
                    unresolved.append(f"{instruction.key}(dynamic)")
                    break
            else:
                # The concrete IR runner accepts the parameterized key first
                # and the base key as a fallback.  An empty argument list is
                # a property-style read, so the base key is the modeled input.
                reads.add(
                    f"{instruction.key}({','.join(map(repr, literal_args))})"
                    if literal_args else instruction.key
                )
    return reads, sorted(set(unresolved))


def audit(*, manifest_path: str, dataset: str, candidates: str,
          output_dir: str) -> dict:
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    rows = _rows(dataset)
    outcomes = []
    for case in manifest["cases"]:
        row = {"case_id": case["id"],
               "manifest_status": case.get("manifest_status")}
        if case.get("manifest_status") != "READY":
            row["status"] = "NOT_READY"
            outcomes.append(row)
            continue
        source_row = rows.get(case["id"])
        source_path = os.path.join(candidates, case["id"] + ".json")
        try:
            if source_row is None:
                raise ValueError("dataset row missing")
            payload = dataset_payload(source_row)
            if canonical_sha256(payload) != case["dataset_payload_sha256"]:
                raise ValueError("dataset payload SHA-256 differs")
            if sha256_bytes(open(source_path, "rb").read()) != \
                    case["candidate_sha256"]:
                raise ValueError("candidate SHA-256 differs")
            candidate = json.load(open(source_path, encoding="utf-8"))
            pair = prepare_pair(payload["ir"], payload["binding"],
                                payload["devices"], candidate["joi_block"])
            ir_reads, ir_unresolved = ir_behavior_reads(pair.ir_runner)
            code_reads, code_unresolved = code_behavior_reads(pair.code_runner)
            expected = ir_reads | code_reads
            declared = set(case.get("input_domains") or {})
            missing = sorted(expected - declared)
            row.update(
                status=("PASS" if not missing and not ir_unresolved
                        and not code_unresolved else "REVIEW"),
                declared_keys=sorted(declared),
                ir_behavior_reads=sorted(ir_reads),
                code_behavior_reads=sorted(code_reads),
                missing_keys=missing,
                unresolved=sorted(set(ir_unresolved + code_unresolved)),
            )
        except Exception as exc:
            row.update(status="AUDIT_ERROR",
                       reason=f"{type(exc).__name__}: {exc}")
        outcomes.append(row)

    counts = Counter(row["status"] for row in outcomes)
    ready = [row for row in outcomes if row["manifest_status"] == "READY"]
    summary = {
        "evidence_class": "static-independent-axis-audit",
        "manifest_path": os.path.abspath(manifest_path),
        "selected_cases": len(outcomes),
        "ready_cases": len(ready),
        "outcomes": dict(sorted(counts.items())),
        "ready_pass_rate": (sum(row["status"] == "PASS" for row in ready)
                            / len(ready) if ready else None),
        "method_boundary": "Does not use runner.axes/derive_axes; shares parsing, grounding, and compilation.",
    }
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "case_outcomes.jsonl"), "w",
              encoding="utf-8") as target:
        for row in outcomes:
            target.write(json.dumps(row, ensure_ascii=False,
                                    sort_keys=True) + "\n")
    with open(os.path.join(output_dir, "summary.json"), "w",
              encoding="utf-8") as target:
        json.dump(summary, target, ensure_ascii=False, indent=2,
                  sort_keys=True)
        target.write("\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--dataset", default="dataset.csv")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(
        manifest_path=args.manifest,
        dataset=args.dataset,
        candidates=args.candidates,
        output_dir=args.output_dir,
    ), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
