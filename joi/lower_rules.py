# -*- coding: utf-8 -*-
"""IR → JoI 코드를 규칙으로 만든다 (v1: 원샷 전사).

지원 모양: start_at(now·cron) + read/call/delay/if(then·else)/wait(edge 없음)
+ 맨 앞 wait(for: 지속) 행 (held 카운터 + break, period 100)
+ 마지막 cycle 행 (wrapper period + 시작 래치 + until break + count 카운터).

LLM 없이 IR 의 각 줄을 정해진 모양으로 베껴 적는다. 지원 밖 모양이 나오면
CantLower 를 던진다 — 억지로 만들지 않는다(fail-closed).
셀렉터 문자열은 파이프라인(build_selectors)이 만든 것을 그대로 쓴다.
수량·셀렉터가 맞는지는 여기 소관이 아니다(따로 잰다) — 여기 소관은 로직:
op 의 종류·순서·인자를 IR 그대로 옮기는 것.
"""
from __future__ import annotations

import re

from pipeline_helpers import _post_process_joi_any_quantifiers


class CantLower(Exception):
    """이 IR 모양은 아직 규칙으로 못 만든다."""


_REF = re.compile(r"\$([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)?)")
_ATOM = re.compile(r"\$?([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)")
_QUOTE = re.compile(r'"[^"]*"|\'[^\']*\'')
# min(식, 수)/max(식, 수) 인자 → JoI 에 min/max 가 없어서 보조 변수 + 클램프로 푼다
_MINMAX = re.compile(r"^\s*(min|max)\(\s*(.+?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)\s*$")
# abs(A - B) 비교 → JoI 에 abs 가 없어서 두 방향 비교로 푼다 (정답 관용구)
_ABS = re.compile(r"abs\(\s*(.+?)\s*-\s*(.+?)\s*\)\s*(>=|<=|==|!=|>|<)\s*(\S+)")
# 참조를 걷어낸 뒤 이 글자만 남으면 산수식이다 (예: "$Television.Channel - 1")
_MATHY = re.compile(r"^[\s0-9+\-*/%().]*$")


_UNIT_MS = {"MS": 1, "MSEC": 1, "SEC": 1000, "MIN": 60000, "HOUR": 3600000}


def dur_ms(text: str) -> int:
    """"30 SEC" 같은 시간 문구 → ms."""
    m = re.fullmatch(r"\s*(\d+)\s*(MSEC|MS|SEC|MIN|HOUR)S?\s*", str(text or ""))
    if not m:
        raise CantLower(f"시간 문구 모양: {text!r}")
    return int(m.group(1)) * _UNIT_MS[m.group(2)]


def token(cat: str, name: str) -> str:
    """Television.SetChannel → television_setChannel (JoI 이름 규칙)."""
    return f"{cat[0].lower()}{cat[1:]}_{name[0].lower()}{name[1:]}"


def _sel(selection: dict, key: str) -> str:
    """서비스의 셀렉터 문자열. 자리별 셀렉터(slots)가 있으면 등장 순서대로 하나씩 꺼내 쓴다.
    없거나 여러 조각이면 아직 지원 밖."""
    queue = (selection.get("_slot_queue") or {}).get(key)
    if queue:
        return queue.pop(0)
    parts = (selection.get("selectors") or {}).get(key) or []
    if len(parts) != 1:
        raise CantLower(f"셀렉터가 1개가 아님: {key} → {parts}")
    return parts[0]


def _ref_code(ref: str, selection: dict) -> str:
    """$참조 하나 → JoI 조각. Svc.Attr 는 기기 읽기, 맨이름은 변수."""
    if "." in ref:
        cat, attr = ref.split(".", 1)
        return f"{_sel(selection, ref)}.{token(cat, attr)}"
    return ref


def _arg_code(v, selection: dict) -> str:
    """call 인자 값 하나 → JoI 조각.

    숫자는 그대로, 참조 없는 글은 따옴표, 참조가 든 산수식은 식 그대로,
    참조가 든 글은 조각을 " + " 로 잇는다 (정답 관용구와 동일)."""
    if isinstance(v, bool):
        raise CantLower(f"참/거짓 인자: {v!r}")
    if isinstance(v, (int, float)):
        # 5.0 은 5 로 — 정답 코드와 게이트 행동 비교가 글자 기반이라 소수점을 남기지 않는다
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    if not isinstance(v, str):
        raise CantLower(f"모르는 인자 형: {v!r}")
    refs = list(_REF.finditer(v))
    if not refs:
        return '"' + v + '"'
    if _MATHY.match(_REF.sub("", v)):
        return _REF.sub(lambda m: _ref_code(m.group(1), selection), v)
    parts, last = [], 0
    for m in refs:
        if m.start() > last:
            parts.append('"' + v[last:m.start()] + '"')
        parts.append(_ref_code(m.group(1), selection))
        last = m.end()
    if last < len(v):
        parts.append('"' + v[last:] + '"')
    return " + ".join(parts)


