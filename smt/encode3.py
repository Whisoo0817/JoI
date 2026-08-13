"""M3 — symbolic encoder for cron-anchored (IR, JoI) pairs.

Key simplification: cron fire times carry no input dependence, so they are
enumerated CONCRETELY with the simulator's own `_next_cron_fire` (bit-exact
occurrence semantics, including its ignore-day/month quirk). The first
N_OCC occurrences are modeled; input change points are constrained inside
that span.

Per occurrence f_i:
- IR: body re-executes at f_i (one-shot semantics; nested cycle unrolled per
  window). An occurrence is skipped when the previous body overran past it
  (cursor guard), mirroring ir_simulator's advance-then-search loop.
- JoI: script runs at f_i; if period > 0, sub-ticks at +period while the
  next tick still fits in the window (in-tick delays drift the schedule,
  like joi_simulator). `break` terminates the CURRENT window only.
  `:=` initializers run on the very first execution only.

Window bound for sub-ticks: static floor(gap/period); if over the cap, an
effective end is derived from concrete Clock.Hour thresholds in the pair's
until/break conditions (+2 tick margin so a missing break still shows up).

Equivalence claim scope: first N_OCC occurrences, inputs on the 100 ms grid
with phases >= max(period, 100), tolerance max(1s, period+1s).
"""

from __future__ import annotations

from typing import Optional

import z3

from sim import expr as E
from sim.ir_simulator import _next_cron_fire, MAX_T_MS
from sim.scenario import Scenario
from sim.catalog import load_catalog

from smt.encode import (
    TOLERANCE_MS, Unsupported, InputModel, collect_keys_and_types,
    collect_clock_landmarks, extract_scenario, MWait, MDelay, MAssign,
    MEmit, MIf,
)
from smt.encode2 import (
    ITEExec, MCycle, MBreak, ir_to_micro2 as _ir_steps_frontend, _steps2,
    joi_to_micro2 as _joi_frontend_periodic, _joi_stmts2,
    _scan_thresholds_and_delays, assert_ordered_mismatch, MAX_ITERS,
)
from sim import joi_parser as jp
from smt.obligations import decide

N_OCC = 3
TICK_CAP = 128
_MS_PER_DAY = 86_400_000
_MS_PER_HOUR = 3_600_000


def ir_to_micro3(ir: dict) -> tuple[list, str]:
    tl = ir.get("timeline", [])
    head = tl[0] if tl else {}
    if not (isinstance(head, dict) and head.get("op") == "start_at"):
        raise Unsupported("timeline[0] is not start_at")
    if head.get("anchor") != "cron":
        raise Unsupported("not a cron pair")
    cron = head.get("cron", "") or ""
    return _steps2(tl[1:]), cron


def joi_to_micro3(joi_block: dict) -> tuple[list, str, int]:
    cron = (joi_block.get("cron") or "").strip()
    if not cron:
        raise Unsupported("JoI has no cron")
    period = int(joi_block.get("period", 0) or 0)
    stmts = jp.parse_script(joi_block.get("script", "") or "")
    return _joi_stmts2(stmts), cron, period


def enumerate_fires(cron: str, n: int) -> list[int]:
    """First n concrete fire times (ms), via the simulator's own logic."""
    sc = Scenario()
    fires: list[int] = []
    t = 0
    while len(fires) < n:
        f = _next_cron_fire(cron, t, sc)
        if f is None or f >= MAX_T_MS:
            break
        fires.append(f)
        t = f + 60_000
    return fires


def _clock_hour_thresholds(ops_lists: list[list]) -> set[int]:
    """Concrete Clock.Hour comparison constants in until/break/if conds."""
    hours: set[int] = set()

    def walk_expr(node):
        if isinstance(node, E.BinaryOp):
            for side, other in ((node.left, node.right), (node.right, node.left)):
                from smt.encode import _node_key
                if _node_key(side) == "clock.hour" and isinstance(other, E.Lit) \
                        and isinstance(other.value, (int, float)):
                    hours.add(int(other.value))
            walk_expr(node.left)
            walk_expr(node.right)
        elif isinstance(node, E.UnaryOp):
            walk_expr(node.operand)

    def walk(ops):
        for op in ops:
            if isinstance(op, MIf):
                walk_expr(op.cond)
                walk(op.then)
                walk(op.els)
            elif isinstance(op, MWait):
                walk_expr(op.cond)
            elif isinstance(op, MCycle):
                if op.until is not None:
                    walk_expr(op.until)
                walk(op.body)

    for ol in ops_lists:
        walk(ol)
    return hours


