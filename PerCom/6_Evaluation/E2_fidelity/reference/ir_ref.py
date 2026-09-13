"""E2 independent reference — Timeline IR interpreter.

Written from files/timeline_ir/extractor.md (Step/Expression grammar, D-rules), PerCom/3_Timeline_IR/HANDOFF.md
("E1 에서 확정된 실행 의미"), RUNTIME_CONTRACT, VERIFICATION_CONTRACT, FRONTEND_CORRECTNESS §1–§3 and
PROTOCOL_DRAFT S1–S4. Open points: SPEC_GAPS.md.
"""
from __future__ import annotations

import re

from common import (Delay, Wait, RefUnsupported, UNIT_MS, arith, check_typed, cmp_values, device_has_category,
                    is_num, to_text)

# ───────────────────────────── expression grammar ─────────────────────────────
_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_TOKEN = re.compile(
    r"(?P<ws>[ \t\r\n]+)"
    r"|(?P<num>[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)"
    r"|(?P<str>\"[^\"\\]*\")"
    r"|(?P<op>==|!=|<=|>=|<|>|\+|-|\*|/|%|\(|\)|,)"
    rf"|(?P<ref>\$?{_NAME}(?:\[[^\]]*\])?(?:\.{_NAME})?)"
)
KEYWORDS = {"and", "or", "not", "true", "false", "null"}
FUNCS = {"abs", "min", "max"}


def tokenize(src):
    toks, i = [], 0
    while i < len(src):
        m = _TOKEN.match(src, i)
        if not m:
            if src[i:i + 2] in ("&&", "||") or src[i] == "!":
                raise RefUnsupported("ir-expr-c-logic", f"C-style logical operator in {src!r} (extractor: forbidden)")
            raise RefUnsupported("ir-expr-syntax", f"cannot tokenize {src!r} at {i} ({src[i:i+6]!r})")
        i = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        toks.append((kind, m.group(kind)))
    return toks


def parse_ref(text):
    """`$var`, bare `var`, `Svc.Member`, `$Svc.Member`, `Svc[Dev,...].Member`, `Clock.Member`, `clock.time`."""
    body = text[1:] if text.startswith("$") else text
    m = re.fullmatch(rf"({_NAME})(?:\[([^\]]*)\])?(?:\.({_NAME}))?", body)
    if not m:
        raise RefUnsupported("ir-expr-syntax", text)
    head, devs, member = m.group(1), m.group(2), m.group(3)
    if member is None:
        if devs is not None:
            raise RefUnsupported("ir-expr-syntax", text)
        return ("var", head)
    if head.lower() == "clock" and devs is None:
        return ("clock", member.lower())
    dev_list = None if devs is None else [d.strip() for d in devs.split(",") if d.strip()]
    return ("attr", head, dev_list, member)


