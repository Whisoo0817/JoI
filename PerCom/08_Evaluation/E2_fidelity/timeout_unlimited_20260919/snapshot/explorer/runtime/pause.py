"""멈춤 이어가기 실행기 — blocking 문이 if 안에 중첩된 JoI 스크립트용.

플랫폼 JoI는 wait until/delay에서 멈췄다가 그 자리부터 이어서 실행한다.
oneshot.py는 최상위 blocking만 다루므로, 여기서는 멈춘 위치를 경로
(__path: 바깥→안쪽 (문장 번호, 가지) 목록)로 기억하고, 다음 tick에 그
자리로 내려가 다시 검사한다. 멈춤은 한 번에 한 곳뿐이라 delay 시작
시각 레지스터(__dstart)는 하나면 된다.

채택한 실행 의미(실제 플랫폼과의 적합성은 별도 검증 대상):
- 멈춘 동안 바깥 if 조건은 다시 검사하지 않는다 (멈춘 인스턴스가 그냥
  이어서 실행되는 것).
- repeat=True(주기형): 회차 종료 후 period_ms를 기다린 뒤 처음부터 다시.
  period_ms 없는 구 경로는 다음 호출에서 재시작하며 timed 탐색에서는 거절한다.
  최상위 break는 인스턴스 영구 종료 → terminated (DoneLatch가 고정).
- repeat=False(one-shot): 한 바퀴 끝나면 영구 멈춤 (__done).
- blocking이 아닌 문장은 interp.step에 한 문장씩 맡긴다 (의미 동일).

한계: loop 안 blocking은 회차가 경로에 안 담기므로 Unsupported.

Run:  (m3_check가 사용)
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from explorer.runtime import joi_parser as jp
from explorer.analysis.explore import Axes, derive_axes, finiteness_check
from explorer.runtime.interp import StepResult, Unsupported, parse, step
from explorer.analysis.predicates import VarInfo, classify_vars, program_var_names, walk_stmts


def has_blocking(stmts: list) -> bool:
    return any(isinstance(x, (jp.WaitUntil, jp.Delay))
               for x in walk_stmts(stmts))


class PauseRunner:
    def __init__(self, src: str | list, repeat: bool,
                 period_ms: int | None = None) -> None:
        stmts = src if isinstance(src, list) else parse(src)
        if any(isinstance(x, jp.ForEach) for x in walk_stmts(stmts)):
            raise Unsupported("ForEach needs grounding")
        for x in walk_stmts(stmts):
            if isinstance(x, jp.Loop) and has_blocking(x.body):
                raise Unsupported("loop 안 blocking 문 (회차가 경로에 안 담김)")
        self.stmts = stmts
        from explorer.analysis.modular import counter_moduli
        self.moduli = counter_moduli(stmts)
        self.repeat = repeat
        self.period_ms = period_ms
        if period_ms is not None and (type(period_ms) is not int or period_ms <= 0):
            raise ValueError("period_ms must be a positive integer")
        self._joi_vars = classify_vars(stmts)
        reserved = {"__path", "__dstart", "__done", "__next_run", "__iterated", "__fin", "__c"}
        conflicts = reserved & program_var_names(stmts)
        if conflicts:
            raise Unsupported(f"reserved runner variables: {sorted(conflicts)}")
        self.vars_info = dict(self._joi_vars)
        self.vars_info["__path"] = VarInfo("state", init=())
        self.vars_info["__dstart"] = VarInfo("state", timestamp=True)
        self.vars_info["__next_run"] = VarInfo("state", timestamp=True)
        self.vars_info["__iterated"] = VarInfo("state", init=False)
        if not repeat:
            self.vars_info["__done"] = VarInfo("state", init=False)
        axes = derive_axes(stmts, self._joi_vars)
        ts = set(axes.ts_thresholds)
        ts.update(x.ms / 1000 for x in walk_stmts(stmts)
                  if isinstance(x, jp.Delay))
        if period_ms:
            ts.add(period_ms / 1000)
        self.axes = replace(axes, ts_thresholds=sorted(ts))

    def check_finite(self, axes: Axes | None = None) -> list[str]:
        # 추가 상태(__path 유한 경로·__dstart zone·__done 래치)는 구조상 유한
        return [n for n in finiteness_check(self._joi_vars, axes or self.axes, self.stmts)
                if n not in self.moduli]

    def step(self, vars_in: dict, gv_in: dict, inputs: dict, now_ms: int,
             first_tick: bool = False) -> StepResult:
        vars_, gv = dict(vars_in), dict(gv_in)
        actions: list = []
        if vars_.get("__done"):
            return StepResult(vars_, gv, actions, True)
        due = vars_.get("__next_run")
        if due is not None and now_ms < round(due * 1000):
            return StepResult(vars_, gv, actions)
        vars_.pop("__next_run", None)

        def run1(s, ft: bool) -> bool:
            """비 blocking 문장 하나를 interp에 맡긴다. break면 True."""
            nonlocal vars_, gv
            r = step([s], vars_, gv, inputs, now_ms, first_tick=ft)
            vars_, gv = dict(r.vars), dict(r.gv)
            actions.extend(r.actions)
            return r.terminated

        def cond_true(cond) -> bool:
            r = step([jp.Assign("__c", "=", cond)], vars_, gv, inputs, now_ms)
            return bool(r.vars.get("__c"))

        def delay_blocked(ms: int) -> bool:
            if ms <= 0:
                return False
            reg = vars_.get("__dstart")
            if reg is None:
                vars_["__dstart"] = Fraction(now_ms, 1000)
                return True
            if now_ms - round(reg * 1000) >= ms:
                vars_.pop("__dstart", None)
                return False
            return True

        def blocked(s) -> bool:
            if isinstance(s, jp.WaitUntil):
                return not cond_true(s.cond)
            return delay_blocked(int(s.ms))

        def go(stmts: list, prefix: tuple, rpath: tuple, ft: bool) -> str:
            """rpath가 있으면 그 위치부터 이어간다. "pause"|"break"|"done"."""
            start = 0
            if rpath:
                idx, br = rpath[0]
                s = stmts[idx]
                if len(rpath) > 1:          # 더 안쪽에서 멈췄음 — if 가지로
                    body = s.then_body if br == 0 else (s.else_body or [])
                    r = go(body, prefix + ((idx, br),), rpath[1:], ft)
                    if r != "done":
                        return r
                else:                        # 여기가 멈춘 blocking 문
                    if blocked(s):
                        return "pause"
                    vars_["__path"] = ()
                start = idx + 1
            for i in range(start, len(stmts)):
                s = stmts[i]
                if isinstance(s, (jp.WaitUntil, jp.Delay)):
                    if blocked(s):
                        vars_["__path"] = prefix + ((i, -1),)
                        return "pause"
                elif isinstance(s, jp.IfStmt) and has_blocking([s]):
                    br = 0 if cond_true(s.cond) else 1
                    body = s.then_body if br == 0 else (s.else_body or [])
                    r = go(body, prefix + ((i, br),), (), ft)
                    if r != "done":
                        return r
                else:
                    if run1(s, ft):
                        return "break"
            return "done"

        rpath = tuple(vars_.get("__path") or ())
        # one-shot은 문장마다 정확히 한 번 실행 → := 초기화 항상 활성
        ft = not vars_.get("__iterated", False) if self.repeat else True
        r = go(self.stmts, (), rpath, ft)
        for name, modulus in self.moduli.items():
            if name in vars_:
                if type(vars_[name]) is not int:
                    raise Unsupported('modular counter must remain an integer')
                vars_[name] %= modulus
        if r != "pause":
            vars_["__path"] = ()
            vars_.pop("__dstart", None)
            vars_["__iterated"] = True
            if not self.repeat:
                vars_["__done"] = True
            elif r == "done" and self.period_ms is not None:
                vars_["__next_run"] = Fraction(now_ms + self.period_ms, 1000)
        return StepResult(vars_, gv, actions,
                          r == "break" or (not self.repeat and r == "done"))

    def next_wakeup_ms(self, vars_, now_ms, input_step_ms):
        if vars_.get("__done"):
            return None
        if vars_.get("__next_run") is not None:
            return round(vars_["__next_run"] * 1000)
        path = vars_.get("__path") or ()
        stmts = self.stmts
        for index, branch in path:
            statement = stmts[index]
            if branch >= 0:
                stmts = statement.then_body if branch == 0 else statement.else_body
        if path and isinstance(statement, jp.Delay):
            return round(vars_["__dstart"] * 1000) + statement.ms
        return now_ms + input_step_ms
