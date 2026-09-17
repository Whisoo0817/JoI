"""Preview current E4 results without changing manuscript or historical figures."""
import json
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator

HERE = Path(__file__).resolve().parent
OUT = HERE / 'figs/options'
MODES = [
    ('free', 'e4_free_serial.jsonl', 'Explorer', '#2a78d6', '-'),
    ('explicit', 'e4_explicit_w4.jsonl', 'Explicit-state exploration', '#d96332', '-'),
]
LIMIT = 120
summary = {}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                     'axes.labelcolor': '#252525', 'axes.edgecolor': '#666666',
                     'xtick.color': '#555555', 'ytick.color': '#555555',
                     'pdf.fonttype': 42, 'ps.fonttype': 42})
fig, ax = plt.subplots(figsize=(3.65, 2.8))
for mode, filename, label, color, style in MODES:
    groups = defaultdict(list)
    for line in (HERE / 'runs' / filename).read_text().splitlines():
        r = json.loads(line)
        assert r['mode'] == mode
        groups[r['cell_id']].append(r)
    assert len(groups) == 30
    assert all(len(rs) == 3 and {r['rep'] for r in rs} == {0, 1, 2} for rs in groups.values())
    times = sorted(max(r['wall_seconds'] for r in rs) for rs in groups.values()
                   if all(r['verdict'] == 'EQUIV' and r['closed'] for r in rs))
    assert all(0.01 <= t <= LIMIT for t in times)
    x = [0.01] + times + [LIMIT]
    y = [0] + list(range(1, len(times) + 1)) + [len(times)]
    marker_options = {'marker': 's' if mode == 'explicit' else 'o',
                      'markersize': 3.5,
                      'markeredgecolor': 'white', 'markeredgewidth': 0.5,
                      'markevery': list(range(1, len(times) + 1))}
    ax.step(x, y, where='post', color=color, lw=1.8, ls=style, label=label,
            **marker_options)
    ax.annotate(str(len(times)), (LIMIT, len(times)), xytext=(4, 0),
                textcoords='offset points', va='center', fontsize=9, fontweight='bold',
                annotation_clip=False, color=color)
    summary[mode] = {'programs': 30, 'completed': len(times), 'undecided': 30-len(times),
                     'within_1s': sum(t <= 1 for t in times),
                     'within_5s': sum(t <= 5 for t in times),
                     'slowest_completed_s': max(times), 'times_s': times}
assert summary['free']['completed'] == 28
assert summary['explicit']['completed'] == 12
n5 = summary['free']['within_5s']
ax.axvline(5, color='#777777', lw=0.8, ls=(0, (2, 3)), zorder=0)
ax.plot(5, n5, 'o', color='#2a78d6', ms=4.2, mec='white', mew=0.8, zorder=4)
ax.annotate(f'{n5}/30 within 5 s', xy=(5, n5), xytext=(8, 16.5), fontsize=7.2,
            arrowprops={'arrowstyle': '-', 'color': '#666666', 'lw': 0.7}, color='#333333')
ax.set_xscale('log')
ax.set_xlim(0.01, LIMIT)
ax.set_ylim(0, 31.5)
ax.set_xticks([0.01, 0.1, 1, 5, 20, 120])
ax.set_xticklabels(['0.01', '0.1', '1', '5', '20', '120'])
ax.xaxis.set_minor_locator(NullLocator())
ax.set_yticks(range(0, 31, 5))
ax.set_xlabel('Checking time per program (s)')
ax.set_ylabel('Programs decided (out of 30)')
ax.grid(axis='y', color='#e6e6e6', lw=0.6)
ax.set_axisbelow(True)
ax.spines[['top', 'right']].set_visible(False)
ax.legend(loc='upper left', bbox_to_anchor=(0, 1.24), frameon=False,
          fontsize=7.5, borderaxespad=0, handlelength=2.3, labelspacing=0.5)
fig.subplots_adjust(left=0.16, right=0.92, bottom=0.19, top=0.80)
for ext in ['pdf', 'png']:
    fig.savefig(OUT / f'C_cumulative_current.{ext}', dpi=240)
(OUT / 'C_cumulative_current.json').write_text(json.dumps(summary, indent=2)+'\n')
(OUT / 'C_cumulative_current.md').write_text('''# E4 cumulative figure preview

For each of 30 programs, a method counts as complete only if all three runs return EQUIV with closed exploration. The plotted time is the slowest of those three runs. Undecided programs remain in the denominator of 30 and do not appear as completed at the budget limit. The horizontal axis is logarithmic. The run budget is 120 s.

Source: `runs/e4_free_serial.jsonl` and `runs/e4_explicit_w4.jsonl`. Explorer ran serially; explicit-state exploration used four concurrent workers on an eight-core host. These curves describe those configurations, not a matched-load speedup experiment.

The proposed fixed-step exploration with the same completion criterion has not been measured. Historical bounded fixed-step results are not included in this comparison.

Suggested caption: Cumulative number of programs decided within each checking time. Times are the slowest of three runs, and a program counts as decided only when all three runs complete. Explorer decided 28 of 30 programs; explicit-state exploration decided 12.
''')
print(json.dumps({k: {a:b for a,b in v.items() if a != 'times_s'} for k,v in summary.items()}, indent=2))
