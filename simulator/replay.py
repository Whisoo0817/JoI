"""Deployment replay: does a certified behavior ever ENGAGE in this home?

Exploration answers what the code CAN do. It cannot answer whether any of
that ever happened here. This module drives the same interpreter with a
home's recorded sensor trace instead of enumerated inputs, then reads the
result against the certified graph.

The point is not "no action for N days therefore broken". That inference is
wrong often enough to be dangerous (a fire alert SHOULD stay silent). The
point is to separate causes that look identical in a platform's
`last_triggered` field:

  VACUOUS       the action fires on no edge at all — a code defect, and no
                amount of data changes it (already reported statically)
  WINDOW        reachable, but every edge that emits it needs a calendar
                cell the observation window never contained (asking a
                summer log about the heating branch)
  UNMET         reachable and in-window, but some guard cell never occurred
                in this home (the named axis and value are the finding:
                "occupancy was never true", "temperature never exceeded
                25.5") — this is where mis-fitted thresholds and dead
                preconditions surface
  NONCONFORM    the guard WAS satisfied in the trace and the code would
                have acted, but the platform log shows no such action —
                the defect is in deployment, not in the code
  ENGAGED       fired, with a count and a days-since-last

Only VACUOUS is a verdict. The rest are observations bounded by the window,
and they are reported with the window and its gaps so nobody reads absence
of evidence as evidence of absence.

Run:  python -m simulator.replay   (synthetic traces until real logs land)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .explore import (DAY_MS, cell_of, derive_axes, explore, fired_key)
from .interp import step
from .predicates import classify_vars

# axes whose absence is a property of the observation window, not the home
CAL_AXES = ("clock.month", "clock.hour", "clock.weekday", "clock.isholiday")


@dataclass
class LogRow:
    """One sampled instant of the home. `inputs` uses the same keys the
    explorer uses (`aq1.temperature`, `@gv:occupancy`). `actions` is what
    the PLATFORM recorded, when available; None means unknown and disables
    the NONCONFORM check for that row."""
    t_ms: int
    inputs: dict
    actions: set | None = None


@dataclass
class Finding:
    action: tuple
    status: str
    detail: str = ""
    count: int = 0
    last_ms: int | None = None


@dataclass
class ReplayReport:
    window_ms: int = 0
    rows: int = 0
    gaps: list = field(default_factory=list)      # (from_ms, to_ms)
    findings: list = field(default_factory=list)
    nonconform: int = 0
    unmodeled: list = field(default_factory=list)  # logged, not in graph
    cells_seen: dict = field(default_factory=dict)


def _split(inputs: dict) -> tuple[dict, dict]:
    return ({k: v for k, v in inputs.items() if not k.startswith("@gv:")},
            {k[4:]: v for k, v in inputs.items() if k.startswith("@gv:")})


def replay(stmts: list, period_ms: int, rows: list[LogRow],
           graph=None) -> ReplayReport:
    r = ReplayReport(rows=len(rows))
    if not rows:
        return r
    g = graph if graph is not None else explore(stmts, period_ms,
                                                keep_graph=True)
    vinfo = classify_vars(stmts)
    axes = derive_axes(stmts, vinfo)

    r.window_ms = rows[-1].t_ms - rows[0].t_ms
    for a, b in zip(rows, rows[1:]):
        if b.t_ms - a.t_ms > 2 * period_ms:
            r.gaps.append((a.t_ms, b.t_ms))

    seen: dict[str, set] = {}
    counts: dict[tuple, int] = {}
    last: dict[tuple, int] = {}
    miss: dict[tuple, int] = {}
    vars_, gv = {}, {}
    for n, row in enumerate(rows):
        world, gvs = _split(row.inputs)
        for k, v in row.inputs.items():
            # store the CELL, not the reading: a July sample and the April
            # representative are the same observation to this code
            c = cell_of(axes, k, v)
            seen.setdefault(k, set()).add(v if c is None else c)
        res = step(stmts, vars_, {**gv, **gvs}, world, row.t_ms,
                   first_tick=(n == 0))
        expected = {fired_key(a) for a in res.actions}
        for k in expected:
            counts[k] = counts.get(k, 0) + 1
            last[k] = row.t_ms
        if row.actions is not None:
            missing = expected - row.actions
            r.nonconform += len(missing)
            for k in missing:
                miss[k] = miss.get(k, 0) + 1
            r.unmodeled += [(k, row.t_ms) for k in row.actions - expected
                            if k not in g.fired]
        vars_, gv = res.vars, res.gv
    r.cells_seen = {k: sorted(v, key=repr) for k, v in seen.items()}

    # actions the code contains but no edge emits: a code defect the log
    # can never distinguish from "the conditions just never came up"
    from .obligations import static_actions
    for key in sorted(static_actions(stmts) - set(g.fired)):
        r.findings.append(Finding(key, "VACUOUS",
                                  "어떤 입력·무한 시간에도 발화 불가 (정적 판정)"))

    # every action the certified graph says is possible
    end = rows[-1].t_ms
    for key in sorted(g.fired):
        if key in counts:
            if miss.get(key):
                r.findings.append(Finding(
                    key, "NONCONFORM", count=counts[key], last_ms=last[key],
                    detail=f"코드 발화 {counts[key]}회 중 {miss[key]}회가"
                           f" 플랫폼 로그에 없음 (배포 측 결함)"))
            else:
                r.findings.append(Finding(
                    key, "ENGAGED", count=counts[key], last_ms=last[key],
                    detail=f"마지막 발화 "
                           f"{(end - last[key]) / DAY_MS:.1f}일 전"))
            continue
        # which input cells do the emitting edges require, and were any of
        # them ever observed? report the axis that never matched.
        need: dict[str, set] = {}
        for (src, dst, dw, acts), inp in zip(g.edges, g.edge_inputs):
            if any(fired_key(a) == key for a in acts):
                for ax, val in inp.items():
                    need.setdefault(ax, set()).add(val)
        unmet = [(ax, vals) for ax, vals in sorted(need.items())
                 if not (vals & seen.get(ax, set()))]
        if not unmet:
            r.findings.append(Finding(key, "UNMET",
                                      "가드 조합이 관측 창에서 동시 성립한 적 없음"))
            continue
        env = [u for u in unmet if u[0] not in CAL_AXES]
        # an unmet environment cell is a fact about THIS home and is
        # actionable; an unmet calendar cell only says the window was too
        # short. When both block, report the home, not the window.
        ax, vals = (env or unmet)[0]
        txt = f"{ax} ∈ {sorted(vals, key=repr)} 미관측"
        if len(unmet) > 1:
            txt += f" (외 {len(unmet) - 1}개 축도 미충족)"
        r.findings.append(Finding(key, "UNMET" if env else "WINDOW", txt))
    return r


# ── Synthetic traces (placeholder until real logs arrive) ────────────────────

def _july_office(days: int, period_ms: int, occupied: bool = True,
                 t0: int = 28 * DAY_MS) -> list[LogRow]:
    """A summer office: diurnal temperature crossing the 25.5 deadband,
    humidity mid-band, occupancy on weekday work hours."""
    import math

    rows = []
    n = days * DAY_MS // period_ms
    for i in range(n):
        t = t0 + i * period_ms
        mins = (t // 60_000) % 1440
        wd = (t // DAY_MS) % 7
        temp = 24.6 + 1.6 * math.sin((mins - 300) / 1440 * 2 * math.pi)
        occ = occupied and wd < 5 and 540 <= mins < 1080
        rows.append(LogRow(t, {
            "clock.month": 7.0,
            "aq1.temperature": round(temp, 2),
            "ts1.temperature": round(temp - 0.3, 2),
            "aq1.humidity": 55.0,
            "hs1.humidity": 54.0,
            "@gv:occupancy": occ,
        }))
    return rows


def main() -> None:
    import json

    from adapt.inventory import base_office
    from .ground import from_adapt, ground
    from .interp import parse
    from .obligations import _fmt

    devs = from_adapt(base_office())
    data = {s["name"]: s for s in
            json.load(open("paper_v2/joi_automation_codes.json"))}
    s = data["온습도 자동 제어"]
    stmts, _ = ground(parse(s["code"]), devs)
    period = int(s["period"])
    g = explore(stmts, period, keep_graph=True)
    print(f"인증 그래프: 상태 {g.n_states}, 도달 액션 {len(g.fired)}\n")

    def report(title: str, rows: list[LogRow]) -> ReplayReport:
        r = replay(stmts, period, rows, graph=g)
        print(f"== {title} ==")
        print(f"   창 {r.window_ms / DAY_MS:.0f}일, 샘플 {r.rows:,}, "
              f"결측 구간 {len(r.gaps)}")
        for f in r.findings:
            n = f" ×{f.count}" if f.count else ""
            print(f"   [{f.status:10s}] {_fmt(f.action):32s}{n} {f.detail}")
        if r.nonconform:
            print(f"   NONCONFORM: 코드가 실행했어야 할 액션 {r.nonconform}건이"
                  f" 플랫폼 로그에 없음")
        print()
        return r

    report("여름 30일, 정상 재실", _july_office(30, period))
    report("여름 30일, occupancy가 한 번도 참이 아님",
           _july_office(30, period, occupied=False))

    rows = _july_office(30, period)
    r0 = replay(stmts, period, rows, graph=g)
    fired_now = {f.action for f in r0.findings if f.status == "ENGAGED"}
    drop = sorted(fired_now)[0]
    vars_, gv = {}, {}
    for n, row in enumerate(rows):
        world, gvs = _split(row.inputs)
        res = step(stmts, vars_, {**gv, **gvs}, world, row.t_ms,
                   first_tick=(n == 0))
        row.actions = {fired_key(a) for a in res.actions} - {drop}
        vars_, gv = res.vars, res.gv
    report(f"여름 30일, 배포 고장 주입 ({_fmt(drop)} 미실행)", rows)

    # ── why the graph is load-bearing ───────────────────────────────────
    # Same log, two codes. The log is IDENTICAL on the humidifier: zero
    # actions, forever. Only the graph separates "the season never came"
    # from "this code cannot do it at all".
    dead_src = s["code"].replace("    is_winter = true", "    is_winter = false")
    assert dead_src != s["code"]
    dstmts, _ = ground(parse(dead_src), devs)
    dg = explore(dstmts, period, keep_graph=True)
    log = _july_office(30, period)
    print("== 엣지 없이는 구분 불가한 쌍 (같은 로그, 다른 코드) ==")
    for label, st, gg in (("원본", stmts, g), ("is_winter 상실 변형", dstmts, dg)):
        rr = replay(st, period, log, graph=gg)
        hf = [f for f in rr.findings if "hf1" in _fmt(f.action)]
        logged = sum(f.count for f in hf)
        print(f"   [{label}] 가습기 관련 로그 발화 {logged}건 "
              f"→ 엣지 판정: {sorted({f.status for f in hf})}")
        for f in hf:
            print(f"        {f.status:10s} {_fmt(f.action):30s} {f.detail}")


if __name__ == "__main__":
    main()
