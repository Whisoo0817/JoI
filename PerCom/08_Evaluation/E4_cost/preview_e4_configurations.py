"""Preview E4 combined scaling at (W, B, K); wait fixed at 120 seconds."""
import json
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
from gen_grid import DIAGONAL

HERE = Path(__file__).resolve().parent
OUT = HERE / 'figs/options'
MODES = [('free', 'e4_free_serial.jsonl', 'Explorer', '#2a78d6', 'o', -0.085),
         ('explicit', 'e4_explicit_w4.jsonl', 'Explicit-state exploration', '#d96332', 's', 0.085)]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                     'axes.edgecolor': '#777777', 'axes.labelcolor': '#252525',
                     'xtick.color': '#555555', 'ytick.color': '#555555',
                     'pdf.fonttype': 42, 'ps.fonttype': 42})
fig, (status, ax) = plt.subplots(2, 1, figsize=(5.7, 3.9), sharex=True,
                                gridspec_kw={'height_ratios': [0.55, 3], 'hspace': 0.09})
summary = {}
for mode, filename, label, color, marker, offset in MODES:
    by = defaultdict(list)
    for line in (HERE / 'runs' / filename).read_text().splitlines():
        r = json.loads(line)
        assert r['mode'] == mode
        by[r['cell_id']].append(r)
    values = []
    details = []
    for i, (w, b, k) in enumerate(DIAGONAL):
        cid = f'W{w}_B{b}_T120000_K{k}'
        rs = by[cid]
        assert len(rs) == 3 and {r['rep'] for r in rs} == {0, 1, 2}
        complete = all(r['verdict'] == 'EQUIV' and r['closed'] for r in rs)
        if complete:
            t = max(r['wall_seconds'] for r in rs)
            assert t < 120
            values.append(t)
            ax.annotate(f'{t:.2f}' if t < 10 else f'{t:.1f}', (i, t),
                        xytext=(0, 8), textcoords='offset points', ha='center',
                        fontsize=7.5, color=color)
        else:
            assert all(r['verdict'] == 'TIMEOUT' for r in rs)
            values.append(float('nan'))
            status.plot(i+offset, 0.5, marker=marker, color=color, ms=5.2,
                        mec='white', mew=0.6)
        details.append({'configuration': [w, b, k], 'wait_s': 120,
                        'completed': complete,
                        'slowest_completed_s': values[-1] if complete else None})
    ax.plot(range(len(DIAGONAL)), values, label=label, color=color, marker=marker,
            lw=1.7, ms=5, mec='white', mew=0.6)
    summary[mode] = details
status.set_facecolor('#f2f2f2')
status.set_ylim(0, 1)
status.set_yticks([])
status.text(-0.02, 0.5, 'Timed out', transform=status.transAxes, ha='right',
            va='center', fontsize=8, color='#555555')
status.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
for s in status.spines.values():
    s.set_visible(False)
ax.set_yscale('log')
ax.set_ylim(0.01, 200)
ax.set_yticks([0.01, 0.1, 1, 10, 120])
ax.set_yticklabels(['0.01', '0.1', '1', '10', '120'])
ax.yaxis.set_minor_locator(NullLocator())
ax.axhline(120, color='#999999', lw=0.8, ls=(0, (2, 3)))
ax.text(6.2, 92, '120 s budget', ha='right', va='top', fontsize=7.5, color='#777777')
ax.set_xlim(-0.4, 6.4)
ax.set_xticks(range(len(DIAGONAL)))
ax.set_xticklabels([f'({w}, {b}, {k})' for w, b, k in DIAGONAL], fontsize=8)
ax.set_xlabel('Configuration (W, B, K)', labelpad=7)
ax.set_ylabel('Checking time (s)', labelpad=8)
ax.grid(axis='y', color='#e5e5e5', lw=0.6)
ax.set_axisbelow(True)
ax.spines[['top', 'right']].set_visible(False)
handles, labels = ax.get_legend_handles_labels()
fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.56, 1.0),
           ncol=2, frameon=False, fontsize=8.5, handlelength=2.0, columnspacing=1.5)
fig.text(0.56, 0.015, 'W: sensors   B: stages   K: repetitions   |   Wait: 2 min',
         ha='center', va='bottom', fontsize=8, color='#555555')
fig.subplots_adjust(left=0.17, right=0.98, top=0.84, bottom=0.21)
for ext in ['png', 'pdf']:
    fig.savefig(OUT / f'D_combined_configurations.{ext}', dpi=240)
(OUT / 'D_combined_configurations.json').write_text(json.dumps(summary, indent=2)+'\n')
(OUT / 'D_combined_configurations.md').write_text('''# E4 combined configuration preview

Seven existing combined-scaling configurations from `gen_grid.DIAGONAL`. W is sensor count, B is stage count, and K is repetition count. Wait duration is fixed at 2 min. These seven programs are a subset of the full 30-program E4 set.

Source files: `runs/e4_free_serial.jsonl`, `runs/e4_explicit_w4.jsonl`. Each point is the slowest of three completed runs; completion requires EQUIV and closed exploration in all three runs. All other displayed cases timed out in all three runs. The timeout strip is categorical; its marker locations do not encode runtimes. Lines connect measured configurations as visual guides, not fitted curves.

Explorer ran serially, while explicit-state exploration used four concurrent workers on an eight-core host. The comparison describes these configurations and is not a matched-load speedup measurement. No new experiment was performed.
''')
print(json.dumps(summary, indent=2))
