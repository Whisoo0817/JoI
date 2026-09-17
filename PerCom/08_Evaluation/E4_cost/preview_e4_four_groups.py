"""Restore historical W/B/K/combined four-group layout with current E4 results."""
import json
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
from gen_grid import grid

HERE = Path(__file__).resolve().parent
OUT = HERE / 'figs/options'
MODES = [('free', 'e4_free_serial.jsonl', 'Explorer', '#2a78d6', 'o'),
         ('explicit', 'e4_explicit_w4.jsonl', 'Explicit-state exploration', '#d96332', 's')]
rows = {}
for mode, filename, *_ in MODES:
    by = defaultdict(list)
    for line in (HERE/'runs'/filename).read_text().splitlines():
        r = json.loads(line)
        assert r['mode'] == mode
        by[r['cell_id']].append(r)
    assert len(by) == 30
    rows[mode] = by
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':9,
                     'axes.edgecolor':'#777777', 'xtick.color':'#555555',
                     'ytick.color':'#555555', 'pdf.fonttype':42, 'ps.fonttype':42})
fig, axes = plt.subplots(2, 4, figsize=(12.4, 4.6), sharex='col',
                         gridspec_kw={'height_ratios':[2.6, 1], 'hspace':0.16})
axes_order = [('W','(a) Sensor count','Sensors (W)'),
              ('B','(b) Stage count','Stages (B)'),
              ('K','(c) Repetition count','Repetitions (K)'),
              ('D','(d) Combined scaling','Configuration (W, B, K)')]
summary = {}
for col, (axis,title,xlabel) in enumerate(axes_order):
    points = [p for p in grid() if p['axis'] == axis]
    labels = [str(p['level']) if axis != 'D' else p['level'].replace('/', ',') for p in points]
    top, bottom = axes[:,col]
    top.set_title(title, fontsize=10, pad=10)
    summary[axis] = {}
    for mode, _, label, color, marker in MODES:
        times, counts, timeout_indices = [], [], []
        for i,p in enumerate(points):
            rs = rows[mode][p['cell_id']]
            assert len(rs) == 3 and {r['rep'] for r in rs} == {0,1,2}
            n = sum(r['verdict'] == 'EQUIV' and r['closed'] for r in rs)
            counts.append(n)
            if n == 3:
                times.append(max(r['wall_seconds'] for r in rs))
            else:
                assert all(r['verdict'] == 'TIMEOUT' for r in rs)
                times.append(float('nan'))
                timeout_indices.append(i)
        x = list(range(len(points)))
        top.plot(x,times,color=color,marker=marker,ms=4,lw=1.5,mec='white',mew=0.5,label=label)
        # Axis-fraction placement makes timeouts categorical, not runtime observations.
        top.plot(timeout_indices,[0.97 if mode=='free' else 0.915]*len(timeout_indices),
                 linestyle='none',color=color,marker=marker,ms=4,mec='white',mew=0.5,
                 transform=top.get_xaxis_transform(),clip_on=False)
        bottom.plot(x,counts,color=color,marker=marker,ms=4,lw=1.5,mec='white',mew=0.5)
        summary[axis][mode] = [{'cell_id':p['cell_id'],'completed_runs':n,
                                'slowest_completed_s':t if n==3 else None}
                               for p,n,t in zip(points,counts,times)]
    top.set_yscale('log')
    top.set_ylim(0.01,420)
    top.set_yticks([0.01,0.1,1,10,120])
    top.set_yticklabels(['0.01','0.1','1','10','120'])
    top.yaxis.set_minor_locator(NullLocator())
    top.axhspan(140,420,color='#f2f2f2',zorder=0)
    top.text(0.02,0.95,'Timeout',transform=top.transAxes,fontsize=7,color='#666666',va='center')
    top.axhline(120,color='#999999',lw=0.65,ls=(0,(2,3)))
    top.grid(axis='y',color='#e8e8e8',lw=0.5)
    bottom.set_ylim(-0.35,3.35)
    bottom.set_yticks([0,3]); bottom.set_yticklabels(['0/3','3/3'])
    bottom.grid(axis='y',color='#e8e8e8',lw=0.5)
    bottom.set_xticks(range(len(points)))
    bottom.set_xticklabels(labels,rotation=40 if axis=='D' else 0,
                          ha='right' if axis=='D' else 'center',fontsize=8)
    bottom.set_xlabel(xlabel,fontsize=9)
    for ax in (top,bottom):
        ax.set_axisbelow(True)
        ax.spines[['top','right']].set_visible(False)
        ax.set_xlim(-0.45,len(points)-0.55)
axes[0,0].set_ylabel('Checking time (s)')
axes[1,0].set_ylabel('Completed runs')
handles,labels=axes[0,0].get_legend_handles_labels()
fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(0.5,1.005),ncol=2,
           frameon=False,fontsize=10,columnspacing=2)
fig.subplots_adjust(left=0.065,right=0.99,top=0.84,bottom=0.24,wspace=0.33)
fig.text(0.5,0.025,'Wait fixed at 2 min. Panels (a)–(c) vary one parameter from W=2, B=2, K=5; panel (d) varies all three.',
         ha='center',fontsize=8,color='#555555')
for ext in ['png','pdf']:
    fig.savefig(OUT/f'E_four_groups_current.{ext}',dpi=200)
(OUT/'E_four_groups_current.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'E_four_groups_current.md').write_text('''# Four-group E4 preview

Restores the historical W / B / K / combined layout from commit e61f2de, using current Explorer and explicit-state runs. Upper plots use the slowest of three runs, only where all three return EQUIV with closed exploration. Gray strips show categorical timeout markers; their heights do not represent runtimes. Lower plots show completed runs out of three. Each configuration has three runs; shared configurations occur in multiple panels. The wait-duration sweep is not shown here.

Sources: `runs/e4_free_serial.jsonl` and `runs/e4_explicit_w4.jsonl`. Explorer ran serially and the explicit-state baseline ran four workers on an eight-core host. This is a descriptive comparison of those configurations, not a matched-load speedup claim. No new measurements were made. The older horizon-limited baselines are not included.
''')
print('Saved E_four_groups_current.png and .pdf')
