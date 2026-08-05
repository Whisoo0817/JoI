"""Stage ② — purpose templates: role slots, role contracts, behavioural contracts.

A template is the scenario minus its binding:

    T = ( skeleton            the verified source, unchanged
        , role slots          TEMP_SENSORS, THERMO_ACTUATOR, OCC_SOURCE, ...
        , role contracts      required capability / effect direction / temporal
                              class / value domain / quantifier intent /
                              essential-or-optional / what to do when unavailable
        , parameter slots     thresholds, cooldowns, the location tag, the period
        , behavioural contracts   "no actuation while unoccupied", deadband,
                                  cooldown, "never heat in summer", ...
        , validity domain )   parameter ranges under which the certificate holds

A **binding** β maps each role to the tags that realise it in a concrete home.
Instantiating T under β is a set of typed edits (stage ⑤), so the output is the
original bytes with the slots swapped — never a re-emitted program.

The contract is where the missing knowledge lives. The catalog says a Fan has
`SetFanMode`; only the contract says this scenario needs something that can move
`temperature` **up** in winter, which is why swapping in a Fan is a defect and
not a rename. Everything in `requires` is checkable against the effect catalog
(stage ③); `essential` / `on_unavailable` / `quantifier_intent` are the parts no
catalog can supply, because they encode the scenario's *purpose*.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .effects import DeviceProfile, catalog_members, load_profiles
from .patch import Edit, apply_and_check, replace_tag
from .structure import DeviceRef, Structure, extract

_HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(_HERE, "templates")

ON_UNAVAILABLE = ("abort", "drop_feature", "degrade", "substitute_required")
QUANTIFIER_INTENT = ("any", "all", "avg", "one")


# ── contracts ────────────────────────────────────────────────────────────────

@dataclass
class Requirement:
    """What a device must be able to do to fill this role."""

    kind: str                                   # sensor | actuator | notifier | namespace
    properties: list[dict] = field(default_factory=list)
    # sensor:   {"property": "temperature", "unit": "°C", "type": "DOUBLE"}
    # actuator: {"property": "temperature", "direction": "up", "when": "winter"}
    temporal: Optional[str] = None              # level | pulse | continuous | oneshot
    control: Optional[str] = None               # setpoint | onoff | level | oneshot
    members: list[str] = field(default_factory=list)   # canonical capability keys used by the code


@dataclass
class Source:
    """One device type that can realise a role, with the members *it* provides.

    Members are per source, not per role: the comfort scenario reads
    `airqualitysensor.temperature` from one source and
    `temperaturesensor.temperature` from the other, and neither device is
    required to have the other's member.
    """

    tags: list[str]
    members: list[str] = field(default_factory=list)


@dataclass
class RoleContract:
    """One slot of the template, plus everything a binding must honour.

    `sources` is a list of alternative tag sets, because a role is often filled
    by more than one device type: the comfort scenario averages temperature over
    `#AirQualitySensor` *and* `#TemperatureSensor`. Location/scope tags are not
    listed here — they are a parameter slot, so that re-scoping a scenario and
    re-binding a role stay independent edits.
    """

    role: str
    purpose: str
    essential: bool
    requires: Requirement
    sources: list[Source]                       # alternative device types realising the role
    cardinality: str = "one"                    # one | one_or_more | zero_or_more
    quantifier_intent: Optional[str] = None     # any | all | avg | one  (fault class (c))
    on_unavailable: str = "abort"               # abort | drop_feature | degrade | substitute_required
    feature: Optional[str] = None               # optional feature this role serves
    gv_keys: list[str] = field(default_factory=list)   # for GlobalVariable-backed roles
    note: str = ""

    @property
    def base_tags(self) -> list[str]:
        return list(self.sources[0].tags) if self.sources else []


@dataclass
class ParamSlot:
    name: str
    kind: str                                   # scope_tag | threshold | cooldown | period | gv_key
    anchor: dict                                # {"var": "max_temp_summer"} | {"tag": "Office"} | {"gv": "occupancy"}
    base_value: str
    unit: Optional[str] = None
    domain: Optional[dict] = None               # {"min":..,"max":..} or {"enum":[..]}
    note: str = ""


@dataclass
class BehaviouralContract:
    id: str
    statement: str
    kind: str                                   # gating | deadband | cooldown | direction | guarded | vacuity
    checkable: str                              # static | smt | runtime
    note: str = ""


@dataclass
class Template:
    id: str
    name: str
    purpose: str
    source_ref: dict                            # {"corpus": "...", "index": 4}
    roles: list[RoleContract]
    params: list[ParamSlot]
    contracts: list[BehaviouralContract]
    features: dict[str, str] = field(default_factory=dict)
    validity: dict[str, Any] = field(default_factory=dict)

    def role(self, name: str) -> RoleContract:
        for r in self.roles:
            if r.role == name:
                return r
        raise KeyError(name)

    @property
    def essential_roles(self) -> list[RoleContract]:
        return [r for r in self.roles if r.essential]


# ── (de)serialisation ────────────────────────────────────────────────────────

def _source(d) -> Source:
    if isinstance(d, list):                      # shorthand: bare tag list
        return Source(tags=list(d))
    return Source(tags=list(d["tags"]), members=list(d.get("members", [])))


def _req(d: dict) -> Requirement:
    return Requirement(kind=d["kind"], properties=d.get("properties", []),
                       temporal=d.get("temporal"), control=d.get("control"),
                       members=d.get("members", []))


def from_dict(d: dict) -> Template:
    return Template(
        id=d["id"], name=d["name"], purpose=d["purpose"], source_ref=d.get("source_ref", {}),
        roles=[RoleContract(role=r["role"], purpose=r.get("purpose", ""),
                            essential=r["essential"], requires=_req(r["requires"]),
                            sources=[_source(x) for x in r["sources"]],
                            cardinality=r.get("cardinality", "one"),
                            quantifier_intent=r.get("quantifier_intent"),
                            on_unavailable=r.get("on_unavailable", "abort"),
                            feature=r.get("feature"), gv_keys=r.get("gv_keys", []),
                            note=r.get("note", ""))
               for r in d.get("roles", [])],
        params=[ParamSlot(name=p["name"], kind=p["kind"], anchor=p["anchor"],
                          base_value=str(p["base_value"]), unit=p.get("unit"),
                          domain=p.get("domain"), note=p.get("note", ""))
                for p in d.get("params", [])],
        contracts=[BehaviouralContract(id=c["id"], statement=c["statement"], kind=c["kind"],
                                       checkable=c["checkable"], note=c.get("note", ""))
                   for c in d.get("contracts", [])],
        features=d.get("features", {}), validity=d.get("validity", {}),
    )


def load_template(template_id: str, directory: str = TEMPLATE_DIR) -> Template:
    with open(os.path.join(directory, f"{template_id}.json"), encoding="utf-8") as f:
        return from_dict(json.load(f))


def list_templates(directory: str = TEMPLATE_DIR) -> list[str]:
    if not os.path.isdir(directory):
        return []
    return sorted(f[:-5] for f in os.listdir(directory) if f.endswith(".json"))


def load_skeleton(t: Template) -> str:
    """The verified source this template abstracts."""
    ref = t.source_ref
    path = os.path.join(os.path.dirname(_HERE), *ref["corpus"].split("/"))
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    return rows[ref["index"]]["code"]


# ── binding ──────────────────────────────────────────────────────────────────

#: role -> one tag list per source (empty list = that source unavailable)
#: (typing aliases, not builtin generics: this line RUNS at import time, and
#:  the deployment interpreter is 3.8 — dict[...] is 3.9+)
Binding = Dict[str, List[List[str]]]


def base_binding(t: Template) -> Binding:
    return {r.role: [list(s.tags) for s in r.sources] for r in t.roles}


def refs_for_role(st: Structure, contract: RoleContract,
                  source: Optional[Source] = None) -> list[DeviceRef]:
    """Device references realising this role (optionally one source only).

    A reference belongs to the role when it carries the source's device tags and
    — when the contract narrows it — uses one of the declared members or GV keys.
    Member/key narrowing matters because one device type can serve several roles:
    `#AirQualitySensor` feeds both TEMP_SENSORS (`.temperature`) and
    HUMID_SENSORS (`.humidity`).
    """
    sources = [source] if source is not None else contract.sources
    gv_keys = set(contract.gv_keys)
    shared = {m.lower() for m in contract.requires.members}
    out: list[DeviceRef] = []
    for d in st.devices:
        hit = next((s for s in sources if set(s.tags).issubset(set(d.tags))), None)
        if hit is None:
            continue
        if gv_keys:
            if _gv_key_of(st, d) not in gv_keys:
                continue
        else:
            allowed = {m.lower() for m in hit.members} | shared
            if allowed and d.key.lower() not in allowed:
                continue
        out.append(d)
    return out


def _gv_key_of(st: Structure, ref: DeviceRef) -> Optional[str]:
    for g in st.gvars:
        if g.ref is ref:
            return g.key
    return None


def instantiate(t: Template, st: Structure, binding: Binding,
                params: Optional[dict[str, str]] = None) -> list[Edit]:
    """Typed edits that re-bind the skeleton. Roles bound to their base sources
    and parameters left at their base value produce no edits at all (identity)."""
    edits: list[Edit] = []
    for contract in t.roles:
        new_sources = binding.get(contract.role, contract.sources)
        for src, new_tags in zip(contract.sources, new_sources):
            if list(src.tags) == list(new_tags) or not new_tags:
                continue          # unchanged, or dropped (a deletion is stage ④'s call)
            refs = refs_for_role(st, contract, source=src)
            for old, new in zip(src.tags, new_tags):
                if old != new:
                    edits.extend(replace_tag(st, old, new, only_refs=refs))

    for name, value in (params or {}).items():
        slot = next((p for p in t.params if p.name == name), None)
        if slot is None:
            raise KeyError(f"unknown parameter slot {name!r}")
        edits.extend(_param_edits(st, slot, value))
    return edits


def _param_edits(st: Structure, slot: ParamSlot, value: str) -> list[Edit]:
    if "var" in slot.anchor:
        var = slot.anchor["var"]
        return [Edit(a.rhs_span, value, "ModifyPredicate", f"{slot.name}={value}")
                for a in st.assigns if a.name == var and a.persistent]
    if "tag" in slot.anchor:
        return replace_tag(st, slot.anchor["tag"], value.lstrip("#"))
    if "gv" in slot.anchor:
        key = slot.anchor["gv"]
        return [Edit(g.key_span, f'"{value}"', "ReplaceArgument", f"gv {key}->{value}")
                for g in st.gvars if g.key == key and g.key_span is not None]
    raise KeyError(f"parameter slot {slot.name!r} has no supported anchor {slot.anchor}")


# ── contract discharge (the part a structural diff cannot do) ────────────────

@dataclass
class Violation:
    role: str
    fault_class: str        # a..f, matching the paper's fault model
    severity: str           # blocking | degraded | warning
    detail: str


def check_role(contract: RoleContract, service: Optional[str],
               profiles: Optional[dict[str, DeviceProfile]] = None,
               source: Optional[Source] = None) -> list[Violation]:
    """Discharge one role contract against a candidate device type.

    `service=None` means "no device available for this role".
    """
    profiles = profiles or load_profiles()
    out: list[Violation] = []

    if service is None:
        sev = "blocking" if contract.essential else "degraded"
        out.append(Violation(contract.role, "f", sev,
                             f"no device for role; on_unavailable={contract.on_unavailable}"))
        return out

    p = profiles.get(service)
    if p is None:
        out.append(Violation(contract.role, "a", "blocking",
                             f"{service}: no effect profile (cannot judge the binding) - fail closed"))
        return out

    req = contract.requires
    if req.kind and p.kind != req.kind:
        out.append(Violation(contract.role, "a", "blocking",
                             f"{service} is a {p.kind}, role needs a {req.kind}"))

    if req.temporal and p.temporal != req.temporal:
        sev = "blocking" if (req.temporal, p.temporal) == ("level", "pulse") else "warning"
        out.append(Violation(contract.role, "b", sev,
                             f"temporal class {p.temporal} != required {req.temporal}"
                             + (" (a pulse cannot sustain a level guard without a latch)"
                                if sev == "blocking" else "")))

    if req.control and p.control != req.control:
        sev = "blocking" if req.control == "setpoint" else "warning"
        out.append(Violation(contract.role, "a", sev,
                             f"control mode {p.control} != required {req.control}"
                             + (f"; {service} has no setpoint" if req.control == "setpoint" and not p.setpoint else "")))

    for spec in req.properties:
        prop = spec["property"]
        if req.kind == "sensor":
            m = p.measures_property(prop)
            if m is None:
                out.append(Violation(contract.role, "a", "blocking",
                                     f"{service} does not measure {prop}"))
                continue
            want_unit, want_type = spec.get("unit"), spec.get("type")
            if want_unit and m.unit and m.unit != want_unit:
                out.append(Violation(contract.role, "d", "blocking",
                                     f"{prop} unit {m.unit} != expected {want_unit} "
                                     f"(thresholds are calibrated for {want_unit})"))
            if want_type and m.type != want_type:
                out.append(Violation(contract.role, "d", "blocking",
                                     f"{prop} type {m.type} != expected {want_type}"))
        else:
            direction = spec.get("direction", "set")
            eff = p.moves(prop, direction)
            if eff is None:
                when = f" (needed {spec['when']})" if spec.get("when") else ""
                opposite = {"up": "down", "down": "up"}.get(direction)
                inverse = p.moves(prop, opposite) if opposite else None
                if inverse is not None:
                    out.append(Violation(contract.role, "d", "blocking",
                                         f"{service} moves {prop} {opposite}, the role needs "
                                         f"{direction}{when} — polarity inverted"))
                else:
                    out.append(Violation(contract.role, "a", "blocking",
                                         f"{service} cannot move {prop} {direction}{when}"))
            elif not eff.closed_loop and spec.get("closed_loop", True):
                out.append(Violation(contract.role, "a", "warning",
                                     f"{service} affects {prop} open-loop only; "
                                     f"a guard reading {prop} will never be satisfied by it"))
            elif eff.incidental:
                out.append(Violation(contract.role, "a", "warning",
                                     f"{service} moves {prop} {direction} only incidentally"))

    need_members = list(req.members) + list(source.members if source else [])
    if need_members:
        # The platform catalog is the authority on which members exist; the
        # profile only adds the ones the annotation names explicitly.
        known = catalog_members(service)
        if p.setpoint:
            known.add(str(p.setpoint.get("member", "")).lower())
        if p.mode:
            known.add(str(p.mode.get("member", "")).lower())
        known |= {m.member.lower() for m in p.measures}
        for need in need_members:
            if need.lower() not in known:
                out.append(Violation(contract.role, "a", "blocking",
                                     f"{service} lacks member {need} used by the skeleton"))
    return out


def check_binding(t: Template, binding: Binding,
                  service_of: Optional[dict[str, str]] = None) -> list[Violation]:
    """Discharge every role contract under `binding`.

    Each *source* of a role is judged separately, then combined: a role with
    `cardinality=one_or_more` survives as long as one source still satisfies the
    contract (the surviving sources cover it); a role whose sources are all gone
    or all violating is reported against `on_unavailable`.

    `service_of` maps a tag to its device type; by default the first tag of a
    source names the device type (the corpus convention).
    """
    profiles = load_profiles()
    out: list[Violation] = []
    for contract in t.roles:
        sources = [s for s in binding.get(contract.role, []) if s]
        if not sources:
            out.extend(check_role(contract, None, profiles))
            continue

        per_source: list[list[Violation]] = []
        for src, tags in zip(contract.sources, sources):
            service = (service_of or {}).get(tags[0], tags[0])
            per_source.append(check_role(contract, service, profiles, source=src))

        healthy = [v for v in per_source if not any(x.severity == "blocking" for x in v)]
        if healthy and contract.cardinality in ("one_or_more", "zero_or_more"):
            # at least one source still honours the contract: report the rest as warnings
            for tags, vs in zip(sources, per_source):
                for v in vs:
                    if v.severity == "blocking":
                        out.append(Violation(v.role, v.fault_class, "warning",
                                             f"source {'+'.join(tags)} dropped: {v.detail}"))
                    else:
                        out.append(v)
        else:
            for vs in per_source:
                out.extend(vs)

    seen: set[tuple] = set()
    deduped: list[Violation] = []
    for v in out:
        key = (v.role, v.fault_class, v.severity, v.detail)
        if key not in seen:
            seen.add(key)
            deduped.append(v)
    return deduped


def verdict(violations: list[Violation], t: Template) -> str:
    """abort / degrade / ok — the three-way judgement stage ④ has to make."""
    blocking = [v for v in violations if v.severity == "blocking"]
    if any(t.role(v.role).essential for v in blocking):
        return "abort"
    if blocking or any(v.severity == "degraded" for v in violations):
        return "degrade"
    return "ok"


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Stage ②: purpose templates")
    ap.add_argument("template", nargs="?", help="template id (omit to list)")
    ap.add_argument("--bind", action="append", default=[],
                    help="ROLE=tag[,tag] override, repeatable; ROLE= (empty) means unavailable")
    args = ap.parse_args(argv)

    if not args.template:
        for tid in list_templates():
            t = load_template(tid)
            print(f"{tid:<22} {t.name:<18} roles={len(t.roles)} "
                  f"(essential {len(t.essential_roles)}) params={len(t.params)} contracts={len(t.contracts)}")
        return 0

    t = load_template(args.template)
    binding = base_binding(t)
    for spec in args.bind:
        role, _, tags = spec.partition("=")
        binding[role] = [x for x in tags.split(",") if x]

    print(f"# {t.name} — {t.purpose}")
    for r in t.roles:
        mark = "essential" if r.essential else f"optional({r.feature or '-'})"
        print(f"  {r.role:<18} {mark:<20} bound={binding.get(r.role)} "
              f"card={r.cardinality} quant={r.quantifier_intent} on_unavail={r.on_unavailable}")
    vs = check_binding(t, binding)
    print(f"\n  verdict: {verdict(vs, t).upper()}")
    for v in vs:
        print(f"    [{v.severity:<9}] ({v.fault_class}) {v.role}: {v.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