class _Parser:
    """Precedence (FRONTEND §2): parentheses, unary minus, * / %, + -, comparison, not, and, or."""

    def __init__(self, src):
        self.src = src
        self.toks = tokenize(src)
        self.i = 0

    def peek(self, kind=None, val=None):
        if self.i >= len(self.toks):
            return False
        k, v = self.toks[self.i]
        if kind is not None and k != kind:
            return False
        if val is not None and v != val:
            return False
        return True

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind, val):
        if not self.peek(kind, val):
            raise RefUnsupported("ir-expr-syntax", f"expected {val!r} in {self.src!r}")
        return self.take()

    def parse(self):
        if not self.toks:
            raise RefUnsupported("ir-expr-syntax", "empty expression")
        e = self.p_or()
        if self.i != len(self.toks):
            raise RefUnsupported("ir-expr-syntax", f"trailing tokens in {self.src!r}")
        return e

    def _kw(self, word):
        return self.peek("ref", word)

    def p_or(self):
        e = self.p_and()
        while self._kw("or"):
            self.take()
            e = ("or", e, self.p_and())
        return e

    def p_and(self):
        e = self.p_not()
        while self._kw("and"):
            self.take()
            e = ("and", e, self.p_not())
        return e

    def p_not(self):
        if self._kw("not"):
            self.take()
            return ("not", self.p_not())
        return self.p_cmp()

    def p_cmp(self):
        e = self.p_add()
        if self.peek("op") and self.toks[self.i][1] in ("==", "!=", "<", ">", "<=", ">="):
            op = self.take()[1]
            r = self.p_add()
            if self.peek("op") and self.toks[self.i][1] in ("==", "!=", "<", ">", "<=", ">="):
                raise RefUnsupported("ir-expr-chained-compare", self.src)
            return ("cmp", op, e, r)
        return e

    def p_add(self):
        e = self.p_mul()
        while self.peek("op") and self.toks[self.i][1] in ("+", "-"):
            op = self.take()[1]
            e = ("bin", op, e, self.p_mul())
        return e

    def p_mul(self):
        e = self.p_unary()
        while self.peek("op") and self.toks[self.i][1] in ("*", "/", "%"):
            op = self.take()[1]
            e = ("bin", op, e, self.p_unary())
        return e

    def p_unary(self):
        if self.peek("op", "-"):
            self.take()
            return ("neg", self.p_unary())
        return self.p_primary()

    def p_primary(self):
        if self.i >= len(self.toks):
            raise RefUnsupported("ir-expr-syntax", f"unexpected end of {self.src!r}")
        k, v = self.take()
        if k == "num":
            return ("lit", float(v) if "." in v else int(v))
        if k == "str":
            return ("lit", v[1:-1])
        if k == "op" and v == "(":
            e = self.p_or()
            self.expect("op", ")")
            return e
        if k == "ref":
            low = v.lower()
            if v in ("true", "false"):
                return ("lit", v == "true")
            if v == "null":
                return ("lit", None)
            if v in KEYWORDS:
                raise RefUnsupported("ir-expr-syntax", f"misplaced {v!r} in {self.src!r}")
            if low in FUNCS and not v.startswith("$") and self.peek("op", "("):
                self.take()
                args = [self.p_or()]
                while self.peek("op", ","):
                    self.take()
                    args.append(self.p_or())
                self.expect("op", ")")
                return ("fn", low, args)
            return parse_ref(v)
        raise RefUnsupported("ir-expr-syntax", f"unexpected {v!r} in {self.src!r}")


def parse_expr(src):
    if not isinstance(src, str):
        raise RefUnsupported("ir-expr-syntax", f"expression is not a string: {src!r}")
    return _Parser(src).parse()


_TEMPLATE_REF = re.compile(rf"\$({_NAME}(?:\[[^\]]*\])?(?:\.{_NAME})?)")


def parse_template(s):
    parts, pos = [], 0
    for m in _TEMPLATE_REF.finditer(s):
        if m.start() > pos:
            parts.append(s[pos:m.start()])
        parts.append(parse_ref("$" + m.group(1)))
        pos = m.end()
    if pos < len(s):
        parts.append(s[pos:])
    return parts


def walk_refs(node):
    if isinstance(node, str):
        return
    k = node[0]
    if k in ("attr", "clock", "var"):
        yield node
    elif k == "fn":
        for a in node[2]:
            yield from walk_refs(a)
    elif k in ("bin", "cmp"):
        yield from walk_refs(node[2])
        yield from walk_refs(node[3])
    elif k in ("and", "or"):
        yield from walk_refs(node[1])
        yield from walk_refs(node[2])
    elif k in ("not", "neg"):
        yield from walk_refs(node[1])


def parse_duration(s, what):
    if not isinstance(s, str):
        raise RefUnsupported("ir-duration", f"{what}: {s!r}")
    m = re.fullmatch(r"\s*([0-9]+)\s+(HOUR|MIN|SEC|MSEC)\s*", s)
    if not m:
        raise RefUnsupported("ir-duration", f"{what}: {s!r} (extractor: '<N> <UNIT>', UNIT in HOUR/MIN/SEC/MSEC)")
    return int(m.group(1)) * UNIT_MS[m.group(2)]


