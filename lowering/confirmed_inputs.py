"""Build lowering inputs directly from a confirmed IR and binding plan."""

from __future__ import annotations

import re
from collections import defaultdict


_REF = re.compile(r"\$?\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")
_SLOT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:#([1-9][0-9]*))?")


class ConfirmedInputError(ValueError):
    pass


def parse_binding_slots(binding: dict) -> dict[str, list[tuple[list[str], str | None]]]:
    if not isinstance(binding, dict):
        raise ConfirmedInputError("binding must be an object")
    indexed: dict[str, dict[int, tuple[list[str], str | None]]] = defaultdict(dict)
    for name, value in binding.items():
        match = _SLOT.fullmatch(name or "")
        if not match:
            raise ConfirmedInputError(f"invalid binding slot name: {name!r}")
        service, index_text = match.groups()
        index = int(index_text or 1)
        if isinstance(value, dict):
            if len(value) != 1 or next(iter(value)) not in ("any", "all"):
                raise ConfirmedInputError(f"invalid binding quantifier: {name}")
            quantifier, ids = next(iter(value.items()))
        else:
            quantifier, ids = None, value
        if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids):
            raise ConfirmedInputError(f"binding slot needs nonempty device IDs: {name}")
        indexed[service][index] = (list(ids), quantifier)
    result = {}
    for service, entries in indexed.items():
        expected = set(range(1, len(entries) + 1))
        if set(entries) != expected:
            raise ConfirmedInputError(f"non-contiguous binding slots for {service}: {sorted(entries)}")
        result[service] = [entries[i] for i in sorted(entries)]
    return result


def ir_occurrences(ir: dict) -> list[tuple[str, str, str]]:
    """Return ``(Service, member, role)`` in binding-consumption order."""
    found: list[tuple[str, str, str]] = []

    def refs(text, role):
        if not isinstance(text, str):
            return
        for match in _REF.finditer(text):
            service, member = match.groups()
            if service.lower() != "clock":
                found.append((service, member, role))

    def walk(steps):
        for step in steps or []:
            if not isinstance(step, dict):
                continue
            refs(step.get("cond"), "condition")
            refs(step.get("until"), "condition")
            if step.get("op") == "read":
                refs(step.get("src"), "read")
            if step.get("op") == "call":
                target = step.get("target")
                if isinstance(target, str) and "." in target:
                    service, member = target.split(".", 1)
                    found.append((service, member, "query" if step.get("var") else "action"))
                for value in (step.get("args") or {}).values():
                    if isinstance(value, str) and "$" in value:
                        refs(value, "argument")
            for value in step.values():
                if isinstance(value, list):
                    walk(value)

    walk((ir or {}).get("timeline") or [])
    return found


def _selector(service: str, ids: list[str], quantifier: str | None, role: str) -> str:
    if len(ids) == 1:
        return f"(#{ids[0]})"
    if quantifier in ("any", "all"):
        return f"{quantifier}(#{service})"
    if role == "action":
        return f"all(#{service})"
    raise ConfirmedInputError(
        f"scalar/grouped {role} for {service} needs one provider or an explicit any/all binding"
    )


def pipeline_contract(ir: dict, binding: dict, devices: dict) -> dict:
    """Return the mapping adapter shape without natural-language inference."""
    slots = parse_binding_slots(binding)
    occurrences = ir_occurrences(ir)
    seen = defaultdict(int)
    selectors: dict[str, list[str]] = {}
    resolved: dict[str, dict] = {}
    selected: list[str] = []

    for service, member, role in occurrences:
        if service not in slots:
            raise ConfirmedInputError(f"missing binding service: {service}")
        service_slots = slots[service]
        index = seen[service]
        seen[service] += 1
        ids, quantifier = service_slots[0] if len(service_slots) == 1 else (
            service_slots[index] if index < len(service_slots) else (None, None)
        )
        if ids is None:
            raise ConfirmedInputError(f"binding slot underflow: {service}")
        for device_id in ids:
            info = devices.get(device_id)
            if not isinstance(info, dict):
                raise ConfirmedInputError(f"unknown bound device: {device_id}")
            categories = info.get("category") or []
            if isinstance(categories, str):
                categories = [categories]
            if service not in categories:
                raise ConfirmedInputError(f"{device_id} does not declare capability {service}")
        full = f"{service}.{member}"
        if full not in selected:
            selected.append(full)
        rendered = _selector(service, ids, quantifier, role)
        member_selectors = selectors.setdefault(full, [])
        if rendered not in member_selectors:
            member_selectors.append(rendered)
        prior = resolved.get(full)
        if prior:
            prior["devices"] = sorted(set(prior["devices"]) | set(ids))
        else:
            resolved[full] = {"q": quantifier or ("all" if len(ids) > 1 else "one"),
                              "devices": sorted(ids)}

    for service, service_slots in slots.items():
        count = seen.get(service, 0)
        if not count:
            continue
        if len(service_slots) > 1 and count != len(service_slots):
            raise ConfirmedInputError(
                f"binding occurrence mismatch for {service}: {count} uses, {len(service_slots)} slots"
            )
    return {
        "selected_services": selected,
        "df_selectors": selectors,
        "df_resolved": resolved,
        "df_read_services": {f"{s}.{m}" for s, m, role in occurrences if role in ("read", "argument")},
        "errors": [],
        "precision": {"selectors": selectors, "resolved": resolved,
                      "reasoning": "confirmed ir_gt + binding_gt; no NL mapping"},
    }
