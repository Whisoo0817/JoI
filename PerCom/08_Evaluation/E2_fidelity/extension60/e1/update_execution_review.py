"""Read-only result/source audit; writes only execution-review artifacts."""
import collections,datetime,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXT=HERE.parent;ROOT=EXT.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
    path=EXT/'runs/e1_new48.jsonl';raw=path.read_bytes();rows=[json.loads(l) for l in raw.splitlines() if l.strip()]
    meta=read(EXT/'runs/e1_new48.meta.json');expected=set(meta['lock']['pair_ids']);actual=[r['pair_id'] for r in rows]
    problems=[];missing=sorted(expected-set(actual))
    if len(actual)!=len(set(actual)):problems.append('Duplicate result IDs')
    if set(actual)-expected:problems.append('Unexpected result IDs')
    freeze=read(HERE/'FREEZE_MANIFEST.json')
    checked=1
    if sha(EXT/'runtime_freeze.json')!=meta['lock']['runtime_freeze_sha256']:problems.append('Runtime freeze manifest hash mismatch')
    if read(EXT/'runtime_freeze.json')!=meta['runtime']:problems.append('Runtime metadata differs from freeze manifest')
    for name,digest in freeze['files'].items():
        checked+=1
        if sha(HERE/name)!=digest:problems.append('Changed pair freeze file: '+name)
    for source in [meta['lock']['inputs_sha256'],meta['lock']['catalogs_sha256']]:
        for name,digest in source.items():
            checked+=1
            if sha(name)!=digest:problems.append('Changed input: '+name)
    for name,digest in meta['runtime']['files'].items():
        checked+=1
        if sha(ROOT/name)!=digest:problems.append('Changed runtime: '+name)
    totals=collections.Counter();special=[];false=[]
    for r in rows:
        pid=r['pair_id'];ref=r.get('reference',{});expl=r.get('explorer',{})
        if r.get('extension_execution',{}).get('runtime_freeze_sha256')!=meta['lock']['runtime_freeze_sha256']:problems.append(pid+': row freeze mismatch')
        if not ref or not expl:problems.append(pid+': missing engine result')
        if r.get('agreement','').startswith('FALSE-'):false.append(pid)
        if expl.get('verdict') in ['EQUIV','EQUIV-BOUNDED'] and ref.get('outcome')=='REF-DIVERGE':problems.append(pid+': false equivalence candidate')
        witness=expl.get('witness_on_reference',{})
        if expl.get('verdict')=='DIVERGE' and witness.get('status')!='diverge':special.append(pid+': divergence witness replay '+str(witness.get('status')))
        audit=r.get('reference_assignment_checks',[])+r.get('reference_supplement',{}).get('assignment_checks',[])
        if not audit:problems.append(pid+': missing short-circuit audit')
        for a in audit:
            n=a['n_histories_examined'];available=a['n_histories_available'];replay=a['n_diagnostic_replays']
            if not 0<n<=available:problems.append(pid+': invalid examined count')
            if a['outcome']=='REF-EQUIV-CHECKED' and n!=available:problems.append(pid+': incomplete equivalence')
            if replay not in (0,1) or (replay and a['outcome']!='REF-DIVERGE'):problems.append(pid+': invalid replay count')
            totals['assignment_checks']+=1;totals['histories_examined']+=n;totals['diagnostic_replays']+=replay
        original=r.get('reference_frozen_histories',ref)
        if 'n_histories_examined' in original and sum(original.get('counts',{}).values())!=original['n_histories_examined']:problems.append(pid+': returned counts do not sum to examined')
        if r.get('reference_supplement') and original.get('outcome')!='REF-EQUIV-CHECKED':problems.append(pid+': supplement ran outside conditional policy')
    outcome={label:dict(collections.Counter(r.get(label,{}).get(field,'MISSING') for r in rows)) for label,field in [('explorer','verdict'),('reference','outcome')]};outcome['agreement']=dict(collections.Counter(r.get('agreement','MISSING') for r in rows))
    result=dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),complete=len(rows)==48 and not missing,n_rows=len(rows),missing=missing,output_sha256=hashlib.sha256(raw).hexdigest(),n_hashes_checked=checked,problems=problems,false_verdict_candidates=false,witness_replay_notes=special,counts=outcome,execution_counts=dict(totals),runtime_freeze_sha256=meta['lock']['runtime_freeze_sha256'])
    (HERE/'EXECUTION_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
    text=f'''# E1 extension execution review\n\nSnapshot: {result['timestamp_utc']}. {'Complete: all 48 frozen pairs have results.' if result['complete'] else f'Partial: {len(rows)}/48 frozen pairs have results; no claim is made about missing pairs.'}\n\nThis reviewer inspected frozen source and recorded results only; no evaluator was run or runtime file edited. Result snapshot SHA-256: `{result['output_sha256']}`.\n\n## Short-circuit correctness\n\n`install_reference_short_circuit` calls the original `_reference_once` with `stop_at_diverge=True` for each selector assignment. One concrete differing history is sufficient to reject that assignment; later histories cannot restore universal equality. `reference_side` still enumerates alternative B5 assignments and accepts equivalence only when an assignment completes all histories equally. Unsupported assignments remain undecided under the original B5 fold. Therefore early divergence does not collapse the existential assignment search.\n\nThe wrapper counts actual examined histories by summing returned per-history outcome counts. `n_histories` retains its inherited available-history meaning; use `n_histories_examined` and `reference_assignment_checks` for actual coverage. For each short-circuit witness, it reruns the exact named history under the same assignment with short-circuit disabled and requires `REF-DIVERGE`, restoring diagnostic trace evidence. Replays are recorded separately and should not be mistaken for additional distinct histories. Original and supplementary assignment searches remain separate, preserving the historical fold described in REVIEW.md.\n\nThe reviewed runner now includes the lowering tree in runtime source hashes, resolving the earlier source-coverage note.\n\n## Recorded result audit\n\n- Rows: {len(rows)} / 48; missing: {', '.join(missing) if missing else 'none'}.\n- Explorer: `{json.dumps(outcome['explorer'])}`.\n- Reference: `{json.dumps(outcome['reference'])}`.\n- Agreement: `{json.dumps(outcome['agreement'])}`.\n- Candidate false verdicts: {len(false)}.\n- Freeze/input/catalog/runtime hashes checked: {checked}; mismatches or other audit problems: {len(problems)}.\n- Recorded assignment checks: {totals['assignment_checks']}; actual history checks across assignments: {totals['histories_examined']}; diagnostic replays: {totals['diagnostic_replays']}. These are execution counts, not unique histories or independent requests.\n\nProblems: {json.dumps(problems)}\n\nDivergence witness replay exceptions: {json.dumps(special)}\n\nEvery checked equivalent assignment must have examined its whole available set; checked count sums and supplement eligibility were validated from the rows. Refusals, timeouts, and unsupported references are retained separately and are not treated as false verdicts. The two C16 variants, if present, retain unsupported aggregate reference results while their Explorer witnesses can independently confirm divergence; witness confirmation does not turn their aggregate reference outcomes into `REF-DIVERGE`.\n\nFull machine-readable audit: `EXECUTION_REVIEW.json`.\n'''
    (HERE/'EXECUTION_REVIEW.md').write_text(text);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
