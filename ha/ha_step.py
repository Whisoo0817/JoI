"""HA 제한 문법 파서 + 한-걸음 실행기 (HaRunner).

전략: 제한 조각(README 표) 안의 HA 문서를 **기기 형태 Timeline IR로
번역**하고 explorer의 같은 명령어 집합(ir_step.compile_ir)으로 실행한다 —
"HA 문법을 같은 한-걸음 실행기 명령어로 번역"이 profile의 실행 의미론이고,
번역 규칙이 곧 선언된 HA 의미론이다:

  trigger(state/numeric_state/template) → cycle[wait 엣지] — 래치 초기값
      False = "시작 시 이미 참이면 첫 평가에 발화". HA 재시작 때 엔티티가
      unknown→실제값 전이를 겪어 trigger가 발화하는 실동작과 같다.
  time_pattern(/N)                     → cycle period N (위상은 추상화)
  condition                            → 레벨 검사 (if)
  wait_template                        → wait 레벨 (이미 참이면 즉시 통과)
  wait_* + timeout + [if not wait.completed → … stop] → wait 제한시간 +
      on_timeout (정해진 분기 꼴만 수용 — 조각 선언)
  지속 관용구(repeat[wait_template C; wait_for_trigger not C, timeout X]
      until wait.trigger is none)      → wait 지속(for X)
  repeat while/count (+끝 delay)       → cycle (until은 do-while이라 첫
      회차를 풀어 쓴 뒤 cycle로)
  helper(counter/input_boolean)        → 내부 상태 (관찰 모델: 기기 액션만
      비교 채널) — 선언 없는 helper 참조는 조각 밖(fail-closed)

조각 밖 문법은 전부 interp.Unsupported → 게이트가 REFUSED로 감싼다.
lower_ref.py(생성 방향)와는 이름 규칙(names.py)만 공유한다.
"""

from __future__ import annotations

import re

from explorer.expr import canonical_key
from explorer.interp import Unsupported
from explorer.ir_step import IrRunner, default_to_key

from .names import Tables

_WD_NUM = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
           "sun": 7}
_WD_FULL = {"mon": "monday", "tue": "tuesday", "wed": "wednesday",
            "thu": "thursday", "fri": "friday", "sat": "saturday",
            "sun": "sunday"}


def _dur_sec(d) -> float:
    """HA 시간 표기({'minutes':5} / 'HH:MM:SS' / 숫자 초) → 초."""
    if isinstance(d, (int, float)):
        return float(d)
    if isinstance(d, str):
        hh, mm, ss = (["0", "0"] + d.split(":"))[-3:]
        return int(hh) * 3600 + int(mm) * 60 + float(ss)
    if isinstance(d, dict):
        return (d.get("hours", 0) * 3600 + d.get("minutes", 0) * 60
                + d.get("seconds", 0) + d.get("milliseconds", 0) / 1000)
    raise Unsupported(f"시간 표기: {d!r}")


def _dur_ir(d) -> str:
    s = _dur_sec(d)
    if s < 1:
        return f"{int(round(s * 1000))} MSEC"
    s = int(round(s))
    if s % 3600 == 0:
        return f"{s // 3600} HOUR"
    if s % 60 == 0:
        return f"{s // 60} MIN"
    return f"{s} SEC"


# ── 제한 템플릿(Jinja 부분집합) → 기기 형태 조건 문자열 ──────────────────────

_T_TOKEN = re.compile(
    r"\s*(is_state\s*\(|states\s*\(|now\s*\(\s*\)\s*\.\s*\w+|"
    r"wait\.completed|wait\.trigger|"
    r"\|\s*(?:float|int|abs)|>=|<=|==|!=|>|<|\(|\)|,|\+|-|%|\*|/|"
    r"'[^']*'|\"[^\"]*\"|[\d.]+|\w+)")


