"""Draft figure options for E4 (not yet chosen). Writes figs/options/*.pdf|png.

A - cumulative "programs decided within t" (cactus/survival form used by SMT-COMP / SV-COMP)
B - per-program times on one log axis, undecided runs piled in a TIMEOUT column
Per program: median wall time of its 3 runs if all 3 decided, else undecided (no mixed cells here).
"""
import json, statistics as st
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
OUT = HERE / "figs/options"
OK = {"EQUIV", "EQUIV-BOUNDED"}
MODES = [("free", "Explorer (no H)", "#2a78d6", "o", "-"),
         ("fixed10", "fixed H = 10 s", "#eb6834", "s", "--"),
         ("fixedT", "fixed H covering the wait", "#1baf7a", "^", ":")]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
LIMIT = 120

rows = [json.loads(l) for f in ("runs/e4_free_serial.jsonl", "runs/e4_fixed_w4.jsonl")
        for l in open(HERE / f)]
by = defaultdict(list)
for r in rows:
    by[(r["mode"], r["cell_id"])].append(r)
cells = sorted({c for _, c in by})
time = {m: {} for m, *_ in MODES}
for (m, c), rs in by.items():
    time[m][c] = (st.median(r["wall_seconds"] for r in rs)
                  if all(r["verdict"] in OK for r in rs) else None)

plt.rcParams.update({"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "font.family": "DejaVu Sans"})


def save(fig, name):
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=220)
    print("->", OUT / name)


# ── A: cumulative ────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(3.4, 2.5))
for m, label, color, marker, ls in MODES:
    ts = sorted(t for t in time[m].values() if t is not None)
    xs, ys = [0.01], [0]
    for i, t in enumerate(ts, 1):
        xs += [t, t]; ys += [i - 1, i]
    xs.append(LIMIT); ys.append(len(ts))
    ax.plot(xs, ys, color=color, lw=1.6, ls=ls)
    ax.text(LIMIT * 1.12, len(ts), f"{len(ts)}", color=INK, va="center", fontsize=8, fontweight="bold")
ax.text(0.02, 12, "Explorer (no H)", color="#2a78d6", fontsize=7, fontweight="bold")
ax.text(115, 9.3, "fixed H = 10 s", color="#eb6834", fontsize=6.5, ha="right", fontweight="bold")
ax.text(1.1, 2.4, "fixed H covering\nthe wait", color="#12805a", fontsize=6.5, ha="right", fontweight="bold")
ax.axvline(5, color=MUTED, lw=0.8, ls=(0, (2, 2)))
n5 = sum(1 for t in time["free"].values() if t is not None and t <= 5)
ax.annotate(f"{n5}/30 within 5 s", xy=(5, n5), xytext=(6.5, 13), fontsize=7, color=INK,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
ax.plot([5], [n5], "o", color="#2a78d6", ms=4, mec="white", mew=0.8, zorder=5)
ax.axhline(30, color=GRID, lw=0.8)
ax.set_xscale("log"); ax.set_xlim(0.01, LIMIT); ax.set_ylim(0, 31.5)
ax.set_xticks([0.01, 0.1, 1, 5, 10, 120]); ax.set_xticklabels(["0.01", "0.1", "1", "5", "10", "120"])
ax.set_xlabel("time per program (s)"); ax.set_ylabel("programs decided (of 30)")
ax.grid(axis="y", color=GRID, lw=0.5); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
save(fig, "A_cumulative")

# ── B: per-program strip with a TIMEOUT column ──────────────────────────────
order = sorted(cells, key=lambda c: (time["free"][c] is None, time["free"][c] or 0))
fig, ax = plt.subplots(figsize=(3.4, 3.2))
TO = 400                                            # x position of the "not decided" column
ax.axvspan(200, 800, color="#f1f0ec", zorder=0)
ax.text(TO, len(order) + 0.4, "not\ndecided", ha="center", va="bottom", fontsize=6.5, color=MUTED)
jitter = {"free": -0.25, "fixed10": 0.0, "fixedT": 0.25}
for m, label, color, marker, ls in MODES:
    xs, ys = [], []
    for i, c in enumerate(order):
        t = time[m][c]
        xs.append(TO * (1 + jitter[m] * 0.6) if t is None else t); ys.append(i)
    ax.scatter(xs, ys, s=14, marker=marker, color=color, edgecolor="white", linewidth=0.5,
               label=label, zorder=3)
ax.axvline(5, color=MUTED, lw=0.8, ls=(0, (2, 2)))
ax.text(5.5, -1.6, "5 s", fontsize=6.5, color=MUTED)
ax.set_xscale("log"); ax.set_xlim(0.01, 800); ax.set_ylim(-2.2, len(order) + 2.5)
ax.set_xticks([0.01, 0.1, 1, 5, 20, 120]); ax.set_xticklabels(["0.01", "0.1", "1", "5", "20", "120"])
ax.set_yticks([]); ax.set_ylabel("30 programs, sorted by Explorer time")
ax.set_xlabel("time per program (s)")
ax.grid(axis="x", color=GRID, lw=0.5); ax.set_axisbelow(True)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.10), ncol=2, fontsize=6.5, frameon=False,
          handletextpad=0.2, columnspacing=0.8)
save(fig, "B_per_program")
