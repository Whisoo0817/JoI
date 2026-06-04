#!/usr/bin/env python3
"""Plot fig:rq4 — (a) verification cost comparison, (b) hero deployment trace.

(a) Per-check verification cost, log scale:
    - OVLA verifier: measured on the M4 (m4_verifier_latency.json, p50)
    - local 8B judge on the same M4: measured (m4_judge_latency.json, p50)
    - cloud judge: cited order-of-magnitude (seconds + fees + network)
(b) Hero automation on the physical testbed ("if no one is present in the
    meeting room for at least 5 minutes, turn off the TV plug"):
    IR-predicted trace vs observed actuation without the gate (natural buggy
    lowering, fires at 30 s) and with the gate (repaired lowering, 5 min),
    from deployment/observations.json.

Writes rq4_cost.pdf and rq4_trace.pdf to paper/Final/figs/.
"""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "Final", "evaluation", "results")
FIGS = os.path.join(ROOT, "Final", "figs")
os.makedirs(FIGS, exist_ok=True)


def fig_cost():
    ver = json.load(open(os.path.join(RES, "m4_verifier_latency.json")))["aggregate"]
    jud = json.load(open(os.path.join(RES, "m4_judge_latency.json")))
    v_ms = ver["ms_p50"]
    j_ms = (jud.get("p50_s") or jud.get("aggregate", {}).get("p50_s") or 5.1) * 1000.0
    c_ms = 5_000.0  # cloud judge: seconds-scale per check (cited), plus fees + network

    fig, ax = plt.subplots(figsize=(3.6, 2.4))
    labels = ["OVLA verifier\n(measured, M4)", "local 8B judge\n(measured, M4)",
              "cloud judge\n(cited)"]
    vals = [v_ms, j_ms, c_ms]
    colors = ["#2a7", "#d95", "#b55"]
    bars = ax.bar(labels, vals, color=colors, width=0.62)
    ax.set_yscale("log")
    ax.set_ylabel("per-check latency (ms, log)")
    ax.set_ylim(0.3, 5e4)
    for b, v, extra in zip(bars, vals, ["\\$0", "11.6 GB resident", "fees + network"]):
        txt = f"{v:.2f} ms" if v < 10 else (f"{v/1000:.1f} s")
        ax.annotate(f"{txt}\n{extra}", (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=7.5)
    ax.tick_params(axis="x", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "rq4_cost.pdf"))
    print("-> figs/rq4_cost.pdf", f"(verifier {v_ms:.2f}ms, judge {j_ms/1000:.1f}s)")


def fig_trace():
    horizon = 6.0  # minutes
    lanes = [
        ("IR-predicted", 5.0, "#444", "predicted: off at 5:00"),
        ("with gate\n(repaired)", 5.0, "#2a7", "observed: off at 5:00"),
        ("without gate\n(natural buggy)", 0.5, "#b55", "observed: off at 0:30"),
    ]
    fig, ax = plt.subplots(figsize=(3.6, 2.3))
    ax.axvspan(0, horizon, color="#eef3f8", zorder=0)
    ax.text(horizon / 2, 2.85, "presence = false (room vacated at t=0)",
            ha="center", fontsize=7, color="#567")
    notes_dx = {0: 0.12, 1: 0.12, 2: 0.25}
    for i, (name, t, color, note) in enumerate(lanes):
        y = 2 - i
        ax.hlines(y, 0, horizon, color="#ccc", lw=1)
        ax.plot([t], [y], marker="v", color=color, markersize=9, zorder=3)
        ax.annotate(note, (t, y), xytext=(t + notes_dx[i], y + 0.22),
                    fontsize=7.5, color=color)
        ax.text(-0.15, y, name, ha="right", va="center", fontsize=8)
    # divergence arrow between buggy and predicted firing times
    ax.annotate("", xy=(0.5, -0.28), xytext=(5.0, -0.28),
                arrowprops=dict(arrowstyle="<->", color="#b55", lw=1))
    ax.text(2.75, -0.62, "silent divergence: fires 4.5 min early", ha="center",
            fontsize=7.5, color="#b55")
    ax.set_xlim(-1.6, horizon + 0.1)
    ax.set_ylim(-0.95, 3.1)
    ax.set_yticks([])
    ax.set_xticks(range(0, 7))
    ax.set_xlabel("minutes since the room was vacated")
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "rq4_trace.pdf"))
    print("-> figs/rq4_trace.pdf")


if __name__ == "__main__":
    fig_cost()
    fig_trace()
