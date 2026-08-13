"""One-shot JoI 실행기 — period=0 스크립트 (시작할 때 한 번만 실행).

플랫폼 JoI의 one-shot 스크립트는 blocking 문(wait until / delay)에서
멈췄다가 이어서 실행된다. v2 interp는 순수 per-tick이라 이 멈춤을
모른다. 여기서는 최상위 문장 목록을 blocking 문 경계로 구간(segment)
나누고, 실행 구간은 interp.step으로 그대로 돌리며 "어느 구간까지
왔나"(__seg)와 delay 시작 시각(__dstart)만 상태로 얹는다 — IR 한-걸음
실행기(ir_step.py)와 같은 pc 방식의 겉옷이다.

한계(명시): blocking 문이 if/loop 안(중첩)에 있으면 아직 못 다룬다 →
Unsupported. 최상위만 지원 (캐시 코퍼스의 one-shot은 최상위 사용).

Run:  (m3_check가 사용)
"""

from __future__ import annotations

from dataclasses import replace

from . import joi_parser as jp
from .explore import Axes, derive_axes, finiteness_check
from .interp import StepResult, Unsupported, parse, step
from .predicates import VarInfo, classify_vars, walk_stmts


def _split(stmts: list) -> list[tuple]:
    """최상위 문장 → [("run",[문장들]) | ("wait",cond) | ("delay",ms)]"""
    segs: list[tuple] = []
    buf: list = []
    for s in stmts:
        if isinstance(s, (jp.WaitUntil, jp.Delay)):
            if buf:
                segs.append(("run", buf))
                buf = []
            if isinstance(s, jp.WaitUntil):
                segs.append(("wait", s.cond))
            else:
                segs.append(("delay", int(s.ms)))
        else:
            for x in walk_stmts([s]):
                if isinstance(x, (jp.WaitUntil, jp.Delay)) and x is not s:
                    raise Unsupported("중첩 blocking 문 (if/loop 안 wait/delay)")
            buf.append(s)
    if buf:
        segs.append(("run", buf))
    return segs


class OneShotRunner:
    def __init__(self, src: str | list) -> None:
        stmts = src if isinstance(src, list) else parse(src)
        if any(isinstance(x, jp.ForEach) for x in walk_stmts(stmts)):
            raise Unsupported("ForEach needs grounding")
        self.stmts = stmts
        self.segs = _split(stmts)
        self._joi_vars = classify_vars(stmts)
        self.vars_info = dict(self._joi_vars)
        self.vars_info["__seg"] = VarInfo("state", init=0)
        self.vars_info["__done"] = VarInfo("state", init=False)
        self.vars_info["__dstart"] = VarInfo("state", timestamp=True)
        axes = derive_axes(stmts, self._joi_vars)
        ts = set(axes.ts_thresholds)
        ts.update(ms / 1000 for k, ms in
                  ((k, p) for k, p in self.segs if k == "delay"))
        self.axes = replace(axes, ts_thresholds=sorted(ts))

    def check_finite(self, axes: Axes | None = None) -> list[str]:
        # 추가 상태(__seg 유한 enum·__done 래치·__dstart zone)는 구조상
        # 유한 — 원본 변수만 기존 규칙으로 검사한다.
        return finiteness_check(self._joi_vars, axes or self.axes, self.stmts)

    def step(self, vars_in: dict, gv_in: dict, inputs: dict, now_ms: int,
             first_tick: bool = False) -> StepResult:
        vars_, gv = dict(vars_in), dict(gv_in)
        actions: list = []
        if vars_.get("__done"):
            return StepResult(vars_, gv, actions)
        seg = int(vars_.get("__seg", 0))
        while seg < len(self.segs):
            kind, payload = self.segs[seg]
            if kind == "run":
                # one-shot: 각 구간은 정확히 한 번 실행 → := 초기화 활성
                r = step(payload, vars_, gv, inputs, now_ms, first_tick=True)
                vars_ = {**vars_, **r.vars}
                gv = r.gv
                actions.extend(r.actions)
                if r.terminated:      # 최상위 break 등 — 즉시 종료
                    seg = len(self.segs)
                    break
                seg += 1
            elif kind == "wait":
                # 조건을 interp 의미론 그대로 평가 (임시 대입 후 즉시 회수)
                probe = step([jp.Assign("__c", "=", payload)],
                             vars_, gv, inputs, now_ms)
                if not probe.vars.get("__c"):
                    break
                seg += 1
            else:                     # delay
                reg = vars_.get("__dstart")
                if not reg:
                    vars_["__dstart"] = now_ms / 1000
                    break
                if now_ms - round(reg * 1000) >= payload:
                    vars_["__dstart"] = 0
                    seg += 1
                else:
                    break
        vars_["__seg"] = seg
        vars_.pop("__c", None)
        if seg >= len(self.segs):
            vars_["__done"] = True
        return StepResult(vars_, gv, actions)
