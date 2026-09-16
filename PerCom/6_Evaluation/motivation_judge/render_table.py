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

# Hyphenated single tokens, the spelling used for judge models in the code-judge bias
# literature (GPT-4o-mini, Claude-3.5-Sonnet, LLaMA-3.1-70B-Instruct).
HDR = {"qwen": "Qwen3.5-9B", "gpt": "GPT-5.4-mini", "claude": "Claude-Sonnet-5"}
# Row names are short hyphenated compounds rather than three-letter codes, so the table reads
# without the caption -- the convention of the bias rows in Moon et al.
ROWS = [("Identity", None), ("Var-Rename", "var_rename"), ("Cmp-Flip", "comparator_flip"),
        ("Time-Unit", "time_unit"), ("Group-Cond", "exists_spelling"),
        ("Branch-Swap", "branch_swap"), ("Delay-Split", "delay_split"),
        ("Loop-Unroll", "loop_unroll"), ("Phase-Flag", "phase_flag")]


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


def text_pt(txt, fontsize):
    """Width of a string in points, as LaTeX would set it in the serif face."""
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    if not txt:
        return 0.0
    return TextPath((0, 0), txt, size=fontsize,
                    prop=FontProperties(family="serif")).get_extents().width


def render(width_in, fontsize, out, colsep_pt=2.5):
    """Lay the table out at measured text widths, so the preview reports honestly whether it
    fits. Every column is as wide as its widest entry, which is what tabular does."""
    S = json.load(open(os.path.join(HERE, "results", "summary.json")))
    judges, body, tot = table(S, minus="\u2212")
    ci = ci_row(S)

    stub = ["Rewrite"] + [ab for ab, _ in body] + ["All rewrites", "95% CI"]
    cols = [[HDR[j]] + [v[k] for _, v in body] + [tot[k], ci[k]]
            for k, j in enumerate(judges)]
    stub_w = max(text_pt(t, fontsize) for t in stub)
    col_w = [max(text_pt(t, fontsize) for t in c) for c in cols]
    need = stub_w + sum(col_w) + 2 * colsep_pt * (1 + len(col_w))
    avail = width_in * 72.0
    print(f"  {out}: needs {need:.1f}pt of {avail:.1f}pt"
          + ("" if need <= avail else "   <-- OVERFULL"))

    nrow = len(body) + 4
    rowh = fontsize * 1.85 / 72.0
    tabh = rowh * nrow
    fig_h = tabh + 0.10
    fig = plt.figure(figsize=(need / 72.0, fig_h))
    ax = fig.add_axes([0, 0, 1, tabh / fig_h])
    ax.set_xlim(0, need)
    ax.set_ylim(0, nrow)
    ax.axis("off")
    fp = {"fontsize": fontsize, "family": "serif"}

    x = colsep_pt
    x_lab, right = x, []
    x += stub_w + 2 * colsep_pt
    for w in col_w:
        right.append(x + w)
        x += w + 2 * colsep_pt

    def row(stub_txt, vals, y):
        ax.text(x_lab, y, stub_txt, ha="left", va="center", **fp)
        for r, v in zip(right, vals):
            ax.text(r, y, v, ha="right", va="center", **fp)

    y = nrow - 1.0
    ax.plot([0, need], [y + 0.55] * 2, lw=1.1, color="k")              # \toprule
    row("Rewrite", [HDR[j] for j in judges], y)
    y -= 1
    ax.plot([0, need], [y + 0.55] * 2, lw=0.5, color="k")              # \midrule

    for ab, vals in body:
        row(ab, vals, y)
        if ab == "Identity":
            ax.plot([0, need], [y - 0.45] * 2, lw=0.5, color="k")      # reference sits apart
        y -= 1

    ax.plot([0, need], [y + 0.55] * 2, lw=0.5, color="k")
    row("All rewrites", tot, y)
    y -= 1
    row("95% CI", ci, y)
    y -= 1
    ax.plot([0, need], [y + 0.55] * 2, lw=1.1, color="k")              # \bottomrule

    fig.savefig(os.path.join(HERE, "results", out), dpi=300, bbox_inches="tight",
                facecolor="white")


CAPTION = (
    "Verdict reversal on programs each judge had already accepted. Each cell reports the "
    "rewrites rejected over the accepted programs presented; the parenthesised value is the "
    "change in percentage points from that judge's own Identity rate. Identity re-asks the "
    "identical accepted program and leaves it unedited, so it is the reference row and its "
    "parenthesis holds the rate itself, as does the All rewrites row that the interval refers "
    "to. Cmp-Flip mirrors a comparison (\\texttt{x >= 26} becomes \\texttt{26 <= x}), "
    "Group-Cond respells `at least one device in a group matches', and Phase-Flag replaces an "
    "integer phase counter with a boolean flag; the remaining names are literal. Every rewrite "
    "is certified behavior-preserving by the checker of Sec.~\\ref{sec:explorer}. The judges "
    "are \\texttt{Qwen3.5-9B-fp8} served locally at temperature 0, and "
    "\\texttt{gpt-5.4-mini-2026-03-17} and \\texttt{claude-sonnet-5} at low reasoning effort; "
    "neither hosted model exposes a temperature control, which is why their Identity rates are "
    "not zero. Intervals are 95\\% bootstrap CIs clustered by seed program.")


def write_tex():
    S = json.load(open(os.path.join(HERE, "results", "summary.json")))
    judges, body, tot = table(S, minus="$-$")
    ci = ci_row(S)
    L = [r"\begin{table}[t]", r"\centering", r"\caption{" + CAPTION + "}", r"\label{tab:judge}",
         r"\footnotesize", r"\setlength{\tabcolsep}{2.5pt}",
         r"\begin{tabular}{l rrr}", r"\toprule",
         "Rewrite & " + " & ".join(HDR[j] for j in judges) + r" \\", r"\midrule"]
    for ab, vals in body:
        L.append(ab + " & " + " & ".join(vals) + r" \\")
        if ab == "Identity":
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
