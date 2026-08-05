"""Static analysis for the explorer: variable roles + predicate fragment check.

Two questions, both answered from the AST alone (no execution):

1. Which variables are STATE? A variable's value carries to the next tick
   only if some read of it can happen before it is unconditionally
   overwritten in the body. Everything else is a wire (recomputed each tick,
   dead across ticks) or a param (`:=` init, never reassigned). Only state
   variables belong in the explorer's memoization key.

2. Is every comparison in the fragment? Each atomic comparison is classified
   (calendar / enum / threshold / timer / latch / counter / ...). Classes in
   the fragment admit exact discretization; anything else lands in REVIEW and
   is listed verbatim — that list is the honest boundary of the claim.

Run:  python -m simulator.predicates   (from /home/gnltnwjstk/joi)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from . import expr as expr_mod
from . import joi_parser as jp
from .expr import canonical_key

CMP_OPS = ("==", "!=", "<", ">", "<=", ">=",
           "==|", "!=|", "<|", ">|", "<=|", ">=|")  # OP| = exists-quantified
CAL_KEYS = ("clock.hour", "clock.minute", "clock.weekday", "clock.isholiday")
TS_KEY = "clock.timestamp"


# ── AST walking helpers ──────────────────────────────────────────────────────

def body_stmts(stmts: list) -> list:
    """Statements that run on every tick (`:=` initializers run only once)."""
    return [s for s in stmts
            if not (isinstance(s, jp.Assign) and s.op == ":=")]


def init_stmts(stmts: list) -> list[jp.Assign]:
    return [s for s in stmts if isinstance(s, jp.Assign) and s.op == ":="]


def expr_reads(node: Any, out: list) -> None:
    """Collect (kind, name) reads in an expression: var / device / call-read."""
    if isinstance(node, jp.CallExpr):
        svc, m = canonical_key(node.service, node.method)
        if node.args is None:
            out.append(("device", f"{svc}.{m}"))
        else:
            if svc == "globalvariable" and m.startswith("get"):
                a0 = node.args[0]
                nm = a0.value if isinstance(a0, expr_mod.Lit) else "?"
                out.append(("gv", str(nm)))
            else:
                out.append(("device", f"{svc}.{m}"))  # query read
            for a in node.args:
                expr_reads(a, out)
        return
    if isinstance(node, expr_mod.DeviceRef):
        out.append(("device", node.key))
    elif isinstance(node, expr_mod.ClockRef):
        out.append(("device", f"clock.{node.field.lower()}"))
    elif isinstance(node, expr_mod.VarRef):
        out.append(("var", node.name))
    elif isinstance(node, expr_mod.UnaryOp):
        expr_reads(node.operand, out)
    elif isinstance(node, expr_mod.BinaryOp):
        expr_reads(node.left, out)
        expr_reads(node.right, out)
    elif isinstance(node, expr_mod.FuncCall):
        for a in node.args:
            expr_reads(a, out)


def stmt_exprs(stmt: Any):
    """Expressions evaluated by a statement (cond first, then rhs/args)."""
    if isinstance(stmt, jp.Assign):
        yield stmt.rhs
    elif isinstance(stmt, jp.IfStmt):
        yield stmt.cond
    elif isinstance(stmt, (jp.WaitUntil, jp.Loop)):
        yield stmt.cond
    elif isinstance(stmt, jp.ForEach):
        yield stmt.source
    elif isinstance(stmt, jp.CallStmt):
        for a in (stmt.call.args or ()):
            yield a


def walk_stmts(stmts: list):
    for s in stmts:
        yield s
        if isinstance(s, jp.IfStmt):
            yield from walk_stmts(s.then_body)
            yield from walk_stmts(s.else_body or [])
        elif isinstance(s, (jp.Loop, jp.ForEach)):
            yield from walk_stmts(s.body)


# ── 1. Variable roles ────────────────────────────────────────────────────────

@dataclass
class VarInfo:
    role: str                 # "param" | "state" | "wire" | "dead"
    init: Any = None          # folded init value for params (None if n/a)
    timestamp: bool = False   # holds clock.timestamp-derived values


def _const_fold(node: Any) -> Any:
    """Fold literal-only arithmetic (e.g. `3600 * 3`); None if not constant."""
    if isinstance(node, expr_mod.Lit):
        return node.value
    if isinstance(node, expr_mod.UnaryOp) and node.op == "-":
        v = _const_fold(node.operand)
        return -v if isinstance(v, (int, float)) else None
    if isinstance(node, expr_mod.BinaryOp) and node.op in ("+", "-", "*", "/"):
        a, b = _const_fold(node.left), _const_fold(node.right)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return {"+": a + b, "-": a - b, "*": a * b,
                    "/": a / b if b else None}[node.op]
    return None


def classify_vars(stmts: list) -> dict[str, VarInfo]:
    body = body_stmts(stmts)
    inits = init_stmts(stmts)
    assigned_in_body: set[str] = set()
    for s in walk_stmts(body):
        if isinstance(s, jp.Assign):
            assigned_in_body.add(s.name)

    # Read-before-write scan, path-local: a var read before any write ON THE
    # CURRENT PATH may observe last tick's value → carried. Writes inside a
    # branch make later reads *within that branch* safe, but don't survive
    # past it (the branch may not run next tick). Loop bodies scan like a
    # branch: an iteration-1 read before the in-body write is the danger case.
    carried: set[str] = set()

    def scan(stmts_: list, safe: set[str]) -> None:
        for s in stmts_:
            for e in stmt_exprs(s):
                reads: list = []
                expr_reads(e, reads)
                for k, nm in reads:
                    if k == "var" and nm not in safe:
                        carried.add(nm)
            if isinstance(s, jp.Assign):
                safe.add(s.name)
            elif isinstance(s, jp.IfStmt):
                scan(s.then_body, set(safe))
                scan(s.else_body or [], set(safe))
            elif isinstance(s, jp.Loop):
                scan(s.body, set(safe))
            elif isinstance(s, jp.ForEach):
                scan(s.body, set(safe) | {s.var})

    scan(body, set())

    # Timestamp typing: fixpoint over assigns whose rhs reads clock.timestamp
    # or another timestamp var.
    ts_vars: set[str] = set()
    for _ in range(3):
        for s in walk_stmts(stmts):
            if not isinstance(s, jp.Assign):
                continue
            reads: list = []
            expr_reads(s.rhs, reads)
            if any((k == "device" and nm == TS_KEY) or (k == "var" and nm in ts_vars)
                   for k, nm in reads):
                ts_vars.add(s.name)

    out: dict[str, VarInfo] = {}
    init_names = {s.name for s in inits}
    all_names = init_names | assigned_in_body
    for nm in sorted(all_names):
        init_node = next((s.rhs for s in inits if s.name == nm), None)
        if nm not in assigned_in_body:
            # `:=` only: param if read somewhere, else dead
            role = "param" if nm in carried else "dead"
            out[nm] = VarInfo(role, _const_fold(init_node) if init_node else None,
                              nm in ts_vars)
        else:
            role = "state" if nm in carried else "wire"
            out[nm] = VarInfo(role, _const_fold(init_node) if init_node else None,
                              nm in ts_vars)
    return out


# ── 2. Predicate extraction + fragment classification ────────────────────────

@dataclass
class Pred:
    text: str
    klass: str      # CAL ENUM THRESH TIMER TIMER_SENTINEL LATCH COUNT
                    # WIREBOOL GV_ENUM LINEAR REVIEW
    where: str      # cond | assign


def unparse(node: Any) -> str:
    if isinstance(node, expr_mod.Lit):
        return repr(node.value)
    if isinstance(node, expr_mod.VarRef):
        return node.name
    if isinstance(node, expr_mod.DeviceRef):
        return node.key
    if isinstance(node, expr_mod.ClockRef):
        return f"clock.{node.field}"
    if isinstance(node, expr_mod.UnaryOp):
        return f"{node.op}({unparse(node.operand)})"
    if isinstance(node, expr_mod.BinaryOp):
        return f"({unparse(node.left)} {node.op} {unparse(node.right)})"
    if isinstance(node, expr_mod.FuncCall):
        return f"{node.name}({', '.join(unparse(a) for a in node.args)})"
    if isinstance(node, jp.CallExpr):
        svc, m = canonical_key(node.service, node.method)
        if node.args is None:
            return f"{svc}.{m}"
        return f"{svc}.{m}({', '.join(unparse(a) for a in node.args)})"
    return f"<{type(node).__name__}>"


def _atoms(node: Any, out: list, where: str) -> None:
    """Atomic comparisons inside a boolean expression."""
    if isinstance(node, expr_mod.BinaryOp):
        if node.op in ("and", "or"):
            _atoms(node.left, out, where)
            _atoms(node.right, out, where)
            return
        if node.op in CMP_OPS:
            out.append((node, where))
            return
    if isinstance(node, expr_mod.UnaryOp) and node.op == "not":
        _atoms(node.operand, out, where)


def collect_comparisons(stmts: list) -> list[tuple[Any, str]]:
    out: list = []
    for s in walk_stmts(stmts):
        if isinstance(s, (jp.IfStmt, jp.WaitUntil, jp.Loop)):
            _atoms(s.cond, out, "cond")
        if isinstance(s, jp.Assign):
            _atoms(s.rhs, out, "assign")
    return out


def _fold_with_params(node: Any, vars_: dict[str, VarInfo]) -> Any:
    """Const-fold, treating params as their init values (st_pm10/2 → const)."""
    if isinstance(node, expr_mod.Lit):
        return node.value
    if isinstance(node, expr_mod.VarRef):
        vi = vars_.get(node.name)
        if vi is not None and vi.role == "param" and vi.init is not None:
            return vi.init
        return None
    if isinstance(node, expr_mod.UnaryOp) and node.op == "-":
        v = _fold_with_params(node.operand, vars_)
        return -v if isinstance(v, (int, float)) else None
    if isinstance(node, expr_mod.BinaryOp) and node.op in ("+", "-", "*", "/"):
        a = _fold_with_params(node.left, vars_)
        b = _fold_with_params(node.right, vars_)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return {"+": a + b, "-": a - b, "*": a * b,
                    "/": a / b if b else None}[node.op]
    return None


def _side_kind(node: Any, vars_: dict[str, VarInfo],
               defs: dict[str, list], depth: int = 0) -> tuple[str, Any]:
    """('const', v) ('cal', key) ('ts', _) ('tsdiff', _) ('sensor', key)
    ('gv', name) ('reg', name) ('regnum', name) ('linexpr', _) ('other', _)"""
    folded = _fold_with_params(node, vars_)
    if folded is not None:
        return ("const", folded)
    if isinstance(node, expr_mod.Lit):
        return ("const", node.value)
    if isinstance(node, expr_mod.ClockRef):
        f = node.field.lower()
        return ("ts", None) if f == "timestamp" else ("cal", f"clock.{f}")
    if isinstance(node, expr_mod.DeviceRef):
        if node.key in CAL_KEYS:
            return ("cal", node.key)
        if node.key == TS_KEY:
            return ("ts", None)
        return ("sensor", node.key)
    if isinstance(node, jp.CallExpr):
        svc, m = canonical_key(node.service, node.method)
        if svc == "globalvariable":
            return ("gv", None)
        if svc == "clock":
            return ("ts", None) if m == "timestamp" else ("cal", f"clock.{m}")
        return ("sensor", f"{svc}.{m}")
    if isinstance(node, expr_mod.VarRef):
        vi = vars_.get(node.name)
        if vi is None:
            return ("other", node.name)
        if vi.role == "param":
            return ("const", vi.init)
        if vi.timestamp:
            return ("ts", node.name)
        if vi.role == "state":
            # numeric carried register (bool latches stay 'reg')
            return ("reg", node.name)
        # wire: single definition → substitute and reclassify; multiple
        # definitions → affine check over current-tick reads
        dlist = defs.get(node.name, [])
        if len(dlist) == 1 and depth < 4:
            return _side_kind(dlist[0], vars_, defs, depth + 1)
        if dlist and all(_is_affine(d, vars_, defs) for d in dlist):
            return ("linexpr", node.name)
        return ("other", node.name)
    if isinstance(node, expr_mod.BinaryOp):
        if node.op == "-":
            lk, _ = _side_kind(node.left, vars_, defs, depth + 1)
            rk, _ = _side_kind(node.right, vars_, defs, depth + 1)
            if lk == "ts" and rk == "ts":
                return ("tsdiff", None)
        if _is_affine(node, vars_, defs):
            return ("linexpr", None)
    return ("other", None)


def _is_affine(node: Any, vars_: dict[str, VarInfo],
               defs: dict[str, list], depth: int = 0,
               visiting: frozenset = frozenset()) -> bool:
    """Linear over current-tick reads: sensors, wires, +/-, ×÷ by constants.
    Self-referential wires (intra-tick loop counters like `h = h + 1`) are
    accepted on revisit — every one of their defs is checked once anyway."""
    if depth > 8:
        return False
    if _fold_with_params(node, vars_) is not None:
        return True
    if isinstance(node, (expr_mod.Lit, expr_mod.DeviceRef)):
        return True
    if isinstance(node, jp.CallExpr):
        return True  # a read (query) — a current-tick input
    if isinstance(node, expr_mod.VarRef):
        vi = vars_.get(node.name)
        if vi is None or vi.role == "param":
            return True
        if node.name in visiting:
            return True  # self-referential intra-tick counter
        if vi.role == "wire":
            v2 = visiting | {node.name}
            return all(_is_affine(d, vars_, defs, depth + 1, v2)
                       for d in defs.get(node.name, [expr_mod.Lit(None)]))
        return False  # state var → not a pure current-tick expression
    if isinstance(node, expr_mod.UnaryOp):
        return _is_affine(node.operand, vars_, defs, depth + 1, visiting)
    if isinstance(node, expr_mod.BinaryOp):
        if node.op in ("+", "-"):
            return (_is_affine(node.left, vars_, defs, depth + 1, visiting)
                    and _is_affine(node.right, vars_, defs, depth + 1, visiting))
        if node.op in ("*", "/"):
            lc = _fold_with_params(node.left, vars_) is not None
            rc = _fold_with_params(node.right, vars_) is not None
            if node.op == "*" and not (lc or rc):
                return False
            if node.op == "/" and not rc:
                return False
            return (_is_affine(node.left, vars_, defs, depth + 1, visiting)
                    and _is_affine(node.right, vars_, defs, depth + 1, visiting))
    return False


def classify_comparison(node: Any, vars_: dict[str, VarInfo],
                        wire_bool: set[str], defs: dict[str, list],
                        where: str) -> Pred:
    text = unparse(node)
    lk, lv = _side_kind(node.left, vars_, defs)
    rk, rv = _side_kind(node.right, vars_, defs)
    # normalize: const on the right
    if lk == "const" and rk != "const":
        lk, lv, rk, rv = rk, rv, lk, lv
    k = None
    if rk == "const":
        if lk == "cal":
            k = "CAL"
        elif lk == "tsdiff":
            k = "TIMER"
        elif lk == "ts":
            k = "TIMER_SENTINEL"     # e.g. grace_start == 0
        elif lk == "sensor":
            k = "ENUM" if isinstance(rv, (str, bool)) or rv is None else "THRESH"
        elif lk == "gv":
            k = "GV_ENUM"
        elif lk == "reg":
            vi = vars_.get(lv) if isinstance(lv, str) else None
            if isinstance(rv, bool):
                k = "LATCH"
            elif vi is not None and _reg_is_counter(lv, defs, vars_):
                k = "COUNT"
            else:
                k = "REG_NUM"        # carried numeric register vs const
        elif lk == "linexpr":
            k = "LINEAR"
    elif {lk, rk} <= {"reg", "linexpr", "sensor"}:
        k = "LINEAR"                 # current-tick linear relation
    if k is None:
        # Pure function of current-tick sensor readings (avg/max over a
        # ForEach scan): after grounding unrolls the scan over k devices,
        # the expression becomes (piecewise-)linear → fragment class ③.
        if _sensor_only(node.left, vars_, defs) and \
                _sensor_only(node.right, vars_, defs):
            k = "GROUND"
        else:
            k = "REVIEW"
    return Pred(text, k, where)


def _sensor_only(node: Any, vars_: dict[str, VarInfo],
                 defs: dict[str, list], visiting: frozenset = frozenset()) -> bool:
    """All transitive reads are device readings or constants — no state, gv,
    calendar, or timestamp involvement. Self-referential accumulators
    (`sum = sum + v` in a ForEach scan) are accepted on revisit."""
    reads: list = []
    expr_reads(node, reads)
    for kind, nm in reads:
        if kind == "gv":
            return False
        if kind == "device":
            if nm in CAL_KEYS or nm == TS_KEY:
                return False
            continue
        if kind == "var":
            if nm in visiting:
                continue
            vi = vars_.get(nm)
            if vi is None:
                continue  # ForEach iteration var — a device reading
            if vi.role == "param":
                continue
            if vi.role != "wire" or vi.timestamp:
                return False
            v2 = visiting | {nm}
            if not all(_sensor_only(d, vars_, defs, v2)
                       for d in defs.get(nm, [])):
                return False
    return True


def _reg_is_counter(name: str, defs: dict[str, list],
                    vars_: dict[str, VarInfo]) -> bool:
    """State var whose updates are `= const` or `= self ± const` (a counter,
    bounded in the explorer by the constants it is compared against)."""
    for d in defs.get(name, []):
        if _fold_with_params(d, vars_) is not None:
            continue
        if (isinstance(d, expr_mod.BinaryOp) and d.op in ("+", "-")
                and isinstance(d.left, expr_mod.VarRef) and d.left.name == name
                and _fold_with_params(d.right, vars_) is not None):
            continue
        return False
    return True


def bool_wires(stmts: list, vars_: dict[str, VarInfo]) -> set[str]:
    """Wires assigned only boolean literals / boolean expressions."""
    cand: dict[str, bool] = {}
    for s in walk_stmts(stmts):
        if isinstance(s, jp.Assign) and vars_.get(s.name, VarInfo("x")).role in ("wire", "state"):
            r = s.rhs
            is_bool = (isinstance(r, expr_mod.Lit) and isinstance(r.value, bool)) or \
                      (isinstance(r, expr_mod.BinaryOp) and r.op in
                       ("and", "or") + CMP_OPS) or \
                      (isinstance(r, expr_mod.UnaryOp) and r.op == "not")
            cand[s.name] = cand.get(s.name, True) and is_bool
    return {n for n, ok in cand.items() if ok}


FRAGMENT = {"CAL", "ENUM", "THRESH", "TIMER", "TIMER_SENTINEL",
            "LATCH", "COUNT", "WIREBOOL", "GV_ENUM", "LINEAR"}
# REG_NUM (carried numeric register, e.g. a held average) is fragment-eligible
# only after grounding makes its update linear — reported separately, not
# counted in the headline coverage.


# ── Report ───────────────────────────────────────────────────────────────────

def var_defs(stmts: list) -> dict[str, list]:
    """Every `=` rhs per variable (wire substitution / counter detection)."""
    out: dict[str, list] = {}
    for s in walk_stmts(body_stmts(stmts)):
        if isinstance(s, jp.Assign):
            out.setdefault(s.name, []).append(s.rhs)
    return out


def analyze(name: str, src: str) -> dict:
    stmts = jp.parse_script(src)
    vars_ = classify_vars(stmts)
    wb = bool_wires(stmts, vars_)
    defs = var_defs(stmts)
    preds = [classify_comparison(n, vars_, wb, defs, w)
             for n, w in collect_comparisons(stmts)]
    n_state = sum(1 for v in vars_.values() if v.role == "state")
    n_ts = sum(1 for v in vars_.values() if v.role == "state" and v.timestamp)
    n_bool = sum(1 for nm, v in vars_.items()
                 if v.role == "state" and not v.timestamp)
    in_frag = sum(1 for p in preds if p.klass in FRAGMENT)
    return {"name": name, "vars": vars_, "preds": preds,
            "n_state": n_state, "n_ts": n_ts, "n_bool_or_num": n_bool,
            "in_frag": in_frag, "total": len(preds)}


def main() -> None:
    data = json.load(open("paper_v2/joi_automation_codes.json"))
    grand_in = grand_tot = 0
    reviews: list[tuple[str, Pred]] = []
    print(f"{'시나리오':26s} {'state(ts)':>9s} {'술어':>4s} {'단편내':>5s}  클래스 분포")
    for s in data:
        r = analyze(s["name"], s["code"])
        dist: dict[str, int] = {}
        for p in r["preds"]:
            dist[p.klass] = dist.get(p.klass, 0) + 1
        grand_in += r["in_frag"]
        grand_tot += r["total"]
        for p in r["preds"]:
            if p.klass in ("REVIEW", "REG_NUM", "GROUND"):
                reviews.append((s["name"], p))
        dstr = " ".join(f"{k}:{v}" for k, v in sorted(dist.items()))
        print(f"{r['name'][:24]:26s} {r['n_state']:>4d}({r['n_ts']})"
              f" {r['total']:>5d} {r['in_frag']:>5d}  {dstr}")
    pct = 100.0 * grand_in / grand_tot if grand_tot else 0.0
    n_ground = sum(1 for _, p in reviews if p.klass == "GROUND")
    n_review = sum(1 for _, p in reviews if p.klass == "REVIEW")
    print(f"\n단편 커버리지: {grand_in}/{grand_tot} = {pct:.1f}% 즉시"
          f" + GROUND {n_ground}건(그라운딩 후 선형=단편 ③)"
          f" + 잔여 REVIEW {n_review}건")
    if reviews:
        print("\nGROUND/REVIEW 상세:")
        for nm, p in reviews:
            print(f"  [{nm[:20]}] {p.klass:8s} {p.text}   ({p.where})")

    print("\n각 시나리오 상태 변수 상세:")
    for s in data:
        r = analyze(s["name"], s["code"])
        items = [f"{nm}{'(ts)' if vi.timestamp else ''}"
                 for nm, vi in r["vars"].items() if vi.role == "state"]
        print(f"  {r['name'][:24]:26s} {', '.join(items) if items else '-'}")


if __name__ == "__main__":
    main()