class Tpl:
    """{{ ... }} 본문을 기기 형태 IR 조건 문자열로 바꾼다."""

    def __init__(self, ctx: "Ctx") -> None:
        self.ctx = ctx

    def tokens(self, src: str) -> list[str]:
        out, i = [], 0
        while i < len(src):
            m = _T_TOKEN.match(src, i)
            if not m:
                if src[i:].strip():
                    raise Unsupported(f"템플릿 토큰: {src[i:]!r}")
                break
            out.append(m.group(1))
            i = m.end()
        return out

    def convert(self, body: str) -> str:
        self.toks = self.tokens(body)
        self.pos = 0
        out = self._expr()
        if self.pos != len(self.toks):
            raise Unsupported(f"템플릿 잔여: {self.toks[self.pos:]!r}")
        return out

    def _peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _take(self):
        self.pos += 1
        return self.toks[self.pos - 1]

    def _entity_arg(self) -> str:
        t = self._take()
        if not (t.startswith("'") or t.startswith('"')):
            raise Unsupported(f"entity 인자: {t!r}")
        return t[1:-1]

    def _postfix(self, base: str, numeric: bool) -> str:
        while self._peek() and self._peek().startswith("|"):
            f = self._take().replace(" ", "")
            if f == "|abs":
                base = f"abs({base})"
            elif f in ("|float", "|int"):
                pass                      # 값은 이미 원시형 — 표기만 걷어냄
            else:
                raise Unsupported(f"필터: {f}")
        return base

    def _atom(self) -> str:
        t = self._take()
        if t == "(":
            e = self._expr()
            if self._take() != ")":
                raise Unsupported("템플릿 괄호")
            return self._postfix(f"( {e} )", False)
        if t == "not":
            return f"not {self._atom()}"
        if t.startswith("is_state"):
            ent = self._entity_arg()
            if self._take() != ",":
                raise Unsupported("is_state 인자")
            val = self._take()
            if self._take() != ")":
                raise Unsupported("is_state 닫기")
            return self.ctx.state_eq(ent, val.strip("'\""))
        if t.startswith("states"):
            ent = self._entity_arg()
            if self._take() != ")":
                raise Unsupported("states 닫기")
            return self._postfix(self.ctx.read_of(ent), True)
        if t.startswith("now"):
            field = t.split(".")[-1].strip()
            if field in ("day", "month"):
                return f"clock.{field}"
            raise Unsupported(f"now().{field}")
        if t == "wait.completed" or t == "wait.trigger":
            raise Unsupported("wait 결과는 정해진 분기 꼴에서만")
        if t.startswith(("'", '"')):
            return f'"{t[1:-1]}"'
        if re.fullmatch(r"[\d.]+", t) or t in ("true", "false", "none"):
            return "null" if t == "none" else t
        if re.fullmatch(r"\w+", t):
            return f"${t}"                # script 변수
        raise Unsupported(f"템플릿 원자: {t!r}")

    def _expr(self) -> str:
        parts = [self._cmp()]
        while self._peek() in ("and", "or"):
            parts.append(self._take())
            parts.append(self._cmp())
        return " ".join(parts)

    def _cmp(self) -> str:
        l = self._arith()
        if self._peek() in (">=", "<=", "==", "!=", ">", "<"):
            op = self._take()
            return f"{l} {op} {self._arith()}"
        if self._peek() == "is":          # "wait.trigger is none"류 — 조각 밖
            raise Unsupported("is 비교")
        return l

    def _arith(self) -> str:
        l = self._atom()
        while self._peek() in ("+", "-", "%", "*", "/"):
            op = self._take()
            l = f"{l} {op} {self._atom()}"
        return l


_JJ = re.compile(r"^\s*\{\{\s*(.*?)\s*\}\}\s*$", re.S)


def tpl_body(s: str) -> str:
    m = _JJ.match(s or "")
    if not m:
        raise Unsupported(f"템플릿 꼴 아님: {s!r}")
    return m.group(1)


# ── 문서 번역 문맥 ───────────────────────────────────────────────────────────

