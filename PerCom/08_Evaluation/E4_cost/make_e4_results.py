"""E4 tables from the reported runs.

  ~/temp/bin/python make_e4_results.py [--run ...]

Writes RESULTS.md (every program, every mode) and e4_table.md (the paper table).

Reporting rules (HANDOFF.md common rules, confirmed_ir_evaluation_2026-09-10 §E4):
- TIMEOUT / OOM / ERROR / REFUSED / UNKNOWN all stay in the denominator.
- State and transition counts are reported as counts. They are never restated as a
  runtime speedup; wall time and peak RSS are reported on their own.
- Each mode is reported separately, never merged.
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
         "one process per run (peak RSS is that process's). Explorer runs one at a time "
         "(`runs/e4_free_serial.jsonl`); explicit-state and fixed-step runs 4 at a time on 8 physical cores "
         "(`runs/e4_explicit_w4.jsonl`, `runs/e4_fixed_w4.jsonl`). See README for why the worker count matters.", "",
         "Every run is in the denominator: timeouts, refusals, unknowns and errors "
         "are reported, not dropped. State and transition counts are counts only - "
         "they are not restated as a runtime speedup.", ""]
    for mode, title in (("free", "Explorer"),
                        ("explicit", "Explicit-state exploration without timer zones (main baseline)"),
                        ("fixedT", "Fixed-step simulation through every wait (100 ms steps, until 2T + 5 s)")):
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


# Paper table: one row per setting, slowest of the three runs. A program counts as decided
# only when all three runs decided it. Rows are the base program, the far end of each
# axis, and the two largest diagonal programs (whisoo 2026-09-17: table instead of figure).
PAPER_ROWS = [
    ("Base (2 sensors, 2 stages, 2 min wait, 5 repeats)", "W2_B2_T120000_K5"),
    ("Sensors 4", "W4_B2_T120000_K5"),
    ("Sensors 7", "W7_B2_T120000_K5"),
    ("Stages 6", "W2_B6_T120000_K5"),
    ("Wait 0.1 s", "W2_B2_T100_K5"),
    ("Wait 4 h", "W2_B2_T14400000_K5"),
    ("Repeats 10", "W2_B2_T120000_K10"),
    ("Repeats 200", "W2_B2_T120000_K200"),
    ("All: 5 sensors, 5 stages, 20 repeats", "W5_B5_T120000_K20"),
    ("All: 7 sensors, 6 stages, 100 repeats", "W7_B6_T120000_K100"),
]
PAPER_MODES = (("free", "Explorer"), ("explicit", "Explicit-state"))


def paper_cells(rows, mode, cid):
    rs = [r for r in rows if r["mode"] == mode and r["cell_id"] == cid]
    if not rs or not all(r["complete"] for r in rs):
        return ("timeout" if rs and all(r["verdict"] == "TIMEOUT" for r in rs) else "not decided"), "—"
    states = max(r["n_states"] for r in rs)
    t = max(r["wall_seconds"] for r in rs)
    return f"{states:,}", (f"{t:.2f} s" if t < 10 else f"{t:.1f} s")


def paper_table(rows):
    head = "| Program | " + " | ".join(f"{n} states | {n} time" for _, n in PAPER_MODES) + " |"
    L = [head, "|---|" + "---:|" * (2 * len(PAPER_MODES))]
    for label, cid in PAPER_ROWS:
        cells = []
        for mode, _ in PAPER_MODES:
            st_, t = paper_cells(rows, mode, cid)
            cells += [st_, t]
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    decided = []
    for mode, _ in PAPER_MODES:
        by = defaultdict(list)
        for r in rows:
            if r["mode"] == mode:
                by[r["cell_id"]].append(r)
        n = sum(all(r["complete"] for r in rs) for rs in by.values())
        decided += [f"**{n} / {len(by)}**", "—"]
    L.append("| Programs decided | " + " | ".join(decided) + " |")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="+", default=[str(HERE / "runs/e4_free_serial.jsonl"),
                                                 str(HERE / "runs/e4_explicit_w4.jsonl"),
                                                 str(HERE / "runs/e4_fixed_w4.jsonl")])
    a = ap.parse_args()
    # fixed10 (a 10 s horizon) is measured but not reported: it never reaches the programs'
    # timeouts, so its verdict is not comparable (whisoo 2026-09-17).
    rows = [r for f in a.run if Path(f).exists() for r in load(f) if r["mode"] != "fixed10"]
    (HERE / "RESULTS.md").write_text(md(rows))
    table = "\n".join(paper_table(rows)) + "\n"
    (HERE / "e4_table.md").write_text(table)
    print(table)
    print(f"{len(rows)} runs -> {HERE / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
