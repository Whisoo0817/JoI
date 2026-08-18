# -*- coding: utf-8 -*-
"""① top-1 선택 실패 분류 — build_ir의 target/cond.attr 실패를 절 단위로 뽑아 (텍스트, 예측, 정답, 정답 순위, 형제 그룹) 표로 저장.
형제 그룹: same_cat(같은 카테고리 다른 함수/값) / other_cat(다른 카테고리) / not_in_top5 / state_conv(조건 상태 관례) 등."""
import json, os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("MAPPED_ONLY", "1")
import build_ir as B
from skeleton import skeleton
rows = []
for o in B.T:
    if not o["ir_gt"] or (o["cmd"], 0) not in B.MAP: continue
    G = B.gold_of(o); ir = B.build(o)
    if skeleton(ir) != skeleton(G): continue
    pf, gf = B.flat(ir["timeline"]), B.flat(G["timeline"])
    if len(pf) != len(gf): continue
    S = o["segments"]
    # 절 → 노드 대응은 순서대로: call/wait/if 노드에 절 텍스트를 붙이기 위해 build 시 텍스트를 다시 추적하기 어렵다 → 예측 IR을 다시 만들며 owner를 기록
    for (po, pd), (go, gd) in zip(pf, gf):
        if po != go: continue
        if "target" in gd and pd["target"] != gd["target"]:
            rows.append(("target", o["cmd"], pd["target"], gd["target"]))
        if "cond" in gd:
            ga = sorted(re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", gd["cond"])); pa = sorted(re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", pd["cond"]))
            if ga and ga != pa: rows.append(("cond", o["cmd"], pd["cond"], gd["cond"]))
# 절 텍스트·순위 붙이기: 명령 내 절 후보 목록에서 gold 서비스가 들어있는 절을 찾음
def find_seg(cmd, gold_svc, pred_svc):
    o = next(x for x in B.T if x["cmd"] == cmd)
    best = None
    for j, s in enumerate(o["segments"]):
        ranked = B.MAP.get((cmd, j), [])
        cp = B.CP.get(cmd, {}).get(str(j))
        if cp:
            for x in cp:
                if gold_svc in x["ranked"] or pred_svc in x["ranked"]:
                    return x["part"], x["ranked"], (x["ranked"].index(gold_svc) if gold_svc in x["ranked"] else -1)
        if pred_svc in ranked and (best is None or gold_svc in ranked):
            best = (s["text"], ranked, ranked.index(gold_svc) if gold_svc in ranked else -1)
        elif gold_svc in ranked and best is None:
            best = (s["text"], ranked, ranked.index(gold_svc))
    return best or ("?", [], -1)
out = []
for kind, cmd, p, g in rows:
    if kind == "target":
        text, ranked, gr = find_seg(cmd, g, p)
        pc, gc = p.split(".")[0], g.split(".")[0]
        grp = "not_in_top5" if gr < 0 else ("same_cat" if pc == gc else "other_cat")
        out.append(dict(kind=kind, cmd=cmd, text=text, pred=p, gold=g, gold_rank=gr, group=grp, ranked=ranked))
    else:
        ga = re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", g); pa = re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", p)
        for gs in ga:
            if gs in pa: continue
            ps = next((x for x in pa if x not in ga), pa[0] if pa else "?")
            text, ranked, gr = find_seg(cmd, gs, ps)
            pc, gc = ps.split(".")[0], gs.split(".")[0]
            grp = "not_in_top5" if gr < 0 else ("same_cat" if pc == gc else "other_cat")
            if gs.endswith("Switch.Switch") or gs.split(".")[1] == "Switch": grp += "|state_conv"
            out.append(dict(kind=kind, cmd=cmd, text=text, pred=ps, gold=gs, gold_rank=gr, group=grp, ranked=ranked, pcond=p, gcond=g))
json.dump(out, open(os.path.join(B.HERE, "sel_failures.json"), "w"), ensure_ascii=False, indent=1)
C = collections.Counter((r["kind"], r["group"]) for r in out)
print("실패 절", len(out)); 
for k, v in sorted(C.items()): print(" ", k, v)
print("\n형제 쌍(pred→gold) 빈도")
for (p, g), n in collections.Counter((r["pred"], r["gold"]) for r in out).most_common(40): print(f"  {n:2d} {p} → {g}")
print("\n[예]")
for r in out[:60]:
    print(f"  {r['kind']:6s} {r['group']:22s} r{r['gold_rank']} | {r['text'][:40]:40s} | {r['pred']} → {r['gold']}")
