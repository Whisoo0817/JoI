"""Stage ⑤ — typed edits applied as byte-span splices.

Design lock (ideas.md §9): the adapted program is *never re-emitted*. Every edit
names a char span of the original source and its replacement text; everything
outside those spans is copied verbatim. Two consequences:

* **L1 holds by construction.** Untouched code is byte-identical, so behaviour
  outside the edit footprint needs no proof (3-region model, region ②).
* **The model never copies code.** Stage ④ emits decisions; this module turns a
  decision into spans. That removes the "long-code copy fidelity" failure mode
  that baselines B3/B4 (whole-file / diff LLM editing) are exposed to.

`verify_splice` re-derives the invariant independently of `apply_edits` so the
check is not a tautology: it walks both strings and compares the complement of
the edit footprints byte by byte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from .structure import DeviceRef, Span, Structure, extract, parse_errors

# Closed operator set (guardrail 2 of the NL lock). Anything outside fails closed.
EDIT_OPS = (
    "ReplaceSelector",     # swap tags of a device reference
    "ReplaceArgument",     # change one call argument
    "ModifyPredicate",     # change a guard threshold / comparator
    "ChangeDelay",         # change a delay constant
    "ReplaceMember",       # swap the invoked method / attribute
    "DeleteSpan",          # remove a statement or block (drop)
    "InsertBefore",        # insert text at a point (latch, guard)
)


@dataclass(frozen=True)
class Edit:
    span: Span
    new_text: str
    op: str = "ReplaceSelector"
    label: str = ""

    def __post_init__(self) -> None:
        if self.op not in EDIT_OPS:
            raise ValueError(f"unknown edit op {self.op!r}; closed set = {EDIT_OPS}")


class EditConflict(ValueError):
    """Two edits overlap — refuse rather than guess an order (fail closed)."""


def _sorted_disjoint(edits: Sequence[Edit]) -> list[Edit]:
    ordered = sorted(edits, key=lambda e: (e.span.start, e.span.end))
    for a, b in zip(ordered, ordered[1:]):
        if a.span.overlaps(b.span) or (a.span.end > b.span.start):
            raise EditConflict(f"overlapping edits: {a.label or a.op} {a.span} vs {b.label or b.op} {b.span}")
    return ordered


def apply_edits(src: str, edits: Sequence[Edit]) -> str:
    """Splice `edits` into `src`. Raises EditConflict on overlap."""
    out: list[str] = []
    cursor = 0
    for e in _sorted_disjoint(edits):
        if e.span.start < cursor or e.span.end > len(src):
            raise EditConflict(f"edit out of range: {e.span}")
        out.append(src[cursor:e.span.start])
        out.append(e.new_text)
        cursor = e.span.end
    out.append(src[cursor:])
    return "".join(out)


@dataclass
class SpliceReport:
    ok: bool
    checked_regions: int
    kept_chars: int
    changed_chars: int
    first_mismatch: Optional[tuple[int, int]] = None
    detail: str = ""


def verify_splice(src: str, out: str, edits: Sequence[Edit]) -> SpliceReport:
    """L1 check: every byte *outside* the edit footprints is unchanged.

    Independent of `apply_edits`: walks the complement regions of both strings
    and compares them directly, tracking the running offset shift.
    """
    ordered = _sorted_disjoint(edits)
    shift = 0
    src_cursor = 0
    kept = 0
    changed = 0
    regions = 0
    for e in ordered:
        a, b = src[src_cursor:e.span.start], out[src_cursor + shift:e.span.start + shift]
        regions += 1
        if a != b:
            for i, (ca, cb) in enumerate(zip(a, b)):
                if ca != cb:
                    return SpliceReport(False, regions, kept, changed,
                                        (src_cursor + i, src_cursor + shift + i),
                                        f"preserved region diff: {a[max(0,i-20):i+20]!r} vs {b[max(0,i-20):i+20]!r}")
            return SpliceReport(False, regions, kept, changed, (src_cursor, src_cursor + shift),
                                "preserved region length mismatch")
        kept += len(a)
        replaced = out[e.span.start + shift:e.span.start + shift + len(e.new_text)]
        if replaced != e.new_text:
            return SpliceReport(False, regions, kept, changed, (e.span.start, e.span.start + shift),
                                f"edit text not present: expected {e.new_text!r}, found {replaced!r}")
        changed += len(e.new_text)
        shift += len(e.new_text) - len(e.span)
        src_cursor = e.span.end

    tail_a, tail_b = src[src_cursor:], out[src_cursor + shift:]
    regions += 1
    if tail_a != tail_b:
        return SpliceReport(False, regions, kept, changed, (src_cursor, src_cursor + shift),
                            "trailing region differs")
    kept += len(tail_a)
    return SpliceReport(True, regions, kept, changed)


# ── typed edit builders ──────────────────────────────────────────────────────

def replace_tag(st: Structure, old: str, new: str, *,
                only_refs: Optional[Iterable[DeviceRef]] = None) -> list[Edit]:
    """ReplaceSelector: rename tag `old` -> `new` at every occurrence (or a subset)."""
    scope = list(only_refs) if only_refs is not None else st.devices
    edits: list[Edit] = []
    for d in scope:
        for tag, sp in zip(d.tags, d.tag_spans):
            if tag == old:
                edits.append(Edit(sp, f"#{new}", "ReplaceSelector",
                                  f"#{old}->#{new} @L{d.line}"))
    return edits


def replace_selector(ref: DeviceRef, tags: Sequence[str]) -> Edit:
    """ReplaceSelector: rewrite the whole tag list of one reference."""
    return Edit(ref.taglist_span, " ".join(f"#{t}" for t in tags), "ReplaceSelector",
                f"selector @L{ref.line}")


def replace_member(ref: DeviceRef, member: str) -> Edit:
    return Edit(ref.member_span, member, "ReplaceMember", f"{ref.member}->{member} @L{ref.line}")


def replace_argument(ref: DeviceRef, index: int, text: str) -> Edit:
    if ref.args is None or index >= len(ref.args):
        raise EditConflict(f"argument {index} absent on {ref.key} @L{ref.line}")
    return Edit(ref.args[index].span, text, "ReplaceArgument",
                f"{ref.key} arg{index} @L{ref.line}")


def modify_threshold(st: Structure, *, line: int, new_value: str,
                     side: str = "rhs") -> list[Edit]:
    """ModifyPredicate: retarget the constant of guard atoms on `line`."""
    edits: list[Edit] = []
    for g in st.guards:
        if g.line != line or g.op is None:
            continue
        span = g.rhs_span if side == "rhs" else g.lhs_span
        if span is None:
            continue
        edits.append(Edit(span, new_value, "ModifyPredicate", f"guard@L{line} {side}"))
    return edits


def change_delay(st: Structure, *, line: int, ms: int) -> list[Edit]:
    out: list[Edit] = []
    for t in st.times:
        if t.line == line:
            out.append(Edit(t.span, f"{ms} MSEC", "ChangeDelay", f"delay@L{line}"))
    return out


def delete_span(span: Span, label: str = "") -> Edit:
    return Edit(span, "", "DeleteSpan", label or "delete")


def insert_before(pos: int, text: str, label: str = "") -> Edit:
    return Edit(Span(pos, pos), text, "InsertBefore", label or "insert")


# ── one-call adaptation with the L0/L1 gates ────────────────────────────────

@dataclass
class PatchResult:
    ok: bool
    source: str
    output: str
    edits: list[Edit]
    splice: SpliceReport
    syntax_errors: list[str] = field(default_factory=list)
    structure_after: Optional[Structure] = None

    @property
    def summary(self) -> str:
        state = "OK" if self.ok else "REJECT"
        return (f"{state}: {len(self.edits)} edits, "
                f"{self.splice.kept_chars} chars preserved / {self.splice.changed_chars} written"
                + ("" if self.ok else f"; syntax={self.syntax_errors[:2]} splice={self.splice.detail}"))


def apply_and_check(st: Structure, edits: Sequence[Edit]) -> PatchResult:
    """Apply edits, then run the two cheap gates: L0 syntax, L1 splice invariant.

    Fails closed: any syntax error or preserved-region mismatch marks the patch
    rejected, with the original source left untouched by the caller's choice.
    """
    out = apply_edits(st.src, edits)
    splice = verify_splice(st.src, out, edits)
    errs = parse_errors(out) if out.strip() else []
    after = extract(out, st.name + "'") if not errs else None
    return PatchResult(ok=(splice.ok and not errs), source=st.src, output=out,
                       edits=list(edits), splice=splice, syntax_errors=errs,
                       structure_after=after)
