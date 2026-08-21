"""Lockstep product exploration: base × variant equivalence checking.

Both programs run on the SAME input-cell sequence and the SAME time axis;
each transition executes one tick of each and compares the emitted actions
(device calls and GV writes — the full observable channel). A reachable
state where the outputs differ is a divergence, reported with the input
path that reaches it. If the product graph closes with no divergence, the
two programs are output-equivalent for every input sequence and unbounded
time, within the fragment.

Cells/thresholds are the UNION of both sides' predicates, so the input
partition is fine enough for whichever program distinguishes more.

Run:  python -m explorer.product   (self-checks + seeded fault variants)
"""

from __future__ import annotations

import itertools
import time as _time
from dataclasses import dataclass, field

from .explore import (Axes, T0_DEFAULT, next_event_ms, next_key_change_ms,
                      normalize)
from .interp import Unsupported
from .runner import JoiRunner

STATE_CAP = 400_000
STEP_CAP = 4_000_000


def merge_axes(a: Axes, b: Axes) -> Axes:
    cells: dict[str, list] = {}
    for k in set(a.cells) | set(b.cells):
        cells[k] = sorted(set(a.cells.get(k, [])) | set(b.cells.get(k, [])),
                          key=repr)
    caps = dict(a.counter_caps)
    for k, v in b.counter_caps.items():
        caps[k] = max(caps.get(k, 0), v)
    from math import gcd
    mods = dict(a.counter_mods)
    for k, v in b.counter_mods.items():       # 양쪽이 다른 L 이면 최소공배수
        mods[k] = mods[k] * v // gcd(mods[k], v) if k in mods else v
    return Axes(cells,
                sorted(set(a.hours) | set(b.hours)),
                a.weekdays_used or b.weekdays_used,
                a.holiday_used or b.holiday_used,
                sorted(set(a.ts_thresholds) | set(b.ts_thresholds)),
                caps,
                a.param_reads + b.param_reads,
                sorted(set(a.mirror_gv) | set(b.mirror_gv)),
                minutes=sorted(set(a.minutes) | set(b.minutes)),
                hour_ops=sorted(set(a.hour_ops) | set(b.hour_ops)),
                counter_mods=mods)


@dataclass
class Divergence:
    depth: int              # transitions from an initial state
    input_: dict
    dwell_ms: int
    actions_a: tuple
    actions_b: tuple
    path: list              # [(input, dwell_ms), ...] up to the divergence


@dataclass
class ProductResult:
    verdict: str            # "EQUIV" | "DIVERGE"
    n_states: int = 0
    n_steps: int = 0
    closed: bool = True
    divergences: list = field(default_factory=list)
    seconds: float = 0.0
    notes: list = field(default_factory=list)


@dataclass
class ReplayResult:
    confirmed: bool
    at_step: int = -1        # 몇 번째 걸음에서 실제로 갈라졌나 (0-기준)
    mirror_init: dict = field(default_factory=dict)
    actions_a: tuple = ()
    actions_b: tuple = ()
    note: str = ""


