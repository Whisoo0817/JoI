"""Service catalog loader.

Provides ordered argument lists per (service, method) so both simulators can
canonicalize call args to a positional list before tracing — IR uses named
arg dicts, JoI uses positional lists, and the trace comparison requires a
single canonical form.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

_DEFAULT_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "files", "service_list_ver2.0.4.json",
)


@lru_cache(maxsize=4)
def load_catalog(path: str = _DEFAULT_CATALOG_PATH) -> dict[str, dict]:
    """Load and index the service catalog.

    Returns a dict keyed by service id (e.g., "Light", "Dishwasher") with
    sub-dicts {functions: {fn_id: [arg_id, ...]}, values: {val_id: type}}.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    skills = data.get("skills") if isinstance(data, dict) else data
    if not isinstance(skills, list):
        raise ValueError(f"unexpected catalog shape at {path}")

    indexed: dict[str, dict] = {}
    for sk in skills:
        sid = sk.get("id")
        if not sid:
            continue
        functions: dict[str, list[str]] = {}
        for fn in sk.get("functions", []):
            fn_id = fn.get("id")
            if not fn_id:
                continue
            args = [a.get("id") for a in fn.get("arguments", []) if a.get("id")]
            functions[fn_id] = args
        values: dict[str, str] = {}
        for v in sk.get("values", []):
            vid = v.get("id")
            if vid:
                values[vid] = v.get("type", "")
        indexed[sid] = {"functions": functions, "values": values}

    return indexed


def get_arg_order(catalog: dict[str, dict], service: str, method: str) -> list[str] | None:
    """Return the positional arg name list for `service.method`, or None if unknown."""
    sk = catalog.get(service)
    if sk is None:
        return None
    return sk["functions"].get(method)


def split_target(target: str) -> tuple[str, str]:
    """Split an IR call.target string like 'Light.SetBrightness' into (service, method).

    Targets in the IR are dotted; we take the last component as the method and the
    rest as the service. (Some catalog entries use 'dishwasher_setMode' style with
    underscores in the method — those still come through as 'Dishwasher.dishwasher_setMode'.)
    """
    if "." not in target:
        return ("", target)
    service, _, method = target.rpartition(".")
    return (service, method)
