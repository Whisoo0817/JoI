"""E4 tables and the completion/cost plot from runs/e4_run.jsonl.

  ~/temp/bin/python make_e4_results.py [--run runs/e4_run.jsonl]

Writes RESULTS.md and figs/e4_cost.pdf|png.

Reporting rules (HANDOFF.md common rules, confirmed_ir_evaluation_2026-09-10 §E4):
- TIMEOUT / OOM / ERROR / REFUSED / UNKNOWN all stay in the denominator.
- State and transition counts are reported as counts. They are never restated as a
  runtime speedup; wall time and peak RSS are reported on their own.
- The horizon-free and fixed-horizon modes are reported separately, never merged.
"""
import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
# A run counts as completed when the Explorer returned a decision it stands behind.
# EQUIV is unbounded closure; EQUIV-BOUNDED holds only up to H, so it is counted in
# the fixed-horizon arm but always shown as its own column - never merged with EQUIV.
COMPLETE = {"EQUIV", "EQUIV-BOUNDED", "DIVERGE"}
INCOMPLETE_ORDER = ["REFUSED", "UNKNOWN", "TIMEOUT", "OOM", "ERROR"]


def load(run):
    rows = [json.loads(l) for l in Path(run).read_text().splitlines() if l.strip()]
    for r in rows:
        r["complete"] = r.get("verdict") in COMPLETE and bool(r.get("closed"))
        if not r.get("params"):              # a killed worker leaves no params; read them off the id
            import re
            w, b, t, k = map(int, re.fullmatch(r"W(\d+)_B(\d+)_T(\d+)_K(\d+)", r["cell_id"]).groups())
            r["params"] = {"W": w, "B": b, "T_ms": t, "K": k}
    return rows


def agg(rows, pick):
    """median / p95 / max of `pick` over rows that have it."""
    v = sorted(x for x in (pick(r) for r in rows) if x is not None)
    if not v:
        return None, None, None
    p95 = v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]
    return st.median(v), p95, max(v)


def fmt(x, nd=2):
    return "-" if x is None else f"{x:.{nd}f}"


