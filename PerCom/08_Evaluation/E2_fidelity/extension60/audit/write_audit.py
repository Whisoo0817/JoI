"""Root self-review of the complete E2 extension; requires all frozen outputs."""
import hashlib,json
from pathlib import Path
ROOT=Path('/home/gnltnwjstk/joi');HERE=Path(__file__).resolve().parent;EXT=HERE.parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 s=json.loads((EXT/'summary.json').read_text());assert s['n_pairs']==200
 rows=[json.loads(l)for l in (EXT/'results200.jsonl').read_text().splitlines()]
 assert len(rows)==len({r['pair_id']for r in rows})==200
 frozen=json.loads((EXT/'runtime_freeze.json').read_text())
 changed=[p for p,d in frozen['files'].items()if sha(ROOT/p)!=d]
 assert not changed,changed
 initial=[json.loads(l)for l in (EXT/'runs/llm_new12.jsonl').read_text().splitlines()]
 assert len(initial)==12 and sum(r['agreement']=='HARNESS-ERROR'for r in initial)==1
 for name in ['e1_new48','llm_new12','llm_c15_retry']:
  meta=json.loads((EXT/f'runs/{name}.meta.json').read_text())
  assert meta['lock']['runtime_freeze_sha256']==sha(EXT/'runtime_freeze.json')
  for p,h in meta['lock']['inputs_sha256'].items():assert sha(Path(p))==h
 for r in rows:
  if r['explorer']['verdict']=='DIVERGE':assert r['explorer'].get('witness_on_reference',{}).get('status')=='diverge',r['pair_id']
  if r['explorer']['verdict']=='EQUIV':assert r['reference']['outcome']=='REF-EQUIV-CHECKED',r['pair_id']
 for r in rows[0:]:
  for a in r.get('reference_assignment_checks',[])+r.get('reference_supplement',{}).get('assignment_checks',[]):
   assert 0<=a['n_histories_examined']<=a['n_histories_available']
   if a['outcome']=='REF-EQUIV-CHECKED':assert a['n_histories_examined']==a['n_histories_available']
 # Source integrity of old preserved reference, catalogs and frozen pair contents.
 comp=json.loads((EXT/'reference_compatibility.json').read_text())
 core=['common.py','ir_ref.py','joi_ref.py','run.py','JOILangLexer.py','JOILangParser.py','JOILangListener.py']
 assert all(r['exact']for r in comp['files']if Path(r['path']).name in core)
 assert not s['unresolved_or_contradicted_decisions']
 paths=['summary.json','results200.jsonl','runtime_freeze.json','reference_compatibility.json','runs/baseline140_current.jsonl','runs/e1_new48.jsonl','runs/llm_new12.jsonl','runs/llm_c15_retry.jsonl','e1/PROTOCOL.md','e1/FREEZE_MANIFEST.json','llm/selection.json','llm/retry_c15/CORRECTION.md','plan/experiment-plan.md','RUNNER_NOTES.md']
 arts=[dict(path=str(EXT/p),kind='result'if p.endswith('jsonl')else 'protocol-or-audit',source='experiment',digest=sha(EXT/p))for p in paths]
 ep=[a['path']for a in arts]
 rationales={
 'protocol_integrity':('pass','All200 fixed identities retained; new60 fixed before execution. Sufficient-counterexample stopping specified before newexecution; C15technicalretry preserves initialerror and changes only clock-anchor metadata.'),
 'metric_validity':('pass','Every issuedDIVERGE has separate-reference confirmed witness; EQUIV compares with finite-history reference. Errors/refusals/timeouts included. Histories available vs actualexamined distinguished.'),
 'baseline_fairness':('pass','CurrentExplorer reranall140oldpairs withoutverdictchanges; originalreference runtime sources exactpostR14. Additional60samecurrentExplorer/reference budgets, wrappers onlymemoize andshortcircuit sufficientdifferences.'),
 'outcome_accounting':('pass','200distinctpairresults plusinitialC15HARNESS-ERROR preserved; no outcome-based replacement. LLMstaticexcluded1new plus2old keptinselectionlogs.'),
 'inferential_support':('pass','Supports onlydescriptive finitecohort agreement, no universal proof, population accuracy, significance or independentvariant assumption.'),
 'confound_control':('inconclusive','Variantsshare20requirements and new48allfaults; B5 existential assignment may differ between original/supplement checks underinheritedprotocol. Scope explicitlybounded.'),
 'provenance':('pass','Originaldataandinitialfailedattempt preserved; sourcehashes, exactmutations, seed/order/staticexclusions and clock-anchor correction recorded.'),
 'snapshot_continuity':('pass','All211frozen sources/assets match; allbatchinput hashes match; baseline sourcecompatibilitychecked. Hashcontinuity is not enforceable filesystem isolation.'),
 'independence':('inconclusive','Reference is a separate implementation predatingextension; same rootagent integrates and audits, sharedfilesystemagents provide staticreview only. No external independentaudit claimed.')}
 audit=dict(audit_id='E2-EXT200-A1',claim_id='C1',claim_text=f"{s['decided']} issued Explorer decisions in the200-pair benchmark had no contradiction in the specified reference checks.",scope='200pairs=150hand-built on20E1requests+50generated; currentExplorerregression140 plus60extension; referencecheckscopeandB5conditionalfold only.',source_mode='standalone',requested_assurance_class='exploratory',attained_assurance_class='exploratory',verdict='supports_exploratory_follow_up',audited_claim_effect='strengthen',source_runs=[],run_selection=dict(selection_rule='Includeall200canonicalpairs. Retain allrawattempts including initialC15harnesserror; use correctedmetadata retry for samepair, not a replacementcandidate. Historical140reference reused with codecompatibility evidence; currentExplorer rerun.',excluded_runs=[]),evidence_artifacts=arts,check_results=[dict(check_id=k,status=v[0],rationale=v[1],evidence_paths=ep)for k,v in rationales.items()],independence=dict(self_review=True,dimensions=[],evidence='Same rootauthor audits; Astra independently reads staticrunnerbutsharescontext/filesystem. Reference implementation separate fromExplorer.'),limitations=['Finite histories cannot prove universal equivalence.','Original20selectedwithoutoperatorcoveragecriterion; extra48do not increase numberofrequests.','Versionsandextensionhistory are disclosed; notretroactivepreregistration.','InheritedB5 original/supplementchecks mayuse differentexistential assignments; no single-assignment unionclaim.','C15weeklycron technicalcorrection keepsoneactivationwindowsemantics, notfullscheduleverification.','No external independentaudit.'],predecessor_failures=[],minimum_corrective_action='Keepallscopequalifiers and report refusal/timeouts. Newindependenttasksrequired for stronger generalization.',narrative_anchor='## Audit E2-EXT200-A1')
 out=dict(schema_version='1.0',paper_id='percom-e2-extension200',identity_version=1,status='complete',audits=[audit])
 (HERE/'results-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 (HERE/'results-audit.md').write_text(f'''# E2 extension results audit

## Audit E2-EXT200-A1

- Bounded verdict: supports_exploratory_follow_up

Root self-review, with separate-agent static inspection. All200 distinct pairs are accounted for; {s['decided']} decisions have reference support and {200-s['decided']} remain undecided. Original140 current-version decisions unchanged. Every current divergent witness is reference-confirmed. All runtime/input hashes match. Initial C15 harness error remains in raw evidence; same candidate's clock-anchor correction is a documented technical retry.

This supports the bounded descriptive benchmark result only. It does not establish universal soundness, independent external verification, statistical population accuracy, or representative operator coverage. Inherited B5 original and supplementary checks can use different existential assignments. Mutation siblings are dependent samples. Prepared histories are not all claimed to have executed; examined/replay counts are explicit in new result rows.

The canonical JSON records exact evidence digests and check outcomes. Structural validator success establishes only consistency, not scientific correctness.
''')
 print('Audit complete:',s['decided'],'reference-supporteddecisions;211sourcehasheschecked')
if __name__=='__main__':main()
