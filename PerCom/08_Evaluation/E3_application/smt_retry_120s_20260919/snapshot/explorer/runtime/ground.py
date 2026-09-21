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

Matching: every selector tag must equal the device's id, its type, one of
its spaces, or one of its instance_tags (id matching added 2026-08-14 —
The mapper emits (#<device-id>) selectors for siblings no tag combo can
split, §9.12). Offline devices don't match (device
failure = binding change, P2). Clock/GlobalVariable are ambient, never
grounded. A selector matching NOTHING stays as-is ("floating": the tag set
keeps acting as one implicit device) and is reported — the honest gap list
between the script and this inventory. Singular selectors matching >1
device raise: choosing among them is the binding pipeline's job, not a
default the simulator should invent.

The library takes plain device tuples; only the __main__ demo imports the
adapt/ inventory (keeps this package self-contained).

Run:  python -m explorer.runtime.ground   (bindings report + grounded exploration
                                    + the k=1 vs k=2 quantifier demo)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from explorer.runtime import expr as expr_mod
from explorer.runtime import joi_parser as jp
from explorer.runtime.expr import canonical_key
from explorer.runtime.interp import Unsupported

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
        # 기기 id도 매칭한다 — 태그 조합으로 정확히 못 가르는 형제 기기를
        # 매핑이 (#<기기id>)로 분해해 내보내므로
        if all(t == d.id or t == d.type or t in d.spaces or t in d.tags
               for t in tags):
            out.append(d)
    return out


@dataclass
class GroundReport:
    bindings: dict = field(default_factory=dict)    # selector → [ids]
    floating: list = field(default_factory=list)    # selectors with 0 matches


