"""Bind the standalone audit to the final safety-narrowed full run."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    checks=[json.loads(s) for s in (HERE/'results/checks-v4.jsonl').read_text().splitlines()]
    assert len(checks)==12 and all(r['returncode']==0 for r in checks)
    extra=next(r for r in checks if r['module']=='explorer.tests.test_timer_extensions')
    (HERE/'results/checks-extensions-v4.jsonl').write_text(json.dumps(extra)+'\n')
    path=HERE/'results-audit/results-audit.json'
    # This is an artifact rebind, not a new scientific assurance judgment.
    data=json.loads(path.read_text().replace('extension-v3','extension-v4')
                    .replace('checks-extensions-v3','checks-extensions-v4')
                    .replace('checks-v3','checks-v4'))
    record=data['audits'][0]
    exclusions=record['run_selection']['excluded_runs']
    if not any(r['run_id']=='extension-v3' for r in exclusions):
        exclusions.append({'run_id':'extension-v3',
            'rationale':'Complete predecessor run before rejecting timestamp aliases across blocking continuations. Preserved, but superseded by the full extension-v4 safety-narrowed source rerun; not an independent replication.'})
    note=' The final source rejects timestamp aliases across blocking continuations.'
    if note not in record['run_selection']['selection_rule']:
        record['run_selection']['selection_rule']+=note
    if not any(x['failure_id']=='timestamp-blocking-alias' for x in record['predecessor_failures']):
        record['predecessor_failures'].append({'failure_id':'timestamp-blocking-alias',
            'status':'resolved','rationale':'Use-site audit narrowed snapshot eligibility to nonblocking repeating JoI; dedicated negative test and complete full-population rerun passed.'})
    for artifact in record['evidence_artifacts']:
        if artifact['source']=='experiment':
            artifact['digest']=hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest()
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__': main()
