#!/usr/bin/env python3
"""Figures for the RQ1 human-free substitute:
  (1) NL->IR error distribution (idiom-equivalent vs real-fault split + fault classes)
  (2) faithfulness-surfacing rate (renderer surfaces faults in plain text)

Run: PYTHONPATH=/home/gnltnwjstk/joi python3 paper/plot_rq1_substitute.py
"""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "paper/Final/evaluation/results")
FIGS = os.path.join(ROOT, "paper/Final/evaluation/figs")
os.makedirs(FIGS, exist_ok=True)

dist = json.load(open(os.path.join(RES, "nl2ir_error_distribution.json")))
faith = json.load(open(os.path.join(RES, "faithfulness_surfacing.json")))

# ── Fig 1: NL->IR error distribution ──
fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1, 2.2]})

equiv = dist["n_behaviorally_equivalent"]
err = dist["n_real_errors"]
ax0.bar(["behaviorally\nequivalent\n(idiom)", "real\nerror"], [equiv, err],
        color=["#4c9f70", "#d1495b"])
for i, v in enumerate([equiv, err]):
    ax0.text(i, v + 4, str(v), ha="center", fontsize=11, fontweight="bold")
ax0.set_title(f"NL→IR outputs vs gt (n={equiv+err})\n{equiv/(equiv+err):.0%} idiom-equivalent")
ax0.set_ylabel("rows")

classes = {k: v for k, v in dist["fault_class_counts"].items()
           if k not in ("INVALID_OR_EMPTY_IR",)}
items = sorted(classes.items(), key=lambda kv: kv[1])
ax1.barh([k for k, _ in items], [v for _, v in items], color="#d1495b")
for i, (_, v) in enumerate(items):
    ax1.text(v + 0.2, i, str(v), va="center", fontsize=9)
ax1.set_title("real NL→IR error classes (multi-label)")
ax1.set_xlabel("count")
fig.tight_layout()
fig.savefig(os.path.join(FIGS, "nl2ir_error_distribution.png"), dpi=150)
print("-> figs/nl2ir_error_distribution.png")

# ── Fig 2: faithfulness-surfacing ──
pb = faith["part_B_synthetic_by_class"]
order = ["comparator", "polarity", "wrong_arg_value", "wrong_device", "timing_duration",
         "oneshot_vs_waituntil", "single_vs_cycle_whenever", "and_conjunct_drop"]
labels = [c for c in order if c in pb]
rates = [pb[c]["surface_rate"] * 100 for c in labels]
ns = [pb[c]["applicable"] for c in labels]

fig2, ax = plt.subplots(figsize=(9, 4.2))
bars = ax.bar(range(len(labels)), rates, color="#2e7d8a")
for i, (r, n) in enumerate(zip(rates, ns)):
    ax.text(i, r - 8, f"{r:.0f}%\nn={n}", ha="center", color="white", fontsize=8, fontweight="bold")
ax.set_xticks(range(len(labels)))
ax.set_xticklabels([c.replace("_", "\n") for c in labels], fontsize=8)
ax.set_ylim(0, 105)
ax.set_ylabel("% of injected faults surfaced in plain-text rendering")
ax.set_title("Faithfulness-surfacing: every injected fault class surfaces in the\n"
             "deterministic plain-text rendering (0 blind spots)", fontsize=11)
ax.axhline(100, ls="--", lw=0.8, color="gray")
fig2.tight_layout()
fig2.savefig(os.path.join(FIGS, "faithfulness_surfacing.png"), dpi=150)
print("-> figs/faithfulness_surfacing.png")
