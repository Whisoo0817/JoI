"""참조 lowering — (IR, 바인딩 표, 인벤토리) → HA 문서. 규칙 기반, LLM 불사용.

행 종류 → 산출물 (ha/README.md):
  원샷(cycle 없음, anchor now)        → script (sequence)
  cycle 앞에 다른 op가 있는 행        → script (전주 + repeat 반복)
  cycle 단독 (anchor now)             → automation
      몸통이 wait-엣지로 시작 → 그 조건이 trigger (엣지가 HA primitive)
      아니면 → time_pattern trigger(/period) + 몸통
  anchor cron                          → automation (time/time_pattern trigger
      + weekday/날짜 가드; 게이트가 IR cron과 대조 후 공통 소거)

run 간 기억(cycle count/until)은 helper(counter/input_boolean)로 —
문서의 helpers 블록에 선언한다. 관찰 모델: helper 조작은 내부 상태이고
기기 액션만 비교 채널에 놓인다(IR이 카운터를 내부 상태로 보는 것과 동일).

ha_step.py(의미론 해석)와는 이름 규칙(names.py)만 공유하고 컴파일 코드는
공유하지 않는다 — 게이트 EQUIV 388/388이 둘의 맞검사다.

Run:  python -m ha.lower_ref        # dataset.csv 388행 → ha/gt/*.yaml
"""

from __future__ import annotations

import json
import re

from explorer.gate import parse_binding
from explorer.ir_step import _CMP, parse_cond, parse_duration

from .names import SKILLS, Tables, numeric_attr

_id = lambda n: n          # parse_cond의 to_key — 원래 "Svc.Attr"를 그대로 둠


class LowerError(Exception):
    pass


# ── 시간 표기 ────────────────────────────────────────────────────────────────

