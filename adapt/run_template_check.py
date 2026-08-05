"""M-B evidence run: are the templates faithful, complete, and do the contracts bite?

Per template:

1. **identity round-trip** — instantiating with the base binding and base
   parameters must reproduce the skeleton byte for byte. This is what makes the
   slot table trustworthy: a missed slot or an over-wide anchor shows up here.
2. **re-binding round-trip** — a scope change (`#Office` -> `#Home`) and a
   threshold change must splice cleanly, re-parse, and leave the block
   signatures untouched.
3. **role coverage** — every device reference in the skeleton is claimed by
   exactly one role. Orphans mean the template is under-specified; refs claimed
   twice mean the role predicates overlap.
4. **catalog coverage** — every device type used has an effect profile, and the
   profiles agree with the platform catalog.
5. **fault injection** — the substitutions from the fault model must be reported
   with the right verdict: AC->Fan blocks (a), Presence->Motion blocks (b),
   Humidifier->Dehumidifier blocks (d), losing an optional role degrades,
   losing an essential role aborts.

    python3 -m adapt.run_template_check
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Optional

from .effects import load_profiles, validate_profiles
from .patch import apply_and_check
from .structure import Structure, extract
from .template import (Binding, Template, base_binding, check_binding, instantiate,
                       list_templates, load_skeleton, load_template, refs_for_role, verdict)

_failures: list[str] = []


def check(cond: bool, label: str) -> bool:
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _failures.append(label)
    return cond


# ── per-template checks ──────────────────────────────────────────────────────

def check_identity(t: Template, st: Structure) -> None:
    edits = instantiate(t, st, base_binding(t), params=None)
    res = apply_and_check(st, edits)
    check(not edits and res.output == st.src,
          f"identity: base binding produces no edits and reproduces the source ({len(edits)} edits)")


def check_rebinding(t: Template, st: Structure) -> None:
    scope = next((p for p in t.params if p.kind == "scope_tag"), None)
    if scope is not None:
        edits = instantiate(t, st, base_binding(t), params={scope.name: "Home"})
        res = apply_and_check(st, edits)
        ok = res.ok and res.structure_after is not None
        if ok:
            diff = {k: v for k, v in st.signature("B0")
                    .diff(res.structure_after.signature("B0")).items() if k != "tags"}
            ok = not diff
        check(ok, f"re-scope: {scope.base_value} -> Home in {len(edits)} places, structure stable")

    thr = next((p for p in t.params if p.kind == "threshold"), None)
    if thr is not None:
        new_val = "26.0" if "." in thr.base_value else "26"
        edits = instantiate(t, st, base_binding(t), params={thr.name: new_val})
        res = apply_and_check(st, edits)
        ok = res.ok and len(edits) == 1
        if ok:
            after = res.structure_after
            got = [a for a in after.assigns if a.name == thr.anchor.get("var")]
            ok = bool(got) and got[0].rhs_span.slice(after.src) == new_val
        check(ok, f"value edit: {thr.name} {thr.base_value} -> {new_val} (1 edit, rest untouched)")

    role_with_device = next((r for r in t.roles
                             if r.requires.kind in ("sensor", "actuator") and r.sources), None)
    if role_with_device is not None:
        src_tags = role_with_device.sources[0].tags
        binding = base_binding(t)
        binding[role_with_device.role] = [["Zzz"] + list(src_tags[1:])] + \
            [list(s.tags) for s in role_with_device.sources[1:]]
        edits = instantiate(t, st, binding)
        res = apply_and_check(st, edits)
        check(res.ok and bool(edits),
              f"role re-binding: {role_with_device.role} {src_tags[0]} -> Zzz "
              f"({len(edits)} edits, splice+syntax ok)")


def check_role_coverage(t: Template, st: Structure) -> None:
    claims: dict[int, list[str]] = {}
    for r in t.roles:
        for ref in refs_for_role(st, r):
            claims.setdefault(id(ref), []).append(r.role)

    orphans = [d for d in st.devices if id(d) not in claims]
    doubles = {k: v for k, v in claims.items() if len(v) > 1}
    if orphans:
        for d in orphans[:6]:
            print(f"        orphan ref L{d.line}: {'#' + ' #'.join(d.tags)}.{d.member}")
    if doubles:
        dbl_refs = [d for d in st.devices if id(d) in doubles]
        for d in dbl_refs[:6]:
            print(f"        double-claimed L{d.line}: {'#' + ' #'.join(d.tags)}.{d.member} "
                  f"by {claims[id(d)]}")
    check(not orphans and not doubles,
          f"role coverage: {len(st.devices)} refs, {len(orphans)} orphan, {len(doubles)} double-claimed")


def check_catalog_coverage(t: Template) -> None:
    profiles = load_profiles()
    missing = []
    for r in t.roles:
        for src in r.sources:
            if src.tags and src.tags[0] not in profiles:
                missing.append(src.tags[0])
    check(not missing, f"effect profiles present for every bound device type "
                       f"({sorted(set(missing)) if missing else 'all'})")


# ── fault injection ──────────────────────────────────────────────────────────

@dataclass
class FaultCase:
    template: str
    role: str
    substitute: Optional[str]        # None = role unavailable
    expect_verdict: str              # abort | degrade | ok
    expect_class: Optional[str]      # fault-model letter that must appear
    label: str


FAULTS = [
    FaultCase("thermo_comfort", "THERMO_ACTUATOR", "Fan", "abort", "a",
              "AC -> Fan: no heat direction, no setpoint, open-loop"),
    FaultCase("thermo_comfort", "THERMO_ACTUATOR", None, "abort", "f",
              "thermostat unavailable: essential role lost"),
    FaultCase("thermo_comfort", "HUMID_ACTUATOR", "Dehumidifier", "degrade", "a",
              "humidifier -> dehumidifier: polarity inverted"),
    FaultCase("thermo_comfort", "HUMID_ACTUATOR", None, "degrade", "f",
              "humidifier unavailable: optional feature dropped"),
    FaultCase("thermo_comfort", "TEMP_SENSORS", "PresenceSensor", "abort", "a",
              "temperature source -> presence sensor: property absent"),
    FaultCase("air_quality", "PURIFIER", None, "degrade", "f",
              "purifier unavailable: advisory features remain"),
    FaultCase("air_quality", "AQ_SENSORS", None, "abort", "f",
              "air-quality sensors unavailable: essential role lost"),
    FaultCase("air_quality", "CO2_INDICATOR", "Speaker", "degrade", "a",
              "indicator light -> speaker: cannot set colour"),
    FaultCase("section_presence", "PRESENCE_SOURCE", "MotionSensor", "abort", "b",
              "presence -> motion: same BOOL property, pulse instead of level"),
    FaultCase("section_presence", "INDICATOR", None, "degrade", "f",
              "indicator light unavailable: advisory feature dropped"),
    FaultCase("section_presence", "SECTION_SINK", None, "abort", "f",
              "section key sink unavailable: nothing to publish"),
]


def run_faults() -> None:
    print("\n=== fault injection ===")
    for case in FAULTS:
        t = load_template(case.template)
        binding = base_binding(t)
        contract = t.role(case.role)
        if case.substitute is None:
            binding[case.role] = []
        else:
            binding[case.role] = [[case.substitute] + list(src.tags[1:]) for src in contract.sources]
        vs = check_binding(t, binding)
        got = verdict(vs, t)
        classes = {v.fault_class for v in vs if v.role == case.role}
        ok = got == case.expect_verdict and (case.expect_class is None or case.expect_class in classes)
        check(ok, f"{case.label} -> {got} (want {case.expect_verdict}), classes={sorted(classes)}")
        for v in vs:
            if v.role == case.role:
                print(f"        [{v.severity:<9}] ({v.fault_class}) {v.detail}")


def run_substitution_matrix() -> None:
    """Which catalog device types could fill each role? Precursor of stage ④."""
    print("\n=== candidate matrix (which device types satisfy each role) ===")
    profiles = load_profiles()
    for tid in list_templates():
        t = load_template(tid)
        print(f"  {t.name}")
        for r in t.roles:
            if r.requires.kind not in ("sensor", "actuator"):
                continue
            fits = []
            for svc in sorted(profiles):
                binding = {r.role: [[svc] + list(s.tags[1:]) for s in r.sources]}
                vs = [v for v in check_binding(t, {**base_binding(t), **binding})
                      if v.role == r.role and v.severity == "blocking"]
                if not vs:
                    fits.append(svc)
            print(f"    {r.role:<18} {fits if fits else '(none besides the base binding)'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M-B: template + contract checks")
    ap.add_argument("--template", help="only this template")
    ap.add_argument("--matrix", action="store_true", help="also print the candidate matrix")
    args = ap.parse_args(argv)

    problems = validate_profiles()
    check(not problems, f"effect catalog agrees with the platform catalog ({len(problems)} problems)")
    for p in problems[:5]:
        print("        -", p)

    ids = [args.template] if args.template else list_templates()
    for tid in ids:
        t = load_template(tid)
        src = load_skeleton(t)
        st = extract(src, t.name)
        print(f"\n=== {tid} — {t.name} ===")
        print(f"  roles={len(t.roles)} (essential {len(t.essential_roles)}) "
              f"params={len(t.params)} contracts={len(t.contracts)} "
              f"| skeleton {len(src)} chars, {len(st.devices)} device refs")
        check(not st.errors, f"skeleton parses ({st.errors[:1]})")
        check_identity(t, st)
        check_rebinding(t, st)
        check_role_coverage(t, st)
        check_catalog_coverage(t)

    run_faults()
    if args.matrix:
        run_substitution_matrix()

    print(f"\n{'ALL PASS' if not _failures else str(len(_failures)) + ' FAILURES'}")
    for f in _failures:
        print("  -", f)
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
