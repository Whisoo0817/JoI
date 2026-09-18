#!/usr/bin/env python3
"""Render the existing common-set results; does not rerun or reaggregate experiments."""
from pathlib import Path
import json
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

HERE=Path(__file__).resolve().parent
JOI=HERE.parents[2]
SOURCE=JOI/'PerCom/03_Motivation/motivation_judge/results/summary_common.json'
data=json.loads(SOURCE.read_text())
items=[('VAR','var_rename'),('CMP','comparator_flip'),('UNIT','time_unit'),('GRP','exists_spelling'),('BR','branch_swap'),('ELS','else_split'),('DLY','delay_split'),('UNR','loop_unroll'),('PHS','phase_flag'),('WPC','wait_precheck'),('PHV','period_halve')]
judges=['qwen','gpt','claude']
labels=['Qwen3.5-9B','GPT-5.4-mini','Claude-Sonnet-5']
colors=['#2878B5','#D97732','#7560AA']
ns=[data['judges']['qwen']['by_type'][k]['pairs'] for _,k in items]
assert sum(ns)==168 and len(data['common_seeds'])==52
for j in judges:
 assert [data['judges'][j]['by_type'][k]['pairs'] for _,k in items]==ns
 assert sum(data['judges'][j]['by_type'][k]['rejected'] for _,k in items)==data['judges'][j]['overall']['rejected']
# Register the user-installed Microsoft core fonts; never silently substitute.
font_dir=Path.home()/'.local/share/fonts/msttcorefonts'
for font_file in font_dir.glob('*.TTF'):
 font_manager.fontManager.addfont(str(font_file))
font_manager.findfont('Times New Roman',fallback_to_default=False)
plt.rcParams.update({'font.family':'Times New Roman','font.size':7,'pdf.fonttype':42,'ps.fonttype':42,'axes.linewidth':.5})
fig,ax=plt.subplots(figsize=(3.5,2.30))
fig.subplots_adjust(left=.125,right=.995,bottom=.22,top=.77)
x=np.arange(11,dtype=float); x[4:]+=.5; x[6:]+=.5
width=.24
for i,j in enumerate(judges):
 vals=[100*data['judges'][j]['by_type'][k]['rate'] for _,k in items]
 ax.bar(x+(i-1)*width,vals,width=width,color=colors[i],label=labels[i],linewidth=0,zorder=3)
ax.set_xlim(-.6,x[-1]+.6); ax.set_ylim(0,100)
ax.set_yticks([0,25,50,75,100]); ax.set_ylabel('Rewrite rejection rate (%)',fontsize=7,labelpad=3)
ax.set_xticks(x,[f'{abbr}\n{n}' for (abbr,_),n in zip(items,ns)],fontsize=6)
ax.set_xlabel('Rewrite type / number of variants',fontsize=6.5,labelpad=3)
ax.tick_params(length=2,width=.5,pad=2)
ax.spines[['top','right']].set_visible(False)
ax.set_axisbelow(True); ax.grid(axis='y',color='#E3E3E3',linewidth=.5)
for l,r,lab in [(0,3,'Notation'),(4,5,'Logic'),(6,10,'Temporal')]:
 ax.plot([x[l]-.4,x[r]+.4],[1.045,1.045],transform=ax.get_xaxis_transform(),color='#777777',linewidth=.5,clip_on=False)
 ax.text((x[l]+x[r])/2,1.07,lab,transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=6.5)
ax.legend(loc='lower center',bbox_to_anchor=(.47,1.23),ncol=3,frameon=False,fontsize=5.8,handlelength=1.2,handletextpad=.35,columnspacing=.8,borderaxespad=0)
for ext in ['pdf','png']:
 fig.savefig(HERE/f'judge_rewrites.{ext}',dpi=300,facecolor='white')
shutil.copy2(HERE/'judge_rewrites.pdf',JOI.parent/'overleaf-paper/figures/percom/judge_rewrites.pdf')
(HERE/'judge_plot_data.json').write_text(json.dumps({'source':str(SOURCE.relative_to(JOI)),'common_originals':52,'types':[{'abbreviation':abbr,'type':key,'n':n,'rejections':{j:data['judges'][j]['by_type'][key]['rejected'] for j in judges}} for (abbr,key),n in zip(items,ns)]},indent=2)+'\n')
print('Rendered 11 rewrite types from the 168 common-set variants.')