class _G:
    def __init__(self, devs: list[Dev], pick=None, binding=None, assignment=None):
        self.devs = devs
        # B5: selector occurrence (id of its tag tuple) -> index of the binding device set to use
        self.assignment = assignment or {}
        self.pick = pick          # 단수 셀렉터가 여러 대와 맞을 때 고르는 규약
        self.report = GroundReport()
        # Binding decision (whisoo 2026-09-14, E2 BINDING_DECISION B1):
        # service(lower) -> distinct [(device set, ids in binding order, quantifier)]
        self.binding: dict[str, list] = {}
        for svc, slots in (binding or {}).items():
            entry = self.binding.setdefault(svc.lower(), [])
            for ids, quant in slots:
                ids = list(dict.fromkeys(ids))
                same = [i for i, e in enumerate(entry) if e[0] == frozenset(ids)]
                if not same:
                    entry.append((frozenset(ids), ids, quant))
                elif entry[same[0]][2] is None and quant is not None:
                    entry[same[0]] = (entry[same[0]][0], entry[same[0]][1], quant)

    def _bound(self, service: str, tags: tuple):
        """B1: (devices, binding quantifier) for a selector of a bound service, else None."""
        if not tags or any(t in AMBIENT for t in tags):
            return None
        entry = self.binding.get((service or "").lower())
        if not entry:
            return None
        if len(entry) == 1:
            chosen = entry[0]
        elif id(tags) in self.assignment:
            chosen = entry[self.assignment[id(tags)]]
        else:
            m = {d.id for d in match(self.devs, tuple(tags))}
            exact = [e for e in entry if e[0] == m]
            holding = [e for e in entry if m and m <= e[0]]
            if exact:
                chosen = exact[0]
            elif len(holding) == 1:
                chosen = holding[0]
            else:
                return None
        by_id = {d.id: d for d in self.devs if d.online}
        insts = [by_id[i] for i in chosen[1] if i in by_id]
        if not insts:
            return None
        self.report.bindings["#" + "#".join(tags)] = [d.id for d in insts]
        return insts, chosen[2]

    def _one(self, m: list[Dev], what: str) -> Dev:
        if len(m) == 1:
            return m[0]
        if self.pick is not None:
            return self.pick(m)
        raise Unsupported(
            f"{what} matches {len(m)} devices "
            f"(binding must choose): {[d.id for d in m]}")

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
        """(matches, service, member, binding quantifier) if node is a selector attribute read."""
        if isinstance(node, jp.CallExpr) and node.args is None and node.tags:
            bound = self._bound(canonical_key(node.service, node.method)[0], node.tags)
            if bound is not None:
                return bound[0], node.service, node.method, bound[1]
            m = self._sel(node.tags)
            return None if m is None else (m, node.service, node.method, None)
        if isinstance(node, expr_mod.QuantRef) and node.tags:
            svc = node.tags[-1]
            bound = self._bound(node.key.split(".", 1)[0], node.tags)
            if bound is not None:
                return bound[0], svc, node.member or "", bound[1]
            m = self._sel(node.tags)
            return None if m is None else (m, svc, node.member or "", None)
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
                m, svc, member, bquant = sr
                quant = getattr(side, "quant", None)
                # B1: an explicit JoI quantifier stays; the binding's decides only when the JoI has none
                by_binding = (len(m) > 1 and bquant in ("all", "any")
                              and not quantified and quant not in ("all", "any"))
                if base in ("==", "!=", "<", ">", "<=", ">=") and (by_binding or quantified or quant in ("all", "any")):
                    if by_binding:      # B1: the IR binding's quantifier decides
                        join = "or" if bquant == "any" else "and"
                    else:
                        join = "or" if quantified or quant == "any" else "and"
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
            m, svc, member, binding_quant = sr
            quant = getattr(node, "quant", None) or binding_quant
            if len(m) > 1 and quant in ("any", "all"):
                # A bare grouped Boolean is its explicit truth comparison:
                # any(X) -> OR(X_i == true), all(X) -> AND(X_i == true).
                # Catalog validation later rejects non-Boolean uses; this step
                # only removes frontend syntax ambiguity.
                terms = [expr_mod.BinaryOp(
                    "==", expr_mod.DeviceRef(self._key(inst, svc, member)),
                    expr_mod.Lit(True)) for inst in m]
                out = terms[0]
                join = "or" if quant == "any" else "and"
                for term in terms[1:]:
                    out = expr_mod.BinaryOp(join, out, term)
                return out
            inst = self._one(m, "selector in scalar position")
            return expr_mod.DeviceRef(self._key(inst, svc, member))
        if isinstance(node, jp.CallExpr) and node.args is not None:
            return self._ground_call(node, expect_one=True)[0]
        return node

    # calls / statements ------------------------------------------------------
    def _ground_call(self, call: jp.CallExpr, expect_one: bool) -> list:
        """Always returns a list of grounded CallExpr (1 per instance)."""
        args = [self.ge(a) for a in (call.args or [])]
        bound = self._bound(canonical_key(call.service, call.method)[0], call.tags) if call.tags else None
        if bound is not None:
            # B1: a bound service calls the binding devices; a selector naming only
            # some of them keeps those (split lines), anything else uses the binding
            m = bound[0]
            named = [d for d in match(self.devs, tuple(call.tags)) if d.online]
            if named and {d.id for d in named} <= {d.id for d in m}:
                m = named
            insts = [self._one(m, "call selector")] if expect_one else m
        else:
            m = self._sel(call.tags) if call.tags else None
            if m is None:
                return [jp.CallExpr(call.service, call.method, args,
                                    tags=call.tags, quant=call.quant)]
            if len(m) > 1 and call.quant == "any":
                raise Unsupported("any method call is not an existential property comparison")
            insts = m if (call.quant == "all" and not expect_one) else None
            if insts is None:
                insts = [self._one(m, "call selector")]
        return [jp.CallExpr(call.service, call.method, args,
                            tags=(inst.id,), quant=None,
                            fanout=(i, len(insts)) if len(insts) > 1 else None,
                            input_key=self._key(inst, call.service, call.method))
                for i, inst in enumerate(insts)]

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
            from explorer.analysis.predicates import walk_stmts
            for child in walk_stmts(stmt.body):
                if isinstance(child, (jp.Break, jp.WaitUntil, jp.Delay, jp.ForEach)) or (
                        isinstance(child, jp.Assign) and child.name == stmt.var):
                    raise Unsupported("ForEach unrolling requires no break/blocking/nesting or iterator assignment")
            sr = self._sel_read(stmt.source)
            if sr is None:
                raise Unsupported(
                    f"ForEach selector not in inventory: {stmt.source}")
            m, svc, member, _ = sr
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
                           tags=node.tags, quant=node.quant,
                           fanout=node.fanout, input_key=node.input_key)
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


def ground(stmts: list, devs: list[Dev], pick=None, binding=None, assignment=None) -> tuple[list, GroundReport]:
    """`binding`: parse_binding output of the confirmed IR binding (B1), or None.
    `assignment`: {id(selector tag tuple): device-set index} for B5 selector assignments."""
    g = _G(devs, pick, binding, assignment)
    return g._body(stmts), g.report


# ── Demo driver ──────────────────────────────────────────────────────────────

def main() -> None:
    import json
    from adapt.inventory import base_office
    from explorer.runtime.interp import parse
    from explorer.analysis.explore import explore
    from explorer.verification.product import product_explore

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
