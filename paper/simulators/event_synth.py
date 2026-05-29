"""IR-guided event synthesizer.

Walks an IR and generates a Scenario containing events that satisfy each
`wait` and exercise each `if` branch. Both IR and JoI simulators run on the
same generated scenario for a fair trace comparison.

Phase-1 patterns supported (per locked design):
- `X.Y == V`        → event at +1s: X.Y = V
- `X.Y >= V` / <=, > , <  → event with V (or boundary +1) at +1s
- edge "rising"     → emit prelude (X.Y = !V) then event (X.Y = V)
- edge "falling"    → emit prelude (X.Y = V) then event (X.Y = !V)
- compound `&&`/`||`: walk both sides, emit events for each leaf. (For OR,
  satisfying one leaf is enough; we satisfy both for simplicity.)

Output: a Scenario with `events` populated. Initial-world is left empty —
the IR simulator's `wait` polling will advance the clock to event times.

NOT supported in phase 1 (will hard-error): `any(#X).Y`, `all(#X).Y`,
clock-only conditions (those don't need synth — they fire from time alone),
arithmetic in cond targets (`Volume + 10 >= 100`).
"""

from __future__ import annotations

from typing import Any

from . import expr
from .scenario import Scenario
from .catalog import value_domains
from ..timeline_ir import parse_duration_to_ms

# ── Expression-boundary seeding (codex Round 6 — arithmetic fault class) ─────────
# Arithmetic / min / max / abs operators have INTERNAL boundaries (clamp caps,
# sign-flips, crossovers) that are only exercised if their INPUTS are driven to
# straddling values. We seed those inputs at boundaries derived from each sensor's
# declared value domain (type + range), so e.g. a brightness clamp is actually hit.
_ARITH_OPS = {"+", "-", "*", "/"}
_ARITH_FUNCS = {"min", "max", "abs"}


def _varref_device_key(name: str) -> str | None:
    """Device-state key for a dotted Capitalized VarRef (`Light.CurrentBrightness`),
    matching expr's eval fallback / DeviceRef canonicalization; None for plain regs."""
    if "." in name:
        first, _, rest = name.partition(".")
        if first[:1].isupper():
            svc, a = expr.canonical_key(first, rest)
            return f"{svc}.{a}"
    return None


def _collect_arith_inputs(node, live_keys: set, reg_names: set, inside: bool = False) -> None:
    """Collect inputs feeding an arithmetic / min/max/abs context: device-state keys
    (DeviceRef or dotted `$Service.Attr` VarRef) into `live_keys`, plain register
    names into `reg_names` (resolved later via the read schedule)."""
    if isinstance(node, expr.DeviceRef):
        if inside:
            live_keys.add(node.key)
    elif isinstance(node, expr.VarRef):
        if inside:
            k = _varref_device_key(node.name)
            (live_keys.add(k) if k else reg_names.add(node.name))
    elif isinstance(node, expr.FuncCall):
        ins = inside or node.name in _ARITH_FUNCS
        for a in node.args:
            _collect_arith_inputs(a, live_keys, reg_names, ins)
    elif isinstance(node, expr.BinaryOp):
        ins = inside or node.op in _ARITH_OPS
        _collect_arith_inputs(node.left, live_keys, reg_names, ins)
        _collect_arith_inputs(node.right, live_keys, reg_names, ins)
    elif isinstance(node, expr.UnaryOp):
        _collect_arith_inputs(node.operand, live_keys, reg_names, inside)


def _iter_expr_strings(steps: list):
    """Yield every cond and call-arg expression string in the timeline (recursive)."""
    for s in steps or []:
        op = s.get("op")
        if op in ("if", "wait") and s.get("cond"):
            yield s["cond"]
        if op == "call":
            for v in (s.get("args") or {}).values():
                if isinstance(v, str):
                    yield v
        if op == "if":
            yield from _iter_expr_strings(s.get("then", []) or [])
            yield from _iter_expr_strings(s.get("else", []) or [])
        elif op == "cycle":
            yield from _iter_expr_strings(s.get("body", []) or [])