def _is_pure_clock(node) -> bool:
    """True iff the expression reads only the clock (no devices, no vars) —
    then its truth value at a concrete time is concretely computable."""
    from smt.encode import _node_key
    if isinstance(node, E.Lit):
        return True
    if isinstance(node, E.ClockRef):
        return True
    k = _node_key(node)
    if k is not None:
        return k in ("clock.hour", "clock.minute", "clock.time")
    if isinstance(node, E.UnaryOp):
        return _is_pure_clock(node.operand)
    if isinstance(node, E.BinaryOp):
        return _is_pure_clock(node.left) and _is_pure_clock(node.right)
    return False


def _clock_eval(node, t: int):
    """Concretely evaluate a pure-clock expression at time t (ms)."""
    ms_in_day = t % _MS_PER_DAY
    hour = ms_in_day // _MS_PER_HOUR
    minute = (ms_in_day // 60_000) % 60
    clock = {"time": hour * 100 + minute, "hour": hour, "minute": minute}
    from smt.encode import _node_key
    if isinstance(node, E.Lit):
        return node.value
    if isinstance(node, E.ClockRef):
        return clock.get(node.field)
    k = _node_key(node)
    if k is not None:
        return clock.get(k.split(".", 1)[1])
    if isinstance(node, E.UnaryOp):
        v = _clock_eval(node.operand, t)
        return (not v) if node.op == "not" else -v
    if isinstance(node, E.BinaryOp):
        a, b = _clock_eval(node.left, t), _clock_eval(node.right, t)
        return {"and": lambda: bool(a) and bool(b), "or": lambda: bool(a) or bool(b),
                "==": lambda: a == b, "!=": lambda: a != b,
                "<": lambda: a < b, ">": lambda: a > b,
                "<=": lambda: a <= b, ">=": lambda: a >= b,
                "+": lambda: a + b, "-": lambda: a - b}[node.op]()
    raise ValueError("not pure clock")


def first_clock_true(node, times: list[int]) -> Optional[int]:
    """Index of the first time where the pure-clock cond is true, else None.
    Returns None too when the cond is not pure-clock (no shortcut allowed —
    a never-true quirk like `clock.time >= 2400` must NOT truncate the
    unroll, so only a concretely-verified true stops it)."""
    if node is None or not _is_pure_clock(node):
        return None
    for i, t in enumerate(times):
        try:
            if _clock_eval(node, t):
                return i
        except Exception:
            return None
    return None


def _joi_break_conds(ops: list) -> list:
    """Conditions of `if (pure-clock) { ... break ... }` guards in the script."""
    out = []
    for op in ops:
        if isinstance(op, MIf):
            if any(isinstance(x, MBreak) for x in op.then):
                out.append(op.cond)
            out.extend(_joi_break_conds(op.then))
            out.extend(_joi_break_conds(op.els))
    return out


def _window_ticks(fire: int, gap: int, period: int, break_conds: list) -> int:
    """Sub-tick unroll count for one window (excluding the fire-time exec).
    Bounded by the first tick where a pure-clock break provably fires."""
    if period <= 0:
        return 0
    static = gap // period
    times = [fire + k * period for k in range(min(static, 4 * TICK_CAP) + 1)]
    bounds = [i for c in break_conds
              if (i := first_clock_true(c, times)) is not None]
    n = min(bounds) + 2 if bounds else static   # +2: a missing break surfaces
    n = min(n, static)
    if n > TICK_CAP:
        raise Unsupported(f"window needs {n} sub-ticks > {TICK_CAP}")
    return n


# ── IR occurrence execution ──────────────────────────────────────────────────

IR_ITER_CAP = 96


def run_ir_cron(ex: ITEExec, micro: list, fires: list[int], gaps: list[int],
                horizon: int) -> None:
    cursor = z3.IntVal(0)   # earliest time the next occurrence may start
    for f in fires:
        active = cursor <= z3.IntVal(f)
        ex.time = z3.IntVal(f)
        ex.live = active
        _exec_ir_body(ex, micro, f, horizon)
        end = ex.time
        cursor = z3.If(active, end + 60_000, cursor)


def _exec_ir_body(ex: ITEExec, micro: list, fire: int, horizon: int) -> None:
    """One occurrence: prefix + optional cycle.

    The cycle is NOT window-bounded: the simulator's inner cycle only exits
    on until/break — if neither fires, it runs past every later cron fire
    (which the cursor guard then skips). We unroll to the modeled horizon;
    a pure-clock until that provably fires earlier shortens the unroll."""
    prefix: list = []
    cyc: Optional[MCycle] = None
    for op in micro:
        if isinstance(op, MCycle):
            if cyc is not None:
                raise Unsupported("two top-level cycles")
            cyc = op
        elif cyc is None:
            prefix.append(op)
        else:
            raise Unsupported("steps after cycle in cron body")
    ex.exec_seq_timed(prefix, z3.BoolVal(True))
    if cyc is None:
        return
    has_edge = any(isinstance(b, MWait) and (b.edge in ("rising", "falling")
                                             or b.for_ms > 0) for b in cyc.body)
    if has_edge:
        raise Unsupported("edge/sustain wait in cron cycle body")
    period = max(cyc.period_ms, 1)
    static = -(-(horizon - fire) // period)
    times = [fire + k * period for k in range(min(static, 4 * IR_ITER_CAP) + 1)]
    bound = first_clock_true(cyc.until, times)
    n_iter = min(bound + 2, static) if bound is not None else static
    if n_iter > IR_ITER_CAP:
        raise Unsupported(f"cron cycle unroll {n_iter} > {IR_ITER_CAP}")
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
        # Pad to the period ONLY while the cycle is still running — the sim
        # stops advancing time the moment until/break exits the loop, and an
        # unguarded pad here overshoots the body end time, which (in cron
        # mode) wrongly skips the next occurrence via the cursor guard.
        padded = iter_start + cyc.period_ms
        ex.time = z3.If(z3.And(cont, ex.time - iter_start < cyc.period_ms),
                        padded, ex.time)
    ex.live = cont


# ── JoI occurrence execution ─────────────────────────────────────────────────

def run_joi_cron(ex: ITEExec, micro: list, fires: list[int], gaps: list[int],
                 period: int) -> None:
    from smt.encode2 import _exec_tick
    break_conds = _joi_break_conds(micro)
    first = True
    for f, gap in zip(fires, gaps):
        window_end = f + gap
        window_alive = z3.BoolVal(True)   # break only kills THIS window
        t_k = z3.IntVal(f)
        n_ticks = _window_ticks(f, gap, period, break_conds)
        for k in range(n_ticks + 1):      # k=0 is the fire-time exec
            if k > 0:
                # sim: `while t + period < window_end: advance; exec`
                fits = t_k + period < window_end
                window_alive = z3.And(window_alive, fits)
                t_k = t_k + period
            ex.time = t_k
            ex.live = window_alive
            ex.break_hit = z3.BoolVal(False)
            offset = _exec_tick(ex, micro, z3.BoolVal(True),
                                0 if first else 1, z3.IntVal(0))
            first = False
            window_alive = z3.And(window_alive, z3.Not(ex.break_hit))
            t_k = t_k + offset


# ── run-based acceleration (M3 flavor) ──────────────────────────────────────
#
# When the per-window tick/iteration count blows the unroll caps, pairs whose
# window bounds are PURE-CLOCK (concrete truncation) and whose bodies are
# stateless — emits, optionally guarded by a single-key input condition —
# admit a closed form: every emission grid (start, stride, count) is fully
# concrete; only the input regime is symbolic. Each (window × input regime ×
# emit) becomes one RunSlot; the accel run comparator decides. Outside the
# fragment → NotAccelerable → the original Unsupported stands. Known limit:
# a body that reads back its own effect key (state feedback, e.g. a pump
# toggle) is NOT in the fragment.


def _first_true_tick(cond, fire: int, period: int, n_max: int):
    """First k in [0, n_max) with the pure-clock cond true at fire + k*period,
    else None. Clock granularity is one minute, so dense grids scan minute
    boundaries instead of ticks."""
    if n_max <= 2000 or period >= 60_000:
        for k in range(n_max):
            if _clock_eval(cond, fire + k * period):
                return k
        return None
    t, end = fire, fire + n_max * period
    while t < end:
        if _clock_eval(cond, t):
            k = 0 if t <= fire else -(-(t - fire) // period)
            return k if k < n_max else None
        t = (t // 60_000 + 1) * 60_000
    return None


def _scan_stateless_body(ops: list, breaks: list, emits: list) -> None:
    """Fragment shape: `if (pure-clock) break` guards (all BEFORE any emit —
    the break tick then emits nothing), top-level emits, and single-level
    `if (device cond) { emits } [else { emits }]`. Raises NotAccelerable."""
    from smt.accel import NotAccelerable
    for op in ops:
        if isinstance(op, MIf):
            if any(isinstance(x, MBreak) for x in op.then + op.els):
                if emits:
                    raise NotAccelerable("emit before break guard")
                if op.els or any(not isinstance(x, MBreak) for x in op.then):
                    raise NotAccelerable("break guard shape")
                if not _is_pure_clock(op.cond):
                    raise NotAccelerable("non-clock break cond")
                breaks.append(op.cond)
                continue
            if _is_pure_clock(op.cond):
                raise NotAccelerable("clock-guarded emit")
            for x in op.then + op.els:
                if not isinstance(x, MEmit):
                    raise NotAccelerable("non-emit under guard")
            for x in op.then:
                emits.append((op.cond, True, x))
            for x in op.els:
                emits.append((op.cond, False, x))
        elif isinstance(op, MEmit):
            emits.append((None, True, op))
        else:
            raise NotAccelerable(f"op outside fragment: {type(op).__name__}")


def _runs_for_windows(ex: ITEExec, im: InputModel, emits: list,
                      windows: list, alias: dict):
    """windows: (fire, period, n_e) with everything concrete. One RunSlot per
    (window × emit × input regime); unguarded emits need no regime split."""
    from smt.accel import RunSlot, _ceil_div_pos, NotAccelerable, _expr_keys
    from smt.fragment import _effect_key
    sigs = set()
    for cond, pol, op in emits:
        svc_c, m_c = E.canonical_key(op.service, op.method)
        sg = (m_c, len(op.args))
        if sg in sigs:
            raise NotAccelerable("duplicate emission signature")
        sigs.add(sg)

    cond_keys: set = set()
    for cond, pol, op in emits:
        if cond is not None:
            _expr_keys(cond, cond_keys)
    cond_keys = {alias.get(k, k) for k in cond_keys}
    if len(cond_keys) > 1:
        raise NotAccelerable("multi-key guard")
    cond_key = next(iter(cond_keys)) if cond_keys else None
    for cond, pol, op in emits:
        svc_c, m_c = E.canonical_key(op.service, op.method)
        ek = _effect_key(svc_c, m_c)
        ek = alias.get(ek, ek) if ek is not None else None
        if cond_key is not None and ek == cond_key:
            raise NotAccelerable("state feedback (guard reads own effect)")

    def emit_run(op, guard, t_start, stride, count, runs):
        n0 = len(ex.slots)
        ex._emit_ite(op, guard, t_start)
        for sl in ex.slots[n0:]:
            runs.append(RunSlot(sl.guard, sl.time, stride, count,
                                sl.service, sl.method, sl.args))
        del ex.slots[n0:]

    runs: list = []
    taus = im.taus.get(cond_key, []) if cond_key else []
    for (f, period, n_e) in windows:
        if n_e <= 0:
            continue
        end = f + n_e * period
        for cond, pol, op in emits:
            if cond is None:
                emit_run(op, z3.BoolVal(True), z3.IntVal(f), period,
                         z3.IntVal(n_e), runs)
                continue
            bounds = [z3.IntVal(f)] + list(taus) + [z3.IntVal(end)]
            for j in range(len(bounds) - 1):
                lo = z3.If(bounds[j] < f, z3.IntVal(f), bounds[j])
                hi = z3.If(bounds[j + 1] > end, z3.IntVal(end), bounds[j + 1])
                k_lo = _ceil_div_pos(lo - f, period)
                k_hi = _ceil_div_pos(hi - f, period)
                cnt = z3.If(k_hi > k_lo, k_hi - k_lo, z3.IntVal(0))
                start = f + k_lo * period
                g = ex.to_bool(ex.eval(cond, ex, start))
                if not pol:
                    g = z3.Not(g)
                emit_run(op, z3.And(cnt > 0, g), start, period, cnt, runs)
    return runs


def _build_miter_m3_runs(m_ir: list, m_joi: list, period: int,
                         fires: list[int], gaps: list[int], horizon: int,
                         im: InputModel, ti, clocks, catalog, g,
                         tolerance_ms: int):
    from smt.accel import NotAccelerable, assert_run_mismatch
    if period <= 0:
        raise NotAccelerable("period 0")

    # ── JoI: windows bounded by next fire and pure-clock breaks ──
    breaks_joi: list = []
    emits_joi: list = []
    _scan_stateless_body(m_joi, breaks_joi, emits_joi)
    win_joi = []
    for f, gap in zip(fires, gaps):
        n_fit = max(1, -(-gap // period))
        n_e = n_fit
        for c in breaks_joi:
            k = _first_true_tick(c, f, period, n_fit)
            if k is not None:
                n_e = min(n_e, k)
        win_joi.append((f, period, n_e))

    # ── IR: single cycle, pure-clock until, cursor occurrence-skip ──
    prefix: list = []
    cyc = None
    for op in m_ir:
        if isinstance(op, MCycle):
            if cyc is not None:
                raise NotAccelerable("two cycles")
            cyc = op
        elif cyc is None:
            prefix.append(op)
        else:
            raise NotAccelerable("steps after cycle")
    if prefix or cyc is None:
        raise NotAccelerable("IR prefix outside fragment")
    if cyc.count:
        raise NotAccelerable("cycle.count")
    if cyc.until is not None and not _is_pure_clock(cyc.until):
        raise NotAccelerable("non-clock until")
    if any(isinstance(b, MDelay) for b in cyc.body):
        raise NotAccelerable("delay in cycle body")
    breaks_ir: list = []
    emits_ir: list = []
    _scan_stateless_body(cyc.body, breaks_ir, emits_ir)
    if breaks_ir:
        raise NotAccelerable("break inside IR cycle body")
    p_ir = max(cyc.period_ms, 1)
    win_ir = []
    cursor = 0
    for f, gap in zip(fires, gaps):
        if cursor > f:
            continue                      # occurrence swallowed by overrun
        n_static = max(1, -(-(horizon - f) // p_ir))
        k_u = (_first_true_tick(cyc.until, f, p_ir, n_static)
               if cyc.until is not None else None)
        n_e = k_u if k_u is not None else n_static
        end_t = f + n_e * p_ir
        win_ir.append((f, p_ir, n_e))
        cursor = end_t + 60_000

    ex = ITEExec(im, ti, catalog, clocks, "acc3", alias=g.alias)
    runs_joi = _runs_for_windows(ex, im, emits_joi, win_joi, g.alias)
    runs_ir = _runs_for_windows(ex, im, emits_ir, win_ir, g.alias)

    tol_eff = max(tolerance_ms, period + tolerance_ms)
    min_phase = max(period, 100)
    t_cmp = horizon - tol_eff
    s = z3.Solver()
    for c in im.constraints + ex.constraints:
        s.add(c)
    for key in im.taus:
        taus = im.taus[key]
        for i, tau in enumerate(taus):
            s.add(tau <= horizon)
            if i > 0:
                s.add(tau - taus[i - 1] >= min_phase)
    inst = assert_run_mismatch(s, runs_ir, runs_joi, t_cmp, tol_eff,
                               ex.values_equal)
    meta = {"engine": "m3-runs", "fires": fires, "gaps": gaps,
            "period": period, "alias": g.alias, "mistargets": g.mistargets,
            "tol_eff": tol_eff, "t_cmp": t_cmp,
            "win_joi": [(f, n) for f, _, n in win_joi],
            "win_ir": [(f, n) for f, _, n in win_ir],
            "_obligations": inst}
    return s, im, ti, meta


# ── miter ────────────────────────────────────────────────────────────────────

def build_miter_m3(ir: dict, joi_block: dict, catalog: dict,
                   tolerance_ms: int = TOLERANCE_MS, devices=None):
    m_ir, cron_ir = ir_to_micro3(ir)
    m_joi, cron_joi, period = joi_to_micro3(joi_block)
    if cron_ir.strip() != cron_joi.strip():
        # differing cron strings — compare occurrence sets; if they differ,
        # that is itself a (deterministic) divergence
        f_a = enumerate_fires(cron_ir, N_OCC)
        f_b = enumerate_fires(cron_joi, N_OCC)
        if f_a != f_b:
            return "CRON_MISMATCH", {"ir_fires": f_a, "joi_fires": f_b}, None, None

    # Occurrence count must dominate the tolerance (E-B finding, cron flavor
    # of the M2 window/grace defect): with an hourly cron + hourly period,
    # tol_eff is one hour — 3 modeled windows minus the tail-grace band left
    # only the FIRST window strictly compared, so alternation/call mutants
    # in later windows passed as EQUIV. Scale N_OCC so the strictly-compared
    # span covers several windows.
    probe = enumerate_fires(cron_ir, 2)
    if not probe:
        return "NO_FIRES", None, None, None   # both silent — equivalent
    gap0 = (probe[1] - probe[0]) if len(probe) > 1 else _MS_PER_DAY
    tol_probe = max(tolerance_ms, period + tolerance_ms)
    n_occ = max(N_OCC, min(8, -(-6 * tol_probe // max(gap0, 1)) + 2))

    fires = enumerate_fires(cron_ir, n_occ + 1)
    if not fires:
        return "NO_FIRES", None, None, None
    gaps = []
    for i, f in enumerate(fires[:n_occ]):
        nxt = fires[i + 1] if i + 1 < len(fires) else min(f + _MS_PER_DAY, MAX_T_MS)
        gaps.append(nxt - f)
    fires = fires[:n_occ]

    from smt.grounding import compute_grounding, Grounding
    g = compute_grounding(ir, joi_block, devices) if devices else Grounding()
    keys, ti = collect_keys_and_types([m_ir, m_joi], g.alias)
    clocks = collect_clock_landmarks([m_ir, m_joi])
    im = InputModel(keys, ti)

    horizon = fires[-1] + gaps[-1]
    try:
        ex_ir = ITEExec(im, ti, catalog, clocks, "ir", alias=g.alias)
        ex_joi = ITEExec(im, ti, catalog, clocks, "joi", alias=g.alias)
        run_ir_cron(ex_ir, m_ir, fires, gaps, horizon)
        run_joi_cron(ex_joi, m_joi, fires, gaps, period)
    except Unsupported as e:
        # tick/iteration caps blown → run-based closed form for the
        # pure-clock-bounded stateless fragment (fresh InputModel: the
        # aborted execution above already consumed tau symbols)
        from smt.accel import NotAccelerable
        im2 = InputModel(keys, ti)
        try:
            return _build_miter_m3_runs(m_ir, m_joi, period, fires, gaps,
                                        horizon, im2, ti, clocks, catalog, g,
                                        tolerance_ms)
        except NotAccelerable:
            raise e
    tol_eff = max(tolerance_ms, period + tolerance_ms)
    min_phase = max(period, 100)
    t_cmp = horizon - tol_eff

    s = z3.Solver()
    for c in im.constraints:
        s.add(c)
    for c in ex_ir.constraints + ex_joi.constraints:
        s.add(c)
    for key in im.taus:
        taus = im.taus[key]
        for i, tau in enumerate(taus):
            s.add(tau <= horizon)
            if i > 0:
                s.add(tau - taus[i - 1] >= min_phase)

    inst = assert_ordered_mismatch(s, ex_ir, ex_joi, t_cmp, tol_eff)
    meta = {"fires": fires, "gaps": gaps, "period": period,
            "alias": g.alias, "mistargets": g.mistargets,
            "tol_eff": tol_eff, "t_cmp": t_cmp,
            "slots_ir": len(ex_ir.slots), "slots_joi": len(ex_joi.slots),
            "_obligations": inst}
    return s, im, ti, meta


def check_pair_m3(ir: dict, joi_block: dict, catalog: dict,
                  tolerance_ms: int = TOLERANCE_MS,
                  timeout_ms: int = 0, devices=None,
                  split: bool = False) -> dict:
    import time
    t0 = time.perf_counter()
    try:
        s, im, ti, meta = build_miter_m3(ir, joi_block, catalog, tolerance_ms,
                                         devices=devices)
    except Unsupported as e:
        return {"verdict": "UNSUPPORTED", "reason": str(e),
                "elapsed_s": time.perf_counter() - t0}
    if s == "CRON_MISMATCH":
        return {"verdict": "DIVERGE", "reason": "cron occurrence sets differ",
                "model": {}, "meta": im, "elapsed_s": time.perf_counter() - t0}
    if s == "NO_FIRES":
        return {"verdict": "EQUIV", "reason": "no cron fires in horizon",
                "elapsed_s": time.perf_counter() - t0}
    inst = meta.pop("_obligations")
    out = decide(s, inst, lambda m: extract_scenario(m, im, ti),
                 timeout_ms=timeout_ms, split=split,
                 timeout_verdict="TIMEOUT" if timeout_ms else "UNKNOWN")
    out["elapsed_s"] = time.perf_counter() - t0
    out["meta"] = meta
    return out
