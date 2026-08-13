"""Exhaustive state-space explorer over the pure tick interpreter.

The map-building loop discussed in the design notes:

    frontier ← initial states (one per feasible input combo at t0)
    repeat: pop a state, try every (input combo × dwell), run step() once,
            canonicalize the result, enqueue if unseen.

Finiteness comes from canonicalization (`normalize`), not from luck:
- bool/enum registers: finite as-is
- counters (reset/increment only): saturated one past the largest compared
  constant — beyond it the program cannot distinguish values
- timestamp registers: keyed by (sentinel | region between compared
  thresholds | FAR beyond the largest) plus the pairwise ordering of the
  registers' capture times (which timer fires first matters)
- calendar: hour region (against compared hour constants) + weekday
- absolute time is NEVER in the key — states reached at different wall
  times with the same normalized view are one node (that merge is what
  closes infinite time into a finite graph)

Dwell (time-jump) rule: from a state, the 1-tick successor always runs.
Longer dwells (skip to just after the next timer crossing / calendar
boundary) are allowed only when a probe tick with the held input is a
stutter (same key, no actions) — the conservative version of the two
exceptions (armed edge/counter idioms walk tick-by-tick; every-tick
emitters never jump, so no multiplicity is lost).

Pre-flight `finiteness_check` refuses exploration when a carried variable
fits none of the finite shapes — surfaced by name, never a silent hang.

Run:  python -m explorer.explore     (door demo + all periodic scenarios)
"""

from __future__ import annotations

import itertools
import time as _time
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any

from . import expr as expr_mod
from . import joi_parser as jp
from .expr import canonical_key
from .interp import Unsupported, clock_state, parse, step, world_key
from .predicates import (CAL_KEYS, CMP_OPS, TS_KEY, VarInfo, classify_vars,
                         expr_reads, stmt_exprs, walk_stmts,
                         _fold_with_params)


def _closure_device_reads(node, defs, vars_, visiting=frozenset()) -> set:
    """Device keys read by an expression, following wire definitions."""
    out: set = set()
    reads: list = []
    expr_reads(node, reads)
    for k, nm in reads:
        if k == "device":
            if nm not in CAL_KEYS and nm != TS_KEY:
                out.add(nm)
        elif k == "var" and nm not in visiting:
            vi = vars_.get(nm)
            if vi and vi.role == "wire" and not vi.timestamp:
                for d in defs.get(nm, []):
                    out |= _closure_device_reads(d, defs, vars_,
                                                 visiting | {nm})
    return out

DAY_MS = 86_400_000
STATE_CAP = 200_000        # refuse-to-hang backstop
STEP_CAP = 2_000_000


# ── Axis derivation: which inputs exist and which cells each one has ─────────

@dataclass
class Axes:
    cells: dict[str, list]              # world key → representative values
    hours: list[int]                    # compared hour constants
    weekdays_used: bool
    holiday_used: bool
    ts_thresholds: list[float]          # TIMER constants (seconds)
    counter_caps: dict[str, float]      # state var → saturation point
    param_reads: list[str]              # parameterized reads (unsupported v1)
    mirror_gv: list[str] = field(default_factory=list)
    minutes: list[int] = field(default_factory=list)   # compared minute consts
    hour_ops: list = field(default_factory=list)       # (op, const) on hour
    # (op, const) pairs the code actually compares on each numeric key —
    # what makes two raw readings indistinguishable. Deployment replay needs
    # it to place an observed value in its cell rather than matching the
    # representative literally (July is the same cell as the April rep).
    cell_preds: dict = field(default_factory=dict)
    # GVs this scenario both writes and reads back (write-on-change mirrors).
    # Their pre-existing value matters — the explorer enumerates initial
    # values instead of assuming a runtime default (unseeded read = None is
    # exactly the seed-fault class and must stay visible).


def _read_key(node: Any) -> str | None:
    """World key for a sensor-read AST node, or None."""
    if isinstance(node, jp.CallExpr) and node.args is None:
        return world_key(node.tags, node.service, node.method)
    if isinstance(node, expr_mod.QuantRef):
        svc = node.tags[-1] if node.tags else ""
        return world_key(node.tags, svc, node.member)
    if isinstance(node, expr_mod.DeviceRef):
        return node.key
    return None


