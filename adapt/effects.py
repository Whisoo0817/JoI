"""Stage ③ — effect-annotation catalog.

The device catalog (`files/service_list_ver2.0.7.json`) already gives types,
units and enums. Re-binding needs three axes it does not carry:

* **effect direction** — `AirConditioner` moves `temperature` *down* in cool mode
  and *up* in heat mode; `Fan` moves only `perceived_temperature` down and never
  touches measured room temperature. That difference is invisible to the catalog
  and to any structural diff, yet it is exactly fault class (a).
* **temporal class** — `PresenceSensor.Presence` and `MotionSensor.Motion` are
  both `BOOL` in the catalog. One is a level, the other a pulse: fault class (b).
* **control mode** — setpoint / on-off / level. A scenario that calls
  `SetTargetTemperature` cannot be re-bound to a device with no setpoint.

`essential` is deliberately absent here: whether a role may be dropped depends on
the scenario's purpose, so it belongs to the template's role contract (stage ②).

This module also cross-checks every annotation against the real catalog, so an
annotation can never silently drift from the platform definition.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from sim.catalog import _DEFAULT_CATALOG_PATH, load_catalog  # noqa: E402
from sim.expr import canonical_key  # noqa: E402

EFFECTS_PATH = os.path.join(_HERE, "effects.json")

DIRECTIONS = ("up", "down", "set")
TEMPORAL = ("level", "pulse", "continuous", "oneshot")
CONTROL = ("setpoint", "onoff", "level", "oneshot")


@dataclass(frozen=True)
class Effect:
    """One physical property a device moves, and which way."""

    property: str
    direction: str
    requires_mode: Optional[str] = None
    closed_loop: bool = True          # does the effect feed back into a sensor we read?
    incidental: bool = False          # side effect, not the reason to bind this device
    note: str = ""


@dataclass(frozen=True)
class Measurement:
    property: str
    member: str                       # canonical "capability.attr"
    type: str
    unit: Optional[str]
    plausible_range: Optional[tuple[float, float]] = None
    note: str = ""


@dataclass
class DeviceProfile:
    service: str
    kind: str                         # actuator | sensor | notifier | infrastructure | namespace
    temporal: str
    control: Optional[str] = None
    power: Optional[str] = None
    affects: list[Effect] = field(default_factory=list)
    measures: list[Measurement] = field(default_factory=list)
    setpoint: Optional[dict] = None
    mode: Optional[dict] = None
    note: str = ""

    # -- queries used by the contract checker (stage ④/⑥) --

    def moves(self, prop: str, direction: str) -> Optional[Effect]:
        for e in self.affects:
            if e.property == prop and e.direction == direction:
                return e
        return None

    def measures_property(self, prop: str) -> Optional[Measurement]:
        for m in self.measures:
            if m.property == prop:
                return m
        return None

    @property
    def properties(self) -> set[str]:
        return {e.property for e in self.affects} | {m.property for m in self.measures}


def _mk_profile(service: str, raw: dict) -> DeviceProfile:
    return DeviceProfile(
        service=service,
        kind=raw.get("kind", "unknown"),
        temporal=raw.get("temporal", "level"),
        control=raw.get("control"),
        power=raw.get("power"),
        affects=[Effect(property=e["property"], direction=e["direction"],
                        requires_mode=e.get("requires_mode"),
                        closed_loop=e.get("closed_loop", True),
                        incidental=e.get("incidental", False),
                        note=e.get("note", ""))
                 for e in raw.get("affects", [])],
        measures=[Measurement(property=m["property"], member=m["member"], type=m["type"],
                              unit=m.get("unit"),
                              plausible_range=(tuple(m["plausible_range"])
                                               if m.get("plausible_range") else None),
                              note=m.get("note", ""))
                  for m in raw.get("measures", [])],
        setpoint=raw.get("setpoint"),
        mode=raw.get("mode"),
        note=raw.get("note", ""),
    )


@lru_cache(maxsize=2)
def load_profiles(path: str = EFFECTS_PATH) -> dict[str, DeviceProfile]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {svc: _mk_profile(svc, body) for svc, body in raw.items() if not svc.startswith("_")}


# ── consistency with the platform catalog ────────────────────────────────────

def catalog_members(service: str, catalog: Optional[dict] = None) -> set[str]:
    """Canonical "capability.attr" keys the platform catalog defines for a service.

    The catalog — not the effect annotation — is the authority on which members
    exist, so namespace services like GlobalVariable (whose members are pure
    functions with no physical effect) are covered too.
    """
    catalog = catalog if catalog is not None else load_catalog()
    entry = catalog.get(service) or catalog.get(service.lower()) or {}
    out: set[str] = set()
    for fn in (entry.get("functions") or {}):
        cap, attr = canonical_key(service, f"{service[0].lower()}{service[1:]}_{fn}")
        out.add(f"{cap}.{attr}")
        out.add(f"{service.lower()}.{fn.lower()}")
    for val in (entry.get("values") or {}):
        out.add(f"{service.lower()}.{val.lower()}")
    # every device also exposes the shared Switch capability in this platform
    out |= {"switch.on", "switch.off", "switch.switch", "switch.toggle"}
    return out


@lru_cache(maxsize=2)
def _catalog_enums(path: str = _DEFAULT_CATALOG_PATH) -> dict[str, set[str]]:
    """service -> allowed enum member values (lowercased).

    `sim.catalog.load_catalog` keeps only functions and values, so the enum
    vocabulary is read straight from the platform JSON; without this the mode
    check would pass vacuously.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    skills = data.get("skills") if isinstance(data, dict) else data
    out: dict[str, set[str]] = {}
    for s in skills or []:
        vals: set[str] = set()
        for e in s.get("enums", []) or []:
            for m in e.get("members", []) or []:
                vals.add(str(m.get("value", "")).lower())
        out[s["id"]] = vals
    return out


