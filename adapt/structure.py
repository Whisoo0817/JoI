"""Stage ① — structural extraction from JoI source.

Produces, for one scenario script:

* **role reference table** — every device selector use `(#A #B).member(args)`,
  with the char span of the whole expression, of the tag list, of each tag,
  of the member, and of each argument. This is what stage ⑤ edits.
* **block table** — the nesting tree (root / then / else / loop / for body) with
  one *signature* per block: state keys read, variables and GlobalVariable keys
  written, guard atoms, call keys, time constants. Blocks with equal signatures
  are candidates for the same role contract; a signature diff before/after an
  edit is the cheap (L2) conformance check.
* **assignments** — `:=` (persistent seed) vs `=`, with spans.
* **guard atoms**, **time constants**, **literals** — the parameter slots that
  value edits ("25도를 26도로") target.

Spans are half-open char offsets into the *original* source, so the patcher can
splice without re-emitting the program.

Parsing uses the ANTLR grammar (`parser/JOILang.g4`) rather than
`sim.joi_parser`: the generated parser carries token positions and already
covers the hand-written corpus syntax (`for`, `loop`, `all/any`, `==|`).
`sim.joi_parser` stays untouched as the SMT front end.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GENERATED = os.path.join(_REPO, "parser", "generated")
if _GENERATED not in sys.path:
    sys.path.insert(0, _GENERATED)

from antlr4 import CommonTokenStream, InputStream  # noqa: E402
from antlr4.error.ErrorListener import ErrorListener  # noqa: E402
from antlr4.tree.Tree import TerminalNode  # noqa: E402

from JOILangLexer import JOILangLexer  # noqa: E402
from JOILangParser import JOILangParser  # noqa: E402

if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
from sim.expr import canonical_key  # noqa: E402  (same convention as the SMT front end)

P = JOILangParser

TIME_UNIT_MS = {
    "MSEC": 1,
    "SEC": 1000,
    "MIN": 60_000,
    "HOUR": 3_600_000,
    "DAY": 86_400_000,
}

GV_TAG = "GlobalVariable"


# ── spans ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, order=True)
class Span:
    """Half-open char range [start, end) into the original source."""

    start: int
    end: int

    def slice(self, src: str) -> str:
        return src[self.start:self.end]

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end

    def __len__(self) -> int:  # noqa: D105
        return self.end - self.start


def _span(ctx) -> Span:
    return Span(ctx.start.start, ctx.stop.stop + 1)


def _tok_span(tok) -> Span:
    return Span(tok.start, tok.stop + 1)


def _term_span(node: TerminalNode) -> Span:
    return _tok_span(node.symbol)


# ── reference records ────────────────────────────────────────────────────────

@dataclass
class Arg:
    text: str
    span: Span


@dataclass
class DeviceRef:
    """One use of a device selector.

    kind: "call" (method with parens) | "read" (attribute) | "iter" (for-each source)
    """

    kind: str
    quantifier: Optional[str]          # "all" | "any" | None
    tags: tuple[str, ...]
    member: str
    args: Optional[list[Arg]]          # None for attribute reads
    span: Span
    quant_span: Optional[Span]
    taglist_span: Span                 # covers "#A #B" (inside the parens)
    tag_spans: tuple[Span, ...]
    member_span: Span
    block: str
    line: int
    assigns_to: Optional[str] = None   # `x = (#A).b()` -> "x"

    @property
    def service(self) -> str:
        """Tag most likely naming the device type.

        Only a heuristic for reporting (`#AirConditioner #Office` -> AirConditioner):
        the tag whose lowercase form prefixes the member name, else the first tag.
        **Not** used for keying — see `capability`.
        """
        for t in self.tags:
            if self.member.lower().startswith(t.lower()):
                return t
        return self.tags[0] if self.tags else "?"

    @property
    def capability(self) -> tuple[str, str]:
        """(capability, attribute) derived from the *member*, e.g.
        ``switch_on`` -> ``("switch", "on")``. Uses the simulator's
        `canonical_key`, so adapt and the SMT front end agree.

        Deliberately independent of the tags: which devices are bound is
        binding detail, what the code asks them to do is structure. That split
        is the thesis — structure is preserved by a re-binding; whether the new
        device *can* honour the capability is stage ④'s contract question.
        """
        return canonical_key(self.service, self.member)

    @property
    def key(self) -> str:
        cap, attr = self.capability
        return f"{cap}.{attr}"


@dataclass
class AssignRef:
    name: str
    op: str                            # ":=" | "="
    span: Span
    name_span: Span
    rhs_span: Span
    block: str
    line: int

    @property
    def persistent(self) -> bool:
        """`:=` runs once per scenario start (seed), `=` every tick."""
        return self.op == ":="


@dataclass
class GuardAtom:
    text: str
    span: Span
    lhs_span: Optional[Span]
    op: Optional[str]
    op_span: Optional[Span]
    rhs_span: Optional[Span]
    block: str
    line: int


@dataclass
class TimeConst:
    ms: int
    raw: str
    span: Span                         # whole `1000 MSEC`
    value_span: Span                   # just `1000`
    unit: str
    kind: str                          # "delay"
    block: str
    line: int


@dataclass
class Literal:
    text: str
    kind: str                          # int | double | string | bool
    span: Span
    context: str                       # guard | arg | assign | delay | other
    block: str
    line: int


@dataclass
class GVRef:
    """GlobalVariable access, keyed by its string literal argument."""

    kind: str                          # "get" | "set"
    key: Optional[str]
    key_span: Optional[Span]
    ref: DeviceRef


# ── blocks ───────────────────────────────────────────────────────────────────

@dataclass
class Block:
    id: str
    kind: str                          # root | then | else | loop | for
    span: Span
    header_span: Optional[Span]        # `if (...)`, `loop (...)`, `for (...)`
    parent: Optional[str]
    depth: int
    line: int
    children: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BlockSignature:
    """Semantic fingerprint of a block — the L2 diff unit.

    Two guard views are kept on purpose:

    * ``guards`` is the raw source text. It moves whenever *any* tag in the
      predicate is renamed, so it is only useful for display.
    * ``guards_abstract`` keeps the **service** tag (the catalog-facing one, last
      in a selector) and drops instance/location tags, mirroring how ``reads``
      and ``calls`` are keyed. A pure re-binding — same device type in another
      room — must leave this view untouched; swapping the device *type* must not.

    ``guards_abstract`` is therefore the field the L2 conformance check reads:
    "structure preserved" means every field but ``tags`` is stable.
    """

    reads: frozenset[str]              # "Tag.member"
    writes: frozenset[str]             # variable names
    gv_reads: frozenset[str]
    gv_writes: frozenset[str]
    calls: frozenset[str]              # "Tag.member/arity"
    guards: tuple[str, ...]
    guards_abstract: tuple[str, ...]
    times: tuple[int, ...]
    tags: frozenset[str]

    #: fields that a pure slot substitution must not perturb
    STABLE_FIELDS = ("reads", "writes", "gv_reads", "gv_writes", "calls",
                     "guards_abstract", "times")

    def diff(self, other: "BlockSignature", *, abstract: bool = True) -> dict[str, tuple]:
        """Field-wise difference. With ``abstract`` (default) the raw guard text
        is skipped, so renaming a location tag is not reported as drift."""
        out: dict[str, tuple] = {}
        for fld in ("reads", "writes", "gv_reads", "gv_writes", "calls", "tags"):
            a, b = getattr(self, fld), getattr(other, fld)
            if a != b:
                out[fld] = (tuple(sorted(a - b)), tuple(sorted(b - a)))
        seq_fields = ("guards_abstract", "times") if abstract else ("guards", "guards_abstract", "times")
        for fld in seq_fields:
            a, b = getattr(self, fld), getattr(other, fld)
            if a != b:
                out[fld] = (a, b)
        return out


# ── structure ────────────────────────────────────────────────────────────────

@dataclass
class Structure:
    src: str
    name: str
    blocks: dict[str, Block]
    devices: list[DeviceRef]
    assigns: list[AssignRef]
    guards: list[GuardAtom]
    times: list[TimeConst]
    literals: list[Literal]
    gvars: list[GVRef]
    errors: list[str]

    # -- role / tag views -----------------------------------------------------

    @property
    def tags(self) -> dict[str, list[Span]]:
        """Tag -> every char span where it occurs (the slot-substitution table)."""
        out: dict[str, list[Span]] = {}
        for d in self.devices:
            for tag, sp in zip(d.tags, d.tag_spans):
                out.setdefault(tag, []).append(sp)
        for k in out:
            out[k].sort()
        return out

    def refs_for_tag(self, tag: str) -> list[DeviceRef]:
        return [d for d in self.devices if tag in d.tags]

    def services(self) -> dict[str, list[DeviceRef]]:
        out: dict[str, list[DeviceRef]] = {}
        for d in self.devices:
            out.setdefault(d.service, []).append(d)
        return out

    # -- block views ----------------------------------------------------------

    def block_of(self, span: Span) -> str:
        """Innermost block containing `span`."""
        best, best_len = "B0", len(self.src) + 1
        for b in self.blocks.values():
            if b.span.start <= span.start and span.end <= b.span.end and len(b.span) < best_len:
                best, best_len = b.id, len(b.span)
        return best

    def signature(self, block_id: str = "B0", *, recursive: bool = True) -> BlockSignature:
        ids = {block_id}
        if recursive:
            stack = [block_id]
            while stack:
                cur = stack.pop()
                for ch in self.blocks[cur].children:
                    ids.add(ch)
                    stack.append(ch)

        reads, writes, calls, tags = set(), set(), set(), set()
        gv_reads, gv_writes = set(), set()
        guards, times = [], []

        gv_ref_ids = {id(g.ref): g for g in self.gvars}
        for d in self.devices:
            if d.block not in ids:
                continue
            tags.update(d.tags)
            gv = gv_ref_ids.get(id(d))
            if gv is not None:
                (gv_writes if gv.kind == "set" else gv_reads).add(gv.key or "?")
                continue
            if d.kind == "call":
                calls.add(f"{d.key}/{len(d.args or [])}")
            else:
                reads.add(d.key)
        for a in self.assigns:
            if a.block in ids:
                writes.add(a.name)
        for g in self.guards:
            if g.block in ids:
                guards.append(_normalize_ws(g.text))
        for t in self.times:
            if t.block in ids:
                times.append(t.ms)

        return BlockSignature(
            reads=frozenset(reads),
            writes=frozenset(writes),
            gv_reads=frozenset(gv_reads),
            gv_writes=frozenset(gv_writes),
            calls=frozenset(calls),
            guards=tuple(sorted(guards)),
            guards_abstract=tuple(sorted(abstract_selectors(g) for g in guards)),
            times=tuple(sorted(times)),
            tags=frozenset(tags),
        )

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "chars": len(self.src),
            "blocks": len(self.blocks),
            "devices": len(self.devices),
            "calls": sum(1 for d in self.devices if d.kind == "call"),
            "reads": sum(1 for d in self.devices if d.kind != "call"),
            "tags": len(self.tags),
            "assigns": len(self.assigns),
            "persistent": sum(1 for a in self.assigns if a.persistent),
            "guards": len(self.guards),
            "times": len(self.times),
            "literals": len(self.literals),
            "gv_get": sum(1 for g in self.gvars if g.kind == "get"),
            "gv_set": sum(1 for g in self.gvars if g.kind == "set"),
            "errors": len(self.errors),
        }


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


_SELECTOR_RE = None


def abstract_selectors(text: str) -> str:
    """Erase the tag list of every selector in `text`.

    ``all(#Light #Office #Section1).switch_switch ==| false``
        -> ``all(<>).switch_switch ==| false``

    Tags say *which devices*; the member says *what is asked of them*. Only the
    latter is structure, so the abstracted guard is invariant under any
    re-binding — including a device-type swap, which is caught by the contract
    layer (stage ④), not by a structural diff.
    """
    global _SELECTOR_RE
    if _SELECTOR_RE is None:
        import re as _re
        _SELECTOR_RE = _re.compile(r"\(\s*(?:#[^\s()#]+\s*)+\)")

    return _SELECTOR_RE.sub("(<>)", text)


# ── parsing ──────────────────────────────────────────────────────────────────

class _Collector(ErrorListener):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):  # noqa: N802
        self.errors.append(f"{line}:{column} {msg}")


def _parse(src: str):
    listener = _Collector()
    lexer = JOILangLexer(InputStream(src))
    lexer.removeErrorListeners()
    lexer.addErrorListener(listener)
    parser = JOILangParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(listener)
    tree = parser.scenario()
    return tree, listener.errors


def parse_errors(src: str) -> list[str]:
    """Syntax errors only (cheap pre-check; L0 of the verification ladder)."""
    return _parse(src)[1]


def _children(ctx) -> Iterable:
    return ctx.children or []


def _typed(ctx, cls):
    for ch in _children(ctx):
        if isinstance(ch, cls):
            return ch
    return None


def _terminals(ctx, token_type: int) -> list[TerminalNode]:
    return [ch for ch in _children(ctx)
            if isinstance(ch, TerminalNode) and ch.symbol.type == token_type]


def _tag_list(ctx: "P.Tag_listContext") -> tuple[tuple[str, ...], tuple[Span, ...], Span]:
    hashtags: list[TerminalNode] = []
    hl = _typed(ctx, P.Hashtag_listContext)
    for ch in _children(hl if hl is not None else ctx):
        if isinstance(ch, TerminalNode) and ch.symbol.type == P.HASHTAG_ID:
            hashtags.append(ch)
    tags = tuple(t.getText().lstrip("#") for t in hashtags)
    spans = tuple(_term_span(t) for t in hashtags)
    return tags, spans, _span(ctx)


def _args_of(ctx: "P.Action_inputContext", src: str) -> list[Arg]:
    out: list[Arg] = []
    il = _typed(ctx, P.Input_listContext) if ctx is not None else None
    if il is None:
        return out
    for ch in _children(il):
        if isinstance(ch, P.Arithmetic_expressionContext):
            sp = _span(ch)
            out.append(Arg(text=sp.slice(src), span=sp))
    return out


class _Walker:
    """Single recursive pass; maintains the current block and literal context."""

    def __init__(self, src: str, name: str) -> None:
        self.src = src
        self.name = name
        self.blocks: dict[str, Block] = {}
        self.devices: list[DeviceRef] = []
        self.assigns: list[AssignRef] = []
        self.guards: list[GuardAtom] = []
        self.times: list[TimeConst] = []
        self.literals: list[Literal] = []
        self.gvars: list[GVRef] = []
        self._n = 0

    # -- blocks --

    def new_block(self, kind: str, span: Span, header: Optional[Span],
                  parent: Optional[str], line: int) -> str:
        bid = f"B{self._n}"
        self._n += 1
        depth = 0 if parent is None else self.blocks[parent].depth + 1
        self.blocks[bid] = Block(id=bid, kind=kind, span=span, header_span=header,
                                 parent=parent, depth=depth, line=line)
        if parent is not None:
            self.blocks[parent].children.append(bid)
        return bid

    # -- entry --

    def run(self, tree) -> None:
        root = self.new_block("root", Span(0, len(self.src)), None, None, 1)
        self.visit(tree, root, "other")

    # -- generic dispatch --

    def visit(self, node, block: str, lit_ctx: str) -> None:
        if isinstance(node, TerminalNode):
            self._literal(node, block, lit_ctx)
            return

        if isinstance(node, P.Action_behaviorContext):
            self._action(node, block)
            return
        if isinstance(node, P.Primary_expressionContext) and _typed(node, P.Tag_listContext):
            self._read(node, block)
            return
        if isinstance(node, P.Value_assign_behaviorContext):
            self._assign(node, block, lit_ctx)
            return
        if isinstance(node, P.If_statementContext):
            self._if(node, block)
            return
        if isinstance(node, P.Loop_statementContext):
            self._loop(node, block)
            return
        if isinstance(node, P.For_each_statementContext):
            self._for(node, block)
            return
        if isinstance(node, P.Wait_until_statementContext):
            self._wait(node, block)
            return
        if isinstance(node, P.Delay_statementContext):
            self._delay(node, block)
            return
        if isinstance(node, P.Condition_atomContext):
            self._guard(node, block)
            return

        for ch in _children(node):
            self.visit(ch, block, lit_ctx)

    # -- leaves --

    def _literal(self, node: TerminalNode, block: str, context: str) -> None:
        t = node.symbol.type
        kind = {
            P.INTEGER: "int", P.DOUBLE: "double", P.STRING_LITERAL: "string",
            P.TRUE: "bool", P.FALSE: "bool",
        }.get(t)
        if kind is None:
            return
        self.literals.append(Literal(
            text=node.getText(), kind=kind, span=_term_span(node),
            context=context, block=block, line=node.symbol.line))

    def _selector_parts(self, ctx, block: str):
        rt = _typed(ctx, P.Range_typeContext)
        tl = _typed(ctx, P.Tag_listContext)
        tags, tag_spans, taglist_span = _tag_list(tl)
        ids = _terminals(ctx, P.IDENTIFIER)
        return rt, tags, tag_spans, taglist_span, ids

    def _action(self, ctx: "P.Action_behaviorContext", block: str) -> None:
        rt, tags, tag_spans, taglist_span, ids = self._selector_parts(ctx, block)
        out_ctx = _typed(ctx, P.OutputContext)
        # `output` is its own rule, so the remaining IDENTIFIER terminal is the member
        member_node = ids[-1] if ids else None
        if member_node is None:
            return
        ai = _typed(ctx, P.Action_inputContext)
        args = _args_of(ai, self.src)
        ref = DeviceRef(
            kind="call", quantifier=rt.getText() if rt else None, tags=tags,
            member=member_node.getText(), args=args, span=_span(ctx),
            quant_span=_span(rt) if rt else None, taglist_span=taglist_span,
            tag_spans=tag_spans, member_span=_term_span(member_node),
            block=block, line=ctx.start.line,
            assigns_to=out_ctx.getText() if out_ctx is not None else None,
        )
        self.devices.append(ref)
        self._maybe_gv(ref)
        if ai is not None:
            self.visit(ai, block, "arg")

    def _read(self, ctx: "P.Primary_expressionContext", block: str) -> None:
        rt, tags, tag_spans, taglist_span, ids = self._selector_parts(ctx, block)
        if not ids:
            return
        member_node = ids[-1]
        ref = DeviceRef(
            kind="read", quantifier=rt.getText() if rt else None, tags=tags,
            member=member_node.getText(), args=None, span=_span(ctx),
            quant_span=_span(rt) if rt else None, taglist_span=taglist_span,
            tag_spans=tag_spans, member_span=_term_span(member_node),
            block=block, line=ctx.start.line)
        self.devices.append(ref)

    def _maybe_gv(self, ref: DeviceRef) -> None:
        if GV_TAG not in ref.tags:
            return
        low = ref.member.lower()
        kind = "set" if "set" in low else "get" if "get" in low else None
        if kind is None:
            return
        key, key_span = None, None
        if ref.args:
            first = ref.args[0]
            txt = first.text.strip()
            if len(txt) >= 2 and txt[0] in "\"'":
                key, key_span = txt[1:-1], first.span
        self.gvars.append(GVRef(kind=kind, key=key, key_span=key_span, ref=ref))

    def _assign(self, ctx: "P.Value_assign_behaviorContext", block: str, lit_ctx: str) -> None:
        out_ctx = _typed(ctx, P.OutputContext)
        op_node = None
        for ch in _children(ctx):
            if isinstance(ch, TerminalNode) and ch.symbol.type in (P.ASSIGN, P.INITIAL_ASSIGN):
                op_node = ch
                break
        rhs = _typed(ctx, P.Arithmetic_expressionContext)
        if out_ctx is None or op_node is None or rhs is None:
            return
        self.assigns.append(AssignRef(
            name=out_ctx.getText(), op=op_node.getText(), span=_span(ctx),
            name_span=_span(out_ctx), rhs_span=_span(rhs), block=block,
            line=ctx.start.line))
        self.visit(rhs, block, "assign")

    def _guard(self, ctx: "P.Condition_atomContext", block: str) -> None:
        exprs = [ch for ch in _children(ctx) if isinstance(ch, P.Arithmetic_expressionContext)]
        op_ctx = _typed(ctx, P.Comparison_operatorContext)
        sp = _span(ctx)
        self.guards.append(GuardAtom(
            text=sp.slice(self.src), span=sp,
            lhs_span=_span(exprs[0]) if exprs else None,
            op=op_ctx.getText() if op_ctx is not None else None,
            op_span=_span(op_ctx) if op_ctx is not None else None,
            rhs_span=_span(exprs[1]) if len(exprs) > 1 else None,
            block=block, line=ctx.start.line))
        for ch in _children(ctx):
            self.visit(ch, block, "guard")

    def _delay(self, ctx: "P.Delay_statementContext", block: str) -> None:
        pt = _typed(ctx, P.Period_timeContext)
        if pt is None:
            return
        num = _terminals(pt, P.INTEGER)
        unit_ctx = _typed(pt, P.Time_unitContext)
        unit = unit_ctx.getText() if unit_ctx is not None else "MSEC"
        raw_val = num[0].getText() if num else "0"
        self.times.append(TimeConst(
            ms=int(raw_val) * TIME_UNIT_MS.get(unit, 1), raw=_span(pt).slice(self.src),
            span=_span(pt), value_span=_term_span(num[0]) if num else _span(pt),
            unit=unit, kind="delay", block=block, line=ctx.start.line))

    # -- nesting --

    def _body_block(self, stmt_ctx, kind: str, header: Optional[Span], parent: str) -> None:
        if stmt_ctx is None:
            return
        bid = self.new_block(kind, _span(stmt_ctx), header, parent, stmt_ctx.start.line)
        self.visit(stmt_ctx, bid, "other")

    def _if(self, ctx: "P.If_statementContext", block: str) -> None:
        cond = _typed(ctx, P.Condition_listContext)
        header = Span(ctx.start.start, (cond.stop.stop + 2) if cond is not None else ctx.start.stop + 1)
        if cond is not None:
            self.visit(cond, block, "guard")
        stmts = [ch for ch in _children(ctx) if isinstance(ch, P.StatementContext)]
        self._body_block(stmts[0] if stmts else None, "then", header, block)
        els = _typed(ctx, P.Else_statementContext)
        if els is not None:
            inner = _typed(els, P.StatementContext)
            self._body_block(inner, "else", Span(els.start.start, els.start.stop + 1), block)

    def _loop(self, ctx: "P.Loop_statementContext", block: str) -> None:
        cond = _typed(ctx, P.Loop_conditionContext)
        if cond is not None:
            self.visit(cond, block, "guard")
        header = Span(ctx.start.start, (cond.stop.stop + 2) if (cond is not None and cond.stop) else ctx.start.stop + 1)
        stmt = _typed(ctx, P.StatementContext)
        self._body_block(stmt, "loop", header, block)

    def _for(self, ctx: "P.For_each_statementContext", block: str) -> None:
        le = _typed(ctx, P.List_expressionContext)
        if le is not None:
            self._iter_source(le, block)
        stmt = _typed(ctx, P.StatementContext)
        header = Span(ctx.start.start, (le.stop.stop + 2) if le is not None else ctx.start.stop + 1)
        self._body_block(stmt, "for", header, block)

    def _iter_source(self, ctx: "P.List_expressionContext", block: str) -> None:
        tl = _typed(ctx, P.Tag_listContext)
        if tl is None:
            return
        tags, tag_spans, taglist_span = _tag_list(tl)
        ids = _terminals(ctx, P.IDENTIFIER)
        if not ids:
            return
        member_node = ids[-1]
        rt = _typed(ctx, P.Range_typeContext)
        quant = rt.getText() if rt is not None else "all"
        self.devices.append(DeviceRef(
            kind="iter", quantifier=quant, tags=tags, member=member_node.getText(),
            args=None, span=_span(ctx), quant_span=_span(rt) if rt is not None else None,
            taglist_span=taglist_span, tag_spans=tag_spans,
            member_span=_term_span(member_node), block=block, line=ctx.start.line))

    def _wait(self, ctx: "P.Wait_until_statementContext", block: str) -> None:
        cond = _typed(ctx, P.Condition_listContext)
        if cond is not None:
            self.visit(cond, block, "guard")


def extract(src: str, name: str = "scenario") -> Structure:
    """Parse `src` and build the structure tables. Never raises on syntax errors;
    partial results plus `errors` are returned so callers can fail closed."""
    tree, errors = _parse(src)
    w = _Walker(src, name)
    try:
        w.run(tree)
    except Exception as exc:  # defensive: malformed tree after syntax errors
        errors = errors + [f"walk: {type(exc).__name__}: {exc}"]
    return Structure(src=src, name=name, blocks=w.blocks, devices=w.devices,
                     assigns=w.assigns, guards=w.guards, times=w.times,
                     literals=w.literals, gvars=w.gvars, errors=errors)


# ── CLI ──────────────────────────────────────────────────────────────────────

def _print_report(st: Structure) -> None:
    print(f"# {st.name}  ({len(st.src)} chars)")
    if st.errors:
        print(f"  !! syntax errors: {st.errors[:3]}")
    s = st.summary()
    print(f"  blocks={s['blocks']} devices={s['devices']} (call {s['calls']} / read {s['reads']}) "
          f"tags={s['tags']} assigns={s['assigns']} (persistent {s['persistent']}) "
          f"guards={s['guards']} delays={s['times']} gv={s['gv_get']}g/{s['gv_set']}s")

    print("\n  ## blocks")
    for b in st.blocks.values():
        sig = st.signature(b.id, recursive=False)
        head = ("  " * b.depth) + f"{b.id}:{b.kind}@L{b.line}"
        print(f"  {head:<28} reads={len(sig.reads)} calls={len(sig.calls)} "
              f"writes={sorted(sig.writes) if sig.writes else '-'} "
              f"gv={sorted(sig.gv_reads | sig.gv_writes) if (sig.gv_reads or sig.gv_writes) else '-'}")

    print("\n  ## role references (tag -> occurrences)")
    for tag, spans in sorted(st.tags.items(), key=lambda kv: -len(kv[1])):
        print(f"    #{tag:<22} x{len(spans):<3} at {[sp.start for sp in spans][:8]}")

    print("\n  ## device uses")
    for d in st.devices:
        q = f"{d.quantifier}" if d.quantifier else ""
        args = "" if d.args is None else "(" + ", ".join(a.text for a in d.args) + ")"
        print(f"    L{d.line:<3} {d.block:<4} {d.kind:<5} {q}({' '.join('#'+t for t in d.tags)}).{d.member}{args}")


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Stage ①: structural extraction")
    ap.add_argument("--corpus", default=os.path.join(_REPO, "paper_v2", "joi_automation_codes.json"),
                    help="hand-written scenario JSON (list of {name, code})")
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--pair", help="instead: a sim/cache pair id, e.g. C01_001")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = ap.parse_args(argv)

    if args.pair:
        path = os.path.join(_REPO, "sim", "cache", f"{args.pair}.json")
        with open(path, encoding="utf-8") as f:
            pair = json.load(f)
        src, name = (pair.get("joi_block") or {}).get("script", ""), args.pair
    else:
        with open(args.corpus, encoding="utf-8") as f:
            rows = json.load(f)
        row = rows[args.index]
        src, name = row["code"], row.get("name", f"#{args.index}")

    st = extract(src, name)
    if args.json:
        print(json.dumps(st.summary(), ensure_ascii=False, indent=2))
    else:
        _print_report(st)
    return 1 if st.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
