"""Obligation layer: checks that READ the exploration result.

The explorer builds the map; nothing here re-executes the program. Two
code-derived obligations for now, both spec-free (no user-authored
properties — the criteria come from the code itself and from domain
idioms):

1. VACUITY — an action written in the script that fires on NO edge of the
   closed graph, under ANY input sequence, any mirror-GV seeding, unbounded
   time. Dead code is either a defect or an unstated precondition; either
   way it must be named, not silently shipped.

2. SEED-DEPENDENCE — actions reachable when mirror GVs may be pre-seeded
   but NOT reachable from an unseeded store. These are the scenario's
   hidden preconditions ("occupancy must exist before this runs") and go
   into the certificate as environment requirements.

Run:  python -m explorer.obligations   (base_office-grounded corpus report)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import expr as expr_mod
from . import joi_parser as jp
from .expr import canonical_key
from .interp import Unsupported
from .predicates import walk_stmts
from .explore import Graph, explore


def static_actions(stmts: list) -> set[tuple]:
    """Every action the script CAN emit, same identity as Graph.fired:
    (service, method, target) — GV writes keyed by variable name."""
    out: set[tuple] = set()

    def note(call: jp.CallExpr) -> None:
        svc, m = canonical_key(call.service, call.method)
        if svc == "globalvariable":
            if m.startswith("set") and call.args:
                a0 = call.args[0]
                if isinstance(a0, expr_mod.Lit):
                    out.add((svc, m, (str(a0.value),)))
            return
        out.add((svc, m, tuple(call.tags)))

    for s in walk_stmts(stmts):
        if isinstance(s, jp.CallStmt):
            note(s.call)
        elif isinstance(s, jp.Assign) and isinstance(s.rhs, jp.CallExpr) \
                and s.rhs.args is not None:
            svc, _ = canonical_key(s.rhs.service, s.rhs.method)
            if svc == "globalvariable":
                note(s.rhs)
            # non-GV calls in expression position are queries, not actions
    return out


# duration-carrying services: (service, method) → index of the seconds arg.
# Driver-level catalog knowledge; extend as the corpus grows.
DURATION_ARGS = {("camera", "capturevideo"): 0}


@dataclass
class ObligationReport:
    static: set = field(default_factory=set)
    fired: set = field(default_factory=set)
    dead: set = field(default_factory=set)           # vacuity
    seed_dependent: set = field(default_factory=set) # unreachable if unseeded
    overlaps: list = field(default_factory=list)     # (action, gap_s, dur_s)
    counter_carry: list = field(default_factory=list)
    mirror_gv: list = field(default_factory=list)
    graph: Graph | None = None


def overlap_findings(g: Graph, dur_map: dict) -> list:
    """Paths where a duration-carrying action re-fires before its previous
    occupancy interval ends (e.g. capture again while still recording).
    Pure graph arithmetic: Dijkstra over edge dwells from each firing."""
    import heapq

    from .interp import OpaqueToken

    def events(acts) -> list:
        """(event key, duration) occurrences on one edge: direct duration
        actions plus opaque tokens carried inside action arguments (a
        capture is an expression-position QUERY — it never appears as an
        action itself, but the email that ships it does). A capture whose
        result reaches no action is invisible here — named limitation."""
        out = []
        for a in acts:
            am = (a.service, a.method)
            if am in dur_map:
                i = dur_map[am]
                if len(a.args) > i and isinstance(a.args[i], (int, float)):
                    out.append(((a.service, a.method, tuple(a.target)),
                                float(a.args[i])))
            for arg in a.args:
                if isinstance(arg, OpaqueToken) \
                        and (arg.service, arg.method) in dur_map:
                    i = dur_map[(arg.service, arg.method)]
                    if len(arg.args) > i and isinstance(arg.args[i],
                                                        (int, float)):
                        out.append(((arg.service, arg.method, arg.target),
                                    float(arg.args[i])))
        return out

    adj: dict[int, list] = {}
    for src, dst, dw, acts in g.edges:
        adj.setdefault(src, []).append((dst, dw, acts))
    finds: dict[tuple, tuple] = {}
    for src, dst, dw, acts in g.edges:
        for ek, dur in events(acts):
            if not dur:
                continue
            dur_ms = dur * 1000
            if sum(1 for e2, _ in events(acts) if e2 == ek) > 1:
                finds.setdefault(ek, (0.0, dur))          # same-tick double
                continue
            if dst < 0:
                continue
            dist = {dst: 0}
            pq = [(0, dst)]
            hit = None
            while pq and hit is None:
                D, s = heapq.heappop(pq)
                if D > dist.get(s, 1 << 60) or D >= dur_ms:
                    continue
                for d2, dw2, acts2 in adj.get(s, []):
                    t = D + dw2
                    if t >= dur_ms:
                        continue
                    if any(e2 == ek for e2, _ in events(acts2)):
                        hit = t
                        break
                    if d2 >= 0 and t < dist.get(d2, 1 << 60):
                        dist[d2] = t
                        heapq.heappush(pq, (t, d2))
            if hit is not None:
                finds.setdefault(ek, (hit / 1000, dur))
    return [(k, gap, dur) for k, (gap, dur) in sorted(finds.items())]


def counter_carry_findings(g: Graph, counters: dict) -> list:
    """Window-scoped suspicion: a counter register crossing a calendar-cell
    boundary with a non-initial value. Not auto-judged — surfaced as a
    question ('carries Saturday's count into Sunday — intended?')."""
    out: set = set()
    for src, dst, dw, acts in g.edges:
        if dst < 0 or src == dst:
            continue
        ks, kd = g.state_keys[src], g.state_keys[dst]
        if ks[2] == kd[2]:                     # same calendar cell
            continue
        for nm, val in kd[0]:
            if nm in counters and isinstance(val, (int, float)) \
                    and not isinstance(val, bool) and val != counters[nm]:
                out.add((nm, val))
    return sorted(out)


def check(stmts: list, period_ms: int) -> ObligationReport:
    r = ObligationReport()
    r.static = static_actions(stmts)
    g_full = explore(stmts, period_ms, keep_graph=True)    # seeded worlds too
    r.graph = g_full
    r.fired = set(g_full.fired)
    r.dead = r.static - r.fired
    from .explore import derive_axes
    from .predicates import classify_vars
    vinfo = classify_vars(stmts)
    axes = derive_axes(stmts, vinfo)
    r.mirror_gv = list(axes.mirror_gv)
    if r.mirror_gv:
        g_unseeded = explore(stmts, period_ms, mirror_mode="unseeded")
        r.seed_dependent = r.fired - set(g_unseeded.fired)
    r.overlaps = overlap_findings(g_full, DURATION_ARGS)
    counters = {nm: (vinfo[nm].init or 0) for nm in axes.counter_caps
                if nm in vinfo and vinfo[nm].role == "state"
                and not vinfo[nm].timestamp}
    r.counter_carry = counter_carry_findings(g_full, counters)
    return r


def _fmt(k: tuple) -> str:
    svc, m, tgt = k
    t = ("#" + "#".join(tgt)) if tgt else ""
    return f"{svc}{t}.{m}"


def main() -> None:
    import json
    from adapt.inventory import base_office
    from .interp import parse
    from .ground import from_adapt, ground

    devs = from_adapt(base_office())
    data = json.load(open("explorer/corpus/joi_automation_codes.json"))
    print(f"{'시나리오':26s} {'정적':>4s} {'발화':>4s}  판정")
    for s in data:
        if s.get("cron") not in ("", "x", None):
            continue
        try:
            gstmts, _ = ground(parse(s["code"]), devs)
            r = check(gstmts, int(s["period"]))
            problems = []
            for k in sorted(r.dead):
                problems.append(f"VACUOUS {_fmt(k)}")
            for k in sorted(r.seed_dependent):
                problems.append(f"SEED-DEP {_fmt(k)} (전제: {r.mirror_gv} 사전 시드)")
            for k, gap, dur in r.overlaps:
                problems.append(f"OVERLAP {_fmt(k)} ({dur}s 점유 중 {gap}s 만에 재발화)")
            for nm, val in r.counter_carry:
                problems.append(f"COUNTER-CARRY {nm}={val} 달력 경계 생존 — 의도?")
            verdict = "; ".join(problems) if problems else "전 액션 도달 가능"
            print(f"{s['name'][:24]:26s} {len(r.static):>4d} {len(r.fired):>4d}"
                  f"  {verdict}")
        except Unsupported as e:
            print(f"{s['name'][:24]:26s}    —    Unsupported: {e}")

    print("\n== 의무 데모 ==")
    intr = next(s for s in data if s["name"] == "보안모드 침입 감지")
    mut = intr["code"].replace("alert_cooldown := 600", "alert_cooldown := 5")
    assert mut != intr["code"]
    gm, _ = ground(parse(mut), devs)
    rm = check(gm, int(intr["period"]))
    ov = "; ".join(f"OVERLAP {_fmt(k)} ({dur}s 점유, {gap}s 간격)"
                   for k, gap, dur in rm.overlaps) or "겹침 없음(?)"
    print(f"침입 cooldown 600→5 변형: {ov}")
    gi, _ = ground(parse(intr["code"]), devs)
    ri = check(gi, int(intr["period"]))
    print(f"침입 base(cooldown 600): {'겹침 없음 확인' if not ri.overlaps else ri.overlaps}")

    from .demo_tick import SRC as DOOR_SRC
    from .explore import DAY_MS
    rd = check(parse(DOOR_SRC), 1000)
    cc = "; ".join(f"COUNTER-CARRY {nm}={val}" for nm, val in rd.counter_carry)
    print(f"문-불 데모(주말 count): {cc or '경계 생존 없음'}"
          f"  ← 통산 3회인지 주말당 3회인지 표면화 대상")


if __name__ == "__main__":
    main()
