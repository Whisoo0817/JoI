# -*- coding: utf-8 -*-
"""객관식 구조 판정 — 명령어 + 후보 배치(원문 절 timeline) → 보기 기호 1토큰의 로짓으로 선택.
모델: 2B(HF, 로컬 로짓) / 9B(vLLM localhost:8002, logprobs). 보기 순서 셔플 SHUF회 → 로짓 평균.
평가: 382 중 G/G 뼈대 일치 & 절≥2 명령 → 정답 후보 + 교란 후보 ≤4. 지표 = 정답 선택률.
"""
import json, os, sys, random, math, collections, urllib.request
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from box import assemble_tree, gold_flags, assemble
from skeleton import skeleton
from candidates import tree_to_lines, render, make_candidates
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("MCQ_MODEL", "2b")     # 2b | 9b
SHUF = int(os.environ.get("SHUF", "3"))
K = int(os.environ.get("K", "5"))
LETTERS = "ABCDEFG"

LEGEND = ("표기: [시각] 정해진 시각에 시작 · [반복] 주기적으로 반복(들여쓴 줄이 반복 내용) · [조건] 조건이 참일 때만(들여쓴 줄) · "
          "[아니면] 앞 조건이 거짓일 때 · [대기] 사건이 일어날 때까지 기다림 · [지연] 시간이 지난 뒤 · [읽기] 값 확인 · "
          "[참조] 앞에서 이미 한 동작을 가리킴(새로 실행하지 않음) · [무시] 실행과 무관한 말. 들여쓰기 없는 줄은 순서대로 실행.")

def prompt(cmd, opts):
    body = "\n\n".join(render(L, segs_, LETTERS[i]) for i, (L, segs_) in enumerate(opts))
    return (f"사용자 명령: \"{cmd}\"\n\n아래는 이 명령을 실행 순서대로 배치한 후보들이다.\n{LEGEND}\n"
            f"명령의 의미와 정확히 일치하는 후보의 기호를 하나만 답하라.\n\n{body}\n\n답:")

if MODEL == "2b":
    import torch
    from transformers import AutoConfig, AutoTokenizer, Qwen3_5ForConditionalGeneration
    MID = "cyankiwi/Qwen3.5-2B-AWQ-4bit"
    tok = AutoTokenizer.from_pretrained(MID)
    cfg = AutoConfig.from_pretrained(MID)
    q = dict(cfg.quantization_config); q["ignore"] = list(q.get("ignore", [])) + ["re:.*in_proj_a$", "re:.*in_proj_b$"]; cfg.quantization_config = q
    model = Qwen3_5ForConditionalGeneration.from_pretrained(MID, config=cfg, dtype=torch.bfloat16, attn_implementation="eager", device_map="cuda").eval()
    LID = {c: [tok.encode(c, add_special_tokens=False)[0], tok.encode(" " + c, add_special_tokens=False)[-1]] for c in LETTERS}
    CHAT = os.environ.get("CHAT", "0") == "1"
    def scores(p, n):
        if CHAT:
            try:
                p = tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True, enable_thinking=False) + "답:"
            except TypeError:
                p = tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True) + "답:"
        enc = tok(p, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.no_grad():
            lg = model(**enc).logits[0, -1].float()
        lp = torch.log_softmax(lg, -1)
        return [max(lp[i].item() for i in LID[LETTERS[k]]) for k in range(n)]
else:
    def scores(p, n):
        req = json.dumps({"model": "cyankiwi/Qwen3.5-9B-AWQ-4bit", "prompt": p, "max_tokens": 1, "temperature": 0, "logprobs": 20}).encode()
        r = urllib.request.Request("http://localhost:8002/v1/completions", data=req, headers={"Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(r, timeout=120).read())
        top = res["choices"][0]["logprobs"]["top_logprobs"][0]
        return [max([v for t, v in top.items() if t.strip() == LETTERS[k]] or [-30.0]) for k in range(n)]

def evaluate(items, tag=""):
    """items: [(cmd, correct_lines, segs, distractors[list of lines])]"""
    hit = 0; tot = 0; by_n = collections.defaultdict(lambda: [0, 0]); by_tag = collections.defaultdict(lambda: [0, 0]); wrong = []
    for cmd, gold_L, segs, dis in items:
        opts = [("gold", gold_L)] + dis
        n = len(opts); acc = np.zeros(n)
        for s in range(SHUF):
            perm = list(range(n)); random.Random(s).shuffle(perm)
            sc = scores(prompt(cmd, [(opts[j][1], segs) for j in perm]), n)
            for pos, j in enumerate(perm): acc[j] += sc[pos]
        pick = int(np.argmax(acc)); ok = pick == 0
        hit += ok; tot += 1; by_n[len(segs)][0] += ok; by_n[len(segs)][1] += 1
        if not ok: wrong.append((cmd, opts[pick][0], render(gold_L, segs), render(opts[pick][1], segs)))
        for t, _ in dis: by_tag[t.split("+")[0]][1] += 1
        if not ok: by_tag[opts[pick][0].split("+")[0]][0] += 1
    print(f"[{MODEL} {tag}] 정답 선택률 {hit}/{tot} = {hit/max(tot,1):.3f}   보기 수 평균 {np.mean([1+len(d) for *_, d in items]):.1f}")
    print("  절 수별:", {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_n.items())})
    print("  오답이 고른 교란 종류(오답 수/등장 수):", {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_tag.items())})
    return wrong

if __name__ == "__main__":
    T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
    items = []
    for o in T:
        if not o["ir_gt"] or len(o["segments"]) < 2: continue
        segs = [(s["type"], s["mods"], s["text"]) for s in o["segments"]]
        cron, cyc = gold_flags(o["ir_gt"])
        if assemble(segs, cron, cyc) != skeleton(o["ir_gt"]): continue
        root = assemble_tree(segs, cron, cyc); L = tree_to_lines(root, segs)
        dis = make_candidates(L, segs, k=K, seed=o["i"])
        if not dis: continue
        items.append((o["cmd"], L, segs, dis))
    LIM = int(os.environ.get("LIM", "0"))
    if LIM: items = items[:LIM]
    print("평가 명령", len(items))
    wrong = evaluate(items, "382 sanity")
    json.dump(wrong, open(os.path.join(HERE, f"mcq_wrong_{MODEL}.json"), "w"), ensure_ascii=False, indent=1)
    for w in wrong[:8]:
        print("\n✗", w[0], "| 고른 교란:", w[1]); print("  정답:\n" + "\n".join("    " + l for l in w[2].splitlines())); print("  선택:\n" + "\n".join("    " + l for l in w[3].splitlines()))
