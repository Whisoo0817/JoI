"""M2 — symbolic encoder for periodic (IR, JoI) pairs (cron == "", period > 0).

Differences from the M1 (one-shot) encoder:

- **ITE-style execution** (no path forking): branch effects merge back via
  z3.If, so unrolled cycles/ticks stay linear in size instead of 2^N paths.
- **JoI tick unrolling over a bounded window**: W ticks chosen to cover the
  largest persistent-counter threshold (+margin). Tick times are symbolic
  (in-tick delays shift the schedule, matching joi_simulator's
  advance-by-period-after-body semantics).
- **IR cycle unrolling**: N iterations bounded by input transitions (bodies
  gated on an edge wait can fire at most once per transition) or by the
  window / period otherwise.
- **Register-based effects**: per-key (last_effect_time, value) registers
  instead of an effect list, so a 600-tick unroll stays O(1) per read.
- **Bag-style comparison**: emissions become guarded slots; divergence =
  per-signature count mismatch OR some active slot with no same-signature
  active slot on the other side within TOLERANCE_MS. Over-eager SATs are
  filtered by simulator replay.

Claim scope: equivalence within the window [0, T_cmp] for inputs whose
change points lie within tau_cap. (Bounded-window translation validation;
the full-horizon quotient argument is future work.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import z3

from sim import expr as E
from sim import joi_parser as jp
from sim.timeline_ir import parse_duration_to_ms

from etc.smt.encode import (
    TOLERANCE_MS, Unsupported, InputModel, TypeInfo, SymExec, Path, SParts,
    NONE_VAL, MWait, MDelay, MAssign, MEmit, MIf,
    collect_keys_and_types, collect_clock_landmarks,
    _ir_arg_to_ast, _node_key, _CLOCK_KEYS, extract_scenario,
)
from etc.smt.fragment import _effect_key
from etc.smt.obligations import Installed, ObligationSet, decide
from sim.catalog import get_arg_order

MAX_TICKS = 2000
MAX_ITERS = 64


# ── extra micro-ops ──────────────────────────────────────────────────────────

@dataclass
class MBreak:
    pass

@dataclass
class MCycle:
    body: list
    until: Any            # expr AST or None
    period_ms: int
    count: Optional[str]


def ir_to_micro2(ir: dict) -> list:
    tl = ir.get("timeline", [])
    head = tl[0] if tl else {}
    if not (isinstance(head, dict) and head.get("op") == "start_at"):
        raise Unsupported("timeline[0] is not start_at")
    if head.get("anchor") != "now":
        raise Unsupported("cron anchor is M3")
    return _steps2(tl[1:])


def _steps2(steps: list) -> list:
    out: list = []
    for s in steps:
        op = s.get("op")
        if op == "cycle":
            period = s.get("period")
            out.append(MCycle(
                _steps2(s.get("body", []) or []),
                E.parse(s["until"]) if s.get("until") else None,
                parse_duration_to_ms(period) if period else 100,
                s.get("count"),
            ))
        elif op == "break":
            out.append(MBreak())
        elif op == "wait":
            for_str = s.get("for")
            out.append(MWait(E.parse(s.get("cond", "")), s.get("edge", "none") or "none",
                             parse_duration_to_ms(for_str) if for_str else 0))
        elif op == "delay":
            out.append(MDelay(parse_duration_to_ms(s.get("duration", "0 MSEC"))))
        elif op == "read":
            out.append(MAssign(s["var"], E.parse(s["src"])))
        elif op == "call":
            svc, _, method = s.get("target", "").partition(".")
            out.append(MEmit(svc, method,
                             [(k, _ir_arg_to_ast(v)) for k, v in (s.get("args") or {}).items()],
                             bind=s.get("var") or s.get("bind")))
        elif op == "if":
            out.append(MIf(E.parse(s.get("cond", "")),
                           _steps2(s.get("then", []) or []),
                           _steps2(s.get("else", []) or [])))
        else:
            raise Unsupported(f"IR op {op}")
    return out


def joi_to_micro2(joi_block: dict) -> tuple[list, int]:
    period = int(joi_block.get("period", 0) or 0)
    if (joi_block.get("cron") or "").strip():
        raise Unsupported("cron JoI is M3")
    stmts = jp.parse_script(joi_block.get("script", "") or "")
    return _joi_stmts2(stmts), period


def _joi_stmts2(stmts: list) -> list:
    out: list = []
    for s in stmts:
        if isinstance(s, jp.Assign):
            if isinstance(s.rhs, jp.CallExpr) and s.rhs.args is not None:
                out.append(MEmit(s.rhs.service, s.rhs.method, list(s.rhs.args), bind=s.name))
            else:
                out.append(MAssign(s.name, s.rhs))
            out[-1].init_once = (s.op == ":=") if isinstance(out[-1], MAssign) else False
        elif isinstance(s, jp.CallStmt):
            out.append(MEmit(s.call.service, s.call.method, list(s.call.args or [])))
        elif isinstance(s, jp.WaitUntil):
            out.append(MWait(s.cond, "none", 0))
        elif isinstance(s, jp.Delay):
            out.append(MDelay(s.ms))
        elif isinstance(s, jp.IfStmt):
            out.append(MIf(s.cond, _joi_stmts2(s.then_body), _joi_stmts2(s.else_body or [])))
        elif isinstance(s, jp.Break):
            out.append(MBreak())
        else:
            raise Unsupported(f"JoI stmt {type(s).__name__}")
    return out


# ── window sizing ────────────────────────────────────────────────────────────

def _collect_int_thresholds(node, out: set) -> None:
    """Persistent-counter thresholds: `var CMP <int-lit>` comparisons."""
    if isinstance(node, E.BinaryOp):
        if node.op in ("<", ">", "<=", ">=", "==", "!="):
            for a, b in ((node.left, node.right), (node.right, node.left)):
                if isinstance(a, E.VarRef) and isinstance(b, E.Lit) \
                        and isinstance(b.value, (int, float)) \
                        and not isinstance(b.value, bool):
                    out.add(int(abs(b.value)))
        _collect_int_thresholds(node.left, out)
        _collect_int_thresholds(node.right, out)
    elif isinstance(node, E.UnaryOp):
        _collect_int_thresholds(node.operand, out)
    elif isinstance(node, E.FuncCall):
        for a in node.args:
            _collect_int_thresholds(a, out)


def _scan_thresholds_and_delays(ops: list, thr: set, delays: list) -> None:
    for op in ops:
        if isinstance(op, MWait):
            _collect_int_thresholds(op.cond, thr)
            if op.for_ms:
                delays.append(op.for_ms)
        elif isinstance(op, MAssign):
            _collect_int_thresholds(op.rhs, thr)
        elif isinstance(op, MDelay):
            delays.append(op.ms)
        elif isinstance(op, MIf):
            _collect_int_thresholds(op.cond, thr)
            _scan_thresholds_and_delays(op.then, thr, delays)
            _scan_thresholds_and_delays(op.els, thr, delays)
        elif isinstance(op, MCycle):
            if op.until is not None:
                _collect_int_thresholds(op.until, thr)
            _scan_thresholds_and_delays(op.body, thr, delays)


# ── ITE-style executor ───────────────────────────────────────────────────────

@dataclass
class Slot:
    guard: Any            # z3 Bool
    time: Any             # z3 Int expr
    service: str
    method: str           # canonical
    args: list


class ITEExec(SymExec):
    """Guard-merging executor. Reuses SymExec's expression evaluation but
    replaces path forking with If-merged state and register-based effects."""

    def __init__(self, im: InputModel, ti: TypeInfo, catalog: dict,
                 clock_landmarks: list, tag: str, alias: dict | None = None):
        super().__init__(im, ti, catalog, clock_landmarks, tag, alias=alias)
        self.env: dict = {}
        self.regs: dict = {}      # key → (last_eff_time expr, value expr)
        self.time: Any = z3.IntVal(0)
        self.live: Any = z3.BoolVal(True)   # within current activation
        self.slots: list[Slot] = []
        # SymExec.eval takes a `path` with .env/.effects — self acts as it.
        self.effects: list = []   # unused in register mode

    # register-based state read (overrides effect-list fold)
    def state_at(self, path, key: str, t) -> Any:
        key = self.alias.get(key, key)
        if key in _CLOCK_KEYS:
            return self._clock_value(key, t)
        if key not in self.im.taus:
            return NONE_VAL
        base = self.im.base_value(key, t)
        if key not in self.regs:
            return base
        eff_t, eff_v = self.regs[key]
        lsc = self.im.last_change_before(key, t)
        return z3.If(z3.And(eff_t >= 0, eff_t <= t, lsc <= eff_t), eff_v, base)

    def _write_effect(self, key: str, guard, t, value) -> None:
        if key not in self.regs:
            self.regs[key] = (z3.IntVal(-1), value)
        eff_t, eff_v = self.regs[key]
        # sort mismatch guard: coerce to a common representation
        try:
            merged_v = z3.If(guard, self._z3val(value), self._z3val(eff_v))
        except z3.Z3Exception:
            merged_v = eff_v
        self.regs[key] = (z3.If(guard, t, eff_t), merged_v)

    def _z3val(self, v):
        if isinstance(v, bool):
            return z3.BoolVal(v)
        if isinstance(v, (int, float)):
            return z3.RealVal(v)
        if isinstance(v, str):
            return z3.IntVal(self.ti.intern(v))
        if v is NONE_VAL:
            return z3.RealVal(0)
        if isinstance(v, SParts):
            raise z3.Z3Exception("SParts effect")
        return v

    def assign_var(self, name: str, guard, value) -> None:
        old = self.env.get(name, NONE_VAL)
        if old is NONE_VAL and value is not NONE_VAL:
            # first write — merge with a typed default so If sorts agree
            try:
                self.env[name] = z3.If(guard, self._z3val(value),
                                       self._z3default(value))
            except z3.Z3Exception:
                self.env[name] = value
            return
        if isinstance(value, SParts) or isinstance(old, SParts) or \
                value is NONE_VAL or old is NONE_VAL:
            self.env[name] = value   # non-mergeable — last write wins
            return
        self.env[name] = z3.If(guard, self._z3val(value), self._z3val(old))

    def _z3default(self, like):
        if isinstance(like, bool) or (z3.is_expr(like) and z3.is_bool(like)):
            return z3.BoolVal(False)
        if isinstance(like, str):
            return z3.IntVal(0)
        if z3.is_expr(like) and like.sort() == z3.IntSort():
            return z3.IntVal(0)
        return z3.RealVal(0)

    # `%` support (counters): a % m for const m, a ≥ 0 — a − m·floor(a/m)
    def _eval_binop(self, node, path, t):
        if node.op == "%":
            if not isinstance(node.right, E.Lit):
                raise Unsupported("% with non-constant rhs")
            a = self.to_num(self.eval(node.left, path, t))
            m = float(node.right.value)
            if m <= 0:
                raise Unsupported("% modulus <= 0")
            q = z3.ToInt(a / z3.RealVal(m))
            return a - z3.RealVal(m) * z3.ToReal(q)
        return super()._eval_binop(node, path, t)

    # ── one-shot-style sequence execution (IR prefix / cycle body) ──
    def exec_seq_timed(self, ops: list, bg) -> None:
        """Execute ops sequentially; waits ADVANCE time (IR semantics).
        `bg` = branch guard (z3 Bool). Stall folds into self.live."""
        for op in ops:
            g = z3.And(self.live, bg)
            if isinstance(op, MWait):
                done, Tp = self._wait_ite(op, g)
                self.time = z3.If(g, Tp, self.time)
                self.live = z3.And(self.live, z3.Or(z3.Not(bg), done))
            elif isinstance(op, MDelay):
                self.time = z3.If(g, self.time + op.ms, self.time)
            elif isinstance(op, MAssign):
                self.assign_var(op.var, g, self.eval(op.rhs, self, self.time))
            elif isinstance(op, MEmit):
                self._emit_ite(op, g, self.time)
            elif isinstance(op, MIf):
                c = self.to_bool(self.eval(op.cond, self, self.time))
                t_before = self.time
                self.exec_seq_timed(op.then, z3.And(bg, c))
                t_then = self.time
                self.time = t_before
                self.exec_seq_timed(op.els, z3.And(bg, z3.Not(c)))
                self.time = z3.If(c, t_then, self.time)
            elif isinstance(op, MBreak):
                self.break_hit = z3.Or(getattr(self, "break_hit", z3.BoolVal(False)), g)
                self.live = z3.And(self.live, z3.Not(bg))
            elif isinstance(op, MCycle):
                raise Unsupported("nested cycle")
            else:
                raise Unsupported(f"op {type(op).__name__}")

    def _wait_ite(self, op: MWait, g):
        """ITE variant of wait: returns (completes Bool, completion time)."""
        T = self.time
        Lms = self.base_landmarks
        cands = ([T] + Lms) if op.edge == "none" else list(Lms)

        def cond_at(t):
            return self.to_bool(self.eval(op.cond, self, t))

        def fires_at(t):
            c = z3.And(t >= T, t <= z3.IntVal(10**12),
                       cond_at(t) if op.edge != "falling" else z3.Not(cond_at(t)))
            if op.edge in ("rising", "falling"):
                before = cond_at(t - 1)
                want_before = z3.Not(before) if op.edge == "rising" else before
                c = z3.And(c, t > T, want_before)
            if op.for_ms > 0:
                hold = cond_at if op.edge != "falling" else (lambda x: z3.Not(cond_at(x)))
                sus = [z3.Implies(z3.And(l > t, l < t + op.for_ms), hold(l)) for l in Lms]
                c = z3.And(c, *sus)
            return c

        # `fired` must NOT contain Tp — otherwise the solver can falsify
        # completion by picking a bogus Tp (found via C12_015 false positive).
        fired = z3.Or(*[fires_at(c) for c in cands]) if cands else z3.BoolVal(False)
        Tp = self.fresh_time()
        disj = []
        for i, ci in enumerate(cands):
            earlier = [z3.Implies(z3.And(cj >= T, cj < ci), z3.Not(fires_at(cj)))
                       for j, cj in enumerate(cands) if j != i]
            disj.append(z3.And(fires_at(ci),
                               Tp == ci + (op.for_ms if op.for_ms > 0 else 0),
                               *earlier))
        # Tp = earliest firing candidate, asserted globally (vacuous if ¬fired;
        # Tp is then unconstrained but every dependent guard is false).
        if disj:
            self.constraints.append(z3.Implies(fired, z3.Or(*disj)))
        return fired, Tp

    def _emit_ite(self, op: MEmit, g, t) -> None:
        svc_c, method_c = E.canonical_key(op.service, op.method)
        if op.args and isinstance(op.args[0], tuple) and isinstance(op.args[0][0], str):
            names = [a[0] for a in op.args]
            nodes = {a[0]: a[1] for a in op.args}
            order = get_arg_order(self.catalog, op.service, op.method)
            keys = ([k for k in order if k in nodes] +
                    sorted(k for k in names if k not in (order or []))) if order \
                else sorted(names)
            arg_nodes = [nodes[k] for k in keys]
        else:
            arg_nodes = list(op.args)
        vals = [self.eval(n, self, t) for n in arg_nodes]
        vals = [self._coerce_arg(v) for v in vals]
        # comparator-style fan-out dedup: identical (method, args) at the same
        # instant under the same guard collapses to one emission
        dup = False
        for prev in reversed(self.slots):
            if not (z3.is_expr(prev.time) and z3.is_expr(t) and prev.time.eq(t)):
                break
            if (prev.method == method_c and prev.guard.eq(g)
                    and self._args_syntactically_equal(
                        type("A", (), {"args": prev.args})(),
                        type("A", (), {"args": vals})())):
                dup = True
                break
        if not dup:
            self.slots.append(Slot(g, t, svc_c, method_c, vals))
        # effect — MUST use the canonical pair: the sim applies effects via
        # canonical_key (e.g. `all(#Pump #Switch #Factory).switch_off()` →
        # ("switch","off") → key "switch.switch"); the raw selector service
        # ("Factory") would write a key nobody reads.
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
                written = z3.Not(self.to_bool(self.state_at(self, ek, t)))
            elif len(vals) == 1:
                written = vals[0]
            if written is not None:
                try:
                    self._write_effect(ek, g, t, written)
                except z3.Z3Exception:
                    pass
        if op.bind:
            self.assign_var(op.bind, g,
                            written if (ek is not None and written is not None)
                            else NONE_VAL)


# ── IR periodic driver ───────────────────────────────────────────────────────

def run_ir_periodic(ex: ITEExec, micro: list, w_ms: int, n_transitions: int) -> None:
    """Execute IR timeline: one-shot prefix + at most one top-level cycle."""
    prefix: list = []
    cyc: Optional[MCycle] = None
    suffix: list = []
    for op in micro:
        if isinstance(op, MCycle):
            if cyc is not None:
                raise Unsupported("two top-level cycles")
            cyc = op
        elif cyc is None:
            prefix.append(op)
        else:
            suffix.append(op)

    ex.exec_seq_timed(prefix, z3.BoolVal(True))
    if cyc is None:
        return

    # iteration bound
    has_edge_wait = any(isinstance(b, MWait) and b.edge in ("rising", "falling")
                        for b in cyc.body)
    has_sustain = any(isinstance(b, MWait) and b.for_ms > 0 for b in cyc.body)
    if has_edge_wait or has_sustain:
        n_iter = min(n_transitions + 2, 8)
    else:
        n_iter = -(-w_ms // max(cyc.period_ms, 1))  # ceil
        if n_iter > MAX_ITERS:
            raise Unsupported(f"cycle unroll {n_iter} > {MAX_ITERS}")

    if cyc.count:
        ex.assign_var(cyc.count, ex.live, 0.0)

    cont = ex.live
    for _ in range(n_iter):
        if cyc.until is not None:
            u = ex.to_bool(ex.eval(cyc.until, ex, ex.time))
            cont = z3.And(cont, z3.Not(u))
        iter_start = ex.time
        ex.live = cont
        ex.break_hit = z3.BoolVal(False)
        ex.exec_seq_timed(cyc.body, z3.BoolVal(True))
        cont = z3.And(ex.live, z3.Not(ex.break_hit))
        if cyc.count:
            cur = ex.to_num(ex.env.get(cyc.count, 0.0))
            ex.env[cyc.count] = z3.If(cont, cur + 1, cur)
        # pad to period — only while the cycle still runs (see encode3 note)
        padded = iter_start + cyc.period_ms
        ex.time = z3.If(z3.And(cont, ex.time - iter_start < cyc.period_ms),
                        padded, ex.time)
    ex.live = cont
    ex.exec_seq_timed(suffix, z3.BoolVal(True))


# ── JoI tick driver ──────────────────────────────────────────────────────────

def run_joi_ticks(ex: ITEExec, micro: list, period_ms: int, w_ticks: int) -> None:
    alive = z3.BoolVal(True)
    t_k = z3.IntVal(0)
    for k in range(w_ticks):
        ex.time = t_k
        ex.live = alive
        ex.break_hit = z3.BoolVal(False)
        offset_total = _exec_tick(ex, micro, z3.BoolVal(True), k, z3.IntVal(0))
        alive = z3.And(alive, z3.Not(ex.break_hit))
        t_k = t_k + period_ms + offset_total


def _exec_tick(ex: ITEExec, ops: list, bg, k: int, offset):
    """Execute one tick's statements. Waits ABORT (no time advance); delays
    shift in-tick offset. Returns total guarded delay offset added."""
    for op in ops:
        g = z3.And(ex.live, bg)
        t_now = ex.time + offset
        if isinstance(op, MAssign):
            if getattr(op, "init_once", False) and k > 0:
                continue
            ex.assign_var(op.var, g, ex.eval(op.rhs, ex, t_now))
        elif isinstance(op, MEmit):
            ex._emit_ite(op, g, t_now)
        elif isinstance(op, MWait):
            if op.edge != "none" or op.for_ms:
                raise Unsupported("edge/sustain wait inside periodic JoI")
            c = ex.to_bool(ex.eval(op.cond, ex, t_now))
            ex.live = z3.And(ex.live, z3.Or(z3.Not(bg), c))
        elif isinstance(op, MDelay):
            offset = offset + z3.If(g, z3.IntVal(op.ms), z3.IntVal(0))
        elif isinstance(op, MBreak):
            ex.break_hit = z3.Or(ex.break_hit, g)
            ex.live = z3.And(ex.live, z3.Not(bg))
        elif isinstance(op, MIf):
            c = ex.to_bool(ex.eval(op.cond, ex, t_now))
            offset = _exec_tick(ex, op.then, z3.And(bg, c), k, offset)
            offset = _exec_tick(ex, op.els, z3.And(bg, z3.Not(c)), k, offset)
        else:
            raise Unsupported(f"tick op {type(op).__name__}")
    return offset


# ── miter ────────────────────────────────────────────────────────────────────

def _sig(slot: Slot) -> tuple:
    return (slot.method, len(slot.args))


def assert_ordered_mismatch(s: "z3.Solver", ex_ir: ITEExec, ex_joi: ITEExec,
                            t_cmp: int, tol_eff: int) -> Installed:
    """Assert the divergence query: ordered-index matching per signature.

    The i-th active emission on one side must match the i-th active emission
    on the other (time within tol_eff, equal args). Slots unmatched only
    because of the window tail (time >= t_cmp - tol_eff) get grace — a pure
    time shift <= tol_eff must not register as a count mismatch there.

    The disjuncts are grouped into per-signature obligations
    (align:<method>/<nargs>, count:<method>/<nargs>) behind assumption
    switches; a plain check() still runs the whole query.
    """
    def active(sl: Slot):
        return z3.And(sl.guard, sl.time < t_cmp, sl.time >= 0)

    def index_exprs(slots: list, tag: str):
        idx = []
        cur = z3.IntVal(0)
        for i, sl in enumerate(slots):
            v = z3.Int(f"idx_{tag}_{id(sl)}_{i}")
            s.add(v == cur)
            idx.append(v)
            cur = cur + z3.If(active(sl), 1, 0)
        return idx, cur  # per-slot start index, total active count

    sigs = {_sig(sl) for sl in ex_ir.slots} | {_sig(sl) for sl in ex_joi.slots}
    obs = ObligationSet()
    for si, sig in enumerate(sorted(sigs)):
        label = f"{sig[0]}/{sig[1]}"
        xs = [sl for sl in ex_ir.slots if _sig(sl) == sig]
        ys = [sl for sl in ex_joi.slots if _sig(sl) == sig]
        ix, cnt_x = index_exprs(xs, f"ir{si}")
        iy, cnt_y = index_exprs(ys, f"joi{si}")
        for a_slots, a_idx, b_slots, b_idx, b_cnt in (
                (xs, ix, ys, iy, cnt_y), (ys, iy, xs, ix, cnt_x)):
            for a, ia in zip(a_slots, a_idx):
                for b, ib in zip(b_slots, b_idx):
                    args_eq = [ex_ir.values_equal(x, y)
                               for x, y in zip(a.args, b.args)]
                    ok = z3.And(a.time - b.time <= tol_eff,
                                b.time - a.time <= tol_eff, *args_eq)
                    obs.add(f"align:{label}", z3.And(active(a), active(b),
                                                     ia == ib, z3.Not(ok)))
                obs.add(f"count:{label}", z3.And(active(a), ia >= b_cnt,
                                                 a.time < t_cmp - tol_eff))
    return obs.install(s, tag="ord")


def _collect_edge_waits(ops: list, out: list) -> None:
    for op in ops:
        if isinstance(op, MWait) and op.edge in ("rising", "falling"):
            out.append(op)
        elif isinstance(op, MIf):
            _collect_edge_waits(op.then, out)
            _collect_edge_waits(op.els, out)
        elif isinstance(op, MCycle):
            _collect_edge_waits(op.body, out)


def build_miter_m2(ir: dict, joi_block: dict, catalog: dict,
                   tolerance_ms: int = TOLERANCE_MS,
                   assume_quiescent: bool = True, devices=None):
    m_ir = ir_to_micro2(ir)
    m_joi, period = joi_to_micro2(joi_block)
    if period <= 0:
        raise Unsupported("period 0 is M1")

    from etc.smt.grounding import compute_grounding, Grounding
    g = compute_grounding(ir, joi_block, devices) if devices else Grounding()

    keys, ti = collect_keys_and_types([m_ir, m_joi], g.alias)
    clocks = collect_clock_landmarks([m_ir, m_joi])
    im = InputModel(keys, ti)

    # tolerance first — the window must dominate it (E-B finding: with
    # period=100 the old W=24 gave a 2.4s window vs 1.1s tolerance, so the
    # tail-grace band swallowed all but the first ~2 ticks and genuinely
    # divergent mutants passed as EQUIV)
    tol_eff_w = max(tolerance_ms, period + tolerance_ms)

    # window sizing
    thr: set = set()
    delays: list = []
    _scan_thresholds_and_delays(m_ir, thr, delays)
    _scan_thresholds_and_delays(m_joi, thr, delays)
    thr_ticks = max(thr) if thr else 0
    delay_ms = sum(delays)
    w_ticks = max(thr_ticks + 24, -(-(delay_ms + 4 * period) // period), 24,
                  -(-(6 * tol_eff_w) // period) + 8)
    if w_ticks > MAX_TICKS:
        raise Unsupported(f"window {w_ticks} ticks > {MAX_TICKS}")
    w_ms = w_ticks * period
    tau_cap = max(4 * period, w_ms - (thr_ticks + 8) * period)
    t_cmp = w_ms - tolerance_ms - period

    n_transitions = sum(len(im.taus[k]) for k in im.taus) or 2

    ex_ir = ITEExec(im, ti, catalog, clocks, "ir", alias=g.alias)
    ex_joi = ITEExec(im, ti, catalog, clocks, "joi", alias=g.alias)
    run_ir_periodic(ex_ir, m_ir, w_ms, n_transitions)
    run_joi_ticks(ex_joi, m_joi, period, w_ticks)

    # Sampling-granularity-aware equivalence: the deployed JoI polls every
    # `period` ms, so (a) response latency up to one period is inherent to
    # the lowering — tolerance widens to period + TOLERANCE_MS; (b) input
    # phases shorter than the period are invisible to the deployed artifact —
    # the input model only ranges over phases lasting >= max(period, 100).
    tol_eff = max(tolerance_ms, period + tolerance_ms)
    min_phase = max(period, 100)

    s = z3.Solver()
    for c in im.constraints:
        s.add(c)
    for c in ex_ir.constraints + ex_joi.constraints:
        s.add(c)
    for key in im.taus:
        taus = im.taus[key]
        for i, tau in enumerate(taus):
            s.add(tau <= tau_cap)
            s.add(tau >= min_phase if i == 0 else tau - taus[i - 1] >= min_phase)

    # Quiescent-start assumption: no edge-wait condition is already at its
    # target polarity at deployment (t=0). Removes the known template-boundary
    # divergence class (D-3/B-1b "already-true-at-start") from the search so
    # residual divergences surface; run with assume_quiescent=False to get
    # the boundary class itself.
    if assume_quiescent:
        edge_waits: list = []
        _collect_edge_waits(m_ir, edge_waits)
        for w in edge_waits:
            c0 = ex_ir.to_bool(ex_ir.eval(w.cond, ex_ir, z3.IntVal(0)))
            s.add(z3.Not(c0) if w.edge == "rising" else c0)

    inst = assert_ordered_mismatch(s, ex_ir, ex_joi, t_cmp, tol_eff)
    meta = {"w_ticks": w_ticks, "w_ms": w_ms, "t_cmp": t_cmp,
            "tau_cap": tau_cap, "period": period, "tol_eff": tol_eff,
            "min_phase": min_phase, "alias": g.alias, "mistargets": g.mistargets,
            "slots_ir": len(ex_ir.slots), "slots_joi": len(ex_joi.slots),
            "_obligations": inst}
    return s, im, ti, meta


def check_pair_m2(ir: dict, joi_block: dict, catalog: dict,
                  tolerance_ms: int = TOLERANCE_MS,
                  assume_quiescent: bool = True,
                  timeout_ms: int = 0, devices=None,
                  split: bool = False) -> dict:
    import time
    t0 = time.perf_counter()
    try:
        s, im, ti, meta = build_miter_m2(ir, joi_block, catalog, tolerance_ms,
                                         assume_quiescent, devices)
    except Unsupported as e:
        return {"verdict": "UNSUPPORTED", "reason": str(e),
                "elapsed_s": time.perf_counter() - t0}
    inst = meta.pop("_obligations")
    out = decide(s, inst, lambda m: extract_scenario(m, im, ti),
                 timeout_ms=timeout_ms, split=split,
                 timeout_verdict="TIMEOUT" if timeout_ms else "UNKNOWN")
    out["elapsed_s"] = time.perf_counter() - t0
    out["meta"] = meta
    return out
