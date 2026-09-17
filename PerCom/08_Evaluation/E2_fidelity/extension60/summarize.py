"""Aggregate complete versioned E2 extension outputs; never replace missing/failed cases."""
import argparse,gzip,hashlib,json
from pathlib import Path
from collections import Counter,defaultdict
HERE=Path(__file__).resolve().parent; E2=HERE.parent
GOOD={'AGREE-EQUIV-ON-CHECKED','AGREE-DIVERGE','EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS'}
def load(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else p.open())as f:return json.load(f)
def rows(p):return [json.loads(l)for l in p.read_text().splitlines()if l.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verdict(r):return r.get('explorer',{}).get('verdict','MISSING')
def decided(r):return verdict(r)in('EQUIV','DIVERGE')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');a=ap.parse_args()
 inputs=[HERE/'runs/baseline140_current.jsonl',HERE/'runs/e1_new48.jsonl',HERE/'runs/llm_new12.jsonl']
 groups=[rows(p)if p.exists()else [] for p in inputs]
 retryfile=HERE/'runs/llm_c15_retry.jsonl'
 retries=rows(retryfile)if retryfile.exists()else []
 if retries:
  assert len(retries)==1 and retries[0]['pair_id']=='C15_002/llm'
  initial=next(r for r in groups[2]if r['pair_id']=='C15_002/llm')
  assert initial['agreement']=='HARNESS-ERROR'
  groups[2]=[dict(retries[0],technical_retry_of='runs/llm_new12.jsonl:C15_002/llm',initial_attempt_agreement=initial['agreement'])if r['pair_id']=='C15_002/llm'else r for r in groups[2]]
 if a.partial:
  print(json.dumps({str(p.name):dict(n=len(g),verdicts=dict(Counter(map(verdict,g))))for p,g in zip(inputs,groups)},indent=2));return
 assert list(map(len,groups))==[140,48,12],list(map(len,groups))
 assert len(retries)==1,'C15 technical retry must be completed and recorded'
 rs=sum(groups,[]);assert len({r['pair_id']for r in rs})==200
 oldp=[q for name in('e1_pairs.json','sample_388_pairs.json')for q in load(E2/'pairs'/name)['pairs']if q['pair_id']not in('C03_008/llm','C20_011/llm')]
 newp=load(HERE/'e1/pairs.json')['pairs']+load(HERE/'llm/pairs.json')['pairs'];ps=oldp+newp
 if retries:
  rp=load(HERE/'llm/retry_c15/pairs.json')['pairs'][0]
  ps=[rp if p['pair_id']==rp['pair_id'] else p for p in ps]
 assert {p['pair_id']for p in ps}=={r['pair_id']for r in rs}
 for p,r in zip(inputs,groups):
  if p.name!='baseline140_current.jsonl':
   meta=load(p.with_suffix('.meta.json'))
   for path,digest in meta['lock']['inputs_sha256'].items():assert sha(Path(path))==digest,path
 hs={}
 for p in [E2/'histories/e1_histories.json',E2/'histories/sample_388_histories.json',E2/'histories/supplement_histories.json.gz',HERE/'llm/histories.json',HERE/'llm/supplement_histories.json']:
  for k,v in load(p)['histories'].items():
   if k in ['C03_008','C20_011']:continue
   for h in v:hs[(k,h['name'])]=h
 obs=[r for r in rs if r['kind']=='fault'and(r.get('reference',{}).get('outcome')=='REF-DIVERGE' or r.get('explorer',{}).get('witness_on_reference',{}).get('status')=='diverge')]
 by=defaultdict(list)
 for r in rs:
  if r['kind']!='llm':by[r['base_case']].append(r)
 unexpected=[r['pair_id']for r in rs if decided(r)and r['agreement']not in GOOD]
 failures=[dict(pair_id=r['pair_id'],verdict=verdict(r),agreement=r['agreement'],reference=r.get('reference',{}).get('outcome'),reason=r.get('explorer',{}).get('reason'))for r in rs if not decided(r) or r['agreement']not in GOOD]
 summary=dict(n_pairs=200,hand_built=150,llm=50,base_e1_requests=len(by),verdicts=dict(Counter(map(verdict,rs))),agreement=dict(Counter(r['agreement']for r in rs)),decided=sum(map(decided,rs)),decided_with_reference_support=sum(decided(r)and r['agreement']in GOOD for r in rs),unresolved_or_contradicted_decisions=unexpected,observed_faults=len(obs),observed_fault_verdicts=dict(Counter(map(verdict,obs))),llm_decided=sum(decided(r)for r in rs if r['kind']=='llm'),hand_decided=sum(decided(r)for r in rs if r['kind']!='llm'),requests_all_decided=sum(all(map(decided,g))for g in by.values()),undecided_requests=sorted(k for k,g in by.items()if not all(map(decided,g))),available_distinct_histories=len(hs),new_available_histories=6081,baseline_verdict_changes=[r['pair_id']for r in groups[0]if r.get('verdict_changed')],failures=failures,cohorts={str(p.name):dict(n=len(g),verdicts=dict(Counter(map(verdict,g))),agreement=dict(Counter(r['agreement']for r in g)))for p,g in zip(inputs,groups)},technical_retries=[dict(pair_id='C15_002/llm',initial='runs/llm_new12.jsonl',retry='runs/llm_c15_retry.jsonl',reason='Weekly cron anchor was missing; only t_start_ms corrected, same candidate and histories retained.')],source_sha256={str(p.relative_to(HERE)):sha(p)for p in inputs+[retryfile]},scope='Descriptive200pair extended benchmark. Old140 Explorer replayed currentversion, reference reused on source-equivalence evidence; new60 bothrun. Newreference shortcircuits concrete differences perassignment; equivalence requires complete assignment pass. Available histories are not asserted to all have executed. No random or operatorrepresentative E1 claim; no universal soundness or independentexternal audit.')
 checks=[a for r in sum(groups[1:],[])for a in r.get('reference_assignment_checks',[])+r.get('reference_supplement',{}).get('assignment_checks',[])]
 summary['extension_reference_history_executions']=sum(a['n_histories_examined']for a in checks)
 summary['extension_reference_diagnostic_replays']=sum(a['n_diagnostic_replays']for a in checks)
 summary['canonical_explorer_attempts']=200
 summary['additional_preserved_harness_error_attempts']=1
 (HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 (HERE/'results200.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n'for r in sorted(rs,key=lambda r:r['pair_id'])))
 report=f'''# E2 추가 평가 결과

총 200쌍: E1 요청20건에서 직접 만든150쌍 + LLM후보50쌍. 기존140쌍과 추가48+12쌍을 모두 포함한다.

| 항목 | 수치 |
| --- | ---: |
| 판정 완료 | {summary['decided']}/200 |
| 동등 | {summary['verdicts'].get('EQUIV',0)} |
| 불일치 | {summary['verdicts'].get('DIVERGE',0)} |
| 지원 거절 | {summary['verdicts'].get('REFUSED',0)} |
| 시간 초과 | {summary['verdicts'].get('TIMEOUT',0)} |
| 판정 중 기준검사로 뒷받침되지 않은 건 | {len(unexpected)} |
| 직접 구성한 쌍 판정 완료 | {summary['hand_decided']}/150 |
| LLM 후보 판정 완료 | {summary['llm_decided']}/50 |

기존140쌍의 현재버전 재판정 변화: {len(summary['baseline_verdict_changes'])}건. 기존 기준 실행기의 실행 소스는 R14 반영 시점과 동일해 결과를 재사용하고, 현재 Explorer의 반례는 다시 실행했다. 추가60쌍은 새로 실행했다.

추가48쌍은 새 요청48건이 아니라 기존20건에 대한 새로운 결함 변형이다. 기존102쌍과 중복되지 않는 코드다. 모든 의도된 결함이 실제 행동 차이를 만든다고 가정하지 않는다. 동일 요청의 변형은 독립 표본이 아니다.

LLM후보는 고정시드20260918로 기존40개와 겹치지 않게 뽑았다. 정적 검사에서 기기 기능정보가 잘못된1개를 제외해12개를 확정했다. 제외와 전체 추첨순서는 llm/selection.json과 draw_order.json에 보존했다. 실행 결과를 보고 교체하지 않았다.

입력 이력은 총 {len(hs):,}개가 준비돼 있다. 추가 평가에서는 특정 기기 선택에 대해 행동 차이가 확인되면 이후 입력 검사를 중단한다. B5의 다른 선택 가능성은 계속 검사하며, 동등 판정에는 해당 선택에서 모든 입력의 일치가 필요하다. 실제 검사 수는 각 결과행에 기록한다. 준비된 입력 수를 전부 실행한 횟수로 해석하면 안 된다.

C15_002는 주말 cron의 시작 시각이 빠진 실험 입력 때문에 첫 시도에서 하네스 오류가 났다. 같은 후보의 시작 시각만 토요일 00:00으로 수정해 재실행했으며 원래 오류 기록과 수정 내역을 모두 보존했다. 후보를 다른 것으로 교체하지 않았다.

미판정·실패·해석 한계는 summary.json의 failures 및 아래 감사 기록을 확인한다. 유한한 입력의 일치는 모든 입력에서의 동등성을 증명하지 않는다. 전체가 처음부터200쌍으로 계획된 실험이 아니라, 기존 결과를 본 뒤 실행 전에 추가60쌍을 고정한 확장이다.
'''
 (HERE/'RESULT_KO.md').write_text(report)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
