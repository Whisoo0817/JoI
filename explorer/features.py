"""Fail-closed 패턴 탐지기 — 현재 추상화가 감당 못 하는 세 무늬를 찾아 거절.

2026-09-02 P1 Day 1 (whisoo 승인, 리뷰어 계획 반영): full 지원 전에 먼저
허위 EQUIV가 절대 나올 수 없게 막는다. 탐지 무늬:

1. 결합·변형 산술 guard — 비교식의 한쪽이 "맨 읽기 vs 상수"가 아닌 경우.
   축(cells)은 키마다 (op, 상수) 술어의 1차원 분할이므로,
   - 두 입력을 섞은 식 (x + y > 10, x > y)        → joint-guard
   - 한 입력이라도 변형을 거친 식 (x / 2 > 10)     → derived-guard
   는 대표값이 실제 경계(합 20, 몫 경계 등)를 놓칠 수 있다. k=1도
   항등이 아니면 안전하지 않다 (x/2>10의 경계는 20인데 술어 상수는 10).
   guard 모양 자체가 지원 밖(함수 호출 조건 등)이면    → opaque-guard
2. 값이 산술을 거쳐 관찰 지점(액션 인자·GV 쓰기·질의 인자)으로 나가는
   경우 — 두 프로그램이 대표값에서만 우연히 일치할 수 있다 → arith-arg
   (맨 읽기·문자열 이어붙이기는 항등 전달이라 허용: 콤보가 원값을 곱집합
   으로 돌리므로 정확하다.)
3. 포화(saturation)된 counter 값이 관찰 지점으로 나가는 경우 — 포화는
   "비교 전용"일 때만 정당하다. cap 위 5회/6회가 같은 상태로 접히는데
   출력은 다르다                                     → observable-counter
4. 마감 경쟁하는 타이머 — 살아있는 타임스탬프 레지스터가 2개 이상이고
   서로 다른 임계값이 관여하면, 상태 키의 (zone, 선후 부호)만으로는
   교차 순서(v1+c1 vs v2+c2)를 보존하지 못한다        → multi-timer
   (모두 같은 단일 임계값이면 선후 부호로 충분 — 제외. IR은 pc 직렬이라
   서로 다른 wait끼리는 경쟁 불가; 같은 wait의 for+timeout 쌍만 해당.)

전부 과대 탐지(=더 많은 REFUSED) 방향으로만 틀린다. 실제 발생 빈도는
`python3 -m explorer.prevalence`로 측정해 full 지원 여부를 결정한다.

Run:  python3 -m explorer.features   (내장 자가 점검)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import expr as expr_mod
from . import joi_parser as jp
from .expr import canonical_key
from .interp import Unsupported
from .predicates import (CMP_OPS, TS_KEY, VarInfo, _fold_with_params,
                         stmt_exprs, var_defs, walk_stmts)

ARITH_OPS = ("+", "-", "*", "/", "%")
NUM_FUNCS = ("min", "max", "avg", "abs")
CLOCK_FIELDS = ("hour", "minute", "weekday", "isholiday", "timestamp")


@dataclass(frozen=True)
class Feature:
    kind: str          # joint-guard | derived-guard | opaque-guard |
    #                    arith-arg | observable-counter | multi-timer
    detail: str


# ── 공용 조각 ────────────────────────────────────────────────────────────────

def _unparse(n: Any) -> str:
    from .predicates import unparse
    try:
        return unparse(n)
    except Exception:
        return repr(n)


def _is_str_lit(n: Any, vars_: dict) -> bool:
    v = _fold_with_params(n, vars_)
    return isinstance(v, str)


# ── JoI 쪽: 변수 요약 (원천 집합 + 산술 통과 여부) ───────────────────────────

@dataclass
class _ExprInfo:
    sources: frozenset      # 입력 원천: 월드 키 / "@gv:이름" / "query:키"
    arith: bool             # 숫자 산술·수치 함수를 거쳤나
    has_ts: bool            # clock.timestamp 또는 timestamp 변수 관여


def _var_summaries(stmts: list, vars_: dict, defs: dict) -> dict[str, _ExprInfo]:
    """변수 → (전이적 입력 원천, 산술 통과) 고정점. state 변수 포함(값 보존).
    자기 참조(n = n + 1)는 이전 회차 요약을 잎으로 써서 수렴한다."""
    info: dict[str, _ExprInfo] = {}
    names = [nm for nm in vars_ if defs.get(nm)]
    for _ in range(len(names) + 1):
        changed = False
        for nm in names:
            vi = vars_.get(nm)
            if vi is None or vi.timestamp or vi.role == "param":
                continue
            parts = [_expr_info_with(d, vars_, defs, info)
                     for d in defs.get(nm, [])]
            r = _ExprInfo(frozenset().union(*(p.sources for p in parts))
                          if parts else frozenset(),
                          any(p.arith for p in parts),
                          any(p.has_ts for p in parts))
            if info.get(nm) != r:
                info[nm] = r
                changed = True
        if not changed:
            break
    return info


# ── JoI 쪽 분석 ──────────────────────────────────────────────────────────────

def analyze_stmts(stmts: list, vars_: dict[str, VarInfo],
                  axes=None) -> list[Feature]:
    from .explore import _gv_read_name, _read_key, derive_axes
    defs = var_defs(stmts)
    if axes is None:
        axes = derive_axes(stmts, vars_)
    summaries = _var_summaries(stmts, vars_, defs)
    feats: list[Feature] = []

    def einfo(node: Any) -> _ExprInfo:
        return _expr_info_with(node, vars_, defs, summaries)

    def resolve(node: Any, depth: int = 0) -> Any:
        if depth > 4 or not isinstance(node, expr_mod.VarRef):
            return node
        vi = vars_.get(node.name)
        if vi is not None and vi.role == "wire" \
                and len(defs.get(node.name, [])) == 1:
            return resolve(defs[node.name][0], depth + 1)
        return node

    def is_constish(n: Any) -> bool:
        from .explore import _const_options
        if _fold_with_params(n, vars_) is not None:
            return True
        return _const_options(n, vars_, defs) is not None

    bool_reads = _bool_evidenced_reads(stmts, vars_, defs)
    bool_ok = _bool_vars(vars_, defs, bool_reads)

    def is_bare(n: Any) -> bool:
        """항등으로 값을 나르는 잎: 맨 읽기 / GV 읽기 / 질의 읽기 /
        산술 안 거친 변수 / 모델링된 clock 필드."""
        if _read_key(n) is not None or _gv_read_name(n) is not None:
            return True
        if isinstance(n, jp.CallExpr) and n.args is not None:
            return True               # 질의 읽기 (인자 문제는 param_reads가 거름)
        if isinstance(n, expr_mod.ClockRef):
            return n.field.lower() in CLOCK_FIELDS
        if isinstance(n, expr_mod.VarRef):
            s = summaries.get(n.name)
            return s is None or not s.arith
        return False

    def is_boolish(n: Any) -> bool:
        if isinstance(n, expr_mod.Lit):
            return isinstance(n.value, bool)
        if isinstance(n, expr_mod.VarRef):
            vi = vars_.get(n.name)
            if vi is not None and isinstance(vi.init, bool) \
                    and not defs.get(n.name):
                return True
            return n.name in bool_ok
        k = _read_key(n)
        if k is not None:
            return k in bool_reads
        if isinstance(n, jp.CallExpr) and n.args is not None:
            svc, m = canonical_key(n.service, n.method)
            return svc == "globalvariable" and m.startswith("get") \
                and "boolean" in m.lower()
        if isinstance(n, expr_mod.ClockRef):
            return n.field.lower() == "isholiday"
        return False

    def _unmodeled_clock(n: Any) -> bool:
        if isinstance(n, expr_mod.ClockRef):
            return n.field.lower() not in CLOCK_FIELDS
        for v in vars(n).values() if hasattr(n, "__dict__") else ():
            if hasattr(v, "__dict__") and _unmodeled_clock(v):
                return True
            if isinstance(v, (list, tuple)) and any(
                    hasattr(x, "__dict__") and _unmodeled_clock(x)
                    for x in v):
                return True
        return False

    def check_atom(atom: expr_mod.BinaryOp) -> None:
        l, r = resolve(atom.left), resolve(atom.right)
        if _unmodeled_clock(l) or _unmodeled_clock(r):
            # clock_state가 제공하지 않는 필드(clock.time 등) — 지금은
            # None으로 조용히 평가되는 미모델 입력이다
            feats.append(Feature("opaque-guard",
                                 f"미모델 clock 읽기: {_unparse(atom)}"))
            return
        li, ri = einfo(l), einfo(r)
        # 타이머 무늬는 zone 기계가 담당 — 상대가 상수일 때만 면제
        if (li.has_ts and is_constish(r)) or (ri.has_ts and is_constish(l)):
            return
        for side, other in ((l, r), (r, l)):
            if is_constish(other) and is_bare(side):
                return
        if is_constish(l) and is_constish(r):
            return
        if is_bare(l) and is_bare(r) and is_boolish(l) and is_boolish(r):
            return                    # bool×bool — 도메인 전량 열거로 정확
        src = li.sources | ri.sources
        kind = "joint-guard" if len(src) >= 2 else "derived-guard"
        feats.append(Feature(kind, _unparse(atom)))

    def atoms_in(node: Any) -> None:
        """임의 식 안의 비교 원자를 전부 검사 (bool wire 정의 포함)."""
        if isinstance(node, expr_mod.BinaryOp):
            if node.op in ("and", "or"):
                atoms_in(node.left)
                atoms_in(node.right)
                return
            if node.op in CMP_OPS:
                check_atom(node)
                return
            atoms_in(node.left)
            atoms_in(node.right)
            return
        if isinstance(node, expr_mod.UnaryOp):
            atoms_in(node.operand)
        elif isinstance(node, expr_mod.FuncCall):
            for a in node.args:
                atoms_in(a)
        elif isinstance(node, jp.CallExpr) and node.args:
            for a in node.args:
                atoms_in(a)

    def check_guard_shape(node: Any) -> None:
        """guard 조건의 허용 모양: and/or/not 트리 + (검사된) 비교 원자 +
        맨 truthy 읽기/변수. 그 밖(함수 호출 조건 등)은 축이 못 담는다."""
        if isinstance(node, expr_mod.BinaryOp):
            if node.op in ("and", "or"):
                check_guard_shape(node.left)
                check_guard_shape(node.right)
                return
            if node.op in CMP_OPS:
                check_atom(node)
                return
            feats.append(Feature("opaque-guard", _unparse(node)))
            return
        if isinstance(node, expr_mod.UnaryOp) and node.op == "not":
            check_guard_shape(node.operand)
            return
        rn = resolve(node)
        if _read_key(rn) is not None or _gv_read_name(rn) is not None \
                or isinstance(rn, expr_mod.Lit):
            return
        if isinstance(rn, expr_mod.ClockRef):
            if rn.field.lower() in CLOCK_FIELDS:
                return
            feats.append(Feature("opaque-guard",
                                 f"미모델 clock 읽기: {_unparse(rn)}"))
            return
        if isinstance(rn, expr_mod.VarRef):
            s = summaries.get(rn.name)
            if s is None or not s.arith:
                return
        if isinstance(rn, jp.CallExpr) and rn.args is not None:
            return                    # truthy 질의 읽기
        feats.append(Feature("opaque-guard", _unparse(node)))

    # 1·2. guard / 원자 / 관찰 인자
    counters = set(axes.counter_caps)
    tainted = _counter_taint(stmts, vars_, defs, counters)

    def check_sink_arg(a: Any, where: str) -> None:
        inf = einfo(a)
        if inf.arith and (inf.sources or inf.has_ts):
            feats.append(Feature("arith-arg", f"{where}: {_unparse(a)}"))
        reads: list = []
        from .predicates import expr_reads
        expr_reads(a, reads)
        hit = sorted({nm for k, nm in reads if k == "var" and nm in tainted})
        if hit:
            feats.append(Feature(
                "observable-counter", f"{where}: {', '.join(hit)}"))

    for s in walk_stmts(stmts):
        if isinstance(s, (jp.IfStmt, jp.WaitUntil, jp.Loop)):
            check_guard_shape(s.cond)
        elif isinstance(s, jp.Assign):
            atoms_in(s.rhs)
            if isinstance(s.rhs, jp.CallExpr) and s.rhs.args is not None:
                svc, m = canonical_key(s.rhs.service, s.rhs.method)
                args = s.rhs.args
                if svc == "globalvariable" and m.startswith("set"):
                    for a in args[1:]:
                        check_sink_arg(a, f"gv set {_unparse(args[0])}")
                elif not (svc == "globalvariable" or svc == "clock"):
                    for a in args:    # 질의 인자 (키 선택에 값이 들어감)
                        check_sink_arg(a, f"query {svc}.{m}")
        elif isinstance(s, jp.CallStmt):
            svc, m = canonical_key(s.call.service, s.call.method)
            for a in (s.call.args or ()):
                check_sink_arg(a, f"{svc}.{m}")

    # 4. 마감 경쟁 타이머 (프로그램 자체의 타임스탬프 상태 변수 기준)
    ts_vars = sorted(nm for nm, vi in vars_.items()
                     if vi.role == "state" and vi.timestamp)
    if len(ts_vars) >= 2 and len(set(axes.ts_thresholds)) >= 2:
        feats.append(Feature(
            "multi-timer",
            f"타이머 {ts_vars} × 임계 {sorted(set(axes.ts_thresholds))}"))
    return _dedup(feats)


def _expr_info_with(node: Any, vars_: dict, defs: dict,
                    summaries: dict[str, _ExprInfo]) -> _ExprInfo:
    """summaries(변수 고정점)를 잎으로 쓰는 식 요약."""
    from .explore import _gv_read_name, _read_key
    if isinstance(node, expr_mod.Lit):
        return _ExprInfo(frozenset(), False, False)
    if isinstance(node, expr_mod.ClockRef):
        f = node.field.lower()
        if f == "timestamp":
            return _ExprInfo(frozenset(), False, True)
        return _ExprInfo(frozenset({f"clock.{f}"}), False, False)
    k = _read_key(node)
    if k is not None:
        if k == TS_KEY:
            return _ExprInfo(frozenset(), False, True)
        return _ExprInfo(frozenset({k}), False, False)
    g = _gv_read_name(node)
    if g is not None:
        return _ExprInfo(frozenset({f"@gv:{g}"}), False, False)
    if isinstance(node, jp.CallExpr) and node.args is not None:
        svc, m = canonical_key(node.service, node.method)
        if svc == "clock":
            return _ExprInfo(frozenset(), False, m == "timestamp")
        parts = [_expr_info_with(a, vars_, defs, summaries)
                 for a in node.args]
        return _ExprInfo(frozenset({f"query:{svc}.{m}"}).union(
            *(p.sources for p in parts)) if parts
            else frozenset({f"query:{svc}.{m}"}),
            any(p.arith for p in parts), any(p.has_ts for p in parts))
    if isinstance(node, expr_mod.VarRef):
        vi = vars_.get(node.name)
        if vi is None:
            return _ExprInfo(frozenset({f"iter:{node.name}"}), False, False)
        if vi.role == "param":
            return _ExprInfo(frozenset(), False, False)
        if vi.timestamp:
            return _ExprInfo(frozenset(), False, True)
        return summaries.get(node.name, _ExprInfo(frozenset(), False, False))
    if isinstance(node, expr_mod.UnaryOp):
        inner = _expr_info_with(node.operand, vars_, defs, summaries)
        if node.op == "-":
            return _ExprInfo(inner.sources,
                             inner.arith or bool(inner.sources), inner.has_ts)
        return inner
    if isinstance(node, expr_mod.BinaryOp):
        li = _expr_info_with(node.left, vars_, defs, summaries)
        ri = _expr_info_with(node.right, vars_, defs, summaries)
        src = li.sources | ri.sources
        ts = li.has_ts or ri.has_ts
        if node.op in ("and", "or") or node.op in CMP_OPS:
            return _ExprInfo(src, li.arith or ri.arith, ts)
        if node.op == "+" and (_is_str_lit(node.left, vars_)
                               or _is_str_lit(node.right, vars_)):
            return _ExprInfo(src, li.arith or ri.arith, ts)
        if node.op in ARITH_OPS:
            folded = _fold_with_params(node, vars_) is not None
            return _ExprInfo(src, (li.arith or ri.arith
                                   or bool(src) or ts) and not folded, ts)
        return _ExprInfo(src, li.arith or ri.arith, ts)
    if isinstance(node, expr_mod.FuncCall):
        parts = [_expr_info_with(a, vars_, defs, summaries)
                 for a in node.args]
        src = frozenset().union(*(p.sources for p in parts)) \
            if parts else frozenset()
        ts = any(p.has_ts for p in parts)
        if node.name in NUM_FUNCS:
            return _ExprInfo(src, bool(src) or any(p.arith for p in parts), ts)
        return _ExprInfo(src, any(p.arith for p in parts), ts)
    return _ExprInfo(frozenset(), False, False)


def _bool_evidenced_reads(stmts: list, vars_: dict, defs: dict) -> set[str]:
    """bool 리터럴과 비교되거나 truthy 조건으로 쓰인 읽기 키 — 값이 bool이라는
    직접 증거. (derive_axes의 bool_keys는 '상수 없는 비교'도 fallback으로
    담으므로 boolness 판정에는 못 쓴다.)"""
    from .explore import _read_key
    out: set[str] = set()

    def resolve(node: Any, depth: int = 0) -> Any:
        if depth > 4 or not isinstance(node, expr_mod.VarRef):
            return node
        vi = vars_.get(node.name)
        if vi is not None and vi.role == "wire" \
                and len(defs.get(node.name, [])) == 1:
            return resolve(defs[node.name][0], depth + 1)
        return node

    def scan(node: Any) -> None:
        if isinstance(node, expr_mod.BinaryOp):
            if node.op in CMP_OPS:
                for side, other in ((node.left, node.right),
                                    (node.right, node.left)):
                    v = _fold_with_params(other, vars_)
                    if isinstance(v, bool):
                        k = _read_key(resolve(side))
                        if k is not None:
                            out.add(k)
                return
            scan(node.left)
            scan(node.right)
        elif isinstance(node, expr_mod.UnaryOp):
            scan(node.operand)

    for s in walk_stmts(stmts):
        for e in stmt_exprs(s):
            scan(e)
        if isinstance(s, jp.IfStmt):
            k = _read_key(resolve(s.cond))
            if k is not None:
                out.add(k)
    return out


def _bool_vars(vars_: dict, defs: dict, bool_reads: set[str]) -> set[str]:
    """값이 항상 bool인 변수 집합 (최대 고정점: 전부 bool로 가정하고 반증).
    bool 도메인은 축·상태 키가 전량 열거하므로 bool끼리의 비교는 정확하다."""
    from .explore import _read_key
    assume = {nm for nm in vars_ if defs.get(nm)}

    def ok(n: Any) -> bool:
        if isinstance(n, expr_mod.Lit):
            return isinstance(n.value, bool)
        if isinstance(n, expr_mod.VarRef):
            vi = vars_.get(n.name)
            if vi is not None and isinstance(vi.init, bool) \
                    and not defs.get(n.name):
                return True
            return n.name in assume
        if isinstance(n, expr_mod.UnaryOp) and n.op == "not":
            return True
        if isinstance(n, expr_mod.BinaryOp):
            if n.op in CMP_OPS:
                return True
            if n.op in ("and", "or"):
                return ok(n.left) and ok(n.right)
            return False
        k = _read_key(n)
        if k is not None:
            return k in bool_reads
        if isinstance(n, jp.CallExpr) and n.args is not None:
            svc, m = canonical_key(n.service, n.method)
            if svc == "globalvariable" and m.startswith("get"):
                return "boolean" in m.lower()
        if isinstance(n, expr_mod.ClockRef):
            return n.field.lower() == "isholiday"
        return False

    for _ in range(len(assume) + 1):
        drop = {nm for nm in assume
                if not all(ok(d) for d in defs.get(nm, []))}
        if not drop:
            break
        assume -= drop
    return assume


def _counter_taint(stmts: list, vars_: dict, defs: dict,
                   counters: set[str]) -> set[str]:
    """포화 counter에서 시작해 대입을 따라 번지는 오염 변수 집합.
    (counter 자신의 self ± c 갱신은 전파 시작점일 뿐 별도 취급 없음.)"""
    from .predicates import expr_reads
    tainted = set(counters)
    for _ in range(len(vars_) + 1):
        changed = False
        for nm, dlist in defs.items():
            if nm in tainted:
                continue
            for d in dlist:
                reads: list = []
                expr_reads(d, reads)
                if any(k == "var" and r in tainted for k, r in reads):
                    tainted.add(nm)
                    changed = True
                    break
        if not changed:
            break
    return tainted


# ── IR 쪽 분석 (compile_ir의 튜플 AST + 명령열) ──────────────────────────────

def _t_reads(n: tuple, out: set) -> None:
    if not isinstance(n, tuple):
        return
    if n[0] == "read":
        out.add(n[1])
    elif n[0] == "var":
        out.add(f"var:{n[1]}")
    elif n[0] in ("abs", "not"):
        _t_reads(n[1], out)
    elif n[0] in ("min", "max"):
        _t_reads(n[1], out)
        _t_reads(n[2], out)
    elif n[0] == "bin":
        _t_reads(n[2], out)
        _t_reads(n[3], out)


def _t_arith(n: tuple) -> bool:
    if not isinstance(n, tuple):
        return False
    if n[0] in ("abs", "min", "max"):
        return True
    if n[0] == "bin":
        if n[1] in ARITH_OPS:
            reads: set = set()
            _t_reads(n, reads)
            return bool(reads)
        return _t_arith(n[2]) or _t_arith(n[3])
    if n[0] == "not":
        return _t_arith(n[1])
    return False


def _t_unparse(n: tuple) -> str:
    if not isinstance(n, tuple):
        return repr(n)
    if n[0] == "lit":
        return repr(n[1])
    if n[0] == "read":
        return n[1]
    if n[0] == "var":
        return f"${n[1]}"
    if n[0] in ("abs", "not"):
        return f"{n[0]}({_t_unparse(n[1])})"
    if n[0] in ("min", "max"):
        return f"{n[0]}({_t_unparse(n[1])}, {_t_unparse(n[2])})"
    if n[0] == "bin":
        return f"({_t_unparse(n[2])} {n[1]} {_t_unparse(n[3])})"
    return repr(n)


def analyze_ir(prog) -> list[Feature]:
    """IrProgram(ins·vars_info·axes) 검사 — analyze_stmts와 같은 무늬."""
    from .ir_step import _CMP
    feats: list[Feature] = []
    counters = {x.cname for x in prog.ins if getattr(x, "cname", "")} \
        | set(prog.axes.counter_caps)

    def check_cond(n: tuple) -> None:
        if not isinstance(n, tuple):
            return
        if n[0] == "bin" and n[1] in ("and", "or"):
            check_cond(n[2])
            check_cond(n[3])
            return
        if n[0] == "not":
            check_cond(n[1])
            return
        if n[0] == "bin" and n[1] in _CMP:
            l, r = n[2], n[3]
            src0: set = set()
            _t_reads(n, src0)
            bad_clock = sorted(
                k for k in src0
                if k.startswith("clock.")
                and k.rsplit(".", 1)[1] not in CLOCK_FIELDS)
            if bad_clock:
                feats.append(Feature(
                    "opaque-guard",
                    f"미모델 clock 읽기: {_t_unparse(n)}"))
                return
            for side, other in ((l, r), (r, l)):
                if other[0] == "lit" and side[0] in ("read", "var"):
                    return            # 맨 읽기/변수 vs 상수 (counter 비교 포함)
            if l[0] == "lit" and r[0] == "lit":
                return
            src: set = set()
            _t_reads(n, src)
            kind = "joint-guard" if len(src) >= 2 else "derived-guard"
            feats.append(Feature(kind, _t_unparse(n)))
            return
        if n[0] in ("read", "var", "lit"):
            return                    # truthy
        feats.append(Feature("opaque-guard", _t_unparse(n)))

    for x in prog.ins:
        if x.cond is not None:
            check_cond(x.cond)
        if x.kind == "WAIT" and x.for_sec > 0 and x.to_sec > 0 \
                and x.for_sec != x.to_sec:
            feats.append(Feature(
                "multi-timer",
                f"wait 지속 {x.for_sec}s vs 제한 {x.to_sec}s 마감 경쟁"))
        for a in (x.args or ()):
            tag, v = a[0], a[1]
            if tag == "var" and v in counters:
                feats.append(Feature("observable-counter",
                                     f"{x.svc}.{x.method}: {v}"))
            elif tag == "expr":
                src: set = set()
                _t_reads(v, src)
                if _t_arith(v):
                    feats.append(Feature(
                        "arith-arg", f"{x.svc}.{x.method}: {_t_unparse(v)}"))
                hit = sorted(s[4:] for s in src
                             if s.startswith("var:") and s[4:] in counters)
                if hit:
                    feats.append(Feature(
                        "observable-counter",
                        f"{x.svc}.{x.method}: {', '.join(hit)}"))
            elif tag == "tmpl":       # 문자열 템플릿 = 항등 전달, counter만 검사
                for p in v:
                    if isinstance(p, tuple) and p[0] == "var" \
                            and p[1] in counters:
                        feats.append(Feature(
                            "observable-counter",
                            f"{x.svc}.{x.method}: {p[1]}"))
    return _dedup(feats)


# ── 실행기 배선 ──────────────────────────────────────────────────────────────

def analyze_runner(r) -> list[Feature]:
    while hasattr(r, "inner"):        # DoneLatch 등 겉옷 벗기기
        r = r.inner
    if hasattr(r, "prog"):            # IrRunner
        return analyze_ir(r.prog)
    if hasattr(r, "stmts"):           # JoiRunner / OneShot / Pause
        vars_ = getattr(r, "_joi_vars", None) or r.vars_info
        return analyze_stmts(r.stmts, vars_, getattr(r, "axes", None))
    return []


def enforce(feats: list[Feature]) -> None:
    if feats:
        head = "; ".join(f"{f.kind}: {f.detail}" for f in feats[:4])
        more = f" 외 {len(feats) - 4}건" if len(feats) > 4 else ""
        raise Unsupported(f"미지원 무늬(fail-closed): {head}{more}")


def _dedup(feats: list[Feature]) -> list[Feature]:
    seen: set = set()
    out: list[Feature] = []
    for f in feats:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


# ── 자가 점검 ────────────────────────────────────────────────────────────────

def _selfcheck() -> None:
    from .interp import parse
    from .predicates import classify_vars

    def kinds(src: str) -> set[str]:
        stmts = parse(src)
        return {f.kind for f in analyze_stmts(stmts, classify_vars(stmts))}

    T = "(#TemperatureSensor).temperatureSensor_temperature"
    H = "(#HumiditySensor).humiditySensor_humidity"
    SAY = '(#Speaker).speaker_speak'
    cases = [
        (f"t = {T}\nif (t > 10) {{ {SAY}(\"x\") }}\n", set()),
        (f"t = {T}\nh = {H}\nif (t > 10 and h < 5) {{ {SAY}(\"x\") }}\n",
         set()),
        (f"t = {T}\nh = {H}\nif (t + h > 100) {{ {SAY}(\"x\") }}\n",
         {"joint-guard"}),
        (f"t = {T}\nh = {H}\nif (t > h) {{ {SAY}(\"x\") }}\n",
         {"joint-guard"}),
        (f"t = {T}\nif (t / 2 > 10) {{ {SAY}(\"x\") }}\n",
         {"derived-guard"}),
        (f"t = {T}\n{SAY}(t * 2)\n", {"arith-arg"}),
        (f"t = {T}\n{SAY}(t)\n", set()),
        (f't = {T}\n{SAY}("v is " + t)\n', set()),
        ("n := 0\nif ((#Door).door_contact == true) { n = n + 1 }\n"
         f"if (n >= 3) {{ {SAY}(n) }}\n", {"observable-counter"}),
        ("n := 0\nif ((#Door).door_contact == true) { n = n + 1 }\n"
         f"if (n >= 3) {{ {SAY}(\"x\") }}\n", set()),
        ("a := 0\nb := 0\nnow = (#Clock).clock_timestamp\n"
         "if ((#Door).door_contact == true) { a = now }\n"
         "if ((#Window).window_contact == true) { b = now }\n"
         f"if (now - a > 30) {{ {SAY}(\"x\") }}\n"
         f"if (now - b > 60) {{ {SAY}(\"y\") }}\n", {"multi-timer"}),
        ("a := 0\nb := 0\nnow = (#Clock).clock_timestamp\n"
         "if ((#Door).door_contact == true) { a = now }\n"
         "if ((#Window).window_contact == true) { b = now }\n"
         f"if (now - a > 30) {{ {SAY}(\"x\") }}\n"
         f"if (now - b > 30) {{ {SAY}(\"y\") }}\n", set()),
    ]
    for src, want in cases:
        got = kinds(src)
        mark = "OK " if got == want else "!! "
        print(f"{mark}{want or '{}'} ← {got or '{}'}  | {src.splitlines()[-2][:60]}")
        assert got == want, (src, got, want)
    print("features selfcheck passed")


if __name__ == "__main__":
    _selfcheck()
