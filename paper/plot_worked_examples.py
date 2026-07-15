#!/usr/bin/env python3
"""Worked-example figure: a reactive-mode IR fault is legible in the deterministic
plain-text rendering (confirmed/correct vs faulty, differing lines highlighted).

Run: PYTHONPATH=/home/gnltnwjstk/joi python3 paper/plot_worked_examples.py
"""
import difflib
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "paper/Final/evaluation/results")
FIGS = os.path.join(ROOT, "paper/Final/evaluation/figs")

ex = json.load(open(os.path.join(RES, "rendering_worked_examples.json")))
by = {(e.get("cls"), e["name"]): e for e in ex if e.get("part") == "B_synth"}
picks = [
    ("oneshot_vs_waituntil", "C03_10", "one-shot check ↔ wait-until"),
    ("single_vs_cycle_whenever", "C01_1", "single ↔ recurring (whenever)"),
]
chosen = [(by[(c, n)], lab) for c, n, lab in picks if (c, n) in by]

fig, axes = plt.subplots(len(chosen), 1, figsize=(11, 3.4 * len(chosen)))
if len(chosen) == 1:
    axes = [axes]

for ax, (e, lab) in zip(axes, chosen):
    cl = [l for l in e["render_correct"].splitlines() if l.strip()]
    fl = [l for l in e["render_faulty"].splitlines() if l.strip()]
    sm = difflib.SequenceMatcher(a=cl, b=fl)
    same_c, same_f = set(), set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            same_c.update(range(i1, i2))
            same_f.update(range(j1, j2))
    ax.axis("off")
    ax.text(0.0, 1.10, f'Command: "{e["command"]}"', fontsize=9.5, fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.0, 0.99, f"[{lab}]  Confirmed / correct rendering", fontsize=8.5,
            fontweight="bold", color="#2e7d32", transform=ax.transAxes)
    ax.text(0.52, 0.99, "Faulty rendering (NL→IR error)", fontsize=8.5,
            fontweight="bold", color="#c62828", transform=ax.transAxes)
    import textwrap

    def wrap(lines, same):
        rows = []  # (text, is_diff)
        for k, ln in enumerate(lines):
            sub = textwrap.wrap(ln, 46) or [""]
            for w in sub:
                rows.append((w, k not in same))
        return rows

    rc, rf = wrap(cl, same_c), wrap(fl, same_f)
    n = max(len(rc), len(rf))
    step = 0.86 / max(n, 1)
    for k, (ln, diff) in enumerate(rc):
        ax.text(0.0, 0.90 - step * k, ln, fontsize=7.5, family="monospace",
                color="#2e7d32" if diff else "#222",
                fontweight="bold" if diff else "normal", transform=ax.transAxes)
    for k, (ln, diff) in enumerate(rf):
        ax.text(0.50, 0.90 - step * k, ln, fontsize=7.5, family="monospace",
                color="#c62828" if diff else "#222",
                fontweight="bold" if diff else "normal", transform=ax.transAxes)

fig.suptitle("The fault is legible in the deterministic rendering "
             "(highlighted = differing lines)", fontsize=11, y=0.995)
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(os.path.join(FIGS, "rendering_worked_examples.png"), dpi=150)
print("-> figs/rendering_worked_examples.png")