class Ctx:
    def __init__(self, doc: dict, devices: dict) -> None:
        self.t = Tables(devices)
        self.name_map: dict[str, str] = {}
        self.bind: dict[tuple, list] = {}
        helpers = doc.get("helpers") or {}
        self.counters = {f"counter.{n}": (n, c.get("initial", 0))
                         for n, c in (helpers.get("counter") or {}).items()}
        self.latches = {f"input_boolean.{n}": (n, c.get("initial", "off"))
                        for n, c in
                        (helpers.get("input_boolean") or {}).items()}
        self.counter_var: dict[str, str] = {}   # counter entity → IR 변수
        self.tpl = Tpl(self)

    # 속성 entity → 기기 형태 원자 ("Dev.Attr") + name_map 기록
    def read_of(self, ent: str) -> str:
        if ent in self.counters:
            v = self.counter_var.setdefault(ent, f"hn{len(self.counter_var)}")
            return f"${v}"
        if ent in self.latches:
            raise Unsupported(f"래치 읽기는 is_state 꼴로: {ent}")
        hit = self.t.ent2attr.get(ent)
        if hit is None:
            if ent.split(".", 1)[0] in ("counter", "input_boolean"):
                raise Unsupported(f"선언 없는 helper: {ent}")
            raise Unsupported(f"모르는 entity: {ent}")
        dev, skill, attr = hit
        self.name_map[default_to_key(f"{dev}.{attr}")] = \
            f"{dev}.{canonical_key(skill, attr)[1]}"
        return f"{dev}.{attr}"

    def state_eq(self, ent: str, val: str) -> str:
        if ent in self.latches:
            v = f"__lat_{self.latches[ent][0]}"
            want = "true" if val == "on" else "false"
            return f"${v} == {want}"
        atom = self.read_of(ent)
        if val in ("on", "off"):
            return f"{atom} == {'true' if val == 'on' else 'false'}"
        return f'{atom} == "{val}"'


# ── 조건 dict 목록 → (IR 조건 문자열, cron 가드 잔여) ────────────────────────

def cond_str(c: dict, ctx: Ctx) -> str:
    k = c.get("condition")
    if k == "template":
        return "( " + ctx.tpl.convert(tpl_body(c["value_template"])) + " )"
    if k == "state":
        return "( " + ctx.state_eq(c["entity_id"], str(c["state"])) + " )"
    if k == "numeric_state":
        atom = ctx.read_of(c["entity_id"])
        parts = []
        if "above" in c:
            parts.append(f"{atom} > {c['above']}")
        if "below" in c:
            parts.append(f"{atom} < {c['below']}")
        if not parts:
            raise Unsupported("numeric_state에 above/below 없음")
        return "( " + " and ".join(parts) + " )"
    if k == "time":
        parts = []
        if "after" in c:
            hh, mm = c["after"].split(":")[:2]
            parts.append(f"clock.time >= {int(hh) * 100 + int(mm)}")
        if "before" in c:
            hh, mm = c["before"].split(":")[:2]
            parts.append(f"clock.time < {int(hh) * 100 + int(mm)}")
        if "weekday" in c:
            wds = [f'clock.weekday == "{_WD_FULL[w]}"' for w in c["weekday"]]
            parts.append("( " + " or ".join(wds) + " )")
        if not parts:
            raise Unsupported("time condition 비어 있음")
        return "( " + " and ".join(parts) + " )"
    if k == "not":
        inner = [cond_str(x, ctx) for x in c.get("conditions") or []]
        return "not ( " + " and ".join(inner) + " )"
    if k in ("and", "or"):
        inner = [cond_str(x, ctx) for x in c.get("conditions") or []]
        return "( " + f" {k} ".join(inner) + " )"
    raise Unsupported(f"condition: {k}")


def conds_str(cs: list, ctx: Ctx) -> str:
    return " and ".join(cond_str(c, ctx) for c in cs)


# ── 액션 목록 → IR 스텝 목록 ─────────────────────────────────────────────────

_ALLOWED_STEP = {"wait_template", "wait_for_trigger", "timeout",
                 "continue_on_timeout", "if", "then", "else", "delay",
                 "variables", "action", "service", "target", "data",
                 "response_variable", "repeat", "stop", "choose", "alias"}


def _arg_ir(v, ctx: Ctx):
    """data 값 → IR 인자. "{{ x }}" 삽입은 $ 표기로 되돌린다."""
    if not isinstance(v, str) or "{{" not in v:
        return v
    out, last = [], 0
    for m in re.finditer(r"\{\{\s*(.*?)\s*\}\}", v):
        out.append(v[last:m.start()])
        body = m.group(1)
        em = re.fullmatch(r"states\s*\(\s*'([^']+)'\s*\)", body)
        if em:
            out.append("$" + ctx.read_of(em.group(1)))
        elif re.fullmatch(r"\w+", body):
            out.append("$" + body)
        else:
            raise Unsupported(f"인자 템플릿: {body!r}")
        last = m.end()
    out.append(v[last:])
    return "".join(out)


