"""M2.6 — certified template library (feasibility).

A certified template is (JoI skeleton, IR skeleton, relational invariant,
offline z3 proof, side conditions). The proof is TICK-INDUCTIVE and
parametric in the slots:

    INIT: invariant holds at tick 0 (quiescent side condition)
    STEP: invariant ∧ tick-abstraction ⟹ invariant' ∧ per-interval
          output agreement (JoI emission at the tick ⟺ IR emission inside
          the tick interval; time skew ≤ one period ≤ φ tolerance)

The tick abstraction is where the input assumption (phases ≥ period) is
consumed: a phase-constant input changes at most once per tick interval,
so the pair of boundary samples (c_prev, c_now) fully determines interval
behavior. The proof quantifies over abstract boolean/int streams — the
fact that BOTH sides read the same condition and emit the same actions is
discharged syntactically by the matcher, not by the solver.

Online verification = matching only (no solver): skeleton match + slot
compatibility ⟹ proof inheritance. Anything that fails to match (every
mutation does, by construction) falls back to the SMT gate — the library
is fail-closed by matching.

Templates: D-3 (rising-edge triggered flag), B-2 (stateless periodic),
D-10cw (cycle-wrapped sustain counter).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import z3

from sim import expr as E
from sim import joi_parser as jp
from sim.catalog import get_arg_order
from sim.timeline_ir import parse_duration_to_ms
from sim.traces import normalize_value


# ── expression / call normal-form comparison ────────────────────────────────

def expr_equal(a, b, bind: dict) -> bool:
    """Structural equality of parsed cond ASTs (shared node types), with a
    variable-rename binding map (IR read var ↔ JoI assign var)."""
    if isinstance(a, E.Lit) and isinstance(b, E.Lit):
        return normalize_value(a.value) == normalize_value(b.value)
    if isinstance(a, E.DeviceRef) and isinstance(b, E.DeviceRef):
        return a.key == b.key
    if isinstance(a, E.VarRef) and isinstance(b, E.VarRef):
        if a.name in bind:
            return bind[a.name] == b.name
        bind[a.name] = b.name
        return True
    if isinstance(a, E.ClockRef) and isinstance(b, E.ClockRef):
        return a.field == b.field
    if isinstance(a, E.UnaryOp) and isinstance(b, E.UnaryOp):
        return a.op == b.op and expr_equal(a.operand, b.operand, bind)
    if isinstance(a, E.BinaryOp) and isinstance(b, E.BinaryOp):
        if a.op != b.op:
            return False
        return expr_equal(a.left, b.left, bind) and expr_equal(a.right, b.right, bind)
    if isinstance(a, E.FuncCall) and isinstance(b, E.FuncCall):
        return a.name == b.name and len(a.args) == len(b.args) and \
            all(expr_equal(x, y, bind) for x, y in zip(a.args, b.args))
    # JoI attribute reads arrive as DeviceRef already (joi_parser canonicalizes)
    return False


def _canon_call_joi(cs: jp.CallStmt) -> Optional[tuple]:
    svc, m = E.canonical_key(cs.call.service, cs.call.method)
    args = []
    for a in (cs.call.args or []):
        if not isinstance(a, E.Lit):
            return None            # non-literal args → not certifiable (v0)
        args.append(normalize_value(a.value))
    return (m, tuple(args))


def _canon_call_ir(step: dict, catalog) -> Optional[tuple]:
    target = step.get("target", "")
    svc, _, method = target.partition(".")
    svc_c, m = E.canonical_key(svc, method)
    named = step.get("args") or {}
    order = get_arg_order(catalog, svc, method)
    keys = ([k for k in order if k in named] +
            sorted(k for k in named if k not in (order or []))) if order \
        else sorted(named)
    args = []
    for k in keys:
        v = named[k]
        if isinstance(v, str) and any(c in "+-*/<>=!&|$" for c in v):
            return None            # expression arg → not certifiable (v0)
        args.append(normalize_value(v))
    return (m, tuple(args))


# ── match result ─────────────────────────────────────────────────────────────

@dataclass
class Cert:
    template: str
    slots: dict
    assumptions: list = field(default_factory=list)


class NoMatch(Exception):
    pass


def _ir_parts(ir: dict):
    tl = ir.get("timeline", [])
    if not tl or tl[0].get("op") != "start_at" or tl[0].get("anchor") != "now":
        raise NoMatch("not start_at(now)")
    return tl[1:]


def _single_cycle(steps: list) -> dict:
    if len(steps) != 1 or steps[0].get("op") != "cycle":
        raise NoMatch("not a single top-level cycle")
    c = steps[0]
    if c.get("until") is not None or c.get("count"):
        raise NoMatch("cycle has until/count")
    return c


def _is_eq_false(node, var: str) -> bool:
    return isinstance(node, E.BinaryOp) and node.op == "==" and \
        isinstance(node.left, E.VarRef) and node.left.name == var and \
        isinstance(node.right, E.Lit) and node.right.value is False


# ── D-3 matcher ──────────────────────────────────────────────────────────────

def match_d3(ir: dict, joi_block: dict, catalog) -> Cert:
    period = int(joi_block.get("period", 0) or 0)
    if (joi_block.get("cron") or "").strip() or period <= 0:
        raise NoMatch("not periodic")
    stmts = jp.parse_script(joi_block.get("script", "") or "")
    if len(stmts) != 2 or not isinstance(stmts[0], jp.Assign) \
            or stmts[0].op != ":=" \
            or not (isinstance(stmts[0].rhs, E.Lit) and stmts[0].rhs.value is False):
        raise NoMatch("no `flag := false` prelude")
    flag = stmts[0].name
    outer = stmts[1]
    if not isinstance(outer, jp.IfStmt) or len(outer.then_body) != 1 \
            or len(outer.else_body) != 1:
        raise NoMatch("outer if shape")
    inner = outer.then_body[0]
    els = outer.else_body[0]
    if not (isinstance(els, jp.Assign) and els.name == flag and els.op == "="
            and isinstance(els.rhs, E.Lit) and els.rhs.value is False):
        raise NoMatch("else branch is not flag reset")
    if not isinstance(inner, jp.IfStmt) or inner.else_body:
        raise NoMatch("inner if shape")
    if not _is_eq_false(inner.cond, flag):
        raise NoMatch("inner guard is not flag == false")
    body = inner.then_body
    if not body or not (isinstance(body[-1], jp.Assign) and body[-1].name == flag
                        and isinstance(body[-1].rhs, E.Lit)
                        and body[-1].rhs.value is True):
        raise NoMatch("no flag = true terminator")
    calls_joi = []
    for s in body[:-1]:
        if not isinstance(s, jp.CallStmt):
            raise NoMatch("non-call in Y block")
        c = _canon_call_joi(s)
        if c is None:
            raise NoMatch("non-literal call args")
        calls_joi.append(c)

    cyc = _single_cycle(_ir_parts(ir))
    b = cyc.get("body") or []
    if not b or b[0].get("op") != "wait" or b[0].get("edge") != "rising" \
            or b[0].get("for"):
        raise NoMatch("IR body[0] is not wait(rising)")
    cond_ir = E.parse(b[0].get("cond", ""))
    if not expr_equal(cond_ir, outer.cond, {}):
        raise NoMatch("cond mismatch IR↔JoI")
    calls_ir = []
    for s in b[1:]:
        if s.get("op") != "call":
            raise NoMatch("non-call after wait in IR body")
        c = _canon_call_ir(s, catalog)
        if c is None:
            raise NoMatch("IR expression arg")
        calls_ir.append(c)
    if calls_ir != calls_joi:
        raise NoMatch("action mismatch IR↔JoI")
    return Cert("D-3", {"flag": flag, "period": period, "calls": calls_joi},
                ["quiescent start (cond false at t=0)",
                 "input phases >= period", "tolerance >= period + 1s"])


# ── D-4 matcher ──────────────────────────────────────────────────────────────

def match_d4(ir: dict, joi_block: dict, catalog) -> Cert:
    """Prefix-wait phase machine: `phase := 0; if (phase == 0) { wait
    until(cond); phase = 1; CALLS } else { CALLS }` ↔ IR `wait(cond,
    level); cycle(P) { CALLS }`. v0 restrictions (each excludes a class
    that genuinely diverges under φ in the corpus): CALLS are literal
    calls only — no delay in the JoI body (tick-cadence drift, C12_005),
    no if-guarded body (cross-key sampling-offset divergence, C12_003) —
    and the first-fire block must equal the repeat block (C12_004)."""
    period = int(joi_block.get("period", 0) or 0)
    if (joi_block.get("cron") or "").strip() or period <= 0:
        raise NoMatch("not periodic")
    stmts = jp.parse_script(joi_block.get("script", "") or "")
    if len(stmts) != 2 or not isinstance(stmts[0], jp.Assign) \
            or stmts[0].op != ":=" \
            or not (isinstance(stmts[0].rhs, E.Lit) and stmts[0].rhs.value == 0):
        raise NoMatch("no `phase := 0` prelude")
    phase = stmts[0].name
    outer = stmts[1]
    if not isinstance(outer, jp.IfStmt) or not outer.else_body:
        raise NoMatch("outer if shape")
    oc = outer.cond
    if not (isinstance(oc, E.BinaryOp) and oc.op == "=="
            and isinstance(oc.left, E.VarRef) and oc.left.name == phase
            and isinstance(oc.right, E.Lit) and oc.right.value == 0):
        raise NoMatch("outer guard is not phase == 0")
    tb = outer.then_body
    if len(tb) < 3 or not isinstance(tb[0], jp.WaitUntil):
        raise NoMatch("then branch is not wait-first")
    if not (isinstance(tb[1], jp.Assign) and tb[1].name == phase
            and tb[1].op == "=" and isinstance(tb[1].rhs, E.Lit)
            and tb[1].rhs.value == 1):
        raise NoMatch("no phase = 1 latch")

    def _calls(ss, what):
        out = []
        for s in ss:
            if not isinstance(s, jp.CallStmt):
                raise NoMatch(f"non-call in {what} block")
            c = _canon_call_joi(s)
            if c is None:
                raise NoMatch("non-literal call args")
            out.append(c)
        return out

    calls_first = _calls(tb[2:], "first")
    calls_rep = _calls(outer.else_body, "repeat")
    if not calls_rep or calls_first != calls_rep:
        raise NoMatch("first-fire block != repeat block")

    parts = _ir_parts(ir)
    if len(parts) != 2 or parts[0].get("op") != "wait":
        raise NoMatch("IR is not wait; cycle")
    w = parts[0]
    if (w.get("edge") or "none") != "none" or w.get("for"):
        raise NoMatch("IR wait is not a plain level wait")
    if not expr_equal(E.parse(w.get("cond", "")), tb[0].cond, {}):
        raise NoMatch("cond mismatch IR↔JoI")
    cyc = _single_cycle(parts[1:])
    if parse_duration_to_ms(cyc.get("period", "0 MSEC")) != period:
        raise NoMatch("period mismatch")
    body = list(cyc.get("body") or [])
    # a trailing delay <= period is cadence-neutral (pad-to-period absorbs it)
    if body and body[-1].get("op") == "delay":
        if parse_duration_to_ms(body[-1].get("duration", "0 MSEC")) > period:
            raise NoMatch("trailing delay exceeds period")
        body = body[:-1]
    calls_ir = []
    for s in body:
        if s.get("op") != "call":
            raise NoMatch("non-call in IR cycle body")
        c = _canon_call_ir(s, catalog)
        if c is None:
            raise NoMatch("IR expression arg")
        calls_ir.append(c)
    if calls_ir != calls_rep:
        raise NoMatch("action mismatch IR↔JoI")
    return Cert("D-4", {"phase": phase, "period": period, "calls": calls_rep},
                ["input phases >= period", "tolerance >= period + 1s"])


# ── B-2 matcher ──────────────────────────────────────────────────────────────

def _b2_body_equal(joi_stmts: list, ir_steps: list, catalog, bind: dict) -> bool:
    js = [s for s in joi_stmts]
    irs = [s for s in ir_steps if not (s.get("op") == "delay")]  # cadence delay
    if len(js) != len(irs):
        return False
    for s, t in zip(js, irs):
        if isinstance(s, jp.CallStmt) and t.get("op") == "call":
            if _canon_call_joi(s) is None or \
                    _canon_call_joi(s) != _canon_call_ir(t, catalog):
                return False
        elif isinstance(s, jp.Assign) and s.op == "=" and t.get("op") == "read":
            if not isinstance(s.rhs, (E.DeviceRef,)):
                return False
            if not expr_equal(E.parse(t.get("src", "")), s.rhs, bind):
                return False
            bind[t.get("var")] = s.name
        elif isinstance(s, jp.IfStmt) and t.get("op") == "if":
            if not expr_equal(E.parse(t.get("cond", "")), s.cond, bind):
                return False
            if not _b2_body_equal(s.then_body, t.get("then", []) or [], catalog, bind):
                return False
            if not _b2_body_equal(s.else_body or [], t.get("else", []) or [], catalog, bind):
                return False
        else:
            return False
    return True


def match_b2(ir: dict, joi_block: dict, catalog) -> Cert:
    period = int(joi_block.get("period", 0) or 0)
    if (joi_block.get("cron") or "").strip() or period <= 0:
        raise NoMatch("not periodic")
    stmts = jp.parse_script(joi_block.get("script", "") or "")

    def stateless(ss):
        for s in ss:
            if isinstance(s, (jp.WaitUntil, jp.Break, jp.Delay)):
                return False
            if isinstance(s, jp.Assign) and s.op == ":=":
                return False
            if isinstance(s, jp.IfStmt):
                if not stateless(s.then_body) or not stateless(s.else_body or []):
                    return False
        return True

    if not stateless(stmts):
        raise NoMatch("stateful script")
    cyc = _single_cycle(_ir_parts(ir))
    if parse_duration_to_ms(cyc.get("period", "0 MSEC")) != period:
        raise NoMatch("period mismatch")
    if any(isinstance(b, dict) and b.get("op") == "wait" for b in cyc.get("body") or []):
        raise NoMatch("IR body has wait")
    if not _b2_body_equal(stmts, cyc.get("body") or [], catalog, {}):
        raise NoMatch("body mismatch IR↔JoI")
    return Cert("B-2", {"period": period},
                ["input phases >= period", "tolerance >= period + 1s"])


# ── D-10cw matcher ───────────────────────────────────────────────────────────

def match_d10cw(ir: dict, joi_block: dict, catalog) -> Cert:
    period = int(joi_block.get("period", 0) or 0)
    if (joi_block.get("cron") or "").strip() or period <= 0:
        raise NoMatch("not periodic")
    stmts = jp.parse_script(joi_block.get("script", "") or "")
    if len(stmts) != 3 or not all(isinstance(s, jp.Assign) for s in stmts[:2]):
        raise NoMatch("prelude shape")
    (h_st, f_st), outer = stmts[:2], stmts[2]
    if h_st.op != ":=" or not (isinstance(h_st.rhs, E.Lit) and h_st.rhs.value == 0):
        raise NoMatch("no hold := 0")
    if f_st.op != ":=" or not (isinstance(f_st.rhs, E.Lit) and f_st.rhs.value is False):
        raise NoMatch("no fired := false")
    hold, fired = h_st.name, f_st.name
    if not isinstance(outer, jp.IfStmt) or len(outer.then_body) != 1 \
            or len(outer.else_body) != 2:
        raise NoMatch("outer if shape")
    inner = outer.then_body[0]
    e1, e2 = outer.else_body
    if not (isinstance(e1, jp.Assign) and e1.name == hold
            and isinstance(e1.rhs, E.Lit) and e1.rhs.value == 0):
        raise NoMatch("else: hold reset")
    if not (isinstance(e2, jp.Assign) and e2.name == fired
            and isinstance(e2.rhs, E.Lit) and e2.rhs.value is False):
        raise NoMatch("else: fired reset")
    if not isinstance(inner, jp.IfStmt) or not _is_eq_false(inner.cond, fired) \
            or inner.else_body:
        raise NoMatch("inner fired-guard shape")
    ib = inner.then_body
    if len(ib) != 2 or not isinstance(ib[0], jp.Assign) or ib[0].name != hold:
        raise NoMatch("hold increment shape")
    inc = ib[0].rhs
    if not (isinstance(inc, E.BinaryOp) and inc.op == "+"
            and isinstance(inc.left, E.VarRef) and inc.left.name == hold
            and isinstance(inc.right, E.Lit) and inc.right.value == 1):
        raise NoMatch("hold increment shape")
    thr_if = ib[1]
    if not isinstance(thr_if, jp.IfStmt) or thr_if.else_body:
        raise NoMatch("threshold if shape")
    tc = thr_if.cond
    if not (isinstance(tc, E.BinaryOp) and tc.op == ">="
            and isinstance(tc.left, E.VarRef) and tc.left.name == hold
            and isinstance(tc.right, E.Lit)):
        raise NoMatch("threshold cond shape")
    thr = int(tc.right.value)
    body = thr_if.then_body
    if not body or not (isinstance(body[-1], jp.Assign) and body[-1].name == fired
                        and isinstance(body[-1].rhs, E.Lit)
                        and body[-1].rhs.value is True):
        raise NoMatch("no fired = true terminator")
    calls_joi = []
    for s in body[:-1]:
        if not isinstance(s, jp.CallStmt) or _canon_call_joi(s) is None:
            raise NoMatch("Y block shape")
        calls_joi.append(_canon_call_joi(s))

    cyc = _single_cycle(_ir_parts(ir))
    b = cyc.get("body") or []
    if not b or b[0].get("op") != "wait" or not b[0].get("for"):
        raise NoMatch("IR body[0] is not sustain wait")
    for_ms = parse_duration_to_ms(b[0]["for"])
    if for_ms != thr * period:
        raise NoMatch(f"threshold mismatch: for={for_ms}ms vs {thr}*{period}")
    if not expr_equal(E.parse(b[0].get("cond", "")), outer.cond, {}):
        raise NoMatch("cond mismatch IR↔JoI")
    calls_ir = []
    for s in b[1:]:
        if s.get("op") != "call" or _canon_call_ir(s, catalog) is None:
            raise NoMatch("IR Y shape")
        calls_ir.append(_canon_call_ir(s, catalog))
    if calls_ir != calls_joi:
        raise NoMatch("action mismatch IR↔JoI")
    edge = b[0].get("edge", "none") or "none"
    return Cert("D-10cw", {"hold": hold, "fired": fired, "thr": thr,
                           "period": period, "edge": edge},
                ["quiescent start", "input phases >= period",
                 "tolerance >= period + 1s"])


TEMPLATES = {"D-3": match_d3, "D-4": match_d4, "B-2": match_b2,
             "D-10cw": match_d10cw}


def certify(ir: dict, joi_block: dict, catalog) -> Optional[Cert]:
    for name, fn in TEMPLATES.items():
        try:
            return fn(ir, joi_block, catalog)
        except NoMatch:
            continue
        except Exception:
            continue
    return None


# ── offline proofs (run once per template library build) ─────────────────────

def prove_d3() -> dict:
    """STEP: invariant trig == c_prev; per-interval output agreement.
    JoI tick: if c_now: (emit iff ¬trig); trig' = c_now.  IR interval:
    emit iff rising (¬c_prev ∧ c_now). Time skew ≤ 1 period ≤ tolerance."""
    c_prev, c_now, trig = z3.Bools("c_prev c_now trig")
    joi_emit = z3.And(c_now, z3.Not(trig))
    trig_post = c_now
    ir_emit = z3.And(z3.Not(c_prev), c_now)
    inv_pre = trig == c_prev
    inv_post = trig_post == c_now
    step = z3.Implies(inv_pre, z3.And(joi_emit == ir_emit, inv_post))
    init = z3.Implies(z3.Not(z3.BoolVal(False)),   # quiescent: c_{-1} = false
                      z3.BoolVal(False) == z3.BoolVal(False))  # trig0 == c_{-1}
    return _prove({"step": step, "init": init})


def prove_d4() -> dict:
    """Invariant: JoI phase-latch p == IR wait-completed s.
    JoI tick: p==0 ∧ c → emit CALLS, p'=1; p==1 → emit CALLS (wait aborts
    the tick while c is false).  IR interval: wait completes in the first
    interval whose boundary sample is true (phases >= period make the
    boundary sample exhaustive), then one cycle iteration per period —
    emit iff s' where s' = s ∨ c.  Both latch permanently; occurrence j
    skew = (first-true tick − first-true instant) < period ≤ tolerance."""
    c, p, s = z3.Bools("c p s")
    joi_emit = z3.Or(p, c)          # p==0∧c → first fire; p==1 → repeat
    ir_emit = z3.Or(s, c)           # completes-and-fires or keeps cycling
    p_post, s_post = z3.Or(p, c), z3.Or(s, c)
    step = z3.Implies(p == s, z3.And(joi_emit == ir_emit, p_post == s_post))
    init = z3.BoolVal(False) == z3.BoolVal(False)   # p0 = 0-latch = s0
    return _prove({"step": step, "init": init})


def prove_b2() -> dict:
    """Stateless: both sides evaluate the same body on the same sample at the
    same (period-aligned) instant — output agreement is per-tick syntactic
    identity; invariant is True. The obligation degenerates to sample
    identity, recorded for the certificate chain."""
    c = z3.Bool("c")
    return _prove({"step": z3.Implies(z3.BoolVal(True), c == c)})


def prove_d10cw() -> dict:
    """Invariant over (JoI h, f) vs IR episode length ℓ (consecutive true
    samples): f == (ℓ >= thr) ∧ (¬f → h == ℓ).
    JoI tick (c_now true): if ¬f: h' = h+1; emit iff h+1 >= thr; f' = f ∨ emit.
    IR: ℓ' = ℓ+1; emits iff ℓ+1 == thr (sustain completes at the thr-th
    consecutive true sample; skew ≤ 1 period ≤ tolerance).
    c_now false: both reset."""
    h, l, thr = z3.Ints("h l thr")
    f = z3.Bool("f")
    c_now = z3.Bool("c_now")
    inv = z3.And(f == (l >= thr), z3.Implies(z3.Not(f), h == l))
    # true branch
    joi_emit_t = z3.And(z3.Not(f), h + 1 >= thr)
    h_t = z3.If(z3.Not(f), h + 1, h)
    f_t = z3.Or(f, joi_emit_t)
    ir_emit_t = l + 1 == thr
    l_t = l + 1
    inv_t = z3.And(f_t == (l_t >= thr), z3.Implies(z3.Not(f_t), h_t == l_t))
    step_true = z3.Implies(z3.And(inv, c_now, thr >= 1, l >= 0, h >= 0),
                           z3.And(joi_emit_t == ir_emit_t, inv_t))
    # false branch: reset on both sides
    inv_f = z3.And(z3.BoolVal(False) == (z3.IntVal(0) >= thr) if False else
                   z3.And((z3.IntVal(0) >= thr) == z3.BoolVal(False),
                          z3.IntVal(0) == z3.IntVal(0)))
    step_false = z3.Implies(z3.And(inv, z3.Not(c_now), thr >= 1), inv_f)
    init = z3.Implies(thr >= 1, z3.And((z3.IntVal(0) >= thr) == z3.BoolVal(False),
                                       z3.IntVal(0) == z3.IntVal(0)))
    return _prove({"step_true": step_true, "step_false": step_false,
                   "init": init})


def _prove(obligations: dict) -> dict:
    import time
    out = {}
    for name, ob in obligations.items():
        s = z3.Solver()
        s.add(z3.Not(ob))
        t0 = time.perf_counter()
        r = s.check()
        out[name] = {"valid": r == z3.unsat,
                     "ms": (time.perf_counter() - t0) * 1000}
    return out


PROOFS = {"D-3": prove_d3, "D-4": prove_d4, "B-2": prove_b2,
          "D-10cw": prove_d10cw}
