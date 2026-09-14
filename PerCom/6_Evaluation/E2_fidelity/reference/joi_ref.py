"""E2 independent reference — JoI interpreter over the ANTLR parse tree of lowering/parser/JOILang.g4.

Semantics from docs/JOI_SPEC.md, files/joi_common.md, RUNTIME_CONTRACT R1–R13, VERIFICATION_CONTRACT,
SERVICE_MODEL, FRONTEND_CORRECTNESS §1–§3 and PROTOCOL_DRAFT S5–S11, L1. Open points: SPEC_GAPS.md.
The parser is regenerated in reference/grammar/ from a copy of JOILang.g4 plus `%` (author decision, G11).
"""
from __future__ import annotations

import sys
from pathlib import Path

from common import (Delay, Wait, DeviceSets, RefError, RefUnsupported, UNIT_MS, arith, check_typed, cmp_values,
                    resolve_device_member)

# Parser generated inside reference/grammar/ from a copy of lowering/parser/JOILang.g4 with `%` added at the
# precedence of `*` and `/` (author decision 2026-09-14, SPEC_GAPS G11). The deployment grammar is not modified.
_GEN = Path(__file__).resolve().parent / "grammar"
if str(_GEN) not in sys.path:
    sys.path.insert(0, str(_GEN))
sys.dont_write_bytecode = True

from antlr4 import CommonTokenStream, InputStream                     # noqa: E402
from antlr4.error.ErrorListener import ErrorListener                   # noqa: E402
from antlr4.tree.Tree import TerminalNode                             # noqa: E402
from JOILangLexer import JOILangLexer                                 # noqa: E402
from JOILangParser import JOILangParser as P                          # noqa: E402

CLOCK_MEMBERS = {"hour", "minute", "weekday", "timestamp", "isholiday"}


# ───────────────────────────── parse → AST ─────────────────────────────
class _Collect(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f"{line}:{column} {msg}")