# ───────────────────────────── program ─────────────────────────────
_ALLOWED_KEYS = {
    "start_at": {"op", "anchor", "cron"},
    "wait": {"op", "cond", "edge", "for", "timeout", "on_timeout"},
    "delay": {"op", "duration"},
    "read": {"op", "var", "src"},
    "call": {"op", "target", "args", "var"},
    "if": {"op", "cond", "then", "else"},
    "cycle": {"op", "until", "period", "count", "body"},
    "break": {"op"},
}
_NUMERIC_ARG = {"INTEGER", "DOUBLE", "BOOL", "BOOLEAN"}


class IrProgram:
    def __init__(self, ir, binding, devices, catalog):
        self.catalog, self.devices = catalog, devices
        if not isinstance(ir, dict) or not isinstance(ir.get("timeline"), list):
            raise RefUnsupported("ir-shape", "expected {'timeline': [...]}")
        self._uid = 0
        self._occ = []          # (service_lower, member_lower, step uid) in walk order, binding-grounded refs only
        self.steps = self._compile_list(ir["timeline"], top=True)
        self.slot_of = self._assign_slots(binding or {})

    # ---- compile ----
    def _compile_list(self, steps, top=False):
        if not isinstance(steps, list):
            raise RefUnsupported("ir-shape", f"step list expected, got {steps!r}")
        out = []
        for i, st in enumerate(steps):
            if not isinstance(st, dict) or st.get("op") not in _ALLOWED_KEYS:
                raise RefUnsupported("ir-op", f"unknown step {st!r}")
            op = st["op"]
            extra = set(st) - _ALLOWED_KEYS[op]
            if extra:
                raise RefUnsupported("ir-field", f"{op} has unknown fields {sorted(extra)}")
            if op == "start_at" and not (top and i == 0):
                raise RefUnsupported("ir-start_at", "start_at must be the first top-level step")
            out.append(self._compile(st))
        return out

    def _note(self, node, uid):
        """Record binding-grounded attribute references in document order (left to right inside an expression)."""
        for r in walk_refs(node):
            if r[0] == "attr" and r[2] is None:
                self._occ.append((r[1].lower(), r[3].lower(), r))

    def _expr(self, src, uid):
        e = parse_expr(src)
        self._note(e, uid)
        return e

    _EXPR_FIELDS = {"wait": ("cond",), "if": ("cond",), "cycle": ("until",), "read": ("src",)}
    _LIST_FIELDS = {"wait": ("on_timeout",), "if": ("then", "else"), "cycle": ("body",)}

    def _compile(self, st):
        self._uid += 1
        uid = self._uid
        op = st["op"]
        n = {"op": op, "uid": uid}
        if op == "call":
            self._compile_call(st, n, uid)
            return n
        parsed = {}
        for key in st:                  # fields in document (JSON key) order, so occurrences keep their order (G8)
            if key in self._EXPR_FIELDS.get(op, ()) and st[key] is not None:
                parsed[key] = self._expr(st[key], uid)
            elif key in self._LIST_FIELDS.get(op, ()):
                parsed[key] = self._compile_list(st[key] if st[key] is not None else [])
        if op == "start_at":
            if st.get("anchor") not in ("now", "cron"):
                raise RefUnsupported("ir-start_at", f"anchor {st.get('anchor')!r}")
        elif op == "wait":
            if "cond" not in parsed:
                raise RefUnsupported("ir-field", "wait without cond")
            n["cond"] = parsed["cond"]
            edge = st.get("edge")
            if edge not in (None, "none", "rising"):
                raise RefUnsupported("ir-edge", repr(edge))
            n["rising"] = edge == "rising"
            n["for"] = parse_duration(st["for"], "wait.for") if st.get("for") is not None else None
            n["timeout"] = parse_duration(st["timeout"], "wait.timeout") if st.get("timeout") is not None else None
            if st.get("on_timeout") is not None and n["timeout"] is None:
                raise RefUnsupported("ir-field", "on_timeout without timeout")
            n["on_timeout"] = parsed.get("on_timeout", [])
        elif op == "delay":
            n["ms"] = parse_duration(st.get("duration"), "delay.duration")
        elif op == "read":
            var = st.get("var")
            if not isinstance(var, str) or not re.fullmatch(_NAME, var.lstrip("$")):
                raise RefUnsupported("ir-read", f"bad var {var!r}")
            n["var"] = var.lstrip("$")
            src = parsed.get("src")
            if src is None or src[0] not in ("attr", "clock"):
                raise RefUnsupported("ir-read-src", f"read.src must be a device attribute: {st.get('src')!r}")
            n["src"] = src
        elif op == "if":
            if "cond" not in parsed or "then" not in parsed:
                raise RefUnsupported("ir-field", "if needs cond and then")
            n["cond"] = parsed["cond"]
            n["then"] = parsed["then"]
            n["else"] = parsed.get("else", [])
        elif op == "cycle":
            n["until"] = parsed.get("until")
            if st.get("period") is None:
                raise RefUnsupported("ir-cycle", "cycle.period is required (extractor D7b)")
            n["period"] = parse_duration(st["period"], "cycle.period")
            cnt = st.get("count")
            if cnt is not None and (not isinstance(cnt, str) or not re.fullmatch(_NAME, cnt.lstrip("$"))):
                raise RefUnsupported("ir-cycle", f"bad count {cnt!r}")
            n["count"] = cnt.lstrip("$") if cnt else None
            if "body" not in parsed:
                raise RefUnsupported("ir-cycle", "cycle without body")
            n["body"] = parsed["body"]
        return n

    def _compile_arg(self, spec, v, uid):
        t = (spec.get("type") or "").upper()
        if isinstance(v, str):
            if t in _NUMERIC_ARG:
                return ("expr", self._expr(v, uid))
            if "$" in v:
                parts = parse_template(v)
                for p in parts:
                    if not isinstance(p, str):
                        self._note(p, uid)
                return ("template", parts)
            return ("lit", v)
        return ("lit", v)

    def _compile_call(self, st, n, uid):
        tgt = parse_ref(st.get("target") or "")
        if tgt[0] != "attr":
            raise RefUnsupported("ir-call-target", repr(st.get("target")))
        _, svc_name, explicit, mname = tgt
        member = self.catalog.member(svc_name, mname)
        if member is None:
            raise RefUnsupported("unknown-member", f"{svc_name}.{mname}")
        if member.kind != "function":
            raise RefUnsupported("call-of-value", f"{member} is not a function")
        n["target"] = tgt
        n["member"] = member
        given = st.get("args") or {}
        if not isinstance(given, dict):
            raise RefUnsupported("ir-call-args", repr(given))
        lower = {}
        for k, v in given.items():
            if k.lower() in lower:
                raise RefUnsupported("ir-call-args", f"duplicate argument {k}")
            lower[k.lower()] = v
        spec_by = {a["id"].lower(): a for a in member.args}
        if set(lower) != set(spec_by):
            raise RefUnsupported("ir-call-args", f"{member}: args {sorted(given)} != catalog {[a['id'] for a in member.args]}")
        compiled_by = {}
        for key in st:                       # document order: target and args occurrences (G8)
            if key == "target" and explicit is None:
                self._occ.append((svc_name.lower(), mname.lower(), tgt))
            elif key == "args":
                for k, v in given.items():
                    compiled_by[k.lower()] = self._compile_arg(spec_by[k.lower()], v, uid)
        n["args"] = [compiled_by[a["id"].lower()] for a in member.args]     # catalog order (SERVICE_MODEL §1)
        var = st.get("var")
        if var is not None:
            if not isinstance(var, str) or not re.fullmatch(_NAME, var.lstrip("$")):
                raise RefUnsupported("ir-call-var", repr(var))
            if not member.read_role:
                raise RefUnsupported("effectful-return", f"{member} return assignment (SERVICE_MODEL §2)")
            for kind, val in n["args"]:
                if kind == "template" or (kind == "expr" and val[0] != "lit"):
                    raise RefUnsupported("dynamic-query-arg", f"{member} query argument is not a literal")
            n["var"] = var.lstrip("$")
        else:
            if member.read_role:
                raise RefUnsupported("discarded-query", f"{member} called as a statement (SERVICE_MODEL §2)")
            n["var"] = None

    def _assign_slots(self, binding):
        """FRONTEND §3: `Service#2` is the second slot regardless of JSON key order; one slot is reused by every
        occurrence. SERVICE_MODEL §1: ground in original appearance order. With k > 1 slots, the i-th occurrence of
        the service in IR document order takes slot i and the counts must match (G8). Keyed by the AST node."""
        slots = {}
        for key, val in binding.items():
            m = re.fullmatch(r"(.+?)(?:#([0-9]+))?", str(key))
            svc, k = m.group(1).lower(), int(m.group(2) or 1)
            if isinstance(val, list):
                parsed = ("list", [str(x) for x in val])
            elif isinstance(val, dict) and len(val) == 1 and next(iter(val)) in ("any", "all") \
                    and isinstance(next(iter(val.values())), list):
                q = next(iter(val))
                parsed = (q, [str(x) for x in val[q]])
            else:
                raise RefUnsupported("binding-shape", f"{key}: {val!r}")
            slots.setdefault(svc, {})[k] = parsed
        occ = {}
        for svc, mem, node in self._occ:
            occ.setdefault(svc, []).append((mem, node))
        slot_of = {}
        for svc, items in occ.items():
            if svc not in slots:
                raise RefUnsupported("binding-missing", f"no binding for service {svc}")
            ks = sorted(slots[svc])
            if ks != list(range(1, len(ks) + 1)):
                raise RefUnsupported("binding-slot-gap", f"{svc}: slots {ks}")
            if len(ks) == 1:
                for _, node in items:
                    slot_of[id(node)] = slots[svc][1]
            elif len(ks) == len(items):
                for i, (_, node) in enumerate(items):
                    slot_of[id(node)] = slots[svc][i + 1]
            else:
                raise RefUnsupported("binding-slot-count",
                                     f"{svc}: {len(ks)} slots for {len(items)} occurrences {[m for m, _ in items]}")
        self._nodes_alive = [node for _, _, node in self._occ]
        return slot_of

    # ---- grounding ----
    def ground(self, ref):
        """-> (mode, device ids, member). mode: 'list' | 'any' | 'all'."""
        _, svc, explicit, mname = ref
        member = self.catalog.member(svc, mname)
        if member is None:
            raise RefUnsupported("unknown-member", f"{svc}.{mname}")
        if explicit is not None:
            mode, devs = "list", explicit
        else:
            mode, devs = self.slot_of[id(ref)]
        if not devs:
            raise RefUnsupported("binding-empty", f"{svc}.{mname}")
        for d in devs:
            if d not in self.devices:
                raise RefUnsupported("device-not-in-inventory", d)
            if not device_has_category(self.devices, d, member.service):
                raise RefUnsupported("capability", f"{d} lacks category {member.service}")
        return mode, list(devs), member

    def read_device(self, rt, d, member):
        if member.kind == "function":
            if not (member.read_role and not member.args):
                raise RefUnsupported("function-as-property", f"{member} read without a call")
        return rt.inputs.read(d, member, ())

    # ---- evaluation ----
    def ev(self, rt, e, store):
        k = e[0]
        if k == "lit":
            return e[1]
        if k == "var":
            return store.get(e[1])
        if k == "clock":
            if e[1] == "time":                     # VERIFICATION_CONTRACT: clock.time = hour*100 + minute
                return rt.clock("hour") * 100 + rt.clock("minute")
            return rt.clock(e[1])
        if k == "attr":
            mode, devs, member = self.ground(e)
            if mode != "list" or len(devs) != 1:
                raise RefUnsupported("read-quantifier", f"{member} bound to {mode} {devs} outside a comparison")
            return self.read_device(rt, devs[0], member)
        if k == "neg":
            v = self.ev(rt, e[1], store)
            v = 0 if v is None else v
            if not is_num(v):
                raise RefUnsupported("arith-type", f"-{v!r}")
            return -v
        if k == "bin":
            return arith(e[1], self.ev(rt, e[2], store), self.ev(rt, e[3], store), null_zero=True)
        if k == "fn":
            vals = [self.ev(rt, a, store) for a in e[2]]
            vals = [0 if v is None else v for v in vals]
            if not all(is_num(v) for v in vals):
                raise RefUnsupported("arith-type", f"{e[1]}{vals}")
            if e[1] == "abs" and len(vals) == 1:
                return abs(vals[0])
            if e[1] in ("min", "max") and len(vals) == 2:
                return min(vals) if e[1] == "min" else max(vals)
            raise RefUnsupported("ir-function", f"{e[1]} with {len(vals)} args")
        if k == "cmp":
            return self.ev_cmp(rt, e, store)
        if k == "not":
            v = self.ev(rt, e[1], store)
            if not isinstance(v, bool):
                raise RefUnsupported("logic-type", f"not {v!r}")
            return not v
        if k in ("and", "or"):
            a, b = self.ev(rt, e[1], store), self.ev(rt, e[2], store)   # both sides evaluated (FRONTEND §2)
            if not (isinstance(a, bool) and isinstance(b, bool)):
                raise RefUnsupported("logic-type", f"{a!r} {k} {b!r}")
            return (a and b) if k == "and" else (a or b)
        raise RefUnsupported("ir-expr", repr(e))

    def _quantified(self, e):
        if e[0] != "attr":
            return None
        mode, devs, member = self.ground(e)
        return (mode, devs, member) if mode in ("any", "all") else None

    def ev_cmp(self, rt, e, store):
        _, op, a, b = e
        qa, qb = self._quantified(a), self._quantified(b)
        if qa and qb:
            raise RefUnsupported("quantifier-both-sides", op)
        if qa or qb:
            mode, devs, member = qa or qb
            other = self.ev(rt, b if qa else a, store)
            res = []
            for d in devs:            # FRONTEND §3: any -> OR, all -> AND, operand position kept
                v = self.read_device(rt, d, member)
                res.append(cmp_values(op, v, other) if qa else cmp_values(op, other, v))
            return any(res) if mode == "any" else all(res)
        return cmp_values(op, self.ev(rt, a, store), self.ev(rt, b, store))

    def ev_bool(self, rt, e, store):
        v = self.ev(rt, e, store)
        if not isinstance(v, bool):
            raise RefUnsupported("condition-type", f"condition value {v!r} is not BOOL")
        return v

    def clock_sensitive(self, e):
        return any(r[0] == "clock" for r in walk_refs(e))

    def eval_arg(self, rt, spec, carg, store):
        kind, val = carg
        if kind == "lit":
            v = val
        elif kind == "expr":
            v = self.ev(rt, val, store)
        else:
            refs = [p for p in val if not isinstance(p, str)]
            if len(val) == 1 and refs:
                v = self.ev(rt, val[0], store)            # the whole string is one reference: raw value
                if v is None:
                    raise RefUnsupported("none-action-arg", f"{spec['id']} receives a missing value")
            else:
                v = "".join(p if isinstance(p, str) else to_text(self.ev(rt, p, store)) for p in val)
        return v

    # ---- execution ----
    def gen(self, rt):
        self.store = {}
        self.latch = {}
        yield from self.g_list(rt, self.steps)
        return None

    def g_list(self, rt, steps):
        for st in steps:
            r = yield from self.g_step(rt, st)
            if r != "normal":
                return r
        return "normal"

    def g_step(self, rt, st):
        rt.tick()
        op, store = st["op"], self.store
        if op == "start_at":
            return "normal"          # cron anchor erased, one firing window (HANDOFF)
        if op == "delay":
            if st["ms"] > 0:
                yield Delay(rt.now + st["ms"])
            return "normal"
        if op == "read":
            store[st["var"]] = self.ev(rt, st["src"], store)
            return "normal"
        if op == "call":
            mode, devs, member = self.ground(st["target"])
            args = []
            for spec, carg in zip(member.args, st["args"]):
                v = self.eval_arg(rt, spec, carg, store)
                check_typed(self.catalog, member.service, spec.get("type"), spec.get("format"), spec.get("bound"),
                            v, f"{member}.{spec['id']}")
                args.append(v)
            if mode != "list":
                raise RefUnsupported("call-quantified-binding", f"{member} bound with {mode}")
            if st["var"] is not None:
                if len(devs) != 1:
                    raise RefUnsupported("multi-device-query", f"{member} on {devs}")
                store[st["var"]] = rt.inputs.read(devs[0], member, tuple(args))
            else:
                rt.emit(member.service, member.id, args, devs, fanout=len(devs) > 1)
            return "normal"
        if op == "if":
            branch = st["then"] if self.ev_bool(rt, st["cond"], store) else st["else"]
            return (yield from self.g_list(rt, branch))
        if op == "wait":
            w = _IrWait(self, rt, st)
            r = w.poll(rt.now)
            if r is None:
                r = yield Wait(w)
            if r == "fire":
                return "normal"
            if not st["on_timeout"]:          # empty on_timeout: continue past the wait (G7)
                return "normal"
            r2 = yield from self.g_list(rt, st["on_timeout"])
            if r2 in ("break", "halt"):
                return r2
            return "abort_iter"               # non-empty on_timeout ends the current iteration (G7)
        if op == "cycle":
            if st["count"]:
                store[st["count"]] = 0         # reset on every entry (FRONTEND §4)
            while True:
                rt.tick()
                if st["until"] is not None and self.ev_bool(rt, st["until"], store):   # S1
                    break
                r = yield from self.g_list(rt, st["body"])
                if r == "break":
                    break
                if r == "halt":
                    return "halt"
                if st["count"]:
                    store[st["count"]] = (store.get(st["count"]) or 0) + 1       # S2
                if st["period"] > 0:
                    yield Delay(rt.now + st["period"])                            # R5 / S1
            return "normal"
        if op == "break":
            return "break"
        raise RefUnsupported("ir-op", op)


