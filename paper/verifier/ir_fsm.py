"""IR-FSM derivation (paper §6.4 V1).

Translates a validated Timeline IR into an explicit list of *transition
obligations* — small, checkable assertions that any correct lowering must
satisfy at runtime. L2 (l2_runtime) consumes this list by streaming a JoI
trace through it; L1 (l1_static) consults it for catalog/structural checks.

Design points:
- Each IR op contributes one or more `Obligation`s tagged with a source path
  (e.g., `timeline[2].then[0]`) so downstream diagnosis can point at the
  exact IR feature responsible for any violation.
- Obligations form a DAG via `id` references in `after`. Sequencing is
  encoded as `after=[prev_id]`; branch activation is encoded via `guard`
  (a cond string carrying the branch context); re-arming is captured by
  `CycleObligation` containing nested obligations.
- Cron is *not* unrolled into per-occurrence obligations here — that would
  bloat the FSM. Instead we mark top-level `start_at(cron)` as a recurring
  scope; the runtime checker is responsible for matching each cron fire.

This module is purely deterministic. It does NOT call the LLM, simulate, or
read catalogs. It accepts an IR dict already passing `validate_ir`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from paper.timeline_ir import parse_duration_to_ms


# ── Obligation kinds ────────────────────────────────────────────────────────

@dataclass
class Obligation:
    """Base obligation. Subclasses carry kind-specific payload."""
    id: int
    kind: str
    path: str
    after: list[int] = field(default_factory=list)
    guard: Optional[str] = None  # active-branch cond from enclosing `if`


@dataclass
class CallObligation(Obligation):
    target: str = ""
    args: dict = field(default_factory=dict)


@dataclass
class WaitObligation(Obligation):
    cond: str = ""
    edge: str = "none"
    # Sustain duration (ms). 0 = no sustain requirement. When > 0, cond must
    # remain true CONTINUOUSLY for `for_ms` after the (post-edge if edge!=none,
    # otherwise immediate) cond-true point. Lowering must reset its timer on
    # cond-flip; a `delay`-style lowering fails the flap scenario.
    for_ms: int = 0


@dataclass
class DelayObligation(Obligation):
    ms: int = 0


@dataclass
class ReadObligation(Obligation):
    var: str = ""
    src: str = ""


@dataclass
class CycleObligation(Obligation):
    period_ms: int = 0
    until: Optional[str] = None
    body: list[Obligation] = field(default_factory=list)


@dataclass
class IfObligation(Obligation):
    cond: str = ""
    then_body: list[Obligation] = field(default_factory=list)
    else_body: list[Obligation] = field(default_factory=list)


@dataclass
class BreakObligation(Obligation):
    pass


# ── FSM container ───────────────────────────────────────────────────────────

@dataclass
class IRFSM:
    """Derived FSM. `top` is the flat top-level obligation list (in timeline
    order). `anchor` captures the start_at semantics (now / cron string).
    `recurring` is True iff the top-level start is cron (every-fire body)."""
    anchor: str  # "now" | "cron"
    cron: Optional[str]
    recurring: bool
    top: list[Obligation]

    def all_obligations(self) -> list[Obligation]:
        """Flatten nested obligations (into cycle/if bodies) for L1 walks."""
        out: list[Obligation] = []
        _flatten(self.top, out)
        return out


def _flatten(items: list[Obligation], out: list[Obligation]) -> None:
    for ob in items:
        out.append(ob)
        if isinstance(ob, CycleObligation):
            _flatten(ob.body, out)
        elif isinstance(ob, IfObligation):
            _flatten(ob.then_body, out)
            _flatten(ob.else_body, out)


# ── Derivation ──────────────────────────────────────────────────────────────

class _IdGen:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> int:
        self._n += 1
        return self._n


def derive_fsm(ir: dict) -> IRFSM:
    """Build an `IRFSM` from a validated Timeline IR.

    Caller must have run `validate_ir(ir)` first. Reject-path IRs
    (`{"error": ...}`) yield an empty FSM with anchor='now'.
    """
    if not isinstance(ir, dict) or "timeline" not in ir or "error" in ir:
        return IRFSM(anchor="now", cron=None, recurring=False, top=[])

    timeline = ir["timeline"]
    first = timeline[0] if timeline else {}
    anchor = first.get("anchor", "now")
    cron = first.get("cron") if anchor == "cron" else None
    recurring = anchor == "cron"

    idg = _IdGen()
    top = _lower_steps(timeline[1:], idg, path="timeline", prev_ids=[], guard=None)
    return IRFSM(anchor=anchor, cron=cron, recurring=recurring, top=top)


def _lower_steps(
    steps: list,
    idg: _IdGen,
    path: str,
    prev_ids: list[int],
    guard: Optional[str],
) -> list[Obligation]:
    out: list[Obligation] = []
    last_ids = list(prev_ids)
    for i, s in enumerate(steps):
        sp = f"{path}[{i}]"
        op = s.get("op")
        ob: Optional[Obligation] = None
        if op == "call":
            ob = CallObligation(
                id=idg.next(), kind="call", path=sp, after=last_ids, guard=guard,
                target=s.get("target", ""), args=dict(s.get("args") or {}),
            )
        elif op == "wait":
            for_str = s.get("for")
            for_ms = parse_duration_to_ms(for_str) if for_str else 0
            ob = WaitObligation(
                id=idg.next(), kind="wait", path=sp, after=last_ids, guard=guard,
                cond=s.get("cond", ""), edge=s.get("edge", "none"),
                for_ms=for_ms,
            )
        elif op == "delay":
            ob = DelayObligation(
                id=idg.next(), kind="delay", path=sp, after=last_ids, guard=guard,
                ms=parse_duration_to_ms(s.get("duration", "0 MSEC")),
            )
        elif op == "read":
            ob = ReadObligation(
                id=idg.next(), kind="read", path=sp, after=last_ids, guard=guard,
                var=s.get("var", ""), src=s.get("src", ""),
            )
        elif op == "break":
            ob = BreakObligation(
                id=idg.next(), kind="break", path=sp, after=last_ids, guard=guard,
            )
        elif op == "if":
            cond = s.get("cond", "")
            then_g = cond
            else_g = f"!({cond})"
            then_body = _lower_steps(s.get("then", []) or [], idg, f"{sp}.then",
                                     prev_ids=last_ids, guard=_and(guard, then_g))
            else_body = _lower_steps(s.get("else", []) or [], idg, f"{sp}.else",
                                     prev_ids=last_ids, guard=_and(guard, else_g))
            ob = IfObligation(
                id=idg.next(), kind="if", path=sp, after=last_ids, guard=guard,
                cond=cond, then_body=then_body, else_body=else_body,
            )
        elif op == "cycle":
            period_ms = parse_duration_to_ms(s.get("period", "100 MSEC"))
            body = _lower_steps(s.get("body", []) or [], idg, f"{sp}.body",
                                prev_ids=[], guard=guard)
            ob = CycleObligation(
                id=idg.next(), kind="cycle", path=sp, after=last_ids, guard=guard,
                period_ms=period_ms, until=s.get("until"), body=body,
            )
        else:
            continue  # unknown ops were rejected by validate_ir

        out.append(ob)
        last_ids = [ob.id]
    return out


def _and(g1: Optional[str], g2: str) -> str:
    if not g1:
        return g2
    return f"({g1}) && ({g2})"


# ── Debug rendering ─────────────────────────────────────────────────────────

def render_fsm(fsm: IRFSM) -> str:
    """One-line-per-obligation dump for debugging / paper figures."""
    lines = [f"# IR-FSM anchor={fsm.anchor} cron={fsm.cron!r} recurring={fsm.recurring}"]
    _render(fsm.top, lines, indent=0)
    return "\n".join(lines)


def _render(items: list[Obligation], out: list[str], indent: int) -> None:
    pad = "  " * indent
    for ob in items:
        head = f"{pad}#{ob.id} {ob.kind} @ {ob.path}"
        if ob.after:
            head += f"  after={ob.after}"
        if ob.guard:
            head += f"  guard={ob.guard!r}"
        if isinstance(ob, CallObligation):
            head += f"  target={ob.target} args={ob.args}"
        elif isinstance(ob, WaitObligation):
            head += f"  cond={ob.cond!r} edge={ob.edge}"
            if ob.for_ms > 0:
                head += f" for={ob.for_ms}ms"
        elif isinstance(ob, DelayObligation):
            head += f"  {ob.ms}ms"
        elif isinstance(ob, ReadObligation):
            head += f"  ${ob.var} := {ob.src}"
        elif isinstance(ob, IfObligation):
            head += f"  cond={ob.cond!r}"
        elif isinstance(ob, CycleObligation):
            head += f"  period={ob.period_ms}ms until={ob.until!r}"
        out.append(head)
        if isinstance(ob, CycleObligation):
            _render(ob.body, out, indent + 1)
        elif isinstance(ob, IfObligation):
            out.append(f"{pad}  then:")
            _render(ob.then_body, out, indent + 2)
            if ob.else_body:
                out.append(f"{pad}  else:")
                _render(ob.else_body, out, indent + 2)


if __name__ == "__main__":
    import json
    import sys
    from paper.timeline_ir import validate_ir
    ir = json.loads(sys.stdin.read())
    validate_ir(ir)
    fsm = derive_fsm(ir)
    print(render_fsm(fsm))