def validate_profiles(profiles: Optional[dict[str, DeviceProfile]] = None) -> list[str]:
    """Return a list of problems: unknown services, members not in the catalog,
    bad enum values, out-of-vocabulary direction / temporal / control values."""
    profiles = profiles or load_profiles()
    catalog = load_catalog()
    known = {k.lower() for k in catalog}
    problems: list[str] = []

    for svc, p in profiles.items():
        if svc.lower() not in known and p.kind not in ("namespace", "infrastructure"):
            problems.append(f"{svc}: not in platform catalog")
            continue
        if p.temporal not in TEMPORAL:
            problems.append(f"{svc}: bad temporal {p.temporal!r}")
        if p.control is not None and p.control not in CONTROL:
            problems.append(f"{svc}: bad control {p.control!r}")
        for e in p.affects:
            if e.direction not in DIRECTIONS:
                problems.append(f"{svc}: bad direction {e.direction!r} on {e.property}")
        if p.kind in ("namespace", "infrastructure"):
            continue

        members = catalog_members(svc, catalog)
        for m in p.measures:
            if m.member.lower() not in members:
                problems.append(f"{svc}: measure member {m.member!r} absent from catalog")
        for key in ("setpoint", "mode"):
            spec = getattr(p, key)
            if spec and spec.get("member") and spec["member"].lower() not in members:
                problems.append(f"{svc}: {key} member {spec['member']!r} absent from catalog")
        if p.mode and p.mode.get("enum"):
            allowed = _catalog_enums().get(svc, set())
            if not allowed:
                problems.append(f"{svc}: mode enum declared but catalog defines no enum values")
            else:
                unknown = [v for v in p.mode["enum"] if str(v).lower() not in allowed]
                if unknown:
                    problems.append(f"{svc}: mode values not in catalog enum: {unknown}")
    return problems


def coverage(services: list[str]) -> tuple[list[str], list[str]]:
    """Split `services` into (annotated, missing)."""
    profiles = load_profiles()
    have = [s for s in services if s in profiles]
    miss = [s for s in services if s not in profiles]
    return have, miss


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Stage ③: effect catalog")
    ap.add_argument("--validate", action="store_true", help="cross-check against the platform catalog")
    ap.add_argument("--show", help="print one profile")
    args = ap.parse_args(argv)

    profiles = load_profiles()
    if args.show:
        p = profiles.get(args.show)
        if not p:
            print(f"no profile for {args.show!r}; have {sorted(profiles)}")
            return 1
        print(json.dumps({
            "service": p.service, "kind": p.kind, "temporal": p.temporal, "control": p.control,
            "affects": [vars(e) for e in p.affects],
            "measures": [vars(m) for m in p.measures],
            "setpoint": p.setpoint, "mode": p.mode,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"profiles: {len(profiles)}  ({', '.join(sorted(profiles))})")
    if args.validate:
        problems = validate_profiles(profiles)
        if problems:
            print(f"\n{len(problems)} problems:")
            for p in problems:
                print("  -", p)
            return 1
        print("catalog cross-check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