def _cond_code(src: str, selection: dict) -> str:
    """if/wait 의 조건식 → JoI 조각.

    따옴표 안은 손대지 않고, 밖에서 Svc.Attr 를 기기 읽기로, $var 를 변수로
    바꾼다. and/or/비교/숫자는 그대로 베낀다."""
    out, last = [], 0
    for q in _QUOTE.finditer(src):
        out.append(_cond_atoms(src[last:q.start()], selection))
        out.append(q.group(0))
        last = q.end()
    out.append(_cond_atoms(src[last:], selection))
    code = "".join(out)
    code = _ABS.sub(lambda m: f"({m.group(1)} - {m.group(2)} {m.group(3)} {m.group(4)}"
                              f" or {m.group(2)} - {m.group(1)} {m.group(3)} {m.group(4)})",
                    code)
    return code


def _cond_atoms(chunk: str, selection: dict) -> str:
    chunk = _ATOM.sub(lambda m: (f"{_sel(selection, m.group(1) + '.' + m.group(2))}"
                                 f".{token(m.group(1), m.group(2))}")
                      if (m.group(1) + "." + m.group(2)) in (selection.get("selectors") or {})
                      else m.group(0), chunk)
    return re.sub(r"\$([A-Za-z][A-Za-z0-9_]*)", r"\1", chunk)


def lower_ir(ir: dict, selection: dict) -> dict:
    """정답 IR + 기기 고르기 결과 → JoI 블록 {"name","cron","period","script"}."""
    # 자리별 셀렉터는 IR 을 걷는 순서(게이트와 같은 순서)대로 소비한다
    selection = {**selection, "_slot_queue": {k: list(v) for k, v in (selection.get("slots") or {}).items()}}
    tl = list(ir.get("timeline") or [])
    if not tl or tl[0].get("op") != "start_at":
        raise CantLower("첫 줄이 start_at 이 아님")
    anchor = tl[0].get("anchor")
    cron = ""
    if anchor == "cron":
        cron = (tl[0].get("cron") or "").strip()   # 크론 문구는 자구 그대로
        if not cron:
            raise CantLower("cron 앵커인데 크론 문구가 없음")
    elif anchor != "now":
        raise CantLower(f"앵커 지원 밖: {anchor!r}")

    period = 0
    body = tl[1:]
    first = body[0] if body else {}
    cyc_at = [i for i, st in enumerate(body) if st.get("op") == "cycle"]
    if cyc_at:
        # cycle 은 wrapper 의 되풀이로 편다: body 가 곧 script, period 가 주기.
        # 코퍼스 전 행에서 cycle 은 항상 하나뿐이고 마지막 op 이다.
        i = cyc_at[0]
        if len(cyc_at) > 1 or i != len(body) - 1:
            raise CantLower("cycle 이 하나·마지막이 아님")
        cyc = body[i]
        period = dur_ms(cyc.get("period"))
        lines = []
        if body[:i]:
            # cycle 앞의 한 번짜리 준비(대기·호출)는 시작 래치로 한 번만 돌린다
            lines += ["started := false", "if (started == false) {"]
            lines += _stmts(body[:i], selection, 1)
            lines += ["    started = true", "}"]
        until = cyc.get("until")
        if isinstance(until, str) and until.strip():
            lines += [f"if ({_cond_code(until, selection)}) {{", "    break", "}"]
        n = cyc.get("count")
        if n:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(n)):
                raise CantLower(f"count 이름 모양: {n!r}")
            lines.append(f"{n} := 0")
        cbody = cyc.get("body") or []
        if cbody and cbody[0].get("op") == "wait" \
                and cbody[0].get("edge") == "rising":
            # 눌리는 "순간"(rising)은 triggered 래치로 — 유지되는 동안 한 번만
            w = cbody[0]
            if w.get("for") or w.get("timeout"):
                raise CantLower(f"rising 에 for/timeout 이 같이 옴: {w!r}")
            cond = _cond_code(w.get("cond") or "", selection)
            # 회차 카운터는 "한 회차가 끝날 때" 오른다 — rising 몸통은 눌린 순간에만
            # 한 회차가 끝나니 카운터도 그 안에서 올린다(틱마다 올리면 틱을 세게 됨.
            # 게이트 % 접기 뒤 C14#3 반례로 확정).
            lines += ["triggered := false",
                      f"if ({cond}) {{",
                      "    if (triggered == false) {",
                      *_stmts(cbody[1:], selection, 2),
                      *([f"        {n} = {n} + 1"] if n else []),
                      "        triggered = true",
                      "    }",
                      "} else {",
                      "    triggered = false",
                      "}"]
        else:
            lines += _stmts(cbody, selection, 0)
            if n:
                lines.append(f"{n} = {n} + 1")
    elif first.get("op") == "wait" and first.get("for"):
        # 지속 조건: JoI 에 "N 초 이상 유지"가 없어서 100ms 마다 재는
        # held(유지 시간)/fired(이미 발화했나) 관용구로 푼다. 정답 코드와 동일.
        if first.get("edge") not in (None, "none") or first.get("timeout"):
            raise CantLower(f"wait(for) 에 edge/timeout 이 같이 옴: {first!r}")
        cond = _cond_code(first.get("cond") or "", selection)
        ms = dur_ms(first["for"])
        rest = _stmts(body[1:], selection, 1)
        # 두 군데가 게이트 반례로 확정된 요점이다:
        # ① 문턱은 > (>= 는 held 가 관찰 "후" 더해져 한 tick(100ms) 일찍 발화)
        # ② 발화 뒤 break (없으면 조건이 끊겼다 다시 차면 재발화 — IR 은 원샷)
        lines = ["held := 0",
                 f"if ({cond}) {{",
                 "    held = held + 100",
                 "} else {",
                 "    held = 0",
                 "}",
                 f"if (held > {ms}) {{",
                 *rest,
                 "    break",
                 "}"]
        period = 100
    else:
        lines = _stmts(body, selection, 0)
    # 마지막 줄이 call 결과 대입인데 뒤에서 아무도 안 쓰면(죽은 대입) 대입만 뗀다
    # — 실행기는 대입 꼴의 call 을 액션으로 안 치기 때문에 있으면 동작이 사라진다.
    if lines and not lines[-1].startswith(" "):
        m = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]* = (\S.*\))", lines[-1])
        if m:
            lines[-1] = m.group(1)
    script = "\n".join(lines)
    # 조건 자리의 any(#X) 비교는 JoI 관용구 all(#X) op| 로 (파이프라인 후처리와 동일)
    script = _post_process_joi_any_quantifiers(script)
    return {"name": "", "cron": cron, "period": period, "script": script}