def cell_table(rows, mode):
    sub = [r for r in rows if r["mode"] == mode]
    by = defaultdict(list)
    for r in sub:
        by[r["cell_id"]].append(r)
    out = []
    for cid, rs in sorted(by.items()):
        p = rs[0].get("params", {})
        med_w, p95_w, max_w = agg(rs, lambda r: r.get("wall_seconds"))
        med_s, _, max_s = agg(rs, lambda r: r.get("n_states"))
        # n_steps counts the IR step and the code step separately (+2 per paired transition;
        # the Explorer's cap check is n_steps // 2 >= max_transitions), so halve it.
        med_t, _, max_t = agg(rs, lambda r: r["n_steps"] // 2 if r.get("n_steps") is not None else None)
        med_r, _, max_r = agg(rs, lambda r: r.get("peak_rss_mb"))
        bad = [r["verdict"] for r in rs if not r["complete"]]
        out.append({"cell_id": cid, "params": p, "n": len(rs),
                    "complete": sum(r["complete"] for r in rs),
                    "verdicts": sorted(set(r["verdict"] for r in rs)),
                    "incomplete": sorted(set(bad)),
                    "wall": (med_w, p95_w, max_w), "states": (med_s, max_s),
                    "steps": (med_t, max_t), "rss": (med_r, max_r)})
    return out


def sweeps(rows):
    import sys
    sys.path.insert(0, str(HERE))
    from gen_grid import grid
    out = defaultdict(list)
    for c in grid():
        out[c["axis"]].append((c["level"], c["cell_id"]))
    return out


def md(rows):
    L = ["# E4 - Cost and scale", "",
         f"Run: `{len(rows)}` runs, budget {rows[0].get('budget_s', 120)} s per run, "
         "one process per run (peak RSS is that process's). Horizon-free runs one at a time "
         "(`runs/e4_free_serial.jsonl`); fixed-horizon runs 4 at a time on 8 physical cores "
         "(`runs/e4_fixed_w4.jsonl`). See README for why the worker count matters.", "",
         "Every run is in the denominator: timeouts, refusals, unknowns and errors "
         "are reported, not dropped. State and transition counts are counts only - "
         "they are not restated as a runtime speedup.", ""]
    for mode, title in (("free", "Horizon-free (H = None)"),
                        ("fixed10", "Fixed horizon (H = 10 s)"),
                        ("fixedT", "Fixed horizon (H = 2T + 5 s)")):
        sub = [r for r in rows if r["mode"] == mode]
        if not sub:
            continue
        done = sum(r["complete"] for r in sub)
        kinds = defaultdict(int)
        for r in sub:
            if r["complete"]:
                kinds[r["verdict"]] += 1
        L += [f"## {title}", "",
              f"Completed (decided and closed): **{done}/{len(sub)}** "
              f"({100.0 * done / len(sub):.1f}%) - "
              + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())), ""]
        inc = defaultdict(int)
        for r in sub:
            if not r["complete"]:
                inc[r["verdict"]] += 1
        if inc:
            L.append("Not completed: " + ", ".join(
                f"{k} {inc[k]}" for k in INCOMPLETE_ORDER if inc.get(k)) + "")
            L.append("")
        med, p95, mx = agg(sub, lambda r: r.get("wall_seconds"))
        rmed, rp95, rmx = agg(sub, lambda r: r.get("peak_rss_mb"))
        L += [f"Wall time (s): median {fmt(med)}, p95 {fmt(p95)}, max {fmt(mx)}  ",
              f"Peak RSS (MB): median {fmt(rmed, 1)}, p95 {fmt(rp95, 1)}, max {fmt(rmx, 1)}", "",
              "| cell | W | B | T (ms) | K | done/n | verdicts | states med/max | transitions med/max | wall med/p95/max (s) | RSS med/max (MB) |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for c in cell_table(rows, mode):
            p = c["params"]
            L.append(
                f"| `{c['cell_id']}` | {p.get('W')} | {p.get('B')} | {p.get('T_ms')} | {p.get('K')} "
                f"| {c['complete']}/{c['n']} | {','.join(c['verdicts'])} "
                f"| {fmt(c['states'][0], 0)}/{fmt(c['states'][1], 0)} "
                f"| {fmt(c['steps'][0], 0)}/{fmt(c['steps'][1], 0)} "
                f"| {fmt(c['wall'][0])}/{fmt(c['wall'][1])}/{fmt(c['wall'][2])} "
                f"| {fmt(c['rss'][0], 1)}/{fmt(c['rss'][1], 1)} |")
        L.append("")
    return "\n".join(L)


def plot(rows, axes_order=("W", "B", "K", "D"), name="e4_cost_full", width=3.1, height=5.2):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available; skipping the figure")
        return
    sw = sweeps(rows)
    by = defaultdict(list)
    for r in rows:
        by[(r["cell_id"], r["mode"])].append(r)
    names = {"W": "input width W (sensors)", "B": "stages B", "T": "wait length T (ms)",
             "K": "cycle repeats K", "D": "all axes together"}
    axes_order = [a for a in axes_order if a in sw]
    fig, axs = plt.subplots(2, len(axes_order), figsize=(width * len(axes_order), height),
                            squeeze=False, sharex="col")
    for col, ax_name in enumerate(axes_order):
        pts = sw[ax_name]
        xs = list(range(len(pts)))
        labels = [str(l) for l, _ in pts]
        for mode, marker in (("free", "o"), ("fixed10", "s"), ("fixedT", "^")):
            label = {"free": "Explorer (no H)", "fixed10": "H = 10 s",
                     "fixedT": "H covers wait"}[mode]
            wall, comp = [], []
            for _, cid in pts:
                rs = by.get((cid, mode), [])
                m, _, _ = agg(rs, lambda r: r.get("wall_seconds"))
                wall.append(m)
                comp.append(100.0 * sum(r["complete"] for r in rs) / len(rs) if rs else None)
            if any(v is not None for v in wall):
                axs[0][col].plot(xs, wall, marker=marker, label=label)
            if any(v is not None for v in comp):
                axs[1][col].plot(xs, comp, marker=marker, label=label)
        for row in (0, 1):
            axs[row][col].set_xticks(xs)
            axs[row][col].set_xticklabels(labels, rotation=45, fontsize=7)
        if any(v for v in axs[0][col].get_lines() for v in v.get_ydata()
               if v is not None and v > 0):
            axs[0][col].set_yscale("log")
        if len(axes_order) > 1:
            axs[0][col].set_title(names[ax_name], fontsize=8)
        axs[1][col].set_ylim(-5, 105)
        axs[1][col].set_xlabel(names[ax_name] + (" (W/B/K)" if ax_name == "D" else ""), fontsize=8)
    axs[0][0].set_ylabel("median time (s)", fontsize=8)
    axs[1][0].set_ylabel("decided runs (%)", fontsize=8)
    fig.align_ylabels(axs[:, 0])
    handles, labels = axs[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3,
               fontsize=7, frameon=False)
    top = 0.91 if len(axes_order) == 1 else 0.94
    fig.tight_layout(rect=(0, 0, 1, top))
    d = HERE / "figs"
    d.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(d / f"{name}.{ext}", dpi=200)
    print(f"figure -> {d}/{name}.pdf|png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="+", default=[str(HERE / "runs/e4_free_serial.jsonl"),
                                                 str(HERE / "runs/e4_fixed_w4.jsonl")])
    a = ap.parse_args()
    rows = [r for f in a.run if Path(f).exists() for r in load(f)]
    (HERE / "RESULTS.md").write_text(md(rows))
    print(f"{len(rows)} runs -> {HERE / 'RESULTS.md'}")
    plot(rows)                                                        # all sweeps (appendix/record)
    plot(rows, axes_order=("D",), name="e4_cost", width=3.4, height=3.6)  # paper: all axes together


if __name__ == "__main__":
    main()
