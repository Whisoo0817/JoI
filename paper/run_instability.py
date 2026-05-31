#!/usr/bin/env python3
"""Instability experiment (motivation, ours-free, LABEL-FREE).

Each equivalence group = a seed program + trace-IDENTICAL rewrites (same action
trace, different surface idiom). A stable verification oracle MUST return the same
verdict for all members. We measure how often an LLM judge FLIPS its verdict across
behaviorally-identical variants. No ground-truth correctness needed -- only verdict
consistency under truth-preserving perturbation.

Per (base, variant) pair: flip = judge(base) != judge(variant). Reported overall,
by rewrite type, and by depth (structural vs shallow). Backends: qwen / openai.

Usage:
  PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_instability.py \
      --backend openai --model gpt-5.1 --equiv /tmp/equiv_stress.json \
      --cap-per-type 25 --out /tmp/instab_gpt51
"""
import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "paper"))
from paper.run_motivation_judge import (
    gen_qwen, gen_openai, judge_prompt, parse_correct, _fewshot_block,
    load_commands)
from paper.run_mutation_test import load_meta, load_catalog


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["qwen", "openai"], default="qwen")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--equiv", default="/tmp/equiv_stress.json")
    ap.add_argument("--cap-per-type", type=int, default=25)
    ap.add_argument("--out", default="/tmp/instab")
    ap.add_argument("--dump-dir", default="experiments/e2e_382/20260528_150445__d886015/intermediate/off")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    groups = json.load(open(a.equiv, encoding="utf-8"))
    meta = load_meta(); cat = load_catalog(); commands = load_commands()
    fewshot = _fewshot_block(meta, cat, commands, a.dump_dir)
    if a.backend == "openai":
        gen = lambda p: gen_openai(p, a.model); tag = a.model.replace(".", "").replace("-", "")
    else:
        gen = gen_qwen; tag = "qwen"

    # flatten to (seed, command, base_joi, variant_joi, type, depth) with per-type cap
    pairs, per_type = [], Counter()
    for g in groups:
        for v in g["variants"]:
            if per_type[v["type"]] >= a.cap_per_type:
                continue
            per_type[v["type"]] += 1
            pairs.append((g["seed"], g["command"], g["base_joi"], v["joi"], v["type"], v["depth"]))

    print(f"[instab] backend={a.backend} pairs={len(pairs)} per_type={dict(per_type)}")

    base_cache = {}      # seed -> verdict(bool correct) for base
    def verdict(cmd, joi, key=None):
        if key and key in base_cache:
            return base_cache[key]
        raw = gen(judge_prompt(cmd, joi, fewshot))
        v = parse_correct(raw)
        if key:
            base_cache[key] = v
        return v

    flips = defaultdict(lambda: [0, 0])   # type -> [flip, total]
    depth_flips = defaultdict(lambda: [0, 0])
    detail = []
    t0 = time.time()
    for i, (seed, cmd, base, var, typ, depth) in enumerate(pairs, 1):
        try:
            vb = verdict(cmd, base, key=seed)
            vv = verdict(cmd, var)
        except Exception as e:
            print(f"  [{i}] {seed}/{typ} ERR {type(e).__name__}: {str(e)[:50]}")
            continue
        if vb is None or vv is None:
            continue
        flip = (vb != vv)
        flips[typ][1] += 1; flips[typ][0] += int(flip)
        depth_flips[depth][1] += 1; depth_flips[depth][0] += int(flip)
        detail.append({"seed": seed, "type": typ, "depth": depth,
                       "base_verdict": vb, "variant_verdict": vv, "flip": flip})
        if i % 25 == 0:
            print(f"  [{i}/{len(pairs)}] {time.time()-t0:.0f}s")

    def rate(d): return {k: f"{v[0]}/{v[1]} = {v[0]/v[1]:.0%}" if v[1] else "-/-" for k, v in d.items()}
    tot_f = sum(v[0] for v in flips.values()); tot_n = sum(v[1] for v in flips.values())
    print("\n" + "=" * 60)
    print(f"OVERALL flip-rate (judge changed verdict on behaviorally-IDENTICAL variant): "
          f"{tot_f}/{tot_n} = {tot_f/max(1,tot_n):.1%}")
    print("by rewrite type:", rate(flips))
    print("by depth       :", rate(depth_flips))
    summary = {"backend": a.backend, "model": a.model, "pairs": len(pairs),
               "overall_flip": f"{tot_f}/{tot_n}", "overall_rate": tot_f/max(1, tot_n),
               "by_type": {k: v for k, v in flips.items()},
               "by_depth": {k: v for k, v in depth_flips.items()}, "detail": detail}
    json.dump(summary, open(os.path.join(a.out, f"_instab_{tag}.json"), "w"), indent=1)
    print(f"-> {a.out}/_instab_{tag}.json")


if __name__ == "__main__":
    main()
