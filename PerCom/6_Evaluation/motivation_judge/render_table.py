#!/usr/bin/env python3
"""Write results/table1.tex and preview it at the real IEEE column width.

The preview is not a paper artifact. It exists so the table's fit can be checked before the
manuscript does: every string is measured and each column is sized to its widest entry, the way
tabular does, and the required width is reported against the target.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
IEEE_1COL_IN = 3.5      # IEEE conference single column

# The spelling used for judge models in the code-judge bias literature: one hyphenated token
# (GPT-4o-mini, Claude-3.5-Sonnet, LLaMA-3.1-70B-Instruct).
HDR = {"qwen": "Qwen3.5-9B", "gpt": "GPT-5.4-mini", "claude": "Claude-Sonnet-5"}
BANDS = [("Notation", "spelling"), ("Logic", "logic"), ("Temporal", "temporal")]


def table(C):
    """Stub, n, and one consistency figure per judge.

    Both rows measure the same thing -- the share of items on which the judge did not contradict
    itself -- so they share a column. The first row is over every seed program, asked three times
    identically, with no selection; the rest are over the rewrites of the common set. Reported as
    100 minus the reversal rate, so that higher is better throughout.
    """
    judges = list(C["judges"])
    sd = C["self_disagreement"]
    body = [("No edit", str(sd[judges[0]]["seeds"]),
             [f"{100 * (1 - sd[j]['rate']):.1f}" for j in judges])]
    for lab, b in BANDS:
        x = [C["judges"][j]["by_band"][b] for j in judges]
        body.append((lab, str(x[0]["pairs"]), [f"{100 * (1 - v['rate']):.1f}" for v in x]))
    x = [C["judges"][j]["overall"] for j in judges]
    body.append(("All", str(x[0]["pairs"]), [f"{100 * (1 - v['rate']):.1f}" for v in x]))
    return judges, body


def text_pt(txt, fontsize):
    """Width of a string in points, as LaTeX would set it in the serif face."""
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    if not txt:
        return 0.0
    return TextPath((0, 0), txt, size=fontsize,
                    prop=FontProperties(family="serif")).get_extents().width


def render(C, width_in, fontsize, out, colsep_pt=3.0):
    judges, body = table(C)
    stub = ["Condition"] + [r[0] for r in body]
    ncol = ["n"] + [r[1] for r in body]
    cols = [[HDR[j]] + [r[2][k] for r in body] for k, j in enumerate(judges)]
    sw = max(text_pt(t, fontsize) for t in stub)
    nw = max(text_pt(t, fontsize) for t in ncol)
    cw = [max(text_pt(t, fontsize) for t in c) for c in cols]
    need = sw + nw + sum(cw) + 2 * colsep_pt * (2 + len(cw))
    avail = width_in * 72.0
    print(f"  {out}: needs {need:.1f}pt of {avail:.1f}pt"
          + ("" if need <= avail else "   <-- OVERFULL"))

    nrow = len(body) + 4
    rowh = fontsize * 1.85 / 72.0
    tabh = rowh * nrow
    fig = plt.figure(figsize=(need / 72.0, tabh + 0.10))
    ax = fig.add_axes([0, 0, 1, tabh / (tabh + 0.10)])
    ax.set_xlim(0, need)
    ax.set_ylim(0, nrow)
    ax.axis("off")
    fp = {"fontsize": fontsize, "family": "serif"}

    x = colsep_pt
    x_lab = x
    x += sw + 2 * colsep_pt
    x_n = x + nw
    x += nw + 2 * colsep_pt
    right = []
    for w in cw:
        right.append(x + w)
        x += w + 2 * colsep_pt

    def row(a, b, vals, y, **kw):
        ax.text(x_lab, y, a, ha="left", va="center", **fp, **kw)
        ax.text(x_n, y, b, ha="right", va="center", **fp, **kw)
        for r, v in zip(right, vals):
            ax.text(r, y, v, ha="right", va="center", **fp, **kw)

    span_l, span_r = right[0] - cw[0], right[-1]
    y = nrow - 1.0
    ax.plot([0, need], [y + 0.55] * 2, lw=1.1, color="k")              # \toprule
    ax.text((span_l + span_r) / 2, y, "Verdict consistency (%, higher is better)",
            ha="center", va="center", **fp)
    ax.plot([span_l, span_r], [y - 0.42] * 2, lw=0.5, color="k")       # \cmidrule
    y -= 1
    row("Condition", "n", [HDR[j] for j in judges], y)
    y -= 1
    ax.plot([0, need], [y + 0.55] * 2, lw=0.5, color="k")              # \midrule

    for i, (a, b, vals) in enumerate(body):
        row(a, b, vals, y)
        if i in (0, len(body) - 2):
            ax.plot([0, need], [y - 0.45] * 2, lw=0.5, color="k")
        y -= 1
    ax.plot([0, need], [y + 0.55] * 2, lw=1.1, color="k")              # \bottomrule

    fig.savefig(os.path.join(HERE, "results", out), dpi=300, bbox_inches="tight",
                facecolor="white")


CAPTION = (
    "How often each judge stands by its own verdict, as a percentage of the items presented; "
    "higher is better. The first row asks nothing new: every one of the {tot} seed programs was "
    "submitted three times, identically, and the figure is the share on which all three answers "
    "agreed. It is unconditional -- no program is excluded -- and it bounds what any rewrite "
    "result below can mean. The remaining rows take the {n} programs that all three judges called "
    "correct in at least two of those three asks, so one set of programs and one denominator "
    "serves every column, and report the share of each band's rewrites the judge still accepted. "
    "Notation renames a variable, mirrors a comparison ({cmp}), changes the time unit, or "
    "respells `at least one device in a group matches'; Logic negates a guard and swaps the "
    "branches; Temporal splits one delay into two, unrolls a counted periodic loop, or replaces "
    "an integer phase counter with a boolean flag. Every rewrite is certified behavior-preserving "
    "by the checker of Sec.~\\ref{{sec:explorer}}, so every point below 100 is a judge "
    "contradicting itself. The judges are \\texttt{{Qwen3.5-9B-fp8}} served locally at "
    "temperature 0, and \\texttt{{gpt-5.4-mini-2026-03-17}} and \\texttt{{claude-sonnet-5}} at "
    "low reasoning effort; neither hosted model exposes a temperature control.")


def write_tex(C):
    judges, body = table(C)
    cap = CAPTION.format(n=len(C["common_seeds"]), tot=C["seeds_total"],
                         cmp="\\texttt{x >= 26} becomes \\texttt{26 <= x}")
    L = [r"\begin{table}[t]", r"\centering", r"\caption{" + cap + "}", r"\label{tab:judge}",
         r"\footnotesize", r"\setlength{\tabcolsep}{3pt}",
         r"\begin{tabular}{lr rrr}", r"\toprule",
         r" & & \multicolumn{3}{c}{Verdict consistency (\%, higher is better)} \\",
         r"\cmidrule(lr){3-5}",
         "Condition & $n$ & " + " & ".join(HDR[j] for j in judges) + r" \\", r"\midrule"]
    for i, (a, b, vals) in enumerate(body):
        L.append(f"{a} & {b} & " + " & ".join(vals) + r" \\")
        if i in (0, len(body) - 2):
            L.append(r"\midrule")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    p = os.path.join(HERE, "results", "table1.tex")
    open(p, "w").write("\n".join(L) + "\n")
    print("wrote", p)


if __name__ == "__main__":
    C = json.load(open(os.path.join(HERE, "results", "summary_common.json")))
    write_tex(C)
    render(C, IEEE_1COL_IN, 8, "table1_preview.png")
