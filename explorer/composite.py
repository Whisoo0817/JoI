"""P4: co-exploration of multiple scenarios sharing one GV store.

Single-scenario exploration treats a GV another scenario writes as a FREE
input — sound (over-approximate) but weak: it can't certify the actual
combination. Here the members run in lockstep on one store, so
`occupancy` is whatever 재실감지 actually wrote, and the questions become
combination-level:

- does the intrusion email chain stay reachable under the real wiring?
- does one member's missing seed CASCADE (재실 never writes → 보안/침입
  read None forever → downstream actions dead)?
- do two members fight over an actuator in the same tick?
- does member execution ORDER change behavior (same-tick write→read race)?

Semantics: all members share the tick grid (equal periods asserted); one
composite tick runs every member once, in list order, threading the GV
store. Order sensitivity is measured, not assumed away.

Run:  python -m explorer.composite   (재실감지 → 보안모드 → 침입감지 3-체인)
"""

from __future__ import annotations

import itertools
import time as _time
from dataclasses import dataclass, field

from . import expr as expr_mod
from . import joi_parser as jp
from .expr import canonical_key
from .interp import Unsupported, step
from .predicates import classify_vars, expr_reads, stmt_exprs, walk_stmts
from .explore import (Axes, T0_DEFAULT, derive_axes, finiteness_check,
                      fired_key, next_event_ms, next_key_change_ms, normalize)

STATE_CAP = 300_000
STEP_CAP = 3_000_000


@dataclass
class Member:
    name: str
    stmts: list
    vinfo: dict
    axes: Axes


@dataclass
class CompositeResult:
    n_states: int = 0
    n_edges: int = 0
    n_steps: int = 0
    closed: bool = True
    fired: set = field(default_factory=set)      # (member, svc, method, tgt)
    conflicts: set = field(default_factory=set)  # (svc, target, methods)
    seconds: float = 0.0
    notes: list = field(default_factory=list)


def gv_written_names(stmts: list) -> set[str]:
    out: set = set()
    for s in walk_stmts(stmts):
        call = s.call if isinstance(s, jp.CallStmt) else (
            s.rhs if isinstance(s, jp.Assign)
            and isinstance(s.rhs, jp.CallExpr) else None)
        if isinstance(call, jp.CallExpr) and call.args is not None:
            svc, m = canonical_key(call.service, call.method)
            if svc == "globalvariable" and m.startswith("set") \
                    and isinstance(call.args[0], expr_mod.Lit):
                out.add(str(call.args[0].value))
    return out


def gv_read_names(stmts: list) -> set[str]:
    out: set = set()
    for s in walk_stmts(stmts):
        for e in stmt_exprs(s):
            reads: list = []
            expr_reads(e, reads)
            out |= {nm for k, nm in reads if k == "gv"}
    return out


def build_members(specs: list[tuple[str, list]]) -> list[Member]:
    ms = []
    for name, stmts in specs:
        vinfo = classify_vars(stmts)
        ms.append(Member(name, stmts, vinfo, derive_axes(stmts, vinfo)))
    return ms


