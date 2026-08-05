"""Stage ⑤b — feature drop as deletion edits (M-D).

Turns a `drop_feature` decision into DeleteSpan edits by computing the dropped
role's dependency cone over the skeleton:

    seeds          every device reference of the dropped role sources
    tainted vars   variables fed (directly or transitively) from seed reads
    units          whole statements/blocks to remove:
                     - a seed call statement -> its line
                     - a seed iter           -> its whole for-statement
                     - an if whose guard reads a seed or a tainted var -> the
                       whole if-statement (header + body)

Safety rules (all violations escalate -> None, fail closed, never a bad edit):

* **no live actuation inside** — a control-tainted block may only contain calls
  of dropped roles or of notifier-kind roles (a toast announcing an action that
  no longer happens must go with it); any other actuator call inside aborts the
  plan.
* **no else-branches** (v0) — deleting one arm of an if/else changes the other
  arm's reachability; escalate.
* **no undefined survivors** — a variable written inside a deleted unit and read
  outside it must also be written outside, or the survivor code would read an
  undefined name.

Deletions are whole-line spans, so the splice invariant (L1) and the grammar's
non-empty-block rule are both respected; dead seeds left at the top (e.g. an
unused cooldown constant) are harmless by construction and intentionally kept —
deleting less is the safe direction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .patch import Edit, delete_span
from .structure import Block, DeviceRef, Span, Structure
from .template import RoleContract, Template, refs_for_role


@dataclass
class DropPlan:
    ok: bool
    roles: list[str]
    edits: list[Edit] = field(default_factory=list)
    units: list[Span] = field(default_factory=list)
    tainted_vars: set[str] = field(default_factory=set)
    reason: str = ""                   # why escalated, when not ok


# ── helpers ──────────────────────────────────────────────────────────────────

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _line_span(src: str, span: Span) -> Span:
    start = src.rfind("\n", 0, span.start) + 1
    end = src.find("\n", span.end - 1)
    end = len(src) if end == -1 else end + 1
    return Span(start, end)


def _block_unit(st: Structure, block: Block) -> Optional[Span]:
    """Whole if/for statement: header through body end, as full lines.
    Escalates (None) when an else follows — v0 does not split if/else."""
    if block.header_span is None:
        return None
    unit = Span(block.header_span.start, block.span.end)
    tail = st.src[unit.end:unit.end + 16].lstrip()
    if tail.startswith("else"):
        return None
    # an else-block's own deletion would strand its if; likewise escalate
    if block.kind == "else":
        return None
    return _line_span(st.src, unit)


def _vars_in(text: str) -> set[str]:
    return set(_WORD.findall(text))


# ── the planner ──────────────────────────────────────────────────────────────

def plan_drop_source(t: Template, st: Structure, role: str, source_idx: int) -> DropPlan:
    """Drop ONE source of a multi-source role (the dead sensor's for-loop) while
    the surviving sources keep the role alive. Not an essential loss: the role
    stays bound, so the essential guard does not apply — but only when another
    source actually survives, which the caller (stage ④/⑦) has established."""
    import copy
    contract = t.role(role)
    if len(contract.sources) <= 1:
        return DropPlan(False, [role], reason="single-source role — use plan_drop (role-level)")
    r2 = copy.deepcopy(contract)
    r2.sources = [contract.sources[source_idx]]
    r2.essential = False
    t2 = copy.deepcopy(t)
    t2.roles = [r2 if r.role == role else r for r in t2.roles]
    plan = plan_drop(t2, st, [role])
    plan.roles = [f"{role}[src{source_idx}]"]
    return plan


def plan_drop(t: Template, st: Structure, drop_roles: list[str]) -> DropPlan:
    dropped = [t.role(r) for r in drop_roles]

    # An essential role is never dropped — its loss is the abort path (stage ④).
    # Deleting it would leave a structurally fine but purpose-dead program (R1).
    ess = [r.role for r in dropped if r.essential]
    if ess:
        return DropPlan(False, drop_roles,
                        reason=f"essential role(s) {ess} cannot be dropped — abort, not degrade")

    # ref -> owning role, for every role in the template
    owner: dict[int, RoleContract] = {}
    for r in t.roles:
        for ref in refs_for_role(st, r):
            owner.setdefault(id(ref), r)

    seeds: list[DeviceRef] = []
    for r in dropped:
        seeds.extend(refs_for_role(st, r))
    if not seeds:
        return DropPlan(False, drop_roles, reason="no references found for dropped roles")
    seed_ids = {id(x) for x in seeds}

    # 1) tainted variables: assignments fed from seed reads, then transitively
    tainted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for a in st.assigns:
            if a.name in tainted:
                continue
            rhs_text = a.rhs_span.slice(st.src)
            feeds = any(a.rhs_span.start <= s.span.start and s.span.end <= a.rhs_span.end
                        for s in seeds)
            feeds = feeds or bool(_vars_in(rhs_text) & tainted)
            if feeds:
                tainted.add(a.name)
                changed = True

    # 2) control-tainted blocks: guard mentions a seed ref or a tainted var
    tainted_blocks: list[Block] = []
    for b in st.blocks.values():
        if b.header_span is None:
            continue
        header_text = b.header_span.slice(st.src)
        by_ref = any(b.header_span.start <= s.span.start and s.span.end <= b.header_span.end
                     for s in seeds)
        by_var = bool(_vars_in(header_text) & tainted)
        if by_ref or by_var:
            tainted_blocks.append(b)

    # keep outermost tainted blocks only
    outer: list[Block] = []
    for b in tainted_blocks:
        if not any(o.span.start <= b.span.start and b.span.end <= o.span.end
                   for o in tainted_blocks if o.id != b.id):
            outer.append(b)

    units: list[Span] = []
    dropped_names = {r.role for r in dropped}

    # 3) block units, with the no-live-actuation rule
    def _inner_ids(b: Block) -> set[str]:
        ids, stack = {b.id}, [b.id]
        while stack:
            for ch in st.blocks[stack.pop()].children:
                ids.add(ch)
                stack.append(ch)
        return ids

    for b in outer:
        inner = _inner_ids(b)
        for d in st.devices:
            if d.block not in inner or d.kind != "call":
                continue
            own = owner.get(id(d))
            if own is None:
                return DropPlan(False, drop_roles,
                                reason=f"unclaimed call inside tainted block @L{d.line}")
            if own.role not in dropped_names and own.requires.kind != "notifier":
                return DropPlan(False, drop_roles,
                                reason=f"live {own.role} call inside tainted block @L{d.line} "
                                       f"— cannot cleanly drop")
        u = _block_unit(st, b)
        if u is None:
            return DropPlan(False, drop_roles,
                            reason=f"tainted block {b.id}@L{b.line} has an else arm (v0 escalates)")
        units.append(u)

    # 4) remaining seeds outside those blocks: statement-level units
    covered = lambda sp: any(u.start <= sp.start and sp.end <= u.end for u in units)  # noqa: E731
    for s in seeds:
        if covered(s.span):
            continue
        if s.kind == "iter":
            blk = next((b for b in st.blocks.values()
                        if b.header_span is not None
                        and b.header_span.start <= s.span.start <= b.header_span.end), None)
            u = _block_unit(st, blk) if blk is not None else None
            if u is None:
                return DropPlan(False, drop_roles,
                                reason=f"iter seed @L{s.line} without deletable for-block")
        elif s.kind == "call":
            u = _line_span(st.src, s.span)
        else:
            # A read seed feeding an assignment (`now = (#Clock).timestamp`): the
            # assignment line goes too. Whether its variable is still read by
            # surviving code is exactly rule 5's job — if it is, the plan is
            # refused there with the precise reader named.
            host = next((a for a in st.assigns
                         if a.rhs_span.start <= s.span.start and s.span.end <= a.rhs_span.end), None)
            if host is None:
                return DropPlan(False, drop_roles,
                                reason=f"read seed @L{s.line} outside any tainted guard "
                                       f"— its consumer survives, cannot drop cleanly")
            u = _line_span(st.src, host.span)
        if not covered(u):
            units.append(u)

    # merge overlapping units (outermost wins)
    units.sort()
    merged: list[Span] = []
    for u in units:
        if merged and u.start < merged[-1].end:
            merged[-1] = Span(merged[-1].start, max(merged[-1].end, u.end))
        else:
            merged.append(u)

    # 5) no-undefined-survivors rule.
    # Writes include call-assignments (`video = (#Camera).captureVideo(...)`) —
    # those live in st.devices, not st.assigns; missing them would let a
    # camera-only drop leave the email reading an undefined `video`.
    in_units = lambda sp: any(u.start <= sp.start and sp.end <= u.end for u in merged)  # noqa: E731
    writes: list[tuple[str, Span]] = [(a.name, a.span) for a in st.assigns]
    writes += [(d.assigns_to, d.span) for d in st.devices if d.assigns_to]

    def _read_outside(name: str) -> Optional[str]:
        for g in st.guards:
            if not in_units(g.span) and name in _vars_in(g.text):
                return f"guard @L{g.line}"
        for o in st.assigns:
            if not in_units(o.span) and name in _vars_in(o.rhs_span.slice(st.src)):
                return f"assignment @L{o.line}"
        for d in st.devices:
            if in_units(d.span) or not d.args:
                continue
            if any(name in _vars_in(arg.text) for arg in d.args):
                return f"call argument @L{d.line}"
        return None

    for name, span in writes:
        if not in_units(span):
            continue
        if any(n == name and not in_units(sp) for n, sp in writes):
            continue
        where = _read_outside(name)
        if where:
            return DropPlan(False, drop_roles,
                            reason=f"{name} written only in dropped code but read "
                                   f"by surviving {where}")

    edits = [delete_span(u, f"drop {'/'.join(drop_roles)}") for u in merged]
    return DropPlan(True, drop_roles, edits=edits, units=merged, tainted_vars=tainted)
