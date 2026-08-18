import os, sys, random, torch
os.environ.setdefault("MCQ_MODEL", "2b")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcq, synth_struct
from mcq import prompt, model
from sft_mcq import inject, build_items, letter_logits
from candidates import make_candidates
HERE = os.path.dirname(os.path.abspath(__file__))
for p_ in model.parameters(): p_.requires_grad_(False)
inject(model); own = dict(model.named_parameters())
for k, v in torch.load(os.path.join(HERE, sys.argv[1])).items(): own[k].data.copy_(v.to("cuda"))
items = build_items(); train = [it for it in items if it[0] % 5 != 0]
f, r, p = synth_struct.build(train, seed=1); rnd = random.Random(3)
def acc(group, name, mode_train):
    model.train() if mode_train else model.eval(); h = 0; n = 0
    for k, (cmd, L, segs) in enumerate(group):
        dis = make_candidates(L, segs, k=5, seed=5000 + k)
        if not dis: continue
        opts = [L] + [M for _, M in dis]; perm = list(range(len(opts))); rnd.shuffle(perm)
        with torch.no_grad(): lg = letter_logits(prompt(cmd, [(opts[j], segs) for j in perm]), len(opts))
        h += int(lg.argmax().item() == perm.index(0)); n += 1
    print(f"{name} train_mode={mode_train}: {h}/{n}", flush=True)
rep = [(c, L, s) for _, c, L, s in train[:40]]
acc(rep, "재생40", False); acc(rep, "재생40", True)
acc(f[:30], "필러30", False); acc(r[:30], "REF30", False); acc(p[:30], "후치30", False)
