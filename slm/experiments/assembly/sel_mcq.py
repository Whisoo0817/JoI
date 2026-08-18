# -*- coding: utf-8 -*-
"""③ top-1 선택 객관식 실험 — build_ir의 선택 지점(함수/값 서비스)마다 후보(top-5+규칙 추가)를 보기로 주고 모델이 기호 1토큰으로 고른다.
비교: (a) 규칙만  (b) 객관식만  (c) 규칙 + 게이트(규칙 점수 차 ≤ GATE 이면 객관식) — 절 단위 선택 정확도 + 명령 단위 완전 IR.
모델: MCQ_MODEL=9b(vLLM :8002) | 2b(HF 로짓). 보기 셔플 SHUF회 평균. 결과 sel_mcq_<model>.json"""
import json, os, sys, re, random, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("MAPPED_ONLY", "1"); os.environ.setdefault("RERANK", "1")
import build_ir as B
from skeleton import skeleton
import mcq
from mcq import scores, LETTERS
HERE = B.HERE
SHUF = int(os.environ.get("SHUF", "2")); GATE = float(os.environ.get("GATE", "1.0"))
EFF = B.EFF; AL = B.AL

def build_items():
    """선택 지점 → (kind, cmd, text, cands, gold, rule_pick, margin)"""
    items = []
    for o in B.T:
        if not o["ir_gt"] or (o["cmd"], 0) not in B.MAP: continue
        G = B.gold_of(o); B.TRACE.clear(); ir = B.build(o); tr = list(B.TRACE)
        if skeleton(ir) != skeleton(G): continue
        pf, gf = B.flat(ir["timeline"]), B.flat(G["timeline"])
        if len(pf) != len(gf): continue
        # 순서 정렬: call → func 트레이스 1개, cond → 값 트레이스(부분 수)
        fi = [t for t in tr if t[0] == "func"]; vi = [t for t in tr if t[0] == "value"]
        ok = True; loc = []
        for (po, pd), (go, gd) in zip(pf, gf):
            if po != go: ok = False; break
            if po == "call":
                if not fi: ok = False; break
                t = fi.pop(0); loc.append((t, gd["target"]))
            elif "cond" in gd:
                pa = re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", pd["cond"]); ga = re.findall(r"[A-Z][A-Za-z]+\.[A-Za-z0-9]+", gd["cond"])
                if len(pa) != len(ga): 
                    for _ in pa:
                        if vi: vi.pop(0)
                    continue
                for g in ga:
                    if not vi: ok = False; break
                    t = vi.pop(0); loc.append((t, g))
        if not ok: continue
        for (kind, text, cands, pick, margin), gold in loc:
            items.append(dict(kind=kind, cmd=o["cmd"], text=text, cands=cands, gold=gold, rule=pick, margin=margin))
    return items

def desc(svc):
    k, spec = B.svc_info(svc); cat, name = svc.split(".", 1)
    ko = EFF.get(svc, {}).get("ko_triggers", [])[:6]
    al = AL.get(cat, [])[:3]
    d = f"{svc}  ({', '.join(al)})"
    if ko: d += f" — {', '.join(ko)}"
    if k == "function":
        args = [f"{a['id']}:{a.get('type')}" for a in spec.get("arguments", [])]
        d += f" | 인자: {', '.join(args) if args else '없음'}"
    else:
        d += f" | 값 타입: {spec.get('type')}"
        if spec.get("type") == "ENUM": d += " {" + ", ".join(m.split(" - ")[0] for m in B.members_of(cat, spec.get("format"))[:8]) + "}"
    return d

FEW = int(os.environ.get("FEW", "0")); POOL = []     # few-shot: 같은 kind, 다른 명령의 최근접 항목(문자 2-gram 자카드)
def _bg(t): t = re.sub(r"[\s.,\"']", "", t); return {t[i:i + 2] for i in range(len(t) - 1)}
def neighbors(it, k):
    a = _bg(it["text"]); sc = []
    for p in POOL:
        if p["kind"] != it["kind"] or p["cmd"] == it["cmd"]: continue
        b = _bg(p["text"]); sc.append((len(a & b) / max(1, len(a | b)), p))
    sc.sort(key=lambda x: -x[0]); return [p for _, p in sc[:k]]
