"""Summarize measured remaining72 outputs; does not alter any experiment record."""
from pathlib import Path
import json,hashlib,datetime,csv
import run_batch as B
HERE=Path(__file__).resolve().parent
BATCHES=['batch_er','batch_official','batch_community']

def shape(step):
 out={'op':step['op']}
 for key in ('edge','for','timeout','period','until','count'):
  if key in step:out[key]=step[key]
 for key in ('body','then','else','on_timeout'):
  if isinstance(step.get(key),list):out[key]=[shape(s) for s in step[key]]
 return out

def paths(steps,prefix=''):
 out=[]
 for s in steps:
  p=prefix+'/'+s['op'];out.append(p)
  for key in ('body','then','else','on_timeout'):
   if isinstance(s.get(key),list):out.extend(paths(s[key],p+':'+key))
 return out

def main():
 rows=[];batch_stats=[]
 for name in BATCHES:
  p=HERE/name;c=B.load('summary_'+name,p/'cases.py');case_by={x['id']:x for x in c.CASES}
  measured=json.loads((p/'runs/results.json').read_text())
  assert set(case_by)=={r['id'] for r in measured},name
  for r in measured:
   c=case_by[r['id']];hs=r.get('histories',[])
   exact=sum(h.get('exact',False) for h in hs)
   full=bool(hs) and exact==len(c['histories']) and not r.get('error')
   row={'id':r['id'],'batch':name,'candidate_label':r['label'],'candidate_reason':r['label_reason'],'all_frozen_histories_exact':full,'exact_histories':exact,'histories':len(c['histories']),'source_url':c.get('source_url'),'source_record':c.get('source',{}),'alternative_interpretation':c.get('alternative_interpretation',c.get('alternatives',[])),'favorable_bias':c.get('favorable_bias',[]),'interpretation':c['spec'],'assumptions':c.get('transcription',[]),'alternative_bias':c.get('alternative_bias',c.get('alternatives_bias',c.get('bias',[]))),'automations':len(r.get('automations',[])),'operator_compositions':[{ 'name':a['name'],'tree':[shape(s) for s in a['ir']['timeline']],'paths':sorted(set(paths(a['ir']['timeline'])))} for a in r.get('automations',[])],'raw_results':f'{name}/runs/results.json'}
   rows.append(row)
  batch_stats.append({'batch':name,'cases':len(measured),'histories':sum(len(r.get('histories',[])) for r in measured),'exact':sum(sum(h.get('exact',False) for h in r.get('histories',[])) for r in measured)})
 rows.sort(key=lambda r:r['id'])
 expected=json.loads((HERE.parent/'extension72_plan/cohort_snapshot.json').read_text())['remaining_ids']
 assert sorted(expected)==[r['id'] for r in rows]
 supplemental=[]
 for rel in ['batch_community/runs/sensitivity_results.json','batch_er/sensitivity/runs/results.json']:
  p=HERE/rel
  if p.exists():
   rs=json.loads(p.read_text());hs=[h for r in rs for h in r.get('histories',[])]
   supplemental.append({'path':rel,'case_ids':[r['id'] for r in rs],'histories':len(hs),'exact':sum(h['exact'] for h in hs)})
 fallback=json.loads((HERE/'batch_er/runs/joi_024.json').read_text())
 result={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'provenance':'agent-derived interpretations and finite reference execution; not new human validation','cases':len(rows),'all_frozen_histories_exact_cases':sum(r['all_frozen_histories_exact'] for r in rows),'histories':sum(r['histories'] for r in rows),'exact_histories':sum(r['exact_histories'] for r in rows),'batches':batch_stats,'supplemental_not_in_main_denominator':supplemental,'joi_fallback':{'id':'E1-024','scope':fallback['scope'],'exact_histories':sum(h['exact'] for h in fallback['histories']),'histories':len(fallback['histories'])},'rows':rows}
 revision_path=HERE/'e1_024_rolling/REVISION.json'
 revision_notice=None
 if revision_path.exists():
  revision=json.loads(revision_path.read_text())
  measured_revision=json.loads((revision_path.parent/'results.json').read_text())
  original24=next(x for x in json.loads((HERE/'batch_er/runs/results.json').read_text()) if x['id']=='E1-024')
  revised={h['name']:h for h in measured_revision['histories']}
  assert all(revised[h['name']]['expected']==h['expected'] and revised[h['name']]['exact'] for h in original24['histories'])
  result['follow_up_revisions']=[revision]
  result['main_cohort_with_follow_up']={'cases':72,'all_frozen_histories_exact_cases':72,'histories':241,'exact_histories':241,'note':'Substitutes E1-024 revision on its unchanged original3 histories; original run statistics above are preserved. Additional9 revision histories are separate.'}
  revision_notice='> **Follow-up, 2026-09-18:** E1-024 now has an ordinary Timeline IR rolling-budget implementation: original3/3 plus9/9 expiry/boundary histories. See [the revision](e1_024_rolling/README.md) and [raw results](e1_024_rolling/results.json). The71/72 and239/241 counts below describe the preserved initial candidates. Substituting this revision on the same original histories yields72/72 and241/241, subject to the recorded interpretations and integer-second scope. The initial raw results remain unchanged.'
 (HERE/'summary.json').write_text(json.dumps(result,indent=1,ensure_ascii=False))
 with (HERE/'results.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['id','batch','exact_histories','histories','all_frozen_histories_exact','candidate_label','candidate_reason'])
  for r in rows:w.writerow([r[k] for k in ['id','batch','exact_histories','histories','all_frozen_histories_exact','candidate_label','candidate_reason']])
 lines=['# Remaining72 E1 reference execution','',f"All72 requests were attempted. {result['all_frozen_histories_exact_cases']}/72 candidates reproduced every frozen history; {result['exact_histories']}/{result['histories']} histories matched exactly. Interpretations were inferred by Astra agents using source records and the prior20, without a new author semantic audit.",'','## What this result means','','The measured unit is a request under its explicitly frozen interpretation, not every possible interpretation of the source. The original20 remain unchanged. These72 extend the in-scope cohort to92 attempted requests, but a count of92 successful adequacy cases is not supported. The language, fixed selections, waveform assumptions, independently deployed Timelines and other qualifications are retained in per-case records. These are finite test histories, not all-input verification or physical-device validation.','','E1-024 is a partial candidate: a conservative single-session cooldown matches1/3 histories and fails the two legal split-session/cumulative-budget histories. The demand-serving interpretation adds an availability obligation beyond the source\'s literal never-exceed safety constraint: refusing legal requests could satisfy that literal safety property. Thus the two failures concern the declared stronger interpretation, not an inherent source or IR impossibility. A separately executed JoI mutable-accumulator fallback matches3/3 on these shorter-than48h histories; it does not implement general rolling-window expiry and is not claimed complete.','','## Main frozen cohort','','| Batch | Requests | Exact histories |','|---|---:|---:|']
 for b in batch_stats:lines.append(f"| {b['batch']} | {b['cases']} | {b['exact']}/{b['histories']} |")
 lines+=['','## Supplemental diagnostics kept separate','']
 for x in supplemental:lines.append(f"- `{x['path']}`: {x['exact']}/{x['histories']} exact after repairs; these are additional diagnostics on existing cases, not new requests or additions to the241 main histories.")
 lines+=['','Known pre-repair failures and encoding changes are retained in each batch archive. Parent review exposed gaps after candidates passed their initial histories; expectations were frozen before those repairs. A main-cohort pass therefore must not be promoted to an all-input semantic guarantee.','','## Bias and scope','','- The same project and related agents developed assumptions, expected traces and encodings, although expectations were hashed before encoding. This procedural separation does not establish independent oracle validity.','- Prior20 conventions guide event/startup/reentry and property-to-controller choices; assumptions can make a requirement easier or narrower. Alternatives are recorded rather than counted as validated.','- Official examples were checked against live2026-09-17 source after the corpus2026-09-13 freeze. Source drift, especially E1-068 prose versus YAML, is disclosed; this is not a claim that every live variant equals the frozen normalization.','- E1-078 adopts manual-rearm lockout; E1-089 follows the source startup priority with overlapping thresholds. These material interpretations are visible in the community batch.','- E1-020 controls serialized admitted starts under an observed acknowledged lifecycle; it does not prove mutual exclusion for uncontrolled external starts. E1-031 uses a fixed two-use phase representation, not general history aggregation.','- Fixed waveform, selected device sets and independent flow decomposition do not establish arbitrary cardinality, physical fading, joins or shared-state concurrency.','- Typed fixtures expose raw observations and atomic output leaves. Timing and controller decisions are encoded in IR. No Explorer verdict enters the result.','- Legacy T5 groups equal-time actions as an unordered multiset; raw action order and ordered comparison diagnostics remain available. Calendar tests using clock comparisons do not establish unrelated scheduler reliability.','','## Reproduce','','```sh','/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_er','/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequcy/breadth/remaining72/run_batch.py batch_official'.replace('E1_adequcy','E1_adequacy'),'/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_community','/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/summarize.py','```','','Run batch-specific sensitivity/fallback commands from their READMEs to reproduce supplemental records. `summary.json` records operator composition trees and nesting paths for all72. These are measured compositions, not a claim to cover every possible operator combination.','','## Case outcomes','','| Case | Exact histories | Recorded candidate label |','|---|---:|---|']
 for r in rows:lines.append(f"| {r['id']} | {r['exact_histories']}/{r['histories']} | {r['candidate_label']} |")
 if revision_notice:lines[2:2]=[revision_notice,'']
 (HERE/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
 print({k:result[k] for k in ('cases','all_frozen_histories_exact_cases','histories','exact_histories','supplemental_not_in_main_denominator')})
if __name__=='__main__':main()