def _read_schedule(steps: list, cursor=None) -> list:
    """[(var, src_device_key, time_ms)] for each `read` op (delays advance the clock)."""
    if cursor is None:
        cursor = [0]
    out = []
    for s in steps or []:
        op = s.get("op")
        if op == "read":
            src = s.get("src", "") or ""
            k = None
            if "." in src:
                first, _, rest = src.partition(".")
                svc, a = expr.canonical_key(first, rest)
                k = f"{svc}.{a}"
            out.append((s.get("var"), k, cursor[0]))
        elif op == "delay":
            cursor[0] += parse_duration_to_ms(s.get("duration", "0 MSEC"))
        elif op == "if":
            out += _read_schedule(s.get("then", []) or [], cursor)
            out += _read_schedule(s.get("else", []) or [], cursor)
        elif op == "cycle":
            out += _read_schedule(s.get("body", []) or [], cursor)
    return out


def _written_keys(steps: list, out: set | None = None) -> set:
    """Device-state keys WRITTEN by the rule (call effects + `var` write-back captures).
    Mirrors World.apply_effect's key derivation. A read of such a key is a
    self-referential read-modify-write (accumulator), where the IR `var`-capture and
    JoI device-read semantics legitimately differ — so it must NOT be boundary-seeded
    (seeding would manufacture a false divergence, not exercise a clamp boundary)."""
    if out is None:
        out = set()
    for s in steps or []:
        op = s.get("op")
        if op == "call":
            from .catalog import split_target
            svc_raw, method = split_target(s.get("target", "") or "")
            svc = (svc_raw or "").lower()
            m = expr.canonical_name(svc_raw, method)
            if m in ("on", "off", "toggle"):
                out.add(f"{svc}.switch")
            elif m.startswith("set"):
                out.add(f"{svc}.{m[3:]}")
            elif m.startswith("moveto") and m != "movecolor":
                out.add(f"{svc}.{m[6:]}")
            var = s.get("var")
            if isinstance(var, str):
                k = _varref_device_key(var)
                if k:
                    out.add(k)
        elif op == "if":
            _written_keys(s.get("then", []) or [], out)
            _written_keys(s.get("else", []) or [], out)
        elif op == "cycle":
            _written_keys(s.get("body", []) or [], out)
    return out


def _domain_pair(dom: dict):
    """(lo, hi) representative values straddling typical clamp boundaries within the
    sensor's declared numeric range; None for non-numeric domains (arithmetic N/A)."""
    t = (dom or {}).get("type", "").upper()
    if t in ("", "ENUM", "BOOLEAN", "BOOL", "STRING"):
        return None
    b = (dom or {}).get("bound")
    if b and len(b) == 2 and all(isinstance(x, (int, float)) for x in b):
        lo, hi = b
        span = hi - lo
        v_lo, v_hi = lo + 0.05 * span, lo + 0.95 * span
    else:
        v_lo, v_hi = 10.0, 90.0
    if t == "INTEGER":
        v_lo, v_hi = int(round(v_lo)), int(round(v_hi))
    return (v_lo, v_hi)


def _norm_domains() -> dict:
    """value_domains() re-keyed to canonical lowercase (svc.attr) for device-key lookup."""
    out = {}
    for (sid, vid), dom in value_domains().items():
        svc, a = expr.canonical_key(sid, vid)
        out[f"{svc}.{a}"] = dom
    return out


def _synth_expr_boundary(timeline: list, live_keys: set, reg_names: set, written: set | None = None) -> list:
    """Two scenarios seeding arithmetic inputs at their sensor value-domain boundaries:
    `expr:lo` (low side) and `expr:hi` (high side). Live device reads are seeded in
    initial_world; plain registers are driven via stepped events at their read times so
    successive reads differ (hi) or stay equal (lo) — exercising difference/abs guards."""
    doms = _norm_domains()
    written = written or set()
    sched = _read_schedule(timeline)
    reg_reads = [(v, k, t) for (v, k, t) in sched if v in reg_names and k and k not in written]
    scns = []
    for idx, variant in enumerate(("lo", "hi")):
        scn = _synth_plan(timeline, target_id=None, reach={}, label=f"expr:{variant}")
        covers = list(scn.covers)
        for key in sorted(live_keys):
            pair = _domain_pair(doms.get(key))
            if pair is None:
                continue
            scn.initial_world[key] = pair[idx]
            covers.append(f"expr@{key}:{variant}")
        # registers: stepped (hi) so consecutive reads of the same src differ; equal (lo)
        for i, (var, src, t) in enumerate(reg_reads):
            pair = _domain_pair(doms.get(src)) or (10.0, 90.0)
            base = pair[0]
            step = (pair[1] - pair[0]) * 0.4
            val = base + (i * step if variant == "hi" else 0)
            scn.add(t, src, val)
            covers.append(f"expr@{src}:reg_{variant}")
        scn.covers = sorted(set(covers))
        scns.append(scn)
    return scns


