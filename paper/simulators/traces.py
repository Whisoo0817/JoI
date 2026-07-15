"""Trace records and normalization.

A trace line is `(timestamp_ms, service, method, args)`:
- `timestamp_ms`: int, virtual-clock ms since simulation start (Mon 00:00).
- `service`: bare service name (e.g., "Light"). Stored for debugging only —
  comparison uses `method` since user confirmed method names don't collide.
- `method`: bare method name (e.g., "On", "SetBrightness").
- `args`: positional list of normalized values, ordered by catalog arg order.

Normalization is applied uniformly on both IR-sim and JoI-sim emissions so
that comparison is a pure structural diff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceRecord:
    timestamp_ms: int
    service: str
    method: str
    args: tuple

    def key(self) -> tuple:
        """Comparison key: (method, args). Service excluded — names are unique."""
        return (self.method, self.args)

    def to_dict(self) -> dict:
        return {
            "t_ms": self.timestamp_ms,
            "service": self.service,
            "method": self.method,
            "args": list(self.args),
        }


@dataclass
class Trace:
    """Ordered list of trace records emitted during a simulation run.

    Tracks `group_count`: the number of distinct timestamp groups (within ±100ms)
    that have at least one emission. Used as the stop-criterion bound so that
    same-timestamp duplicates (e.g., D-4's phase-transition tick that fires both
    the `if (phase==0)` and `if (phase==1)` blocks) don't cause the IR and JoI
    sims to stop at different virtual times.
    """

    records: list[TraceRecord] = field(default_factory=list)
    group_count: int = 0
    _last_group_anchor: int | None = field(default=None, repr=False)

    def emit(self, ts_ms: int, service: str, method: str, args: tuple) -> None:
        # Canonicalize service+method via the shared canonical_key so trace,
        # DeviceRef, and apply_effect all use the same namespace.
        from .expr import canonical_key
        canon_service, canon_method = canonical_key(service, method)
        self.records.append(TraceRecord(ts_ms, canon_service, canon_method, args))
        # Increment group_count only if this opens a new ±100ms group
        if self._last_group_anchor is None or ts_ms - self._last_group_anchor > 100:
            self.group_count += 1
            self._last_group_anchor = ts_ms

    def __len__(self) -> int:
        return len(self.records)

    def to_list(self) -> list[dict]:
        return [r.to_dict() for r in self.records]


# ── Normalization ────────────────────────────────────────────────────────────

def normalize_value(v: Any) -> Any:
    """Canonicalize a single arg value.

    - bool stays bool (not coerced to int)
    - int stays int
    - float rounded to 4 decimals (covers color xy)
    - str: stripped of surrounding quotes if redundant; otherwise as-is
    - None stays None
    - other: str()'d
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        # int-valued floats collapse to int (e.g., 80.0 → 80)
        if v.is_integer():
            return int(v)
        return round(v, 4)
    if isinstance(v, str):
        s = v.strip()
        # Strip matching outer quotes once
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
            s = s[1:-1]
        return s
    if v is None:
        return None
    return str(v)


def _coerce_to_type(v: Any, type_name: str) -> Any:
    """Coerce a value to its catalog-declared type when the source was a string
    that looks numeric/boolean. IR extractors often emit numeric args as strings
    (e.g., `"300"`) while JoI emits typed literals (`300`); we canonicalize both.
    """
    if v is None:
        return None
    t = (type_name or "").upper()
    if t in ("INTEGER", "INT", "LONG"):
        if isinstance(v, str) and v.lstrip("-").isdigit():
            return int(v)
        if isinstance(v, float) and v.is_integer():
            return int(v)
    elif t in ("DOUBLE", "FLOAT", "NUMBER"):
        if isinstance(v, str):
            try:
                f = float(v)
                return int(f) if f.is_integer() else round(f, 4)
            except ValueError:
                return v
    elif t in ("BOOL", "BOOLEAN"):
        if isinstance(v, str):
            if v.lower() == "true":
                return True
            if v.lower() == "false":
                return False
    # ENUM / STRING / unknown — leave to normalize_value (string passthrough)
    return v


def _arg_type_map(catalog, service: str, method: str) -> dict[str, str]:
    """Return {arg_id: type_name} for a (service, method) from the catalog, or {} if unknown.

    Re-reads the catalog file once per call (cheap with the lru_cache on load).
    """
    if catalog is None:
        return {}
    sk = catalog.get(service)
    if sk is None:
        return {}
    # The cached catalog only stores arg names (positional). To get types we
    # peek at the raw catalog — re-load via load_catalog (lru-cached) and walk.
    # Simpler: extend catalog.py to store types too. For now, lazy-load raw JSON.
    import os, json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                       "files", "service_list_ver2.0.5.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    skills = data.get("skills") if isinstance(data, dict) else data
    for s in skills or []:
        if s.get("id") != service:
            continue
        for fn in s.get("functions", []):
            if fn.get("id") == method:
                return {a.get("id"): a.get("type", "") for a in fn.get("arguments", [])}
    return {}


def normalize_args(
    catalog: dict[str, dict] | None,
    service: str,
    method: str,
    args: dict | list | tuple,
) -> tuple:
    """Convert call args (dict or positional) to a canonical positional tuple.

    If `args` is a dict (IR style), look up the catalog arg order to position them.
    If `args` is a list/tuple (JoI style), normalize each value but keep order.
    Catalog miss → fall back to alphabetical key ordering for dicts.

    Type-coerces numeric-looking strings to int/float when the catalog declares
    the arg as INTEGER/DOUBLE (handles IR-extractor "300" → 300 vs JoI 300).
    """
    type_map = _arg_type_map(catalog, service, method)

    if isinstance(args, (list, tuple)):
        # JoI positional list. We don't know which arg position is which name
        # without arg_order, but if we have it, we can apply type coercion.
        from .catalog import get_arg_order
        arg_order = get_arg_order(catalog, service, method) if catalog else None
        out: list[Any] = []
        for i, v in enumerate(args):
            v_norm = normalize_value(v)
            if arg_order and i < len(arg_order):
                tname = type_map.get(arg_order[i], "")
                v_norm = _coerce_to_type(v_norm, tname)
            out.append(v_norm)
        return tuple(out)

    if not isinstance(args, dict):
        return ()

    # Dict path
    arg_order = None
    if catalog is not None:
        from .catalog import get_arg_order
        arg_order = get_arg_order(catalog, service, method)

    if arg_order is None:
        keys = sorted(args.keys())
    else:
        keys = list(arg_order) + sorted(k for k in args.keys() if k not in arg_order)

    out = []
    for k in keys:
        if k in args:
            v_norm = normalize_value(args[k])
            tname = type_map.get(k, "")
            v_norm = _coerce_to_type(v_norm, tname)
            out.append(v_norm)
        elif catalog is not None and arg_order is not None and k in arg_order:
            out.append(None)
    return tuple(out)
