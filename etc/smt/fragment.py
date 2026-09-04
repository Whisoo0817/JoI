"""M0 — Fragment classifier for the SMT gate.

Walks every cached (IR, JoI) pair and classifies each into an encoder
fragment, so we know what the SMT encoder must support to reach a given
coverage before writing any Z3.

Execution-model class (from the JoI wrapper):
    ONESHOT        cron == "" and period == 0
    PERIODIC       cron == "" and period > 0
    CRON_ONESHOT   cron != "" and period == 0
    CRON_PERIODIC  cron != "" and period > 0

Expression/update flags (each pair may carry several):
    NONLINEAR_EXPR    var*var, var/var, %var — outside the linear fragment
    NONAFFINE_UPDATE  periodic per-tick update not affine in (vars, reads)
    STATE_FEEDBACK    a call's effect key is also read by the script/IR
    PIECEWISE         abs/min/max funcall (piecewise-linear — encodable, flagged)
    CALL_BIND         function-return capture `v = (#X).M(...)`
    STRING_ARG        string concat / interpolation in call args
    QUANTIFIER        any/all quantifier comparison in a condition

Verdict (what encoder milestone unlocks the pair):
    M1  ONESHOT, linear
    M2  PERIODIC, affine
    M3  CRON_*, linear/affine
    FAIL_CLOSED  NONLINEAR_EXPR or NONAFFINE_UPDATE anywhere
    PARSE_FAIL   JoI script does not parse / IR malformed

Usage:
    python3 -m etc.smt.fragment [--cache sensys/simulators/cache] [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sim import expr as expr_mod
from sim import joi_parser as jp

_DEFAULT_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")


# ── Expression linearity walk ────────────────────────────────────────────────

@dataclass
class ExprReport:
    linear: bool = True
    flags: set = field(default_factory=set)
    reads: set = field(default_factory=set)   # DeviceRef keys read


def _is_const(node) -> bool:
    return isinstance(node, expr_mod.Lit)


def _walk_expr(node, rep: ExprReport) -> None:
    """Classify one expression AST (shared expr nodes + joi_parser.CallExpr)."""
    if node is None or isinstance(node, expr_mod.Lit):
        return
    if isinstance(node, expr_mod.DeviceRef):
        rep.reads.add(node.key)
        return
    if isinstance(node, (expr_mod.ClockRef, expr_mod.VarRef)):
        return
    if isinstance(node, expr_mod.UnaryOp):
        _walk_expr(node.operand, rep)
        return
    if isinstance(node, expr_mod.BinaryOp):
        op = node.op
        if op == "*":
            if not (_is_const(node.left) or _is_const(node.right)):
                rep.linear = False
                rep.flags.add("NONLINEAR_EXPR")
        elif op in ("/", "%"):
            if not _is_const(node.right):
                rep.linear = False
                rep.flags.add("NONLINEAR_EXPR")
        elif op == "+":
            # String concat is linear-irrelevant but flagged (arg rendering).
            if _has_string_lit(node):
                rep.flags.add("STRING_ARG")
        _walk_expr(node.left, rep)
        _walk_expr(node.right, rep)
        return
    if isinstance(node, expr_mod.FuncCall):
        rep.flags.add("PIECEWISE")
        for a in node.args:
            _walk_expr(a, rep)
        return
    if isinstance(node, jp.CallExpr):
        if node.args is None:
            # attribute read — canonical key like DeviceRef
            svc, attr = expr_mod.canonical_key(node.service, node.method)
            rep.reads.add(f"{svc}.{attr}")
        else:
            rep.flags.add("CALL_BIND")
            for a in node.args:
                _walk_expr(a, rep)
        return
    # Unknown node type — be conservative.
    rep.linear = False
    rep.flags.add(f"UNKNOWN_NODE:{type(node).__name__}")


def _has_string_lit(node) -> bool:
    if isinstance(node, expr_mod.Lit):
        return isinstance(node.value, str)
    if isinstance(node, expr_mod.BinaryOp):
        return _has_string_lit(node.left) or _has_string_lit(node.right)
    return False


def _parse_ir_expr(src: str):
    """Parse an IR-side expression string ('$var', 'Service.Attr >= 5', ...)."""
    return expr_mod.parse(src)


# ── Effect keys (mirror of sensys.simulators.world.World.effect_key) ─────────

def _effect_key(service: str, method: str) -> str | None:
    svc = (service or "").lower()
    m = expr_mod.canonical_name(service, method)
    if m in ("on", "off", "toggle"):
        return f"{svc}.switch"
    if m.startswith("set") and m != "set":
        return f"{svc}.{m[3:]}"
    if m.startswith("moveto") and m != "movecolor":
        return f"{svc}.{m[6:]}"
    return None


# ── IR walk ──────────────────────────────────────────────────────────────────

@dataclass
class IRReport:
    ok: bool = True
    error: str = ""
    anchor: str = "now"
    cron: str = ""
    ops: Counter = field(default_factory=Counter)
    has_cycle: bool = False
    cycle_until: bool = False
    cycle_count: bool = False
    wait_edges: set = field(default_factory=set)
    wait_for: bool = False
    expr: ExprReport = field(default_factory=ExprReport)
    effect_keys: set = field(default_factory=set)


_EXPR_MARKERS = set("+-*/<>=!&|$")


def _walk_ir_steps(steps: list, rep: IRReport) -> None:
    for s in steps:
        if not isinstance(s, dict):
            rep.ok = False
            rep.error = "non-dict step"
            continue
        op = s.get("op")
        rep.ops[op] += 1
        if op == "wait":
            rep.wait_edges.add(s.get("edge", "none") or "none")
            if s.get("for"):
                rep.wait_for = True
            _ir_expr(s.get("cond", ""), rep)
        elif op == "if":
            _ir_expr(s.get("cond", ""), rep)
            _walk_ir_steps(s.get("then", []) or [], rep)
            _walk_ir_steps(s.get("else", []) or [], rep)
        elif op == "cycle":
            rep.has_cycle = True
            if s.get("until"):
                rep.cycle_until = True
                _ir_expr(s["until"], rep)
            if s.get("count"):
                rep.cycle_count = True
            _walk_ir_steps(s.get("body", []) or [], rep)
        elif op == "call":
            target = s.get("target", "")
            if isinstance(target, str) and "." in target:
                svc, _, m = target.partition(".")
                ek = _effect_key(svc, m)
                if ek:
                    rep.effect_keys.add(ek)
            for v in (s.get("args") or {}).values():
                if isinstance(v, str) and any(c in _EXPR_MARKERS for c in v):
                    _ir_expr(v, rep, tolerant=True)
        elif op == "read":
            _ir_expr(s.get("src", ""), rep, tolerant=True)


def _ir_expr(src: str, rep: IRReport, tolerant: bool = False) -> None:
    if not isinstance(src, str) or not src.strip():
        return
    try:
        ast = _parse_ir_expr(src)
    except Exception:
        if not tolerant:
            rep.ok = False
            rep.error = f"ir expr parse fail: {src!r}"
        return
    _walk_expr(ast, rep.expr)


def analyze_ir(ir: dict) -> IRReport:
    rep = IRReport()
    if not isinstance(ir, dict) or "timeline" not in ir or "error" in ir:
        rep.ok = False
        rep.error = "ir malformed or reject-path"
        return rep
    tl = ir["timeline"]
    head = tl[0] if tl else {}
    if isinstance(head, dict) and head.get("op") == "start_at":
        rep.anchor = head.get("anchor", "now")
        rep.cron = head.get("cron", "") if rep.anchor == "cron" else ""
        body = tl[1:]
    else:
        body = tl
    _walk_ir_steps(body, rep)
    return rep


# ── JoI walk ─────────────────────────────────────────────────────────────────

@dataclass
class JoIReport:
    ok: bool = True
    error: str = ""
    cron: str = ""
    period: int = 0
    persistent_vars: set = field(default_factory=set)
    expr: ExprReport = field(default_factory=ExprReport)
    effect_keys: set = field(default_factory=set)
    nonaffine_updates: set = field(default_factory=set)
    has_wait_until: bool = False
    has_delay: bool = False
    has_break: bool = False
    stmt_count: int = 0


def _affine_in_vars(node, rep: JoIReport) -> bool:
    """True iff expression is affine over (vars, device reads, clock).

    Sums/differences of atoms and const-scaled atoms; const-divisor / and %.
    """
    if node is None or isinstance(node, (expr_mod.Lit, expr_mod.DeviceRef,
                                         expr_mod.ClockRef, expr_mod.VarRef)):
        return True
    if isinstance(node, jp.CallExpr):
        return node.args is None  # attribute read is an atom; a call is not affine
    if isinstance(node, expr_mod.UnaryOp):
        return _affine_in_vars(node.operand, rep)
    if isinstance(node, expr_mod.BinaryOp):
        op = node.op
        if op in ("+", "-"):
            return _affine_in_vars(node.left, rep) and _affine_in_vars(node.right, rep)
        if op == "*":
            return (_is_const(node.left) and _affine_in_vars(node.right, rep)) or \
                   (_is_const(node.right) and _affine_in_vars(node.left, rep))
        if op in ("/", "%"):
            return _is_const(node.right) and _affine_in_vars(node.left, rep)
        # comparisons / and / or are boolean, not value updates
        return False
    if isinstance(node, expr_mod.FuncCall):
        return all(_affine_in_vars(a, rep) for a in node.args)  # piecewise-affine
    return False


def _walk_joi_stmts(stmts: list, rep: JoIReport) -> None:
    for s in stmts:
        rep.stmt_count += 1
        if isinstance(s, jp.Assign):
            if s.op == ":=":
                rep.persistent_vars.add(s.name)
            _walk_expr(s.rhs, rep.expr)
            # Direct function-return capture (`v = (#X).M(...)`) is an
            # uninterpreted-value bind, not arithmetic — CALL_BIND flag only.
            if isinstance(s.rhs, jp.CallExpr) and s.rhs.args is not None:
                pass
            elif not _affine_in_vars(s.rhs, rep):
                # boolean rhs (flag = cond) is fine; only flag value arithmetic
                is_bool = isinstance(s.rhs, expr_mod.BinaryOp) and \
                    s.rhs.op in ("==", "!=", "<", ">", "<=", ">=", "and", "or")
                if not is_bool:
                    rep.nonaffine_updates.add(s.name)
        elif isinstance(s, jp.IfStmt):
            _walk_expr(s.cond, rep.expr)
            _walk_joi_stmts(s.then_body, rep)
            _walk_joi_stmts(s.else_body or [], rep)
        elif isinstance(s, jp.WaitUntil):
            rep.has_wait_until = True
            _walk_expr(s.cond, rep.expr)
        elif isinstance(s, jp.Delay):
            rep.has_delay = True
        elif isinstance(s, jp.Break):
            rep.has_break = True
        elif isinstance(s, jp.CallStmt):
            ek = _effect_key(s.call.service, s.call.method)
            if ek:
                rep.effect_keys.add(ek)
            for a in (s.call.args or []):
                _walk_expr(a, rep.expr)


def analyze_joi(joi_block: dict) -> JoIReport:
    rep = JoIReport()
    rep.cron = (joi_block.get("cron") or "").strip()
    try:
        rep.period = int(joi_block.get("period", 0) or 0)
    except (TypeError, ValueError):
        rep.period = 0
    script = joi_block.get("script", "") or ""
    if not script.strip():
        rep.ok = False
        rep.error = "empty script"
        return rep
    try:
        stmts = jp.parse_script(script)
    except Exception as e:
        rep.ok = False
        rep.error = f"joi parse fail: {e}"
        return rep
    _walk_joi_stmts(stmts, rep)
    return rep


# ── Pair classification ──────────────────────────────────────────────────────

def classify_pair(ir: dict, joi_block: dict) -> dict:
    ir_rep = analyze_ir(ir)
    joi_rep = analyze_joi(joi_block)

    flags: set = set(ir_rep.expr.flags) | set(joi_rep.expr.flags)
    if joi_rep.nonaffine_updates:
        flags.add("NONAFFINE_UPDATE")

    # State feedback: any effect key (either side) also read (either side).
    reads = ir_rep.expr.reads | joi_rep.expr.reads
    effects = ir_rep.effect_keys | joi_rep.effect_keys
    if reads & effects:
        flags.add("STATE_FEEDBACK")

    if joi_rep.cron:
        exec_class = "CRON_PERIODIC" if joi_rep.period > 0 else "CRON_ONESHOT"
    else:
        exec_class = "PERIODIC" if joi_rep.period > 0 else "ONESHOT"

    if not joi_rep.ok or not ir_rep.ok:
        verdict = "PARSE_FAIL"
    elif "NONLINEAR_EXPR" in flags or "NONAFFINE_UPDATE" in flags:
        verdict = "FAIL_CLOSED"
    elif exec_class == "ONESHOT":
        verdict = "M1"
    elif exec_class == "PERIODIC":
        verdict = "M2"
    else:
        verdict = "M3"

    return {
        "exec_class": exec_class,
        "verdict": verdict,
        "flags": sorted(flags),
        "ir": {
            "ok": ir_rep.ok, "error": ir_rep.error,
            "anchor": ir_rep.anchor, "cron": ir_rep.cron,
            "ops": dict(ir_rep.ops),
            "cycle": ir_rep.has_cycle, "cycle_until": ir_rep.cycle_until,
            "cycle_count": ir_rep.cycle_count,
            "wait_edges": sorted(ir_rep.wait_edges), "wait_for": ir_rep.wait_for,
        },
        "joi": {
            "ok": joi_rep.ok, "error": joi_rep.error,
            "cron": joi_rep.cron, "period": joi_rep.period,
            "persistent_vars": sorted(joi_rep.persistent_vars),
            "nonaffine_updates": sorted(joi_rep.nonaffine_updates),
            "wait_until": joi_rep.has_wait_until, "delay": joi_rep.has_delay,
            "break": joi_rep.has_break, "stmts": joi_rep.stmt_count,
        },
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--cache", default=_DEFAULT_CACHE)
    ap.add_argument("--json", default=os.path.join(os.path.dirname(__file__), "results", "fragment_coverage.json"))
    args = ap.parse_args(argv)

    files = sorted(f for f in os.listdir(args.cache) if f.endswith(".json"))
    rows: dict = {}
    for fn in files:
        with open(os.path.join(args.cache, fn), encoding="utf-8") as f:
            pair = json.load(f)
        pid = fn[:-5]
        try:
            rows[pid] = classify_pair(pair.get("ir") or {}, pair.get("joi_block") or {})
        except Exception as e:  # classifier crash — record, keep going
            rows[pid] = {"exec_class": "?", "verdict": "CLASSIFIER_ERROR",
                         "flags": [], "error": f"{type(e).__name__}: {e}"}

    # ── aggregate ──
    by_verdict = Counter(r["verdict"] for r in rows.values())
    by_class = Counter(r["exec_class"] for r in rows.values())
    flag_count = Counter(fl for r in rows.values() for fl in r.get("flags", []))
    n = len(rows)

    print(f"pairs: {n}\n")
    print("verdict:")
    for k, v in by_verdict.most_common():
        print(f"  {k:<18} {v:>4}  ({v/n:5.1%})")
    print("\nexec class:")
    for k, v in by_class.most_common():
        print(f"  {k:<18} {v:>4}  ({v/n:5.1%})")
    print("\nflags (non-exclusive):")
    for k, v in flag_count.most_common():
        print(f"  {k:<18} {v:>4}")

    # cumulative coverage by milestone
    cum = 0
    print("\ncumulative encoder coverage:")
    for m in ("M1", "M2", "M3"):
        cum += by_verdict.get(m, 0)
        print(f"  through {m}: {cum:>4}  ({cum/n:5.1%})")

    # per-verdict examples & failure detail
    print("\nnon-supported detail:")
    for pid, r in rows.items():
        if r["verdict"] in ("PARSE_FAIL", "CLASSIFIER_ERROR"):
            err = r.get("error") or r.get("joi", {}).get("error") or r.get("ir", {}).get("error")
            print(f"  {pid}: {r['verdict']} — {err}")
    fc = [pid for pid, r in rows.items() if r["verdict"] == "FAIL_CLOSED"]
    if fc:
        print(f"\nFAIL_CLOSED rows ({len(fc)}): {', '.join(fc)}")

    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"\ndetail → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
