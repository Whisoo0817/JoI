"""Projections: the graph is queried, never browsed.

Raw edges are machine material. 온습도 alone has 278,516 of them because an
edge is (state × input combo × dwell), and the input dimension is a product.
Nobody reads that, and nobody should: the count says nothing about how
complicated the automation is. Its 17 states and handful of decision paths do.

Three projections, each answering a different question:

  paths()   the code's own decision structure — group edges by the branch
            path the tick actually took. Intensional by construction: a
            coupled guard like `temp_avg > max_temp` is ONE column, so the
            arithmetic that defeats per-axis value tables disappears here.
  behavior()  one row per (source state, action set) with the input cells
            that produce it. Extensional, needed when you want to see the
            values, and it marks conditions that are not a product of axes.
  preimage()  for one action, what must hold for it to happen — the
            projection deployment replay uses to explain silence.

Compression is not summarization: every projection is a quotient of the
edge set, and the rows partition it. `paths()` reports the edge count each
row stands for so nothing is silently dropped.

Run:  python -m explorer.project
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from . import expr as expr_mod
from . import joi_parser as jp
from .explore import explore, fired_key
from .predicates import walk_stmts


# ── Rendering the code's own conditions ──────────────────────────────────────

def _txt(node) -> str:
    if isinstance(node, expr_mod.Lit):
        v = node.value
        return f'"{v}"' if isinstance(v, str) else f"{v:g}" if isinstance(
            v, float) else str(v)
    if isinstance(node, expr_mod.VarRef):
        return node.name
    if isinstance(node, expr_mod.UnaryOp):
        return f"{node.op} {_txt(node.operand)}"
    if isinstance(node, expr_mod.BinaryOp):
        return f"{_txt(node.left)} {node.op} {_txt(node.right)}"
    if isinstance(node, expr_mod.FuncCall):
        return f"{node.name}({', '.join(_txt(a) for a in node.args)})"
    if isinstance(node, (expr_mod.QuantRef, expr_mod.DeviceRef)):
        tags = getattr(node, "tags", ())
        q = (getattr(node, "quant", None) or "")
        sel = "".join(f"#{t}" for t in tags) or node.key
        return f"{q}({sel}).{getattr(node, 'member', '') or node.key}"
    if isinstance(node, expr_mod.ClockRef):
        return f"clock.{node.field}"
    if isinstance(node, jp.CallExpr):
        sel = "".join(f"#{t}" for t in node.tags) or node.service
        q = node.quant or ""
        arg = "" if node.args is None else \
            f"({', '.join(_txt(a) for a in node.args)})"
        return f"{q}({sel}).{node.method}{arg}"
    return repr(node)


def guard_texts(stmts: list) -> dict[int, str]:
    """id(IfStmt) → the condition as written."""
    return {id(s): _txt(s.cond) for s in walk_stmts(stmts)
            if isinstance(s, jp.IfStmt)}


def act_sig(acts) -> tuple:
    out = []
    for a in acts:
        tgt = "+".join(a.target) if a.target else a.service
        arg = ""
        if a.method.startswith("set") and a.args:
            arg = f"({a.args[0]})"
        out.append(f"{tgt}.{a.method}{arg}")
    return tuple(sorted(out))


@dataclass
class PathRow:
    guards: tuple           # ((condition text, taken), ...) in order
    actions: tuple
    edges: int = 0
    states: set = field(default_factory=set)
    dwells: set = field(default_factory=set)
    keys: set = field(default_factory=set)   # fired_key identities


def paths(stmts: list, graph) -> list[PathRow]:
    """Quotient the edge set by (decision path, action set)."""
    txt = guard_texts(stmts)
    rows: dict[tuple, PathRow] = {}
    for (src, dst, dw, acts), gs in zip(graph.edges, graph.edge_guards):
        path = tuple((txt.get(gid, "?"), t) for gid, t in gs)
        sig = act_sig(acts)
        r = rows.setdefault((path, sig), PathRow(path, sig))
        r.edges += 1
        r.states.add(src)
        r.dwells.add(dw)
        r.keys |= {fired_key(a) for a in acts}
    return sorted(rows.values(), key=lambda r: (-len(r.actions), -r.edges))


def preimage(stmts: list, graph, action_key: tuple) -> list[PathRow]:
    """Decision paths that emit one specific action."""
    return [r for r in paths(stmts, graph) if action_key in r.keys]


def essential(rows: list[PathRow]) -> tuple[list, list]:
    """Literals shared by EVERY path that emits the action (necessary
    conditions), and the ones that vary (irrelevant to this action).
    Turns a 157-row unrolling back into one readable sentence."""
    if not rows:
        return [], []
    sets = [set(r.guards) for r in rows]
    common = set.intersection(*sets)
    varying = sorted({g for s in sets for g in s} - common)
    return sorted(common), varying


def render_action(stmts: list, graph, action_key: tuple) -> str:
    rows = preimage(stmts, graph, action_key)
    if not rows:
        return "  (이 액션을 내는 경로 없음 = VACUOUS)"
    com, var = essential(rows)
    cond = " ∧ ".join(g if t else f"¬({g})" for g, t in com) or "(무조건)"
    n = sum(r.edges for r in rows)
    out = [f"  필수 조건: {cond}",
           f"  경로 {len(rows)}개 · 엣지 {n:,}"]
    if var:
        out.append(f"  이 액션과 무관하게 갈리는 술어 {len(var)}개"
                   f" (예: {var[0][0][:46]})")
    return "\n".join(out)


def render(rows: list[PathRow], total_edges: int, limit: int = 0) -> str:
    out = []
    shown = rows[:limit] if limit else rows
    for r in shown:
        cond = " ∧ ".join(g if t else f"¬({g})" for g, t in r.guards) or "(무조건)"
        dw = sorted(r.dwells)
        span = f"{dw[0] // 1000}s" if len(dw) == 1 else \
            f"{dw[0] // 1000}~{dw[-1] // 1000}s"
        out.append(f"  {cond}")
        out.append(f"    → {'; '.join(r.actions) or '(무발화)'}"
                   f"   [엣지 {r.edges:,} · 상태 {len(r.states)} · dwell {span}]")
    if limit and len(rows) > limit:
        rest = sum(r.edges for r in rows[limit:])
        out.append(f"  ... 그 외 {len(rows) - limit}행 (엣지 {rest:,})")
    covered = sum(r.edges for r in rows)
    out.append(f"  [행 {len(rows)}개가 엣지 {covered:,}/{total_edges:,}를 분할]")
    return "\n".join(out)


def main() -> None:
    import json

    from adapt.inventory import base_office
    from .ground import from_adapt, ground
    from .interp import parse

    devs = from_adapt(base_office())
    data = json.load(open("paper_v2/joi_automation_codes.json"))
    for name in ("온습도 자동 제어", "보안모드 자동제어", "재실기반 절전 제어"):
        s = next(x for x in data if x["name"] == name)
        stmts, _ = ground(parse(s["code"]), devs)
        g = explore(stmts, int(s["period"]), keep_graph=True)
        rows = paths(stmts, g)
        firing = [r for r in rows if r.actions]
        print(f"\n=== {name} ===")
        print(f"상태 {g.n_states} · 원시 엣지 {g.n_edges:,} → 경로행 {len(rows)}"
              f" (발화 {len(firing)} / 무발화 {len(rows) - len(firing)})")
        print(render(firing, g.n_edges, limit=2))
        for key in sorted(g.fired)[:2]:
            print(f"  ── 액션 역상: {key[2] and '#' + '#'.join(key[2])}"
                  f".{key[1]}")
            print(render_action(stmts, g, key))


if __name__ == "__main__":
    main()
