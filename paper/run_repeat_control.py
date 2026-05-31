#!/usr/bin/env python3
"""Non-determinism control: judge the SAME (command, program) R times and measure
how often the verdict is not unanimous. Isolates sampling noise (esp. gpt-5* whose
temperature is fixed at 1) from the idiom-sensitivity measured by run_instability.

Usage:
  PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_repeat_control.py \
      --backend openai --model gpt-5.1 --equiv /tmp/equiv_stress.json \
      --n 40 --repeat 5 --out /tmp/instab_gpt51
"""
import argparse, json, os, sys, time
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "paper"))
from paper.run_motivation_judge import gen_qwen, gen_openai, judge_prompt, parse_correct, _fewshot_block, load_commands
from paper.run_mutation_test import load_meta, load_catalog


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["qwen", "openai"], default="openai")
    ap.add_argument("--model", default="gpt-5.1")
    ap.add_argument("--equiv", default="/tmp/equiv_stress.json")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--out", default="/tmp/repeat_control")
    ap.add_argument("--dump-dir", default="experiments/e2e_382/20260528_150445__d886015/intermediate/off")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    groups = json.load(open(a.equiv, encoding="utf-8"))[: a.n]
    meta = load_meta(); cat = load_catalog(); commands = load_commands()
    fewshot = _fewshot_block(meta, cat, commands, a.dump_dir)
    gen = (lambda p: gen_openai(p, a.model)) if a.backend == "openai" else gen_qwen
    tag = (a.model.replace(".", "").replace("-", "") if a.backend == "openai" else "qwen")

    nonunanimous = 0; scored = 0; rows = []
    t0 = time.time()
    for i, g in enumerate(groups, 1):
        verdicts = []
        for _ in range(a.repeat):
            try:
                v = parse_correct(gen(judge_prompt(g["command"], g["base_joi"], fewshot)))
            except Exception:
                v = None
            verdicts.append(v)
        vs = [v for v in verdicts if v is not None]
        if len(vs) < 2:
            continue
        scored += 1
        unan = all(x == vs[0] for x in vs)
        if not unan:
            nonunanimous += 1
        rows.append({"seed": g["seed"], "verdicts": verdicts, "unanimous": unan})
        if i % 10 == 0:
            print(f"  [{i}/{len(groups)}] {time.time()-t0:.0f}s non-unanimous={nonunanimous}/{scored}")
    rate = nonunanimous / max(1, scored)
    print("\n" + "=" * 56)
    print(f"NON-DETERMINISM floor ({a.model}, same input x{a.repeat}): "
          f"{nonunanimous}/{scored} = {rate:.1%} of programs got a NON-unanimous verdict")
    json.dump({"model": a.model, "repeat": a.repeat, "n_scored": scored,
               "nonunanimous": nonunanimous, "rate": rate, "rows": rows},
              open(os.path.join(a.out, f"_repeat_{tag}.json"), "w"), indent=1)
    print(f"-> {a.out}/_repeat_{tag}.json")


if __name__ == "__main__":
    main()