def _gv_read_name(node: Any) -> str | None:
    if isinstance(node, jp.CallExpr) and node.args is not None:
        svc, m = canonical_key(node.service, node.method)
        if svc == "globalvariable" and m.startswith("get"):
            a0 = node.args[0]
            if isinstance(a0, expr_mod.Lit):
                return str(a0.value)
    return None


_MIRROR = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "==": "==", "!=": "!="}


def _apply(op: str, x: float, c: float) -> bool:
    return {"<": x < c, ">": x > c, "<=": x <= c, ">=": x >= c,
            "==": x == c, "!=": x != c}[op]


def _const_options(node: Any, vars_: dict, defs: dict,
                   visiting: frozenset = frozenset()) -> set | None:
    """Every constant value an expression can evaluate to, following wires
    whose definitions are all constant (e.g. seasonal `max_humid` set to 60
    or 55 in branches). None = not resolvable to constants. More options
    only refine the partition — never unsound."""
    v = _fold_with_params(node, vars_)
    if v is not None and isinstance(v, (int, float)) and not isinstance(v, bool):
        return {float(v)}
    if isinstance(node, expr_mod.VarRef):
        vi = vars_.get(node.name)
        if vi is None or node.name in visiting:
            return None
        if vi.role == "wire" and not vi.timestamp:
            opts: set = set()
            for d in defs.get(node.name, []):
                o = _const_options(d, vars_, defs, visiting | {node.name})
                if o is None:
                    return None
                opts |= o
            return opts if 0 < len(opts) <= 16 else None
    return None


def _loop_ranges(stmts: list, vars_: dict, defs: dict) -> dict[str, range]:
    """Loop counters with statically known bounds: `h = a; loop (h <= b)
    { ... h = h + 1 }` → h ∈ range(a, b+1). Used to enumerate the keys of
    parameterized query reads like forecast(h)."""
    out: dict[str, range] = {}
    for s in walk_stmts(stmts):
        if not isinstance(s, jp.Loop):
            continue
        c = s.cond
        if not (isinstance(c, expr_mod.BinaryOp) and c.op in ("<=", "<")
                and isinstance(c.left, expr_mod.VarRef)):
            continue
        hi = _fold_with_params(c.right, vars_)
        nm = c.left.name
        if not isinstance(hi, (int, float)):
            continue
        lo = None
        selfinc = False
        for d in defs.get(nm, []):
            v = _fold_with_params(d, vars_)
            if isinstance(v, (int, float)):
                lo = int(v) if lo is None else min(lo, int(v))
            elif (isinstance(d, expr_mod.BinaryOp) and d.op == "+"
                  and isinstance(d.left, expr_mod.VarRef) and d.left.name == nm
                  and _fold_with_params(d.right, vars_) == 1):
                selfinc = True
        if lo is not None and selfinc:
            out[nm] = range(lo, int(hi) + 1) if c.op == "<=" \
                else range(lo, int(hi))
    return out


