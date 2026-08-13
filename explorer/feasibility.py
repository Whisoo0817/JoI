"""Input-combo deduplication: keep one representative per distinguishable
input world.

The cell product is exhaustive but redundant: the program cannot tell
`forecast(2h)="rain"` from `forecast(2h)="snow"` apart — both flow into the
same OR — yet the raw product explores them separately (강수예보:
78,125 combos/tick). Two combos are interchangeable when, from EVERY state,
they drive the tick identically. Sufficient (and decidable) condition used
here — the combos agree on:

1. the truth of every maximal INPUT-PURE subtree of every condition
   expression (if/wait/loop). A subtree is input-pure when its transitive
   reads are only input axes (sensors, external GVs, params, single-def
   wires thereof). Impure parts (state, timers, calendar) vary by state,
   so instead their input reads fall through to rule 2.
2. the raw value of every VALUE-FLOWING key: inputs that reach a state
   assignment, an action argument, or a GV write — where the value itself,
   not just a branch bit, is observable.

Everything here is deterministic — dropping a genuinely distinct combo
would make EQUIV silently unsound, so no heuristic (and no LLM) ever sits
on the discard side; uncertainty always degrades to "keep raw" (rule 2).

Loop-parameterized reads (`fc = forecast(h)` with h ∈ 1..6) are handled by
evaluating each condition once per loop index with h bound — the wet/dry
pattern over hours becomes part of the signature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import expr as expr_mod
from . import joi_parser as jp
from .expr import canonical_key
from .predicates import (VarInfo, var_defs, walk_stmts, _fold_with_params)

CLOCK_INPUT = "clock.isholiday"          # the only clock read that is an axis


# ── shared read walk ─────────────────────────────────────────────────────────

def _reads(node: Any, out: list) -> None:
    """(kind, name) reads: var / device / gv / query(base, args-ast)."""
    if isinstance(node, jp.CallExpr):
        svc, m = canonical_key(node.service, node.method)
        if node.args is None:
            from .explore import _read_key
            out.append(("device", _read_key(node)))
        elif svc == "globalvariable":
            if m.startswith("get") and isinstance(node.args[0], expr_mod.Lit):
                out.append(("gv", str(node.args[0].value)))
            for a in node.args:
                _reads(a, out)
        else:
            from .interp import world_key
            out.append(("query", (world_key(node.tags, node.service,
                                            node.method), tuple(node.args))))
            for a in node.args:
                _reads(a, out)
        return
    if isinstance(node, expr_mod.QuantRef):
        from .explore import _read_key
        out.append(("device", _read_key(node)))
    elif isinstance(node, expr_mod.DeviceRef):
        out.append(("device", node.key))
    elif isinstance(node, expr_mod.ClockRef):
        out.append(("device", f"clock.{node.field.lower()}"))
    elif isinstance(node, expr_mod.VarRef):
        out.append(("var", node.name))
    elif isinstance(node, expr_mod.UnaryOp):
        _reads(node.operand, out)
    elif isinstance(node, expr_mod.BinaryOp):
        _reads(node.left, out)
        _reads(node.right, out)
    elif isinstance(node, expr_mod.FuncCall):
        for a in node.args:
            _reads(a, out)


def _input_closure(node: Any, vars_: dict, defs: dict,
                   visiting: frozenset = frozenset()) -> tuple[set, set]:
    """(exact combo keys, key prefixes) transitively read by an expression."""
    exact: set = set()
    prefixes: set = set()
    reads: list = []
    _reads(node, reads)
    for kind, nm in reads:
        if kind == "device":
            if nm and (nm == CLOCK_INPUT or not nm.startswith("clock.")):
                exact.add(nm)
        elif kind == "gv":
            exact.add(f"@gv:{nm}")
        elif kind == "query":
            prefixes.add(nm[0] + "(")
        elif kind == "var" and nm not in visiting:
            vi = vars_.get(nm)
            if vi is not None and vi.role == "wire":
                for d in defs.get(nm, []):
                    e2, p2 = _input_closure(d, vars_, defs, visiting | {nm})
                    exact |= e2
                    prefixes |= p2
    return exact, prefixes


# ── pure-subtree evaluator ───────────────────────────────────────────────────

class _Impure(Exception):
    pass


def _eval(node: Any, combo: dict, vars_: dict, defs: dict, env: dict,
          visiting: frozenset = frozenset()) -> Any:
    if isinstance(node, expr_mod.Lit):
        return node.value
    if isinstance(node, expr_mod.VarRef):
        nm = node.name
        if nm in env:
            return env[nm]
        if nm in visiting:
            raise _Impure()
        vi = vars_.get(nm)
        if vi is None:
            raise _Impure()
        if vi.role == "param":
            v = _fold_with_params(node, vars_)
            if v is None:
                raise _Impure()
            return v
        if vi.role == "wire" and not vi.timestamp:
            dl = defs.get(nm, [])
            if len(dl) != 1:
                raise _Impure()
            return _eval(dl[0], combo, vars_, defs, env, visiting | {nm})
        raise _Impure()
    if isinstance(node, (expr_mod.DeviceRef, expr_mod.QuantRef)) \
            or (isinstance(node, jp.CallExpr) and node.args is None):
        from .explore import _read_key
        k = _read_key(node)
        if k in combo:
            return combo[k]
        raise _Impure()
    if isinstance(node, jp.CallExpr):
        svc, m = canonical_key(node.service, node.method)
        if svc == "globalvariable" and m.startswith("get") \
                and isinstance(node.args[0], expr_mod.Lit):
            k = f"@gv:{node.args[0].value}"
            if k in combo:
                return combo[k]
            raise _Impure()
        from .interp import world_key
        base = world_key(node.tags, node.service, node.method)
        args = tuple(_eval(a, combo, vars_, defs, env, visiting)
                     for a in node.args)
        pk = f"{base}({','.join(map(repr, args))})"
        if pk in combo:
            return combo[pk]
        if base in combo:
            return combo[base]
        raise _Impure()
    if isinstance(node, expr_mod.UnaryOp):
        v = _eval(node.operand, combo, vars_, defs, env, visiting)
        return (not v) if node.op == "not" else -v
    if isinstance(node, expr_mod.FuncCall):
        vs = [_eval(a, combo, vars_, defs, env, visiting) for a in node.args]
        fn = {"abs": lambda: abs(vs[0]), "max": lambda: max(vs),
              "min": lambda: min(vs),
              "all": lambda: all(map(bool, vs)),
              "any": lambda: any(map(bool, vs)),
              "avg": lambda: sum(vs) / len(vs)}.get(node.name)
        if fn is None:
            raise _Impure()
        return fn()
    if isinstance(node, expr_mod.BinaryOp):
        op = node.op[:-1] if node.op.endswith("|") else node.op
        if op in ("and", "or"):
            a = _eval(node.left, combo, vars_, defs, env, visiting)
            b = _eval(node.right, combo, vars_, defs, env, visiting)
            return (bool(a) and bool(b)) if op == "and" else (bool(a) or bool(b))
        a = _eval(node.left, combo, vars_, defs, env, visiting)
        b = _eval(node.right, combo, vars_, defs, env, visiting)
        try:
            if op == "==":
                return a == b
            if op == "!=":
                return a != b
            if op == "<":
                return a < b
            if op == ">":
                return a > b
            if op == "<=":
                return a <= b
            if op == ">=":
                return a >= b
            if op == "+":
                if isinstance(a, str) or isinstance(b, str):
                    return str(a) + str(b)
                return (a or 0) + (b or 0)
            if op == "-":
                return (a or 0) - (b or 0)
            if op == "*":
                return (a or 0) * (b or 0)
            if op == "/":
                return (a or 0) / b if b else 0
            if op == "%":
                return (a or 0) % b if b else 0
        except TypeError:
            raise _Impure()
        raise _Impure()
    raise _Impure()


# ── signature construction ───────────────────────────────────────────────────

@dataclass
class DedupStats:
    before: int = 0
    after: int = 0
    n_sig_parts: int = 0
    n_raw_keys: int = 0


def _sig_builders(stmts: list, vars_: dict) -> tuple[list, set, set]:
    """(condition closures, raw exact keys, raw key prefixes)."""
    from .explore import _loop_ranges
    defs = var_defs(stmts)
    ranges = _loop_ranges(stmts, vars_, defs)
    closures: list[Callable] = []
    raw_exact: set = set()
    raw_pref: set = set()

    def _envs_for(node: Any) -> list[dict]:
        """Loop-var environments the expression depends on (via wires)."""
        reads: list = []
        _reads(node, reads)
        seen_vars = {nm for k, nm in reads if k == "var"}
        # follow single-def wires one level to catch fc -> forecast(h)
        for nm in list(seen_vars):
            vi = vars_.get(nm)
            if vi is not None and vi.role == "wire":
                for d in defs.get(nm, []):
                    r2: list = []
                    _reads(d, r2)
                    seen_vars |= {n2 for k2, n2 in r2 if k2 == "var"}
        lv = [nm for nm in sorted(seen_vars) if nm in ranges]
        if not lv:
            return [{}]
        if len(lv) > 1:
            return []                     # give up → impure path
        return [{lv[0]: i} for i in ranges[lv[0]]]

    def add_parts(node: Any) -> None:
        """Maximal pure subtrees become boolean closures; impure leaves
        surrender their input reads as raw keys."""
        envs = _envs_for(node)
        if envs:
            try:
                for env in envs:
                    _eval(node, _AllKeys(), vars_, defs, env)
                for env in envs:
                    closures.append(
                        lambda c, n=node, e=dict(env):
                        bool(_eval(n, c, vars_, defs, e)))
                return
            except _Impure:
                pass
        if isinstance(node, expr_mod.BinaryOp) and node.op in ("and", "or"):
            add_parts(node.left)
            add_parts(node.right)
            return
        if isinstance(node, expr_mod.UnaryOp) and node.op == "not":
            add_parts(node.operand)
            return
        e2, p2 = _input_closure(node, vars_, defs)
        raw_exact.update(e2)
        raw_pref.update(p2)

    for s in walk_stmts(stmts):
        if isinstance(s, (jp.IfStmt, jp.WaitUntil, jp.Loop)):
            add_parts(s.cond)
        # value flow: state assignments, action/GV-write arguments
        if isinstance(s, jp.Assign):
            vi = vars_.get(s.name)
            if vi is not None and vi.role == "state":
                e2, p2 = _input_closure(s.rhs, vars_, defs)
                raw_exact.update(e2)
                raw_pref.update(p2)
        if isinstance(s, jp.CallStmt):
            for a in (s.call.args or ()):
                e2, p2 = _input_closure(a, vars_, defs)
                raw_exact.update(e2)
                raw_pref.update(p2)
        if isinstance(s, jp.Assign) and isinstance(s.rhs, jp.CallExpr) \
                and s.rhs.args is not None:
            svc, m = canonical_key(s.rhs.service, s.rhs.method)
            if svc == "globalvariable" and m.startswith("set"):
                for a in s.rhs.args[1:]:
                    e2, p2 = _input_closure(a, vars_, defs)
                    raw_exact.update(e2)
                    raw_pref.update(p2)
    return closures, raw_exact, raw_pref


class _AllKeys(dict):
    """Purity probe: pretends every key exists (value 1) so _eval only
    raises _Impure for genuinely non-input reads."""
    def __contains__(self, k) -> bool:
        return True

    def __getitem__(self, k):
        return 1


def dedup_combos(programs: list[tuple[list, dict]], combos: list[dict]
                 ) -> tuple[list[dict], DedupStats]:
    st = DedupStats(before=len(combos))
    closures: list = []
    raw_exact: set = set()
    raw_pref: set = set()
    for stmts, vars_ in programs:
        c, e, p = _sig_builders(stmts, vars_)
        closures += c
        raw_exact |= e
        raw_pref |= p
    st.n_sig_parts = len(closures)

    def raw_part(combo: dict) -> tuple:
        out = []
        for k in sorted(combo):
            if k in raw_exact or any(k.startswith(p) for p in raw_pref):
                out.append((k, combo[k]))
        return tuple(out)

    seen: set = set()
    out: list[dict] = []
    for c in combos:
        try:
            sig = (tuple(f(c) for f in closures), raw_part(c))
        except _Impure:
            out.append(c)                # never drop on uncertainty
            continue
        if sig not in seen:
            seen.add(sig)
            out.append(c)
    st.after = len(out)
    st.n_raw_keys = len(raw_exact) + len(raw_pref)
    return out, st