class _IrWait:
    """wait(cond, edge, for, timeout). Level: fires when cond holds (for: continuously for the duration, reset on any
    false observation; release wins at the expiry instant, R6). Rising (R7/D6): latch starts false and is updated
    only when this wait observes; fires on an observation true with latch false (initial true fires). Rising + for
    (S3): the rising observation starts the sustain timer; a false resets it and needs a new rising edge.
    Timeout expiry vs condition at the same instant: condition first (S4)."""

    def __init__(self, prog, rt, st):
        self.prog, self.rt, self.st = prog, rt, st
        self.start = None
        self.timeout_at = rt.now + st["timeout"] if st["timeout"] is not None else None
        self.clock_sensitive = prog.clock_sensitive(st["cond"])

    def poll(self, now):
        st, prog = self.st, self.prog
        c = prog.ev_bool(self.rt, st["cond"], prog.store)
        fired = False
        if st["rising"]:
            latch = prog.latch.get(st["uid"], False)
            if st["for"] is None:
                if c and not latch:
                    fired = True
                prog.latch[st["uid"]] = c
            else:
                if c and not latch:
                    self.start = now
                elif not c:
                    self.start = None
                prog.latch[st["uid"]] = c
                if self.start is not None and now - self.start >= st["for"]:
                    fired = True
        else:
            if st["for"] is None:
                fired = c
            else:
                if c:
                    if self.start is None:
                        self.start = now
                    fired = now - self.start >= st["for"]
                else:
                    self.start = None
        if fired:
            return "fire"
        if self.timeout_at is not None and now >= self.timeout_at:
            return "timeout"
        return None

    def deadline(self):
        c = []
        if self.start is not None and self.st["for"] is not None:
            c.append(self.start + self.st["for"])
        if self.timeout_at is not None:
            c.append(self.timeout_at)
        return min(c) if c else None
