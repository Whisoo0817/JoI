"""Device-set grounding of world-state keys (reviewer attack #2 fix).

The simulators' world model derives state keys from selectors with a
last-tag / method-prefix heuristic, so the SAME physical device can be
read under different keys by the IR and the JoI sides (e.g. IR
`Light.Hallway` → "light.hallway" vs JoI `(#Light #LivingRoom).hallway`
→ "livingroom.hallway"). The symbolic input model then treats them as
independent inputs and reports an artifact divergence.

This module resolves selectors against `connected_devices` (the same
deterministic set-intersection the generation pipeline uses) and unifies
keys ONLY when the device sets prove they denote the same state:

    alias[key_joi] = key_ir   iff  attr matches, resolve(JoI tags) ⊆
                                   resolve(IR service), both nonempty,
                                   and the mapping is unambiguous

Disjoint sets with a matching attr are reported as MISTARGET (a genuine
targeting mismatch — kept separate so the gate flags it). Ambiguous or
colliding mappings are dropped (sound: keys stay separate).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sim import expr as E

_SELECTOR_RE = re.compile(
    r"(?:all|any)?\(\s*((?:#[A-Za-z_][A-Za-z0-9_]*\s*)+)\)\.([A-Za-z_][A-Za-z0-9_]*)")
_TAG_RE = re.compile(r"#([A-Za-z_][A-Za-z0-9_]*)")
_SERVICE_ATTR_RE = re.compile(
    r"(?<![$\w.])([A-Z][A-Za-z0-9]*)\.([A-Za-z][A-Za-z0-9_]*)")


def _norm_devices(devices) -> dict:
    out = {}
    if not isinstance(devices, dict):
        return out
    for did, spec in devices.items():
        if not isinstance(spec, dict):
            continue
        tags = {str(t).lower() for t in (spec.get("tags") or [])}
        cats = spec.get("category") or []
        if isinstance(cats, str):
            cats = [cats]
        cats = {str(c).lower() for c in cats}
        out[did] = {"tags": tags | cats, "cats": cats}
    return out


def resolve_tags(tags: list, devices: dict) -> frozenset:
    """Devices carrying ALL selector tags (intersection semantics)."""
    want = {t.lower() for t in tags}
    return frozenset(d for d, s in devices.items() if want <= s["tags"])


def resolve_service(svc: str, devices: dict) -> frozenset:
    s = svc.lower()
    return frozenset(d for d, s_ in devices.items()
                     if s in s_["cats"] or s in s_["tags"])


@dataclass
class Grounding:
    alias: dict = field(default_factory=dict)       # key_joi → key_ir
    mistargets: list = field(default_factory=list)  # human-readable notes
    reverse: dict = field(default_factory=dict)     # key_ir → [key_joi,...]


def _ir_refs(ir: dict) -> list:
    """(service, member) raw pairs referenced anywhere in the IR."""
    out = []

    def scan_str(s):
        if isinstance(s, str):
            for svc, mem in _SERVICE_ATTR_RE.findall(s):
                out.append((svc, mem))

    def walk(steps):
        for st in steps or []:
            if not isinstance(st, dict):
                continue
            op = st.get("op")
            if op == "call":
                t = st.get("target", "")
                if "." in t:
                    svc, _, m = t.partition(".")
                    out.append((svc, m))
                for v in (st.get("args") or {}).values():
                    scan_str(v)
            elif op == "read":
                scan_str(st.get("src"))
            elif op in ("wait", "if"):
                scan_str(st.get("cond"))
                walk(st.get("then"))
                walk(st.get("else"))
            elif op == "cycle":
                scan_str(st.get("until"))
                walk(st.get("body"))
    walk((ir or {}).get("timeline", [])[1:] if (ir or {}).get("timeline") else [])
    return out


def compute_grounding(ir: dict, joi_block: dict, devices) -> Grounding:
    g = Grounding()
    devs = _norm_devices(devices)
    if not devs:
        return g

    # IR side: canonical key → (device set, attr)
    ir_entries: dict = {}
    for svc, mem in _ir_refs(ir):
        k_svc, k_attr = E.canonical_key(svc, mem)
        key = f"{k_svc}.{k_attr}"
        ir_entries.setdefault(key, {"attr": k_attr,
                                    "set": resolve_service(svc, devs)})

    # JoI side: selector occurrences in the script text
    script = (joi_block or {}).get("script", "") or ""
    joi_refs: dict = {}    # key_joi → {"attr":…, "sets": [frozenset,…]}
    for m in _SELECTOR_RE.finditer(script):
        tags = _TAG_RE.findall(m.group(1))
        member = m.group(2)
        if not tags:
            continue
        k_svc, k_attr = E.canonical_key(tags[-1], member)
        key = f"{k_svc}.{k_attr}"
        ent = joi_refs.setdefault(key, {"attr": k_attr, "sets": []})
        ent["sets"].append(resolve_tags(tags, devs))

    for key_joi, ent in joi_refs.items():
        if key_joi in ir_entries:
            continue                        # same key — no drift
        sets = ent["sets"]
        if any(s != sets[0] for s in sets):
            continue                        # same key from different selectors
        s_j = sets[0]
        if not s_j:
            g.mistargets.append(f"{key_joi}: selector resolves to NO device")
            continue
        cands = [k for k, e in ir_entries.items()
                 if e["attr"] == ent["attr"] and s_j <= e["set"] and e["set"]]
        if len(cands) == 1:
            g.alias[key_joi] = cands[0]
            g.reverse.setdefault(cands[0], []).append(key_joi)
        elif not cands:
            same_attr = [k for k, e in ir_entries.items() if e["attr"] == ent["attr"]]
            if same_attr:
                g.mistargets.append(
                    f"{key_joi} (devices {sorted(s_j)}) targets none of "
                    f"{same_attr} — disjoint device sets")
        # >1 candidates: ambiguous — leave keys separate (sound)
    return g
