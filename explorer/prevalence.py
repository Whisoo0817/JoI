"""미지원 무늬 발생 빈도 측정 — full 지원 여부 결정용 (P1 Day 2 입력).

게이트가 쓰는 것과 같은 캐시 정답쌍(IR×JoI)을 돌며, 강제(enforce) 없이
features 탐지기만 걸어 무늬별 건수를 IR 쪽/JoI 쪽 나눠 센다. 아울러
"독립 다중 센서 and/or"(원자별로는 맨 읽기 vs 상수인 조건이 여러 키에
걸친 행 — 지금도 정확한 경우)를 따로 세어 탐지기가 이를 오탐하지 않는지
확인한다. product 하네스 corpus(8개 시나리오)도 같이 센다.

Run:  python3 -m explorer.prevalence      (joi/ 에서)
"""

from __future__ import annotations

import glob
import json
from collections import Counter

from . import expr as expr_mod
from .features import analyze_ir, analyze_stmts
from .interp import Unsupported, parse
from .predicates import CMP_OPS, classify_vars, stmt_exprs, walk_stmts


def _indep_multikey_cond(stmts, vars_) -> bool:
    """무늬 탐지 없이도 정확한 '독립 다중 센서 and/or' — 한 조건 트리 안에
    서로 다른 읽기 키의 (맨 읽기 vs 상수) 원자가 2개 이상."""
    from .explore import _read_key
    from .predicates import var_defs, _fold_with_params
    defs = var_defs(stmts)

    def resolve(node, depth=0):
        if depth > 4 or not isinstance(node, expr_mod.VarRef):
            return node
        vi = vars_.get(node.name)
        if vi is not None and vi.role == "wire" \
                and len(defs.get(node.name, [])) == 1:
            return resolve(defs[node.name][0], depth + 1)
        return node

    def keys_of(node, acc):
        if isinstance(node, expr_mod.BinaryOp):
            if node.op in ("and", "or"):
                keys_of(node.left, acc)
                keys_of(node.right, acc)
            elif node.op in CMP_OPS:
                for side, other in ((node.left, node.right),
                                    (node.right, node.left)):
                    if _fold_with_params(other, vars_) is not None:
                        k = _read_key(resolve(side))
                        if k is not None:
                            acc.add(k)
        elif isinstance(node, expr_mod.UnaryOp):
            keys_of(node.operand, acc)

    for s in walk_stmts(stmts):
        for e in stmt_exprs(s):
            acc: set = set()
            keys_of(e, acc)
            if len(acc) >= 2:
                return True
    return False


def main() -> None:
    from .gate import devs_of, ground, load_rows, parse_binding, pick_by_rule, \
        reground_ir
    from .ir_step import IrRunner

    rows = load_rows()
    ir_kinds, joi_kinds = Counter(), Counter()
    rows_hit: dict[str, list] = {}
    n_pairs = n_indep = n_err = 0
    indep_flagged: list[str] = []

    for f in sorted(glob.glob("paper/simulators/cache/*.json")):
        key = f.rsplit("/", 1)[-1][:-5]
        d = json.load(open(f))
        jb = d.get("joi_block")
        r = rows.get(key)
        if not jb or r is None:
            continue
        ir = json.loads(r["ir_gt"])
        if json.dumps(d.get("ir"), sort_keys=True) \
                != json.dumps(ir, sort_keys=True):
            continue
        n_pairs += 1
        feats_here: list = []
        try:
            cron = (jb.get("cron") or "").strip()
            if cron and cron != "x":     # gate_pair와 동일한 cron 앵커 소거
                tl = [dict(t) for t in (ir.get("timeline") or [])]
                if tl and tl[0].get("op") == "start_at":
                    tl[0] = {"op": "start_at", "anchor": "now"}
                ir = {**ir, "timeline": tl}
            new_ir, name_map, bind, _ = reground_ir(
                ir, json.loads(r.get("binding_gt") or "{}"))
            fi = analyze_ir(IrRunner(new_ir, name_map=name_map,
                                     bind=bind).prog)
            for x in fi:
                ir_kinds[x.kind] += 1
            feats_here += [("IR", x) for x in fi]
        except (Unsupported, Exception) as e:  # noqa: BLE001 — 측정은 계속
            ir_kinds[f"(분석불가: {type(e).__name__})"] += 1
            n_err += 1
        try:
            devices = json.loads(r["connected_devices"])
            gstmts, _ = ground(parse(jb["script"]), devs_of(devices),
                               pick=pick_by_rule)
            vars_ = classify_vars(gstmts)
            fj = analyze_stmts(gstmts, vars_)
            for x in fj:
                joi_kinds[x.kind] += 1
            feats_here += [("JoI", x) for x in fj]
            if _indep_multikey_cond(gstmts, vars_):
                n_indep += 1
                if fj:
                    indep_flagged.append(key)
        except (Unsupported, Exception) as e:  # noqa: BLE001
            joi_kinds[f"(분석불가: {type(e).__name__})"] += 1
            n_err += 1
        if feats_here:
            rows_hit[key] = feats_here

    print(f"정답쌍 {n_pairs}건 측정 (분석 불가 {n_err}건 포함)")
    print(f"\nIR 쪽 무늬:  {dict(ir_kinds) or '없음'}")
    print(f"JoI 쪽 무늬: {dict(joi_kinds) or '없음'}")
    print(f"\n독립 다중 센서 and/or 행: {n_indep}건 "
          f"(그중 탐지기에 걸린 행: {indep_flagged or '0건 — 오탐 없음'})")
    print(f"\n무늬 있는 행 {len(rows_hit)}건:")
    for k in sorted(rows_hit):
        det = "; ".join(f"{side}:{x.kind}" for side, x in rows_hit[k])
        print(f"  {k}: {det}")

    print("\n== product 하네스 corpus (8 시나리오) ==")
    data = json.load(open("explorer/corpus/joi_automation_codes.json"))
    for s in data:
        try:
            stmts = parse(s["code"])
            fs = analyze_stmts(stmts, classify_vars(stmts))
            tag = "; ".join(f"{x.kind}: {x.detail[:40]}" for x in fs) or "없음"
        except (Unsupported, Exception) as e:  # noqa: BLE001
            tag = f"(분석불가: {e})"
        print(f"  {s['name'][:30]:30s} {tag}")


if __name__ == "__main__":
    main()
