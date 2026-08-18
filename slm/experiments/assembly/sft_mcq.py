# -*- coding: utf-8 -*-
"""2B 객관식 SFT (간단판) — AWQ 2B 위에 수동 LoRA(r=8), 손실 = 보기 기호 로짓 CE(정답 기호 1토큰).
데이터: 382 sanity 항목(절≥2, G/G 일치) 명령 단위 80/20 분할. 학습 항목마다 교란 seed·보기 순서 변형 VAR개.
평가: held-out 20% + challenge 22 (셔플 3회 평균, mcq.evaluate와 동일 방식).
"""
import os, sys, json, random, time, math
os.environ.setdefault("MCQ_MODEL", "2b")
import torch, torch.nn as nn, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcq, challenge
from mcq import prompt, LETTERS, tok, model, LID
from box import assemble_tree, gold_flags, assemble
from skeleton import skeleton
from candidates import tree_to_lines, make_candidates
HERE = os.path.dirname(os.path.abspath(__file__))
R, ALPHA, LR, EPOCHS, VAR = 8, 16, float(os.environ.get("LR", "2e-4")), int(os.environ.get("EPOCHS", "2")), int(os.environ.get("VAR", "4"))

class LoRA(nn.Module):
    def __init__(self, base, r=R, alpha=ALPHA):
        super().__init__(); self.base = base
        d_in = base.weight_shape[1].item() if hasattr(base, "weight_shape") else base.in_features
        d_out = base.weight_shape[0].item() if hasattr(base, "weight_shape") else base.out_features
        self.A = nn.Linear(d_in, r, bias=False, dtype=torch.bfloat16); self.B = nn.Linear(r, d_out, bias=False, dtype=torch.bfloat16)
        nn.init.kaiming_uniform_(self.A.weight, a=math.sqrt(5)); nn.init.zeros_(self.B.weight); self.s = alpha / r
    def forward(self, x): return self.base(x) + self.B(self.A(x)) * self.s

def inject(m):
    n_ = 0
    for name, mod in list(m.named_modules()):
        for cn, ch in list(mod.named_children()):
            if type(ch).__name__ == "CompressedLinear" and cn in ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"):
                setattr(mod, cn, LoRA(ch).to("cuda")); n_ += 1
    return n_

def build_items():
    T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
    items = []
    for o in T:
        if not o["ir_gt"] or len(o["segments"]) < 2: continue
        segs = [(s["type"], s["mods"], s["text"]) for s in o["segments"]]
        cron, cyc = gold_flags(o["ir_gt"])
        if assemble(segs, cron, cyc) != skeleton(o["ir_gt"]): continue
        root = assemble_tree(segs, cron, cyc); L = tree_to_lines(root, segs)
        items.append((o["i"], o["cmd"], L, segs))
    return items

def letter_logits(p, n):
    enc = tok(p, return_tensors="pt", add_special_tokens=False).to("cuda")
    lg = model(**enc).logits[0, -1].float()
    return torch.stack([torch.logsumexp(lg[LID[LETTERS[k]]], 0) for k in range(n)])

if __name__ == "__main__":
    for p_ in model.parameters(): p_.requires_grad_(False)
    n_lora = inject(model); print("LoRA 주입", n_lora, "모듈")
    params = [p_ for n_, p_ in model.named_parameters() if ".A.weight" in n_ or ".B.weight" in n_]
    print("학습 파라미터", sum(p_.numel() for p_ in params))
    items = build_items()
    test = [it for it in items if it[0] % 5 == 0]; train = [it for it in items if it[0] % 5 != 0]
    print("학습 명령", len(train), "평가 명령", len(test))
    # 학습 예제: (프롬프트, 정답 위치, 보기 수)
    ex = []
    for i, cmd, L, segs in train:
        for v in range(VAR):
            dis = make_candidates(L, segs, k=5, seed=1000 * v + i)
            if not dis: continue
            opts = [L] + [M for _, M in dis]; perm = list(range(len(opts))); random.Random(7 * v + i).shuffle(perm)
            ex.append((prompt(cmd, [(opts[j], segs) for j in perm]), perm.index(0), len(opts)))
    print("학습 예제", len(ex))
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=0.0)
    model.gradient_checkpointing_enable() if hasattr(model, "gradient_checkpointing_enable") else None
    model.train()
    t0 = time.time(); step = 0
    for ep in range(EPOCHS):
        random.Random(ep).shuffle(ex); tot = 0.0; hit = 0
        for p, gold, n in ex:
            lg = letter_logits(p, n)
            loss = nn.functional.cross_entropy(lg[None], torch.tensor([gold], device="cuda"))
            loss.backward(); opt.step(); opt.zero_grad()
            tot += loss.item(); hit += int(lg.argmax().item() == gold); step += 1
        print(f"epoch {ep+1}: loss {tot/len(ex):.3f}  train acc {hit/len(ex):.3f}  ({time.time()-t0:.0f}s)")
    model.eval()
    # 평가 (mcq.evaluate 사용: scores를 학습된 모델로)
    def scores(p, n):
        with torch.no_grad(): return letter_logits(p, n).tolist()
    mcq.scores = scores
    te_items = [(cmd, L, segs, make_candidates(L, segs, k=5, seed=i)) for i, cmd, L, segs in test]
    te_items = [it for it in te_items if it[3]]
    mcq.evaluate(te_items, "2B+LoRA held-out 20%")
    wrong = mcq.evaluate(challenge.items(), "2B+LoRA challenge")
    wc = {w[0] for w in wrong}; ch = challenge.items()
    for g, a, b in [("조건후치", 0, 6), ("REF", 6, 12), ("필러", 12, 16), ("장문", 16, 22)]:
        print(f"  {g}: {sum(1 for it in ch[a:b] if it[0] not in wc)}/{b-a}")
    torch.save({n_: p_.detach().cpu() for n_, p_ in model.named_parameters() if ".A.weight" in n_ or ".B.weight" in n_}, os.path.join(HERE, "lora_mcq.pt"))
