"""Static validation for all confirmed E3 IR, binding, inventory and catalog rows."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
import json
from pathlib import Path
import re

from lowering.confirmed_inputs import ir_occurrences, pipeline_contract
from timeline_ir.catalog import load_catalog, load_service_specs, value_domains
from timeline_ir.semantic_contract import EDGE_TRIGGER_DEFAULT_PERIOD, has_rearming_edge
from timeline_ir.timeline_ir import (
    validate_ir,
    validate_ir_against_catalog,
    validate_ir_against_devices,
)


ROOT = Path(__file__).resolve().parents[2]
_VALUE_REF = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)")


def _case_id(row):
    return f"{row['category_v2']}_{int(float(row['index'])):03d}"


def _walk(steps):
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        yield step
        for value in step.values():
            if isinstance(value, list):
                yield from _walk(value)


def _function_specs():
    out = {}
    for service in load_service_specs()["skills"]:
        for fn in service.get("functions", []):
            out[(service["id"], fn["id"])] = fn
    return out


def _interval(node, variables):
    if isinstance(node, ast.Expression):
        return _interval(node.body, variables)
    if isinstance(node, ast.Name):
        return variables[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        value = float(node.value)
        return value, value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        lo, hi = _interval(node.operand, variables)
        return -hi, -lo
    if isinstance(node, ast.BinOp):
        a, b = _interval(node.left, variables), _interval(node.right, variables)
        if isinstance(node.op, ast.Add):
            return a[0] + b[0], a[1] + b[1]
        if isinstance(node.op, ast.Sub):
            return a[0] - b[1], a[1] - b[0]
        if isinstance(node.op, ast.Mult):
            values = (a[0] * b[0], a[0] * b[1], a[1] * b[0], a[1] * b[1])
            return min(values), max(values)
        if isinstance(node.op, ast.Div) and not (b[0] <= 0 <= b[1]):
            values = (a[0] / b[0], a[0] / b[1], a[1] / b[0], a[1] / b[1])
            return min(values), max(values)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("min", "max"):
        args = [_interval(arg, variables) for arg in node.args]
        if node.func.id == "min":
            return min(x[0] for x in args), min(x[1] for x in args)
        return max(x[0] for x in args), max(x[1] for x in args)
    raise ValueError(f"unsupported interval expression: {ast.dump(node)}")


def _numeric_expression_issue(value, arg_spec, domains):
    if not isinstance(value, str) or not _VALUE_REF.search(value):
        return None
    variables = {}
    expression = value
    for index, match in enumerate(_VALUE_REF.finditer(value)):
        service, member = match.groups()
        domain = domains.get((service, member)) or {}
        bound = domain.get("bound")
        if not (isinstance(bound, list) and len(bound) == 2):
            return ("UNBOUNDED_NUMERIC_ACTION_INPUT",
                    f"{service}.{member} has no authoritative numeric bound")
        name = f"v{index}"
        variables[name] = (float(bound[0]), float(bound[1]))
        expression = expression.replace(match.group(0), name, 1)
    try:
        lo, hi = _interval(ast.parse(expression, mode="eval"), variables)
    except Exception as exc:
        return "UNPROVED_NUMERIC_ACTION_EXPRESSION", str(exc)
    arg_bound = arg_spec.get("bound")
    if isinstance(arg_bound, list) and len(arg_bound) == 2:
        if lo < float(arg_bound[0]) or hi > float(arg_bound[1]):
            return ("NUMERIC_ACTION_OUT_OF_BOUNDS",
                    f"proven interval [{lo}, {hi}] exceeds {arg_bound}")
    return None


def validate_row(row, function_specs, domains):
    case_id = _case_id(row)
    ir = json.loads(row["ir_gt"])
    binding = json.loads(row.get("binding_gt") or "{}")
    devices = json.loads(row["connected_devices"])
    errors, limitations = [], []
    try:
        validate_ir(ir)
        validate_ir_against_devices(ir, devices)
        validate_ir_against_catalog(ir, load_catalog())
        pipeline_contract(ir, binding, devices)
    except Exception as exc:
        errors.append({"code": "STRUCTURAL_CONTRACT", "detail": f"{type(exc).__name__}: {exc}"})
        return {"id": case_id, "errors": errors, "limitations": limitations}

    serialized = json.dumps(ir, ensure_ascii=False)
    for step in _walk(ir.get("timeline")):
        if step.get("op") == "cycle" and has_rearming_edge(step):
            if step.get("period") != EDGE_TRIGGER_DEFAULT_PERIOD:
                errors.append({"code": "EDGE_PERIOD_CONTRACT",
                               "detail": f"explicit edge period is {step.get('period')!r}, expected '1 SEC'"})
        if step.get("op") != "call":
            continue
        service, method = step["target"].split(".", 1)
        fn = function_specs[(service, method)]
        return_type = fn.get("return_type")
        if isinstance(return_type, dict):
            return_type = return_type.get("type")
        variable = step.get("var")
        if variable:
            if return_type in (None, "VOID"):
                errors.append({"code": "INVALID_RETURN_ASSIGNMENT", "detail": step["target"]})
            elif not re.search(r"\$" + re.escape(variable) + r"\b", serialized):
                errors.append({"code": "UNUSED_RETURN_ASSIGNMENT", "detail": variable})
        arg_specs = {arg["id"]: arg for arg in fn.get("arguments", [])}
        for name, value in (step.get("args") or {}).items():
            spec = arg_specs[name]
            issue = _numeric_expression_issue(value, spec, domains)
            if issue:
                code, detail = issue
                target = limitations if code.startswith("UNBOUNDED_") else errors
                target.append({"code": code, "detail": f"{step['target']}.{name}: {detail}"})
            bound = spec.get("bound")
            if isinstance(value, (int, float)) and isinstance(bound, list) and len(bound) == 2:
                if value < bound[0] or value > bound[1]:
                    errors.append({"code": "NUMERIC_LITERAL_OUT_OF_BOUNDS",
                                   "detail": f"{step['target']}.{name}={value} outside {bound}"})
    return {"id": case_id, "errors": errors, "limitations": limitations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(ROOT / "dataset.csv"))
    parser.add_argument("--known-limitations", default=str(
        ROOT / "PerCom/6_Evaluation/E3_application/E3_KNOWN_LIMITATIONS.json"))
    parser.add_argument("--output")
    args = parser.parse_args()
    known = json.loads(Path(args.known_limitations).read_text())
    function_specs = _function_specs()
    domains = value_domains()
    rows = []
    with open(args.dataset, encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if (row.get("category_v2") or "").strip() and (row.get("ir_gt") or "").strip():
                rows.append(validate_row(row, function_specs, domains))
    undeclared = []
    for row in rows:
        actual = sorted(x["code"] for x in row["limitations"])
        expected = sorted(known.get(row["id"], []))
        if actual != expected:
            undeclared.append({"id": row["id"], "expected": expected, "actual": actual})
    report = {
        "rows": len(rows),
        "error_count": sum(len(row["errors"]) for row in rows),
        "limitation_count": sum(len(row["limitations"]) for row in rows),
        "error_codes": dict(Counter(x["code"] for row in rows for x in row["errors"])),
        "limitation_codes": dict(Counter(x["code"] for row in rows for x in row["limitations"])),
        "undeclared_limitations": undeclared,
        "cases": [row for row in rows if row["errors"] or row["limitations"]],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    print(rendered)
    if report["error_count"] or undeclared or len(rows) != 388:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