def dur(v) -> dict:
    """'5 MIN' → {'minutes': 5} 식의 HA 시간 표기."""
    s = parse_duration(v)
    if s < 1:
        return {"milliseconds": int(round(s * 1000))}
    s = int(round(s))
    if s % 3600 == 0:
        return {"hours": s // 3600}
    if s % 60 == 0:
        return {"minutes": s // 60}
    return {"seconds": s}


def pattern_of(period) -> dict:
    """cycle period → time_pattern 필드. 1초 미만은 /1초로 붙인다(그리드가
    어차피 그보다 굵다 — 게이트 그리드 선택 참조)."""
    s = parse_duration(period)
    if s < 1:
        return {"seconds": "/1"}
    s = int(round(s))
    if s % 3600 == 0:
        return {"hours": f"/{s // 3600}"}
    if s % 60 == 0:
        return {"minutes": f"/{s // 60}"}
    return {"seconds": f"/{s}"}


def _period_tail(period) -> dict:
    """반복 끝의 주기 맞춤 대기 — delay 사슬은 몸통 지연이 다음 회차로
    번지지만(표류), 벽시계 정렬 대기는 회차 시작을 주기 눈금에 고정한다
    (IR cycle의 회차 앵커와 동일; 위상은 추상화)."""
    return {"wait_for_trigger": [{"trigger": "time_pattern",
                                  **pattern_of(period)}]}


# ── 바인딩 자리 소비 (gate._Rewriter와 같은 걷기 순서·병합 규칙) ─────────────

class Slots:
    def __init__(self, binding: dict) -> None:
        self.slots = parse_binding(binding)
        self.seen: dict[str, int] = {}

    def has(self, svc: str) -> bool:
        return svc in self.slots

    def next(self, svc: str) -> tuple[list[str], str | None]:
        lst = self.slots[svc]
        i = self.seen.get(svc, 0)
        self.seen[svc] = i + 1
        if len(lst) == 1:
            return lst[0]
        return lst[i] if i < len(lst) else lst[-1]


# ── 조건식 → Jinja (자리 소비는 원문 왼→오 순서 = AST 중위 순회) ─────────────

class Cond:
    def __init__(self, slots: Slots, tables: Tables) -> None:
        self.slots, self.t = slots, tables
        self.counter_vars: dict[str, str] = {}   # 이름 카운터 → helper entity

    def _atom(self, dev: str, svc: str, attr: str) -> str:
        return self.t.attr_entity(dev, svc, attr)

    def _cmp1(self, dev: str, svc: str, attr: str, op: str, lit) -> str:
        ent = self._atom(dev, svc, attr)
        if isinstance(lit, bool):
            s = f"is_state('{ent}', '{'on' if lit else 'off'}')"
            return f"not {s}" if op == "!=" else s
        if isinstance(lit, str):
            return f"states('{ent}') {op} '{lit}'"
        return f"states('{ent}')|float {op} {lit}"

    def _read_devs(self, node) -> tuple[list[str], str | None, str, str]:
        svc, attr = node[1].split(".", 1)
        if svc.lower() == "clock":
            # 시계 읽기는 time condition 자리(native_of)에서만 — 일반
            # 템플릿에서는 조각 밖 (README: now() 금지)
            raise LowerError(f"템플릿 속 시계 읽기: {node[1]}")
        if not self.slots.has(svc):
            raise LowerError(f"바인딩에 없는 서비스: {svc}")
        ids, quant = self.slots.next(svc)
        return ids, quant, svc, attr

    def render(self, node, boolctx: bool = False) -> str:
        k = node[0]
        if k == "lit":
            v = node[1]
            if isinstance(v, bool):
                return "true" if v else "false"
            if v is None:
                return "none"
            if isinstance(v, str):
                return f"'{v}'"
            return repr(v)
        if k == "var":
            if node[1] in self.counter_vars:
                return f"states('{self.counter_vars[node[1]]}')|int"
            return node[1]
        if k == "read":
            ids, quant, svc, attr = self._read_devs(node)
            join = " and " if quant == "all" else " or "
            if numeric_attr(svc, attr) and not boolctx:
                parts = [f"states('{self._atom(d, svc, attr)}')|float"
                         for d in ids]
            elif boolctx:
                parts = [f"is_state('{self._atom(d, svc, attr)}', 'on')"
                         for d in ids]
            else:
                parts = [f"states('{self._atom(d, svc, attr)}')" for d in ids]
            return parts[0] if len(ids) == 1 else "(" + join.join(parts) + ")"
        if k == "abs":
            return f"({self.render(node[1])})|abs"
        if k == "not":
            return f"(not {self.render(node[1], boolctx=True)})"
        if k == "bin":
            op, l, r = node[1], node[2], node[3]
            if op in ("and", "or"):
                return (f"({self.render(l, boolctx=True)} {op} "
                        f"{self.render(r, boolctx=True)})")
            if op in _CMP:
                # 읽기 vs 값: 비교 문맥을 기기별로 복제 (any→or, all→and)
                for side, other, flip in ((l, r, False), (r, l, True)):
                    if side[0] == "read" and other[0] == "lit":
                        ids, quant, svc, attr = self._read_devs(side)
                        o = op
                        if flip:
                            o = {">": "<", "<": ">", ">=": "<=",
                                 "<=": ">="}.get(op, op)
                        join = " and " if quant == "all" else " or "
                        parts = [self._cmp1(d, svc, attr, o, other[1])
                                 for d in ids]
                        return (parts[0] if len(ids) == 1
                                else "(" + join.join(parts) + ")")
                return f"({self.render(l)} {op} {self.render(r)})"
            return f"({self.render(l)} {op} {self.render(r)})"
        raise LowerError(f"조각 밖 조건식: {node[0]}")

    def jinja(self, src: str, negate: bool = False) -> str:
        body = self.render(parse_cond(src, _id), boolctx=True)
        return f"{{{{ not ({body}) }}}}" if negate else f"{{{{ {body} }}}}"


_WD_NAME = {"monday": "mon", "tuesday": "tue", "wednesday": "wed",
            "thursday": "thu", "friday": "fri", "saturday": "sat",
            "sunday": "sun"}


def _clock_native(ast, negate: bool) -> dict | None:
    """시계 비교 → HA time condition. clock.time >=/< HHMM → after/before,
    Clock.Weekday == "요일" → weekday. 못 다루는 꼴이면 None."""
    if ast[0] == "bin" and ast[2][0] == "read" \
            and ast[2][1].lower().startswith("clock.") and ast[3][0] == "lit":
        attr = ast[2][1].split(".", 1)[1].lower()
        op, lit = ast[1], ast[3][1]
        if attr == "time" and op in (">=", "<") \
                and isinstance(lit, (int, float)):
            hhmm = int(lit)
            at = f"{hhmm // 100:02d}:{hhmm % 100:02d}:00"
            geq = (op == ">=") != negate      # 결과 조건이 "지금 ≥ t"인가
            return {"condition": "time", ("after" if geq else "before"): at}
        if attr == "weekday" and op == "==" and isinstance(lit, str) \
                and not negate and lit.lower() in _WD_NAME:
            return {"condition": "time", "weekday": [_WD_NAME[lit.lower()]]}
    return None


def native_neg_of(cond: Cond, src: str) -> dict:
    """조건의 부정을 HA 조건 꼴로 (repeat while not(until) 자리)."""
    ast = parse_cond(src, _id)
    c = _clock_native(ast, negate=True)
    if c is not None:
        return c
    c = _clock_native(ast, negate=False)
    if c is not None:                     # 부정형이 안 되는 꼴은 not으로 감쌈
        return {"condition": "not", "conditions": [c]}
    return {"condition": "template",
            "value_template": cond.jinja(src, negate=True)}


def native_of(cond: Cond, src: str, kind: str) -> dict:
    """단일 원자 비교면 state/numeric_state 꼴, 아니면 template 꼴.
    kind: "trigger" | "condition". 자리 소비는 이 함수가 담당."""
    ast = parse_cond(src, _id)
    c = _clock_native(ast, negate=False)
    if c is not None:
        if kind == "trigger":
            raise LowerError(f"시계 조건을 trigger 자리에: {src!r}")
        return c
    if ast[0] == "bin" and ast[1] in _CMP and ast[2][0] == "read" \
            and ast[3][0] == "lit":
        op, lit = ast[1], ast[3][1]
        ids, quant, svc, attr = cond._read_devs(ast[2])
        if len(ids) == 1:
            ent = cond._atom(ids[0], svc, attr)
            if op == "==" and isinstance(lit, bool):
                v = "on" if lit else "off"
                return ({"trigger": "state", "entity_id": ent, "to": v}
                        if kind == "trigger" else
                        {"condition": "state", "entity_id": ent, "state": v})
            if op == "==" and isinstance(lit, str):
                return ({"trigger": "state", "entity_id": ent, "to": lit}
                        if kind == "trigger" else
                        {"condition": "state", "entity_id": ent, "state": lit})
            if op in (">", "<") and isinstance(lit, (int, float)) \
                    and not isinstance(lit, bool):
                # above/below는 exclusive — 딱 >, < 만 정확히 내릴 수 있다.
                # >=, <= 를 above/below로 내리는 것이 경계 fault (E4).
                fkey = "above" if op == ">" else "below"
                return ({"trigger": "numeric_state", "entity_id": ent,
                         fkey: lit} if kind == "trigger" else
                        {"condition": "numeric_state", "entity_id": ent,
                         fkey: lit})
            # 그 외(>=, <=, != 등)는 template로 정확히
            if isinstance(lit, bool):
                body = cond._cmp1(ids[0], svc, attr, op, lit)
            elif isinstance(lit, str):
                body = f"states('{ent}') {op} '{lit}'"
            else:
                body = f"states('{ent}')|float {op} {lit}"
            key = ("value_template" if kind in ("trigger", "condition")
                   else "value_template")
            return ({"trigger": "template", key: f"{{{{ {body} }}}}"}
                    if kind == "trigger" else
                    {"condition": "template", key: f"{{{{ {body} }}}}"})
        # 여러 대 → 비교 문맥 복제 템플릿
        join = " and " if quant == "all" else " or "
        parts = [cond._cmp1(d, svc, attr, op, lit) for d in ids]
        body = "(" + join.join(parts) + ")" if len(parts) > 1 else parts[0]
        return ({"trigger": "template", "value_template": f"{{{{ {body} }}}}"}
                if kind == "trigger" else
                {"condition": "template",
                 "value_template": f"{{{{ {body} }}}}"})
    # 원자 하나가 아니면 전체를 template로
    body = cond.render(ast, boolctx=True)
    return ({"trigger": "template", "value_template": f"{{{{ {body} }}}}"}
            if kind == "trigger" else
            {"condition": "template", "value_template": f"{{{{ {body} }}}}"})


# ── 인자 문자열 렌더링 ($Var / $Svc.Attr 삽입) ───────────────────────────────

_TMPL = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)")


def render_arg(v, cond: Cond):
    if not isinstance(v, str) or "$" not in v:
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v
    out, last = [], 0
    for m in _TMPL.finditer(v):
        out.append(v[last:m.start()])
        nm = m.group(1)
        if "." in nm:                       # $Svc.Attr = 센서 읽기 (자리 소비)
            svc, attr = nm.split(".", 1)
            ids, _, _, _ = cond._read_devs(("read", nm, nm))
            if len(ids) != 1:
                raise LowerError(f"인자 위치에 여러 대 자리: {svc}")
            out.append(f"{{{{ states('{cond._atom(ids[0], svc, attr)}') }}}}")
        else:
            out.append(f"{{{{ {nm} }}}}")
        last = m.end()
    out.append(v[last:])
    return "".join(out)


# ── 몸통 컴파일 (스텝 목록 → HA action 목록) ─────────────────────────────────

class Body:
    def __init__(self, slots: Slots, tables: Tables, key: str,
                 helpers: dict) -> None:
        self.cond = Cond(slots, tables)
        self.slots, self.t, self.key = slots, tables, key
        self.helpers = helpers

    def call(self, step: dict) -> list[dict]:
        svc, method = step["target"].split(".", 1)
        if not self.slots.has(svc):
            raise LowerError(f"바인딩에 없는 서비스: {svc}")
        ids, _ = self.slots.next(svc)
        data = {}
        for a, v in (step.get("args") or {}).items():
            data[a] = render_arg(v, self.cond)
        # 주 스킬 domain이 다른 기기끼리는 호출을 쪼갠다
        by_svc: dict[str, list[str]] = {}
        for d in ids:
            by_svc.setdefault(self.t.service(d, svc, method), []).append(d)
        out = []
        for svc_name, devs in by_svc.items():
            act = {"action": svc_name,
                   "target": {"entity_id": [self.t.dev_entity(d)
                                            for d in devs]}}
            if data:
                act["data"] = dict(data)
            if step.get("var"):
                act["response_variable"] = step["var"]
            out.append(act)
        return out

    def compile(self, steps: list) -> list[dict]:
        out: list[dict] = []
        for s in steps:
            op = s.get("op")
            if op == "call":
                out += self.call(s)
            elif op == "read":
                svc, attr = s["src"].split(".", 1)
                ids, _, _, _ = self.cond._read_devs(("read", s["src"], ""))
                if len(ids) != 1:
                    raise LowerError(f"read 위치에 여러 대 자리: {svc}")
                ent = self.cond._atom(ids[0], svc, attr)
                out.append({"variables":
                            {s["var"]: f"{{{{ states('{ent}') }}}}"}})
            elif op == "delay":
                out.append({"delay": dur(s["duration"])})
            elif op == "if":
                node = {"if": [native_of(self.cond, s["cond"], "condition")],
                        "then": self.compile(s.get("then") or [])}
                if s.get("else"):
                    node["else"] = self.compile(s["else"])
                out.append(node)
            elif op == "wait":
                out += self.wait(s)
            elif op == "cycle":
                out += self.cycle_repeat_ordered(s)
            elif op == "break":
                out.append({"stop": "break"})
            else:
                raise LowerError(f"op: {op}")
        return out

    def wait(self, s: dict) -> list[dict]:
        edge = s.get("edge") or "none"
        if s.get("for"):
            # 지속(sustain): "조건이 for 동안 끊기지 않고 참" —
            # 조건 성립을 기다렸다가, 깨짐을 제한시간 for로 기다린다.
            # 제한시간이 다 되면(wait.trigger 없음) 지속 성공.
            neg = self.cond.jinja(s["cond"], negate=True)
            return [{"repeat": {
                "sequence": [
                    {"wait_template": self.cond.jinja(s["cond"])},
                    {"wait_for_trigger": [
                        {"trigger": "template", "value_template": neg}],
                     "timeout": dur(s["for"]),
                     "continue_on_timeout": True},
                ],
                "until": "{{ wait.trigger is none }}"}}]
        if s.get("timeout"):
            body = [{"wait_template": self.cond.jinja(s["cond"]),
                     "timeout": dur(s["timeout"]),
                     "continue_on_timeout": True},
                    {"if": [{"condition": "template",
                             "value_template": "{{ not wait.completed }}"}],
                     "then": self.compile(s.get("on_timeout") or [])
                     + [{"stop": "timeout"}]}]
            return body
        # 단발 wait은 레벨/엣지 모두 wait_template — 첫 성립에 통과하는
        # 것은 동일하고(엣지 래치 초기값 False), 이미 참이면 즉시 통과가
        # IR 의미(첫 평가 tick 발화)와 같다.
        return [{"wait_template": self.cond.jinja(s["cond"])}]

    def cycle_repeat_ordered(self, s: dict) -> list[dict]:
        """cycle → repeat. 자리 소비 순서(until 먼저, body 나중)를 지키고,
        until 검사는 IR처럼 회차 시작 전 — repeat while not(until)."""
        cnt = s.get("count")
        while_cond = None
        if s.get("until"):
            # "이름 카운터 + until n >= k" = k회 반복 — repeat count로 접음
            if isinstance(cnt, str) and cnt.strip() \
                    and not cnt.strip().isdigit():
                ast = parse_cond(s["until"], _id)
                if ast[0] == "bin" and ast[1] in (">=", ">") \
                        and ast[2] == ("var", cnt.strip()) \
                        and ast[3][0] == "lit":
                    k = int(ast[3][1]) + (1 if ast[1] == ">" else 0)
                    seq = self.compile(s.get("body") or [])
                    seq.append(_period_tail(s["period"]))
                    return [{"repeat": {"count": k, "sequence": seq}}]
            while_cond = native_neg_of(self.cond, s["until"])
        seq = self.compile(s.get("body") or [])
        seq.append(_period_tail(s["period"]))
        if isinstance(cnt, str) and cnt.strip() and not cnt.strip().isdigit():
            raise LowerError("script 반복의 이름 카운터는 조각 밖")
        if while_cond is not None:
            return [{"repeat": {"while": [while_cond], "sequence": seq}}]
        if cnt:
            return [{"repeat": {"count": int(cnt), "sequence": seq}}]
        return [{"repeat": {"while": [{"condition": "template",
                                       "value_template": "{{ true }}"}],
                            "sequence": seq}}]


# ── cron 앵커 → time/time_pattern trigger + 가드 ─────────────────────────────

_WD = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


def _dow_list(field: str) -> list[str]:
    out = []
    for part in field.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += [_WD[i] for i in range(int(a), int(b) + 1)]
        else:
            out.append(_WD[int(part)])
    return out


def cron_head(cron: str) -> tuple[list[dict], list[dict]]:
    m, h, dom, mon, dow = cron.split()
    trig: list[dict] = []
    conds: list[dict] = []
    if "*" in h or "/" in h:
        tp: dict = {}
        if h != "*":
            tp["hours"] = h.replace("*/", "/")
        tp["minutes"] = m
        trig.append({"trigger": "time_pattern", **tp})
    else:
        trig.append({"trigger": "time", "at": f"{int(h):02d}:{int(m):02d}:00"})
    if dow != "*":
        conds.append({"condition": "time", "weekday": _dow_list(dow)})
    if dom != "*" or mon != "*":
        parts = []
        if dom != "*":
            parts.append(f"now().day == {int(dom)}")
        if mon != "*":
            parts.append(f"now().month == {int(mon)}")
        conds.append({"condition": "template",
                      "value_template": "{{ " + " and ".join(parts) + " }}"})
    return trig, conds


# ── 행 하나 lowering ─────────────────────────────────────────────────────────

def lower_row(ir: dict, binding: dict, devices: dict, key: str) -> dict:
    tl = list(ir["timeline"])
    anchor = tl[0]
    rest = tl[1:]
    slots = Slots(binding)
    tables = Tables(devices)
    helpers: dict = {}
    body = Body(slots, tables, key, helpers)
    has_cycle = any(s.get("op") == "cycle" for s in rest)
    kref = key.lower()

    if anchor.get("anchor") == "cron":
        trig, conds = cron_head(anchor["cron"])
        actions = []
        for s in rest:
            if s.get("op") == "cycle":
                actions += body.cycle_repeat_ordered(s)
            else:
                actions += body.compile([s])
        doc = {"kind": "automation", "key": key,
               "automation": {"alias": key, "mode": "single",
                              "triggers": trig, "conditions": conds,
                              "actions": actions}}
    elif has_cycle and rest[0].get("op") == "cycle" and len(rest) == 1:
        cyc = rest[0]
        cbody = list(cyc.get("body") or [])
        trig: list[dict] = []
        conds: list[dict] = []
        actions: list[dict] = []
        # 자리 소비 순서: until → 몸통(트리거 포함) → count 증가
        cnt_raw = cyc.get("count")
        cname_str = cnt_raw.strip() if isinstance(cnt_raw, str) \
            and cnt_raw.strip() and not cnt_raw.strip().isdigit() else None
        until_native = None
        if cyc.get("until"):
            # "이름 카운터 + until n >= k" = k회 반복 — count로 접음
            folded = False
            if cname_str:
                ast = parse_cond(cyc["until"], _id)
                if ast[0] == "bin" and ast[1] in (">=", ">") \
                        and ast[2] == ("var", cname_str) \
                        and ast[3][0] == "lit":
                    cyc = {**cyc, "count":
                           int(ast[3][1]) + (1 if ast[1] == ">" else 0),
                           "until": None}
                    cname_str = None
                    folded = True
            if not folded:
                until_native = native_of(body.cond, cyc["until"],
                                         "condition")
        if cbody and cbody[0].get("op") == "wait" \
                and (cbody[0].get("edge") or "none") == "rising" \
                and not cbody[0].get("for") and not cbody[0].get("timeout"):
            trig = [native_of(body.cond, cbody[0]["cond"], "trigger")]
            cbody = cbody[1:]
        else:
            trig = [{"trigger": "time_pattern", **pattern_of(cyc["period"])}]
        if until_native is not None:
            latch = f"input_boolean.{kref}_done"
            helpers.setdefault("input_boolean", {})[f"{kref}_done"] = \
                {"initial": "off"}
            conds.append({"condition": "state", "entity_id": latch,
                          "state": "off"})
            actions.append({"if": [until_native],
                            "then": [{"action": "input_boolean.turn_on",
                                      "target": {"entity_id": latch}},
                                     {"stop": "until"}]})
        cnt = cyc.get("count")
        counter_ent = None
        if isinstance(cnt, str) and cnt.strip() and not cnt.strip().isdigit():
            # 이름 카운터: 회차 번호를 조건이 읽는다(n % 2 등) — counter
            # helper로 노출, 상한 조건은 없음
            counter_ent = f"counter.{kref}_n"
            helpers.setdefault("counter", {})[f"{kref}_n"] = {"initial": 0}
            body.cond.counter_vars[cnt.strip()] = counter_ent
        elif cnt:
            counter_ent = f"counter.{kref}_n"
            helpers.setdefault("counter", {})[f"{kref}_n"] = {"initial": 0}
            conds.append({"condition": "numeric_state",
                          "entity_id": counter_ent, "below": int(cnt)})
        actions += body.compile(cbody)
        if counter_ent:
            actions.append({"action": "counter.increment",
                            "target": {"entity_id": counter_ent}})
        doc = {"kind": "automation", "key": key,
               "automation": {"alias": key, "mode": "single",
                              "triggers": trig, "conditions": conds,
                              "actions": actions}}
    else:
        # script: 전주 + (있으면) cycle을 repeat으로
        seq: list[dict] = []
        for s in rest:
            if s.get("op") == "cycle":
                seq += body.cycle_repeat_ordered(s)
            else:
                seq += body.compile([s])
        doc = {"kind": "script", "key": key,
               "script": {"alias": key, "mode": "single", "sequence": seq}}

    if helpers:
        doc["helpers"] = helpers
    return doc


# ── 388행 일괄 생성 ──────────────────────────────────────────────────────────

def main() -> None:
    import csv
    import os

    import yaml

    os.makedirs("ha/gt", exist_ok=True)
    n_ok, fails = 0, []
    kinds: dict[str, int] = {}
    for r in csv.DictReader(open("dataset.csv")):
        key = f'{r["category_v2"]}_{int(float(r["index"])):03d}'
        try:
            doc = lower_row(json.loads(r["ir_gt"]),
                            json.loads(r["binding_gt"] or "{}"),
                            json.loads(r["connected_devices"]), key)
            with open(f"ha/gt/{key}.yaml", "w", encoding="utf-8") as f:
                yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False,
                               width=88)
            kinds[doc["kind"]] = kinds.get(doc["kind"], 0) + 1
            n_ok += 1
        except Exception as e:
            fails.append((key, f"{type(e).__name__}: {e}"))
    print(f"생성 {n_ok}/388  종류 {kinds}")
    if fails:
        print(f"실패 {len(fails)}:")
        for k, msg in fails[:20]:
            print(f"  {k}: {msg}")


if __name__ == "__main__":
    main()
