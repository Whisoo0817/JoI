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

from . import joi_parser as jp
from .explore import Axes, derive_axes, finiteness_check
from .interp import StepResult, Unsupported, parse, step
from .predicates import classify_vars, walk_stmts


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
