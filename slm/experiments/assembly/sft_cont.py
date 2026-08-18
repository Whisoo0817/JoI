# -*- coding: utf-8 -*-
"""이어서 학습 — lora_mcq.pt에서 시작, 합성(필러·REF·후치) + 원본 재생 1 epoch. 평가: held-out 20% + challenge."""
import os, sys, json, random, time
os.environ.setdefault("MCQ_MODEL", "2b")
import torch, torch.nn as nn
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcq, challenge, synth_struct
from mcq import prompt, model
from sft_mcq import inject, build_items, letter_logits
from candidates import make_candidates
HERE = os.path.dirname(os.path.abspath(__file__))
LR = float(os.environ.get("LR", "2e-5")); REPLAY = int(os.environ.get("REPLAY", "200"))

for p_ in model.parameters(): p_.requires_grad_(False)
inject(model)
sd = torch.load(os.path.join(HERE, "lora_mcq.pt"))
own = dict(model.named_parameters())
for k, v in sd.items(): own[k].data.copy_(v.to("cuda"))
params = [p_ for n_, p_ in model.named_parameters() if ".A.weight" in n_ or ".B.weight" in n_]
items = build_items()
test = [it for it in items if it[0] % 5 == 0]; train = [it for it in items if it[0] % 5 != 0]
f, r, p = synth_struct.build(train, seed=1)
synth = [(cmd, L, segs) for cmd, L, segs in f + r + p]
rnd = random.Random(3)
replay = [(cmd, L, segs) for _, cmd, L, segs in rnd.sample(train, min(REPLAY, len(train)))]
ex = []
for k, (cmd, L, segs) in enumerate(synth + replay):
    dis = make_candidates(L, segs, k=5, seed=5000 + k)
    if not dis: continue
    opts = [L] + [M for _, M in dis]; perm = list(range(len(opts))); rnd.shuffle(perm)
    ex.append((prompt(cmd, [(opts[j], segs) for j in perm]), perm.index(0), len(opts)))
print(f"합성 필러 {len(f)} REF {len(r)} 후치 {len(p)} + 재생 {len(replay)} → 예제 {len(ex)}", flush=True)
opt = torch.optim.AdamW(params, lr=LR)
model.gradient_checkpointing_enable(); model.train()
rnd.shuffle(ex); t0 = time.time(); tot = hit = 0
WARM = 50
for step, (p_, gold, n) in enumerate(ex):
    for g in opt.param_groups: g["lr"] = LR * min(1.0, (step + 1) / WARM)
    lg = letter_logits(p_, n); loss = nn.functional.cross_entropy(lg[None], torch.tensor([gold], device="cuda"))
    loss.backward(); opt.step(); opt.zero_grad(); tot += loss.item(); hit += int(lg.argmax().item() == gold)
print(f"1 epoch: loss {tot/len(ex):.3f} train acc {hit/len(ex):.3f} ({time.time()-t0:.0f}s)", flush=True)
model.eval()
def scores(pp, n):
    with torch.no_grad(): return letter_logits(pp, n).tolist()
mcq.scores = scores
te = [(cmd, L, segs, make_candidates(L, segs, k=5, seed=i)) for i, cmd, L, segs in test]
mcq.evaluate([it for it in te if it[3]], "2B+LoRA(cont) held-out 20%")
wrong = mcq.evaluate(challenge.items(), "2B+LoRA(cont) challenge")
wc = {w[0] for w in wrong}; ch = challenge.items()
for g, a, b in [("조건후치", 0, 6), ("REF", 6, 12), ("필러", 12, 16), ("장문", 16, 22)]:
    print(f"  {g}: {sum(1 for it in ch[a:b] if it[0] not in wc)}/{b-a}")
for w in wrong: print("✗", w[0], "| 교란:", w[1])
torch.save({n_: p_.detach().cpu() for n_, p_ in model.named_parameters() if ".A.weight" in n_ or ".B.weight" in n_}, os.path.join(HERE, "lora_mcq2.pt"))
