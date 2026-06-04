#!/usr/bin/env python3
"""RQ3: LLM-as-judge vs our LLM-free trace verifier, on the mutation ground-truth.

Ground truth is objective: a verifier-clean Stage-B seed is CORRECT; a genuine
(non-trace-equivalent) mutant of it is WRONG. We ask an LLM to judge IR<->JoI
equivalence (the same question our verifier answers) and compare detection.

Fairness: the judge gets the SAME information our verifier effectively uses --
the JoI grammar/semantics (joi_common), a compact IR-op reference, and the SAME
correctness definition incl. the +/-500ms timing tolerance -- and may reason
(CoT). It does NOT get the NL command (our verifier checks IR<->JoI, not NL) nor
our simulation mechanism (that IS our contribution). temp=0; prompt is dumped.

Backends: --backend qwen (local 9B, free, edge-feasible) | gpt4o (cloud, needs
paper/openai.txt). Reuses the mutation harness operators + verifier.

Usage:
  PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_judge_compare.py \
      --backend qwen --per-op 3 --max 400 --seed-dir <stageB_on_dir> --out <dir>
"""
import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "paper"))

from loader import PROMPTS
from config import get_client, get_model_id
from paper.run_mutation_test import (
    load_meta, load_catalog, OPERATORS, _verify, _trace_signature,
)

# Compact IR-op reference (the IR's definition — fair to give the judge).
_IR_SEMANTICS = """Timeline IR operators (a reactive automation as an ordered timeline):
- start_at(cron): anchor the timeline to a wall-clock schedule.
- wait(cond[, edge]): block until cond holds. edge=none -> level ("when"); edge=rising -> transition ("whenever").
- delay(duration): wait a fixed duration.
- read(service.attr -> var): sample a device attribute into a variable.
- call(service.method, args): emit a device actuation (the observable trace event).
- if(cond){then}[else]: branch on a condition (may compare attrs/vars, arithmetic, enums).
- cycle(period){body}: repeat body every period; optional cycle.count(N) / cycle.until(cond).
- break: terminate the enclosing cycle (one-shot).
Behavioral equality = same sequence of call() emissions (service, method, args), with timestamps matching within +/-500ms."""


def _judge_prompt(ir: dict, joi_block: dict) -> str:
    grammar = PROMPTS.get("joi_common") or ""
    return (
        "# ROLE\nDecide whether the JoI program correctly implements the Timeline IR.\n"
        "CORRECT iff, under every relevant scenario, the JoI emits the SAME sequence of "
        "device actuations as the IR. Two emissions match if (device-service, method, args) "
        "are equal and their timestamps are within +/-500ms. Sub-500ms timing differences "
        "are NOT divergences.\n\n"
        "# IR SEMANTICS\n" + _IR_SEMANTICS + "\n\n"
        "# JoI LANGUAGE REFERENCE\n" + grammar + "\n\n"
        "# TIMELINE IR (specification)\n" + json.dumps(ir, ensure_ascii=False, indent=1) + "\n\n"
        "# JoI PROGRAM (candidate)\n" + json.dumps(joi_block, ensure_ascii=False, indent=1) + "\n\n"
        "# TASK\nReason step by step about both behaviors over time, at boundaries and "
        "branches (you may think before answering). Then output ONLY a JSON object:\n"
        '{"equivalent": true|false, "divergence": "<where/why, or none>"}\n'
    )


def gen_qwen(prompt, max_tokens=2048, temperature=0.0):
    client = get_client()
    model = get_model_id(client)
    r = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}],
        temperature=temperature, max_tokens=max_tokens,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    return r.choices[0].message.content or ""


_GPT = None


def gen_gpt4o(prompt, max_tokens=2048, model="gpt-4o"):
    global _GPT
    if _GPT is None:
        from openai import OpenAI
        with open(os.path.join(ROOT, "paper", "openai.txt")) as f:
            _GPT = OpenAI(api_key=f.read().strip())
    r = _GPT.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}],
        temperature=0.0, max_tokens=max_tokens,
    )
    return r.choices[0].message.content or ""


def parse_verdict(text):
    """Return True (equivalent/correct) / False (divergent) / None (unparseable)."""
    s = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    m = re.findall(r'"equivalent"\s*:\s*(true|false)', s, re.I)
    if m:
        return m[-1].lower() == "true"
    # fallback: last bare json bool / keyword
    m2 = re.search(r'\b(true|false)\b', s[::-1])  # crude
    return None