def prompt(it, order):
    kind = "호출할 함수(서비스)" if it["kind"] == "func" else "조건에서 읽을 센서/상태 값"
    body = "\n".join(f"{LETTERS[i]}. {desc(it['cands'][j])}" for i, j in enumerate(order))
    ex = ""
    if FEW:
        ex = "참고 예시(절 → 정답 서비스):\n" + "\n".join(f"- \"{p['text']}\" → {p['gold']}" for p in neighbors(it, FEW)) + "\n\n"
    return (f"{ex}사용자 명령: \"{it['cmd']}\"\n대상 절: \"{it['text']}\"\n\n이 절이 뜻하는 {kind}로 가장 알맞은 보기를 하나만 고르시오. "
            f"절에 언급된 기기·동작·측정 대상과 정확히 대응하는 것을 고르고, 켜기/끄기는 Switch, 조명 켜기는 Light.MoveToBrightness, 모드 지정은 *Mode 함수, 말하기는 Speaker.Speak를 우선한다.\n\n{body}\n\n답:")

def mcq_pick(it):
    n = len(it["cands"]); acc = np.zeros(n)
    for s in range(SHUF):
        perm = list(range(n)); random.Random(s).shuffle(perm)
        sc = scores(prompt(it, perm), n)
        for pos, j in enumerate(perm): acc[j] += sc[pos]
    return it["cands"][int(np.argmax(acc))]

if __name__ == "__main__":
    items = build_items()
    LIM = int(os.environ.get("LIM", "0"))
    if LIM: items = items[:LIM]
    print("선택 지점", len(items), collections.Counter(i["kind"] for i in items), "gold∈후보", sum(i["gold"] in i["cands"] for i in items))
    POOL.extend(items)
    for it in items:
        it["mcq"] = mcq_pick(it) if len(it["cands"]) > 1 else it["cands"][0]
        it["gated"] = it["mcq"] if it["margin"] <= GATE else it["rule"]
    json.dump(items, open(os.path.join(HERE, f"sel_mcq_{mcq.MODEL}{'_few' + str(FEW) if FEW else ''}.json"), "w"), ensure_ascii=False, indent=1)
    for kind in ("func", "value", "all"):
        sub = [i for i in items if kind == "all" or i["kind"] == kind]
        n = len(sub); ub = sum(i["gold"] in i["cands"] for i in sub)
        print(f"[{kind}] n={n} 상한(gold∈후보)={ub/n:.3f}  규칙 {sum(i['rule']==i['gold'] for i in sub)/n:.3f}  객관식 {sum(i['mcq']==i['gold'] for i in sub)/n:.3f}  규칙+게이트(≤{GATE}) {sum(i['gated']==i['gold'] for i in sub)/n:.3f}  (게이트 발동 {sum(i['margin']<=GATE for i in sub)})")
    # 명령 단위 완전 IR: 선택 결과 주입 후 build_ir 재평가
    for mode in ("rule", "mcq", "gated"):
        B.OVERRIDE.clear()
        for i in items: B.OVERRIDE[(i["kind"], i["text"])] = i[mode]
        lvl = collections.Counter(); N = 0
        for o in B.T:
            if not o["ir_gt"] or (o["cmd"], 0) not in B.MAP: continue
            N += 1; G = B.gold_of(o); ir = B.build(o)
            if skeleton(ir) != skeleton(G): continue
            pf, gf = B.flat(ir["timeline"]), B.flat(G["timeline"])
            if len(pf) != len(gf): continue
            okT = okC = okV = okA = True
            for (po, pd), (go, gd) in zip(pf, gf):
                if po != go: okT = False; continue
                for key in ("cron", "period", "until", "count", "duration", "for", "edge"):
                    if key in gd: okT &= str(pd.get(key)) == str(gd.get(key))
                if "cond" in gd: okC &= B.cond_ok(pd["cond"], gd["cond"], o["cmd"])
                if "target" in gd:
                    okV &= pd["target"] == gd["target"]
                    if pd["target"] == gd["target"]:
                        a, b = B.cmp_args(pd["args"], gd["args"], gd["target"]); okA &= a == b
            lvl["V"] += okT and okC and okV; lvl["A"] += okT and okC and okV and okA
        print(f"  완전 IR [{mode}] S+T+C+V {lvl['V']}/{N} = {lvl['V']/N:.3f}   +A {lvl['A']}/{N} = {lvl['A']/N:.3f}")
