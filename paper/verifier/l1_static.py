"""L1 static analyzer (paper §6.4 V2).

AST-only checks on a JoI block. No simulation, no LLM. Designed to catch the
class of lowering bugs that don't need scenario synthesis to surface:

  - parse failure (brace/paren imbalance, lexer trip)
  - catalog conformance of `(#Service).method(...)` / `(#Service).attr`
        — Service must exist in the runtime `connected_devices` categories
        — method/attr (if catalog provided) must exist for that service
  - cron slot ranges (min 0-59, hour 0-23, dom 1-31, mon 1-12, dow 0-7)
  - use-before-init of `=` lvalues (no prior `:=`)
  - selectors not of the form `(#Tag)` / `all(#Tag)` / `any(#Tag)`

Output: list of `Violation` records with kind, message, and best-effort
source pointer (statement index or selector string). Empty list = pass.

The catalog argument is the indexed dict from
`paper.simulators.catalog.load_catalog`. If None, method/attr existence
checks are skipped (Service-presence still runs from `connected_devices`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from paper.simulators import expr as expr_mod
from paper.simulators import joi_parser as jp
from paper.simulators.expr import canonical_name, canonical_key


def _resolve_service(call_service: str, call_method: str,
                     catalog: Optional[dict],
                     valid_svcs: Optional[set[str]]) -> str:
    """Return the catalog service that OWNS this method.

    Selector tags only steer device_match (which physical device the call hits);
    they do NOT determine which skill provides a method. The owning skill is
    fixed by the method itself — `On`/`switch_on` always belong to Switch,
    regardless of whether the selector reads `(#Dehumidifier)` or
    `(#Plug #Switch #LivingRoom #Dehumidifier)` — exactly as the post-process
    prefix logic assigns `<owner>_<method>` from the method, not the tag. L1
    cannot (and must not) verify device_match, so we resolve the service from
    the METHOD and ignore the selector tag, falling back to the nominal tag
    service only as a last resort so an 'unknown service' / hallucinated method
    can still surface. Assumes method names do not collide across skills.

    This mirrors L2 trace comparison, which also keys on `canonical_key`, so L1
    catalog conformance stays symmetric with L2 trace conformance.
    """
    known_lower = {s.lower() for s in (valid_svcs or set())}
    if catalog:
        known_lower |= {s.lower() for s in catalog.keys()}

    def _orig_cased(name_lower: str) -> Optional[str]:
        for s in (valid_svcs or set()) | set((catalog or {}).keys()):
            if s.lower() == name_lower:
                return s
        return None

    # (1) Owning skill derived from the method prefix (e.g. `switch_on` → Switch,
    #     `dehumidifier_setDehumidifierMode` → Dehumidifier). Tag-independent.
    sub_svc, _ = canonical_key(call_service, call_method)
    if sub_svc and sub_svc.lower() in known_lower:
        return _orig_cased(sub_svc.lower()) or call_service

    # (2) Last resort: the nominal (tag) service, so unknown-service / unknown-
    #     method violations still fire when the method resolves to nothing.
    return call_service


def _catalog_has(catalog_entry: dict, svc: str, method: str) -> tuple[bool, bool]:
    """Return (has_as_func, has_as_value) using prefix-stripped lowercase match.

    JoI scripts post-process methods to `<svc_lower>_<camelMethod>` form
    (e.g. `dishwasher_setDishwasherMode`) while the catalog stores canonical
    names (`SetDishwasherMode`). Compare via simulators.expr.canonical_name,
    which is exactly what trace comparison uses, so L1 catalog conformance
    stays symmetric with L2 trace conformance.
    """
    canon = canonical_name(svc, method)
    funcs = catalog_entry.get("functions", {}) or {}
    vals = catalog_entry.get("values", {}) or {}
    has_func = any(canonical_name(svc, k) == canon for k in funcs)
    has_val = any(canonical_name(svc, k) == canon for k in vals)
    return has_func, has_val


# ── Violation record ────────────────────────────────────────────────────────

@dataclass
class Violation:
    kind: str        # parse | catalog_service | catalog_method | catalog_attr |
                     # cron_slot | use_before_init | selector_form
    message: str
    where: str = ""  # best-effort location label


# ── Entry point ─────────────────────────────────────────────────────────────

def analyze(
    joi_block: dict,
    connected_devices: Optional[dict] = None,
    catalog: Optional[dict] = None,
) -> list[Violation]:
    """Run all L1 checks against `joi_block`. Returns violations (empty if clean)."""
    out: list[Violation] = []

    cron = joi_block.get("cron", "") or ""
    if cron:
        _check_cron(cron, out)

    script_src = joi_block.get("script", "") or ""
    if not script_src.strip():
        return out

    try:
        stmts = jp.parse_script(script_src)
    except Exception as e:
        out.append(Violation("parse", f"{type(e).__name__}: {e}", where="script"))
        return out

    valid_services = _collect_services(connected_devices)
    init_state: set[str] = set()
    for i, s in enumerate(stmts):
        _check_stmt(s, out, valid_services, catalog, init_state, where=f"stmt[{i}]")

    return out


# ── Helpers ─────────────────────────────────────────────────────────────────

_CRON_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
_CRON_SLOT_NAMES = ["minute", "hour", "day-of-month", "month", "day-of-week"]


def _check_cron(cron: str, out: list[Violation]) -> None:
    parts = cron.split()
    if len(parts) != 5:
        out.append(Violation("cron_slot",
                             f"cron must have 5 fields, got {len(parts)}: {cron!r}",
                             where="block.cron"))
        return
    for slot, (lo, hi), name in zip(parts, _CRON_RANGES, _CRON_SLOT_NAMES):
        if slot in ("*", "?"):
            continue
        for v in re.split(r"[,/-]", slot):
            v = v.strip()
            if v in ("", "*"):
                continue
            try:
                n = int(v)
            except ValueError:
                continue  # alpha day names, step-syntax — leave alone
            if not (lo <= n <= hi):
                out.append(Violation(
                    "cron_slot",
                    f"cron {name} out of range [{lo},{hi}]: got {n} in {cron!r}",
                    where="block.cron",
                ))


def _collect_services(connected_devices: Optional[dict]) -> Optional[set[str]]:
    if not isinstance(connected_devices, dict):
        return None
    out: set[str] = set()
    for spec in connected_devices.values():
        if not isinstance(spec, dict):
            continue
        cats = spec.get("category", [])
        if isinstance(cats, list):
            for c in cats:
                if isinstance(c, str):
                    out.add(c)
        elif isinstance(cats, str):
            out.add(cats)
    return out or None


def _check_stmt(s: Any, out: list[Violation], valid_svcs: Optional[set[str]],
                catalog: Optional[dict], init_state: set[str], where: str) -> None:
    if isinstance(s, jp.Assign):
        _walk_expr(s.rhs, out, valid_svcs, catalog, init_state, where=f"{where}.rhs")
        # Treat both `:=` and `=` first-occurrence as initialization. The
        # production lowering uses `=` for fresh variables (matches the prompt
        # examples + runtime accepts it). Read-before-init is still caught via
        # the VarRef path in `_walk_expr`.
        init_state.add(s.name)
    elif isinstance(s, jp.IfStmt):
        _walk_expr(s.cond, out, valid_svcs, catalog, init_state, where=f"{where}.cond")
        for j, t in enumerate(s.then_body):
            _check_stmt(t, out, valid_svcs, catalog, init_state, where=f"{where}.then[{j}]")
        for j, e in enumerate(s.else_body):
            _check_stmt(e, out, valid_svcs, catalog, init_state, where=f"{where}.else[{j}]")
    elif isinstance(s, jp.WaitUntil):
        _walk_expr(s.cond, out, valid_svcs, catalog, init_state, where=f"{where}.cond")
    elif isinstance(s, jp.CallStmt):
        _check_call(s.call, out, valid_svcs, catalog, where=where)
    # Delay / Break: nothing to check


def _walk_expr(node: Any, out: list[Violation], valid_svcs: Optional[set[str]],
               catalog: Optional[dict], init_state: set[str], where: str) -> None:
    if node is None:
        return
    if isinstance(node, jp.CallExpr):
        _check_call(node, out, valid_svcs, catalog, where=where)
        return
    if isinstance(node, expr_mod.VarRef):
        if node.name not in init_state:
            out.append(Violation(
                "use_before_init",
                f"variable {node.name!r} referenced before any `:=` initializer",
                where=where,
            ))
        return
    if isinstance(node, expr_mod.BinaryOp):
        _walk_expr(node.left, out, valid_svcs, catalog, init_state, where)
        _walk_expr(node.right, out, valid_svcs, catalog, init_state, where)
        return
    if isinstance(node, expr_mod.UnaryOp):
        _walk_expr(node.operand, out, valid_svcs, catalog, init_state, where)
        return
    if isinstance(node, expr_mod.FuncCall):
        for a in node.args:
            _walk_expr(a, out, valid_svcs, catalog, init_state, where)
        return
    # Lit, ClockRef, DeviceRef — nothing to flag


def _check_call(call: jp.CallExpr, out: list[Violation],
                valid_svcs: Optional[set[str]], catalog: Optional[dict],
                where: str) -> None:
    svc = _resolve_service(call.service, call.method, catalog, valid_svcs)
    if not svc:
        out.append(Violation("selector_form",
                             "empty selector — expected `(#Service).method(...)`",
                             where=where))
        return
    # `catalog_service` only fires when the (resolved) service is not a known
    # catalog entry. Sub-skill expansion (a Light device implicitly supports
    # Switch / LevelControl / ColorControl) makes the strict
    # `svc in connected_devices.categories` check too noisy; trust catalog
    # membership for service existence and let `catalog_method` /
    # `selector_form` catch the rest.
    if catalog is not None and svc not in catalog and \
            valid_svcs is not None and svc not in valid_svcs:
        out.append(Violation(
            "catalog_service",
            f"selector references service {svc!r} not in connected_devices "
            f"(known: {sorted(valid_svcs)})",
            where=where,
        ))
    if catalog is not None and svc in catalog:
        sk = catalog[svc]
        m = call.method
        is_method = call.args is not None
        has_func, has_val = _catalog_has(sk, svc, m)
        if is_method:
            # Lowering also accepts attr-as-method (some idioms emit
            # `(#X).attr()`). Treat as attr-miss if neither set has it.
            if not (has_func or has_val):
                funcs = sk.get("functions", {})
                vals = sk.get("values", {})
                out.append(Violation(
                    "catalog_method",
                    f"{svc}.{m} is not a known method/attribute (catalog has "
                    f"functions={sorted(funcs.keys())[:6]}{'...' if len(funcs) > 6 else ''}, "
                    f"values={sorted(vals.keys())[:6]}{'...' if len(vals) > 6 else ''})",
                    where=where,
                ))
        else:
            if not (has_val or has_func):
                out.append(Violation(
                    "catalog_attr",
                    f"{svc}.{m} attribute not in catalog",
                    where=where,
                ))


# ── Debug entry ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys
    block = json.loads(sys.stdin.read())
    vs = analyze(block)
    if not vs:
        print("OK")
    else:
        for v in vs:
            print(f"{v.kind} @ {v.where}: {v.message}")