def synthesize_scenarios(ir: dict) -> list[Scenario]:
    """Return a COVERAGE SUITE of scenarios for `ir`.

    Scenario 0 is the happy path (satisfy every wait, take every `then`) — its
    index is preserved for legacy single-scenario callers. We additionally
    return one ELSE-BRANCH scenario per `if`: it falsifies exactly that if's
    condition (taking its `else`) while keeping all ancestors satisfied so the
    target stays reachable. This exercises the false side of every guard and
    every else transition — catching guard-polarity / unconditional-fire bugs
    the happy path structurally cannot reach.

    Additionally, one FLAP-RESET scenario per sustained `wait.for`: the cond is
    satisfied, flipped false before the sustain window elapses, then satisfied
    again — a correct lowering resets its timer and only completes after a fresh
    full window; a `delay`-style lowering fires early and diverges.

    Each scenario records, in `.covers`, the coverage obligations it actually
    exercises (branch sides, sustain/flap edges, guard-boundary sides), so a
    coverage report can diff against the target obligation set (see coverage.py).
    """
    timeline = ir.get("timeline", [])
    scenarios: list[Scenario] = [
        _synth_plan(timeline, target_id=None, reach={}, label="happy")
    ]
    for if_step, reach, path in _collect_ifs(timeline, reach={}, path="timeline"):
        scenarios.append(_synth_plan(
            timeline, target_id=id(if_step), reach=reach, label=f"if@{path}:else"))
    for wait_step, reach, path in _collect_sustained_waits(timeline, reach={}, path="timeline"):
        scenarios.append(_synth_plan(
            timeline, target_id=None, reach=reach,
            label=f"wait@{path}:flap_reset", flap_wait_id=id(wait_step)))
    # RE-ARM: an edge-triggered `wait` inside a `cycle` re-arms each iteration.
    # A single edge fires the body once for correct AND broken triggered-flag
    # lowerings alike. We drive a SECOND rising/falling edge after the first body
    # completes, so a correct lowering fires once per edge (matching IR) while a
    # broken re-arm fires the wrong number of times (-> missing_call/extra_call).
    for wait_step, reach, path in _collect_rearm_waits(timeline, reach={}, path="timeline"):
        scn = _synth_plan(timeline, target_id=None, reach=reach,
                          label=f"wait@{path}:rearm", rearm_wait=wait_step)
        scn.covers = sorted(set(list(scn.covers) + [f"wait@{path}:rearm"]))
        scenarios.append(scn)
    # EXPRESSION-BOUNDARY: seed arithmetic / min/max/abs inputs at their sensor
    # value-domain boundaries so clamps / sign-flips / crossovers are exercised.
    live_keys: set = set()
    reg_names: set = set()
    for es in _iter_expr_strings(timeline):
        try:
            _collect_arith_inputs(expr.parse(es), live_keys, reg_names)
        except Exception:
            continue
    # Exclude self-referential read-modify-write targets (accumulators): a key the
    # rule both reads and writes is out of scope for boundary seeding (§above).
    written = _written_keys(timeline)
    live_keys -= written
    if live_keys or reg_names:
        scenarios += _synth_expr_boundary(timeline, live_keys, reg_names, written)
    return scenarios


def _collect_ifs(steps: list, reach: dict, path: str) -> list:
    """Every `if` in `steps` (recursing into then/else/cycle), each paired with
    the ancestor branch decisions needed to reach it and a debug path."""
    out: list = []
    for i, s in enumerate(steps):
        op = s.get("op")
        sp = f"{path}[{i}]"
        if op == "if":
            out.append((s, dict(reach), sp))
            then_reach = dict(reach); then_reach[id(s)] = "then"
            out += _collect_ifs(s.get("then", []) or [], then_reach, f"{sp}.then")
            else_reach = dict(reach); else_reach[id(s)] = "else"
            out += _collect_ifs(s.get("else", []) or [], else_reach, f"{sp}.else")
        elif op == "cycle":
            out += _collect_ifs(s.get("body", []) or [], reach, f"{sp}.body")
    return out


