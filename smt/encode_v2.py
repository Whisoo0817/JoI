"""v2 frontend: ground the new-syntax JoI (template skeletons / adapted
artifacts) into the v1 micro language — the encoders stay untouched.

The v1 encoders assume one implicit instance per service and reject the
constructs the v2 corpus is built from. This pass removes every one of them
BEFORE micro conversion, by statically resolving selectors against a concrete
device inventory (adapt.inventory) — binding-time grounding, mirroring what
deployment does:

    for (x : all(#T #S).member) {..}   → body copied per instance, x ↦ that
                                         instance's input key
    all(#T #S).member OP v             → And over instances of (key OP v)
    any(#T #S).member OP v             → Or  over instances
    (#T #S).attr  (plain, multi-tag)   → the unique matching instance's key
                                         (0 or >1 candidates = Unsupported —
                                         grounding is fail-closed, not fuzzy)
    (#GlobalVariable).get*("k")        → free input key `globalvariable.k`
                                         (GV = free input, the locked model)
    (#GlobalVariable).set*("k", v)     → emission with the GV name folded into
                                         the method (set*_k), so each GV key
                                         is its own output channel/obligation
    (#Clock).clock_timestamp           → ClockRef("timestamp") = seconds since
                                         deploy (encoder support added)

Per-instance input keys are `service#devid.attr` — fresh names the InputModel
treats like any other key, so N sensors become N independent symbolic
timelines. `:=` (init-once) and tick-persistent variables already exist in the
M2 engine (init_once / ITEExec.env) and pass through untouched.
"""

from __future__ import annotations

import copy
from typing import Optional

from sim import expr as E
from sim import joi_parser as jp

from smt.encode import Unsupported


class Grounder:
    def __init__(self, inv, catalog: dict):
        self.inv = inv
        self.catalog = catalog
        self._types = {t.lower(): t for t in
                       {d.type for d in inv.devices} | set(catalog)}

    # ── selector resolution ──────────────────────────────────────────────────

    def _split_tags(self, tags: tuple) -> tuple[Optional[str], Optional[str], list]:
        type_tag = space = None
        instance: list = []
        for tg in tags:
            if tg.lower() in self._types and type_tag is None:
                type_tag = self._types[tg.lower()]
            elif tg in self.inv.spaces:
                space = tg
            else:
                instance.append(tg)
        return type_tag, space, instance

    def _instances(self, tags: tuple, member: str) -> list[tuple[str, str]]:
        """[(device_id, input_key)] for a selector — offline devices included:
        the miter models the program as deployed, and a dead device's inputs
        simply become free symbols only the old side reads."""
        type_tag, space, instance = self._split_tags(tags)
        if type_tag is None:
            raise Unsupported(f"selector {tags}: no type tag")
        cands = self.inv.candidates(type_tag, space=space,
                                    spatial="same_space" if space else "anywhere",
                                    instance_tags=instance, online_only=False)
        svc, attr = E.canonical_key(type_tag, member)
        return [(d.id, f"{svc}#{d.id}.{attr}") for d in cands]

    def _single_key(self, node: E.QuantRef) -> str:
        inst = self._instances(node.tags, node.member)
        if len(inst) != 1:
            raise Unsupported(f"selector {node.tags}.{node.member}: "
                              f"{len(inst)} instances for a plain (#…) read")
        return inst[0][1]

    # ── expressions ──────────────────────────────────────────────────────────

    def expr(self, node):
        if isinstance(node, E.QuantRef):
            if node.key.startswith("clock."):
                # the clock is time, not a device instance
                return E.ClockRef("timestamp") if node.key == "clock.timestamp" \
                    else E.DeviceRef(node.key)
            if node.quant in ("all", "any"):
                raise Unsupported(f"quantified read {node.tags}.{node.member} "
                                  f"outside a comparison")
            return E.DeviceRef(self._single_key(node))
        if isinstance(node, E.DeviceRef):
            if node.key == "clock.timestamp":
                return E.ClockRef("timestamp")
            return node
        if isinstance(node, E.BinaryOp):
            for side, other, flip in ((node.left, node.right, False),
                                      (node.right, node.left, True)):
                if isinstance(side, E.QuantRef) and side.quant in ("all", "any"):
                    keys = [k for _, k in self._instances(side.tags, side.member)]
                    if not keys:
                        raise Unsupported(f"selector {side.tags}: no instances")
                    g_other = self.expr(other)
                    cmps = [E.BinaryOp(node.op,
                                       g_other if flip else E.DeviceRef(k),
                                       E.DeviceRef(k) if flip else g_other)
                            for k in keys]
                    join = "and" if side.quant == "all" else "or"
                    out = cmps[0]
                    for c in cmps[1:]:
                        out = E.BinaryOp(join, out, c)
                    return out
            return E.BinaryOp(node.op, self.expr(node.left), self.expr(node.right))
        if isinstance(node, E.UnaryOp):
            return E.UnaryOp(node.op, self.expr(node.operand))
        if isinstance(node, E.FuncCall):
            return E.FuncCall(node.name, [self.expr(a) for a in node.args])
        if isinstance(node, jp.CallExpr):
            return self._call_in_expr(node)
        return node   # Lit / VarRef / ClockRef

    def _gv_key(self, call: jp.CallExpr) -> str:
        if not call.args or not isinstance(call.args[0], E.Lit) \
                or not isinstance(call.args[0].value, str):
            raise Unsupported(f"GV access without a literal key: {call.method}")
        return call.args[0].value.strip().lower()

    def _call_in_expr(self, call: jp.CallExpr):
        if call.service.lower() == "globalvariable":
            return E.DeviceRef(f"globalvariable.{self._gv_key(call)}")
        raise Unsupported(f"call {call.service}.{call.method} in value position")

    # ── statements ───────────────────────────────────────────────────────────

    def stmts(self, body: list) -> list:
        out: list = []
        for s in body:
            if isinstance(s, jp.Assign):
                if isinstance(s.rhs, jp.CallExpr) and s.rhs.args is not None \
                        and s.rhs.service.lower() != "globalvariable":
                    # call-assign (`video = (#Camera).captureVideo(...)`) —
                    # stays a call so micro conversion makes MEmit(bind=name)
                    calls = self._call_stmt(s.rhs)
                    if len(calls) != 1:
                        raise Unsupported(f"call-assign {s.rhs.method}: "
                                          f"{len(calls)} instances")
                    out.append(jp.Assign(s.name, s.op, calls[0].call))
                else:
                    out.append(jp.Assign(s.name, s.op, self.expr(s.rhs)))
            elif isinstance(s, jp.CallStmt):
                out.extend(self._call_stmt(s.call))
            elif isinstance(s, jp.IfStmt):
                out.append(jp.IfStmt(self.expr(s.cond), self.stmts(s.then_body),
                                     self.stmts(s.else_body or [])))
            elif isinstance(s, jp.WaitUntil):
                out.append(jp.WaitUntil(self.expr(s.cond)))
            elif isinstance(s, jp.ForEach):
                out.extend(self._foreach(s))
            elif isinstance(s, (jp.Delay, jp.Break)):
                out.append(s)
            else:
                raise Unsupported(f"v2 stmt {type(s).__name__}")
        return out

    def _call_stmt(self, call: jp.CallExpr) -> list:
        if call.service.lower() == "globalvariable":
            key = self._gv_key(call)
            args = [self.expr(a) for a in call.args[1:]]
            return [jp.CallStmt(jp.CallExpr("GlobalVariable",
                                            f"{call.method}_{key}", args))]
        if call.tags:
            inst = self._instances(call.tags, call.method)
            if not inst:
                raise Unsupported(f"call {call.tags}.{call.method}: no instances")
            if len(inst) > 1 and call.quant is None:
                raise Unsupported(f"call {call.tags}.{call.method}: "
                                  f"{len(inst)} instances for a plain (#…) call")
            # service = the RESOLVED type tag, not the parser's last-tag
            # heuristic (`(#Camera #Office)` must not emit as service Office)
            type_tag, _, _ = self._split_tags(call.tags)
            return [jp.CallStmt(jp.CallExpr(type_tag or call.service, call.method,
                                            [self.expr(a) for a in call.args or []]))
                    for _ in inst]
        return [jp.CallStmt(jp.CallExpr(call.service, call.method,
                                        [self.expr(a) for a in call.args or []]))]

    def _foreach(self, s: jp.ForEach) -> list:
        src = s.source
        if not isinstance(src, E.QuantRef):
            raise Unsupported("for-iter source is not a selector read")
        out: list = []
        for _, key in self._instances(src.tags, src.member):
            body = _subst(copy.deepcopy(s.body), s.var, E.DeviceRef(key))
            out.extend(self.stmts(body))
        return out