def parse_script(text):
    errs = _Collect()
    lexer = JOILangLexer(InputStream(text))
    lexer.removeErrorListeners()
    lexer.addErrorListener(errs)
    parser = P(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(errs)
    tree = parser.scenario()
    if errs.errors:
        raise RefUnsupported("syntax", "; ".join(errs.errors[:3]))
    return tree


def _kids(ctx):
    return [ctx.getChild(i) for i in range(ctx.getChildCount())]


def _is_tok(node, text=None):
    return isinstance(node, TerminalNode) and (text is None or node.getText() == text)


def _tags(ctx):
    out = []
    for n in _kids(ctx):
        if isinstance(n, P.Hashtag_listContext):
            out.extend(_tags(n))
        elif _is_tok(n):
            out.append(n.getText()[1:])
    return out


def conv_scenario(tree):
    for n in _kids(tree):
        if isinstance(n, P.Statement_listContext):
            return ("block", conv_stmt_list(n))
    raise RefUnsupported("syntax", "no statement list")


def conv_stmt_list(ctx):
    return [conv_stmt(n) for n in _kids(ctx) if isinstance(n, P.StatementContext)]


def conv_stmt(ctx):
    c = ctx.getChild(0)
    if isinstance(c, P.Value_assign_behaviorContext):
        ch = _kids(c)
        return ("assign", ch[0].getText(), ch[1].getText() == ":=", conv_arith(ch[2]))
    if isinstance(c, P.Action_behaviorContext):
        ch = _kids(c)
        out = None
        if isinstance(ch[0], P.OutputContext):
            out = ch[0].getText()
            ch = ch[2:]
        rng = None
        if isinstance(ch[0], P.Range_typeContext):
            rng = ch[0].getText()
            ch = ch[1:]
        # '(' tag_list ')' '.' IDENTIFIER '(' action_input ')'
        tags = _tags(ch[1])
        name = ch[4].getText()
        args = []
        ai = ch[6]
        for n in _kids(ai):
            if isinstance(n, P.Input_listContext):
                args = [conv_arith(x) for x in _kids(n) if isinstance(x, P.Arithmetic_expressionContext)]
        return ("action", out, rng, tags, name, args)
    if isinstance(c, P.If_statementContext):
        ch = _kids(c)
        cond = next(conv_cond(n) for n in ch if isinstance(n, P.Condition_listContext))
        then = next(conv_stmt(n) for n in ch if isinstance(n, P.StatementContext))
        els = None
        for n in ch:
            if isinstance(n, P.Else_statementContext):
                els = conv_stmt(next(x for x in _kids(n) if isinstance(x, P.StatementContext)))
        return ("if", cond, then, els)
    if isinstance(c, P.Loop_statementContext):
        ch = _kids(c)
        lc = next(n for n in ch if isinstance(n, P.Loop_conditionContext))
        conds = [conv_cond(n) for n in _kids(lc) if isinstance(n, P.Condition_listContext)]
        body = next(conv_stmt(n) for n in ch if isinstance(n, P.StatementContext))
        return ("loop", conds[0] if conds else None, body)
    if isinstance(c, P.For_each_statementContext):
        raise RefUnsupported("for", "`for` is excluded by the protocol (§7)")
    if isinstance(c, P.Wait_until_statementContext):
        return ("wait", next(conv_cond(n) for n in _kids(c) if isinstance(n, P.Condition_listContext)))
    if isinstance(c, P.Delay_statementContext):
        pt = next(n for n in _kids(c) if isinstance(n, P.Period_timeContext))
        num, unit = _kids(pt)
        return ("delay", int(num.getText()), unit.getText())
    if isinstance(c, P.Compound_statementContext):
        sl = next(n for n in _kids(c) if isinstance(n, P.Statement_listContext))
        return ("block", conv_stmt_list(sl))
    if isinstance(c, P.BreakContext):
        return ("break",)
    raise RefUnsupported("syntax", f"unknown statement {c.getText()!r}")


def conv_arith(ctx):
    ch = _kids(ctx)
    if len(ch) == 1:
        return conv_primary(ch[0])
    if len(ch) == 3 and _is_tok(ch[0], "("):
        return conv_arith(ch[1])
    if len(ch) == 3:
        return ("bin", ch[1].getText(), conv_arith(ch[0]), conv_arith(ch[2]))
    raise RefUnsupported("syntax", ctx.getText())


def conv_primary(ctx):
    ch = _kids(ctx)
    if len(ch) == 1 and _is_tok(ch[0]):
        tok = ch[0].getSymbol()
        text = tok.text
        if tok.type == P.TRUE:
            return ("lit", True)
        if tok.type == P.FALSE:
            return ("lit", False)
        if tok.type == P.INTEGER:
            return ("lit", int(text))
        if tok.type == P.DOUBLE:
            return ("lit", float(text))
        if tok.type == P.STRING_LITERAL:
            inner = text[1:-1]
            if "\\" in inner:
                raise RefUnsupported("string-escape", "backslash escapes are refused (FRONTEND §2)")
            return ("lit", inner)
        if tok.type == P.IDENTIFIER:
            return ("var", text)
    rng = None
    if isinstance(ch[0], P.Range_typeContext):
        rng = ch[0].getText()
        ch = ch[1:]
    # '(' tag_list ')' '.' IDENTIFIER
    return ("prop", rng, _tags(ch[1]), ch[4].getText())


def conv_cond(ctx):
    ch = _kids(ctx)
    if len(ch) == 1:
        return conv_atom(ch[0])
    if len(ch) == 2:                     # NOT condition_atom
        return ("not", conv_atom(ch[1]))
    if _is_tok(ch[0], "("):
        return conv_cond(ch[1])
    # and/or share one precedence level in the grammar; re-associate with `and` tighter than `or` (FRONTEND §2)
    operands, ops = [], []
    _flatten(ctx, operands, ops)
    groups = [[operands[0]]]
    for op, x in zip(ops, operands[1:]):
        if op == "and":
            groups[-1].append(x)
        else:
            groups.append([x])

    def fold(kind, xs):
        r = xs[0]
        for x in xs[1:]:
            r = (kind, r, x)
        return r
    return fold("or", [fold("and", g) for g in groups])


def _flatten(ctx, operands, ops):
    ch = _kids(ctx)
    if len(ch) == 3 and not _is_tok(ch[0], "("):
        _flatten(ch[0], operands, ops)
        ops.append(ch[1].getText())
        _flatten(ch[2], operands, ops)
    else:
        operands.append(conv_cond(ctx))


def conv_atom(ctx):
    ch = _kids(ctx)
    if len(ch) == 1:
        return ("truth", conv_arith(ch[0]))
    op_kids = _kids(ch[1])
    return ("cmp", op_kids[0].getText(), len(op_kids) == 2, conv_arith(ch[0]), conv_arith(ch[2]))


def _uses_clock(node):
    if not isinstance(node, tuple):
        return False
    if node[0] == "prop" and _is_clock(node[2], node[3]):
        return True
    return any(_uses_clock(x) for x in node[1:] if isinstance(x, tuple))


def _is_clock(tags, name):
    return tags == ["Clock"] or name.lower().startswith("clock_")


# ───────────────────────────── runtime ─────────────────────────────
class JoiProgram:
    def __init__(self, block, devices, catalog, device_sets=None, selector_assignment=None):
        """device_sets: None -> selectors as before (G1, tags only). A DeviceSets (possibly empty) -> binding
        decision B1 of 2026-09-14 (BINDING_DECISION_2026-09-14.md).
        selector_assignment (B5): list, one device-set index per assignable selector occurrence (see
        assignable_occurrences); None -> B1.2 tag rule."""
        self.devices, self.catalog = devices, catalog
        if device_sets is not None and not isinstance(device_sets, DeviceSets):
            device_sets = DeviceSets(device_sets)
        self.sets = device_sets
        self.assignment = None
        script = block.get("script", block.get("code"))
        if not isinstance(script, str):
            raise RefUnsupported("joi-block", "no script")
        period = block.get("period", 0)
        if isinstance(period, float) and period.is_integer():
            period = int(period)
        if not isinstance(period, int) or isinstance(period, bool) or period < 0:
            raise RefUnsupported("joi-period", repr(period))
        self.period = period
        self.root = conv_scenario(parse_script(script))
        self.occurrences = self.assignable_occurrences() if self.sets is not None else []
        if selector_assignment is not None:
            if self.sets is None:
                raise RefError("selector-assignment", "selector_assignment needs the binding")
            a = list(selector_assignment)
            if len(a) != len(self.occurrences):
                raise RefError("selector-assignment", f"{len(a)} indices for {len(self.occurrences)} occurrences")
            for i, ((node, svc), x) in enumerate(zip(self.occurrences, a)):
                n = len(self.sets.distinct(svc))
                if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < n:
                    raise RefError("selector-assignment", f"occurrence {i}: index {x!r} not in 0..{n - 1}")
            self.assignment = {id(node): x for (node, _), x in zip(self.occurrences, a)}

    # ---- selectors ----
    def match(self, tags):
        """B(T): devices matching every tag, in inventory order (FRONTEND §3). Without device sets: `tags` only (G1).
        With device sets (B1): a selector tag matches if it equals one of the device's tags, its ID or a category."""
        if self.sets is None:
            return [d for d, info in self.devices.items() if all(t in (info.get("tags") or []) for t in tags)]
        return [d for d, info in self.devices.items()
                if all(t in (info.get("tags") or []) or t == d or t in [str(c) for c in (info.get("category") or [])]
                       for t in tags)]

    def selector_service(self, tags, name):
        """B1: the service S the selector's member names. `service_member` prefix -> that service; otherwise the
        binding services that declare the member; several -> narrowed to categories of the tag-matched devices."""
        if "_" in name:
            pre, rest = name.split("_", 1)
            svc = self.catalog.service(pre)
            if svc is not None and self.catalog.member(pre, rest) is not None:
                return svc["id"].lower()
        cands = [s for s in sorted(self.sets.services())
                 if self.catalog.service(s) is not None and self.catalog.member(s, name) is not None]
        if len(cands) <= 1:
            return cands[0] if cands else None
        cats = {str(c).lower() for d in self.match(tags) for c in (self.devices[d].get("category") or [])}
        narrowed = [s for s in cands if s in cats]
        if len(narrowed) == 1:
            return narrowed[0]
        raise RefUnsupported("selector-service-ambiguous", f"(#{' #'.join(tags)}).{name}: binding services {cands}")

    # ---- B5: assignable selector occurrences ----
    def _selector_nodes(self, n):
        """Selector nodes in source order: statements in order; `if` cond, then, else; `loop` cond, body; `wait`
        cond; an action's selector before its arguments; comparison left operand before right; arithmetic left
        before right. Clock selectors are not selectors of a bound service and are skipped."""
        if not isinstance(n, tuple) or not n:
            return
        k = n[0]
        if k == "block":
            for x in n[1]:
                yield from self._selector_nodes(x)
        elif k == "assign":
            yield from self._selector_nodes(n[3])
        elif k == "action":
            if not _is_clock(n[3], n[4]):
                yield (n, n[3], n[4])
            for a in n[5]:
                yield from self._selector_nodes(a)
        elif k == "if":
            for x in n[1:]:
                yield from self._selector_nodes(x)
        elif k == "loop":
            yield from self._selector_nodes(n[1])
            yield from self._selector_nodes(n[2])
        elif k == "wait":
            yield from self._selector_nodes(n[1])
        elif k == "prop":
            if not _is_clock(n[2], n[3]):
                yield (n, n[2], n[3])
        elif k == "bin":
            yield from self._selector_nodes(n[2])
            yield from self._selector_nodes(n[3])
        elif k == "truth":
            yield from self._selector_nodes(n[1])
        elif k == "not":
            yield from self._selector_nodes(n[1])
        elif k in ("and", "or"):
            yield from self._selector_nodes(n[1])
            yield from self._selector_nodes(n[2])
        elif k == "cmp":
            yield from self._selector_nodes(n[3])
            yield from self._selector_nodes(n[4])

    def assignable_occurrences(self):
        """B5.1: [(node, service lower)] for every source selector occurrence whose service has >= 2 distinct device
        sets, in _selector_nodes order. An occurrence whose service cannot be decided (selector-service-ambiguous)
        is not listed (its run is REF-UNSUPPORTED under every assignment)."""
        out = []
        for node, tags, name in self._selector_nodes(self.root):
            try:
                svc = self.selector_service(tags, name)
            except RefUnsupported:
                continue
            if svc is not None and svc in self.sets.services() and len(self.sets.distinct(svc)) >= 2:
                out.append((node, svc))
        return out

    def tag_choice(self, tags, svc):
        """B1.2 index: the set equal to M, else the unique set containing M, else 0 (fallback to M / unsupported)."""
        dist = self.sets.distinct(svc)
        fm = frozenset(self.match(tags))
        for i, (devs, _) in enumerate(dist):
            if frozenset(devs) == fm:
                return i
        containing = [i for i, (devs, _) in enumerate(dist) if fm <= frozenset(devs)]
        return containing[0] if len(containing) == 1 else 0

    def selector_space(self):
        return {"domains": [len(self.sets.distinct(svc)) for _, svc in self.occurrences],
                "tag_choice": [self.tag_choice(node[2] if node[0] == "prop" else node[3], svc)
                               for node, svc in self.occurrences]}

    def bound_devices(self, tags, name, node=None):
        """B1. -> None when there are no device sets or S is not in the IR binding (then the tag rule applies);
        else (devices, IR quantifier) with quantifier None | 'any' | 'all' | 'conflict' (slots with the chosen set
        disagree)."""
        if self.sets is None:
            return None
        svc = self.selector_service(tags, name)
        if svc is None or svc not in self.sets.services():
            return None
        dist = self.sets.distinct(svc)
        if len(dist) == 1:
            chosen = dist[0]
        elif self.assignment is not None and node is not None and id(node) in self.assignment:
            chosen = dist[self.assignment[id(node)]]          # B5: the harness-given device set
        else:
            m = self.match(tags)
            fm = frozenset(m)
            equal = [x for x in dist if frozenset(x[0]) == fm]
            containing = [x for x in dist if fm <= frozenset(x[0])]
            if equal:
                chosen = equal[0]
            elif len(containing) == 1:
                chosen = containing[0]
            else:
                if not m:
                    raise RefUnsupported("selector-no-device", f"(#{' #'.join(tags)}) for {svc}")
                return m, None                      # M itself: no IR slot, JoI quantifier applies
        devs, qs = chosen
        named = {q for q in qs if q}
        q = None if not named else (next(iter(named)) if len(named) == 1 else "conflict")
        return list(devs), q

    def single(self, tags):
        m = self.match(tags)
        if not m:
            raise RefUnsupported("selector-no-device", f"(#{' #'.join(tags)})")
        mains = [d for d in m if "Main" in (self.devices[d].get("tags") or [])]
        return mains[0] if len(mains) == 1 else m[0]          # S6

    def clock_member(self, name):
        low = name.lower()
        if low.startswith("clock_"):
            low = low[len("clock_"):]
        if low not in CLOCK_MEMBERS:
            raise RefUnsupported("clock-member", f"Clock.{name} is not defined by S11")
        return low

    def read_prop(self, rt, tags, name, device=None):
        if _is_clock(tags, name):
            return rt.clock(self.clock_member(name))
        d = device if device is not None else self.single(tags)
        m = resolve_device_member(self.catalog, self.devices, d, name)
        if m.kind != "value":
            raise RefUnsupported("function-as-property", f"{m} used without parentheses (SERVICE_MODEL §1)")
        return rt.inputs.read(d, m)

    # ---- expressions ----
    def ev(self, rt, e):
        k = e[0]
        if k == "lit":
            return e[1]
        if k == "var":
            return self.store.get(e[1])
        if k == "prop":
            if not _is_clock(e[2], e[3]):
                b = self.bound_devices(e[2], e[3], node=e)
                if b is not None:
                    if len(b[0]) != 1:
                        raise RefUnsupported("read-quantifier", f"(#{' #'.join(e[2])}).{e[3]} bound to {b[0]} "
                                                                f"outside a comparison")
                    return self.read_prop(rt, e[2], e[3], device=b[0][0])
            if e[1] is not None:
                raise RefUnsupported("set-valued-selector", f"{e[1]}(#{' #'.join(e[2])}).{e[3]} outside a comparison")
            return self.read_prop(rt, e[2], e[3])
        if k == "bin":
            return arith(e[1], self.ev(rt, e[2]), self.ev(rt, e[3]))
        raise RefUnsupported("joi-expr", repr(e))

    def ev_cond(self, rt, c):
        k = c[0]
        if k == "truth":
            v = self.ev(rt, c[1])
            if not isinstance(v, bool):
                raise RefUnsupported("condition-type", f"bare condition value {v!r} is not BOOL")
            return v
        if k == "not":
            v = self.ev_cond(rt, c[1])
            return not v
        if k in ("and", "or"):
            a, b = self.ev_cond(rt, c[1]), self.ev_cond(rt, c[2])        # both evaluated (FRONTEND §2)
            return (a and b) if k == "and" else (a or b)
        if k == "cmp":
            _, op, flag, a, b = c
            sa, sb = self._operand(a, op, flag), self._operand(b, op, flag)
            qa, qb = sa is not None and sa[0] == "multi", sb is not None and sb[0] == "multi"
            if qa and qb:
                raise RefUnsupported("quantifier-both-sides", op)
            if qa or qb:
                (_, devs, use_or, tags, name), other = (sa, b) if qa else (sb, a)
                ov = self.ev(rt, other)
                res = []
                for d in devs:
                    v = self.read_prop(rt, tags, name, device=d)
                    res.append(cmp_values(op, v, ov) if qa else cmp_values(op, ov, v))
                return any(res) if use_or else all(res)
            if flag and sa is None and sb is None:
                raise RefUnsupported("or-flag-without-all", f"{op}| without all(...)")
            return cmp_values(op, self.ev(rt, a), self.ev(rt, b))
        raise RefUnsupported("joi-cond", repr(c))

    def _operand(self, x, op, flag):
        """Comparison operand. -> None (plain expression) | ("single", ...) resolved by B1 to one device |
        ("multi", devices, use_or, tags, name)."""
        if x[0] != "prop":
            return None
        rng, tags, name = x[1], x[2], x[3]
        if not _is_clock(tags, name):
            bound = self.bound_devices(tags, name, node=x)
            if bound is not None:
                devs, iq = bound
                if len(devs) == 1:
                    return ("single", devs, False, tags, name)
                # B1.4 (revised 2026-09-14): an explicit JoI quantifier first, the IR slot quantifier only without one
                if rng == "any" and flag:
                    raise RefUnsupported("any-with-or-flag", f"any(...) {op}|")
                if rng == "any" or flag:
                    return ("multi", devs, True, tags, name)
                if rng == "all":
                    return ("multi", devs, False, tags, name)
                if iq in ("any", "all"):
                    return ("multi", devs, iq == "any", tags, name)
                raise RefUnsupported("read-quantifier", f"(#{' #'.join(tags)}).{name} bound to {devs} with no "
                                                        f"quantifier in the IR slot or the JoI selector")
        if rng is None:
            return None
        if rng == "any" and flag:
            raise RefUnsupported("any-with-or-flag", f"any(...) {op}|")
        if _is_clock(tags, name):
            raise RefUnsupported("quantified-clock", name)
        devs = self.match(tags)
        if not devs:
            raise RefUnsupported("selector-no-device", f"{rng}(#{' #'.join(tags)})")
        return ("multi", devs, rng == "any" or flag, tags, name)       # S5

    # ---- statements ----
    def gen(self, rt):
        self.store = {}
        first = True
        while True:
            self.first = first                       # R8: first logical iteration
            r = yield from self.g_stmt(rt, self.root)
            if r == "break":                         # S9 / R13
                return None
            if self.period == 0:                     # one-shot
                return None
            first = False
            yield Delay(rt.now + self.period)        # R5: period counted from body completion

    def g_stmt(self, rt, s):
        rt.tick()
        k = s[0]
        if k == "block":
            for x in s[1]:
                r = yield from self.g_stmt(rt, x)
                if r == "break":
                    return r
            return "normal"
        if k == "assign":
            _, name, initial, expr = s
            if initial and not self.first:
                return "normal"
            self.store[name] = self.ev(rt, expr)
            return "normal"
        if k == "action":
            self.do_action(rt, s)
            return "normal"
        if k == "if":
            if self.ev_cond(rt, s[1]):
                return (yield from self.g_stmt(rt, s[2]))
            if s[3] is not None:
                return (yield from self.g_stmt(rt, s[3]))
            return "normal"
        if k == "loop":                               # L1
            while True:
                rt.tick()
                if s[1] is not None and not self.ev_cond(rt, s[1]):
                    break
                r = yield from self.g_stmt(rt, s[2])
                if r == "break":
                    break
            return "normal"
        if k == "wait":                               # R4 / S10: blocks at its position
            w = _LevelWait(self, rt, s[1])
            if w.poll(rt.now) is None:
                yield Wait(w)
            return "normal"
        if k == "delay":                              # R3
            _, n, unit = s
            if n < 0:
                raise RefUnsupported("negative-delay", f"{n} {unit}")
            ms = n * UNIT_MS[unit]
            if ms > 0:
                yield Delay(rt.now + ms)
            return "normal"
        if k == "break":
            return "break"
        raise RefUnsupported("joi-stmt", repr(s))

    def do_action(self, rt, s):
        _, out, rng, tags, name, args = s
        if _is_clock(tags, name):
            raise RefUnsupported("clock-function", name)
        bound = self.bound_devices(tags, name, node=s)
        if bound is not None:
            # B1.3 (revised 2026-09-14): the tag/ID/category match M, when non-empty and a part of the chosen set,
            # is called alone (a bound call split over lines); otherwise every device of the chosen set.
            m_match = self.match(tags)
            devs = m_match if m_match and set(m_match) <= set(bound[0]) else bound[0]
            if out is not None and len(devs) != 1:
                raise RefUnsupported("multi-device-query", f"{out} = (#{' #'.join(tags)}).{name}(...) on {devs}")
        elif out is not None and rng is not None:
            raise RefUnsupported("multi-device-query", f"{out} = {rng}(#{' #'.join(tags)}).{name}(...)")
        elif rng == "any":
            raise RefUnsupported("any-action", f"any(#{' #'.join(tags)}).{name}(): action meaning not specified")
        elif rng == "all":
            devs = self.match(tags)
            if not devs:
                raise RefUnsupported("selector-no-device", f"all(#{' #'.join(tags)})")
        else:
            devs = [self.single(tags)]
        members = [resolve_device_member(self.catalog, self.devices, d, name) for d in devs]
        m = members[0]
        if any(x is not m for x in members):
            raise RefUnsupported("fanout-member-mismatch", f"{name}: {members}")
        if m.kind != "function":
            raise RefUnsupported("call-of-value", f"{m} is not a function")
        argv = [self.ev(rt, a) for a in args]        # evaluated once, left to right (FRONTEND §3)
        if len(argv) != len(m.args):
            raise RefUnsupported("arg-count", f"{m}: {len(argv)} args, catalog {len(m.args)}")
        for spec, v in zip(m.args, argv):
            if v is None:
                raise RefUnsupported("none-action-arg", f"{m}.{spec['id']} receives a missing value")
            check_typed(self.catalog, m.service, spec.get("type"), spec.get("format"), spec.get("bound"), v,
                        f"{m}.{spec['id']}")
        if out is not None:
            if rng is not None and bound is None:
                raise RefUnsupported("multi-device-query", f"{rng}(...).{name}() assigned")
            if not m.read_role:
                raise RefUnsupported("effectful-return", f"{out} = {m}(...) (SERVICE_MODEL §2)")
            if any(a[0] != "lit" for a in args):
                raise RefUnsupported("dynamic-query-arg", f"{m} query argument is not a literal")
            self.store[out] = rt.inputs.read(devs[0], m, tuple(argv))
            return
        if m.read_role:
            raise RefUnsupported("discarded-query", f"{m} called as a statement (SERVICE_MODEL §2)")
        rt.emit(m.service, m.id, argv, devs, fanout=(rng == "all") if bound is None else (len(devs) > 1 or rng == "all"))


class _LevelWait:
    def __init__(self, prog, rt, cond):
        self.prog, self.rt, self.cond = prog, rt, cond
        self.clock_sensitive = _uses_clock(cond)

    def poll(self, now):
        return "fire" if self.prog.ev_cond(self.rt, self.cond) else None

    def deadline(self):
        return None