def _collect_sustained_waits(steps: list, reach: dict, path: str) -> list:
    """Every `wait` carrying a `for` (sustain) duration, with the reach decisions
    (all-then to ancestors) needed to make it reachable, and a debug path."""
    out: list = []
    for i, s in enumerate(steps):
        op = s.get("op")
        sp = f"{path}[{i}]"
        if op == "wait" and s.get("for"):
            out.append((s, dict(reach), sp))
        elif op == "if":
            then_reach = dict(reach); then_reach[id(s)] = "then"
            out += _collect_sustained_waits(s.get("then", []) or [], then_reach, f"{sp}.then")
            else_reach = dict(reach); else_reach[id(s)] = "else"
            out += _collect_sustained_waits(s.get("else", []) or [], else_reach, f"{sp}.else")
        elif op == "cycle":
            out += _collect_sustained_waits(s.get("body", []) or [], reach, f"{sp}.body")
    return out


def _collect_rearm_waits(steps: list, reach: dict, path: str, in_cycle: bool = False) -> list:
    """Every edge-triggered `wait` INSIDE a `cycle` (the re-arm pattern: the cycle
    re-waits for a fresh edge each iteration), with reach decisions and a path."""
    out: list = []
    for i, s in enumerate(steps):
        op = s.get("op")
        sp = f"{path}[{i}]"
        if op == "wait" and in_cycle and s.get("edge", "none") in ("rising", "falling"):
            out.append((s, dict(reach), sp))
        elif op == "if":
            then_reach = dict(reach); then_reach[id(s)] = "then"
            out += _collect_rearm_waits(s.get("then", []) or [], then_reach, f"{sp}.then", in_cycle)
            else_reach = dict(reach); else_reach[id(s)] = "else"
            out += _collect_rearm_waits(s.get("else", []) or [], else_reach, f"{sp}.else", in_cycle)
        elif op == "cycle":
            out += _collect_rearm_waits(s.get("body", []) or [], reach, f"{sp}.body", in_cycle=True)
    return out


def _step_contains(container: dict, target: dict) -> bool:
    """True if `target` (by identity) is anywhere inside `container`'s body."""
    def walk(steps):
        for s in steps or []:
            if s is target:
                return True
            op = s.get("op")
            if op == "if":
                if walk(s.get("then", [])) or walk(s.get("else", [])):
                    return True
            elif op == "cycle":
                if walk(s.get("body", [])):
                    return True
        return False
    return walk(container.get("body", []))


def _synth_plan(timeline: list, target_id, reach: dict,
                label: str, flap_wait_id=None, rearm_wait=None) -> Scenario:
    """Synthesize one scenario. For each `if`: take `else` if it is the negate
    target, the recorded branch if it is an ancestor on the reach path, else
    `then` (default happy). For the `wait` whose id == flap_wait_id, synthesize a
    flap/reset sequence; for `rearm_wait`, drive a SECOND edge after its cycle body
    so the cycle re-arms and fires twice."""
    scn = Scenario()
    scn.label = label
    cov: list[str] = []
    cursor = [0]

    def branch_of(step: dict) -> str:
        sid = id(step)
        if sid == target_id:
            return "else"
        if sid in reach:
            return reach[sid]
        return "then"

    # Map each read variable to its source device key so a guard written over a
    # read var (`temp >= 25`) seeds the underlying sensor. Skip self-referential
    # accumulators (read-modify-write) where IR/JoI read semantics differ.
    written = _written_keys(timeline)
    var_src = {v: k for (v, k, _t) in _read_schedule(timeline)
               if v and k and k not in written}
    _walk(timeline, scn, cursor, period_stack=[], branch_of=branch_of,
          cov=cov, path="timeline", flap_wait_id=flap_wait_id, rearm_wait=rearm_wait,
          var_src=var_src)
    scn.covers = sorted(set(cov))
    return scn


