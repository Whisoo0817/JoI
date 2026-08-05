"""Stage ④ — binding decisions: who fills each role in *this* home, or what
happens instead (M-C ②③④).

For every role of a template, against a concrete inventory:

    keep          the base device type is present (and online) in scope — no edit
    substitute    another present type satisfies the full role contract with the
                  skeleton's own members — pure ReplaceSelector edits (drop-in)
    realize       another present type has a **certified realization** of every
                  composite the role uses — selector + member/argument edits
                  produced from the realization sequences (compile-time adapter;
                  the deployed code contains only concrete calls)
    drop_feature  optional role unavailable — its feature is removed (edit
                  generation for the slice is stage ⑤/M-D; here it is a decision)
    abort         essential role unavailable or only unsound candidates exist

Candidate enumeration is two-axis (the SoPIoT lineage, completed):
    capability(d) ⊨ role contract   ∧   space(d) ⊨ spatial constraint
Sensors/actuators default to `same_space` — a living-room AC cannot close the
loop on a bedroom thermometer; notifiers default to `anywhere`.

Everything here is deterministic. The LLM's seat (choosing among several sound
candidates, proposing degrade designs) plugs in *between* enumeration and edit
generation; it never authors code and can never widen the candidate set.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from .effects import load_profiles
from .inventory import DeviceInstance, Inventory
from .patch import Edit, replace_argument, replace_member, replace_tag
from .structure import DeviceRef, Structure
from .template import (RoleContract, Source, Template, Violation, base_binding,
                       check_role, refs_for_role)

_HERE = os.path.dirname(os.path.abspath(__file__))
COMPOSITES_PATH = os.path.join(_HERE, "composites.json")


# ── composite registry ───────────────────────────────────────────────────────

@dataclass
class Realization:
    device_type: str
    certified: bool
    sequence: list[dict]              # [{member, args}]


@dataclass
class Composite:
    id: str
    params: list[str]
    contract: str
    stop: Optional[str]
    realizations: dict[str, Realization]


def load_composites(path: str = COMPOSITES_PATH) -> dict[str, Composite]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out: dict[str, Composite] = {}
    for cid, body in raw.items():
        if cid.startswith("_"):
            continue
        if not body.get("contract"):
            raise ValueError(f"composite {cid}: schema forbids a missing contract")
        out[cid] = Composite(
            id=cid, params=body.get("params", []), contract=body["contract"],
            stop=body.get("stop"),
            realizations={svc: Realization(svc, r.get("certified", False), r["sequence"])
                          for svc, r in body.get("realizations", {}).items()})
    return out


def composites_of(role: RoleContract, source: Source,
                  registry: dict[str, Composite]) -> list[Composite]:
    """Composites whose realization for the source's device type is exactly a
    subsequence of the members this role uses in the skeleton. This grounds the
    role→composite mapping in the code rather than in extra annotation."""
    base_type = source.tags[0] if source.tags else ""
    used = {m.split(".", 1)[-1].lower() for m in source.members}
    used |= {m.split(".", 1)[-1].lower() for m in role.requires.members}
    out = []
    for c in registry.values():
        r = c.realizations.get(base_type)
        if r is None:
            continue
        seq_members = {_canon_member(s["member"]) for s in r.sequence}
        if seq_members and seq_members.issubset(used | {"on", "off", "toggle"}):
            out.append(c)
    return out


def _canon_member(member: str) -> str:
    m = member.lower()
    return m.split("_", 1)[-1] if "_" in m else m


# ── spatial defaults ─────────────────────────────────────────────────────────

def spatial_mode(role: RoleContract) -> str:
    kind = role.requires.kind
    if kind in ("sensor", "actuator"):
        return "same_space"
    return "anywhere"


# ── decisions ────────────────────────────────────────────────────────────────

@dataclass
class Decision:
    role: str
    source_tags: list[str]
    action: str                        # keep | substitute | realize | drop_feature | abort
    device: Optional[DeviceInstance] = None
    edits: list[Edit] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    rationale: str = ""
    needs_llm_choice: bool = False     # >1 sound candidate: the model may pick, never widen


@dataclass
class BindReport:
    template: str
    inventory: str
    scope: Optional[str]
    decisions: list[Decision]

    @property
    def verdict(self) -> str:
        if any(d.action == "abort" for d in self.decisions):
            return "abort"
        if any(d.action in ("drop_feature", "realize") for d in self.decisions):
            return "degrade" if any(d.action == "drop_feature" for d in self.decisions) else "ok"
        return "ok"

    @property
    def edits(self) -> list[Edit]:
        return [e for d in self.decisions for e in d.edits]

    def show(self) -> str:
        lines = [f"# bind {self.template} @ {self.inventory} (scope={self.scope}) -> {self.verdict.upper()}"]
        for d in self.decisions:
            dev = f" -> {d.device.type}[{d.device.id}]" if d.device else ""
            lines.append(f"  {d.role:<18} {d.action:<12}{dev}  {d.rationale}")
            for v in d.violations[:3]:
                lines.append(f"      [{v.severity}] ({v.fault_class}) {v.detail}")
        return "\n".join(lines)


def _sound(contract: RoleContract, svc: str, source: Source) -> tuple[bool, list[Violation]]:
    vs = check_role(contract, svc, source=source)
    return (not any(v.severity == "blocking" for v in vs)), vs


def _realization_edits(st: Structure, contract: RoleContract, source: Source,
                       old: Realization, new: Realization,
                       new_type: str) -> Optional[list[Edit]]:
    """Selector + member/arg edits turning the old realization's calls into the
    new one. v0 handles equal-length sequences (positional mapping); anything
    needing insertion or deletion escalates (returns None -> fail closed)."""
    if len(old.sequence) != len(new.sequence):
        return None
    all_refs = refs_for_role(st, contract, source=source)
    calls = [d for d in all_refs if d.kind == "call"]
    order = {_canon_member(s["member"]): i for i, s in enumerate(old.sequence)}
    seq_refs: list[Optional[DeviceRef]] = [None] * len(old.sequence)
    for r in calls:
        i = order.get(_canon_member(r.member))
        if i is not None and seq_refs[i] is None:
            seq_refs[i] = r
    if any(r is None for r in seq_refs):
        return None

    edits: list[Edit] = []
    for r, new_step in zip(seq_refs, new.sequence):
        assert r is not None
        edits.extend(replace_tag(st, source.tags[0], new_type, only_refs=[r]))
        if _canon_member(r.member) != _canon_member(new_step["member"]):
            edits.append(replace_member(r, new_step["member"]))
        for i, arg in enumerate(new_step.get("args", [])):
            if arg.startswith("{"):
                continue               # keep the skeleton's expression for parameters
            if r.args is not None and i < len(r.args):
                edits.append(replace_argument(r, i, arg))

    # Refs outside the sequence (the composite's stop(), power-state reads, ...)
    # must move to the new device too, or they would dangle on the dead one.
    # Only the shared switch capability is portable by construction; anything
    # else outside the certified sequence is unsound to carry over -> fail closed.
    covered = {id(r) for r in seq_refs}
    for r in all_refs:
        if id(r) in covered:
            continue
        if not r.key.startswith("switch."):
            return None
        edits.extend(replace_tag(st, source.tags[0], new_type, only_refs=[r]))
    return edits


def bind(t: Template, st: Structure, inv: Inventory, *,
         scope: Optional[str] = None,
         registry: Optional[dict[str, Composite]] = None) -> BindReport:
    """Deterministic binding decisions for every role source."""
    registry = registry if registry is not None else load_composites()
    profiles = load_profiles()
    decisions: list[Decision] = []

    scope_param = next((p for p in t.params if p.kind == "scope_tag"), None)
    scope = scope if scope is not None else (scope_param.base_value if scope_param else None)

    for contract in t.roles:
        if contract.requires.kind in ("namespace", "infrastructure"):
            decisions.append(Decision(contract.role, contract.base_tags, "keep",
                                      rationale=f"{contract.requires.kind}: not a bindable device"))
            continue

        per_source: list[Decision] = []
        for source in contract.sources:
            base_type = source.tags[0]
            instance_tags = [tag for tag in source.tags[1:]
                             if inv.classify_tag(tag) == "instance"]
            mode = spatial_mode(contract)

            present = inv.candidates(base_type, space=scope, spatial=mode,
                                     instance_tags=instance_tags)
            if present:
                per_source.append(Decision(contract.role, source.tags, "keep",
                                           device=present[0],
                                           rationale=f"{base_type} present in scope"))
                continue

            # base type missing: try drop-in substitution among present types
            subs: list[tuple[DeviceInstance, list[Violation]]] = []
            for cand_type in sorted(inv.types_present()):
                if cand_type == base_type or cand_type not in profiles:
                    continue
                ok, vs = _sound(contract, cand_type, source)
                if not ok:
                    continue
                for d in inv.candidates(cand_type, space=scope, spatial=mode,
                                        instance_tags=instance_tags):
                    subs.append((d, vs))
            if subs:
                dev, vs = subs[0]
                edits = replace_tag(st, base_type, dev.type,
                                    only_refs=refs_for_role(st, contract, source=source))
                per_source.append(Decision(contract.role, source.tags, "substitute",
                                           device=dev, edits=edits, violations=vs,
                                           rationale=f"drop-in: {dev.type} satisfies the full contract",
                                           needs_llm_choice=len(subs) > 1))
                continue

            # composite path: certified realization swap
            needed = composites_of(contract, source, registry)
            real_choice: Optional[tuple[DeviceInstance, list[Edit]]] = None
            if needed:
                for cand_type in sorted(inv.types_present()):
                    if cand_type == base_type:
                        continue
                    reals = [c.realizations.get(cand_type) for c in needed]
                    if any(r is None or not r.certified for r in reals):
                        continue      # uncertified realization -> fail closed
                    cands = inv.candidates(cand_type, space=scope, spatial=mode,
                                           instance_tags=instance_tags)
                    if not cands:
                        continue
                    all_edits: list[Edit] = []
                    feasible = True
                    for c, new_r in zip(needed, reals):
                        old_r = c.realizations[base_type]
                        es = _realization_edits(st, contract, source, old_r, new_r, cand_type)
                        if es is None:
                            feasible = False
                            break
                        all_edits.extend(es)
                    if feasible:
                        real_choice = (cands[0], all_edits)
                        break
            if real_choice is not None:
                dev, edits = real_choice
                per_source.append(Decision(contract.role, source.tags, "realize",
                                           device=dev, edits=edits,
                                           rationale=f"certified realization swap -> {dev.type} "
                                                     f"({', '.join(c.id for c in needed)})"))
                continue

            # nothing sound: the role source is unavailable
            vs = check_role(contract, None)
            action = "abort" if contract.on_unavailable == "abort" else "drop_feature"
            per_source.append(Decision(contract.role, source.tags, action, violations=vs,
                                       rationale=f"no sound candidate; on_unavailable={contract.on_unavailable}"))

        # combine sources: one_or_more roles survive on any healthy source
        healthy = [d for d in per_source if d.action in ("keep", "substitute", "realize")]
        if healthy and contract.cardinality in ("one_or_more", "zero_or_more"):
            for d in per_source:
                if d.action == "abort":
                    d.action = "drop_feature"
                    d.rationale += " (covered by a surviving source)"
            decisions.extend(per_source)
        else:
            decisions.extend(per_source)

    return BindReport(template=t.id, inventory=inv.name, scope=scope, decisions=decisions)