def derive_axes(stmts: list, vars_: dict[str, VarInfo]) -> Axes:
    num_consts: dict[str, set] = {}   # key → {(op, const)} as USED by the code
    str_consts: dict[str, set] = {}
    bool_keys: set[str] = set()
    gv_bool: set[str] = set()
    gv_str: dict[str, set] = {}
    hours: set[int] = set()
    hour_ops: set = set()
    minutes: set[int] = set()
    weekdays_used = False
    holiday_used = False
    ts_thresholds: set[float] = set()
    counter_caps: dict[str, float] = {}
    param_reads: list[str] = []
    gv_written: set[str] = set()

    from .predicates import var_defs
    defs = var_defs(stmts)
    ranges = _loop_ranges(stmts, vars_, defs)

    def _query_keys(node: Any) -> list[str] | None:
        """Keys of an expression-position query read (non-GV call with
        args): literal args → one key; a loop-counter arg → one key per
        value in its range; otherwise unresolvable → param_reads."""
        if not (isinstance(node, jp.CallExpr) and node.args is not None):
            return None
        svc, m = canonical_key(node.service, node.method)
        if svc in ("globalvariable", "clock"):
            return None
        base = world_key(node.tags, node.service, node.method)
        if all(isinstance(a, expr_mod.Lit) for a in node.args):
            return [f"{base}({','.join(repr(a.value) for a in node.args)})"]
        if len(node.args) == 1 and isinstance(node.args[0], expr_mod.VarRef) \
                and node.args[0].name in ranges:
            return [f"{base}({i!r})" for i in ranges[node.args[0].name]]
        param_reads.append(f"{base}(unresolvable args)")
        return []

    # GVs this scenario writes are internal state, not input axes
    for s in walk_stmts(stmts):
        call = s.call if isinstance(s, jp.CallStmt) else (
            s.rhs if isinstance(s, jp.Assign) and isinstance(s.rhs, jp.CallExpr)
            else None)
        if isinstance(call, jp.CallExpr) and call.args is not None:
            svc, m = canonical_key(call.service, call.method)
            if svc == "globalvariable" and m.startswith("set"):
                a0 = call.args[0]
                if isinstance(a0, expr_mod.Lit):
                    gv_written.add(str(a0.value))

    gv_read: set[str] = set()

    def note_read(node: Any, const: Any, op: str) -> None:
        nonlocal weekdays_used, holiday_used
        key = _read_key(node)
        keys = [key] if key is not None else (_query_keys(node) or [])
        for key in keys:
            if key == "clock.hour":
                if isinstance(const, (int, float)):
                    hours.add(int(const))
                    hour_ops.add((op, int(const)))
                continue
            if key == "clock.weekday":
                weekdays_used = True
                continue
            if key == "clock.isholiday":
                holiday_used = True
                continue
            if key == "clock.minute":
                if isinstance(const, (int, float)):
                    minutes.add(int(const))
                continue
            if key == "clock.timestamp":
                continue
            if isinstance(const, bool) or const is None:
                bool_keys.add(key)
            elif isinstance(const, str):
                str_consts.setdefault(key, set()).add(const)
            elif isinstance(const, (int, float)):
                num_consts.setdefault(key, set()).add((op, float(const)))
            else:
                bool_keys.add(key)
        if keys:
            return
        g = _gv_read_name(node)
        if g is not None:
            gv_read.add(g)
            if g not in gv_written:
                if isinstance(const, str):
                    gv_str.setdefault(g, set()).add(const)
                else:
                    gv_bool.add(g)

    def _is_duration(nm: str) -> bool:
        """Timestamp var holding a DIFFERENCE (`elapsed = now - reg`), not a
        capture time — its comparison constants are duration thresholds."""
        dlist = defs.get(nm, [])
        return any(isinstance(d, expr_mod.BinaryOp) and d.op == "-"
                   for d in dlist)

    def visit_atom(atom: Any) -> None:
        left, right = atom.left, atom.right
        op = atom.op[:-1] if atom.op.endswith("|") else atom.op
        lc = _fold_with_params(left, vars_)
        rc = _fold_with_params(right, vars_)
        # timestamp thresholds: direct `now - reg > c` differences AND
        # duration-carrying vars (`elapsed = now - reg; elapsed > c`)
        for side, other in ((left, right), (right, left)):
            opts = _const_options(other, vars_, defs)
            if not opts:
                continue
            if isinstance(side, expr_mod.BinaryOp) and side.op == "-":
                reads: list = []
                expr_reads(side, reads)
                if any(nm == "clock.timestamp" or
                       (k == "var" and vars_.get(nm, VarInfo("x")).timestamp)
                       for k, nm in reads):
                    ts_thresholds.update(opts)
                    return
            if isinstance(side, expr_mod.VarRef):
                vi = vars_.get(side.name)
                if vi is not None and vi.timestamp and _is_duration(side.name):
                    ts_thresholds.update(opts)
                    return
        # sensor / gv / calendar reads against the folded constant; the op
        # is mirrored when the constant sits on the left ("c < x" ≡ "x > c")
        for side, other, const, o in ((left, right, rc, op),
                                      (right, left, lc, _MIRROR.get(op, op))):
            opts = _const_options(other, vars_, defs)
            if const is None and opts and _read_key(side) is not None:
                for c in opts:      # direct read vs constant-valued wire
                    note_read(side, c, o)
            else:
                note_read(side, const, o)
            # affine expression over sensor reads (e.g. avg = Σreads/k or a
            # seasonal wire bound) compared to constant option(s): distribute
            # every option to every read it contains. Exact for k=1; k≥2
            # joint regions need the feasibility filter — noted, not silent.
            if opts and _read_key(side) is None:
                for kk in _closure_device_reads(side, defs, vars_):
                    for c in opts:
                        num_consts.setdefault(kk, set()).add((o, c))
            if isinstance(side, expr_mod.VarRef):
                vi = vars_.get(side.name)
                if vi is not None and vi.role == "state" and not vi.timestamp \
                        and isinstance(const, (int, float)) \
                        and not isinstance(const, bool):
                    counter_caps[side.name] = max(
                        counter_caps.get(side.name, 0), float(const))
                if vi is not None and vi.timestamp \
                        and isinstance(const, (int, float)) and const == 0:
                    pass  # sentinel — handled in normalize
                # expand single-def wires so `hr >= 7` reaches clock.hour
                if vi is not None and vi.role == "wire":
                    from .predicates import var_defs
                    # cheap: resolved by caller passing defs; see below

    # substitute single-def wires before atom collection so calendar consts
    # and sensor keys are found through them

    def resolve(node: Any, depth: int = 0) -> Any:
        if depth > 4 or not isinstance(node, expr_mod.VarRef):
            return node
        vi = vars_.get(node.name)
        if vi is not None and vi.role == "wire" \
                and len(defs.get(node.name, [])) == 1:
            return resolve(defs[node.name][0], depth + 1)
        return node

    def collect(node: Any) -> None:
        if isinstance(node, expr_mod.BinaryOp):
            if node.op in ("and", "or"):
                collect(node.left)
                collect(node.right)
                return
            if node.op in CMP_OPS:
                a = expr_mod.BinaryOp(node.op, resolve(node.left),
                                      resolve(node.right))
                visit_atom(a)
                return
        if isinstance(node, expr_mod.UnaryOp) and node.op == "not":
            collect(node.operand)

    for s in walk_stmts(stmts):
        for e in stmt_exprs(s):
            collect(e)
        # bare truthy reads used directly as conditions
        if isinstance(s, jp.IfStmt):
            for side in (s.cond,):
                k = _read_key(resolve(side))
                if k and k not in ("clock.hour", "clock.weekday",
                                   "clock.minute", "clock.timestamp",
                                   "clock.isholiday"):
                    bool_keys.add(k)

    cells: dict[str, list] = {}
    for k, oc in num_consts.items():
        # candidates around every boundary, then merge candidates the code
        # cannot distinguish (identical truth vector over the (op, const)
        # pairs actually used on this key) — one representative per region
        pairs = sorted(oc)
        cand = sorted({v for _, c in pairs for v in (c - 1, c, c + 1)})
        seen_vec: dict[tuple, float] = {}
        for x in cand:
            vec = tuple(_apply(o, x, c) for o, c in pairs)
            seen_vec.setdefault(vec, x)
        cells[k] = sorted(seen_vec.values())
    for k, ss in str_consts.items():
        cells[k] = sorted(ss) + ["__other__"]
    for k in bool_keys:
        cells.setdefault(k, [True, False])
    for g in gv_bool:
        cells[f"@gv:{g}"] = [True, False]
    for g, ss in gv_str.items():
        cells[f"@gv:{g}"] = sorted(ss) + ["__other__"]
    if holiday_used:
        cells["clock.isholiday"] = [False, True]

    return Axes(cells, sorted(hours), weekdays_used, holiday_used,
                sorted(ts_thresholds), counter_caps, param_reads,
                sorted(gv_written & gv_read),
                minutes=sorted(minutes), hour_ops=sorted(hour_ops),
                cell_preds={k: sorted(v) for k, v in num_consts.items()})