def _repeat_edge(wait_step: dict, scn: Scenario, cursor: list[int], period_ms: int) -> None:
    """Append a SECOND rising/falling edge for `wait_step`'s cond at `cursor` so a
    re-arming cycle fires again. The pre-edge (opposite) phase is held WELL BEYOND
    the L2 timing tolerance (>= ~1 s) before the edge: this exposes not just re-arm
    flag bugs (which need >=2 edges) but also trigger-polarity flips — a lowering
    that fires on the wrong side of the guard fires during the long pre-edge phase,
    diverging from the IR's edge time by more than the tolerance. A correct lowering
    still fires only at the edge, so this does not introduce false positives."""
    ast = expr.parse(wait_step["cond"])
    assignments: list[tuple[str, Any]] = []
    _gather_assignments(ast, assignments)
    if not assignments:
        return
    edge = wait_step.get("edge", "rising")
    p = period_ms or 100
    pre_ms = cursor[0] + p                 # set & hold the pre-edge state
    fire_ms = pre_ms + max(1000, 2 * p)    # the edge, beyond the 500ms/10% tolerance
    if period_ms:                          # align the edge to a tick boundary
        fire_ms = ((fire_ms // period_ms) + 1) * period_ms
    if edge == "falling":
        for k, v in assignments:
            scn.add(pre_ms, k, v)              # armed = true
            scn.add(fire_ms, k, _opposite(v))  # fire = false
    else:  # rising (the re-arm default)
        for k, v in assignments:
            scn.add(pre_ms, k, _opposite(v))   # armed = false (held long)
            scn.add(fire_ms, k, v)             # fire = true
    cursor[0] = fire_ms


def _walk(steps: list, scn: Scenario, cursor: list[int],
          period_stack: list[int], branch_of, cov: list, path: str,
          flap_wait_id=None, rearm_wait=None, var_src=None) -> None:
    for i, step in enumerate(steps):
        sp = f"{path}[{i}]"
        op = step.get("op")
        if op == "wait":
            period_ctx = period_stack[-1] if period_stack else 0
            flap = (flap_wait_id is not None and id(step) == flap_wait_id)
            _synth_wait(step, scn, cursor, period_ms=period_ctx, flap=flap)
            if step.get("for"):
                cov.append(f"wait@{sp}:flap_reset" if flap else f"wait@{sp}:sustain")
            if step.get("edge", "none") != "none":
                cov.append(f"wait@{sp}:edge_{step['edge']}")
        elif op == "if":
            take = branch_of(step)
            _synth_if_cond(step, scn, cursor, satisfy=(take == "then"), var_src=var_src)
            cov.append(f"if@{sp}:{take}")
            body = step.get("then") if take == "then" else step.get("else")
            _walk(body or [], scn, cursor, period_stack, branch_of, cov,
                  f"{sp}.{take}", flap_wait_id, rearm_wait, var_src)
        elif op == "cycle":
            # Push cycle.period so nested waits can align prelude/fire to it.
            cyc_period_ms = parse_duration_to_ms(step["period"]) \
                if step.get("period") else 0
            period_stack.append(cyc_period_ms)
            try:
                _walk(step.get("body", []) or [], scn, cursor, period_stack,
                      branch_of, cov, f"{sp}.body", flap_wait_id, rearm_wait, var_src)
                # Re-arm: if this cycle holds the target re-arm wait, drive a 2nd
                # edge after the first body iteration so the cycle fires again.
                if rearm_wait is not None and _step_contains(step, rearm_wait):
                    _repeat_edge(rearm_wait, scn, cursor, cyc_period_ms)
            finally:
                period_stack.pop()
        elif op == "delay":
            cursor[0] += parse_duration_to_ms(step.get("duration", "0 MSEC"))
        # call, read, start_at, break: no synthesis needed


def _synth_if_cond(step: dict, scn: Scenario, cursor: list[int],
                   satisfy: bool = True, var_src: dict | None = None) -> None:
    """Seed device state at cursor time so the if cond evaluates TRUE (satisfy)
    or FALSE (negate). World drains events with at_ms <= t_ms before the cond is
    evaluated, so this lands in time. `var_src` maps a read-variable name to its
    source device key (`temp` -> `temperaturesensor.temperature`) so a guard over
    a read variable (`temp >= 25`) is seeded on its sensor source."""
    ast = expr.parse(step["cond"])
    assignments: list[tuple[str, Any]] = []
    if satisfy:
        _gather_assignments(ast, assignments)
    else:
        _gather_falsifying(ast, assignments)
    for key, val in assignments:
        seed_key = (var_src or {}).get(key, key)
        scn.add(cursor[0], seed_key, val)


def _synth_wait(step: dict, scn: Scenario, cursor: list[int],
                period_ms: int = 0, flap: bool = False) -> None:
    from paper.timeline_ir import parse_duration_to_ms
    cond_src = step["cond"]
    edge = step.get("edge", "none")
    for_str = step.get("for")
    for_ms = parse_duration_to_ms(for_str) if for_str else 0
    ast = expr.parse(cond_src)

    # Find satisfying assignment(s). For compound conds, satisfy all leaves.
    assignments: list[tuple[str, Any]] = []
    _gather_assignments(ast, assignments)

    if not assignments:
        return  # purely clock-based or unrecognized — no synthesis needed

    # Period-aware fire/prelude placement: when wait is inside a cycle with a
    # known period, snap fire_ms to the next period-aligned tick boundary and
    # place the prelude one full period earlier so the previous JoI tick
    # observes prev=false. Without this, large periods (e.g. 60s) cause the
    # prelude to land within the same tick window as the fire and the rising
    # edge is missed. Falls back to ±1000/200 magic for top-level waits.
    if edge in ("rising", "falling"):
        if period_ms and period_ms > 200:
            fire_ms = ((cursor[0] // period_ms) + 1) * period_ms
            prelude_offset = period_ms
        else:
            fire_ms = cursor[0] + 1000
            prelude_offset = 200
        prelude_ms = max(cursor[0], fire_ms - prelude_offset)

    if edge == "rising":
        for key, val in assignments:
            scn.add(prelude_ms, key, _opposite(val))
        for key, val in assignments:
            scn.add(fire_ms, key, val)
        cursor[0] = fire_ms
    elif edge == "falling":
        for key, val in assignments:
            scn.add(prelude_ms, key, val)
        for key, val in assignments:
            scn.add(fire_ms, key, _opposite(val))
        cursor[0] = fire_ms
    else:
        # Level-triggered: satisfy at the current cursor time (no extra delay).
        # This keeps IR-poll and JoI-tick timings aligned: both observe cond
        # true on their next clock check past `cursor[0]`.
        for key, val in assignments:
            scn.add(cursor[0], key, val)
        # cursor unchanged — wait satisfies "instantly" in this scenario

    # Sustain (`wait.for`): after the cond-true point, cond must remain true
    # CONTINUOUSLY for for_ms before the wait completes.
    if for_ms > 0:
        if flap:
            # FLAP-RESET coverage: flip cond false mid-window, then true again.
            # A correct lowering RESETS its sustain timer on the flip and only
            # completes a fresh full window measured from the last true point;
            # a `delay(for_ms)`-style lowering ignores the flip and fires early,
            # diverging from IR-SIM. The flip-false must persist at least one
            # poll tick so the reset registers.
            flip_false = cursor[0] + for_ms // 2
            flip_true = flip_false + max(period_ms or 0, 200)
            for key, val in assignments:
                scn.add(flip_false, key, _opposite(val))
                scn.add(flip_true, key, val)
            cursor[0] = flip_true + for_ms
        else:
            # Happy sustain: cond stays pinned; advance cursor past the window.
            cursor[0] += for_ms


def _gather_assignments(node: Any, out: list[tuple[str, Any]]) -> None:
    """Walk an AST and produce (device.attr key, satisfying value) pairs."""
    if isinstance(node, expr.BinaryOp):
        if node.op in ("and", "or"):
            _gather_assignments(node.left, out)
            _gather_assignments(node.right, out)
            return
        if node.op in ("==", "!=", "<", ">", "<=", ">="):
            # Expect DeviceRef on one side, Lit on the other.
            # Unwrap quantifier wrappers like `avg(X) >= V` to extract inner DeviceRef.
            left = _unwrap_quantifier(node.left)
            right = _unwrap_quantifier(node.right)
            dev, lit = _split_dev_lit(left, right)
            if dev is None or lit is None:
                return  # involves clock or var-var — skip
            val = _satisfying_value(node.op, lit.value, dev_swap=dev.on_right)
            out.append((dev.key, val))
            return
    if isinstance(node, expr.FuncCall) and node.name in ("all", "any"):
        # Top-level quantifier wrapping a relational/boolean expression
        # (e.g., `all(TemperatureSensor.Temperature >= 35)`). Recurse into the
        # inner predicate so a single-device satisfying value is seeded.
        for arg in node.args:
            _gather_assignments(arg, out)
        return
    # Other shapes (UnaryOp not, ClockRef alone, etc.) — skip


def _unwrap_quantifier(node: Any) -> Any:
    """If `node` is `avg(...)` / `all(...)` / `any(...)` over a single operand,
    return that operand so callers can pattern-match it as a DeviceRef. Otherwise
    return `node` unchanged. Single-device collapse fallback (framework 2026-05-08).
    """
    if isinstance(node, expr.FuncCall) and node.name in ("avg", "all", "any"):
        if len(node.args) == 1:
            return _unwrap_quantifier(node.args[0])
    return node


def _ref_key(node: Any) -> str | None:
    """Comparable seeding key for a DeviceRef (`svc.attr`) or a VarRef (the var
    name, later redirected to its read source via var_src). None otherwise."""
    if isinstance(node, expr.DeviceRef):
        return node.key
    if isinstance(node, expr.VarRef):
        return node.name
    return None


class _RefKey:
    """Stand-in exposing `.key` (DeviceRef.key / VarRef.name unified) and an
    `.on_right` flag (was the ref on the right of the operator?)."""
    __slots__ = ("key", "on_right")
    def __init__(self, key):
        self.key = key
        self.on_right = False


def _split_dev_lit(a: Any, b: Any) -> tuple[Any, Any]:
    """Return (ref, literal) regardless of operand order; (None, None) otherwise.
    `ref` exposes `.key` (DeviceRef.key OR read VarRef.name) and `.on_right`."""
    ka, kb = _ref_key(a), _ref_key(b)
    if ka is not None and isinstance(b, expr.Lit):
        return _RefKey(ka), b
    if kb is not None and isinstance(a, expr.Lit):
        r = _RefKey(kb); r.on_right = True
        return r, a
    return (None, None)


def _satisfying_value(op: str, lit_val: Any, dev_swap: bool) -> Any:
    """Pick a value that makes (device OP literal) true.

    `dev_swap`: True if the device was on the RIGHT of the operator, in which
    case we flip the comparison direction.
    """
    # Effective op as seen from device's perspective
    effective = op
    if dev_swap:
        # `5 >= X` is equivalent to `X <= 5`
        flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
        effective = flip.get(op, op)

    if effective == "==":
        return lit_val
    if effective == "!=":
        return _opposite(lit_val)
    if effective == ">=":
        return lit_val  # boundary value satisfies
    if effective == "<=":
        return lit_val
    if effective == ">":
        if isinstance(lit_val, (int, float)):
            return lit_val + 1
        return lit_val
    if effective == "<":
        if isinstance(lit_val, (int, float)):
            return lit_val - 1
        return lit_val
    return lit_val


def _gather_falsifying(node: Any, out: list[tuple[str, Any]]) -> None:
    """Like `_gather_assignments`, but produce values that make each leaf FALSE.
    For `and`/`or` we falsify ALL leaves — sufficient to falsify either."""
    if isinstance(node, expr.BinaryOp):
        if node.op in ("and", "or"):
            _gather_falsifying(node.left, out)
            _gather_falsifying(node.right, out)
            return
        if node.op in ("==", "!=", "<", ">", "<=", ">="):
            left = _unwrap_quantifier(node.left)
            right = _unwrap_quantifier(node.right)
            dev, lit = _split_dev_lit(left, right)
            if dev is None or lit is None:
                return
            val = _falsifying_value(node.op, lit.value, dev_swap=dev.on_right)
            out.append((dev.key, val))
            return
    if isinstance(node, expr.FuncCall) and node.name in ("all", "any"):
        for arg in node.args:
            _gather_falsifying(arg, out)
        return


def _falsifying_value(op: str, lit_val: Any, dev_swap: bool) -> Any:
    """Pick a value that makes (device OP literal) FALSE."""
    effective = op
    if dev_swap:
        flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
        effective = flip.get(op, op)

    if effective == "==":
        return _opposite(lit_val)
    if effective == "!=":
        return lit_val
    if effective == ">=":  # false when device < lit (just-below boundary)
        return lit_val - 1 if isinstance(lit_val, (int, float)) else _opposite(lit_val)
    if effective == "<=":  # false when device > lit
        return lit_val + 1 if isinstance(lit_val, (int, float)) else _opposite(lit_val)
    if effective == ">":   # false when device <= lit; boundary value lit works
        return lit_val
    if effective == "<":   # false when device >= lit; boundary value lit works
        return lit_val
    return _opposite(lit_val)


def _opposite(val: Any) -> Any:
    """Return a value that's NOT equal to `val` (for prelude / != cases)."""
    if isinstance(val, bool):
        return not val
    if isinstance(val, (int, float)):
        return val - 1
    if isinstance(val, str):
        return f"_not_{val}"
    return None
