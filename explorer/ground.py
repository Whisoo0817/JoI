"""Grounding: bind selectors to a concrete device inventory before exploring.

A selector like `all(#AirQualitySensor #Office)` is a QUERY; the inventory
says which concrete instances answer it. Grounding rewrites the AST so the
interpreter only ever sees instance-level reads and actions:

- `(#X #Y).attr` (singular)      → DeviceRef("<id>.attr") of THE match
- `all(#X).attr OP| c` (exists)  → (a1 OP c) or (a2 OP c) or ...
- `all(#X).attr OP  c` (forall)  → (a1 OP c) and (a2 OP c) and ...
   (`OP|` on a plain selector also quantifies over every match — corpus
    usage confirmed 2026-07-31)
- `for (v : all(#X).m) { body }` → body copies with v ↦ DeviceRef("<id>.m")
- `all(#X).act(...)` statement   → one action per instance (target = id)

Matching: every selector tag must equal the device's type, one of its
spaces, or one of its instance_tags. Offline devices don't match (device
failure = binding change, P2). Clock/GlobalVariable are ambient, never
grounded. A selector matching NOTHING stays as-is ("floating": the tag set
keeps acting as one implicit device) and is reported — the honest gap list
between the script and this inventory. Singular selectors matching >1
device raise: choosing among them is the binding pipeline's job, not a
default the simulator should invent.

The library takes plain device tuples; only the __main__ demo imports the
adapt/ inventory (keeps this package self-contained).

Run:  python -m explorer.ground   (bindings report + grounded exploration
                                    + the k=1 vs k=2 quantifier demo)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import expr as expr_mod
from . import joi_parser as jp
from .expr import canonical_key
from .interp import Unsupported

AMBIENT = {"Clock", "GlobalVariable"}


@dataclass(frozen=True)
class Dev:
    id: str
    type: str
    spaces: tuple = ()
    tags: tuple = ()
    online: bool = True


def from_adapt(inv) -> list[Dev]:
    return [Dev(d.id, d.type, tuple(d.spaces), tuple(d.instance_tags),
                d.online) for d in inv.devices]


def match(devs: list[Dev], tags: tuple) -> list[Dev]:
    out = []
    for d in devs:
        if not d.online:
            continue
        if all(t == d.type or t in d.spaces or t in d.tags for t in tags):
            out.append(d)
    return out


@dataclass
class GroundReport:
    bindings: dict = field(default_factory=dict)    # selector → [ids]
    floating: list = field(default_factory=list)    # selectors with 0 matches


class _G:
    def __init__(self, devs: list[Dev]):
        self.devs = devs
        self.report = GroundReport()

    # selector resolution -----------------------------------------------------
    def _sel(self, tags: tuple) -> list[Dev] | None:
        """Matches for a selector; None = ambient or floating (keep as-is)."""
        if not tags or any(t in AMBIENT for t in tags):
            return None
        m = match(self.devs, tuple(tags))
        sel = "#" + "#".join(tags)
        if not m:
            if sel not in self.report.floating:
                self.report.floating.append(sel)
            return None
        self.report.bindings[sel] = [d.id for d in m]
        return m

    @staticmethod
    def _key(inst: Dev, service: str, method: str) -> str:
        _, attr = canonical_key(service, method)
        return f"{inst.id}.{attr}"

    # expressions -------------------------------------------------------------
    def _sel_read(self, node: Any) -> tuple | None:
        """(matches, service, member) if node is a selector attribute read."""
        if isinstance(node, jp.CallExpr) and node.args is None and node.tags:
            m = self._sel(node.tags)
            return None if m is None else (m, node.service, node.method)
        if isinstance(node, expr_mod.QuantRef) and node.tags:
            m = self._sel(node.tags)
            svc = node.tags[-1]
            return None if m is None else (m, svc, node.member or "")
        return None

    def ge(self, node: Any) -> Any:
        if isinstance(node, expr_mod.BinaryOp):
            quantified = node.op.endswith("|")
            base = node.op[:-1] if quantified else node.op
            for side, other, flip in ((node.left, node.right, False),
                                      (node.right, node.left, True)):
                sr = self._sel_read(side)
                if sr is None:
                    continue
                m, svc, member = sr
                is_all = getattr(side, "quant", None) == "all"
                if quantified or (is_all and len(m) >= 1):
                    join = "or" if quantified else "and"
                    other_g = self.ge(other)
                    terms = []
                    for inst in m:
                        ref = expr_mod.DeviceRef(self._key(inst, svc, member))
                        terms.append(expr_mod.BinaryOp(
                            base, other_g if flip else ref,
                            ref if flip else other_g))
                    out = terms[0]
                    for t in terms[1:]:
                        out = expr_mod.BinaryOp(join, out, t)
                    return out
            return expr_mod.BinaryOp(node.op, self.ge(node.left),
                                     self.ge(node.right))
        if isinstance(node, expr_mod.UnaryOp):
            return expr_mod.UnaryOp(node.op, self.ge(node.operand))
        if isinstance(node, expr_mod.FuncCall):
            return expr_mod.FuncCall(node.name, [self.ge(a) for a in node.args])
        sr = self._sel_read(node)
        if sr is not None:
            m, svc, member = sr
            if len(m) == 1:
                return expr_mod.DeviceRef(self._key(m[0], svc, member))
            raise Unsupported(
                f"selector matches {len(m)} devices in scalar position "
                f"(binding must choose): {[d.id for d in m]}")
        if isinstance(node, jp.CallExpr) and node.args is not None:
            return self._ground_call(node, expect_one=True)[0]
        return node

    # calls / statements ------------------------------------------------------
    def _ground_call(self, call: jp.CallExpr, expect_one: bool) -> list:
        """Always returns a list of grounded CallExpr (1 per instance)."""
        args = [self.ge(a) for a in (call.args or [])]
        m = self._sel(call.tags) if call.tags else None
        if m is None:
            return [jp.CallExpr(call.service, call.method, args,
                                tags=call.tags, quant=call.quant)]
        insts = m if (call.quant == "all" and not expect_one) else None
        if insts is None:
            if len(m) != 1:
                raise Unsupported(
                    f"call selector matches {len(m)} devices "
                    f"(binding must choose): {[d.id for d in m]}")
            insts = m
        return [jp.CallExpr(call.service, call.method, args,
                            tags=(inst.id,), quant=None) for inst in insts]

    def gs(self, stmt: Any) -> list:
        if isinstance(stmt, jp.Assign):
            if isinstance(stmt.rhs, jp.CallExpr) and stmt.rhs.args is not None:
                calls = self._ground_call(stmt.rhs, expect_one=True)
                return [jp.Assign(stmt.name, stmt.op, calls[0])]
            return [jp.Assign(stmt.name, stmt.op, self.ge(stmt.rhs))]
        if isinstance(stmt, jp.IfStmt):
            return [jp.IfStmt(self.ge(stmt.cond),
                              self._body(stmt.then_body),
                              self._body(stmt.else_body or []))]
        if isinstance(stmt, jp.WaitUntil):
            return [jp.WaitUntil(self.ge(stmt.cond))]
        if isinstance(stmt, jp.Loop):
            return [jp.Loop(self.ge(stmt.cond), self._body(stmt.body))]
        if isinstance(stmt, jp.CallStmt):
            return [jp.CallStmt(c)
                    for c in self._ground_call(stmt.call, expect_one=False)]
        if isinstance(stmt, jp.ForEach):
            sr = self._sel_read(stmt.source)
            if sr is None:
                raise Unsupported(
                    f"ForEach selector not in inventory: {stmt.source}")
            m, svc, member = sr
            out: list = []
            for inst in m:
                ref = expr_mod.DeviceRef(self._key(inst, svc, member))
                out += self._body([_subst(s, stmt.var, ref)
                                   for s in stmt.body])
            return out
        return [stmt]      # Break, Delay

    def _body(self, stmts: list) -> list:
        out: list = []
        for s in stmts:
            out += self.gs(s)
        return out


def _subst(node: Any, var: str, ref: Any) -> Any:
    """Replace VarRef(var) with ref, deep, over statements and expressions."""
    if isinstance(node, expr_mod.VarRef):
        return ref if node.name == var else node
    if isinstance(node, expr_mod.UnaryOp):
        return expr_mod.UnaryOp(node.op, _subst(node.operand, var, ref))
    if isinstance(node, expr_mod.BinaryOp):
        return expr_mod.BinaryOp(node.op, _subst(node.left, var, ref),
                                 _subst(node.right, var, ref))
    if isinstance(node, expr_mod.FuncCall):
        return expr_mod.FuncCall(node.name,
                                 [_subst(a, var, ref) for a in node.args])
    if isinstance(node, jp.CallExpr):
        if node.args is None:
            return node
        return jp.CallExpr(node.service, node.method,
                           [_subst(a, var, ref) for a in node.args],
                           tags=node.tags, quant=node.quant)
    if isinstance(node, jp.Assign):
        return jp.Assign(node.name, node.op, _subst(node.rhs, var, ref))
    if isinstance(node, jp.IfStmt):
        return jp.IfStmt(_subst(node.cond, var, ref),
                         [_subst(s, var, ref) for s in node.then_body],
                         [_subst(s, var, ref) for s in (node.else_body or [])])
    if isinstance(node, jp.WaitUntil):
        return jp.WaitUntil(_subst(node.cond, var, ref))
    if isinstance(node, jp.Loop):
        return jp.Loop(_subst(node.cond, var, ref),
                       [_subst(s, var, ref) for s in node.body])
    if isinstance(node, jp.CallStmt):
        return jp.CallStmt(_subst(node.call, var, ref))
    return node


def ground(stmts: list, devs: list[Dev]) -> tuple[list, GroundReport]:
    g = _G(devs)
    return g._body(stmts), g.report


# ── Demo driver ──────────────────────────────────────────────────────────────

def main() -> None:
    import json
    from adapt.inventory import base_office
    from .interp import parse
    from .explore import explore
    from .product import product_explore

    devs = from_adapt(base_office())
    data = json.load(open("explorer/corpus/joi_automation_codes.json"))

    print("== base_office 그라운딩 + 탐색 (ForEach 2건 편입 목표) ==")
    for s in data:
        if s.get("cron") not in ("", "x", None):
            continue
        try:
            gstmts, rep = ground(parse(s["code"]), devs)
            g = explore(gstmts, int(s["period"]))
            fl = f" 부유:{rep.floating}" if rep.floating else ""
            print(f"{s['name'][:24]:26s} 상태={g.n_states:<5d} "
                  f"에지={g.n_edges:<7d} {'닫힘' if g.closed else '미완'}"
                  f" 바인딩={sum(len(v) for v in rep.bindings.values())}건{fl}")
        except Unsupported as e:
            print(f"{s['name'][:24]:26s} Unsupported: {e}")

    print("\n== quantifier 고장 × 바인딩 의존 데모 (화재: `==|`→특정 1대 `==`) ==")
    fire = next(s for s in data if s["name"] == "화재 감지 알림")
    mut = fire["code"].replace(
        "(#PresenceSensor #Office).presenceSensor_presence ==| true",
        "(#PresenceSensor #Office #Desk1).presenceSensor_presence == true")
    assert mut != fire["code"]
    for k in (1, 2):
        env = [Dev("sd1", "SmokeDetector", ("Office",)),
               Dev("sp1", "Speaker", ("Office",)),
               Dev("em1", "EmailProvider"), Dev("tp1", "ToastPublisher"),
               Dev("ps1", "PresenceSensor", ("Office",), ("Desk1",))]
        env += [Dev(f"ps{i+2}", "PresenceSensor", ("Office",))
                for i in range(k - 1)]
        ga, _ = ground(parse(fire["code"]), env)
        gb, _ = ground(parse(mut), env)
        r = product_explore(ga, gb, int(fire["period"]))
        print(f"  k={k} (재실센서 {k}대): {r.verdict}"
              f"  상태={r.n_states} step={r.n_steps} {r.seconds:.2f}s")
        for dv in r.divergences[:1]:
            print(f"    ↳ 반례 입력 {dv.input_}")
            print(f"      base: {list(dv.actions_a) or '(무발화)'}")
            print(f"      변형: {list(dv.actions_b) or '(무발화)'}")


if __name__ == "__main__":
    main()