def cell_of(axes: Axes, key: str, value):
    """Representative of the cell an observed reading falls in, or None if
    the key has no axis. Numeric keys compare by truth vector over the
    (op, const) pairs the code uses; string keys fall back to the
    `__other__` catch-all the explorer already carries."""
    reps = axes.cells.get(key)
    if reps is None:
        return None
    if value in reps:
        return value
    pairs = axes.cell_preds.get(key)
    if pairs:
        try:
            vec = tuple(_apply(o, value, c) for o, c in pairs)
        except TypeError:
            return None
        for rep in reps:
            if tuple(_apply(o, rep, c) for o, c in pairs) == vec:
                return rep
        return None
    return "__other__" if "__other__" in reps else None


# ── Finiteness pre-flight ────────────────────────────────────────────────────

def finiteness_check(vars_: dict[str, VarInfo], axes: Axes,
                     stmts: list) -> list[str]:
    """Names of carried variables with no finite shape (empty = safe)."""
    from .predicates import var_defs
    defs = var_defs(stmts)
    bad: list[str] = []
    for nm, vi in vars_.items():
        if vi.role != "state":
            continue
        if vi.timestamp:
            continue                       # zone-normalized
        if isinstance(vi.init, bool):
            continue                       # latch
        if nm in axes.counter_caps:
            # saturation is exact only for reset/increment updates
            from .predicates import _reg_is_counter
            if _reg_is_counter(nm, defs, vars_):
                continue
            bad.append(f"{nm} (compared but non-counter update)")
            continue
        # string-valued state compared by enum? treat via defs: all literal
        # assignments → finite enum
        dlist = defs.get(nm, [])
        if dlist and all(isinstance(d, expr_mod.Lit) or
                         _fold_with_params(d, vars_) is not None or
                         (isinstance(d, expr_mod.BinaryOp)
                          and d.op in ("and", "or") + CMP_OPS)
                         for d in dlist):
            continue                       # finite literal/bool range
        bad.append(nm)
    return bad


