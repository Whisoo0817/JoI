"""JoI script parser.

Parses a JoI script string into a list of statements (AST).

Grammar (informal):
    script := stmt*
    stmt   := assign | if_stmt | wait_until | delay | break | call_stmt
    assign := IDENT (':=' | '=') rhs
    rhs    := call_expr | expr
    call_stmt    := call_expr             # method call as a statement
    call_expr    := target '.' method '(' args ')'
    target       := selector | IDENT      # selector: (#X), all(#X), any(#X)
    if_stmt      := 'if' '(' expr ')' '{' stmt* '}' ('else' (if_stmt | '{' stmt* '}'))?
    wait_until   := 'wait' 'until' '(' expr ')'
    delay        := 'delay' '(' NUMBER UNIT ')'
    break        := 'break'

Whitespace and newlines are separators only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import expr as expr_mod


# ── AST nodes ────────────────────────────────────────────────────────────────

@dataclass
class CallExpr:
    """A method call like `(#Door).DoorState` (no args, treated as attribute read)
    or `(#Light).SetBrightness(80, 0)`. Attribute reads use args=None to distinguish
    from zero-arg method calls (args=[])."""
    service: str        # canonicalized last #tag from selector, or IDENT
    method: str         # method or attribute name
    args: list | None   # None = attribute access, list = method call

@dataclass
class Assign:
    name: str
    op: str             # ':=' or '='
    rhs: Any            # AST node (CallExpr, BinaryOp, Lit, etc.)

@dataclass
class IfStmt:
    cond: Any
    then_body: list
    else_body: list = field(default_factory=list)

@dataclass
class WaitUntil:
    cond: Any

@dataclass
class Delay:
    ms: int

@dataclass
class Break:
    pass

@dataclass
class CallStmt:
    """Bare method-call statement (call as side effect, not assignment rhs)."""
    call: CallExpr


# ── Tokenizer ────────────────────────────────────────────────────────────────

_UNIT_MS = {"HOUR": 3_600_000, "MIN": 60_000, "SEC": 1_000, "MSEC": 1}
_KEYWORDS = {"if", "else", "wait", "until", "delay", "break", "and", "or", "not",
             "true", "false", "null"}

_TOK = re.compile(
    r"""
    \s+                                                  |
    (?P<NUMBER>\d+\.\d+|\d+)                             |
    (?P<STRING>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')      |
    (?P<SELECTOR>(?:\b(?:all|any))?\s*\(\s*\#[^)]*\))    |
    (?P<ASSIGNINIT>:=)                                   |
    (?P<OP>==\||!=\||<=\||>=\||<\||>\||==|!=|<=|>=|&&|\|\||[+\-*/<>!(){},.])    |
    (?P<EQ>=)                                            |
    (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE,
)


@dataclass
class Tok:
    kind: str
    value: str


def _tokenize(src: str) -> list[Tok]:
    out: list[Tok] = []
    pos = 0
    while pos < len(src):
        m = _TOK.match(src, pos)
        if not m:
            raise ValueError(f"unrecognized token at {pos}: {src[pos:pos+30]!r}")
        for k in ("NUMBER", "STRING", "SELECTOR", "ASSIGNINIT", "OP", "EQ", "IDENT"):
            v = m.group(k)
            if v is not None:
                out.append(Tok(k, v))
                break
        pos = m.end()
    return out


# ── Parser ───────────────────────────────────────────────────────────────────

class _P:
    def __init__(self, toks: list[Tok]):
        self.toks = toks
        self.i = 0

    def peek(self, offset: int = 0) -> Tok | None:
        idx = self.i + offset
        return self.toks[idx] if idx < len(self.toks) else None

    def eat(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind: str, value: str | None = None) -> Tok:
        t = self.peek()
        if t is None or t.kind != kind or (value is not None and t.value != value):
            raise ValueError(f"expected {kind} {value!r}, got {t}")
        return self.eat()

    # script := stmt*
    def parse_script(self) -> list:
        stmts = []
        while self.peek() is not None:
            stmts.append(self.parse_stmt())
        return stmts

    def parse_stmt(self) -> Any:
        t = self.peek()
        if t is None:
            raise ValueError("unexpected eof")

        # Keywords
        if t.kind == "IDENT" and t.value == "if":
            return self.parse_if()
        if t.kind == "IDENT" and t.value == "wait":
            return self.parse_wait()
        if t.kind == "IDENT" and t.value == "delay":
            return self.parse_delay()
        if t.kind == "IDENT" and t.value == "break":
            self.eat()
            return Break()

        # Assign vs call_stmt — peek for `:=` or `=` after an IDENT
        if t.kind == "IDENT":
            # Look-ahead: IDENT followed by `:=` or `=` (but not `==`)
            n1 = self.peek(1)
            if n1 is not None and (n1.kind == "ASSIGNINIT" or
                                   (n1.kind == "EQ")):
                return self.parse_assign()

        # Otherwise: a call expression as a standalone stmt
        ce = self.parse_call_expr()
        if not isinstance(ce, CallExpr):
            raise ValueError(f"expression not allowed as statement: {ce}")
        return CallStmt(ce)

    def parse_assign(self) -> Assign:
        name_tok = self.expect("IDENT")
        op_tok = self.peek()
        if op_tok.kind == "ASSIGNINIT":
            self.eat()
            op = ":="
        else:
            self.expect("EQ")
            op = "="
        # RHS: try call_expr first (it's a superset of expr that handles selectors
        # in lvalue position), otherwise fall back to general expr
        rhs = self.parse_rhs_expr()
        return Assign(name_tok.value, op, rhs)

    def parse_rhs_expr(self) -> Any:
        """Parse an RHS — could be a call_expr or a general expression.

        Strategy: use a unified Pratt-ish approach. We hand-roll a small expression
        parser that handles literals, selectors, idents, comparisons, arithmetic,
        and method calls.
        """
        return self._parse_expr()

    def _parse_expr(self) -> Any:
        return self._parse_or()

    def _parse_or(self):
        left = self._parse_and()
        while True:
            t = self.peek()
            if t and ((t.kind == "OP" and t.value == "||") or
                      (t.kind == "IDENT" and t.value == "or")):
                self.eat()
                right = self._parse_and()
                left = expr_mod.BinaryOp("or", left, right)
            else:
                return left

    def _parse_and(self):
        left = self._parse_not()
        while True:
            t = self.peek()
            if t and ((t.kind == "OP" and t.value == "&&") or
                      (t.kind == "IDENT" and t.value == "and")):
                self.eat()
                right = self._parse_not()
                left = expr_mod.BinaryOp("and", left, right)
            else:
                return left

    def _parse_not(self):
        t = self.peek()
        if t and ((t.kind == "OP" and t.value == "!") or
                  (t.kind == "IDENT" and t.value == "not")):
            self.eat()
            return expr_mod.UnaryOp("not", self._parse_not())
        return self._parse_cmp()

    _CMP_OPS = ("==", "!=", "<", ">", "<=", ">=",
                "==|", "!=|", "<|", ">|", "<=|", ">=|")

    def _parse_cmp(self):
        left = self._parse_add()
        t = self.peek()
        if t and t.kind == "OP" and t.value in self._CMP_OPS:
            raw = self.eat().value
            # `OP|` is JoI's any-quantifier form ("exists element with X OP V").
            # Treat as plain OP — selector multiplicity is out of scope.
            op = raw[:-1] if raw.endswith("|") else raw
            right = self._parse_add()
            return expr_mod.BinaryOp(op, left, right)
        return left

    def _parse_add(self):
        left = self._parse_mul()
        while True:
            t = self.peek()
            if t and t.kind == "OP" and t.value in ("+", "-"):
                op = self.eat().value
                right = self._parse_mul()
                left = expr_mod.BinaryOp(op, left, right)
            else:
                return left

    def _parse_mul(self):
        left = self._parse_unary()
        while True:
            t = self.peek()
            if t and t.kind == "OP" and t.value in ("*", "/"):
                op = self.eat().value
                right = self._parse_unary()
                left = expr_mod.BinaryOp(op, left, right)
            else:
                return left

    def _parse_unary(self):
        t = self.peek()
        if t and t.kind == "OP" and t.value == "-":
            self.eat()
            return expr_mod.UnaryOp("-", self._parse_unary())
        return self._parse_atom()

    def _parse_atom(self):
        t = self.peek()
        if t is None:
            raise ValueError("unexpected eof in expression")

        if t.kind == "NUMBER":
            self.eat()
            return expr_mod.Lit(int(t.value) if t.value.isdigit() else float(t.value))

        if t.kind == "STRING":
            self.eat()
            return expr_mod.Lit(t.value[1:-1])

        if t.kind == "OP" and t.value == "(":
            # Parenthesized expression — but might be start of a selector-less call?
            # Only literals/idents are valid in parens here.
            self.eat()
            e = self._parse_expr()
            self.expect("OP", ")")
            return e

        if t.kind == "SELECTOR":
            return self.parse_call_expr()

        if t.kind == "IDENT":
            return self.parse_call_expr()

        raise ValueError(f"unexpected token: {t}")

    def parse_call_expr(self) -> Any:
        """Parse a call expression: selector.method(args), selector.attr,
        ident.method(args), or bare ident.
        """
        from .expr import canonical_name
        t = self.peek()
        # Determine the "service" portion
        if t.kind == "SELECTOR":
            self.eat()
            tags = re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", t.value)
            service = tags[-1] if tags else ""
        elif t.kind == "IDENT":
            # could be a bare var, a literal keyword, or service/clock IDENT
            if t.value in ("true", "false"):
                self.eat()
                return expr_mod.Lit(t.value == "true")
            if t.value == "null":
                self.eat()
                return expr_mod.Lit(None)
            self.eat()
            n = self.peek()
            # `clock.<field>` is always a ClockRef regardless of whether
            # something else follows.
            if t.value == "clock" and n and n.kind == "OP" and n.value == ".":
                self.eat()
                f = self.expect("IDENT")
                return expr_mod.ClockRef(f.value)
            if not (n and n.kind == "OP" and n.value == "."):
                # No dot → bare variable reference
                return expr_mod.VarRef(t.value)
            service = t.value
        else:
            raise ValueError(f"unexpected token in call_expr: {t}")

        # Expect "."
        dot = self.peek()
        if not (dot and dot.kind == "OP" and dot.value == "."):
            return expr_mod.DeviceRef(f"{service.lower()}.")
        self.eat()

        # Method/attr name
        name_tok = self.expect("IDENT")
        method = name_tok.value

        # Optional `(args)` for method call; absence = attribute access
        n = self.peek()
        if n and n.kind == "OP" and n.value == "(":
            self.eat()
            args = []
            if not (self.peek() and self.peek().kind == "OP" and self.peek().value == ")"):
                args.append(self._parse_expr())
                while self.peek() and self.peek().kind == "OP" and self.peek().value == ",":
                    self.eat()
                    args.append(self._parse_expr())
            self.expect("OP", ")")
            return CallExpr(service, method, args)
        else:
            # attribute access — canonicalize to match IR/synth keys
            from .expr import canonical_key
            svc, attr = canonical_key(service, method)
            return expr_mod.DeviceRef(f"{svc}.{attr}")

    def parse_if(self) -> IfStmt:
        self.expect("IDENT", "if")
        self.expect("OP", "(")
        cond = self._parse_expr()
        self.expect("OP", ")")
        self.expect("OP", "{")
        then_body = self.parse_block_body()
        self.expect("OP", "}")
        else_body: list = []
        nxt = self.peek()
        if nxt and nxt.kind == "IDENT" and nxt.value == "else":
            self.eat()
            nxt2 = self.peek()
            if nxt2 and nxt2.kind == "IDENT" and nxt2.value == "if":
                # else if -> nested if
                else_body = [self.parse_if()]
            else:
                self.expect("OP", "{")
                else_body = self.parse_block_body()
                self.expect("OP", "}")
        return IfStmt(cond, then_body, else_body)

    def parse_block_body(self) -> list:
        stmts = []
        while True:
            t = self.peek()
            if t is None:
                break
            if t.kind == "OP" and t.value == "}":
                break
            stmts.append(self.parse_stmt())
        return stmts

    def parse_wait(self) -> WaitUntil:
        self.expect("IDENT", "wait")
        self.expect("IDENT", "until")
        self.expect("OP", "(")
        cond = self._parse_expr()
        self.expect("OP", ")")
        return WaitUntil(cond)

    def parse_delay(self) -> Delay:
        self.expect("IDENT", "delay")
        self.expect("OP", "(")
        n_tok = self.expect("NUMBER")
        unit_tok = self.expect("IDENT")
        unit_ms = _UNIT_MS.get(unit_tok.value)
        if unit_ms is None:
            raise ValueError(f"unknown delay unit: {unit_tok.value}")
        self.expect("OP", ")")
        n = int(n_tok.value) if n_tok.value.isdigit() else float(n_tok.value)
        return Delay(int(n * unit_ms))


def parse_script(src: str) -> list:
    """Parse a JoI script string into a list of statements."""
    toks = _tokenize(src)
    p = _P(toks)
    return p.parse_script()
