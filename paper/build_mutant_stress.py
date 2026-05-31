#!/usr/bin/env python3
"""Build a tagged injected-bug stress set for the motivation / RQ2 judge study.

Each item is a (command, JoI) pair with a construction-guaranteed label:
  - correct control: a verifier-clean seed (label=correct)
  - injected bug: a genuine (non-trace-equivalent) mutant of a clean seed
    (label=wrong), tagged with its fault_family and the seed's construct group.

Stratified sampling: up to K wrong items per (fault_family x construct) cell,
plus correct controls at ratio 1 : CONTROL_DENOM. Labels are clean by
construction (no gt_ir-vs-intent ambiguity). Output feeds run_motivation_judge
(--stress-file). Fault_family / construct tags drive the heatmap aggregation.
"""
import csv
import json
import os
import random
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "paper"))

from paper.run_mutation_test import (
    load_meta, load_catalog, OPERATORS, _verify, _trace_signature,
)

K_PER_CELL = 8           # max wrong mutants per (fault_family x construct)
CONTROL_DENOM = 4        # correct controls = (#wrong) / CONTROL_DENOM
RNG = random.Random(20260531)

# operator -> fault family
FAULT_FAMILY = {
    "comparator": "Boundary", "arg_numeric": "Boundary",
    "cmp_direction": "Direction", "guard_polarity": "Direction",
    "tick_scale": "Timing",
    "call_drop": "Omission", "wait_drop": "Omission", "break_drop": "Omission",
    "call_add": "WrongAction", "enum_flip": "WrongAction", "arith_op": "WrongAction",
}

# category -> construct group
def construct_group(cat):
    g = {
        "C01": "Stateless", "C02": "Stateless", "C03": "Stateless",
        "C04": "Stateless", "C05": "Stateless", "C06": "Stateless",
        "C15": "Stateless", "C16": "Stateless", "C21": "Stateless",
        "C07": "LevelWait",
        "C08": "EdgeTrigger", "C10": "EdgeTrigger", "C14": "EdgeTrigger",
        "C09": "DelaySeq", "C11": "DelaySeq",
        "C17": "PeriodicCond", "C19": "PeriodicCond",
        "C20": "Sustain",
        "C13": "Counter", "C18": "Counter", "C22": "Counter",
        "C23": "Composite", "C24": "Composite", "C25": "Composite",
        "C12": "EdgeTrigger",
    }
    return g.get(cat, "Other")


def load_commands():
    out = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "dataset.csv"), encoding="utf-8")):
        out[f"{r['category_v2']}_{r['index']}"] = (r.get("command_eng") or "").strip()
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump-dir", default="experiments/e2e_382/20260528_150445__d886015/intermediate/off")
    ap.add_argument("--out", default="/tmp/mutant_stress.json")
    a = ap.parse_args()

    meta = load_meta()
    catalog = load_catalog()
    commands = load_commands()

    # gather clean seeds with their construct group
    seeds = []
    for fn in sorted(os.listdir(a.dump_dir)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        name = fn[:-5]
        m = meta.get(name)
        cmd = commands.get(name)
        if not m or not isinstance(m.get("ir_gt"), dict) or not cmd:
            continue
        try:
            d = json.load(open(os.path.join(a.dump_dir, fn), encoding="utf-8"))
        except Exception:
            continue
        jb = d.get("joi_block")
        if not isinstance(jb, dict) or not (jb.get("script") or "").strip():
            continue
        try:
            if _verify(jb, m["ir_gt"], m["devs"], catalog)[0]:
                continue  # seed must be verifier-clean (a true correct)
            seed_sig = _trace_signature(jb, m["ir_gt"], catalog)
        except Exception:
            continue
        seeds.append({"name": name, "cmd": cmd, "joi": jb, "ir": m["ir_gt"],
                      "devs": m["devs"], "sig": seed_sig,
                      "construct": construct_group(name.rsplit("_", 1)[0])})

    print(f"clean seeds: {len(seeds)}")

    # generate genuine mutants, bucket by (fault_family x construct)
    buckets = defaultdict(list)
    for sd in seeds:
        script = sd["joi"].get("script", "")
        for op_name, op in OPERATORS.items():
            fam = FAULT_FAMILY.get(op_name)
            if not fam:
                continue
            muts = op(script)
            RNG.shuffle(muts)
            kept = 0
            for new_script, desc in muts:
                if new_script == script:
                    continue
                mut = dict(sd["joi"]); mut["script"] = new_script
                try:
                    if _trace_signature(mut, sd["ir"], catalog) == sd["sig"]:
                        continue  # equivalent mutant
                    if not _verify(mut, sd["ir"], sd["devs"], catalog)[0]:
                        continue  # our verifier didn't flag -> not a usable wrong label
                except Exception:
                    continue
                buckets[(fam, sd["construct"])].append({
                    "name": f"{sd['name']}__{op_name}", "command": sd["cmd"],
                    "joi": mut, "label": "wrong", "fault_family": fam,
                    "construct": sd["construct"], "operator": op_name,
                    "seed": sd["name"]})
                kept += 1
                if kept >= 3:   # cap mutants per (seed, operator) for diversity
                    break

    # stratified sample K per cell
    wrong = []
    cell_counts = {}
    for cell, lst in sorted(buckets.items()):
        RNG.shuffle(lst)
        take = lst[:K_PER_CELL]
        wrong.extend(take)
        cell_counts[f"{cell[0]}/{cell[1]}"] = len(take)

    # correct controls
    n_ctrl = max(1, len(wrong) // CONTROL_DENOM)
    ctrl_seeds = RNG.sample(seeds, min(n_ctrl, len(seeds)))
    correct = [{"name": f"{s['name']}__clean", "command": s["cmd"], "joi": s["joi"],
                "label": "correct", "fault_family": "none",
                "construct": s["construct"], "operator": "none", "seed": s["name"]}
               for s in ctrl_seeds]

    items = wrong + correct
    RNG.shuffle(items)
    json.dump(items, open(a.out, "w"), ensure_ascii=False, indent=1)

    print(f"wrong={len(wrong)} correct={len(correct)} total={len(items)} -> {a.out}")
    print("cells (fault_family/construct -> #wrong):")
    for k in sorted(cell_counts):
        print(f"  {k:28s} {cell_counts[k]}")
    print("by fault_family:", dict(Counter(w["fault_family"] for w in wrong)))
    print("by construct   :", dict(Counter(w["construct"] for w in wrong)))


if __name__ == "__main__":
    main()
