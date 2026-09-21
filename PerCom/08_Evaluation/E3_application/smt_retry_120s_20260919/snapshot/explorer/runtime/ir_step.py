"""IR 한-걸음 실행기 — 확인받은 Timeline IR의 이벤트 시각 전이.

설계는 ir_step_design.md. 요점:
  - IR(json)을 작은 명령 목록으로 펼치고(if/cycle → 번지 점프),
    "어디까지 왔나"(pc) + 시각 레지스터 + 반복 카운터만 상태로 둔다.
  - timed.py가 delay/지속(for)/timeout의 정확한 만료 시각에 호출한다.
    레지스터는 초 단위이며, 키 부재는 비활성이다(t=0도 정상 시작 시각).
  - 엣지(rising) 래치는 처음엔 False("조건을 아직 못 봄") — 시작부터
    조건이 참이면 첫 평가 tick에 발화로 친다. 래치는 회차를 넘어 유지.
  - cycle은 회차 종료 시각부터 period를 기다린 뒤 다음 회차를 시작한다.
  - 이름 규칙(기본값): "Service.Attr" → 센서 키 "service.attr",
    call "Device.Method" → 액션 service/method 소문자. 실제 JoI 코드와의
    불일치는 M3에서 name_map으로 보정한다.

상태 변수 이름: pc, done, p<i>(엣지 래치), s<i>(지속 시작), t<i>(제한시간
시작), d<i>(delay 시작), c<k>(회차 종료), n<k>(회차 수), 그리고 read/call
이 담는 사용자 변수. 새 timed 탐색은 구체 값을 보존하며 cap을 동치로 처리하지 않는다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from explorer.analysis.explore import Axes, OBSERVABLE_VALUE_DOMAIN
from explorer.runtime.expr import canonical_key
from explorer.runtime.interp import Action, OpaqueToken, StepResult, Unsupported, clock_state, world_key
from explorer.analysis.predicates import VarInfo

FUEL_CAP = 4_096          # tick 하나에서 실행할 수 있는 명령 수 상한


# ── 시간 단위 ────────────────────────────────────────────────────────────────

_UNIT = {"MS": 0.001, "MSEC": 0.001, "SEC": 1, "MIN": 60, "HOUR": 3600,
         "DAY": 86400}


def parse_duration(v: Any) -> Fraction:
    """'30 SEC' / '5 MIN' / 숫자(초) → 초."""
    from decimal import Decimal, InvalidOperation
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        amount, scale = str(v), 1
    else:
        m = re.fullmatch(r"\s*([\d.]+)\s*([A-Za-z]+)\s*", str(v))
        if not m or m.group(2).upper() not in _UNIT:
            raise Unsupported(f"duration format: {v!r}")
        amount, scale = m.group(1), _UNIT[m.group(2).upper()]
    try:
        milliseconds = Decimal(amount) * Decimal(str(scale)) * 1000
    except InvalidOperation:
        raise Unsupported(f"duration format: {v!r}")
    if not milliseconds.is_finite() or milliseconds < 0 or milliseconds != milliseconds.to_integral_value():
        raise Unsupported(f"duration must be a nonnegative whole number of milliseconds: {v!r}")
    return Fraction(int(milliseconds), 1000)


# ── 조건식: 작은 파서 (튜플 AST) ─────────────────────────────────────────────
# expr := or; or := and ('or' and)*; and := cmp ('and' cmp)*
# cmp := add (CMP add)?; add := mul (('+'|'-') mul)*; mul := unary (('*'|'/') u)*
# unary := 'not' u | '-' u | atom
# atom := NUM | STR | true/false/null | abs(expr) | $var | Name.Name | (expr)

_TOKEN = re.compile(r"\s*(>=|<=|==|!=|>|<|\(|\)|,|\+|-|\*|/|%|"
                    r"\$\w+(?:\.\w+)*|\"[^\"]*\"|'[^']*'|[\d.]+|\w+(?:\.\w+)*)")
_CMP = (">=", "<=", "==", "!=", ">", "<")


def _tokens(src: str) -> list[str]:
    out, i = [], 0
    while i < len(src):
        m = _TOKEN.match(src, i)
        if not m:
            if src[i:].strip():
                raise Unsupported(f"cond tokenize: {src[i:]!r}")
            break
        out.append(m.group(1))
        i = m.end()
    return out


_QREF = re.compile(r"(?:all|any)\(\s*(#\w+(?:\s+#\w+)*)\s*\)\.(\w+)")


def parse_cond(src: str, to_key) -> tuple:
    # JoI식 한정 읽기 all(#A #B).Attr → 자리표(__qN)로 바꿔 파싱 후 read로 치환.
    # 한정 비교는 grounding 전엔 그대로의 비교로 평가 (interp와 동일, 1대 세계 정확)
    qmap: dict[str, tuple[str, str]] = {}

    def _q(m: re.Match) -> str:
        tags = tuple(t[1:] for t in m.group(1).split())
        ph = f"__q{len(qmap)}"
        qmap[ph] = (world_key(tags, tags[-1], m.group(2)),
                    f"{'+'.join(tags)}.{m.group(2)}")
        return "$" + ph

    # Quoted text is data, including text that happens to resemble a selector.
    src = "".join(part if part.startswith(("'", '"')) else _QREF.sub(_q, part)
                  for part in re.split(r'''("[^"\\]*(?:\\.[^"\\]*)*"|'[^'\\]*(?:\\.[^'\\]*)*')''', src))
    toks = _tokens(src)
    pos = [0]

    def peek() -> str | None:
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take() -> str:
        if peek() is None:
            raise Unsupported("condition ends before expression is complete")
        pos[0] += 1
        return toks[pos[0] - 1]

    def expect(token):
        if take() != token:
            raise Unsupported(f"condition expected {token!r}")

    def atom() -> tuple:
        t = take()
        if t == "(":
            e = expr_or()
            expect(")")
            return e
        if t == "abs":
            expect("(")
            e = expr_or()
            expect(")")
            return ("abs", e)
        if t in ("all", "any") and peek() == "(":
            take()                  # 한정 비교 = 그대로의 비교 (grounding 전)
            e = expr_or()
            expect(")")
            return e
        if t in ("min", "max") and peek() == "(":
            take()
            a = expr_or()
            expect(",")
            b = expr_or()
            expect(")")
            return (t, a, b)
        if t.startswith("$"):
            nm = t[1:]
            if "." in nm:               # $Service.Attr = 센서 읽기
                return ("read", to_key(nm), nm)
            return ("var", nm)
        if t.startswith(("'", '"')):
            if "\\" in t[1:-1]:
                raise Unsupported("escaped string literals need a specified decoding rule")
            return ("lit", t[1:-1])
        if re.fullmatch(r"[\d.]+", t):
            return ("lit", float(t) if "." in t else int(t))
        if t in ("true", "false"):
            return ("lit", t == "true")
        if t == "null":
            return ("lit", None)
        if "." in t:
            return ("read", to_key(t), t)
        if not re.fullmatch(r"[A-Za-z_]\w*", t) or t in ("and", "or", "not"):
            raise Unsupported(f"condition expected value, got {t!r}")
        return ("var", t)      # 점 없는 이름 = 변수 (read/call/카운터)

    def unary() -> tuple:
        if peek() == "-":
            take()
            operand = unary()
            if operand[0] == "lit" and type(operand[1]) in (int, float):
                return ("lit", -operand[1])
            return ("bin", "-", ("lit", 0), operand)
        return atom()

    def level(ops, nxt):
        def rule() -> tuple:
            e = nxt()
            while peek() in ops:
                e = ("bin", take(), e, nxt())
            return e
        return rule

    expr_mul = level(("*", "/", "%"), unary)
    expr_add = level(("+", "-"), expr_mul)

    def expr_cmp() -> tuple:
        e = expr_add()
        if peek() in _CMP:
            return ("bin", take(), e, expr_add())
        return e

    def expr_not():
        if peek() == "not":
            take()
            return ("not", expr_not())
        return expr_cmp()

    expr_and = level(("and",), expr_not)
    expr_or = level(("or",), expr_and)
    e = expr_or()
    if pos[0] != len(toks):
        raise Unsupported(f"cond trailing: {toks[pos[0]:]!r}")

    if qmap:                        # 자리표 → 한정 읽기 노드로 되돌림
        def sub(n):
            if not isinstance(n, tuple):
                return n
            if n[0] == "var" and n[1] in qmap:
                k, disp = qmap[n[1]]
                return ("read", k, disp)
            return n[:1] + tuple(sub(c) for c in n[1:])
        e = sub(e)
    return e


def eval_cond(n: tuple, vars_: dict, inputs: dict) -> Any:
    from explorer.verification.symbolic_values import resolve_input
    from explorer.runtime.integer_text import value_text
    k = n[0]
    if k == "lit":
        return n[1]
    if k == "var":
        return vars_.get(n[1])
    if k == "read":
        return resolve_input(inputs.get(n[1]))
    if k == "abs":
        v = eval_cond(n[1], vars_, inputs)
        return None if v is None else abs(v)
    if k in ("min", "max"):
        a = eval_cond(n[1], vars_, inputs)
        b = eval_cond(n[2], vars_, inputs)
        if a is None or b is None:
            return None
        return min(a, b) if k == "min" else max(a, b)
    if k == "not":
        return not eval_cond(n[1], vars_, inputs)
    op, l, r = n[1], eval_cond(n[2], vars_, inputs), eval_cond(n[3], vars_, inputs)
    if op == "and":
        return bool(l) and bool(r)
    if op == "or":
        return bool(l) or bool(r)
    if op == "==":
        return l == r
    if op == "!=":
        return l != r
    if op in _CMP:
        if l is None or r is None:
            return False
        try:
            return {">": l > r, ">=": l >= r,
                    "<": l < r, "<=": l <= r}[op]
        except TypeError:
            return False
    # 산술의 None 처리: expr.py의 '+' 규칙과 동일 — 문자열이 끼면 str 강제
    # (None→""), 숫자면 None→0, 0으로 나누기는 0
    if op == "+":
        from explorer.verification.symbolic_values import SymbolicValue, symbolic_add
        if isinstance(l, SymbolicValue) or isinstance(r, SymbolicValue):
            return symbolic_add(l, r)
        if isinstance(l, str) or isinstance(r, str):
            return ("" if l is None else value_text(l)) + ("" if r is None else value_text(r))
    if l is None:
        l = 0
    if r is None:
        r = 0
    try:
        # Evaluate only the selected operator. Eager dict values execute '%'
        # even for '+', which is neither required nor valid for symbolic terms.
        if op == "+": return l + r
        if op == "-": return l - r
        if op == "*": return l * r
        if op == "/": return l / r if r != 0 else 0
        if op == "%": return l % r if r != 0 else 0
        raise Unsupported('IR arithmetic operator: ' + op)
    except TypeError:
        return False if op in _CMP else None


# ── 명령(instruction)과 컴파일 ───────────────────────────────────────────────

@dataclass
class Ins:
    kind: str                 # CALL READ IF GOTO WAIT DELAY TOP END_ITER END
    cond: tuple | None = None
    edge: str = "none"
    for_sec: float = 0.0      # WAIT 지속
    to_sec: float = 0.0       # WAIT 제한시간 (0 = 없음)
    succ: int = 0             # WAIT 성공 시 / IF 거짓 시 / GOTO 목적지
    svc: str = ""
    method: str = ""
    tags: tuple = ()
    groups: tuple = ()        # CALL 액션 타깃 그룹 목록 (집합 바인딩 언롤)
    args: tuple = ()          # ('lit', v) | ('var', nm) 목록
    var: str = ""             # READ/CALL 담을 변수
    key: str = ""             # READ 센서 키
    period: float = 0.0       # TOP
    count: int = 0            # TOP (0 = 무제한)
    idx: int = 0              # TOP/END_ITER 쌍 번호
    cname: str = ""           # 반복 카운터 변수 이름 ("" = 안 셈)
    mod: int = 0              # 카운터를 접는 나머지 (modulo 전용 카운터)


_TMPL = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)")


def _tmpl_parts(v: str, to_key) -> list | None:
    """"a is $B.C d" → ["a is ", ("read",key,"B.C"), " d"]. $ 없으면 None."""
    parts: list = []
    last = 0
    for m in _TMPL.finditer(v):
        if m.start() > last:
            parts.append(v[last:m.start()])
        nm = m.group(1)
        parts.append(("read", to_key(nm), nm) if "." in nm else ("var", nm))
        last = m.end()
    if last == 0:
        return None
    if last < len(v):
        parts.append(v[last:])
    return parts


def default_to_key(name: str) -> str:
    svc, attr = name.split(".", 1)
    csvc, cattr = canonical_key(svc, attr)
    return f"{csvc}.{cattr}"


@dataclass
class IrProgram:
    ins: list[Ins]
    vars_info: dict[str, VarInfo]
    axes: Axes
    var_keys: dict[str, str]          # read 변수 → 센서 키 (축 배분용)


def compile_ir(ir: dict, name_map: dict[str, str] | None = None,
               bind: dict[tuple, tuple] | None = None) -> IrProgram:
    """name_map: canonical 'svc.attr' → 월드 키 (방 태그 포함) 덮어쓰기.
    bind: canonical (svc, method) → 셀렉터 태그 튜플 (액션 타깃 바인딩)."""
    to_key = (lambda n: (name_map or {}).get(default_to_key(n))
              or default_to_key(n))
    tl = list(ir["timeline"])
    if not tl or tl[0].get("op") != "start_at":
        raise Unsupported("timeline must open with start_at")
    if tl[0].get("anchor") != "now":
        raise Unsupported("start_at cron: M1 범위 밖 (cron.py 통합 예정)")
    tl = tl[1:]

    ins: list[Ins] = []
    vinfo: dict[str, VarInfo] = {"pc": VarInfo("state", init=0),
                                 "done": VarInfo("state", init=False)}
    var_keys: dict[str, str] = {}
    axis_var_keys: dict[str, set] = {}
    num_consts: dict[str, set] = {}
    str_consts: dict[str, set] = {}
    bool_keys: set[str] = set()
    truthy_keys: set[str] = set()
    ts_thresholds: set[float] = set()
    tod_ops: set = set()
    counter_caps: dict[str, float] = {}
    param_reads: list[str] = []
    n_cycle = [0]
    all_conds: list[tuple] = []           # 카운터 사용 후분석용
    counter_sites: dict[str, list[Ins]] = {}   # 이름 카운터 → TOP/END_ITER

    # (svc,method)별 call op 수 미리 세기 — 바인딩 그룹 배정 규칙에 사용
    call_counts: dict[tuple, int] = {}
    call_seen: dict[tuple, int] = {}

    def _count_calls(n) -> None:
        if isinstance(n, dict):
            if n.get("op") == "call" and "." in (n.get("target") or ""):
                ck = canonical_key(*n["target"].split(".", 1))
                call_counts[ck] = call_counts.get(ck, 0) + 1
            for v_ in n.values():
                _count_calls(v_)
        elif isinstance(n, list):
            for v_ in n:
                _count_calls(v_)
    _count_calls(tl)

    def note_axes(cond: tuple) -> None:
        all_conds.append(cond)
        """비교식의 (op, 상수)를 관련된 모든 센서 키에 배분 (과분할=안전)."""
        def reads_in(n, out):
            if n[0] == "read":
                out.append(n[1])
            elif n[0] == "var":
                out.extend(axis_var_keys.get(n[1], ()))
            elif n[0] in ("abs", "not"):
                reads_in(n[1], out)
            elif n[0] in ("min", "max"):
                reads_in(n[1], out)
                reads_in(n[2], out)
            elif n[0] == "bin":
                reads_in(n[2], out)
                reads_in(n[3], out)

        def walk(n):
            if n[0] in ("abs", "not"):
                walk(n[1])
            elif n[0] in ("min", "max"):
                walk(n[1])
                walk(n[2])
            elif n[0] == "bin" and n[1] in ("and", "or"):
                walk(n[2])
                walk(n[3])
            elif n[0] == "bin" and n[1] in _CMP:
                for side, other in ((n[2], n[3]), (n[3], n[2])):
                    if other[0] != "lit":
                        continue
                    c, op = other[1], n[1]
                    if side is n[3]:  # 상수가 왼쪽이면 부등호 방향 반전
                        op = {">": "<", "<": ">", ">=": "<=", "<=": ">="}.get(op, op)
                    keys: list[str] = []
                    reads_in(side, keys)
                    for kk in keys:
                        if kk == "clock.time":
                            # HHMM 합성 — 자유 입력 축이 아니라 달력 경계
                            # (ir_step이 hour*100+minute로 파생, explore의
                            # tod_ops/_tod_flips가 구간·점프를 담당)
                            if isinstance(c, (int, float)) \
                                    and not isinstance(c, bool):
                                tod_ops.add((op, int(c)))
                            continue
                        if kk.startswith("clock.") and kk != "clock.isholiday":
                            continue
                        if isinstance(c, bool) or c is None:
                            bool_keys.add(kk)
                        elif isinstance(c, str):
                            str_consts.setdefault(kk, set()).add(c)
                        else:
                            num_consts.setdefault(kk, set()).add((op, float(c)))
            elif n[0] in ("read", "var"):
                keys = []
                reads_in(n, keys)
                for key in keys:
                    if not key.startswith("clock.") or key == "clock.isholiday":
                        bool_keys.add(key)
                        truthy_keys.add(key)
        walk(cond)

    def carg(v: Any) -> tuple:
        if isinstance(v, str) and "$" in v:
            try:                # 인자 안 표현식 (min($X.Y+10,100))
                ast = parse_cond(v, to_key)
            except Exception:
                # 값 삽입 템플릿("humidity is $Humidity"): $이름 자리에
                # 읽은 값을 끼워 넣는다 — JoI의 "..." + 변수 이어붙이기와
                # 같은 규칙(str 강제, None→"")으로 평가 (expr.py '+')
                parts = _tmpl_parts(v, to_key)
                if parts is not None:
                    return ("tmpl", parts)
                return ("lit", v)   # $ 없는 문자열 그대로
            note_axes(ast)
            return ("expr", ast)
        return ("lit", v)

    def emit(node: dict, iter_end: int | None, cyc_exit: list[int]) -> None:
        """iter_end: 이번 회차 종료 시 갈 번지(END_ITER 자리 예약 인덱스
        기록용 콜백 대신, 완성 후 패치). cyc_exit: break가 패치할 목록."""
        op = node.get("op")
        if op == "call":
            svc, method = node["target"].split(".", 1)
            csvc, cm = canonical_key(svc, method)
            # 바인딩 값: 태그 그룹 목록. IR op 수(k)와 그룹 수(g)로 배정 —
            # k==g면 등장 순서대로 1:1, k==1<g면 집합 바인딩(op 하나가 그룹
            # 전체로 언롤, §9.4), 그 외엔 첫 그룹.
            # 자리별 명세(값이 list의 list — [자리i][그룹j]=태그 튜플)면
            # i번째 call 자리가 자기 그룹들로 언롤 (게이트가 바인딩 표에서
            # 만들어 넘기는 형식, §9.10).
            raw = (bind or {}).get((csvc, cm))
            i_op = call_seen.get((csvc, cm), 0)
            call_seen[(csvc, cm)] = i_op + 1
            if raw and isinstance(raw[0], list):
                site = raw[i_op] if i_op < len(raw) else raw[-1]
                groups = [tuple(g) for g in site]
            else:
                if raw and not isinstance(raw[0], (list, tuple)):
                    raw = [tuple(raw)]       # 옛 형식(태그 튜플 하나) 허용
                groups = [tuple(g) for g in raw] if raw else [(svc,)]
                k = call_counts.get((csvc, cm), 1)
                if k == len(groups):
                    groups = [groups[i_op]]
                elif k != 1:
                    groups = [groups[0]]
            args = tuple(carg(v) for v in (node.get("args") or {}).values())
            v = node.get("var", "")
            if v and len(groups) != 1:
                raise Unsupported("query result requires exactly one bound device")
            if v:
                vinfo[v] = VarInfo("state")
            query_key = world_key(groups[0], svc, method)
            if v and len(groups[0]) == 1:
                # Parameterized queries and properties share concrete identity.
                tag = groups[0][0]
                if raw or tag.lower() != csvc:
                    query_key = f"{tag}.{cm}"
            if v:
                if all(a[0] == "lit" for a in args):
                    vals = [a[1] for a in args]
                    var_keys[v] = (f"{query_key}"
                                   if not vals else
                                   f"{query_key}({','.join(map(repr, vals))})")
                    axis_var_keys.setdefault(v, set()).add(var_keys[v])
            # key = 질의 답을 찾을 월드 키 (var 있는 호출 = 질의, interp와 동일)
            ins.append(Ins("CALL", svc=csvc, method=cm, tags=groups[0],
                           groups=tuple(groups), args=args, var=v,
                           key=query_key))
        elif op == "read":
            key = to_key(node["src"])
            v = node["var"]
            vinfo[v] = VarInfo("state")
            var_keys[v] = key
            axis_var_keys.setdefault(v, set()).add(key)
            ins.append(Ins("READ", key=key, var=v))
        elif op == "if":
            cond = parse_cond(node["cond"], to_key)
            note_axes(cond)
            i_if = len(ins)
            ins.append(Ins("IF", cond=cond))
            for ch in node.get("then") or []:
                emit(ch, iter_end, cyc_exit)
            if node.get("else"):
                i_goto = len(ins)
                ins.append(Ins("GOTO"))
                ins[i_if].succ = len(ins)
                for ch in node["else"]:
                    emit(ch, iter_end, cyc_exit)
                ins[i_goto].succ = len(ins)
            else:
                ins[i_if].succ = len(ins)
        elif op == "wait":
            cond = parse_cond(node["cond"], to_key)
            note_axes(cond)
            for_sec = parse_duration(node["for"]) if node.get("for") else 0.0
            to_sec = (parse_duration(node["timeout"])
                      if node.get("timeout") else 0.0)
            if for_sec:
                ts_thresholds.add(for_sec)
            if to_sec:
                ts_thresholds.add(to_sec)
            i_w = len(ins)
            edge = node.get("edge") or "none"
            if edge not in ("none", "rising", "falling"):
                raise Unsupported(f"wait edge: {edge}")
            if for_sec and edge != "none":
                raise Unsupported("combined wait edge and sustain semantics are unspecified")
            ins.append(Ins("WAIT", cond=cond, edge=edge,
                           for_sec=for_sec, to_sec=to_sec))
            vinfo[f"p{i_w}"] = VarInfo("state", init=False)
            vinfo[f"s{i_w}"] = VarInfo("state", timestamp=True)
            vinfo[f"t{i_w}"] = VarInfo("state", timestamp=True)
            if node.get("on_timeout"):
                for ch in node["on_timeout"]:
                    emit(ch, iter_end, cyc_exit)
                # 회차 종료 표시(-1): cycle 안이면 END_ITER로, 최상위면
                # END로 컴파일 마지막에 패치된다
                ins.append(Ins("GOTO", succ=-1))
            ins[i_w].succ = len(ins)
        elif op == "delay":
            sec = parse_duration(node["duration"])
            ts_thresholds.add(sec)
            i_d = len(ins)
            ins.append(Ins("DELAY", for_sec=sec))
            vinfo[f"d{i_d}"] = VarInfo("state", timestamp=True)
        elif op == "cycle":
            k = n_cycle[0]
            n_cycle[0] += 1
            period = parse_duration(node["period"]) if node.get("period") else 0.0
            if period:
                ts_thresholds.add(period)
            until = (parse_cond(node["until"], to_key)
                     if node.get("until") else None)
            if until is not None:
                note_axes(until)
            # count가 숫자면 그만큼 반복, 이름이면 "반복 횟수를 그 이름의
            # 변수로 노출" (until이나 조건이 참조; 접는 방식은 후분석)
            raw = node.get("count")
            count, cname = 0, ""
            if isinstance(raw, str) and raw.strip() and not raw.strip().isdigit():
                if not re.fullmatch(r"[A-Za-z_]\w*", raw.strip()):
                    raise Unsupported("cycle count must be a positive integer or counter name")
                cname = raw.strip()
            elif raw:
                if isinstance(raw, bool) or not str(raw).isdigit() or int(raw) <= 0:
                    raise Unsupported("cycle count must be a positive integer or counter name")
                count, cname = int(raw), f"n{k}"
            elif raw is not None and raw != "":
                raise Unsupported("cycle count must be a positive integer or counter name")
            # Re-entering a nested cycle starts a fresh cycle instance. The
            # back edge targets TOP, so ordinary iterations do not reset it.
            ins.append(Ins("ENTER_CYCLE", idx=k, cname=cname))
            i_top = len(ins)
            top = Ins("TOP", cond=until, period=period, count=count, idx=k,
                      cname=cname)
            ins.append(top)
            vinfo[f"c{k}"] = VarInfo("state", timestamp=True)
            if cname:
                vinfo[cname] = VarInfo("state", init=0)
            if count:      # 숫자 count는 포화 상한이 곧 정해짐
                counter_caps[cname] = float(count)
            my_exit: list[int] = []
            i_end = [None]
            for ch in node.get("body") or []:
                emit(ch, None, my_exit)   # iter_end는 아래에서 일괄 패치
            i_end[0] = len(ins)
            end = Ins("END_ITER", succ=i_top, idx=k, count=count, cname=cname)
            ins.append(end)
            if cname and not count:       # 이름 카운터: 접는 방식 후분석 대상
                counter_sites.setdefault(cname, []).extend([top, end])
            ins[i_top].succ = len(ins)    # until/count 충족 시 탈출 번지
            for a in my_exit:
                ins[a].succ = len(ins)
            # 회차 안 GOTO(-1) = 회차 종료 표시 → END_ITER로 패치
            for a in range(i_top, i_end[0]):
                if ins[a].kind == "GOTO" and ins[a].succ == -1:
                    ins[a].succ = i_end[0]
        elif op == "break":
            i_b = len(ins)
            ins.append(Ins("GOTO"))
            if cyc_exit is None:
                raise Unsupported("break outside cycle")
            cyc_exit.append(i_b)
        elif op == "start_at":
            raise Unsupported("start_at must be first")
        else:
            raise Unsupported(f"op: {op}")

    for node in tl:
        emit(node, None, None)
    ins.append(Ins("END"))
    # 최상위 wait timeout의 회차 종료 = 프로그램 종료
    for a, x in enumerate(ins):
        if x.kind == "GOTO" and x.succ == -1:
            x.kind, x.succ = "END", 0

    # Result calls are queries under this model, even if the result is unused.
    # Liveness must never invent/remove an observable ACTION.
    def _names_in(n, out):
        if isinstance(n, tuple):
            if n[0] == "var":
                out.add(n[1])
            else:
                for c in n[1:]:
                    _names_in(c, out)
        elif isinstance(n, list):
            for c in n:
                _names_in(c, out)
    for x in ins:
        if x.kind == "CALL" and x.var \
                and not all(a[0] == "lit" for a in x.args):
            param_reads.append(f"{x.key}(unresolvable args)")

    reserved = {"pc", "done"}
    for index, instruction in enumerate(ins):
        if instruction.kind == "WAIT":
            reserved.update((f"p{index}", f"s{index}", f"t{index}"))
        elif instruction.kind == "DELAY":
            reserved.add(f"d{index}")
        elif instruction.kind == "TOP":
            reserved.add(f"c{instruction.idx}")
    for instruction in ins:
        names = {instruction.var, instruction.cname} - {""}
        _names_in(instruction.cond, names)
        for argument in instruction.args:
            _names_in(argument, names)
        if names & reserved:
            raise Unsupported(f"reserved IR state variables: {sorted(names & reserved)}")

    # 이름 카운터 후분석: 조건에서 어떻게 쓰였는지에 따라 접는 방식 결정.
    # %k만 쓰면 증가할 때 나머지로 접고(라운드로빈), 크기/등호 비교만 쓰면
    # 최대 상수에서 포화. 둘 다 쓰면 아직 못 다룬다. 아무도 안 읽으면
    # 아예 세지 않는다(생값이 상태 키에 들어가 상태가 무한해지는 것 방지).
    def counter_uses(c: str) -> tuple[list, list]:
        mods, caps = [], []

        def walk(n):
            if not isinstance(n, tuple):
                return
            if n[0] == "bin":
                op, l, r = n[1], n[2], n[3]
                if op == "%" and l == ("var", c) and r[0] == "lit":
                    mods.append(int(r[1]))
                if op in _CMP:
                    for a_, b_ in ((l, r), (r, l)):
                        if a_ == ("var", c) and b_[0] == "lit" \
                                and isinstance(b_[1], (int, float)) \
                                and not isinstance(b_[1], bool):
                            caps.append(float(b_[1]))
                walk(l)
                walk(r)
            elif n[0] in ("abs", "not"):
                walk(n[1])
        for cond in all_conds:
            walk(cond)
        return mods, caps

    for c, sites in counter_sites.items():
        # An ACTION/query argument needs the actual count, not its residue or
        # a guard-only saturation. Templates and expression wrappers count too.
        argument_names = set()
        for instruction in ins:
            for argument in instruction.args:
                _names_in(argument, argument_names)
        if c in argument_names:
            continue
        mods, caps = counter_uses(c)
        if mods and caps:
            raise Unsupported(f"counter {c}: %와 크기 비교 혼용")
        if mods:
            from math import gcd
            m = mods[0]
            for x in mods[1:]:
                m = m * x // gcd(m, x)
            for s in sites:
                s.mod = m
        elif caps:
            counter_caps[c] = max(caps)
        else:
            condition_names = set()
            for condition in all_conds:
                _names_in(condition, condition_names)
            if c not in condition_names:
                for s in sites:
                    s.cname = ""

    observable_reads: set[str] = set()
    observable_var_keys: dict[str, set[str]] = {}
    for instruction in ins:
        if instruction.kind == "READ":
            observable_var_keys.setdefault(instruction.var, set()).add(instruction.key)
        elif instruction.kind == "CALL" and instruction.var:
            key = instruction.key
            if instruction.args and all(arg[0] == "lit" for arg in instruction.args):
                key += "(" + ",".join(repr(arg[1]) for arg in instruction.args) + ")"
            observable_var_keys.setdefault(instruction.var, set()).add(key)

    # Branches/repeated assignments can give the same register multiple
    # sources, including definitions emitted after its condition. Revisit
    # guards with their complete conservative source union.
    axis_var_keys = observable_var_keys
    for condition in list(all_conds):
        note_axes(condition)

    def _observable_tuple_reads(node) -> None:
        if isinstance(node, tuple):
            if not node:
                return
            if node[0] == "read":
                if not str(node[1]).startswith("clock.") or node[1] == "clock.isholiday":
                    observable_reads.add(str(node[1]))
                return
            if node[0] == "var":
                observable_reads.update(key for key in observable_var_keys.get(node[1], ())
                                        if not key.startswith("clock.") or key == "clock.isholiday")
                return
            for child in node[1:]:
                _observable_tuple_reads(child)
        elif isinstance(node, list):
            for child in node:
                _observable_tuple_reads(child)

    # Values reaching an executed CALL are part of the observable trace.
    # Keep their external sources as explicit input axes even when no guard
    # happens to compare them.
    for x in ins:
        if x.kind == "CALL" and not x.var:
            for arg in x.args:
                _observable_tuple_reads(arg)

    for key in truthy_keys:
        if key in num_consts:
            num_consts[key].add(("!=", 0.0))
        if key in str_consts:
            str_consts[key].add("")
    cells: dict[str, list] = {}
    from explorer.analysis.explore import reps_from_preds
    for k, oc in num_consts.items():
        cells[k] = reps_from_preds(sorted(oc))
    for k, ss in str_consts.items():
        cells[k] = sorted(ss) + ["__other__"]
    for k in bool_keys:
        cells.setdefault(k, [True, False])
    for k in observable_reads:
        cells.setdefault(k, list(OBSERVABLE_VALUE_DOMAIN))
    axes = Axes(cells, [], False, False, sorted(ts_thresholds),
                counter_caps, param_reads,
                cell_preds={k: sorted(v) for k, v in num_consts.items()},
                tod_ops=sorted(tod_ops), observable_reads=sorted(observable_reads),
                truthy_reads=sorted(truthy_keys))
    from explorer.verification.input_coverage import ir_coverage, install_coverage
    axes = install_coverage(axes, ir_coverage(ins))
    return IrProgram(ins, vinfo, axes, var_keys)


# ── 실행 ─────────────────────────────────────────────────────────────────────

def ir_step(prog: IrProgram, vars_in: dict, gv_in: dict, inputs: dict,
            now_ms: int, first_tick: bool = False) -> StepResult:
    from explorer.verification.symbolic_values import resolve_input
    from explorer.runtime.integer_text import value_text
    vars_ = dict(vars_in)
    now_sec = Fraction(now_ms, 1000)  # exact even after arbitrary time shifts
    actions: list[Action] = []
    if vars_.get("done"):
        return StepResult(vars_, gv_in, actions, True)
    pc = int(vars_.get("pc", 0))
    fuel = FUEL_CAP
    # interp와 같은 세계 구성: clock.*은 now에서 계산(입력이 덮어쓸 수 있음),
    # clock.time은 항상 hour*100+minute 파생 (자유 입력이 아님 — ClockRef와 동일)
    world = dict(clock_state(now_ms))
    world.update(inputs)
    world["clock.time"] = world["clock.hour"] * 100 + world["clock.minute"]

    def argv(a: tuple) -> Any:
        if a[0] == "lit":
            return a[1]
        if a[0] == "var":
            return vars_.get(a[1])
        if a[0] == "tmpl":               # 값 삽입: str 강제, None→"" (expr '+')
            out = []
            for p in a[1]:
                if isinstance(p, str):
                    out.append(p)
                else:
                    val = eval_cond(p, vars_, world)
                    out.append(val)
            from explorer.verification.symbolic_values import text_join
            return text_join(out)
        v = eval_cond(a[1], vars_, world)      # ("expr", ast)
        return v

    while fuel:
        fuel -= 1
        x = prog.ins[pc]
        if x.kind == "END":
            vars_["done"] = True
            break
        if x.kind == "CALL":
            vals = tuple(argv(a) for a in x.args)
            if x.var:
                # 결과를 담는 호출 = 질의 (interp 표현식 위치 호출과 동일):
                # 액션으로 기록하지 않고, 환경 답 → 없으면 출처 토큰
                pkey = f"{x.key}({','.join(map(repr, vals))})"
                if pkey in world:
                    vars_[x.var] = resolve_input(world[pkey])
                elif x.key in world:
                    vars_[x.var] = resolve_input(world[x.key])
                else:
                    vars_[x.var] = OpaqueToken(x.svc, x.tags, x.method, vals)
            else:
                groups = x.groups or (x.tags,)
                for i, g in enumerate(groups):
                    actions.append(Action(x.svc, x.method, vals, g,
                        (i, len(groups)) if len(groups) > 1 else None))
            pc += 1
        elif x.kind == "READ":
            vars_[x.var] = resolve_input(world.get(x.key))
            pc += 1
        elif x.kind == "IF":
            pc = pc + 1 if eval_cond(x.cond, vars_, world) else x.succ
        elif x.kind == "GOTO":
            pc = x.succ
        elif x.kind == "DELAY":
            reg = f"d{pc}"
            if vars_.get(reg) is None:
                vars_[reg] = now_sec
            if now_ms - round(vars_[reg] * 1000) >= round(x.for_sec * 1000):
                vars_.pop(reg, None)
                pc += 1
            else:
                break                      # 이번 tick은 여기까지
        elif x.kind == "WAIT":
            ok = eval_cond(x.cond, vars_, world)
            fired = False
            if x.for_sec:                  # 지속: 끊기지 않고 for 이상
                reg = f"s{pc}"
                if ok:
                    if vars_.get(reg) is None:
                        vars_[reg] = now_sec
                    fired = now_ms - round(vars_[reg] * 1000) >= round(x.for_sec * 1000)
                else:
                    vars_.pop(reg, None)
            elif x.edge == "rising":
                fired = bool(ok) and not vars_.get(f"p{pc}", False)
                vars_[f"p{pc}"] = bool(ok)
            elif x.edge == "falling":
                fired = (not ok) and vars_.get(f"p{pc}", True)
                vars_[f"p{pc}"] = bool(ok)
            else:
                fired = bool(ok)
            if fired:
                vars_.pop(f"s{pc}", None)
                vars_.pop(f"t{pc}", None)
                pc = x.succ
                continue
            if x.to_sec:                   # 제한시간
                reg = f"t{pc}"
                if vars_.get(reg) is None:
                    vars_[reg] = now_sec
                if now_ms - round(vars_[reg] * 1000) >= round(x.to_sec * 1000):
                    vars_.pop(f"s{pc}", None)
                    vars_.pop(f"t{pc}", None)
                    pc += 1                # on_timeout 블록으로
                    continue
            break
        elif x.kind == "ENTER_CYCLE":
            vars_.pop(f"c{x.idx}", None)
            if x.cname:
                vars_[x.cname] = 0
                from explorer.verification.relational_values import record
                record('initialize', x.cname, 0)
            pc += 1
        elif x.kind == "TOP":
            if x.cname and x.cname not in vars_:
                vars_[x.cname] = 0        # 조건이 첫 회차부터 읽을 수 있게
            if x.count and vars_.get(x.cname, 0) >= x.count:
                vars_.pop(f"c{x.idx}", None)
                pc = x.succ
                continue
            reg = f"c{x.idx}"
            completed = vars_.get(reg)
            if completed is None or now_ms - round(completed * 1000) >= round(x.period * 1000):
                vars_.pop(reg, None)
                pc = (x.succ if x.cond is not None and eval_cond(x.cond, vars_, world)
                      else pc + 1)
            else:
                break
        elif x.kind == "END_ITER":
            if x.cname:
                v = vars_.get(x.cname, 0) + 1
                if x.mod:
                    v %= x.mod
                vars_[x.cname] = v
                from explorer.verification.relational_values import record
                record('increment', x.cname, v)
            # D4: the period starts at completion, including blocking time.
            vars_[f"c{x.idx}"] = now_sec
            pc = x.succ
        else:
            raise Unsupported(f"ins: {x.kind}")
    if not fuel:
        raise Unsupported("IR step fuel exhausted (내부 무한 반복?)")
    vars_["pc"] = pc
    return StepResult(vars_, gv_in, actions, bool(vars_.get("done")))


# ── Runner 계약 (runner.py 참조) ─────────────────────────────────────────────

class IrRunner:
    def __init__(self, ir: dict | str,
                 name_map: dict[str, str] | None = None,
                 bind: dict[tuple, tuple] | None = None) -> None:
        if isinstance(ir, str):
            ir = json.loads(ir)
        self.prog = compile_ir(ir, name_map, bind)
        self.vars_info = self.prog.vars_info
        self.axes = self.prog.axes

    def check_finite(self, axes: Axes | None = None) -> list[str]:
        # Observable/raw counters are preserved; feature eligibility and the
        # selected search's closure check decide whether they can be certified.
        return []

    def step(self, vars_: dict, gv: dict, inputs: dict, now_ms: int,
             first_tick: bool = False) -> StepResult:
        return ir_step(self.prog, vars_, gv, inputs, now_ms, first_tick)

    def next_wakeup_ms(self, vars_, now_ms, input_step_ms):
        if vars_.get("done"):
            return None
        pc = int(vars_.get("pc", 0))
        ins = self.prog.ins[pc]
        if ins.kind == "DELAY" and vars_.get(f"d{pc}") is not None:
            return round(vars_[f"d{pc}"] * 1000) + round(ins.for_sec * 1000)
        if ins.kind == "TOP" and vars_.get(f"c{ins.idx}") is not None:
            return round(vars_[f"c{ins.idx}"] * 1000) + round(ins.period * 1000)
        if ins.kind == "WAIT":
            candidates = [now_ms + input_step_ms]
            for reg, duration in ((f"s{pc}", ins.for_sec), (f"t{pc}", ins.to_sec)):
                if duration and vars_.get(reg) is not None:
                    deadline = round(vars_[reg] * 1000) + round(duration * 1000)
                    if deadline > now_ms:
                        candidates.append(deadline)
            return min(candidates)
        return now_ms + input_step_ms


# ── 자체 점검: 손 tick 6패턴 + 나란히 비교 8건 ──────────────────────────────
# Run:  python -m explorer.runtime.ir_step

def _tick_run(runner: IrRunner, schedule) -> list:
    from explorer.runtime.interp import clock_state
    t0 = (28 * 24) * 3_600_000
    vars_, gv, log = {}, {}, []
    for i, (sec, world) in enumerate(schedule):
        now = t0 + sec * 1000
        inputs = dict(world)
        inputs.update(clock_state(now))
        r = runner.step(vars_, gv, inputs, now, first_tick=(i == 0))
        vars_, gv = r.vars, r.gv
        for a in r.actions:
            log.append(sec)
    return log


IR_EDGE = {"timeline": [{"op": "start_at", "anchor": "now"},
    {"op": "cycle", "period": "1 MIN", "until": None, "body": [
        {"op": "wait", "cond": "TemperatureSensor.Temperature > 25",
         "edge": "rising"},
        {"op": "call", "target": "AirConditioner.On", "args": {}}]}]}

IR_SUSTAIN = {"timeline": [{"op": "start_at", "anchor": "now"},
    {"op": "wait", "cond": "MotionSensor.Motion == false", "edge": "none",
     "for": "30 SEC"},
    {"op": "call", "target": "Switch.Off", "args": {}}]}

IR_COUNT = {"timeline": [{"op": "start_at", "anchor": "now"},
    {"op": "cycle", "period": "30 SEC", "count": 3, "until": None, "body": [
        {"op": "call", "target": "Speaker.Speak", "args": {"Text": "hi"}}]}]}

IR_TIMEOUT = {"timeline": [{"op": "start_at", "anchor": "now"},
    {"op": "wait", "cond": 'Door.Contact == "open"', "edge": "rising"},
    {"op": "wait", "cond": 'Door.Contact == "closed"', "timeout": "5 MIN",
     "on_timeout": [{"op": "call", "target": "Speaker.Speak",
                     "args": {"Text": "door!"}}]}]}


def main() -> None:
    from explorer.verification.product import product_runners
    from explorer.runtime.runner import JoiRunner

    # 1) 손 tick: 즉시 / 지속 / 엣지 / delay / 횟수 / 제한시간
    ir1 = {"timeline": [{"op": "start_at", "anchor": "now"},
        {"op": "call", "target": "Dishwasher.SetDishwasherMode",
         "args": {"Mode": "dry"}}]}
    assert _tick_run(IrRunner(ir1), [(0, {}), (60, {})]) == [0]

    m = "motionsensor.motion"
    assert _tick_run(IrRunner(IR_SUSTAIN),
                     [(0, {m: True}), (10, {m: False}), (20, {m: False}),
                      (40, {m: False}), (50, {m: False})]) == [40]

    t = "temperaturesensor.temperature"
    assert _tick_run(IrRunner(IR_EDGE),
                     [(0, {t: 20}), (60, {t: 26}), (120, {t: 27}),
                      (180, {t: 20}), (240, {t: 30}), (300, {t: 30})]) \
        == [60, 240]

    ir4 = {"timeline": [{"op": "start_at", "anchor": "now"},
        {"op": "wait", "cond": 'Door.DoorState == "open"', "edge": "rising"},
        {"op": "delay", "duration": "5 MIN"},
        {"op": "call", "target": "Light.On", "args": {}}]}
    d = "door.doorstate"
    assert _tick_run(IrRunner(ir4),
                     [(0, {d: "closed"}), (60, {d: "open"}), (120, {d: "open"}),
                      (300, {d: "closed"}), (360, {d: "closed"}),
                      (420, {d: "closed"})]) == [360]

    assert _tick_run(IrRunner(IR_COUNT),
                     [(s, {}) for s in range(0, 180, 30)]) == [0, 30, 60]

    c = "door.contact"
    late = [(0, {c: "closed"}), (60, {c: "open"}), (200, {c: "open"}),
            (361, {c: "open"}), (420, {c: "open"})]
    fast = [(0, {c: "closed"}), (60, {c: "open"}), (120, {c: "closed"}),
            (500, {c: "closed"})]
    assert _tick_run(IrRunner(IR_TIMEOUT), late) == [361]
    assert _tick_run(IrRunner(IR_TIMEOUT), fast) == []
    print("손 tick 6패턴: OK")

    # 2) 나란히 비교: 자기동치 + 올바른/틀린 JoI 관용구
    joi_flag = """
