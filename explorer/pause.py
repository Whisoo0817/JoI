"""멈춤 이어가기 실행기 — blocking 문이 if 안에 중첩된 JoI 스크립트용.

플랫폼 JoI는 wait until/delay에서 멈췄다가 그 자리부터 이어서 실행한다.
oneshot.py는 최상위 blocking만 다루므로, 여기서는 멈춘 위치를 경로
(__path: 바깥→안쪽 (문장 번호, 가지) 목록)로 기억하고, 다음 tick에 그
자리로 내려가 다시 검사한다. 멈춤은 한 번에 한 곳뿐이라 delay 시작
시각 레지스터(__dstart)는 하나면 된다.

의미(플랫폼 실제 실행과 동일):
- 멈춘 동안 바깥 if 조건은 다시 검사하지 않는다 (멈춘 인스턴스가 그냥
  이어서 실행되는 것).
- repeat=True(주기형): 한 바퀴 끝나면 다음 tick에 처음부터 다시.
  최상위 break는 인스턴스 영구 종료 → terminated (DoneLatch가 고정).
- repeat=False(one-shot): 한 바퀴 끝나면 영구 멈춤 (__done).
- blocking이 아닌 문장은 interp.step에 한 문장씩 맡긴다 (의미 동일).

한계: loop 안 blocking은 회차가 경로에 안 담기므로 Unsupported.

Run:  (m3_check가 사용)
"""

from __future__ import annotations

from dataclasses import replace

from . import joi_parser as jp
from .explore import Axes, derive_axes, finiteness_check
from .interp import StepResult, Unsupported, parse, step
from .predicates import VarInfo, classify_vars, walk_stmts


def has_blocking(stmts: list) -> bool:
    return any(isinstance(x, (jp.WaitUntil, jp.Delay))
               for x in walk_stmts(stmts))


class PauseRunner:
    def __init__(self, src: str | list, repeat: bool) -> None:
        stmts = src if isinstance(src, list) else parse(src)
        if any(isinstance(x, jp.ForEach) for x in walk_stmts(stmts)):
            raise Unsupported("ForEach needs grounding")
        for x in walk_stmts(stmts):
            if isinstance(x, jp.Loop) and has_blocking(x.body):
                raise Unsupported("loop 안 blocking 문 (회차가 경로에 안 담김)")
        self.stmts = stmts
        self.repeat = repeat
        self._joi_vars = classify_vars(stmts)
        self.vars_info = dict(self._joi_vars)
        self.vars_info["__path"] = VarInfo("state", init=())
        self.vars_info["__dstart"] = VarInfo("state", timestamp=True)
        if not repeat:
            self.vars_info["__done"] = VarInfo("state", init=False)
        axes = derive_axes(stmts, self._joi_vars)
        ts = set(axes.ts_thresholds)
        ts.update(x.ms / 1000 for x in walk_stmts(stmts)
                  if isinstance(x, jp.Delay))
        self.axes = replace(axes, ts_thresholds=sorted(ts))

    def check_finite(self, axes: Axes | None = None) -> list[str]:
        # 추가 상태(__path 유한 경로·__dstart zone·__done 래치)는 구조상 유한
        return finiteness_check(self._joi_vars, axes or self.axes, self.stmts)

    def step(self, vars_in: dict, gv_in: dict, inputs: dict, now_ms: int,
             first_tick: bool = False) -> StepResult:
        vars_, gv = dict(vars_in), dict(gv_in)
        actions: list = []
        if vars_.get("__done"):
            return StepResult(vars_, gv, actions)

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
            reg = vars_.get("__dstart")
            if not reg:
                vars_["__dstart"] = now_ms / 1000
                return True
            if now_ms - round(reg * 1000) >= ms:
                vars_["__dstart"] = 0
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
        ft = first_tick if self.repeat else True
        r = go(self.stmts, (), rpath, ft)
        if r != "pause":
            vars_["__path"] = ()
            vars_["__dstart"] = 0
            if not self.repeat:
                vars_["__done"] = True
        return StepResult(vars_, gv, actions, r == "break")
