# -*- coding: utf-8 -*-
"""P/P 종단 IR — 예측 경계(경계 head) + 예측 타입·mods(타입 head, OOF; pred_types.json "pred") 절로 build_ir를 돌려 완전 IR 평가.
매핑: 예측 절 텍스트가 gold 절과 같으면 그 절의 ranked/cond_parts 재사용; 병합·분할된 절은 겹치는 gold 절들의 후보를 순위 교대로 합침(재검색 없음, 근사).
출력: 구조/슬롯/완전 IR (G/G 대비), 실패 원인 분류(경계 / 타입·mods / 규칙)."""
import json, os, sys, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("MAPPED_ONLY", "1")
import build_ir as B
from skeleton import skeleton
HERE = B.HERE
PT = json.load(open(os.path.join(HERE, "pred_types.json")))

def norm(t): return re.sub(r"[\s.,]", "", t)
def merge_ranked(lists):
    out = []
    for k in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if k < len(l) and l[k] not in out: out.append(l[k])
    return out
def make_pred_cmd(o):
    """예측 절로 명령 사본을 만들고 MAP/CP 항목을 사본 키로 등록"""
    key = o["cmd"] + "​"; segs = PT[str(o["i"])]["pred"]
    gold_segs = o["segments"]
    o2 = {"i": o["i"], "cmd": key, "ir_gt": o["ir_gt"], "cat": o.get("cat"), "segments": [{"text": s["text"], "type": s["type"], "mods": sorted(s["mods"])} for s in segs]}
    B.CP[key] = {}
    for j, s in enumerate(segs):
        ns = norm(s["text"]); ov = []
        for jg, g in enumerate(gold_segs):
            ng = norm(g["text"])
            if ns == ng or ns in ng or ng in ns: ov.append(jg)
        if not ov:   # 부분 겹침(경계가 단어 중간): 공통 부분 문자열 길이로
            for jg, g in enumerate(gold_segs):
                ng = norm(g["text"])
                if len(set(re.findall(r"..", ns)) & set(re.findall(r"..", ng))) >= 3: ov.append(jg)
        B.MAP[(key, j)] = merge_ranked([B.MAP.get((o["cmd"], jg), []) for jg in ov])
        exact = [jg for jg in ov if norm(gold_segs[jg]["text"]) == ns]
        if exact and str(exact[0]) in B.CP.get(o["cmd"], {}): B.CP[key][str(j)] = B.CP[o["cmd"]][str(exact[0])]
        elif s["type"] in ("COND", "TRIG"):
            parts = [x for jg in ov for x in B.CP.get(o["cmd"], {}).get(str(jg), []) if gold_segs[jg]["type"] in ("COND", "TRIG") and norm(x["part"]) in ns]
            if parts: B.CP[key][str(j)] = parts
    return o2

def evaluate(o, o2, G):
    ir = B.build(o2)
    if os.environ.get("LENIENT", "1") == "1": ir, G = B.canon_ir(ir), B.canon_ir(G)
    if skeleton(ir) != skeleton(G): return "S", ir
    pf, gf = B.flat(ir["timeline"]), B.flat(G["timeline"])
    if len(pf) != len(gf): return "S", ir
    okT = okC = okV = okA = True
    for (po, pd), (go, gd) in zip(pf, gf):
        if po != go: return "S", ir
        for key in ("cron", "period", "until", "count", "duration", "for", "edge"):
            if key in gd: okT &= str(pd.get(key)) == str(gd.get(key))
        if "cond" in gd: okC &= B.cond_ok(pd["cond"], gd["cond"], o["cmd"])
        if "target" in gd:
            v_, a_ = B.call_ok(pd, gd); okV &= v_; okA &= a_
    if not okT: return "T", ir
    if not okC: return "C", ir
    if not okV: return "V", ir
    if not okA: return "A", ir
    return "OK", ir

if __name__ == "__main__":
    res = collections.Counter(); resG = collections.Counter(); N = 0; cause = collections.Counter(); ex = collections.defaultdict(list); out = []
    for o in B.T:
        if not o["ir_gt"] or o["cmd"] not in B.RC or str(o["i"]) not in PT: continue
        N += 1; G = B.gold_of(o)
        rG, _ = evaluate(o, o, G); resG[rG] += 1
        o2 = make_pred_cmd(o); r, ir = evaluate(o, o2, G); res[r] += 1
        out.append({"i": o["i"], "cmd": o["cmd"], "pred_segs": o2["segments"], "result": r, "ir_pred": ir})
        if r != "OK":
            gs = [(s["text"], s["type"], sorted(s["mods"])) for s in o["segments"]]; ps = [(s["text"], s["type"], s["mods"]) for s in o2["segments"]]
            if [g[0] for g in gs] != [p[0] for p in ps]: c = "경계"
            elif gs != ps: c = "타입/mods"
            elif rG != "OK": c = "규칙(G/G도 실패)"
            else: c = "매핑근사"
            cause[c] += 1
            if len(ex[c]) < 5: ex[c].append((o["cmd"], r, " ‖ ".join(f"[{t}{'/'+'+'.join(m) if m else ''}] {x}" for x, t, m in ps)))
    json.dump(out, open(os.path.join(HERE, "ir_pred_pp.json"), "w"), ensure_ascii=False, indent=1)
    def cum(c):
        n = sum(c.values()); s = 0; row = {}
        for k in ("OK", "A", "V", "C", "T", "S"): pass
        okS = n - c["S"]; okT = okS - c["T"]; okC = okT - c["C"]; okV = okC - c["V"]; okA = okV - c["A"]
        return f"S {okS/n:.3f}  S+T {okT/n:.3f}  S+T+C {okC/n:.3f}  S+T+C+V {okV/n:.3f}  완전 {okA/n:.3f}"
    print(f"명령 {N}")
    print("G/G:", cum(resG)); print("P/P:", cum(res))
    print("P/P 실패 원인:", dict(cause))
    for c, v in ex.items():
        print(f"\n[{c}]")
        for e in v: print("  ", e[1], e[0]); print("      ", e[2])