def _fuse_timeout(step: dict, nxt, ctx: Ctx) -> tuple[dict, bool]:
    """wait_* + timeout (+뒤따르는 not wait.completed 분기) → IR wait 제한시간.
    반환: (wait 스텝, 다음 액션을 소비했는가)."""
    if "wait_template" in step:
        cond = ctx.tpl.convert(tpl_body(step["wait_template"]))
        edge = "none"
    else:
        trigs = step["wait_for_trigger"]
        if len(trigs) != 1:
            raise Unsupported("wait_for_trigger는 trigger 1개만")
        cond = trigger_cond(trigs[0], ctx)
        edge = "rising"
    w = {"op": "wait", "cond": cond, "edge": edge}
    if "timeout" not in step:
        return w, False
    if step.get("continue_on_timeout") is not True:
        raise Unsupported("timeout에는 continue_on_timeout 명시 필수")
    w["timeout"] = _dur_ir(step["timeout"])
    w["on_timeout"] = []
    used_next = False
    if isinstance(nxt, dict) and "if" in nxt:
        ic = nxt["if"]
        if len(ic) == 1 and ic[0].get("condition") == "template" \
                and "wait.completed" in (ic[0].get("value_template") or ""):
            body = tpl_body(ic[0]["value_template"]).replace(" ", "")
            if body != "notwait.completed":
                raise Unsupported(f"wait 분기 꼴: {body!r}")
            then = list(nxt.get("then") or [])
            if not (then and isinstance(then[-1], dict)
                    and "stop" in then[-1]):
                raise Unsupported("timeout 분기는 stop으로 끝나야 함")
            w["on_timeout"] = steps_of(then[:-1], ctx)
            used_next = True
    return w, used_next


def _sustain_of(rp: dict, ctx: Ctx) -> dict | None:
    """지속 관용구 repeat → IR wait 지속(for). 아니면 None."""
    u = rp.get("until")
    if not isinstance(u, str) \
            or u.replace(" ", "") != "{{wait.triggerisnone}}":
        return None
    seq = rp.get("sequence") or []
    if len(seq) != 2 or "wait_template" not in seq[0] \
            or "wait_for_trigger" not in seq[1]:
        return None
    cond = ctx.tpl.convert(tpl_body(seq[0]["wait_template"]))
    trigs = seq[1]["wait_for_trigger"]
    if len(trigs) != 1 or trigs[0].get("trigger") != "template":
        return None
    neg = ctx.tpl.convert(tpl_body(trigs[0]["value_template"]))
    if neg.replace(" ", "") != f"not({cond})".replace(" ", "") \
            and neg.replace(" ", "") != f"not(({cond}))".replace(" ", ""):
        raise Unsupported("지속 관용구의 부정 조건이 원조건과 다름")
    if seq[1].get("continue_on_timeout") is not True:
        raise Unsupported("지속 관용구에 continue_on_timeout 명시 필수")
    return {"op": "wait", "cond": cond, "edge": "none",
            "for": _dur_ir(seq[1]["timeout"])}


def _repeat_steps(rp: dict, ctx: Ctx) -> list[dict]:
    sus = _sustain_of(rp, ctx)
    if sus is not None:
        return [sus]
    seq = list(rp.get("sequence") or [])
    period = "0 MSEC"
    if seq and isinstance(seq[-1], dict) and "wait_for_trigger" in seq[-1] \
            and "timeout" not in seq[-1]:
        tail = seq[-1]["wait_for_trigger"]
        if len(tail) == 1 and (tail[0].get("trigger")
                               or tail[0].get("platform")) == "time_pattern":
            # 주기 맞춤 대기: 회차 시작이 주기 눈금에 고정 = cycle period
            period = _dur_ir(_pattern_sec(tail[0]))
            seq = seq[:-1]
    if "count" in rp:
        return [{"op": "cycle", "period": period, "until": None,
                 "count": str(int(rp["count"])),
                 "body": steps_of(seq, ctx)}]
    if "while" in rp:
        wc = rp["while"]
        cond = conds_str(wc, ctx) if isinstance(wc, list) else \
            ctx.tpl.convert(tpl_body(wc))
        until = None if cond.replace(" ", "") in ("(true)", "true") \
            else f"not {cond}"
        return [{"op": "cycle", "period": period, "until": until,
                 "body": steps_of(seq, ctx)}]
    if "until" in rp:
        # do-while: 첫 회차를 풀어 쓰고 cycle로
        uc = rp["until"]
        cond = conds_str(uc, ctx) if isinstance(uc, list) else \
            "( " + ctx.tpl.convert(tpl_body(uc)) + " )"
        first = steps_of(seq, ctx)
        rest = steps_of(seq, ctx)
        return first + [{"op": "cycle", "period": period, "until": cond,
                         "body": rest}]
    raise Unsupported("repeat에 count/while/until 없음")