armed := false
t = (#TemperatureSensor).temperature
if (t > 25 and armed == false) {
  (#AirConditioner).on()
  armed = true
}
if (not (t > 25)) { armed = false }
"""
    joi_level = """
t = (#TemperatureSensor).temperature
if (t > 25) { (#AirConditioner).on() }
"""
    joi_sustain = """
since := 0
fired := false
m = (#MotionSensor).motion
now = (#Clock).clock_timestamp
if (fired == false) {
  if (m == false) {
    if (since == 0) { since = now }
    if (since > 0 and now - since >= 30) {
      (#Switch).off()
      fired = true
    }
  }
  if (m != false) { since = 0 }
}
"""
    joi_count = """
n := 0
if (n < 3) {
  (#Speaker).speak("hi")
  n = n + 1
}
"""
    joi_timeout = """
phase := 0
opened_at := 0
c = (#Door).contact
now = (#Clock).clock_timestamp
if (phase == 0 and c == "open") {
  phase = 1
  opened_at = now
}
if (phase == 1) {
  if (c == "closed") { phase = 2 }
  if (phase == 1 and now - opened_at >= 300) {
    (#Speaker).speak("door!")
    phase = 2
  }
}
"""
    checks = [
        ("엣지 IR×IR", IR_EDGE, IrRunner(IR_EDGE), 60000, "EQUIV"),
        ("엣지 IR×깃발", IR_EDGE, JoiRunner.from_src(joi_flag), 60000, "EQUIV"),
        ("엣지 IR×레벨(오류)", IR_EDGE, JoiRunner.from_src(joi_level), 60000,
         "DIVERGE"),
        ("지속 IR×계수", IR_SUSTAIN, JoiRunner.from_src(joi_sustain), 10000,
         "EQUIV"),
        ("지속 IR×한tick늦음(오류)", IR_SUSTAIN,
         JoiRunner.from_src(joi_sustain.replace("now - since >= 30",
                                                "now - since > 30")),
         10000, "DIVERGE"),
        ("횟수 IR×JoI", IR_COUNT, JoiRunner.from_src(joi_count), 30000,
         "EQUIV"),
        ("횟수 IR×4회(오류)", IR_COUNT,
         JoiRunner.from_src(joi_count.replace("n < 3", "n <= 3")), 30000,
         "DIVERGE"),
        ("제한시간 IR×JoI", IR_TIMEOUT, JoiRunner.from_src(joi_timeout), 60000,
         "EQUIV"),
    ]
    for name, ir, other, period, want in checks:
        r = product_runners(IrRunner(ir), other, period)
        mark = "OK" if r.verdict == want else "**실패**"
        print(f"  {name:26s} {r.verdict:8s} 상태={r.n_states:<4d} "
              f"{'닫힘' if r.closed else '미완'}  [{want} 기대: {mark}]")
        assert r.verdict == want, name
    print("나란히 비교 8건: OK")


if __name__ == "__main__":
    main()
