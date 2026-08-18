# -*- coding: utf-8 -*-
"""③' 2B LoRA 객관식 선택기 — sel_mcq 항목(선택 지점)으로 5-fold(명령 i%5) 학습·예측. 폴드마다 LoRA 재초기화.
출력: sel_mcq_2b_lora.json (항목별 mcq 예측 = OOF) → sel_mcq.py와 같은 비교표 + 완전 IR."""
import os, sys, json, random, time, math, collections
os.environ.setdefault("MCQ_MODEL", "2b")
import torch, torch.nn as nn, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sel_mcq as SM, sft_mcq
from sft_mcq import LoRA, inject, LETTERS, tok, model, LID, letter_logits
import build_ir as B
from skeleton import skeleton
HERE = B.HERE
LR, EPOCHS, VAR = float(os.environ.get("LR", "2e-4")), int(os.environ.get("EPOCHS", "2")), int(os.environ.get("VAR", "2"))
GATE = float(os.environ.get("GATE", "1.0"))

for p_ in model.parameters(): p_.requires_grad_(False)
print("LoRA 주입", inject(model))
loras = [m for m in model.modules() if isinstance(m, LoRA)]
params = [p_ for n_, p_ in model.named_parameters() if ".A.weight" in n_ or ".B.weight" in n_]
if hasattr(model, "gradient_checkpointing_enable"): model.gradient_checkpointing_enable(); model.config.use_cache = False
def reset():
    for m in loras:
        nn.init.kaiming_uniform_(m.A.weight, a=math.sqrt(5)); nn.init.zeros_(m.B.weight)

items = SM.build_items()
cmd_i = {o["cmd"]: o["i"] for o in B.T}
for it in items: it["fold"] = cmd_i[it["cmd"]] % 5
print("선택 지점", len(items), collections.Counter(i["fold"] for i in items))
t0 = time.time()
FOLDS = int(os.environ.get("FOLDS", "5"))
for f in range(FOLDS):
    reset(); tr = [i for i in items if i["fold"] != f and len(i["cands"]) > 1]; te = [i for i in items if i["fold"] == f]
    ex = []
    for k, it in enumerate(tr):
        if it["gold"] not in it["cands"]: continue
        for v in range(VAR):
            perm = list(range(len(it["cands"]))); random.Random(100 * v + k).shuffle(perm)
            ex.append((SM.prompt(it, perm), perm.index(it["cands"].index(it["gold"])), len(perm)))
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=0.0); model.train()
    for ep in range(EPOCHS):
        random.Random(ep).shuffle(ex); tot = 0.0; hit = 0
        for p, gold, n in ex:
            lg = letter_logits(p, n); loss = nn.functional.cross_entropy(lg[None], torch.tensor([gold], device="cuda"))
            loss.backward(); opt.step(); opt.zero_grad(); tot += loss.item(); hit += int(lg.argmax().item() == gold)
        print(f"fold {f} epoch {ep+1}: loss {tot/len(ex):.3f} train acc {hit/len(ex):.3f} ({time.time()-t0:.0f}s)", flush=True)
    model.eval()
    def scores(p, n):
        with torch.no_grad(): return letter_logits(p, n).tolist()
    SM.scores = scores
    for it in te:
        it["mcq"] = SM.mcq_pick(it) if len(it["cands"]) > 1 else it["cands"][0]
        it["gated"] = it["mcq"] if it["margin"] <= GATE else it["rule"]
    print(f"fold {f}: held-out 규칙 {np.mean([i['rule']==i['gold'] for i in te]):.3f} 객관식 {np.mean([i['mcq']==i['gold'] for i in te]):.3f}", flush=True)
items = [i for i in items if "mcq" in i]
json.dump(items, open(os.path.join(HERE, "sel_mcq_2b_lora.json"), "w"), ensure_ascii=False, indent=1)
for kind in ("func", "value", "all"):
    sub = [i for i in items if kind == "all" or i["kind"] == kind]; n = len(sub)
    print(f"[{kind}] n={n} 규칙 {sum(i['rule']==i['gold'] for i in sub)/n:.3f}  2B-LoRA 객관식(OOF) {sum(i['mcq']==i['gold'] for i in sub)/n:.3f}  규칙+게이트 {sum(i['gated']==i['gold'] for i in sub)/n:.3f}")
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
            if "cond" in gd: okC &= pd["cond"] == gd["cond"]
            if "target" in gd:
                okV &= pd["target"] == gd["target"]
                if pd["target"] == gd["target"]:
                    a, b = B.cmp_args(pd["args"], gd["args"], gd["target"]); okA &= a == b
        lvl["V"] += okT and okC and okV; lvl["A"] += okT and okC and okV and okA
    print(f"  완전 IR [{mode}] S+T+C+V {lvl['V']}/{N} = {lvl['V']/N:.3f}   +A {lvl['A']}/{N} = {lvl['A']/N:.3f}")