def composite_explore(members: list[Member], period_ms: int,
                      t0_ms: int | None = None,
                      mirror_mode: str = "enumerate") -> CompositeResult:
    t_start = _time.time()
    t0_ms = T0_DEFAULT if t0_ms is None else t0_ms
    res = CompositeResult()

    written = set().union(*(gv_written_names(m.stmts) for m in members))
    read = set().union(*(gv_read_names(m.stmts) for m in members))
    internal_mirror = sorted(written & read)

    for m in members:
        bad = finiteness_check(m.vinfo, m.axes, m.stmts)
        if bad or m.axes.param_reads:
            raise Unsupported(f"{m.name}: {bad or m.axes.param_reads}")

    # merged external input axes (internal GVs are wiring, not inputs)
    cells: dict[str, list] = {}
    for m in members:
        for k, v in m.axes.cells.items():
            cells[k] = sorted(set(cells.get(k, [])) | set(v), key=repr)
    for x in written:
        cells.pop(f"@gv:{x}", None)
    keys = sorted(cells)
    combos = [dict(zip(keys, vals))
              for vals in itertools.product(*(cells[k] for k in keys))]
    if not combos:
        combos = [{}]
    from .feasibility import dedup_combos
    combos, dd = dedup_combos([(m.stmts, m.vinfo) for m in members], combos)
    if dd.after < dd.before:
        res.notes.append(f"combo dedup {dd.before}→{dd.after}")
    ext_gv = {k[4:] for k in keys if k.startswith("@gv:")}

    def split(i: dict) -> tuple[dict, dict]:
        return ({k: v for k, v in i.items() if not k.startswith("@gv:")},
                {k[4:]: v for k, v in i.items() if k.startswith("@gv:")})

    def cstep(varses: list, gv: dict, i: dict, now: int, first: bool = False):
        world, gvs = split(i)
        gv2 = {**gv, **gvs}
        new_vs, acts = [], []
        for m, vars_i in zip(members, varses):
            r = step(m.stmts, vars_i, gv2, world, now, first_tick=first)
            res.n_steps += 1
            gv2 = r.gv
            new_vs.append(r.vars)
            acts.append(r.actions)
        own = {k: v for k, v in gv2.items() if k not in ext_gv}
        return new_vs, own, acts

    def key_of(varses: list, gv: dict, now: int) -> tuple:
        parts = tuple(normalize(v, {}, now, m.vinfo, m.axes)
                      for m, v in zip(members, varses))
        return parts + (tuple(sorted(gv.items())),)

    def note_actions(acts_per_member) -> None:
        flat: dict[tuple, set] = {}
        for m, acts in zip(members, acts_per_member):
            for a in acts:
                res.fired.add((m.name,) + fired_key(a))
                if a.service != "globalvariable":
                    flat.setdefault((a.service, tuple(a.target)),
                                    set()).add(a.method)
        for (svc, tgt), methods in flat.items():
            if {"on", "off"} <= methods:
                res.conflicts.add((svc, tgt, tuple(sorted(methods))))

    visited: dict[tuple, int] = {}
    queue: list = []

    def push(varses, gv, now, held) -> None:
        k = key_of(varses, gv, now)
        if k not in visited:
            visited[k] = len(visited)
            queue.append((varses, gv, now, held))

    if mirror_mode == "unseeded":
        inits = [{}]
    else:
        inits = [dict(zip(internal_mirror, vals))
                 for vals in itertools.product([None, False, True],
                                               repeat=len(internal_mirror))]
        inits = [{k: v for k, v in d.items() if v is not None} for d in inits]

    for i in combos:
        for gv0 in inits:
            vs, gv1, acts = cstep([{} for _ in members], gv0, i, t0_ms,
                                  first=True)
            note_actions(acts)
            push(vs, gv1, t0_ms, i)

    while queue:
        if len(visited) > STATE_CAP or res.n_steps > STEP_CAP:
            res.notes.append("CAP HIT")
            res.closed = False
            break
        varses, gv, now, held = queue.pop(0)
        here = key_of(varses, gv, now)

        stutter = False
        for cand in [held] + combos:
            vs, gv2, acts = cstep(varses, gv, cand, now + period_ms)
            if not any(acts) and key_of(vs, gv2, now + period_ms) == here:
                stutter = True
                break
        dwells = [period_ms]
        if stutter:
            evs = []
            for m, v in zip(members, varses):
                evs.append(next_event_ms(v, now, m.vinfo, m.axes))
                evs.append(next_key_change_ms(v, now, m.vinfo, m.axes))
            for ev in evs:
                if ev is not None and ev - now > period_ms:
                    pre = ((ev - now) // period_ms) * period_ms
                    for d in (pre, pre + period_ms):
                        if d > period_ms and d not in dwells:
                            dwells.append(d)

        for i in combos:
            for d in dwells:
                vs, gv2, acts = cstep(varses, gv, i, now + d)
                res.n_edges += 1
                note_actions(acts)
                push(vs, gv2, now + d, i)

    res.n_states = len(visited)
    res.closed = res.closed and not queue
    res.seconds = _time.time() - t_start
    return res


# ── Driver: the 3-chain ──────────────────────────────────────────────────────

def main() -> None:
    import json
    from adapt.inventory import base_office
    from .interp import parse
    from .ground import from_adapt, ground

    devs = from_adapt(base_office())
    data = {s["name"]: s for s in
            json.load(open("paper_v2/joi_automation_codes.json"))}
    chain = ["재실 상태 감지", "보안모드 자동제어", "보안모드 침입 감지"]
    specs = []
    for nm in chain:
        g, _ = ground(parse(data[nm]["code"]), devs)
        specs.append((nm, g))
        assert int(data[nm]["period"]) == 1000
    members = build_members(specs)

    print("== 3-체인 곱 (공유 GV: occupancy, security_mode) ==")
    r = composite_explore(members, 1000)
    by = {}
    for m, svc, meth, tgt in r.fired:
        by.setdefault(m, set()).add(f"{svc}.{meth}")
    print(f"상태={r.n_states} 에지={r.n_edges} step={r.n_steps}"
          f" {'닫힘' if r.closed else '미완'} {r.seconds:.1f}s"
          f" {' '.join(r.notes)}")
    for nm in chain:
        print(f"  {nm[:16]:18s} 발화: {sorted(by.get(nm, ['-']))}")
    print(f"  액추에이터 충돌: {sorted(r.conflicts) or '없음'}")

    print("\n== 미시드 스토어 연쇄 (unseeded cascade) ==")
    ru = composite_explore(members, 1000, mirror_mode="unseeded")
    dead = {k for k in r.fired} - {k for k in ru.fired}
    print(f"상태={ru.n_states} {'닫힘' if ru.closed else '미완'} {ru.seconds:.1f}s")
    if dead:
        for m, svc, meth, tgt in sorted(dead):
            print(f"  연쇄 사망: [{m[:12]}] {svc}.{meth}")
    else:
        print("  차이 없음")

    print("\n== 실행 순서 민감성 (write→read 동일 tick 경쟁) ==")
    rev = composite_explore(list(reversed(members)), 1000)
    same = {k[1:] for k in r.fired} == {k[1:] for k in rev.fired}
    print(f"역순 실행: 상태={rev.n_states}, 발화집합 "
          f"{'동일' if same else '상이 — 순서 의존!'}"
          f" (정순 {r.n_states}상태 vs 역순 {rev.n_states}상태)")


if __name__ == "__main__":
    main()