# ── Canonicalization (the state key) ─────────────────────────────────────────

def _hour_region(hour: int, hours: list[int]) -> int:
    return bisect_right(hours, hour)


def normalize(vars_: dict, gv: dict, now_ms: int,
              vinfo: dict[str, VarInfo], axes: Axes) -> tuple:
    now_sec = now_ms // 1000
    regs: list = []
    ts_vals: list[tuple[str, float]] = []
    tmax = max(axes.ts_thresholds) if axes.ts_thresholds else 0.0
    for nm in sorted(vinfo):
        vi = vinfo[nm]
        if vi.role != "state" or nm not in vars_:
            continue
        v = vars_[nm]
        if vi.timestamp:
            if not v:                      # 0/None sentinel
                regs.append((nm, "SENT"))
            else:
                delta = now_sec - v
                if delta > tmax:
                    regs.append((nm, "FAR"))
                else:
                    # (bisect_left, bisect_right) pair: a delta exactly ON a
                    # threshold is its own region — `>` is still false there
                    # while `>=` would be true, and the next tick differs
                    from bisect import bisect_left
                    regs.append((nm, ("Z",
                                      bisect_left(axes.ts_thresholds, delta),
                                      bisect_right(axes.ts_thresholds, delta))))
                    ts_vals.append((nm, v))
        elif nm in axes.counter_caps and isinstance(v, (int, float)):
            cap = axes.counter_caps[nm]
            regs.append((nm, v if v <= cap else cap + 1))
        else:
            regs.append((nm, v))
    # pairwise capture order of live timers (who crosses first)
    order = tuple(sorted(nm for nm, _ in ts_vals))
    order_sig = tuple(
        (a, b, (ts_vals_d := dict(ts_vals))[a] <= ts_vals_d[b])
        for i, a in enumerate(order) for b in order[i + 1:])
    cal = _cal_cell(now_ms, axes)
    return (tuple(regs), tuple(sorted(gv.items())), cal, order_sig)


# ── Next-event computation for jumps ─────────────────────────────────────────

