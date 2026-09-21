"""실행기(Runner) — 프로그램 한 개를 다루는 데 필요한 것의 묶음.

나란히 비교(product.py)가 JoI 코드에 못박히지 않도록, 비교기가 프로그램
한쪽에 요구하는 것만 작은 계약으로 정의한다:

  - vars_info      상태 변수 목록 + 성격(래치/시각/카운터) — VarInfo dict
  - axes           이 프로그램이 구분하는 입력 칸·시간 임계 — Axes
  - check_finite(axes)  못 다루는 변수 이름 목록 (비면 통과).
                   비교 때는 양쪽 합집합 axes를 받는다.
  - step(vars, gv, inputs, now_ms, first_tick) -> StepResult

  - stmts (선택)   JoI 문장 AST. 있으면 feasibility의 콤보 dedup에 쓰인다.
                   양쪽 다 있을 때만 dedup — 한쪽이라도 없으면 "불확실하면
                   유지" 원칙대로 dedup을 건너뛴다.

JoiRunner는 기존 함수들을 그대로 감싼다(동작 변화 0). IR 한-걸음 실행기
(ir_step.py), HA 실행기가 뒤이어 같은 자리에 들어온다.
"""

from __future__ import annotations

from dataclasses import dataclass

from explorer.runtime import joi_parser as jp
from explorer.analysis.explore import Axes, derive_axes, finiteness_check
from explorer.runtime.interp import StepResult, Unsupported, parse, step
from explorer.analysis.predicates import classify_vars, program_var_names, walk_stmts


class TerminalRunner:
    """Make termination absorbing while leaving it outside ACTION observation."""
    key = "__vets_terminated"

    def __init__(self, inner):
        from explorer.analysis.predicates import VarInfo
        self.inner = inner
        self.vars_info = dict(inner.vars_info)
        if self.key in self.vars_info or self.key in program_var_names(getattr(inner, "stmts", [])):
            raise Unsupported(f"reserved verifier variable: {self.key}")
        self.vars_info[self.key] = VarInfo("state", init=False)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def step(self, vars_, gv, inputs, now_ms, first_tick=False):
        if vars_.get(self.key):
            return StepResult(dict(vars_), dict(gv), [], True)
        result = self.inner.step(vars_, gv, inputs, now_ms, first_tick)
        if result.terminated:
            result.vars = {**result.vars, self.key: True}
        return result

    def next_wakeup_ms(self, vars_, now_ms, input_step_ms):
        if vars_.get(self.key):
            return None
        method = getattr(self.inner, "next_wakeup_ms", None)
        return method(vars_, now_ms, input_step_ms) if method else now_ms + input_step_ms


@dataclass
class JoiRunner:
    stmts: list
    vars_info: dict
    axes: Axes

    @classmethod
    def from_src(cls, src: str | list) -> "JoiRunner":
        stmts = src if isinstance(src, list) else parse(src)
        if any(isinstance(x, jp.ForEach) for x in walk_stmts(stmts)):
            raise Unsupported("ForEach needs grounding")
        vars_ = classify_vars(stmts)
        return cls(stmts, vars_, derive_axes(stmts, vars_))

    def check_finite(self, axes: Axes | None = None) -> list[str]:
        return finiteness_check(self.vars_info, axes or self.axes, self.stmts)

    def step(self, vars_: dict, gv: dict, inputs: dict, now_ms: int,
             first_tick: bool = False) -> StepResult:
        return step(self.stmts, vars_, gv, inputs, now_ms, first_tick)


class DoneLatch:
    """겉옷: 안쪽 실행기가 "끝났다"(terminated)를 낸 뒤로는 영구히 멈춤.

    주기형 JoI의 최상위 break는 플랫폼에서 블록의 영구 종료지만, v2
    interp는 tick마다 처음부터 다시 돌므로 다음 tick에 되살아난다.
    __fin 래치가 그 플랫폼 의미(한 번 끝나면 끝)를 복원한다.
    terminated 플래그는 삼킨다(항상 False) — 비교는 행동(액션)으로만
    하고, 상대편(IR END → done 래치 후 무행동)과 같은 모양이 된다.
    stmts는 일부러 노출하지 않는다 → product의 콤보 dedup은 건너뜀(보수적).
    """

    def __init__(self, inner) -> None:
        from explorer.analysis.predicates import VarInfo
        self.inner = inner
        self.vars_info = dict(inner.vars_info)
        self.vars_info["__fin"] = VarInfo("state", init=False)
        self.axes = inner.axes

    def check_finite(self, axes: Axes | None = None) -> list[str]:
        return self.inner.check_finite(axes)

    def next_wakeup_ms(self, vars_, now_ms, input_step_ms):
        if vars_.get("__fin"):
            return None
        method = getattr(self.inner, "next_wakeup_ms", None)
        return method(vars_, now_ms, input_step_ms) if method else now_ms + input_step_ms

    def step(self, vars_: dict, gv: dict, inputs: dict, now_ms: int,
             first_tick: bool = False) -> StepResult:
        if vars_.get("__fin"):
            return StepResult(dict(vars_), dict(gv), [])
        r = self.inner.step(vars_, gv, inputs, now_ms, first_tick)
        if r.terminated:
            v = dict(r.vars)
            v["__fin"] = True
            return StepResult(v, r.gv, r.actions)
        return r
