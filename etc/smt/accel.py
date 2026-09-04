"""M2.5 — phase-wise counter acceleration for periodic pairs.

Removes the tick-window (W) dependence WITHIN the accelerated fragment:

    fragment = single condition key (piecewise-constant, K change points)
             + affine persistent counters (c = c + <const> / c = <const>)
             + constant-valued flags
             + guards over {input atoms, flag tests, counter-vs-const}
             + unconditional in-tick delays only
             + emission args constant / input reads (not counter-dependent)
             + no clock atoms

Outside the fragment the caller falls back to the bounded-window unroll
encoder (encode2). Explicit non-goals kept as stated limitations: K change
points, cron occurrence count (N_OCC), and complex persistent-state
branching are NOT lifted by this module.

Mechanics per input phase (value constant):
    repeat up to R regimes:
        1 explicit symbolic tick (may flip flags / cross a threshold / emit)
      + 1 "bulk" of n collapsed ticks, where n is FORCED (not solver-chosen)
        to min(ticks to phase end, ticks to nearest counter-atom crossing),
        and n > 0 is only allowed when the explicit tick provably left every
        flag unchanged. Counters advance in closed form (n * delta); a
        uniformly-emitting regime contributes ONE emission run-slot.

Emissions are RunSlots (guard, start, stride, count, action); a point
emission is a run of count 1. Matching is run-aware ordered-index alignment
(smt/runs semantics below): per signature, cumulative-count indexing, pair
alignment checked at overlap endpoints (time difference linear in index),
effective counts truncated at t_cmp, tail grace at t_cmp - tol.

Claim scope: full 7-day horizon (no W), inputs on the 100 ms grid with
phases >= max(period, 100), tolerance period + 1s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import z3

from sim import expr as E
from sim import joi_parser as jp

from etc.smt.encode import (
    TOLERANCE_MS, HORIZON_MS, Unsupported, InputModel, TypeInfo,
    collect_keys_and_types, MWait, MDelay, MAssign, MEmit, MIf,
    _node_key, _CLOCK_KEYS, extract_scenario,
)
from etc.smt.encode2 import (
    ITEExec, MBreak, MCycle, ir_to_micro2, joi_to_micro2, Slot,
)
from etc.smt.fragment import _effect_key
from etc.smt.obligations import Installed, ObligationSet, decide

R_REGIMES = 6
INF = z3.IntVal(10 ** 15)


# ── run slots ────────────────────────────────────────────────────────────────

@dataclass
class RunSlot:
    guard: Any          # z3 Bool — whole run active?
    start: Any          # z3 Int expr — time of emission 0
    stride: int         # ms between emissions (concrete within fragment)
    count: Any          # z3 Int expr — number of emissions (>= 0)
    service: str
    method: str
    args: list


def point(guard, time, service, method, args) -> RunSlot:
    return RunSlot(guard, time, 1, z3.IntVal(1), service, method, args)


def slots_to_runs(slots: list[Slot]) -> list[RunSlot]:
    return [point(s.guard, s.time, s.service, s.method, s.args) for s in slots]


# ── fragment check + shape extraction ────────────────────────────────────────

@dataclass
class FragmentInfo:
    cond_key: Optional[str]         # the single input key read (or None)
    counters: set                   # persistent int counters
    flags: set                      # constant-assigned persistent vars
    counter_atoms: list             # (var, op, const) guards
    deltas: dict                    # var -> set of literal deltas seen
    uncond_delay_ms: int


class NotAccelerable(Exception):
    pass


def _expr_keys(node, keys: set) -> None:
    k = _node_key(node)
    if k is not None:
        if k in _CLOCK_KEYS:
            raise NotAccelerable("clock atom")
        keys.add(k)
        return
    if isinstance(node, E.UnaryOp):
        _expr_keys(node.operand, keys)
    elif isinstance(node, E.BinaryOp):
        _expr_keys(node.left, keys)
        _expr_keys(node.right, keys)
    elif isinstance(node, E.FuncCall):
        for a in node.args:
            _expr_keys(a, keys)
    elif isinstance(node, jp.CallExpr) and node.args is not None:
        for a in node.args:
            _expr_keys(a, keys)


def _classify_rhs(var: str, rhs, info: FragmentInfo) -> str:
    """'counter' for c=c+const / c=const(int); 'flag' for other constants;
    raises for anything else."""
    if isinstance(rhs, E.Lit):
        if isinstance(rhs.value, bool) or isinstance(rhs.value, str):
            return "flag"
        if isinstance(rhs.value, (int, float)):
            info.deltas.setdefault(var, set())
            return "counter_or_flag"
        return "flag"
    if isinstance(rhs, E.BinaryOp) and rhs.op in ("+", "-"):
        a, b = rhs.left, rhs.right
        if isinstance(a, E.VarRef) and a.name == var and isinstance(b, E.Lit) \
                and isinstance(b.value, (int, float)):
            d = int(b.value) * (1 if rhs.op == "+" else -1)
            info.deltas.setdefault(var, set()).add(d)
            return "counter"
    raise NotAccelerable(f"non-affine update of {var!r}")


def _walk_guard(node, info: FragmentInfo) -> None:
    """Collect counter atoms; ensure guard shape is in the fragment."""
    if isinstance(node, E.BinaryOp):
        if node.op in ("and", "or"):
            _walk_guard(node.left, info)
            _walk_guard(node.right, info)
            return
        if node.op in ("==", "!=", "<", ">", "<=", ">="):
            for a, b in ((node.left, node.right), (node.right, node.left)):
                if isinstance(a, E.VarRef) and _node_key(a) is None \
                        and isinstance(b, E.Lit) \
                        and isinstance(b.value, (int, float)) \
                        and not isinstance(b.value, bool):
                    info.counter_atoms.append((a.name, node.op, int(b.value)))
            keys: set = set()
            _expr_keys(node, keys)
            return
    if isinstance(node, E.UnaryOp):
        _walk_guard(node.operand, info)
        return
    keys = set()
    _expr_keys(node, keys)


def analyze_fragment(micro: list) -> FragmentInfo:
    """Raise NotAccelerable if the script is outside the fragment."""
    info = FragmentInfo(None, set(), set(), [], {}, 0)
    keys: set = set()
    kinds: dict = {}

    def walk(ops, in_branch: bool):
        for op in ops:
            if isinstance(op, MAssign):
                kind = _classify_rhs(op.var, op.rhs, info)
                prev = kinds.get(op.var)
                if prev and prev != kind and "counter" in (prev, kind) \
                        and "counter_or_flag" not in (prev, kind):
                    raise NotAccelerable(f"mixed update kinds for {op.var!r}")
                kinds[op.var] = kind if prev in (None, "counter_or_flag") else prev
                _expr_keys(op.rhs, keys)
            elif isinstance(op, MEmit):
                for a in op.args:
                    node = a[1] if isinstance(a, tuple) else a
                    # counter-dependent args (alternation) are not collapsible
                    refs: set = set()
                    _collect_varrefs(node, refs)
                    if refs & set(v for v, k in kinds.items() if "counter" in k):
                        raise NotAccelerable("counter-dependent emission args")
                    _expr_keys(node, keys)
                if op.bind:
                    raise NotAccelerable("bind in accelerated fragment")
            elif isinstance(op, MWait):
                if op.edge != "none" or op.for_ms:
                    raise NotAccelerable("edge/sustain wait in periodic script")
                _walk_guard(op.cond, info)
                _expr_keys(op.cond, keys)
            elif isinstance(op, MDelay):
                # unconditional delays fold into the stride; conditional
                # ones are handled via the drift variable (bulk requires a
                # zero-offset explicit tick)
                if not in_branch:
                    info.uncond_delay_ms += op.ms
            elif isinstance(op, MIf):
                _walk_guard(op.cond, info)
                _expr_keys(op.cond, keys)
                walk(op.then, True)
                walk(op.els, True)
            elif isinstance(op, MBreak):
                pass
            else:
                raise NotAccelerable(f"op {type(op).__name__}")

    walk(micro, False)
    if len(keys) > 1:
        raise NotAccelerable(f"multi-key conds {sorted(keys)}")
    info.cond_key = next(iter(keys)) if keys else None
    info.counters = {v for v, k in kinds.items() if k == "counter"}
    info.flags = {v for v, k in kinds.items() if k in ("flag", "counter_or_flag")}
    return info


def _collect_varrefs(node, out: set) -> None:
    if isinstance(node, E.VarRef) and _node_key(node) is None:
        out.add(node.name)
    elif isinstance(node, E.UnaryOp):
        _collect_varrefs(node.operand, out)
    elif isinstance(node, E.BinaryOp):
        _collect_varrefs(node.left, out)
        _collect_varrefs(node.right, out)
    elif isinstance(node, E.FuncCall):
        for a in node.args:
            _collect_varrefs(a, out)


# ── accelerated executor ─────────────────────────────────────────────────────

class AccelExec(ITEExec):
    """Reuses ITEExec expression evaluation; state is (env, regs) as usual.
    Counters live in env as Int exprs; acceleration happens in the driver."""

    def eval_counters_as_int(self):
        pass  # counters kept as Real via to_num; deltas are ints — sound.


def _ceil_div_pos(a, c: int):
    """ceil(a / c) for symbolic a >= 0 and concrete c > 0 (z3 Int)."""
    return (a + (c - 1)) / c


class AccelMachine:
    """Drives phase x regime execution for ONE side (JoI ticks or IR cycle)."""

    def __init__(self, ex: ITEExec, micro: list, info: FragmentInfo,
                 stride: int, im: InputModel, side: str, base=None):
        self.ex = ex
        self.micro = micro
        self.info = info
        self.stride = stride          # period + unconditional in-tick delays
        self.im = im
        self.side = side
        self.base = base if base is not None else z3.IntVal(0)  # first tick time
        self.runs: list[RunSlot] = []
        self.constraints: list = []
        # completeness side conditions: each entry must be UNSAT under the
        # input constraints, else ticks were left unmodeled → fall back
        self.leftovers: list = []

    # phase boundaries as TICK indices (Int exprs), relative to base time
    def phase_tick_bounds(self) -> list:
        key = self.info.cond_key
        bounds = [z3.IntVal(0)]
        if key is not None and key in self.im.taus:
            for tau in self.im.taus[key]:
                rel = _ceil_div_pos(tau - self.base, self.stride)
                bounds.append(z3.If(rel > 0, rel, z3.IntVal(0)))
        bounds.append(_ceil_div_pos(z3.IntVal(HORIZON_MS) - self.base,
                                    self.stride))
        return bounds

    def _prerun_inits(self) -> None:
        """`:=` initializers are constants in the fragment — run them once
        up front, decoupled from the phase structure (the first explicit
        tick may fall in an empty phase and execute with a false guard,
        which would otherwise silently drop a non-zero init)."""
        def walk(ops):
            for op in ops:
                if isinstance(op, MAssign) and getattr(op, "init_once", False):
                    self.ex.env[op.var] = self.ex.eval(op.rhs, self.ex,
                                                       z3.IntVal(0))
                elif isinstance(op, MIf):
                    walk(op.then)
                    walk(op.els)
        walk(self.micro)

    def run_side(self, alive0=None) -> None:
        ex = self.ex
        self._prerun_inits()
        n = z3.IntVal(0)              # current tick index
        drift = z3.IntVal(0)          # accumulated conditional in-tick delays
        alive = alive0 if alive0 is not None else z3.BoolVal(True)
        bounds = self.phase_tick_bounds()
        for pi in range(len(bounds) - 1):
            end = bounds[pi + 1]
            for r in range(R_REGIMES):
                in_phase = n < end
                # ── explicit tick ──
                t_now = self.base + n * self.stride + drift
                ex.time = t_now
                ex.live = z3.And(alive, in_phase)
                ex.break_hit = z3.BoolVal(False)
                flags_before = {f: ex.env.get(f) for f in self.info.flags}
                counters_before = {c: ex.env.get(c) for c in self.info.counters}
                emits_before = len(ex.slots)
                from etc.smt.encode2 import _exec_tick
                off = _exec_tick(ex, self.micro, z3.BoolVal(True), 1, z3.IntVal(0))
                off = off - self.info.uncond_delay_ms  # uncond part is in stride
                drift = drift + z3.If(z3.And(alive, in_phase), off, z3.IntVal(0))
                alive = z3.And(alive, z3.Not(ex.break_hit))
                new_slots = ex.slots[emits_before:]
                del ex.slots[emits_before:]
                for sl in new_slots:
                    self.runs.append(point(sl.guard, sl.time, sl.service,
                                           sl.method, sl.args))
                n = z3.If(in_phase, n + 1, n)

                # ── bulk ──
                # flag stability: every flag provably unchanged by that tick
                stable = z3.BoolVal(True)
                for f in self.info.flags:
                    b, a = flags_before.get(f), ex.env.get(f)
                    stable = z3.And(stable, self._val_eq(b, a))
                # counter deltas from the explicit tick
                deltas = {}
                for c in self.info.counters:
                    b, a = counters_before.get(c), ex.env.get(c)
                    deltas[c] = ex.to_num(a) - ex.to_num(b) \
                        if b is not None and a is not None else z3.RealVal(0)
                # candidate bulk lengths
                cands = [end - n]                      # to phase end
                for (var, op, K) in self.info.counter_atoms:
                    if var not in self.info.counters:
                        continue
                    cands.append(self._ticks_to_crossing(
                        ex.to_num(ex.env.get(var, 0.0)), deltas[var],
                        op, K, var))
                n_bulk_raw = cands[0]
                for c in cands[1:]:
                    n_bulk_raw = z3.If(c < n_bulk_raw, c, n_bulk_raw)
                # bulk also requires a drift-free explicit tick — a regime
                # that executes a conditional delay cannot be collapsed
                # (its repetition would shift the schedule per tick)
                n_bulk = z3.If(z3.And(stable, alive, n < end,
                                      off == 0, n_bulk_raw > 0),
                               n_bulk_raw, z3.IntVal(0))
                # emissions during bulk: the SAME guarded emissions repeat.
                # Re-evaluate emission guards is unsound in general; within
                # the fragment they depend on (inputs, flags, counter atoms),
                # all stable across the bulk — so the explicit tick's
                # emission guards carry over.
                for sl in new_slots:
                    self.runs.append(RunSlot(
                        z3.And(sl.guard, n_bulk > 0),
                        sl.time + self.stride,     # first bulk tick
                        self.stride, n_bulk,
                        sl.service, sl.method, sl.args))
                # advance counters in closed form
                for c in self.info.counters:
                    cur = ex.to_num(ex.env.get(c, 0.0))
                    ex.env[c] = cur + z3.ToReal(n_bulk) * deltas[c]
                n = n + n_bulk
            # phase must be consumed within R regimes (dead ticks excepted)
            self.leftovers.append(z3.And(alive, n < end))

    def _val_eq(self, a, b):
        if a is None and b is None:
            return z3.BoolVal(True)
        if a is None or b is None:
            return z3.BoolVal(False)
        return self.ex.values_equal(a, b)

    def _ticks_to_crossing(self, c0, delta, op, K: int, var: str):
        """Ticks until atom (var op K) changes truth value, given per-tick
        delta. Delta is symbolic but drawn from a small literal set — we
        case-split on those literals so every division is by a constant."""
        lits = sorted(self.info.deltas.get(var, set()))
        expr = INF   # delta == 0 (or unseen) → never crosses in this regime
        for d in lits:
            if d == 0:
                continue
            if op in ("==", "!="):
                # equality atoms can flip on any tick — no bulk under a
                # moving counter (sound, merely un-accelerated)
                expr = z3.If(delta == d, z3.IntVal(0), expr)
                continue
            # boundary value the counter must reach to flip the atom
            if op in (">=", ">"):
                B = K if op == ">=" else K + 1
                dist = z3.ToInt(z3.RealVal(B) - c0) if d > 0 else None
            elif op in ("<=", "<"):
                B = K if op == "<=" else K - 1
                dist = z3.ToInt(c0 - z3.RealVal(B)) if d < 0 else None
            else:
                dist = None
            if dist is None:
                cross = INF
            else:
                steps = _ceil_div_pos(z3.If(dist > 0, dist, z3.IntVal(0)),
                                      abs(d))
                # −1 safety margin: templates increment THEN compare inside
                # one tick, so the atom may flip one tick earlier than the
                # entry-value distance suggests. The flip tick then becomes
                # the next regime's explicit tick — sound either way.
                steps = steps - 1
                cross = z3.If(z3.And(dist > 0, steps > 0), steps, z3.IntVal(0))
            expr = z3.If(delta == d, cross, expr)
        return expr


# ── run-aware mismatch ───────────────────────────────────────────────────────

def _rsig(r: RunSlot) -> tuple:
    return (r.method, len(r.args))


def assert_run_mismatch(s: z3.Solver, runs_ir: list[RunSlot],
                        runs_joi: list[RunSlot], t_cmp: int, tol_eff: int,
                        veq) -> Installed:
    def eff_count(r: RunSlot, cutoff: int):
        """Emissions of the run strictly before `cutoff`."""
        raw = z3.If(r.guard, r.count, z3.IntVal(0))
        by_time = _ceil_div_pos(z3.IntVal(cutoff) - r.start, r.stride)
        by_time = z3.If(r.start >= cutoff, z3.IntVal(0), by_time)
        return z3.If(raw < by_time, raw, by_time)

    def starts(runs, tag):
        idx, cur = [], z3.IntVal(0)
        for i, r in enumerate(runs):
            v = z3.Int(f"ridx_{tag}_{i}")
            s.add(v == cur)
            idx.append(v)
            cur = cur + eff_count(r, t_cmp)
        return idx, cur

    sigs = {_rsig(r) for r in runs_ir} | {_rsig(r) for r in runs_joi}
    obs = ObligationSet()
    for si, sig in enumerate(sorted(sigs)):
        label = f"{sig[0]}/{sig[1]}"
        xs = [r for r in runs_ir if _rsig(r) == sig]
        ys = [r for r in runs_joi if _rsig(r) == sig]
        ix, _ = starts(xs, f"ir{si}")
        iy, _ = starts(ys, f"joi{si}")
        # strict/loose totals for tail grace
        cx_strict = z3.Sum([eff_count(r, t_cmp - tol_eff) for r in xs]) \
            if xs else z3.IntVal(0)
        cy_strict = z3.Sum([eff_count(r, t_cmp - tol_eff) for r in ys]) \
            if ys else z3.IntVal(0)
        cx_loose = z3.Sum([eff_count(r, t_cmp) for r in xs]) if xs else z3.IntVal(0)
        cy_loose = z3.Sum([eff_count(r, t_cmp) for r in ys]) if ys else z3.IntVal(0)
        obs.add(f"count:{label}", cx_strict > cy_loose)
        obs.add(f"count:{label}", cy_strict > cx_loose)
        for a, ia in zip(xs, ix):
            na = eff_count(a, t_cmp)
            for b, ib in zip(ys, iy):
                nb = eff_count(b, t_cmp)
                lo = z3.If(ia > ib, ia, ib)
                hi = z3.If(ia + na < ib + nb, ia + na, ib + nb)
                nonempty = hi > lo
                args_eq = z3.And(*[veq(x, y) for x, y in zip(a.args, b.args)]) \
                    if a.args else z3.BoolVal(True)

                def t_at(r, i0, j):
                    return r.start + (j - i0) * r.stride
                d_lo = t_at(a, ia, lo) - t_at(b, ib, lo)
                d_hi = t_at(a, ia, hi - 1) - t_at(b, ib, hi - 1)
                aligned = z3.And(d_lo <= tol_eff, -d_lo <= tol_eff,
                                 d_hi <= tol_eff, -d_hi <= tol_eff)
                obs.add(f"align:{label}",
                        z3.And(nonempty, z3.Not(z3.And(args_eq, aligned))))
    return obs.install(s, tag="run")


# ── entry point ──────────────────────────────────────────────────────────────

def build_miter_accel(ir: dict, joi_block: dict, catalog: dict,
                      tolerance_ms: int = TOLERANCE_MS,
                      assume_quiescent: bool = True, devices=None):
    """Accelerated M2 miter. Raises NotAccelerable → caller falls back."""
    from etc.smt.grounding import compute_grounding, Grounding
    grd = compute_grounding(ir, joi_block, devices) if devices else Grounding()

    m_ir = ir_to_micro2(ir)
    m_joi, period = joi_to_micro2(joi_block)
    if period <= 0:
        raise NotAccelerable("period 0")

    # JoI side must be in the fragment
    info_joi = analyze_fragment(m_joi)
    if info_joi.cond_key is not None:
        info_joi.cond_key = grd.alias.get(info_joi.cond_key, info_joi.cond_key)

    keys, ti = collect_keys_and_types([m_ir, m_joi], grd.alias)
    im = InputModel(keys, ti)
    if info_joi.cond_key is not None and len(keys - {info_joi.cond_key}) > 0:
        # extra keys may exist as write-only effects; conds must stay single-key
        pass

    tol_eff = max(tolerance_ms, period + tolerance_ms)
    min_phase = max(period, 100)
    stride_joi = period + info_joi.uncond_delay_ms

    ex_joi = ITEExec(im, ti, catalog, [], "joi", alias=grd.alias)
    mach_joi = AccelMachine(ex_joi, m_joi, info_joi, stride_joi, im, "joi")
    mach_joi.run_side()
    runs_joi = mach_joi.runs

    # IR side: cycle with edge/sustain wait → transition-bounded ITE unroll
    # (already W-independent); stateless/level cycle → accelerate with the
    # same machine (iteration = tick of length cycle.period).
    runs_ir, ex_ir, leftovers_ir = _encode_ir_side(m_ir, im, ti, catalog,
                                                   info_joi, alias=grd.alias)

    base_constraints: list = []
    base_constraints += im.constraints
    base_constraints += ex_joi.constraints
    base_constraints += ex_ir.constraints
    for key in im.taus:
        taus = im.taus[key]
        for i, tau in enumerate(taus):
            base_constraints.append(tau <= HORIZON_MS - 4 * stride_joi)
            base_constraints.append(tau >= min_phase if i == 0
                                    else tau - taus[i - 1] >= min_phase)
    if assume_quiescent:
        from etc.smt.encode2 import _collect_edge_waits
        edge_waits: list = []
        _collect_edge_waits(m_ir, edge_waits)
        exq = ITEExec(im, ti, catalog, [], "q", alias=grd.alias)
        for w in edge_waits:
            c0 = exq.to_bool(exq.eval(w.cond, exq, z3.IntVal(0)))
            base_constraints.append(z3.Not(c0) if w.edge == "rising" else c0)
        base_constraints += exq.constraints

    # completeness side condition: every phase consumed within R regimes on
    # BOTH sides — else ticks were left unmodeled and the miter's UNSAT
    # would be vacuous there. Checked as its own query; failure → fallback.
    leftover = z3.Or(*(mach_joi.leftovers + leftovers_ir)) \
        if (mach_joi.leftovers or leftovers_ir) else z3.BoolVal(False)
    s_side = z3.Solver()
    for c in base_constraints:
        s_side.add(c)
    s_side.add(leftover)
    if s_side.check() != z3.unsat:
        raise NotAccelerable("phase not consumed within R regimes")

    s = z3.Solver()
    for c in base_constraints:
        s.add(c)
    t_cmp = HORIZON_MS - tol_eff
    veq = ex_joi.values_equal
    inst = assert_run_mismatch(s, runs_ir, runs_joi, t_cmp, tol_eff, veq)
    meta = {"engine": "accel", "period": period, "tol_eff": tol_eff,
            "t_cmp": t_cmp, "horizon": HORIZON_MS,
            "runs_ir": len(runs_ir), "runs_joi": len(runs_joi),
            "alias": grd.alias, "mistargets": grd.mistargets,
            "_obligations": inst}
    return s, im, ti, meta, []


def _encode_ir_side(m_ir: list, im: InputModel, ti: TypeInfo, catalog: dict,
                    info_joi: FragmentInfo, alias: dict | None = None):
    prefix: list = []
    cyc: Optional[MCycle] = None
    for op in m_ir:
        if isinstance(op, MCycle):
            if cyc is not None:
                raise NotAccelerable("two IR cycles")
            cyc = op
        elif cyc is None:
            prefix.append(op)
        else:
            raise NotAccelerable("steps after IR cycle")

    ex = ITEExec(im, ti, catalog, [], "ir", alias=alias)
    ex.exec_seq_timed(prefix, z3.BoolVal(True))
    runs = slots_to_runs(ex.slots)
    ex.slots = []

    if cyc is None:
        return runs, ex, []

    has_edge = any(isinstance(b, MWait) and (b.edge in ("rising", "falling")
                                             or b.for_ms > 0) for b in cyc.body)
    if has_edge:
        # transition-bounded: each iteration consumes an input transition
        n_trans = sum(len(im.taus[k]) for k in im.taus)
        n_iter = min(n_trans + 2, 8)
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
            padded = iter_start + cyc.period_ms
            ex.time = z3.If(z3.And(cont, ex.time - iter_start < cyc.period_ms),
                            padded, ex.time)
        runs += slots_to_runs(ex.slots)
        ex.slots = []
        return runs, ex, []

    # stateless / level cycle → accelerate (iteration == tick), anchored at
    # the prefix completion time (symbolic when the prefix contains a wait)
    body = list(cyc.body)
    if cyc.until is not None:
        body = [MIf(cyc.until, [MBreak()], [])] + body
    if cyc.count:
        raise NotAccelerable("cycle.count on IR accelerated path")
    info_ir = analyze_fragment(body)
    if info_ir.cond_key is not None and alias:
        info_ir.cond_key = alias.get(info_ir.cond_key, info_ir.cond_key)
    if info_ir.cond_key not in (None, info_joi.cond_key):
        raise NotAccelerable("IR/JoI cond keys differ")
    delays = sum(b.ms for b in body if isinstance(b, MDelay))
    stride = max(cyc.period_ms, delays)   # iteration >= period (sim pads)
    info_ir.uncond_delay_ms = 0           # IR pad absorbs top-level delays
    mach = AccelMachine(ex, body, info_ir, stride, im, "ir", base=ex.time)
    mach.run_side(alive0=ex.live)
    return runs + mach.runs, ex, mach.leftovers


def check_pair_accel(ir: dict, joi_block: dict, catalog: dict,
                     tolerance_ms: int = TOLERANCE_MS,
                     timeout_ms: int = 60_000, devices=None,
                     split: bool = False) -> dict:
    import time
    t0 = time.perf_counter()
    try:
        s, im, ti, meta, _ = build_miter_accel(ir, joi_block, catalog,
                                               tolerance_ms, devices=devices)
    except NotAccelerable as e:
        return {"verdict": "NOT_ACCELERABLE", "reason": str(e),
                "elapsed_s": time.perf_counter() - t0}
    except Unsupported as e:
        return {"verdict": "UNSUPPORTED", "reason": str(e),
                "elapsed_s": time.perf_counter() - t0}
    inst = meta.pop("_obligations")
    out = decide(s, inst, lambda m: extract_scenario(m, im, ti),
                 timeout_ms=timeout_ms, split=split,
                 timeout_verdict="TIMEOUT")
    out["elapsed_s"] = time.perf_counter() - t0
    out["meta"] = meta
    return out