def next_event_ms(vars_: dict, now_ms: int, vinfo: dict[str, VarInfo],
                  axes: Axes) -> int | None:
    cands: list[int] = []
    now_sec = now_ms // 1000
    for nm, vi in vinfo.items():
        if vi.role == "state" and vi.timestamp and vars_.get(nm):
            v = vars_[nm]
            for t in axes.ts_thresholds:
                cross = (v + t) * 1000
                if cross > now_ms:
                    cands.append(int(cross))
    # hour-region entries AND exits (h:00 and h+1:00), next occurrence
    bounds = {h for h in axes.hours} | {h + 1 for h in axes.hours}
    for h in bounds:
        day = now_ms // DAY_MS
        for d in (day, day + 1):
            t = d * DAY_MS + (h % 24) * 3_600_000 + (DAY_MS if h >= 24 else 0)
            if t > now_ms:
                cands.append(t)
                break
    for m in axes.minutes:                  # next :m of any hour
        hour_start = (now_ms // 3_600_000) * 3_600_000
        for hs in (hour_start, hour_start + 3_600_000):
            t = hs + m * 60_000
            if t > now_ms:
                cands.append(t)
                break
    if axes.weekdays_used or axes.hours:
        cands.append((now_ms // DAY_MS + 1) * DAY_MS)   # midnight
    return min(cands) if cands else None


def _cal_cell(now_ms: int, axes: Axes) -> tuple:
    """Calendar part of the state key: the hour SEGMENT between adjacent
    compared boundaries (not the predicates' truth vector — hours 0 and 11
    share the truth vector of `==9`/`==10` but sit at different phases of
    the daily cycle, and merging them severs the ladder that walks the
    week), plus the weekday when the code reads it."""
    cs = clock_state(now_ms)
    bounds = sorted({h for h in axes.hours} | {h + 1 for h in axes.hours})
    return (bisect_right(bounds, cs["clock.hour"]),
            cs["clock.weekday"] if axes.weekdays_used else "-")


def _ts_regions(vars_: dict, now_ms: int, vinfo: dict, axes: Axes) -> tuple:
    from bisect import bisect_left
    now_sec = now_ms // 1000
    tmax = max(axes.ts_thresholds) if axes.ts_thresholds else 0.0
    out = []
    for nm in sorted(vinfo):
        vi = vinfo[nm]
        if vi.role == "state" and vi.timestamp and vars_.get(nm):
            delta = now_sec - vars_[nm]
            out.append("FAR" if delta > tmax else
                       (bisect_left(axes.ts_thresholds, delta),
                        bisect_right(axes.ts_thresholds, delta)))
    return tuple(out)


def next_key_change_ms(vars_: dict, now_ms: int, vinfo: dict,
                       axes: Axes) -> int | None:
    """Nearest future time at which the state KEY's time-derived part
    (calendar cell or a timer region) actually differs. The nearest raw
    event alone can be a no-op tick (Monday 01:00 for a Thursday guard):
    its successor is dropped as already-visited and time never advances —
    the weekly ladder needs a jump that lands somewhere genuinely new."""
    cands: set[int] = set()
    now_sec = now_ms // 1000
    for nm, vi in vinfo.items():
        if vi.role == "state" and vi.timestamp and vars_.get(nm):
            for t in axes.ts_thresholds:
                cross = int((vars_[nm] + t) * 1000)
                if cross > now_ms:
                    cands.add(cross)
    day = now_ms // DAY_MS
    for d in range(0, 9):                       # a full week of ladders
        for h in ({h for h in axes.hours} | {h + 1 for h in axes.hours}):
            cands.add((day + d) * DAY_MS + (h % 24) * 3_600_000
                      + (DAY_MS if h >= 24 else 0))
        cands.add((day + d + 1) * DAY_MS)       # midnights
    base = (_cal_cell(now_ms, axes), _ts_regions(vars_, now_ms, vinfo, axes))
    for t in sorted(cands):
        if t <= now_ms:
            continue
        if (_cal_cell(t, axes), _ts_regions(vars_, t, vinfo, axes)) != base:
            return t
    return None


# ── The explorer ─────────────────────────────────────────────────────────────

@dataclass
class Graph:
    n_states: int = 0
    n_edges: int = 0
    n_steps: int = 0
    closed: bool = False
    actions_seen: dict = field(default_factory=dict)   # repr → count
    fired: set = field(default_factory=set)            # (svc, method, target)
    notes: list = field(default_factory=list)
    # populated when keep_graph=True:
    edges: list = field(default_factory=list)   # (src, dst|-1, dwell, actions)
    state_keys: list = field(default_factory=list)      # id → normalized key
    edge_inputs: list = field(default_factory=list)     # aligned with edges
    edge_guards: list = field(default_factory=list)     # aligned with edges


def _regs_frozen(before: dict, after: dict, vinfo: dict) -> bool:
    """Do all carried timestamp registers hold their EXACT value across one
    tick? The normalized key stores `now - reg` regions, so a register the
    program rewrites to `now` every tick looks stationary while its absolute
    value drifts. Dwell jumps replay a single step at now+d against the
    pre-jump register values, which is only faithful when those values would
    genuinely still be there."""
    for nm, vi in vinfo.items():
        if vi.role == "state" and vi.timestamp \
                and before.get(nm) != after.get(nm):
            return False
    return True


def fired_key(a) -> tuple:
    """Identity of an action for obligation checks: GV writes are keyed by
    the variable name, device calls by their instance target."""
    if a.service == "globalvariable":
        return (a.service, a.method, (str(a.args[0]),) if a.args else ())
    return (a.service, a.method, tuple(a.target))


T0_DEFAULT = 28 * DAY_MS   # Monday 00:00, far past every cooldown threshold,
                           # so `reg := 0` initializers read as "long ago"
                           # instead of "just fired" (t0=0 would silently
                           # freeze every cooldown for its first window)


def explore(src: str | list, period_ms: int, t0_ms: int | None = None,
            axes_override: Axes | None = None,
            mirror_mode: str = "enumerate", keep_graph: bool = False) -> Graph:
    """mirror_mode: 'enumerate' tries {unseeded, False, True} per mirror GV;
    'unseeded' starts only from an empty GV store (seed-dependence probe).
    keep_graph: retain edges and state keys for the obligation layer."""
    stmts = src if isinstance(src, list) else parse(src)
    if any(isinstance(s, jp.ForEach) for s in walk_stmts(stmts)):
        raise Unsupported("ForEach needs grounding (unroll over inventory)")
    t0_ms = T0_DEFAULT if t0_ms is None else t0_ms
    vinfo = classify_vars(stmts)
    axes = axes_override or derive_axes(stmts, vinfo)
    g = Graph()

    if axes.param_reads:
        raise Unsupported(f"parameterized reads need grounding: {axes.param_reads}")
    bad = finiteness_check(vinfo, axes, stmts)
    if bad:
        raise Unsupported(f"unbounded carried vars: {bad}")

    keys = sorted(axes.cells)
    combos = [dict(zip(keys, vals))
              for vals in itertools.product(*(axes.cells[k] for k in keys))]
    if not combos:
        combos = [{}]
    from .feasibility import dedup_combos
    combos, dd = dedup_combos([(stmts, vinfo)], combos)
    if dd.after < dd.before:
        g.notes.append(f"combo dedup {dd.before}→{dd.after}")
    # external GV inputs are injected into the gv store, not the world
    ext_gv = {k[4:] for k in axes.cells if k.startswith("@gv:")}

    def split(i: dict) -> tuple[dict, dict]:
        world = {k: v for k, v in i.items() if not k.startswith("@gv:")}
        gvs = {k[4:]: v for k, v in i.items() if k.startswith("@gv:")}
        return world, gvs

    def own_gv(gv: dict) -> dict:
        return {k: v for k, v in gv.items() if k not in ext_gv}

    visited: dict[tuple, int] = {}
    queue: list[tuple[dict, dict, int, dict]] = []   # vars, gv, now, held input

    def push(vars_: dict, gv: dict, now: int, held: dict) -> int:
        k = normalize(vars_, gv, now, vinfo, axes)
        if k not in visited:
            visited[k] = len(visited)
            if keep_graph:
                g.state_keys.append(k)
            queue.append((vars_, gv, now, held))
        return visited[k]

    def run(vars_: dict, gv: dict, i: dict, now: int, first: bool = False):
        world, gvs = split(i)
        r = step(stmts, vars_, {**gv, **gvs}, world, now, first_tick=first)
        g.n_steps += 1
        return r

    # initial frontier: input combos × initial values of mirror GVs
    # (None = unseeded store — keeps the seed-fault class observable)
    if mirror_mode == "unseeded":
        mirror_inits = [{n: None for n in axes.mirror_gv}]
    else:
        mirror_inits = [dict(zip(axes.mirror_gv, vals)) for vals in
                        itertools.product([None, False, True],
                                          repeat=len(axes.mirror_gv))]
    for i in combos:
        for m in mirror_inits:
            gv0 = {k: v for k, v in m.items() if v is not None}
            r = run({}, gv0, i, t0_ms, first=True)
            for a in r.actions:
                g.actions_seen[repr(a)] = g.actions_seen.get(repr(a), 0) + 1
                g.fired.add(fired_key(a))
            if not r.terminated:
                push(r.vars, own_gv(r.gv), t0_ms, i)

    while queue:
        if len(visited) > STATE_CAP or g.n_steps > STEP_CAP:
            g.notes.append("CAP HIT — aborted")
            break
        vars_, gv, now, held = queue.pop(0)
        key_here = normalize(vars_, gv, now, vinfo, axes)

        # stutter WITNESS: long dwells are legal if SOME input exists that
        # the environment can hold through the gap without the state
        # changing or actions repeating. Gating on the arrival input alone
        # is wrong — a repeat-emitting held input would block the jump and
        # memoized 1-tick walking can never cross a minutes-long region.
        stutter = False
        for cand in [held] + combos:
            probe = run(vars_, gv, cand, now + period_ms)
            if (not probe.actions and not probe.terminated and
                    normalize(probe.vars, own_gv(probe.gv), now + period_ms,
                              vinfo, axes) == key_here):
                if not _regs_frozen(vars_, probe.vars, vinfo):
                    # a timestamp register that TRACKS now is abstractly
                    # stationary (delta stays 0) while drifting concretely.
                    # Jumping replays the gap tick against a stale register
                    # and invents firings tick-by-tick execution never
                    # produces. Suppress the jump and name it.
                    note = "jump suppressed: now-tracking register"
                    if note not in g.notes:
                        g.notes.append(note)
                    continue
                stutter = True
                break
        dwells = [period_ms]
        if stutter:
            # nearest raw event (edge coverage at marks like :30) AND the
            # nearest key-changing time (temporal progress, e.g. the weekly
            # ladder to Thursday) — both get just-before/just-after ticks
            for ev in (next_event_ms(vars_, now, vinfo, axes),
                       next_key_change_ms(vars_, now, vinfo, axes)):
                if ev is not None and ev - now > period_ms:
                    pre = ((ev - now) // period_ms) * period_ms
                    for d in (pre, pre + period_ms):
                        if d > period_ms and d not in dwells:
                            dwells.append(d)

        src_id = visited[key_here]
        for i in combos:
            for d in dwells:
                r = run(vars_, gv, i, now + d)
                g.n_edges += 1
                for a in r.actions:
                    g.actions_seen[repr(a)] = g.actions_seen.get(repr(a), 0) + 1
                    g.fired.add(fired_key(a))
                dst = -1
                if not r.terminated:
                    dst = push(r.vars, own_gv(r.gv), now + d, i)
                if keep_graph:
                    g.edges.append((src_id, dst, d, tuple(r.actions)))
                    g.edge_inputs.append(dict(i))
                    g.edge_guards.append(r.guards)

    g.n_states = len(visited)
    g.closed = not queue
    return g


# ── Driver ───────────────────────────────────────────────────────────────────

def main() -> None:
    import json
    from .demo_tick import SRC as DOOR_SRC, SAT_14H

    print(f"{'시나리오':26s} {'상태':>6s} {'에지':>8s} {'step수':>8s} "
          f"{'닫힘':>4s} {'시간':>7s}  액션 종류")
    targets = [("문-불 데모 (period 1s)", DOOR_SRC, 1000,
                28 * DAY_MS + SAT_14H)]   # +28d keeps Saturday
    data = json.load(open("paper_v2/joi_automation_codes.json"))
    for s in data:
        if s.get("cron") not in ("", "x", None):
            targets.append((s["name"] + " [cron→스킵]", None, 0, 0))
            continue
        targets.append((s["name"], s["code"], int(s["period"]), None))

    for name, src, period, t0 in targets:
        if src is None:
            print(f"{name[:34]:26s} {'—':>6s}  (cron 스케줄은 드라이버 TODO)")
            continue
        try:
            t_start = _time.time()
            g = explore(src, period, t0)
            dt = _time.time() - t_start
            acts = ", ".join(sorted({a.split("(")[0]
                                     for a in g.actions_seen})) or "-"
            note = " ".join(g.notes)
            print(f"{name[:26]:26s} {g.n_states:>6d} {g.n_edges:>8d} "
                  f"{g.n_steps:>8d} {'예' if g.closed else 'NO':>4s} "
                  f"{dt:>6.2f}s  {acts[:60]} {note}")
        except Unsupported as e:
            print(f"{name[:26]:26s} {'—':>6s}  Unsupported: {e}")


if __name__ == "__main__":
    main()
