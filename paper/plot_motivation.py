#!/usr/bin/env python3
"""Render motivation figures from judge result jsons.
  - heatmap: per-cell MISS-RATE (FN-rate) over fault_family x construct, for one
    method (default the strongest baseline). n annotated; n<3 hatched; empty grey.
  - bars: FN-rate (silent-wrong) AND FP-rate (over-rejection) per method.

Usage:
  python3 paper/plot_motivation.py --heatmap LABEL=path.json \
      --bars L1=p1.json L2=p2.json ... --out-dir /tmp/figs
"""
import argparse
import json
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FAMILIES = ["Boundary", "Direction", "Timing", "Omission", "WrongAction"]
CONSTRUCTS = ["Stateless", "LevelWait", "EdgeTrigger", "DelaySeq",
              "PeriodicCond", "Sustain", "Counter", "Composite"]


def detail(path):
    return json.load(open(path, encoding="utf-8"))["detail"]


def heatmap(label, path, out):
    det = detail(path)
    miss = np.full((len(FAMILIES), len(CONSTRUCTS)), np.nan)
    nmat = np.zeros((len(FAMILIES), len(CONSTRUCTS)), int)
    cell = defaultdict(lambda: [0, 0])  # missed, total
    for d in det:
        if d["gt"] != "wrong":
            continue
        c = cell[(d.get("fault_family"), d.get("construct"))]
        c[1] += 1
        if d["judge_says_wrong"] is False:   # accepted a buggy program = miss
            c[0] += 1
    for i, fam in enumerate(FAMILIES):
        for j, con in enumerate(CONSTRUCTS):
            c = cell.get((fam, con))
            if c and c[1]:
                miss[i, j] = c[0] / c[1]
                nmat[i, j] = c[1]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    cmap = plt.cm.Reds.copy(); cmap.set_bad("0.85")
    im = ax.imshow(miss, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(CONSTRUCTS))); ax.set_xticklabels(CONSTRUCTS, rotation=35, ha="right")
    ax.set_yticks(range(len(FAMILIES))); ax.set_yticklabels(FAMILIES)
    for i in range(len(FAMILIES)):
        for j in range(len(CONSTRUCTS)):
            if np.isnan(miss[i, j]):
                continue
            n = nmat[i, j]
            txt = f"{miss[i,j]:.2f}\n(n={n})"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                    color="white" if miss[i, j] > 0.5 else "black")
            if n < 3:  # low-confidence cell: hatch
                ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False,
                             hatch="///", edgecolor="0.4", lw=0))
    ax.set_title(f"{label}: silent-wrong (miss) rate by fault x construct\n"
                 "red = misses more injected bugs; grey = N/A; hatched = n<3", fontsize=9)
    fig.colorbar(im, ax=ax, label="miss-rate (FN)")
    fig.tight_layout()
    p = f"{out}/heatmap_{label}.png"
    fig.savefig(p, dpi=150); print("->", p)


def bars(methods, out):
    labels = list(methods)
    fn, fp = [], []
    for lab in labels:
        det = methods[lab]
        wrong = [d for d in det if d["gt"] == "wrong"]
        corr = [d for d in det if d["gt"] == "correct"]
        fn.append(sum(1 for d in wrong if d["judge_says_wrong"] is False) / max(1, len(wrong)))
        fp.append(sum(1 for d in corr if d["judge_says_wrong"] is True) / max(1, len(corr)))
    x = np.arange(len(labels)); w = 0.36
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - w/2, fn, w, label="FN: silent-wrong (unsafe)", color="#c0392b")
    ax.bar(x + w/2, fp, w, label="FP: over-rejection (unusable)", color="#2980b9")
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=15)
    ax.set_ylabel("failure rate"); ax.set_ylim(0, 1)
    ax.set_title("No LLM method is both sound (low FN) and precise (low FP)\n"
                 "ours = 0 / 0 (not shown)", fontsize=9)
    ax.legend(fontsize=8)
    for i, (a, b) in enumerate(zip(fn, fp)):
        ax.text(i - w/2, a + .02, f"{a:.0%}", ha="center", fontsize=7)
        ax.text(i + w/2, b + .02, f"{b:.0%}", ha="center", fontsize=7)
    fig.tight_layout()
    p = f"{out}/bars_fn_fp.png"
    fig.savefig(p, dpi=150); print("->", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heatmap", default="", help="LABEL=path.json")
    ap.add_argument("--bars", nargs="*", default=[], help="LABEL=path.json ...")
    ap.add_argument("--out-dir", default="/tmp/figs")
    a = ap.parse_args()
    import os; os.makedirs(a.out_dir, exist_ok=True)
    if a.heatmap:
        lab, p = a.heatmap.split("=", 1)
        heatmap(lab, p, a.out_dir)
    if a.bars:
        m = {}
        for arg in a.bars:
            lab, p = arg.split("=", 1)
            m[lab] = detail(p)
        bars(m, a.out_dir)


if __name__ == "__main__":
    main()
