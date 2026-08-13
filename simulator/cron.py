"""Cron scheduling driver: map a cron-fired scenario onto the tick explorer.

v1 runtime semantics: the cron spec defines firing times; the script body
runs once per fire (period sub-ticks only fit inside windows longer than a
minute — corpus crons fire every minute, so the period field is inert).
Equivalent tick model, explored with the ordinary machinery:

- tick grid = 60 s (the cron minute grid)
- cron field constraints become a calendar GUARD wrapping the body:
  `* * * * 4` → `if (clock.weekday == "thursday") { body }` — registers
  survive non-matching minutes untouched, exactly like unfired windows
- `:=` initializers stay top-level (first-tick-only, unchanged)
- a top-level `break` in cron semantics ends the current WINDOW, not the
  script → rewritten to AbortTickStmt (skip rest of this tick, keep state).
  `break` inside loop() keeps its loop-exit meaning.

Supported specs: minute/hour = `*` or int; day-of-week = `*` or 0-7
(0/7 = sunday); day-of-month and month must be `*` (else Unsupported).

Run:  python -m simulator.cron   (강수예보 · 주간미팅 exploration + obligations)
"""

from __future__ import annotations

from . import expr as expr_mod
from . import joi_parser as jp
from .interp import AbortTickStmt, Unsupported

CRON_TICK_MS = 60_000
_DOW = {0: "sunday", 1: "monday", 2: "tuesday", 3: "wednesday",
        4: "thursday", 5: "friday", 6: "saturday", 7: "sunday"}


def _field(v: str, lo: int, hi: int, name: str) -> int | None:
    if v == "*":
        return None
    if v.isdigit() and lo <= int(v) <= hi:
        return int(v)
    raise Unsupported(f"cron {name} field {v!r} (only * or a single int)")


def parse_cron(spec: str) -> dict:
    parts = spec.split()
    if len(parts) != 5:
        raise Unsupported(f"cron spec {spec!r}")
    minute = _field(parts[0], 0, 59, "minute")
    hour = _field(parts[1], 0, 23, "hour")
    if parts[2] != "*" or parts[3] != "*":
        raise Unsupported("cron day-of-month/month must be *")
    dow = _field(parts[4], 0, 7, "day-of-week")
    return {"minute": minute, "hour": hour, "dow": dow}


def _rewrite_breaks(stmts: list, loop_depth: int = 0) -> list:
    out = []
    for s in stmts:
        if isinstance(s, jp.Break) and loop_depth == 0:
            out.append(AbortTickStmt())
        elif isinstance(s, jp.IfStmt):
            out.append(jp.IfStmt(s.cond,
                                 _rewrite_breaks(s.then_body, loop_depth),
                                 _rewrite_breaks(s.else_body or [],
                                                 loop_depth)))
        elif isinstance(s, jp.Loop):
            out.append(jp.Loop(s.cond, _rewrite_breaks(s.body,
                                                       loop_depth + 1)))
        else:
            out.append(s)
    return out


def prepare(stmts: list, cron: str) -> tuple[list, int]:
    """Grounded statements + cron spec → (tick statements, tick period)."""
    c = parse_cron(cron)
    inits = [s for s in stmts
             if isinstance(s, jp.Assign) and s.op == ":="]
    body = _rewrite_breaks([s for s in stmts if s not in inits])
    guards = []
    if c["dow"] is not None:
        guards.append(expr_mod.BinaryOp(
            "==", expr_mod.DeviceRef("clock.weekday"),
            expr_mod.Lit(_DOW[c["dow"]])))
    if c["hour"] is not None:
        guards.append(expr_mod.BinaryOp(
            "==", expr_mod.DeviceRef("clock.hour"), expr_mod.Lit(c["hour"])))
    if c["minute"] is not None:
        guards.append(expr_mod.BinaryOp(
            "==", expr_mod.DeviceRef("clock.minute"),
            expr_mod.Lit(c["minute"])))
    if guards:
        g = guards[0]
        for extra in guards[1:]:
            g = expr_mod.BinaryOp("and", g, extra)
        body = [jp.IfStmt(g, body, [])]
    return inits + body, CRON_TICK_MS


def main() -> None:
    import json
    import time as _time
    from adapt.inventory import base_office
    from .interp import parse
    from .ground import from_adapt, ground
    from .obligations import check, _fmt

    devs = from_adapt(base_office())
    data = json.load(open("paper_v2/joi_automation_codes.json"))
    for s in data:
        cron = s.get("cron", "")
        if cron in ("", "x", None):
            continue
        try:
            gstmts, rep = ground(parse(s["code"]), devs)
            tstmts, tick = prepare(gstmts, cron)
            t0 = _time.time()
            r = check(tstmts, tick)
            dt = _time.time() - t0
            g = r.graph
            problems = [f"VACUOUS {_fmt(k)}" for k in sorted(r.dead)]
            problems += [f"SEED-DEP {_fmt(k)}" for k in sorted(r.seed_dependent)]
            print(f"{s['name'][:22]:24s} cron={cron!r:14s} 상태={g.n_states:<5d}"
                  f" 에지={g.n_edges:<7d} {'닫힘' if g.closed else '미완'}"
                  f" {dt:5.1f}s  {'; '.join(problems) or '전 액션 도달 가능'}")
            if rep.floating:
                print(f"{'':24s} 부유: {rep.floating}")
        except Unsupported as e:
            print(f"{s['name'][:22]:24s} Unsupported: {e}")


if __name__ == "__main__":
    main()
