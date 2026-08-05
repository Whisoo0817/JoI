"""M1 — symbolic encoder for one-shot (IR, JoI) pairs.

Pipeline:
    IR timeline ──┐
                  ├─→ micro-op sequence ─→ symbolic execution ─→ per-path
    JoI AST ──────┘        (shared)          (z3, landmark times)   action lists
                                                     │
                                        miter: ∃ input where action
                                        lists mismatch (tol 1000 ms)

Modeling decisions (v0):
- Input model: every state key read by either side is a piecewise-constant
  function of time with K (default 2) symbolic change points.
- Time: z3 Int milliseconds, horizon = 7 days (same as the simulators).
- Values: Real for numeric keys, Bool for boolean keys, interned Int codes
  for enum/string keys (universe = literals seen + one fresh "other").
- wait completion = first element of a finite landmark set (wait-start,
  input change points, clock boundaries) where the condition holds.
- Actions compare by (method, positional args) — service excluded, exactly
  like TraceRecord.key(). Times must agree within TOLERANCE_MS.
- Call effects write back into the world (same rules as World.apply_effect)
  so read-after-effect sees the written value unless a later scenario
  change overwrote it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import z3

from sim import expr as E
from sim import joi_parser as jp
from sim.catalog import get_arg_order
from sim.timeline_ir import parse_duration_to_ms

from smt.obligations import ObligationSet, decide

import os as _os

TOLERANCE_MS = 1000
HORIZON_MS = 7 * 86_400_000
K_CHANGE_POINTS = int(_os.environ.get("SMT_K_POINTS", "2"))   # K-sensitivity knob

_MS_PER_DAY = 86_400_000
_MS_PER_HOUR = 3_600_000


class Unsupported(Exception):
    """Pair uses a construct outside the M1 fragment — fail-closed."""


# ── micro-ops ────────────────────────────────────────────────────────────────

@dataclass
class MWait:
    cond: Any                 # expr AST
    edge: str = "none"        # none | rising | falling
    for_ms: int = 0

@dataclass
class MDelay:
    ms: int

@dataclass
class MAssign:
    var: str
    rhs: Any                  # expr AST (or jp.CallExpr for binds)

@dataclass
class MEmit:
    service: str
    method: str
    args: list                # list of expr AST / python literals (positional)
    bind: Optional[str] = None

@dataclass
class MIf:
    cond: Any
    then: list
    els: list


# ── frontends ────────────────────────────────────────────────────────────────

_EXPR_MARKERS = set("+-*/<>=!&|")
_VAR_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_.]*)")


def _ir_arg_to_ast(v: Any) -> Any:
    """IR arg value → expr AST / literal, mirroring ir_simulator._maybe_eval."""
    if not isinstance(v, str):
        return E.Lit(v)
    if any(c in _EXPR_MARKERS for c in v) or v.lstrip().startswith("$"):
        stripped = v.strip()
        m = _VAR_RE.fullmatch(stripped)
        if m:  # whole-string $ref keeps raw type
            return E.parse(stripped)
        try:
            ast = E.parse(v)
            return ast
        except Exception:
            pass
    if "$" in v:  # interpolation "temp is $t" → concat parts
        parts: list = []
        pos = 0
        for m in _VAR_RE.finditer(v):
            if m.start() > pos:
                parts.append(E.Lit(v[pos:m.start()]))
            parts.append(E.parse("$" + m.group(1)))
            pos = m.end()
        if pos < len(v):
            parts.append(E.Lit(v[pos:]))
        node = parts[0]
        for p in parts[1:]:
            node = E.BinaryOp("+", node, p)
        return node
    return E.Lit(v)


def ir_to_micro(ir: dict) -> list:
    """One-shot Timeline IR (anchor=now, no cycle) → micro-ops."""
    tl = ir.get("timeline", [])
    head = tl[0] if tl else {}
    if not (isinstance(head, dict) and head.get("op") == "start_at"):
        raise Unsupported("timeline[0] is not start_at")
    if head.get("anchor") != "now":
        raise Unsupported("cron anchor is M3")
    return _ir_steps_to_micro(tl[1:])


def _ir_steps_to_micro(steps: list) -> list:
    out: list = []
    for s in steps:
        op = s.get("op")
        if op == "wait":
            for_str = s.get("for")
            out.append(MWait(E.parse(s.get("cond", "")), s.get("edge", "none") or "none",
                             parse_duration_to_ms(for_str) if for_str else 0))
        elif op == "delay":
            out.append(MDelay(parse_duration_to_ms(s.get("duration", "0 MSEC"))))
        elif op == "read":
            out.append(MAssign(s["var"], E.parse(s["src"])))
        elif op == "call":
            svc, _, method = s.get("target", "").partition(".")
            args_named = s.get("args") or {}
            out.append(MEmit(svc, method,
                             [( k, _ir_arg_to_ast(v)) for k, v in args_named.items()],
                             bind=s.get("var") or s.get("bind")))
        elif op == "if":
            out.append(MIf(E.parse(s.get("cond", "")),
                           _ir_steps_to_micro(s.get("then", []) or []),
                           _ir_steps_to_micro(s.get("else", []) or [])))
        elif op == "cycle":
            raise Unsupported("cycle is M2")
        elif op == "break":
            raise Unsupported("top-level break outside cycle")
        else:
            raise Unsupported(f"unknown IR op {op}")
    return out


def joi_to_micro(joi_block: dict) -> list:
    """One-shot JoI block (cron '', period 0) → micro-ops."""
    if (joi_block.get("cron") or "").strip():
        raise Unsupported("cron JoI is M3")
    if int(joi_block.get("period", 0) or 0) != 0:
        raise Unsupported("periodic JoI is M2")
    stmts = jp.parse_script(joi_block.get("script", "") or "")
    return _joi_stmts_to_micro(stmts)


def _joi_stmts_to_micro(stmts: list) -> list:
    out: list = []
    for s in stmts:
        if isinstance(s, jp.Assign):
            if isinstance(s.rhs, jp.CallExpr) and s.rhs.args is not None:
                out.append(MEmit(s.rhs.service, s.rhs.method,
                                 list(s.rhs.args), bind=s.name))
            else:
                out.append(MAssign(s.name, s.rhs))
        elif isinstance(s, jp.CallStmt):
            out.append(MEmit(s.call.service, s.call.method, list(s.call.args or [])))
        elif isinstance(s, jp.WaitUntil):
            out.append(MWait(s.cond, "none", 0))
        elif isinstance(s, jp.Delay):
            out.append(MDelay(s.ms))
        elif isinstance(s, jp.IfStmt):
            out.append(MIf(s.cond, _joi_stmts_to_micro(s.then_body),
                           _joi_stmts_to_micro(s.else_body or [])))
        elif isinstance(s, jp.Break):
            raise Unsupported("break in one-shot JoI")
        else:
            raise Unsupported(f"unknown JoI stmt {type(s).__name__}")
    return out


# ── key & type inference ─────────────────────────────────────────────────────

def _dotted_varref_key(name: str) -> Optional[str]:
    """`$Service.Attr` VarRef → canonical device key (evaluate() fallback)."""
    if "." in name:
        first, _, rest = name.partition(".")
        if first[:1].isupper():
            svc, a = E.canonical_key(first, rest)
            return f"{svc}.{a}"
    return None


def _node_key(node) -> Optional[str]:
    """Device-state key a leaf node reads, or None."""
    if isinstance(node, E.DeviceRef):
        return node.key
    if isinstance(node, E.VarRef):
        return _dotted_varref_key(node.name)
    if isinstance(node, jp.CallExpr) and node.args is None:
        svc, a = E.canonical_key(node.service, node.method)
        return f"{svc}.{a}"
    return None


_CLOCK_KEYS = {"clock.hour", "clock.minute", "clock.weekday", "clock.day",
               "clock.month", "clock.year", "clock.time", "clock.date",
               "clock.dayofweek"}


class TypeInfo:
    """Per-key sort inference + enum interning."""

    def __init__(self) -> None:
        self.kinds: dict[str, str] = {}          # key → num|bool|enum
        self.enum_universe: dict[str, list] = {}  # key → [str literals]
        self._intern: dict[str, int] = {}

    def observe(self, key: str, lit: Any) -> None:
        if key is None or key in _CLOCK_KEYS:
            return
        if isinstance(lit, bool):
            self._raise(key, "bool")
        elif isinstance(lit, str):
            self._raise(key, "enum")
            self.enum_universe.setdefault(key, [])
            if lit not in self.enum_universe[key]:
                self.enum_universe[key].append(lit)
        elif isinstance(lit, (int, float)):
            self._raise(key, "num")

    _ORDER = {"num": 0, "bool": 1, "enum": 2}

    def _raise(self, key: str, kind: str) -> None:
        cur = self.kinds.get(key)
        if cur is None or self._ORDER[kind] > self._ORDER[cur]:
            self.kinds[key] = kind

    def kind(self, key: str) -> str:
        return self.kinds.get(key, "num")

    def intern(self, s: str) -> int:
        if s not in self._intern:
            self._intern[s] = len(self._intern) + 1
        return self._intern[s]

    def uninterned(self, code: int) -> Optional[str]:
        for s, c in self._intern.items():
            if c == code:
                return s
        return None


def collect_keys_and_types(micro_lists: list[list],
                           alias: dict | None = None) -> tuple[set, TypeInfo]:
    """All device keys read + inferred sorts from comparisons/assignments.
    `alias` unifies device-grounded duplicate keys (grounding.py)."""
    keys: set = set()
    ti = TypeInfo()
    alias = alias or {}
    env: dict = {}   # local var → device key, for `v = (#X).attr; v == "lit"`

    def _k(key):
        return alias.get(key, key)

    def _key_of(node):
        """Device key a comparison side reads — directly, or through a local
        variable bound to a bare read (assignment indirection would otherwise
        lose the enum observation and turn the guard statically false)."""
        k = _node_key(node)
        if k is None and isinstance(node, E.VarRef):
            k = env.get(node.name)
        return k

    def walk_expr(node) -> None:
        k = _node_key(node)
        if k is not None and k not in _CLOCK_KEYS:
            keys.add(_k(k))
            return
        if isinstance(node, E.UnaryOp):
            walk_expr(node.operand)
        elif isinstance(node, E.BinaryOp):
            # comparison against literal → type observation
            if node.op in ("==", "!=", "<", ">", "<=", ">="):
                lk, rk = _key_of(node.left), _key_of(node.right)
                if lk and isinstance(node.right, E.Lit):
                    ti.observe(_k(lk), node.right.value)
                if rk and isinstance(node.left, E.Lit):
                    ti.observe(_k(rk), node.left.value)
            walk_expr(node.left)
            walk_expr(node.right)
        elif isinstance(node, E.FuncCall):
            for a in node.args:
                walk_expr(a)
        elif isinstance(node, jp.CallExpr) and node.args is not None:
            for a in node.args:
                walk_expr(a)

    def walk_ops(ops: list) -> None:
        for op in ops:
            if isinstance(op, MWait):
                walk_expr(op.cond)
            elif isinstance(op, MAssign):
                rk = _node_key(op.rhs)
                if rk is not None and rk not in _CLOCK_KEYS:
                    env[op.var] = rk
                walk_expr(op.rhs)
            elif isinstance(op, MEmit):
                for a in op.args:
                    node = a[1] if isinstance(a, tuple) else a
                    walk_expr(node)
            elif isinstance(op, MIf):
                walk_expr(op.cond)
                walk_ops(op.then)
                walk_ops(op.els)

    for ml in micro_lists:
        walk_ops(ml)
    return keys, ti


# ── input model ──────────────────────────────────────────────────────────────

class InputModel:
    """Piecewise-constant symbolic input per key + shared landmark set."""

    def __init__(self, keys: set, ti: TypeInfo, k_points: int = K_CHANGE_POINTS):
        self.ti = ti
        self.keys = sorted(keys)
        self.constraints: list = []
        self.taus: dict[str, list] = {}
        self.vals: dict[str, list] = {}
        self._consts: dict[str, Any] = {}
        for key in self.keys:
            safe = key.replace(".", "_")
            taus = [z3.Int(f"tau_{safe}_{i}") for i in range(k_points)]
            for i, t in enumerate(taus):
                self.constraints.append(t >= 0)
                self.constraints.append(t <= HORIZON_MS)
                # Simulators sample on a 100 ms poll grid; sub-grid events are
                # invisible to them, so the symbolic input lives on the grid too.
                self.constraints.append(t % 100 == 0)
                if i > 0:
                    self.constraints.append(taus[i - 1] <= t)
            kind = ti.kind(key)
            vals = []
            for i in range(k_points + 1):
                if kind == "bool":
                    v = z3.Bool(f"v_{safe}_{i}")
                elif kind == "enum":
                    v = z3.Int(f"v_{safe}_{i}")
                    universe = ti.enum_universe.get(key, [])
                    codes = [ti.intern(s) for s in universe]
                    other = len(ti._intern) + 1000 + i  # fresh "other" code
                    self.constraints.append(
                        z3.Or(*[v == c for c in codes], v == other))
                else:
                    v = z3.Real(f"v_{safe}_{i}")
                vals.append(v)
            self.taus[key] = taus
            self.vals[key] = vals

    def shared_const(self, name: str, lo: int, hi: int) -> Any:
        """A symbolic constant SHARED by every executor over this input model
        (e.g. clock.month: fixed within the window, unknown which — proving
        under it means proving for every value in [lo, hi]). Window-crossing
        (deploy near a month boundary) is outside the input model, as stated."""
        if name not in self._consts:
            v = z3.Int(f"const_{name.replace('.', '_')}")
            self.constraints.append(v >= lo)
            self.constraints.append(v <= hi)
            self._consts[name] = v
        return self._consts[name]

    def base_value(self, key: str, t) -> Any:
        """Scenario value of `key` at time t (no effect overrides)."""
        taus, vals = self.taus[key], self.vals[key]
        expr = vals[len(vals) - 1]
        for i in range(len(taus) - 1, -1, -1):
            expr = z3.If(t < taus[i], vals[i], expr)
        return expr

    def last_change_before(self, key: str, t) -> Any:
        """Time of the last scenario change of `key` at or before t (0 if none)."""
        taus = self.taus[key]
        expr = z3.IntVal(0)
        for tau in taus:
            expr = z3.If(tau <= t, tau, expr)
        return expr

    def landmarks(self) -> list:
        """All input change points (z3 Int exprs)."""
        out = []
        for key in self.keys:
            out.extend(self.taus[key])
        return out


# ── symbolic executor ────────────────────────────────────────────────────────

# Symbolic string value = tuple of parts; each part is a python str or a
# ("val", z3expr/py) marker. Adjacent str parts merged at construction.
class SParts:
    def __init__(self, parts: list):
        merged: list = []
        for p in parts:
            if isinstance(p, str) and merged and isinstance(merged[-1], str):
                merged[-1] += p
            else:
                merged.append(p)
        self.parts = merged

    def __repr__(self):
        return f"SParts({self.parts!r})"


NONE_VAL = ("__none__",)  # shared opaque None (unbound cloud-call return)


@dataclass
class Action:
    time: Any                 # z3 Int expr
    service: str
    method: str               # canonical method
    args: list                # positional; z3 exprs / python literals / SParts


@dataclass
class Path:
    guard: list = field(default_factory=list)    # z3 Bools
    time: Any = None                             # z3 Int expr — current time
    env: dict = field(default_factory=dict)      # var → symbolic value
    effects: list = field(default_factory=list)  # (key, time_expr, value)
    actions: list = field(default_factory=list)
    stalled: bool = False                        # wait never completes

    def fork(self) -> "Path":
        return Path(list(self.guard), self.time, dict(self.env),
                    list(self.effects), list(self.actions), self.stalled)


class SymExec:
    def __init__(self, im: InputModel, ti: TypeInfo, catalog: dict,
                 clock_landmarks: list, tag: str, alias: dict | None = None):
        self.im = im
        self.ti = ti
        self.catalog = catalog
        self.tag = tag           # "ir" | "joi" — fresh-var namespacing
        self.alias = alias or {}  # device-grounded key unification (grounding.py)
        self._n = 0
        self.constraints: list = []
        # landmark pool: input change points + concrete clock boundaries
        self.base_landmarks = im.landmarks() + [z3.IntVal(c) for c in clock_landmarks]

    def fresh_time(self) -> Any:
        self._n += 1
        return z3.Int(f"t_{self.tag}_{self._n}")

    # ── state read ──
    def state_at(self, path: Path, key: str, t) -> Any:
        key = self.alias.get(key, key)
        if key in _CLOCK_KEYS:
            return self._clock_value(key, t)
        if key not in self.im.taus:
            return NONE_VAL   # key not modeled (never read by either side)
        v = self.im.base_value(key, t)
        lsc = self.im.last_change_before(key, t)
        for (k, te, ve) in path.effects:
            if k == key:
                v = z3.If(z3.And(te <= t, lsc <= te), ve, v)
        return v

    def _clock_value(self, key: str, t) -> Any:
        if key == "clock.hour":
            return (t % _MS_PER_DAY) / _MS_PER_HOUR
        if key == "clock.minute":
            return (t / 60000) % 60
        if key in ("clock.weekday", "clock.dayofweek"):
            raise Unsupported("weekday cond in one-shot")  # M3 territory
        if key == "clock.time":
            return ((t % _MS_PER_DAY) / _MS_PER_HOUR) * 100 + (t / 60000) % 60
        if key == "clock.month":
            # constant within the window, symbolic across deployments —
            # a proof under it holds for every month (v2 seasonal branches)
            return self.im.shared_const("clock.month", 1, 12)
        if key == "clock.day":
            return self.im.shared_const("clock.day", 1, 31)
        raise Unsupported(f"clock key {key}")

    # ── expression evaluation ──
    def eval(self, node, path: Path, t) -> Any:
        if isinstance(node, E.Lit):
            return node.value
        k = _node_key(node)
        if k is not None:
            return self.state_at(path, k, t)
        if isinstance(node, E.ClockRef):
            if node.field == "time":
                return self._clock_value("clock.time", t)
            if node.field == "timestamp":
                # epoch seconds = T0 (symbolic deploy time, shared by both
                # miter sides) + seconds since deploy. Epoch-scale matters:
                # `last := 0` is a NEVER-YET sentinel, and `now - 0 > cooldown`
                # must be true at first fire — a deploy-relative clock would
                # keep every such gate shut for the whole window (vacuous
                # proofs). Integer truncation is identical on both sides.
                t0 = self.im.shared_const("clock.epoch0",
                                          1_000_000_000, 2_000_000_000)
                return t0 + self.to_num(t) / 1000
            raise Unsupported(f"clock.{node.field}")
        if isinstance(node, E.VarRef):
            if node.name in path.env:
                return path.env[node.name]
            return NONE_VAL
        if isinstance(node, E.UnaryOp):
            v = self.eval(node.operand, path, t)
            if node.op == "not":
                return z3.Not(self.to_bool(v))
            if node.op == "-":
                return -self.to_num(v)
            raise Unsupported(f"unary {node.op}")
        if isinstance(node, E.FuncCall):
            vals = [self.eval(a, path, t) for a in node.args]
            if node.name == "abs":
                x = self.to_num(vals[0])
                return z3.If(x < 0, -x, x)
            if node.name == "max":
                r = self.to_num(vals[0])
                for v in vals[1:]:
                    x = self.to_num(v)
                    r = z3.If(x > r, x, r)
                return r
            if node.name == "min":
                r = self.to_num(vals[0])
                for v in vals[1:]:
                    x = self.to_num(v)
                    r = z3.If(x < r, x, r)
                return r
            if node.name in ("any", "all", "avg"):
                # single-device collapse (same as evaluate())
                return vals[0]
            raise Unsupported(f"func {node.name}")
        if isinstance(node, E.BinaryOp):
            return self._eval_binop(node, path, t)
        if isinstance(node, jp.CallExpr):
            raise Unsupported("call expression in value position")
        raise Unsupported(f"node {type(node).__name__}")

    def _eval_binop(self, node, path: Path, t) -> Any:
        op = node.op
        if op in ("and", "or"):
            a = self.to_bool(self.eval(node.left, path, t))
            b = self.to_bool(self.eval(node.right, path, t))
            return z3.And(a, b) if op == "and" else z3.Or(a, b)
        a = self.eval(node.left, path, t)
        b = self.eval(node.right, path, t)
        if op in ("==", "!="):
            eq = self.values_equal(a, b, node)
            return eq if op == "==" else z3.Not(eq)
        if op in ("<", ">", "<=", ">="):
            an, bn = self.to_num(a), self.to_num(b)
            return {"<": an < bn, ">": an > bn,
                    "<=": an <= bn, ">=": an >= bn}[op]
        if op == "+":
            if self._is_stringish(a) or self._is_stringish(b):
                return SParts(self._to_parts(a) + self._to_parts(b))
            return self.to_num(a) + self.to_num(b)
        if op == "-":
            return self.to_num(a) - self.to_num(b)
        if op == "*":
            return self.to_num(a) * self.to_num(b)
        if op == "/":
            bn = self.to_num(b)
            return z3.If(bn == 0, z3.RealVal(0), self.to_num(a) / bn)
        if op == "%":
            raise Unsupported("% in one-shot")
        raise Unsupported(f"binop {op}")

    # ── value plumbing ──
    def _is_stringish(self, v) -> bool:
        return isinstance(v, (str, SParts))

    def _to_parts(self, v) -> list:
        if isinstance(v, SParts):
            return list(v.parts)
        if isinstance(v, str):
            return [v]
        if v is NONE_VAL:
            return [""]        # None → "" in string concat (evaluate() policy)
        return [("val", v)]

    def to_bool(self, v) -> Any:
        if isinstance(v, bool):
            return z3.BoolVal(v)
        if v is NONE_VAL:
            return z3.BoolVal(False)
        if isinstance(v, (int, float)):
            return z3.BoolVal(bool(v))
        if isinstance(v, str):
            return z3.BoolVal(bool(v))
        if z3.is_bool(v):
            return v
        # numeric expr → truthy
        return v != 0

    def to_num(self, v) -> Any:
        if isinstance(v, bool):
            return z3.RealVal(1 if v else 0)
        if isinstance(v, (int, float)):
            return z3.RealVal(v)
        if v is NONE_VAL:
            return z3.RealVal(0)
        if isinstance(v, (str, SParts)):
            raise Unsupported("string in numeric context")
        if z3.is_bool(v):
            return z3.If(v, z3.RealVal(1), z3.RealVal(0))
        if z3.is_int(v):
            return z3.ToReal(v)
        return v

    def values_equal(self, a, b, node=None) -> Any:
        """Equality across our value kinds. Enum string vs enum-coded key read:
        the key read already yields an Int code; intern the literal."""
        # resolve which side is a raw python string literal vs z3 expr
        def norm(x, other):
            if isinstance(x, str) and z3.is_expr(other) and not z3.is_bool(other) \
                    and other.sort() == z3.IntSort():
                return z3.IntVal(self.ti.intern(x))
            if isinstance(x, bool) and z3.is_expr(other) and z3.is_bool(other):
                return z3.BoolVal(x)
            return x
        a2, b2 = norm(a, b), norm(b, a)
        if a2 is NONE_VAL and b2 is NONE_VAL:
            return z3.BoolVal(True)
        if a2 is NONE_VAL or b2 is NONE_VAL:
            return z3.BoolVal(False)
        if isinstance(a2, SParts) or isinstance(b2, SParts):
            return self.parts_equal(self._to_parts(a2), self._to_parts(b2))
        if isinstance(a2, str) and isinstance(b2, str):
            return z3.BoolVal(a2 == b2)
        if isinstance(a2, str) or isinstance(b2, str):
            # string vs numeric/bool expr — sims: == is False on type mismatch
            s, e = (a2, b2) if isinstance(a2, str) else (b2, a2)
            if z3.is_expr(e) and not z3.is_bool(e) and e.sort() == z3.IntSort():
                return e == z3.IntVal(self.ti.intern(s))
            return z3.BoolVal(False)
        if isinstance(a2, bool) or isinstance(b2, bool):
            return self.to_bool(a2) == self.to_bool(b2)
        if z3.is_expr(a2) and z3.is_bool(a2) or z3.is_expr(b2) and z3.is_bool(b2):
            return self.to_bool(a2) == self.to_bool(b2)
        # numeric/enum-int
        if z3.is_expr(a2) and z3.is_expr(b2) and a2.sort() == b2.sort():
            return a2 == b2
        return self.to_num(a2) == self.to_num(b2)

    def parts_equal(self, pa: list, pb: list) -> Any:
        if len(pa) != len(pb):
            return z3.BoolVal(False)
        conj = []
        for x, y in zip(pa, pb):
            xs, ys = isinstance(x, str), isinstance(y, str)
            if xs and ys:
                if x != y:
                    return z3.BoolVal(False)
            elif xs != ys:
                return z3.BoolVal(False)
            else:
                conj.append(self.values_equal(x[1], y[1]))
        return z3.And(*conj) if conj else z3.BoolVal(True)

    # ── wait encoding ──
    def wait_first_true(self, path: Path, cond, edge: str, for_ms: int) -> list:
        """Encode wait completion. Returns list of successor Paths:
        one completing path (time = T'), one stalled path (never completes)."""
        T = path.time
        Lms = self.base_landmarks
        # candidate completion instants
        if edge == "none":
            cands = [T] + Lms
        else:
            cands = list(Lms)   # transitions only happen at landmarks

        def cond_at(t):
            return self.to_bool(self.eval(cond, path, t))

        def fires_at(t):
            """cond satisfied in the edge-aware sense at instant t."""
            c = z3.And(t >= T, t <= HORIZON_MS, cond_at(t) if edge != "falling"
                       else z3.Not(cond_at(t)))
            if edge in ("rising", "falling"):
                # transition: value just before t differs. "Just before" =
                # evaluate at t-1 ms (piecewise-constant ⇒ exact), and the
                # transition must be after wait start (prev sampled at T).
                before = cond_at(t - 1)
                want_before = z3.Not(before) if edge == "rising" else before
                c = z3.And(c, t > T, want_before)
            if for_ms > 0:
                # sustain: cond (post-edge polarity) holds on [t, t+for_ms):
                # no landmark in that window may falsify it.
                hold = cond_at if edge != "falling" else (lambda x: z3.Not(cond_at(x)))
                sus = [z3.Implies(z3.And(l > t, l < t + for_ms),
                                  hold(l)) for l in Lms]
                c = z3.And(c, t + for_ms <= HORIZON_MS, *sus)
            return c

        Tp = self.fresh_time()
        fire_disj = []
        for i, ci in enumerate(cands):
            earlier = [z3.Implies(z3.And(cj >= T, cj < ci), z3.Not(fires_at(cj)))
                       for j, cj in enumerate(cands) if j != i]
            fire_disj.append(z3.And(fires_at(ci), Tp == ci +
                                    (for_ms if for_ms > 0 else 0), *earlier))
        completes = z3.Or(*fire_disj) if fire_disj else z3.BoolVal(False)
        never = z3.And(*[z3.Not(fires_at(c)) for c in cands]) if cands else z3.BoolVal(True)

        done = path.fork()
        done.guard.append(completes)
        done.time = Tp
        stall = path.fork()
        stall.guard.append(never)
        stall.stalled = True
        return [done, stall]

    # ── emit ──
    def emit(self, path: Path, op: MEmit) -> None:
        svc_c, method_c = E.canonical_key(op.service, op.method)
        # positional args: IR gives named tuples, JoI gives raw ASTs
        if op.args and isinstance(op.args[0], tuple) and isinstance(op.args[0][0], str) \
                and not z3.is_expr(op.args[0][0]):
            # IR named form — order via catalog (raw service/method ids)
            names = [a[0] for a in op.args]
            nodes = {a[0]: a[1] for a in op.args}
            order = get_arg_order(self.catalog, op.service, op.method)
            if order is None:
                keys = sorted(names)
            else:
                keys = [k for k in order if k in nodes] + sorted(
                    k for k in names if k not in order)
            arg_nodes = [nodes[k] for k in keys]
        else:
            arg_nodes = list(op.args)
        vals = [self.eval(n, path, path.time) for n in arg_nodes]
        vals = [self._coerce_arg(v) for v in vals]
        act = Action(path.time, svc_c, method_c, vals)
        # comparator-style dedup: identical (method, args) at same instant
        if path.actions:
            prev = path.actions[-1]
            if prev.method == act.method and self._args_syntactically_equal(prev, act) \
                    and prev.time is act.time:
                self._apply_effect(path, op, vals)
                return
        path.actions.append(act)
        self._apply_effect(path, op, vals)

    def _coerce_arg(self, v):
        if isinstance(v, SParts) and len(v.parts) == 1 and isinstance(v.parts[0], str):
            return v.parts[0]
        return v

    def _args_syntactically_equal(self, a: Action, b: Action) -> bool:
        if len(a.args) != len(b.args):
            return False
        for x, y in zip(a.args, b.args):
            if isinstance(x, SParts) or isinstance(y, SParts):
                if not (isinstance(x, SParts) and isinstance(y, SParts)
                        and repr(x) == repr(y)):
                    return False
            elif z3.is_expr(x) or z3.is_expr(y):
                if not (z3.is_expr(x) and z3.is_expr(y) and x.eq(y)):
                    return False
            elif x != y:
                return False
        return True

    def _apply_effect(self, path: Path, op: MEmit, vals: list) -> None:
        from smt.fragment import _effect_key
        # canonical pair, mirroring the sims' apply_effect(canonical_key(...))
        svc_c, method_c = E.canonical_key(op.service, op.method)
        ek = _effect_key(svc_c, method_c)
        if ek is not None:
            ek = self.alias.get(ek, ek)
        m = E.canonical_name(svc_c, method_c)
        written = None
        if ek is not None:
            if m == "on":
                written = True
            elif m == "off":
                written = False
            elif m == "toggle":
                cur = self.state_at(path, ek, path.time)
                written = z3.Not(self.to_bool(cur))
            elif len(vals) == 1:
                written = vals[0]
            if written is not None:
                path.effects.append((ek, path.time, written))
        if op.bind:
            if ek is not None and written is not None:
                path.env[op.bind] = written
            else:
                path.env[op.bind] = NONE_VAL

    # ── main loop ──
    def run(self, micro: list) -> list[Path]:
        init = Path(guard=[], time=z3.IntVal(0))
        return self._run_ops(micro, [init])

    def _run_ops(self, ops: list, paths: list[Path]) -> list[Path]:
        for op in ops:
            nxt: list[Path] = []
            for p in paths:
                if p.stalled:
                    nxt.append(p)
                    continue
                if isinstance(op, MWait):
                    nxt.extend(self.wait_first_true(p, op.cond, op.edge, op.for_ms))
                elif isinstance(op, MDelay):
                    q = p.fork()
                    q.time = p.time + op.ms
                    nxt.append(q)
                elif isinstance(op, MAssign):
                    q = p.fork()
                    q.env[op.var] = self.eval(op.rhs, p, p.time)
                    nxt.append(q)
                elif isinstance(op, MEmit):
                    q = p.fork()
                    self.emit(q, op)
                    nxt.append(q)
                elif isinstance(op, MIf):
                    c = self.to_bool(self.eval(op.cond, p, p.time))
                    pt = p.fork(); pt.guard.append(c)
                    pf = p.fork(); pf.guard.append(z3.Not(c))
                    nxt.extend(self._run_ops(op.then, [pt]))
                    nxt.extend(self._run_ops(op.els, [pf]))
                else:
                    raise Unsupported(f"op {type(op).__name__}")
            paths = nxt
            if len(paths) > 64:
                raise Unsupported(f"path explosion ({len(paths)})")
        return paths


# ── clock landmark extraction ────────────────────────────────────────────────

def collect_clock_landmarks(micro_lists: list[list]) -> list[int]:
    """Concrete times (ms) where clock-based atoms can change truth value."""
    hours: set[int] = set()
    minutes: set[tuple] = set()

    def walk_expr(node) -> None:
        if isinstance(node, E.BinaryOp):
            for side, other in ((node.left, node.right), (node.right, node.left)):
                k = _node_key(side)
                if k == "clock.hour" and isinstance(other, E.Lit) \
                        and isinstance(other.value, (int, float)):
                    hours.add(int(other.value))
                    hours.add(int(other.value) + 1)
            walk_expr(node.left)
            walk_expr(node.right)
        elif isinstance(node, E.UnaryOp):
            walk_expr(node.operand)
        elif isinstance(node, E.FuncCall):
            for a in node.args:
                walk_expr(a)

    def walk_ops(ops: list) -> None:
        for op in ops:
            if isinstance(op, MWait):
                walk_expr(op.cond)
            elif isinstance(op, MIf):
                walk_expr(op.cond)
                walk_ops(op.then)
                walk_ops(op.els)
            elif isinstance(op, MAssign):
                walk_expr(op.rhs)

    for ml in micro_lists:
        walk_ops(ml)
    out = []
    for day in range(7):
        for h in hours:
            if 0 <= h <= 24:
                out.append(day * _MS_PER_DAY + h * _MS_PER_HOUR)
    return sorted(set(out))


# ── miter ────────────────────────────────────────────────────────────────────

def build_miter(ir: dict, joi_block: dict, catalog: dict,
                tolerance_ms: int = TOLERANCE_MS, devices=None):
    """Return (solver, im, ti, grounding) with the divergence query asserted."""
    m_ir = ir_to_micro(ir)
    m_joi = joi_to_micro(joi_block)

    from smt.grounding import compute_grounding, Grounding
    grd = compute_grounding(ir, joi_block, devices) if devices else Grounding()

    keys, ti = collect_keys_and_types([m_ir, m_joi], grd.alias)
    clocks = collect_clock_landmarks([m_ir, m_joi])
    im = InputModel(keys, ti)

    ex_ir = SymExec(im, ti, catalog, clocks, "ir", alias=grd.alias)
    ex_joi = SymExec(im, ti, catalog, clocks, "joi", alias=grd.alias)
    paths_ir = ex_ir.run(m_ir)
    paths_joi = ex_joi.run(m_joi)

    def path_guard(p: Path):
        return z3.And(*p.guard) if p.guard else z3.BoolVal(True)

    obs = ObligationSet()
    for p in paths_ir:
        for q in paths_joi:
            g = z3.And(path_guard(p), path_guard(q))
            if len(p.actions) != len(q.actions):
                obs.add("shape:count", g)
                continue
            for a, b in zip(p.actions, q.actions):
                if a.method != b.method or len(a.args) != len(b.args):
                    # both paths active is already a mismatch at this index
                    obs.add("shape:method", g)
                    continue
                t_ok = z3.And(a.time - b.time <= tolerance_ms,
                              b.time - a.time <= tolerance_ms)
                arg_eqs = [ex_ir.values_equal(x, y) for x, y in zip(a.args, b.args)]
                obs.add(f"sig:{a.method}/{len(a.args)}",
                        z3.And(g, z3.Not(z3.And(t_ok, *arg_eqs))))
            # identical empty action lists → no possible mismatch on this pair

    s = z3.Solver()
    for c in im.constraints:
        s.add(c)
    inst = obs.install(s)
    return s, im, ti, grd, inst


def check_pair(ir: dict, joi_block: dict, catalog: dict,
               tolerance_ms: int = TOLERANCE_MS, devices=None,
               split: bool = False) -> dict:
    """Gate entry: → {verdict: EQUIV|DIVERGE|UNSUPPORTED, ...}."""
    import time
    t0 = time.perf_counter()
    try:
        s, im, ti, g, inst = build_miter(ir, joi_block, catalog,
                                         tolerance_ms, devices)
    except Unsupported as e:
        return {"verdict": "UNSUPPORTED", "reason": str(e),
                "elapsed_s": time.perf_counter() - t0}
    out = decide(s, inst, lambda m: extract_scenario(m, im, ti), split=split)
    out["elapsed_s"] = time.perf_counter() - t0
    out["meta"] = {"alias": g.alias, "mistargets": g.mistargets}
    return out


def extract_scenario(model, im: InputModel, ti: TypeInfo) -> dict:
    """z3 model → {key: {initial, events: [(t_ms, value)]}} for sim replay."""
    def dec(v, kind):
        val = model.eval(v, model_completion=True)
        if kind == "bool":
            return z3.is_true(val)
        if kind == "enum":
            code = val.as_long()
            return ti.uninterned(code) or f"<other:{code}>"
        # Real
        if z3.is_rational_value(val):
            num, den = val.numerator_as_long(), val.denominator_as_long()
            f = num / den
            return int(f) if f.is_integer() else f
        return 0

    out: dict = {}
    for key in im.keys:
        kind = ti.kind(key)
        vals = [dec(v, kind) for v in im.vals[key]]
        taus = [model.eval(t, model_completion=True).as_long()
                for t in im.taus[key]]
        events = []
        for tau, v in zip(taus, vals[1:]):
            events.append((tau, v))
        out[key] = {"initial": vals[0], "events": events}
    return out
