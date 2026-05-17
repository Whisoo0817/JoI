"""Expression parser and evaluator for IR and JoI cond/arg expressions.

Accepts both syntaxes (single grammar, alternative tokens):
- Logical: `&&`/`and`, `||`/`or`, `!`/`not`
- Variables: `$var` (IR) or `var` (JoI) — both resolve to the same name
- Device refs: `Door.DoorState` (IR) or `(#Door).DoorState` / `all(#X).Y` / `any(#X).Y` (JoI)
- Clock builtins: `clock.time`, `clock.date`, `clock.dayOfWeek`
- Literals: int, float, "string", true/false/null
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Arithmetic: `+`, `-`, `*`, `/`, unary `-`

Canonicalization: a device ref like `(#Door).DoorState` resolves to a key
"Door.DoorState" by taking the last `#tag` inside the selector. This lets
both simulators read/write the same world-state dict regardless of source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# ── Tokenizer ────────────────────────────────────────────────────────────────

_TOK_RE = re.compile(
    r"""
    \s+                                  |  # whitespace (skip)
    (?P<NUMBER>\d+\.\d+|\d+)             |  # numeric literal
    (?P<STRING>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')  |  # string literal
    (?P<SELECTOR>\b(?:all|any)?\s*\(\s*\#[^)]*\))    |  # JoI selector chunk: (#X), all(#X #Y), any(#X)
    (?P<OP>==|!=|<=|>=|&&|\|\||[+\-*/<>!=(),])       |  # operators / parens / comma (func-call separator)
    (?P<IDENT>\$?[A-Za-z_][A-Za-z0-9_.]*)               # ident with optional $ prefix and dots
    """,
    re.VERBOSE,
)

# Allowed function names in IR/JoI expressions. abs/max/min are convenience
# primitives in IR (JoI itself has none — lowering emits a manual workaround).
_BUILTIN_FUNCS = {"abs", "max", "min"}


@dataclass
class Token:
    kind: str
    value: str


def tokenize(src: str) -> list[Token]:
    out: list[Token] = []
    pos = 0
    while pos < len(src):
        m = _TOK_RE.match(src, pos)
        if not m:
            raise ValueError(f"unrecognized token at {pos}: {src[pos:pos+20]!r}")
        if m.group("NUMBER"):
            out.append(Token("NUMBER", m.group("NUMBER")))
        elif m.group("STRING"):
            out.append(Token("STRING", m.group("STRING")))
        elif m.group("SELECTOR"):
            out.append(Token("SELECTOR", m.group("SELECTOR")))
        elif m.group("OP"):
            out.append(Token("OP", m.group("OP")))
        elif m.group("IDENT"):
            out.append(Token("IDENT", m.group("IDENT")))
        # else: whitespace, skip
        pos = m.end()
    return out


# ── AST ──────────────────────────────────────────────────────────────────────

@dataclass
class Lit:
    value: Any

def canonical_name(service: str, name: str) -> str:
    """Strip `<service>_` prefix (case-insensitive) and lowercase.

    Run-local post-processing renames methods/attrs to `<svc_lower>_<camelCase>`
    style (e.g., `Dishwasher.SetDishwasherMode` → `dishwasher_setDishwasherMode`).
    Trace comparison and world-state lookups need to match across both forms,
    so we canonicalize both to a prefix-stripped lowercase form.
    """
    if service:
        svc_low = service.lower()
        n_low = name.lower()
        if n_low.startswith(svc_low + "_"):
            return n_low[len(svc_low) + 1:]
        return n_low
    return (name or "").lower()


def canonical_key(service: str, name: str) -> tuple[str, str]:
    """Reduce (service, name) to canonical (sub_service, attr_or_method) pair.

    Symmetric with Trace.emit: if the canonical name still contains `_` (i.e.,
    after stripping `<service>_`, a `<sub_service>_<rest>` form remains), the
    leading word IS the actual capability and we use it as the service.

    Examples:
      ("Switch", "Switch")               → ("switch", "switch")
      ("FaceRecognizer", "switch_switch") → ("switch", "switch")
      ("Dishwasher", "SetDishwasherMode") → ("dishwasher", "setdishwashermode")
      ("Light", "switch_on")              → ("switch", "on")
    """
    can = canonical_name(service, name)
    svc = (service or "").lower()
    if "_" in can:
        prefix, _, rest = can.partition("_")
        if prefix and rest:
            return (prefix, rest)
    return (svc, can)


@dataclass
class DeviceRef:
    key: str  # canonicalized "service.attr" (both lowercased, prefix stripped)

@dataclass
class ClockRef:
    field: str  # "time", "date", "dayOfWeek"

@dataclass
class VarRef:
    name: str

@dataclass
class UnaryOp:
    op: str
    operand: Any

@dataclass
class BinaryOp:
    op: str
    left: Any
    right: Any

@dataclass
class FuncCall:
    name: str       # one of _BUILTIN_FUNCS
    args: list      # list of AST nodes


# ── Parser ───────────────────────────────────────────────────────────────────

class _Parser:
    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.i = 0

    def peek(self) -> Token | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def consume(self) -> Token:
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def expect_op(self, op: str) -> None:
        tok = self.peek()
        if tok is None or tok.kind != "OP" or tok.value != op:
            raise ValueError(f"expected '{op}', got {tok}")
        self.consume()

    def parse_expr(self) -> Any:
        return self._parse_or()

    def _parse_or(self) -> Any:
        left = self._parse_and()
        while True:
            tok = self.peek()
            if tok and ((tok.kind == "OP" and tok.value == "||") or
                        (tok.kind == "IDENT" and tok.value == "or")):
                self.consume()
                right = self._parse_and()
                left = BinaryOp("or", left, right)
            else:
                return left

    def _parse_and(self) -> Any:
        left = self._parse_not()
        while True:
            tok = self.peek()
            if tok and ((tok.kind == "OP" and tok.value == "&&") or
                        (tok.kind == "IDENT" and tok.value == "and")):
                self.consume()
                right = self._parse_not()
                left = BinaryOp("and", left, right)
            else:
                return left

    def _parse_not(self) -> Any:
        tok = self.peek()
        if tok and ((tok.kind == "OP" and tok.value == "!") or
                    (tok.kind == "IDENT" and tok.value == "not")):
            self.consume()
            return UnaryOp("not", self._parse_not())
        return self._parse_cmp()

    def _parse_cmp(self) -> Any:
        left = self._parse_add()
        tok = self.peek()
        if tok and tok.kind == "OP" and tok.value in ("==", "!=", "<", ">", "<=", ">="):
            op = self.consume().value
            right = self._parse_add()
            return BinaryOp(op, left, right)
        return left

    def _parse_add(self) -> Any:
        left = self._parse_mul()
        while True:
            tok = self.peek()
            if tok and tok.kind == "OP" and tok.value in ("+", "-"):
                op = self.consume().value
                right = self._parse_mul()
                left = BinaryOp(op, left, right)
            else:
                return left

    def _parse_mul(self) -> Any:
        left = self._parse_unary()
        while True:
            tok = self.peek()
            if tok and tok.kind == "OP" and tok.value in ("*", "/"):
                op = self.consume().value
                right = self._parse_unary()
                left = BinaryOp(op, left, right)
            else:
                return left

    def _parse_unary(self) -> Any:
        tok = self.peek()
        if tok and tok.kind == "OP" and tok.value == "-":
            self.consume()
            return UnaryOp("-", self._parse_unary())
        return self._parse_atom()

    def _parse_atom(self) -> Any:
        tok = self.peek()
        if tok is None:
            raise ValueError("unexpected end of expression")

        if tok.kind == "OP" and tok.value == "(":
            self.consume()
            e = self.parse_expr()
            self.expect_op(")")
            return e

        if tok.kind == "NUMBER":
            self.consume()
            v = tok.value
            return Lit(int(v) if v.isdigit() else float(v))

        if tok.kind == "STRING":
            self.consume()
            s = tok.value
            # strip quotes
            return Lit(s[1:-1])

        if tok.kind == "SELECTOR":
            # JoI form like "(#Door)" or "all(#X #Y)" — followed by ".Attr"
            self.consume()
            sel_text = tok.value
            # Extract last "#tag" inside the selector as the canonical service
            tags = re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", sel_text)
            service = tags[-1] if tags else ""
            # Expect ".attr"
            nxt = self.peek()
            if nxt and nxt.kind == "OP" and nxt.value == ".":
                # tokenizer doesn't emit "." as OP; this branch is dead but defensive
                self.consume()
                attr_tok = self.consume()
                attr = attr_tok.value
                svc, a = canonical_key(service, attr)
                return DeviceRef(f"{svc}.{a}")
            if nxt and nxt.kind == "IDENT" and nxt.value.startswith("."):
                self.consume()
                attr = nxt.value.lstrip(".")
                svc, a = canonical_key(service, attr)
                return DeviceRef(f"{svc}.{a}")
            return DeviceRef(f"{service.lower()}.")

        if tok.kind == "IDENT":
            self.consume()
            name = tok.value
            # Builtin function call: IDENT '(' expr (',' expr)* ')'
            if name in _BUILTIN_FUNCS:
                nxt = self.peek()
                if nxt and nxt.kind == "OP" and nxt.value == "(":
                    self.consume()  # '('
                    args = [self.parse_expr()]
                    while True:
                        nxt2 = self.peek()
                        if nxt2 and nxt2.kind == "OP" and nxt2.value == ",":
                            self.consume()
                            args.append(self.parse_expr())
                        else:
                            break
                    self.expect_op(")")
                    return FuncCall(name, args)
            # Reserved literals
            if name == "true":
                return Lit(True)
            if name == "false":
                return Lit(False)
            if name == "null" or name == "none":
                return Lit(None)
            # `clock.time`, `clock.date`, `clock.dayOfWeek`
            if name.startswith("clock."):
                return ClockRef(name.split(".", 1)[1])
            # `$var` (IR style)
            if name.startswith("$"):
                return VarRef(name[1:])
            # `Service.Attr` (IR device ref) — exactly two dotted parts and Capitalized
            if "." in name:
                first, _, rest = name.partition(".")
                if first[:1].isupper():
                    svc, a = canonical_key(first, rest)
                    return DeviceRef(f"{svc}.{a}")
                # something else; treat as opaque var name
                return VarRef(name)
            # Bare identifier → variable (JoI fresh read or persistent var)
            return VarRef(name)

        raise ValueError(f"unexpected token {tok}")


def parse(src: str) -> Any:
    """Parse a single expression and return the AST root."""
    # Tokenizer doesn't emit "." as standalone op — but selectors are followed by ".Attr".
    # Pre-process: insert space after `)` to ensure `.Attr` becomes its own IDENT-like token.
    # Actually our IDENT regex requires leading letter; ".Attr" needs special handling.
    # Hack: rewrite ").Attr" → ") .Attr" and accept ".Attr" as a bare IDENT we splice.
    # Cleaner: handle in parser by extending tokenizer. Below: pre-rewrite to make the
    # leading-dot identifier explicit.
    src2 = re.sub(r"\)\s*\.([A-Za-z_])", r") .\1", src)
    # Also tokenize `.Attr` as IDENT by adapting regex: we keep the trailing-dot ident form
    # working by pre-pending a `_` only when it would otherwise fail. Instead, just tweak
    # the IDENT-from-tokenizer: allow leading dot for tokens that start with `.A-Z`.
    tokens = _tokenize_with_leading_dot(src2)
    p = _Parser(tokens)
    e = p.parse_expr()
    if p.i != len(tokens):
        raise ValueError(f"trailing tokens: {tokens[p.i:]}")
    return e


def _tokenize_with_leading_dot(src: str) -> list[Token]:
    """Tokenize allowing `.Identifier` as a single IDENT (used after selectors)."""
    extended = re.compile(
        r"""
        \s+                                  |
        (?P<NUMBER>\d+\.\d+|\d+)             |
        (?P<STRING>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')  |
        (?P<SELECTOR>\b(?:all|any)?\s*\(\s*\#[^)]*\))    |
        (?P<OP>==|!=|<=|>=|&&|\|\||[+\-*/<>!=(),])       |
        (?P<DOTIDENT>\.[A-Za-z_][A-Za-z0-9_]*)           |
        (?P<IDENT>\$?[A-Za-z_][A-Za-z0-9_.]*)
        """,
        re.VERBOSE,
    )
    out: list[Token] = []
    pos = 0
    while pos < len(src):
        m = extended.match(src, pos)
        if not m:
            raise ValueError(f"unrecognized token at {pos}: {src[pos:pos+20]!r}")
        for k in ("NUMBER", "STRING", "SELECTOR", "OP", "DOTIDENT", "IDENT"):
            v = m.group(k)
            if v is not None:
                if k == "DOTIDENT":
                    out.append(Token("IDENT", v))  # parser sees IDENT starting with '.'
                else:
                    out.append(Token(k, v))
                break
        pos = m.end()
    return out


# ── Evaluator ────────────────────────────────────────────────────────────────

class EvalContext:
    """Read-only evaluation context for cond/arg expressions.

    - `world`: dict of "Service.Attr" -> value (current device state)
    - `vars`: dict of var name -> value (from IR `read` ops or JoI `=` assignments)
    - `clock`: dict with keys "time" (int hhmm), "date" (str YYYYMMdd), "dayOfWeek" (str MON..SUN)
    """
    def __init__(self, world: dict, vars_: dict, clock: dict):
        self.world = world
        self.vars = vars_
        self.clock = clock


def evaluate(node: Any, ctx: EvalContext) -> Any:
    if isinstance(node, Lit):
        return node.value
    if isinstance(node, DeviceRef):
        return ctx.world.get(node.key)
    if isinstance(node, ClockRef):
        return ctx.clock.get(node.field)
    if isinstance(node, VarRef):
        return ctx.vars.get(node.name)
    if isinstance(node, UnaryOp):
        v = evaluate(node.operand, ctx)
        if node.op == "not":
            return not v
        if node.op == "-":
            return -v
        raise ValueError(f"unknown unary op: {node.op}")
    if isinstance(node, FuncCall):
        vals = [evaluate(a, ctx) for a in node.args]
        # None substitution: skip None args so abs/max/min still produce useful
        # values when an unseeded var slips through (matches BinaryOp's lenient
        # arithmetic policy).
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
        if node.name == "abs":
            return abs(vals[0])
        if node.name == "max":
            return max(vals)
        if node.name == "min":
            return min(vals)
        raise ValueError(f"unknown function: {node.name}")
    if isinstance(node, BinaryOp):
        a = evaluate(node.left, ctx)
        b = evaluate(node.right, ctx)
        op = node.op
        if op == "and": return bool(a) and bool(b)
        if op == "or":  return bool(a) or bool(b)
        if op == "==":  return a == b
        if op == "!=":  return a != b
        # Comparisons against None (state never set) → treat cond as False.
        # This happens when lowering reads an attribute key that synth didn't
        # seed (typically due to IR↔JoI naming-convention drift). Returning
        # False is more useful than crashing — surfaces as trace_mismatch.
        if op in ("<", ">", "<=", ">="):
            if a is None or b is None:
                return False
            if op == "<":   return a < b
            if op == ">":   return a > b
            if op == "<=":  return a <= b
            if op == ">=":  return a >= b
        # Arithmetic with JoI semantics: `+` auto-casts to string when either
        # operand is a string ("text" + 5 → "text5"). None substituted with
        # "" for string ops or 0 for numeric ops, matching JoI runtime which
        # always sees a concrete sensor value (here we don't pre-seed every
        # read, so None substitution avoids spurious crashes that wouldn't
        # happen on a real device).
        if op == "+":
            if isinstance(a, str) or isinstance(b, str):
                a_s = "" if a is None else str(a)
                b_s = "" if b is None else str(b)
                return a_s + b_s
            if a is None: a = 0
            if b is None: b = 0
            return a + b
        if op in ("-", "*", "/"):
            if a is None: a = 0
            if b is None: b = 0
            if op == "-": return a - b
            if op == "*": return a * b
            if op == "/": return a / b if b != 0 else 0
        raise ValueError(f"unknown binary op: {op}")
    raise TypeError(f"cannot evaluate {type(node).__name__}")


def eval_str(src: str, ctx: EvalContext) -> Any:
    """Parse and evaluate an expression string in one shot."""
    return evaluate(parse(src), ctx)


# ── Reference extraction (for event synthesis) ───────────────────────────────

def collect_device_refs(node: Any, out: list[str]) -> None:
    """Walk an AST and collect all DeviceRef keys."""
    if isinstance(node, DeviceRef):
        out.append(node.key)
    elif isinstance(node, UnaryOp):
        collect_device_refs(node.operand, out)
    elif isinstance(node, BinaryOp):
        collect_device_refs(node.left, out)
        collect_device_refs(node.right, out)
    elif isinstance(node, FuncCall):
        for a in node.args:
            collect_device_refs(a, out)
    # Lit, ClockRef, VarRef have no device refs