def replay_divergence(runner_a, runner_b, div: "Divergence",
                      t0_ms: int | None = None) -> ReplayResult:
    """반례 경로를 구체 상태로 되밟아 진짜 갈라짐인지 확인 (T2 복원).

    탐색(BFS)은 정규화된 상태(키 병합·과근사)를 걷기 때문에 DIVERGE가
    허위일 수 있다. 여기서는 병합 없이 실제 상태 dict를 끌고 기록된
    입력·시간 경로를 그대로 다시 실행한다. 어느 걸음에서든 양쪽 액션이
    실제로 다르면 확인(confirmed) — 반례 = 실행 가능한 입력 시퀀스.
    거울 GV 초기값은 경로에 저장되지 않으므로 조합을 전부 시도한다.
    """
    t0_ms = T0_DEFAULT if t0_ms is None else t0_ms
    axes = merge_axes(runner_a.axes, runner_b.axes)
    ext_gv = {k[4:] for k in axes.cells if k.startswith("@gv:")}
    seq = list(div.path) + [(div.input_, div.dwell_ms)]

    def split(i: dict) -> tuple[dict, dict]:
        return ({k: v for k, v in i.items() if not k.startswith("@gv:")},
                {k[4:]: v for k, v in i.items() if k.startswith("@gv:")})

    def own(gv: dict) -> dict:
        return {k: v for k, v in gv.items() if k not in ext_gv}

    mirror_inits = [dict(zip(axes.mirror_gv, vals)) for vals in
                    itertools.product([None, False, True],
                                      repeat=len(axes.mirror_gv))]
    for m in mirror_inits:
        gv0 = {k: v for k, v in m.items() if v is not None}
        av, ag = {}, dict(gv0)
        bv, bg = {}, dict(gv0)
        now = t0_ms
        for n, (i, d) in enumerate(seq):
            if i is None:        # 기록 없는 걸음(방어) — 재생 불가
                break
            w, gvs = split(i)
            now += d
            ra = runner_a.step(av, {**ag, **gvs}, w, now, first_tick=(n == 0))
            rb = runner_b.step(bv, {**bg, **gvs}, w, now, first_tick=(n == 0))
            if _out(ra.actions) != _out(rb.actions) \
                    or ra.terminated != rb.terminated:
                return ReplayResult(True, n, gv0,
                                    _out(ra.actions), _out(rb.actions))
            if ra.terminated or rb.terminated:
                break            # 양쪽 다 종료했고 액션도 같았음 — 이 초기값은 실패
            av, ag = ra.vars, own(ra.gv)
            bv, bg = rb.vars, own(rb.gv)
    return ReplayResult(False, note="재생에서 갈라짐 없음 — 허위 반례 의심")


def _canon(v):
    """비교용 인자 표기 통일: 100.0(JSON)과 100(코드)은 같은 값."""
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _out(actions) -> tuple:
    out = []
    for a in actions:
        try:
            args = tuple(_canon(x) for x in a.args)
            out.append(repr(type(a)(a.service, a.method, args, a.target)))
        except Exception:
            out.append(repr(a))
    return tuple(sorted(out))


def product_explore(src_a: str | list, src_b: str | list, period_ms: int,
                    t0_ms: int | None = None,
                    max_diverge: int = 3) -> ProductResult:
    """JoI × JoI 진입점 — 실행기(Runner)로 감싸 본체에 넘긴다."""
    return product_runners(JoiRunner.from_src(src_a), JoiRunner.from_src(src_b),
                           period_ms, t0_ms, max_diverge)