def call_step(a: dict, ctx: Ctx) -> dict:
    svc_call = a.get("action") or a.get("service")
    dom, _, name = svc_call.partition(".")
    ents = a.get("target", {}).get("entity_id")
    if isinstance(ents, str):
        ents = [ents]
    if not ents:
        raise Unsupported(f"target 없는 호출: {svc_call}")
    sk_m = None
    devs = []
    for e in ents:
        hit = ctx.t.ent2dev.get(e)
        if hit is None:
            raise Unsupported(f"모르는 entity: {e}")
        did, _ = hit
        got = ctx.t.svc_of.get((did, name))
        if got is None:
            raise Unsupported(f"기기에 없는 서비스: {did}.{name}")
        if sk_m is None:
            sk_m = got
        elif sk_m != got:
            raise Unsupported(f"호출 대상 서비스 불일치: {sk_m} vs {got}")
        devs.append(did)
    skill, method = sk_m
    args = {k: _arg_ir(v, ctx) for k, v in (a.get("data") or {}).items()}
    ck = canonical_key(skill, method)
    ctx.bind.setdefault(ck, []).append([(d,) for d in devs])
    step = {"op": "call", "target": f"{skill}.{method}", "args": args}
    if a.get("response_variable"):
        step["var"] = a["response_variable"]
    return step


def steps_of(actions: list, ctx: Ctx) -> list[dict]:
    out: list[dict] = []
    i = 0
    while i < len(actions):
        a = actions[i]
        if not isinstance(a, dict):
            raise Unsupported(f"action 항목: {a!r}")
        bad = set(a) - _ALLOWED_STEP
        if bad:
            raise Unsupported(f"조각 밖 키: {sorted(bad)}")
        if "wait_template" in a or "wait_for_trigger" in a:
            w, used = _fuse_timeout(a, actions[i + 1] if i + 1
                                    < len(actions) else None, ctx)
            out.append(w)
            i += 2 if used else 1
            continue
        if "repeat" in a:
            out += _repeat_steps(a["repeat"], ctx)
        elif "if" in a:
            step = {"op": "if", "cond": conds_str(a["if"], ctx),
                    "then": steps_of(a.get("then") or [], ctx),
                    "else": steps_of(a.get("else") or [], ctx)}
            out.append(step)
        elif "delay" in a:
            out.append({"op": "delay", "duration": _dur_ir(a["delay"])})
        elif "variables" in a:
            for v, tv in a["variables"].items():
                body = tpl_body(tv)
                m = re.fullmatch(r"states\s*\(\s*'([^']+)'\s*\)", body)
                if not m:
                    raise Unsupported(f"variables 값: {body!r}")
                out.append({"op": "read", "var": v,
                            "src": ctx.read_of(m.group(1))})
        elif "action" in a or "service" in a:
            dom = (a.get("action") or a.get("service", "")).split(".")[0]
            if dom in ("counter", "input_boolean"):
                raise Unsupported(f"helper 조작은 정해진 자리에서만: {a}")
            out.append(call_step(a, ctx))
        elif "stop" in a:
            out.append({"op": "break"})
        elif "choose" in a:
            raise Unsupported("choose는 v1 조각 밖 (if/else 사용)")
        else:
            raise Unsupported(f"action 꼴: {sorted(a)}")
        i += 1
    return out


# ── trigger → 조건/period/cron 조각 ──────────────────────────────────────────

def trigger_cond(t: dict, ctx: Ctx) -> str:
    k = t.get("trigger") or t.get("platform")
    if t.get("for"):
        raise Unsupported("trigger for:는 v1 조각 밖 (지속 관용구 사용)")
    if k == "state":
        if "to" not in t:
            raise Unsupported("state trigger에 to 없음")
        return ctx.state_eq(t["entity_id"], str(t["to"]))
    if k == "numeric_state":
        atom = ctx.read_of(t["entity_id"])
        if "above" in t:
            return f"{atom} > {t['above']}"
        if "below" in t:
            return f"{atom} < {t['below']}"
        raise Unsupported("numeric_state trigger에 above/below 없음")
    if k == "template":
        return ctx.tpl.convert(tpl_body(t["value_template"]))
    raise Unsupported(f"trigger: {k}")


