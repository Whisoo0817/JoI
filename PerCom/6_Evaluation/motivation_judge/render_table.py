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

# two-line headers: model family on top, size/variant below, so no column outgrows a
# single IEEE column
HDR = {"qwen": ("Qwen3.5", "9B"), "gpt": ("GPT-5.4", "mini"),
       "claude": ("Claude", "Sonnet 5")}
ROWS = [("CTL", None), ("VAR", "var_rename"), ("CMP", "comparator_flip"), ("UNIT", "time_unit"),
        ("GRP", "exists_spelling"), ("BR", "branch_swap"), ("DLY", "delay_split"),
        ("UNR", "loop_unroll"), ("PHS", "phase_flag")]


def cell(sm, t, minus):
    """One judge, one condition. The cell carries the counts; the parenthesised value is the
    percentage-point change from that judge's own CTL rate, following the convention of Moon et
    al. (EACL Findings 2026), whose bias rows are read against an unbiased reference row. CTL is
    that reference here, so its own parenthesis holds the rate itself."""
    a = sm["accepted"]
    x = a["overall"] if t is None or t == "__all__" else a["by_type"][t]
    k = x["control_rejected"] if t is None else x["rejected"]
    n = x["control_seeds"] if t is None else x["pairs"]
    rate = 100.0 * k / n
    if t is None or t == "__all__":
        return f"{k}/{n} ({rate:.1f})"
    d = rate - 100.0 * a["overall"]["control_rate"]
    sign = "+" if d >= 0 else minus
    return f"{k}/{n} ({sign}{abs(d):.1f})"


def table(S, minus="-"):
    """Rows of (stub, [cell per judge]) plus the totals, shared by both renderers."""
    judges = list(S)
    body = [(ab, [cell(S[j], t, minus) for j in judges]) for ab, t in ROWS]
    tot = [cell(S[j], "__all__", minus) for j in judges]
    return judges, body, tot


def ci_row(S):
    return ["[{:.1f}, {:.1f}]".format(*[100 * v for v in S[j]["accepted"]["overall"]["ci95"]])
            for j in S]


def render(width_in, fontsize, out):
    S = json.load(open(os.path.join(HERE, "results", "summary.json")))
    judges, body, tot = table(S, minus="\u2212")
    ci = ci_row(S)

    nrow = len(body) + 5                       # header + total + CI
    rowh = fontsize * 1.85 / 72.0              # inches per row
    tabh = rowh * nrow
    fig_h = tabh + 0.10
    fig = plt.figure(figsize=(width_in, fig_h))
    ax = fig.add_axes([0, 0, 1, tabh / fig_h])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, nrow)
    ax.axis("off")
    fp = {"fontsize": fontsize, "family": "serif"}

    # stub column on the left, then one right-aligned column per judge
    x_lab = 0.005
    lab_w, gw = 0.22, (1.0 - 0.22) / 3.0
    right = [lab_w + (i + 1) * gw - 0.005 for i in range(3)]

    y = nrow - 1.0
    ax.plot([0, 1], [y + 0.55, y + 0.55], lw=1.1, color="k")           # \toprule
    ax.text(x_lab, y, "Condition", ha="left", va="center", **fp)
    for line in (0, 1):
        for r, j in zip(right, judges):
            ax.text(r, y, HDR[j][line], ha="right", va="center", **fp)
        y -= 1
    ax.plot([0, 1], [y + 0.55, y + 0.55], lw=0.5, color="k")           # \midrule

    for ab, vals in body:
        ax.text(x_lab, y, ab, ha="left", va="center", **fp)
        for r, v in zip(right, vals):
            ax.text(r, y, v, ha="right", va="center", **fp)
        if ab == "CTL":
            ax.plot([0, 1], [y - 0.45, y - 0.45], lw=0.5, color="k")   # control sits apart
        y -= 1

    ax.plot([0, 1], [y + 0.55, y + 0.55], lw=0.5, color="k")
    for stub, vals in (("All rewrites", tot), ("95\\% CI", ci)):
        ax.text(x_lab, y, stub.replace("\\", ""), ha="left", va="center", **fp)
        for r, v in zip(right, vals):
            ax.text(r, y, v, ha="right", va="center", **fp)
        y -= 1
    ax.plot([0, 1], [y + 0.55, y + 0.55], lw=1.1, color="k")           # \bottomrule

    fig.savefig(os.path.join(HERE, "results", out), dpi=300, bbox_inches="tight",
                facecolor="white")
    print("wrote", out, f"({width_in}in, {fontsize}pt)")


CAPTION = (
    "Verdict reversal on programs each judge had already accepted. Each cell reports the "
    "rewrites rejected over the accepted programs presented; the parenthesised value is the "
    "change in percentage points from that judge's own CTL rate. CTL re-asks the identical "
    "accepted program and carries no rewrite, so it is the reference row and its parenthesis "
    "holds the rate itself, as does the All rewrites row, which the CI row refers to. CTL "
    "bounds how much a judge moves with no edit at all. VAR renames "
    "a variable, CMP mirrors a comparison, UNIT "
    "changes the time unit, GRP respells a condition over a group of devices, BR negates the "
    "guard and swaps the branches, DLY splits one delay into two, UNR unrolls a counted "
    "periodic loop, and PHS replaces an integer phase with a boolean flag. Every rewrite is "
    "certified behavior-preserving by the checker of Sec.~\\ref{sec:explorer}. The judges are "
    "\\texttt{Qwen3.5-9B-fp8} served locally at temperature 0, and \\texttt{gpt-5.4-mini-2026-03-17} "
    "and \\texttt{claude-sonnet-5} at low reasoning effort; neither hosted model exposes a "
    "temperature control, which is why their CTL rates are not zero. Intervals are 95\\% "
    "bootstrap CIs clustered by seed program.")


def write_tex():
    S = json.load(open(os.path.join(HERE, "results", "summary.json")))
    judges, body, tot = table(S, minus="$-$")
    ci = ci_row(S)
    L = [r"\begin{table}[t]", r"\centering", r"\caption{" + CAPTION + "}", r"\label{tab:judge}",
         r"\footnotesize", r"\setlength{\tabcolsep}{4pt}",
         r"\begin{tabular}{l rrr}", r"\toprule",
         "Condition & " + " & ".join(HDR[j][0] for j in judges) + r" \\",
         " & " + " & ".join(HDR[j][1] for j in judges) + r" \\", r"\midrule"]
    for ab, vals in body:
        L.append(ab + " & " + " & ".join(vals) + r" \\")
        if ab == "CTL":
            L.append(r"\midrule")
    L += [r"\midrule",
          "All rewrites & " + " & ".join(tot) + r" \\",
          r"95\% CI & " + " & ".join(ci) + r" \\",
          r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    p = os.path.join(HERE, "results", "table1.tex")
    open(p, "w").write("\n".join(L) + "\n")
    print("wrote", p)


if __name__ == "__main__":
    write_tex()
    render(IEEE_1COL_IN, 8, "table1_preview_1col.png")
    render(IEEE_2COL_IN, 9, "table1_preview_2col.png")