def product_runners(runner_a, runner_b, period_ms: int,
                    t0_ms: int | None = None,
                    max_diverge: int = 3) -> ProductResult:
    """실행기 두 개를 나란히 걸으며 액션을 대조한다 (runner.py의 계약 참조)."""
    t_start = _time.time()
    t0_ms = T0_DEFAULT if t0_ms is None else t0_ms
    va, vb = runner_a.vars_info, runner_b.vars_info
    axes = merge_axes(runner_a.axes, runner_b.axes)
    if axes.param_reads:
        raise Unsupported(f"parameterized reads: {axes.param_reads}")
    bad = runner_a.check_finite(axes) + runner_b.check_finite(axes)
    if bad:
        raise Unsupported(f"unbounded carried vars: {bad}")

    res = ProductResult("EQUIV")
    keys = sorted(axes.cells)
    combos = [dict(zip(keys, vals))
              for vals in itertools.product(*(axes.cells[k] for k in keys))]
    if not combos:
        combos = [{}]
    from .feasibility import dedup_combos
    if hasattr(runner_a, "stmts") and hasattr(runner_b, "stmts"):
        combos, dd = dedup_combos([(runner_a.stmts, va), (runner_b.stmts, vb)],
                                  combos)
        if dd.after < dd.before:
            res.notes.append(f"combo dedup {dd.before}→{dd.after}")
    ext_gv = {k[4:] for k in axes.cells if k.startswith("@gv:")}

    def split(i: dict) -> tuple[dict, dict]:
        return ({k: v for k, v in i.items() if not k.startswith("@gv:")},
                {k[4:]: v for k, v in i.items() if k.startswith("@gv:")})

    def own(gv: dict) -> dict:
        return {k: v for k, v in gv.items() if k not in ext_gv}

    visited: dict[tuple, None] = {}
    parents: dict[tuple, tuple] = {}      # key → (parent_key|None, input, dwell)
    queue: list = []                      # (A_vars, A_gv, B_vars, B_gv, now, held)

    def key_of(av, ag, bv, bg, now) -> tuple:
        return (normalize(av, ag, now, va, axes),
                normalize(bv, bg, now, vb, axes))

    def push(av, ag, bv, bg, now, held, parent, i, d) -> None:
        k = key_of(av, ag, bv, bg, now)
        if k not in visited:
            visited[k] = None
            parents[k] = (parent, i, d)
            queue.append((av, ag, bv, bg, now, held))

    def path_to(k) -> list:
        out = []
        while k is not None and k in parents:
            p, i, d = parents[k]
            out.append((i, d))
            k = p
        return list(reversed(out))

    mirror_inits = [dict(zip(axes.mirror_gv, vals)) for vals in
                    itertools.product([None, False, True],
                                      repeat=len(axes.mirror_gv))]
    for i in combos:
        for m in mirror_inits:
            gv0 = {k: v for k, v in m.items() if v is not None}
            w, gvs = split(i)
            ra = runner_a.step({}, {**gv0, **gvs}, w, t0_ms, first_tick=True)
            rb = runner_b.step({}, {**gv0, **gvs}, w, t0_ms, first_tick=True)
            res.n_steps += 2
            if _out(ra.actions) != _out(rb.actions) \
                    or ra.terminated != rb.terminated:
                res.divergences.append(Divergence(
                    0, i, 0, _out(ra.actions), _out(rb.actions), []))
                if len(res.divergences) >= max_diverge:
                    break
                continue
            if not ra.terminated:
                push(ra.vars, own(ra.gv), rb.vars, own(rb.gv), t0_ms, i,
                     None, i, 0)
        if len(res.divergences) >= max_diverge:
            break

    while queue and len(res.divergences) < max_diverge:
        if len(visited) > STATE_CAP or res.n_steps > STEP_CAP:
            res.notes.append("CAP HIT")
            res.closed = False
            break
        av, ag, bv, bg, now, held = queue.pop(0)
        here = key_of(av, ag, bv, bg, now)

        # stutter witness (see explore.py): some holdable input must keep
        # BOTH sides silent and stationary for a long dwell to be legal
        stutter = False
        for cand in [held] + combos:
            w, gvs = split(cand)
            pa = runner_a.step(av, {**ag, **gvs}, w, now + period_ms)
            pb = runner_b.step(bv, {**bg, **gvs}, w, now + period_ms)
            res.n_steps += 2
            if (not pa.actions and not pb.actions
                    and not pa.terminated and not pb.terminated
                    and key_of(pa.vars, own(pa.gv), pb.vars, own(pb.gv),
                               now + period_ms) == here):
                stutter = True
                break
        dwells = [period_ms]
        if stutter:
            for ev in (next_event_ms(av, now, va, axes),
                       next_event_ms(bv, now, vb, axes),
                       next_key_change_ms(av, now, va, axes),
                       next_key_change_ms(bv, now, vb, axes)):
                if ev is not None and ev - now > period_ms:
                    pre = ((ev - now) // period_ms) * period_ms
                    for d in (pre, pre + period_ms):
                        if d > period_ms and d not in dwells:
                            dwells.append(d)

        for i in combos:
            w, gvs = split(i)
            for d in dwells:
                ra = runner_a.step(av, {**ag, **gvs}, w, now + d)
                rb = runner_b.step(bv, {**bg, **gvs}, w, now + d)
                res.n_steps += 2
                if _out(ra.actions) != _out(rb.actions) \
                        or ra.terminated != rb.terminated:
                    res.divergences.append(Divergence(
                        len(path_to(here)) + 1, i, d,
                        _out(ra.actions), _out(rb.actions), path_to(here)))
                    if len(res.divergences) >= max_diverge:
                        break
                    continue
                if not ra.terminated:
                    push(ra.vars, own(ra.gv), rb.vars, own(rb.gv), now + d, i,
                         here, i, d)
            if len(res.divergences) >= max_diverge:
                break

    res.n_states = len(visited)
    res.closed = res.closed and not queue
    if res.divergences:
        res.verdict = "DIVERGE"
    res.seconds = _time.time() - t_start
    return res


# ── Driver: self-equivalence + seeded fault variants ─────────────────────────

def _show(name: str, r: ProductResult, replay_with=None) -> None:
    print(f"{name[:44]:44s} {r.verdict:8s} 상태={r.n_states:<6d} "
          f"step={r.n_steps:<7d} {r.seconds:5.2f}s "
          f"{'닫힘' if r.closed else '미완'} {' '.join(r.notes)}")
    for dv in r.divergences[:2]:
        ia = {k.split(':')[-1].split('.')[-1]: v for k, v in dv.input_.items()}
        print(f"    ↳ 반례: 깊이 {dv.depth}, 입력 {ia}, dwell {dv.dwell_ms/1000:.0f}s")
        print(f"      base : {list(dv.actions_a) or '(무발화)'}")
        print(f"      변형 : {list(dv.actions_b) or '(무발화)'}")
        if replay_with:
            rr = replay_divergence(replay_with[0], replay_with[1], dv)
            tag = (f"확인 (걸음 {rr.at_step})" if rr.confirmed
                   else f"허위? {rr.note}")
            print(f"      재생 : {tag}")


def main() -> None:
    import json
    data = json.load(open("explorer/corpus/joi_automation_codes.json"))
    by_name = {s["name"]: s for s in data}

    print("== 자기동치 (base × base → 전부 EQUIV여야 함) ==")
    for s in data:
        if s.get("cron") not in ("", "x", None):
            continue
        try:
            r = product_explore(s["code"], s["code"], int(s["period"]))
            _show(s["name"], r)
        except Unsupported as e:
            print(f"{s['name'][:44]:44s} —        Unsupported: {e}")

    def mutate(code: str, old: str, new: str) -> str:
        out = code.replace(old, new)
        assert out != code, f"no-op mutation: {old!r} not found"
        return out

    print("\n== 고장 주입 변형 (전부 DIVERGE + 재생 확인이어야 함) ==")

    def show_mut(name: str, base_src: str, mut_src: str, period: int) -> None:
        ra = JoiRunner.from_src(base_src)
        rb = JoiRunner.from_src(mut_src)
        _show(name, product_runners(ra, rb, period), replay_with=(ra, rb))

    fire = by_name["화재 감지 알림"]
    mut1 = mutate(fire["code"], "30 * 60", "3 * 60")
    show_mut("화재: cooldown 30분→3분 (단위류 오류)",
             fire["code"], mut1, int(fire["period"]))

    sec = by_name["보안모드 자동제어"]
    mut2 = sec["code"].replace(
        "if (pushed == true and was_pushed == false)",
        "if (pushed == true)")
    show_mut("보안모드: 엣지→레벨 (was_pushed 조건 삭제)",
             sec["code"], mut2, int(sec["period"]))

    intr = by_name["보안모드 침입 감지"]
    mut3 = intr["code"].replace("now - grace_start > grace_sec",
                                "now - grace_start >= grace_sec")
    show_mut("침입: grace 경계 > → >= (1 tick 조기 발화)",
             intr["code"], mut3, int(intr["period"]))

    mut4 = intr["code"].replace("alert_cooldown := 600",
                                "alert_cooldown := 60")
    show_mut("침입: cooldown 600→60 (재알림 폭주)",
             intr["code"], mut4, int(intr["period"]))


if __name__ == "__main__":
    main()