def _pattern_sec(t: dict) -> float:
    for f, mul in (("seconds", 1), ("minutes", 60), ("hours", 3600)):
        v = t.get(f)
        if isinstance(v, str) and v.startswith("/"):
            return int(v[1:]) * mul
    raise Unsupported(f"time_pattern 꼴: {t}")


# ── cron 재구성 (time/time_pattern trigger + 달력 가드 → cron 문자열) ────────

def _cron_of(trig: dict, conds: list, ctx: Ctx) -> tuple[str, list]:
    """소비한 달력 가드를 뺀 잔여 조건과 cron 문자열을 돌려준다."""
    k = trig.get("trigger") or trig.get("platform")
    if k == "time":
        hh, mm = trig["at"].split(":")[:2]
        m_f, h_f = str(int(mm)), str(int(hh))
    else:                                  # time_pattern (시간 필드형)
        m_f = str(trig.get("minutes", "*"))
        h_f = trig.get("hours", "*")
        if isinstance(h_f, str) and h_f.startswith("/"):
            h_f = "*/" + h_f[1:]
    dom_f = mon_f = dow_f = "*"
    rest = []
    for c in conds:
        if c.get("condition") == "time" and "weekday" in c \
                and len(c) == 2:
            dow_f = ",".join(str(_WD_NUM[w]) for w in c["weekday"])
        elif c.get("condition") == "template" and "now()" in \
                (c.get("value_template") or ""):
            body = tpl_body(c["value_template"])
            for part in re.split(r"\band\b", body):
                pm = re.fullmatch(r"\s*now\(\)\.(day|month)\s*==\s*(\d+)\s*",
                                  part)
                if not pm:
                    raise Unsupported(f"달력 가드 꼴: {part!r}")
                if pm.group(1) == "day":
                    dom_f = pm.group(2)
                else:
                    mon_f = pm.group(2)
        else:
            rest.append(c)
    return f"{m_f} {h_f} {dom_f} {mon_f} {dow_f}", rest


_F_RANGE = {"m": range(60), "h": range(24), "dom": range(1, 32),
            "mon": range(1, 13), "dow": range(1, 8)}


def cron_norm(cron: str) -> tuple:
    """cron 5필드 → 필드별 값 집합 (표기 차이를 무시한 비교용)."""
    out = []
    for field, key in zip(cron.split(), ("m", "h", "dom", "mon", "dow")):
        full = _F_RANGE[key]
        vals: set[int] = set()
        for part in field.split(","):
            step = 1
            if "/" in part:
                part, s = part.split("/")
                step = int(s)
            if part in ("*", ""):
                vals |= {v for v in full if v % step == 0} \
                    if step > 1 else set(full)
            elif "-" in part:
                a, b = part.split("-")
                vals |= set(range(int(a), int(b) + 1, step))
            else:
                vals.add(int(part))
        out.append(frozenset(vals))
    return tuple(out)


# ── 문서 → (기기 형태 IR, name_map, bind, cron) ──────────────────────────────

