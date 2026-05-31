#!/usr/bin/env python3
"""Aggregate motivation/judge results into the three reportable artifacts:
  1. SILENT-WRONG: among truly-wrong programs, how many each method accepted
     (the motivation headline -- unsoundness, not accuracy).
  2. INCONSISTENCY: per (fault_family x construct) "bug schema" with >=2 instances,
     does the method both accept AND reject instances of the same schema?
     (instance sensitivity -> not a stable decision procedure)
  3. HEATMAP: recall over (fault_family x construct) -- diagnostic (eval/appendix).

Usage: python3 paper/aggregate_motivation.py LABEL=path.json [LABEL=path.json ...]
"""
import json
import sys
from collections import defaultdict

FAMILIES = ["Boundary", "Direction", "Timing", "Omission", "WrongAction"]
CONSTRUCTS = ["Stateless", "LevelWait", "EdgeTrigger", "DelaySeq",
              "PeriodicCond", "Sustain", "Counter", "Composite"]


def load(path):
    return json.load(open(path, encoding="utf-8"))["detail"]


def main():
    methods = {}
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        methods[label] = load(path)

    # 1. BOTH failure modes: FN (silent-wrong, unsafe) AND FP (over-reject, unusable)
    print("=" * 70)
    print("1. TWO FAILURE MODES per method (ours target = 0/0 on both)")
    print("   FN = silent-wrong rate (truly-wrong ACCEPTED -> ships a bug = UNSAFE)")
    print("   FP = over-rejection rate (truly-correct REJECTED = UNUSABLE)")
    print(f"{'method':18s} {'wrong':>6} {'FN(silent)':>11} {'FN-rate':>8}"
          f" {'correct':>8} {'FP(over-rej)':>13} {'FP-rate':>8}")
    for label, det in methods.items():
        wrong = [d for d in det if d["gt"] == "wrong"]
        correct = [d for d in det if d["gt"] == "correct"]
        fn = [d for d in wrong if d["judge_says_wrong"] is False]
        fp = [d for d in correct if d["judge_says_wrong"] is True]
        fnr = len(fn) / max(1, len(wrong))
        fpr = len(fp) / max(1, len(correct))
        print(f"{label:18s} {len(wrong):6d} {len(fn):11d} {fnr:7.1%}"
              f" {len(correct):8d} {len(fp):13d} {fpr:7.1%}")

    # 2. INCONSISTENCY (bug schema = fault_family x construct, >=2 wrong instances)
    print("\n" + "=" * 70)
    print("2. INCONSISTENCY (instance sensitivity): bug schemas where the method both"
          " CAUGHT and MISSED instances of the SAME (fault x construct)")
    for label, det in methods.items():
        schemas = defaultdict(list)
        for d in det:
            if d["gt"] != "wrong":
                continue
            schemas[(d.get("fault_family"), d.get("construct"))].append(
                d["judge_says_wrong"] is True)  # True = caught
        multi = {k: v for k, v in schemas.items() if len(v) >= 2}
        mixed = {k: v for k, v in multi.items() if any(v) and not all(v)}
        print(f"  {label:16s}: {len(mixed)}/{len(multi)} schemas MIXED "
              f"({len(mixed)/max(1,len(multi)):.0%} of >=2-instance schemas inconsistent)")

    # 3. HEATMAP recall (fault x construct)
    print("\n" + "=" * 70)
    print("3. HEATMAP -- recall over (fault_family x construct) [diagnostic / eval]")
    for label, det in methods.items():
        print(f"\n--- {label} ---")
        cell = defaultdict(lambda: [0, 0])  # (caught, total)
        for d in det:
            if d["gt"] != "wrong":
                continue
            c = cell[(d.get("fault_family"), d.get("construct"))]
            c[1] += 1
            if d["judge_says_wrong"] is True:
                c[0] += 1
        hdr = "fault\\construct  " + "".join(f"{c[:8]:>9}" for c in CONSTRUCTS)
        print(hdr)
        for fam in FAMILIES:
            row = f"{fam:16s}"
            for con in CONSTRUCTS:
                c = cell.get((fam, con))
                row += (f"{c[0]/c[1]:>9.2f}" if c and c[1] else f"{'--':>9}")
            print(row)
        # over-rejection (FP) by construct on the correct controls
        fpc = defaultdict(lambda: [0, 0])
        for d in det:
            if d["gt"] != "correct":
                continue
            c = fpc[d.get("construct")]
            c[1] += 1
            if d["judge_says_wrong"] is True:
                c[0] += 1
        fprow = "FP-rate (correct) "
        for con in CONSTRUCTS:
            c = fpc.get(con)
            fprow += (f"{c[0]/c[1]:>9.2f}" if c and c[1] else f"{'--':>9}")
        print(fprow)


if __name__ == "__main__":
    main()