# ── variable substitution (for-unroll) ───────────────────────────────────────

def _subst_expr(node, var: str, repl):
    if isinstance(node, E.VarRef) and node.name == var:
        return copy.deepcopy(repl)
    if isinstance(node, E.BinaryOp):
        return E.BinaryOp(node.op, _subst_expr(node.left, var, repl),
                          _subst_expr(node.right, var, repl))
    if isinstance(node, E.UnaryOp):
        return E.UnaryOp(node.op, _subst_expr(node.operand, var, repl))
    if isinstance(node, E.FuncCall):
        return E.FuncCall(node.name, [_subst_expr(a, var, repl) for a in node.args])
    if isinstance(node, jp.CallExpr) and node.args is not None:
        return jp.CallExpr(node.service, node.method,
                           [_subst_expr(a, var, repl) for a in node.args],
                           tags=node.tags, quant=node.quant)
    return node


def _subst(body: list, var: str, repl) -> list:
    out: list = []
    for s in body:
        if isinstance(s, jp.Assign):
            out.append(jp.Assign(s.name, s.op, _subst_expr(s.rhs, var, repl)))
        elif isinstance(s, jp.CallStmt):
            out.append(jp.CallStmt(_subst_expr(s.call, var, repl)))
        elif isinstance(s, jp.IfStmt):
            out.append(jp.IfStmt(_subst_expr(s.cond, var, repl),
                                 _subst(s.then_body, var, repl),
                                 _subst(s.else_body or [], var, repl)))
        elif isinstance(s, jp.WaitUntil):
            out.append(jp.WaitUntil(_subst_expr(s.cond, var, repl)))
        elif isinstance(s, jp.ForEach):
            if s.var == var:      # inner shadowing — leave its body alone
                out.append(s)
            else:
                out.append(jp.ForEach(s.var, _subst_expr(s.source, var, repl),
                                      _subst(s.body, var, repl)))
        else:
            out.append(s)
    return out


# ── entry ────────────────────────────────────────────────────────────────────

def ground_script(src: str, inv, catalog: dict) -> list:
    """v2 source text → grounded v1-compatible statement list."""
    return Grounder(inv, catalog).stmts(jp.parse_script(src))


def to_micro2(src: str, inv, catalog: dict) -> list:
    """v2 source text → v1 micro ops for the periodic (M2) engine."""
    from smt.encode2 import _joi_stmts2
    return _joi_stmts2(ground_script(src, inv, catalog))
