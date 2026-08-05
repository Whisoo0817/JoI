"""Tick-by-tick walkthrough of interp.step on the weekend-door-light example.

Run:  python -m simulator.demo_tick   (from /home/gnltnwjstk/joi)

Prints, for each tick: the inputs fed in, the variable store after the tick,
and any emitted actions — the "beginner view" of what one step() call does.
"""

from __future__ import annotations

from .interp import parse, step, clock_state

SRC = """
count := 0
was_open := false
done := false

wd = (#Clock).clock_weekday
hr = (#Clock).clock_hour
weekend_pm = false
if ((wd == "saturday" or wd == "sunday") and hr >= 12 and hr < 18) { weekend_pm = true }

open = false
if ((#Door).contact == "open") { open = true }

if (done == false and weekend_pm == true) {
  if (open == true and was_open == false) {
    (#Light).light_on()
    count = count + 1
    if (count >= 3) { done = true }
  }
}
was_open = open
"""

# Saturday 14:00. t=0 is Monday 00:00, so Saturday = day 5.
SAT_14H = (5 * 24 + 14) * 3_600_000

SCHEDULE = [
    ("closed", "닫힌 채 시작"),
    ("closed", "그대로"),
    ("open",   "1번째 열림"),
    ("open",   "열린 채 유지 (엣지 아님)"),
    ("closed", "닫힘"),
    ("open",   "2번째 열림"),
    ("closed", "닫힘"),
    ("open",   "3번째 열림 → 종료 래치"),
    ("closed", "닫힘"),
    ("open",   "4번째 열림 (이미 종료)"),
]


def main() -> None:
    stmts = parse(SRC)
    vars_: dict = {}
    gv: dict = {}
    now = SAT_14H
    print(f"시작 시각: 토요일 14:00  (clock={clock_state(now)['clock.weekday']}"
          f" {clock_state(now)['clock.hour']}시)\n")
    for i, (door, note) in enumerate(SCHEDULE):
        r = step(stmts, vars_, gv, {"door.contact": door}, now,
                 first_tick=(i == 0))
        vars_, gv = r.vars, r.gv
        regs = {k: vars_[k] for k in ("count", "was_open", "done")}
        acts = " ".join(repr(a) for a in r.actions) or "-"
        print(f"tick {i:2d}  door={door:6s}  {regs}  actions: {acts}   ({note})")
        now += 1_000  # period 1s

    print("\n--- 평일에 문이 열리면? (수요일 14:00) ---")
    WED_14H = (2 * 24 + 14) * 3_600_000
    vars_, gv, now = {}, {}, WED_14H
    for i, door in enumerate(["closed", "open"]):
        r = step(stmts, vars_, gv, {"door.contact": door}, now,
                 first_tick=(i == 0))
        vars_, gv = r.vars, r.gv
        acts = " ".join(repr(a) for a in r.actions) or "-"
        print(f"tick {i:2d}  door={door:6s}  count={vars_['count']}  actions: {acts}")
        now += 1_000


if __name__ == "__main__":
    main()