def harvest(seed_dir, meta, catalog, per_op, cap, rng):
    """Build labeled items: each clean seed -> 1 'correct' item; up to per_op
    genuine mutants per operator across seeds -> 'wrong' items. Returns list of
    {name, op, label('correct'|'wrong'), ir, joi, our_caught}."""
    files = sorted(f for f in os.listdir(seed_dir)
                   if f.endswith(".json") and not f.startswith("_"))
    items = []
    op_budget = Counter()
    for fn in files:
        name = fn[:-5]
        m = meta.get(name)
        if not m or not isinstance(m.get("ir_gt"), dict):
            continue
        ir_gt, devs = m["ir_gt"], m["devs"]
        try:
            d = json.load(open(os.path.join(seed_dir, fn), encoding="utf-8"))
        except Exception:
            continue
        jb = d.get("joi_block")
        if not isinstance(jb, dict) or not (jb.get("script") or "").strip():
            continue
        # seed must be verifier-clean
        try:
            seed_caught, _, _ = _verify(jb, ir_gt, devs, catalog)
        except Exception:
            continue
        if seed_caught:
            continue
        try:
            seed_sig = _trace_signature(jb, ir_gt, catalog)
        except Exception:
            seed_sig = None
        items.append({"name": name, "op": "clean", "label": "correct",
                      "ir": ir_gt, "joi": jb, "our_caught": False})
        # genuine mutants: one per operator per seed (cheap, diverse)
        for op_name, op in OPERATORS.items():
            muts = op(jb.get("script", ""))
            rng.shuffle(muts)
            for new_script, _desc in muts:
                if new_script == jb.get("script"):
                    continue
                mut = dict(jb); mut["script"] = new_script
                try:
                    if _trace_signature(mut, ir_gt, catalog) == seed_sig:
                        continue  # equivalent mutant
                    hit, _, _ = _verify(mut, ir_gt, devs, catalog)
                except Exception:
                    continue
                items.append({"name": name, "op": op_name, "label": "wrong",
                              "ir": ir_gt, "joi": mut, "our_caught": bool(hit)})
                op_budget[op_name] += 1
                break  # one genuine mutant per (seed, op)
        # early stop: enough wrong items harvested (bounds the slow per-seed sim)
        if sum(1 for it in items if it["label"] == "wrong") >= cap:
            break
    # subsample: keep all 'correct', cap 'wrong' stratified per op
    correct = [it for it in items if it["label"] == "correct"]
    wrong = [it for it in items if it["label"] == "wrong"]
    by_op = defaultdict(list)
    for it in wrong:
        by_op[it["op"]].append(it)
    sampled = []
    for op_name, lst in by_op.items():
        rng.shuffle(lst)
        sampled.extend(lst[:per_op * 20])  # generous per-op pool; global cap below
    rng.shuffle(sampled)
    sampled = sampled[:cap]
    rng.shuffle(correct)
    correct = correct[: max(1, cap // 3)]
    out = correct + sampled
    rng.shuffle(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["qwen", "gpt4o"], default="qwen")
    ap.add_argument("--per-op", type=int, default=3)
    ap.add_argument("--max", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0, help="cap total judged (smoke)")
    ap.add_argument("--seed-dir", required=True)
    ap.add_argument("--out", default="/tmp/judge_compare")
    ap.add_argument("--rng", type=int, default=20260528)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.rng)
    meta = load_meta()
    catalog = load_catalog()
    items = harvest(a.seed_dir, meta, catalog, a.per_op, a.max, rng)
    if a.limit:
        items = items[: a.limit]
    n_correct = sum(1 for it in items if it["label"] == "correct")
    n_wrong = len(items) - n_correct
    print(f"[judge] backend={a.backend} items={len(items)} (correct={n_correct} wrong={n_wrong})")

    gen = gen_gpt4o if a.backend == "gpt4o" else gen_qwen
    # confusion: positive = "divergent/wrong"
    judge = {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "unparsed": 0}
    ours = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
    miss_by_op = Counter()
    dumped = []
    t0 = time.time()
    for i, it in enumerate(items, 1):
        gt_wrong = it["label"] == "wrong"
        # our verifier
        if gt_wrong:
            ours["TP" if it["our_caught"] else "FN"] += 1
        else:
            ours["FP" if it["our_caught"] else "TN"] += 1
        # llm judge
        prompt = _judge_prompt(it["ir"], it["joi"])
        try:
            raw = gen(prompt)
            v = parse_verdict(raw)
        except Exception as e:
            print(f"  [{i}] {it['name']}/{it['op']} GEN-ERR {type(e).__name__}: {str(e)[:60]}")
            judge["unparsed"] += 1
            continue
        if v is None:
            judge["unparsed"] += 1
            jpred_wrong = None
        else:
            jpred_wrong = (v is False)  # equivalent=False => judge says wrong
            if gt_wrong:
                judge["TP" if jpred_wrong else "FN"] += 1
                if not jpred_wrong:
                    miss_by_op[it["op"]] += 1
            else:
                judge["FP" if jpred_wrong else "TN"] += 1
        dumped.append({"name": it["name"], "op": it["op"], "gt": it["label"],
                       "our_caught": it["our_caught"], "judge_says_wrong": jpred_wrong})
        if i % 25 == 0:
            print(f"  [{i}/{len(items)}] {time.time()-t0:.0f}s  judge={judge}")

    def stats(cm):
        tp, fp, fn, tn = cm["TP"], cm["FP"], cm["FN"], cm["TN"]
        rec = tp / (tp + fn) if tp + fn else 0.0
        prec = tp / (tp + fp) if tp + fp else 0.0
        return rec, prec

    jr, jp = stats(judge)
    orr, orp = stats(ours)
    print("\n" + "=" * 64)
    print(f"GROUND TRUTH: wrong={n_wrong} correct={n_correct}")
    print(f"OUR VERIFIER : {ours}  recall={orr:.3f} precision={orp:.3f}")
    print(f"{a.backend}-judge: {judge}  recall={jr:.3f} precision={jp:.3f}  "
          f"(recall=caught wrong; FP=flagged correct as wrong)")
    if miss_by_op:
        print("judge MISSED wrong-by-operator:", dict(miss_by_op.most_common()))
    summary = {"backend": a.backend, "n_items": len(items),
               "n_wrong": n_wrong, "n_correct": n_correct,
               "our_verifier": {**ours, "recall": orr, "precision": orp},
               "llm_judge": {**judge, "recall": jr, "precision": jp},
               "judge_miss_by_op": dict(miss_by_op), "detail": dumped}
    with open(os.path.join(a.out, f"_judge_{a.backend}.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[judge] -> {a.out}/_judge_{a.backend}.json")


if __name__ == "__main__":
    main()
