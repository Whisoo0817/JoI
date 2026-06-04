#!/usr/bin/env python3
"""Plot the instability experiment (motivation, paper Fig 1 + Table 2 decomposition).

Reads paper/Final/evaluation/results/instability/*.json and writes:
  - instability_by_type.png   (Fig 1: per-rewrite-type flip, 9B vs GPT-5.1, temp=0)
  - instability_decomp.png    (decomposition: config x model; matches Table 2)
to paper/Final/evaluation/figs/.

Usage: python3 paper/plot_instability.py
"""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "Final", "evaluation", "results", "instability")
FIGS = os.path.join(ROOT, "Final", "evaluation", "figs")
os.makedirs(FIGS, exist_ok=True)


def load(name):
    return json.load(open(os.path.join(RES, name), encoding="utf-8"))


def rate(cell):  # cell = [flips, total]
    return 100.0 * cell[0] / cell[1] if cell[1] else 0.0


# ---- Fig 1: per-rewrite-type flip (deterministic temp=0) ----
# trivial (surface) controls left, logical/algebraic right, idiom last.
ORDER = ["selector_reorder", "operand_swap", "var_rename", "arith_commute",
         "branch_swap", "double_neg", "demorgan", "prevcurr"]
LABEL = {"selector_reorder": "SEL", "operand_swap": "AND",
         "var_rename": "VAR", "arith_commute": "ADD",
         "branch_swap": "BR", "double_neg": "DN", "demorgan": "DM",
         "prevcurr": "IDM"}
q = load("instability_9b_temp0.json")["by_type"]
g = load("instability_gpt51_temp0.json")["by_type"]
x = range(len(ORDER))
w = 0.38
fig, ax = plt.subplots(figsize=(7.0, 2.8))
ax.bar([i - w/2 for i in x], [rate(q[t]) for t in ORDER], w, label="local 9B", color="#d9776f")
ax.bar([i + w/2 for i in x], [rate(g[t]) for t in ORDER], w, label="cloud GPT-5.1", color="#6f8fd9")
ax.axhline(0, color="green", lw=1.4, ls="--")
ax.text(len(ORDER)-1.0, 1.5, "OVLA = 0", color="green", fontsize=9)
ax.set_xticks(list(x)); ax.set_xticklabels([LABEL[t] for t in ORDER], fontsize=10)
ax.set_ylabel("flip rate (%)")
ax.set_title("Verdict flip on behaviorally-identical rewrites (deterministic, temp=0)", fontsize=9)
ax.legend(fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(os.path.join(FIGS, "instability_by_type.png"), dpi=200)
print("wrote instability_by_type.png")

# ---- decomposition bar (config x model) = Table 2 ----
cfgs = [("deterministic\n(temp=0)", "temp0"),
        ("+ sampling\n(temp=0.7)", "temp07"),
        ("+ majority\nvote (K=5)", "vote5")]
qv = [load(f"instability_9b_{k}.json")["overall_rate"] * 100 for _, k in cfgs]
gv = [load(f"instability_gpt51_{k}.json")["overall_rate"] * 100 for _, k in cfgs]
x = range(len(cfgs))
fig, ax = plt.subplots(figsize=(4.6, 2.8))
ax.bar([i - w/2 for i in x], qv, w, label="local 9B", color="#d9776f")
ax.bar([i + w/2 for i in x], gv, w, label="cloud GPT-5.1", color="#6f8fd9")
ax.axhline(0, color="green", lw=1.4, ls="--")
ax.text(2.0, 1.2, "OVLA = 0", color="green", fontsize=9)
# floor lines (deterministic) to show voting never drops below
ax.axhline(qv[0], color="#d9776f", lw=0.8, ls=":")
ax.axhline(gv[0], color="#6f8fd9", lw=0.8, ls=":")
ax.set_xticks(list(x)); ax.set_xticklabels([c for c, _ in cfgs], fontsize=8)
ax.set_ylabel("overall flip rate (%)")
ax.set_title("No judge config beats the deterministic floor", fontsize=9)
ax.legend(fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(os.path.join(FIGS, "instability_decomp.png"), dpi=200)
print("wrote instability_decomp.png")
