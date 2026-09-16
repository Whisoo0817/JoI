#!/usr/bin/env python3
"""Render Table 1 the way LaTeX/booktabs would, at the real IEEE column width, to check that it
fits before the manuscript exists. Writes results/table1_preview_1col.png and _2col.png.

Not a paper artifact: the manuscript uses results/table1.tex. This only previews the geometry.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
IEEE_1COL_IN = 3.5      # IEEE conference single column
IEEE_2COL_IN = 7.16     # full text width (table*)

HDR = {"qwen": "Qwen-9B", "gpt": "GPT-mini", "claude": "Sonnet 5"}
ROWS = [("CTL", None), ("VAR", "var_rename"), ("CMP", "comparator_flip"), ("UNIT", "time_unit"),
        ("GRP", "exists_spelling"), ("BR", "branch_swap"), ("DLY", "delay_split"),
        ("UNR", "loop_unroll"), ("PHS", "phase_flag")]


def cells(sm, t):
    x = sm["accepted"]["overall"] if t is None else sm["accepted"]["by_type"][t]
    k = x["control_rejected"] if t is None else x["rejected"]
    n = x["control_seeds"] if t is None else x["pairs"]
    return f"{k}/{n}", f"{100 * k / n:.1f}"


def render(width_in, fontsize, out, caption_width):
    S = json.load(open(os.path.join(HERE, "results", "summary.json")))
    judges = list(S)
    body = [(ab, [c for j in judges for c in cells(S[j], t)]) for ab, t in ROWS]
    tot = []
    for j in judges:
        a = S[j]["accepted"]["overall"]
        tot += [f"{a['rejected']}/{a['pairs']}", f"{100 * a['rate']:.1f}"]

    nrow = len(body) + 4                       # header rows + total + CI note
    rowh = fontsize * 1.85 / 72.0              # inches per row
    tabh = rowh * nrow
    fig_h = tabh + 0.10
    fig = plt.figure(figsize=(width_in, fig_h))
    ax = fig.add_axes([0, 0, 1, tabh / fig_h])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, nrow)
    ax.axis("off")
    fp = {"fontsize": fontsize, "family": "serif"}

    # column x positions: label left, then 6 right-aligned numeric columns
    x_lab = 0.005
    lab_w, gw = 0.15, (1.0 - 0.15) / 3.0
    right, group_mid, group_span = [], [], []
    for i in range(3):
        a, b = lab_w + i * gw, lab_w + (i + 1) * gw
        right += [a + gw * 0.62, b - 0.005]
        group_mid.append((a + b) / 2 - 0.01)
        group_span.append((a + 0.015, b - 0.005))

    y = nrow - 0.9
    ax.plot([0, 1], [y + 0.55, y + 0.55], lw=1.1, color="k")          # \toprule
    for m, name in zip(group_mid, (HDR[j] for j in judges)):
        ax.text(m, y, name, ha="center", va="center", **fp)
    y -= 1
    for (a, b) in group_span:                                          # \cmidrule
        ax.plot([a, b], [y + 0.62, y + 0.62], lw=0.5, color="k")
    for r in right:
        ax.text(r, y, "n" if right.index(r) % 2 == 0 else "%", ha="right", va="center", **fp)
    y -= 1
    ax.plot([0, 1], [y + 0.55, y + 0.55], lw=0.5, color="k")           # \midrule

    for i, (ab, vals) in enumerate(body):
        bold = ab == "CTL"
        ax.text(x_lab, y, ab, ha="left", va="center",
                fontweight="bold" if bold else "normal", **fp)
        for r, v in zip(right, vals):
            ax.text(r, y, v, ha="right", va="center",
                    fontweight="bold" if bold else "normal", **fp)
        if bold:
            ax.plot([0, 1], [y - 0.45, y - 0.45], lw=0.5, color="k")
        y -= 1

    ax.plot([0, 1], [y + 0.55, y + 0.55], lw=0.5, color="k")
    ax.text(x_lab, y, "All", ha="left", va="center", **fp)
    for r, v in zip(right, tot):
        ax.text(r, y, v, ha="right", va="center", **fp)
    y -= 1
    ci = "; ".join(f"{HDR[j]} [{100 * S[j]['accepted']['overall']['ci95'][0]:.1f}, "
                   f"{100 * S[j]['accepted']['overall']['ci95'][1]:.1f}]" for j in judges)
    ax.text(x_lab, y, "95% CI on All: " + ci, ha="left", va="center",
            fontsize=fontsize - 1.6, family="serif")
    ax.plot([0, 1], [y - 0.45, y - 0.45], lw=1.1, color="k")           # \bottomrule

    fig.savefig(os.path.join(HERE, "results", out), dpi=300, bbox_inches="tight",
                facecolor="white")
    print("wrote", out, f"({width_in}in, {fontsize}pt)")


if __name__ == "__main__":
    render(IEEE_1COL_IN, 8, "table1_preview_1col.png", IEEE_1COL_IN)
    render(IEEE_2COL_IN, 9, "table1_preview_2col.png", IEEE_2COL_IN)