def ha_to_ir(doc: dict, devices: dict) \
        -> tuple[dict, dict, dict, str | None, float]:
    """번역 결과: (IR dict, name_map, bind, cron|None, 주기 힌트 초)."""
    ctx = Ctx(doc, devices)
    kind = doc.get("kind")
    if kind == "script":
        sc = doc["script"]
        if sc.get("mode", "single") != "single":
            raise Unsupported(f"mode: {sc.get('mode')}")
        steps = steps_of(sc.get("sequence") or [], ctx)
        ir = {"timeline": [{"op": "start_at", "anchor": "now"}] + steps}
        return ir, ctx.name_map, _bind_sites(ctx), None, 0.0
    if kind != "automation":
        raise Unsupported(f"kind: {kind}")

    au = doc["automation"]
    if au.get("mode", "single") != "single":
        raise Unsupported(f"mode: {au.get('mode')}")
    bad = set(au) - {"alias", "mode", "triggers", "conditions", "actions",
                     "trigger", "condition", "action"}
    if bad:
        raise Unsupported(f"조각 밖 키: {sorted(bad)}")
    trigs = au.get("triggers") or au.get("trigger") or []
    conds = list(au.get("conditions") or au.get("condition") or [])
    actions = list(au.get("actions") or au.get("action") or [])
    if len(trigs) != 1:
        raise Unsupported(f"trigger는 1개만 (지금 {len(trigs)})")
    trig = trigs[0]
    tk = trig.get("trigger") or trig.get("platform")

    # cron 꼴 = time trigger, 또는 고정값 필드가 있는 time_pattern
    # (전부 /N 꼴이면 주기 자동화)
    fixed = [v for v in (trig.get(f) for f in ("seconds", "minutes", "hours"))
             if v is not None and not str(v).startswith("/")]
    cron = None
    if tk == "time" or (tk == "time_pattern" and fixed):
        cron, conds = _cron_of(trig, conds, ctx)
        # cron 발화 1회 = 잔여 타임라인 1회 실행 (앵커는 게이트가 소거)
        until = None
        steps = steps_of(actions, ctx)
        if conds:
            steps = [{"op": "if", "cond": conds_str(conds, ctx),
                      "then": steps, "else": []}]
        ir = {"timeline": [{"op": "start_at", "anchor": "now"}] + steps}
        return ir, ctx.name_map, _bind_sites(ctx), cron, 0.0

    # 주기/트리거 automation → cycle
    lead_wait = None
    if tk == "time_pattern":
        period = _pattern_sec(trig)
    else:
        period = 0.1                       # trigger 감시는 tick마다
        lead_wait = {"op": "wait", "cond": trigger_cond(trig, ctx),
                     "edge": "rising"}

    until = None
    count = None
    # until 래치 관용구: 조건 [래치 off] + 첫 액션 if(U){latch on; stop}
    for c in list(conds):
        if c.get("condition") == "state" and \
                c.get("entity_id") in ctx.latches:
            if c.get("state") != "off":
                raise Unsupported("래치 조건은 off 검사만")
            if not (actions and "if" in actions[0]):
                raise Unsupported("래치 조건에 대응하는 분기 없음")
            head = actions[0]
            then = head.get("then") or []
            if not (len(then) == 2 and "stop" in then[1]
                    and (then[0].get("action") == "input_boolean.turn_on")):
                raise Unsupported("until 래치 분기 꼴")
            until = conds_str(head["if"], ctx)
            conds.remove(c)
            actions = actions[1:]
    # count 관용구: 조건 [counter below N] + 마지막 액션 increment
    for c in list(conds):
        ent = c.get("entity_id")
        if c.get("condition") == "numeric_state" and ent in ctx.counters:
            if "below" not in c:
                raise Unsupported("counter 조건은 below만")
            count = str(int(c["below"]))
            conds.remove(c)
    inc = None
    if actions and isinstance(actions[-1], dict) \
            and (actions[-1].get("action") == "counter.increment"):
        inc = actions[-1]["target"]["entity_id"]
        if inc not in ctx.counters:
            raise Unsupported(f"선언 없는 counter: {inc}")
        actions = actions[:-1]
    if count is not None and inc is None:
        raise Unsupported("counter 조건은 있는데 increment가 없음")
    if inc is not None and count is None:
        # 이름 카운터: 회차 번호 노출 (조건이 states('counter…')로 읽음)
        count = ctx.counter_var.setdefault(inc,
                                           f"hn{len(ctx.counter_var)}")

    body = steps_of(actions, ctx)
    if conds:                              # 잔여 조건 = 레벨 가드
        body = [{"op": "if", "cond": conds_str(conds, ctx),
                 "then": body, "else": []}]
    if lead_wait is not None:
        body = [lead_wait] + body
    cyc = {"op": "cycle", "period": _dur_ir(period), "until": until,
           "body": body}
    if count is not None:
        cyc["count"] = count
    ir = {"timeline": [{"op": "start_at", "anchor": "now"}, cyc]}
    return ir, ctx.name_map, _bind_sites(ctx), None, period


def _bind_sites(ctx: Ctx) -> dict:
    """(svc,method)별 자리 목록 — compile_ir의 자리별 명세 형식."""
    return {k: v for k, v in ctx.bind.items()}


class HaRunner(IrRunner):
    """제한 조각 HA 문서 → 번역 IR → 같은 한-걸음 실행기."""

    def __init__(self, doc: dict, devices: dict) -> None:
        ir, name_map, bind, cron, period = ha_to_ir(doc, devices)
        self.cron = cron
        self.period_hint = period
        super().__init__(ir, name_map=name_map, bind=bind)
