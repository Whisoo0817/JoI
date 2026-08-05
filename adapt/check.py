"""Stage ⑥ — static checks on an adapted program (M-D).

Cheap, solver-free layer of the verification ladder (L2): everything here is
interval/ordering arithmetic over template metadata, catching the faults that
survive a syntactically perfect edit.

* **domain**   — every parameter value lies in its declared domain and inside
  the bound device's physical range (setpoint). "25 -> 26" is fine; "25 -> 99"
  silently saturates the thermostat and is refused here.
* **band**     — min/max threshold pairs stay ordered with a non-empty gap.
  The simplest possible request ("26도로 바꿔줘") can invert a deadband and make
  both branches unreachable; that is fault class vacuity at parameter level.
* **drop signature** — after a feature drop, the dropped role's capability keys
  are gone and every surviving capability key is untouched (counts included):
  the deletion removed exactly the feature, nothing else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .structure import Structure
from .template import ParamSlot, Template


@dataclass
class Finding:
    check: str                 # domain | band | drop_signature
    severity: str              # blocking | warning
    detail: str


def _num(text: str) -> Optional[float]:
    try:
        return float(eval(text, {"__builtins__": {}}, {}))  # noqa: S307 — literals like "30 * 60"
    except Exception:
        return None


def _current_value(st: Structure, slot: ParamSlot) -> Optional[float]:
    var = slot.anchor.get("var")
    if var is None:
        return None
    for a in st.assigns:
        if a.name == var and a.persistent:
            return _num(a.rhs_span.slice(st.src))
    return None


def check_domains(t: Template, st: Structure) -> list[Finding]:
    out: list[Finding] = []
    for p in t.params:
        if p.domain is None:
            continue
        v = _current_value(st, p)
        if v is None:
            continue
        lo, hi = p.domain.get("min"), p.domain.get("max")
        if lo is not None and v < lo or hi is not None and v > hi:
            out.append(Finding("domain", "blocking",
                               f"{p.name}={v} outside domain [{lo}, {hi}] {p.unit or ''}"))
    return out


_BAND = re.compile(r"^min_(.+)$")


def check_bands(t: Template, st: Structure) -> list[Finding]:
    """Pairs by naming convention min_X / max_X over the template's own params."""
    out: list[Finding] = []
    by_name = {p.name: p for p in t.params}
    for name, p in by_name.items():
        m = _BAND.match(name)
        if not m or f"max_{m.group(1)}" not in by_name:
            continue
        q = by_name[f"max_{m.group(1)}"]
        lo, hi = _current_value(st, p), _current_value(st, q)
        if lo is None or hi is None:
            continue
        if lo >= hi:
            out.append(Finding("band", "blocking",
                               f"band inverted/empty: {p.name}={lo} >= {q.name}={hi} "
                               f"— both branches become unreachable"))
    return out


def check_drop_signature(t: Template, before: Structure, after: Structure,
                         dropped_roles: list[str]) -> list[Finding]:
    out: list[Finding] = []
    from .template import refs_for_role

    # Keys are service-qualified: the shared switch capability means a bare
    # `switch.on` belongs to the humidifier AND the AC — dropping one must not
    # be confused with the other's survival.
    def qkey(d) -> str:
        return f"{d.service}:{d.key}".lower()

    dropped_keys = set()
    for r in dropped_roles:
        for ref in refs_for_role(before, t.role(r)):
            dropped_keys.add(qkey(ref))

    def keyed_counts(st: Structure) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in st.devices:
            counts[qkey(d)] = counts.get(qkey(d), 0) + 1
        return counts

    b, a = keyed_counts(before), keyed_counts(after)
    for k in sorted(dropped_keys):
        if a.get(k, 0) > 0:
            out.append(Finding("drop_signature", "blocking",
                               f"dropped capability {k} still referenced {a[k]}x"))
    for k in sorted(set(b) - dropped_keys):
        # surviving keys may only shrink by collateral notifier deletions
        if a.get(k, 0) > b[k]:
            out.append(Finding("drop_signature", "blocking",
                               f"surviving capability {k} count grew {b[k]} -> {a.get(k, 0)}"))
        if a.get(k, 0) == 0 and b[k] > 0 and ":toastpublisher." not in k and ":speaker." not in k:
            out.append(Finding("drop_signature", "warning",
                               f"surviving capability {k} disappeared with the drop "
                               f"({b[k]}x) — check it was genuinely feature-local"))
    return out


def check_static(t: Template, st: Structure, *, before: Optional[Structure] = None,
                 dropped_roles: Optional[list[str]] = None) -> list[Finding]:
    out = check_domains(t, st) + check_bands(t, st)
    if before is not None and dropped_roles:
        out += check_drop_signature(t, before, st, dropped_roles)
    return out