def _stmts(steps: list, selection: dict, depth: int) -> list[str]:
    pad = "    " * depth
    lines: list[str] = []
    for s in steps or []:
        op = s.get("op")
        if op == "read":
            cat, _, attr = (s.get("src") or "").partition(".")
            if not attr:
                raise CantLower(f"read src 모양: {s.get('src')!r}")
            lines.append(f"{pad}{s['var']} = {_sel(selection, s['src'])}.{token(cat, attr)}")
        elif op == "call":
            cat, _, method = (s.get("target") or "").partition(".")
            if not method:
                raise CantLower(f"call target 모양: {s.get('target')!r}")
            vals = []
            for name, v in (s.get("args") or {}).items():
                m = _MINMAX.match(v) if isinstance(v, str) else None
                if m:
                    # min/max 는 보조 변수 + 클램프 if 로 편다 (정답 관용구)
                    hv = name[0].lower() + name[1:]
                    bound = m.group(3)
                    if bound.endswith(".0"):
                        bound = bound[:-2]
                    cmp_ = ">" if m.group(1) == "min" else "<"
                    lines += [f"{pad}{hv} = {_arg_code(m.group(2), selection)}",
                              f"{pad}if ({hv} {cmp_} {bound}) {{",
                              f"{pad}    {hv} = {bound}",
                              f"{pad}}}"]
                    vals.append(hv)
                else:
                    vals.append(_arg_code(v, selection))
            code = f"{_sel(selection, s['target'])}.{token(cat, method)}({', '.join(vals)})"
            var = s.get("var")
            cats = {k.split(".", 1)[0] for k in (selection.get("selectors") or {})}
            if var and "." not in var and var not in cats:
                # 결과를 담는 자리 — 단 서비스 이름(예: "Light")은 담는 게 아니다
                code = f"{var} = {code}"
            lines.append(pad + code)
        elif op == "delay":
            dur = s.get("duration")
            if not isinstance(dur, str) or not dur.strip():
                raise CantLower(f"delay duration 모양: {dur!r}")
            lines.append(f"{pad}delay({dur})")
        elif op == "if":
            cond = _cond_code(s.get("cond") or "", selection)
            lines.append(f"{pad}if ({cond}) {{")
            lines += _stmts(s.get("then") or [], selection, depth + 1)
            if s.get("else"):
                lines.append(f"{pad}}} else {{")
                lines += _stmts(s["else"], selection, depth + 1)
            lines.append(f"{pad}}}")
        elif op == "break":
            lines.append(pad + "break")
        elif op == "wait":
            if s.get("edge") not in (None, "none") or s.get("for") or s.get("timeout"):
                raise CantLower(f"wait 모양 지원 밖: edge={s.get('edge')!r} "
                                f"for={s.get('for')!r} timeout={s.get('timeout')!r}")
            cond = _cond_code(s.get("cond") or "", selection)
            lines.append(f"{pad}wait until ({cond})")
        else:
            raise CantLower(f"op 지원 밖: {op}")
    return lines
