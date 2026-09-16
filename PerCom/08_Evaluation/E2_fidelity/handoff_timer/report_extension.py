"""Reproducible full-population accounting, with no reference-code execution."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import argparse

HERE = Path(__file__).resolve().parent
RESULTS = HERE / 'results'
ROOT = HERE.parents[3]


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',default='extension-v4')
    args=parser.parse_args()
    run=args.run
    path = RESULTS / f'{run}.jsonl'
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    assert len(rows) == len({r['pair_id'] for r in rows}) == 142
    population = json.loads((HERE/'e2_population.json').read_text())
    excluded = {x['pair_id']: x for x in population['exclusions']}
    categorized=[]
    for r in rows:
        ident, verdict=r['pair_id'],r['explorer']['verdict']
        if ident in excluded: category=excluded[ident]['category']
        elif verdict in ('EQUIV','DIVERGE'): category='decided'
        elif ident.startswith(('E1-095/','E1-099/')): category='arithmetic_state_relations'
        elif ident.startswith('C07/'): category='finite_product_state_explosion'
        else: category='unexplained'
        categorized.append({**r,'category':category})
    counts=Counter(r['category'] for r in categorized)
    verdicts=Counter(r['explorer']['verdict'] for r in categorized)
    old=[r for r in rows if r['previous']['verdict'] in ('EQUIV','DIVERGE')]
    changes=[r['pair_id'] for r in old if r['previous']['verdict']!=r['explorer']['verdict']]
    false_equiv=[r['pair_id'] for r in rows if r['explorer']['verdict']=='EQUIV'
                 and r['frozen_reference_outcome']=='REF-DIVERGE']
    new=[r for r in rows if r['previous']['verdict'] not in ('EQUIV','DIVERGE')
         and r['explorer']['verdict'] in ('EQUIV','DIVERGE')]
    reference_gaps=[r['pair_id'] for r in new if r['explorer']['verdict']=='DIVERGE'
                    and r['frozen_reference_outcome']!='REF-DIVERGE']
    assert len(old)==104 and not changes and not false_equiv
    assert not counts['unexplained'], counts
    assert all(r['explorer']['verdict']=='REFUSED' for r in categorized if r['pair_id'] in excluded)
    summary={'population':population,'category_counts':dict(counts),'verdict_counts':dict(verdicts),
             'existing_decision_changes':changes,'new_decisions':[r['pair_id'] for r in new],
             'new_equiv_against_frozen_diverge':false_equiv,'reference_follow_up':reference_gaps,
             'rows':[{**r,
                      'previous':{k:v for k,v in r['previous'].items() if k!='witness'},
                      'explorer':{k:v for k,v in r['explorer'].items() if k!='witness'}}
                     for r in sorted(categorized,key=lambda r:r['pair_id'])],
             'witness_artifact':f'results/{run}.jsonl.gz'}
    (RESULTS/f'{run}-classified.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    with (RESULTS/f'{run}.jsonl.gz').open('wb') as out:
        with gzip.GzipFile(filename='',fileobj=out,mode='wb',mtime=0) as f: f.write(path.read_bytes())
    decided=counts['decided']
    text=f'''# E2 개발 재평가와 한계 분류 — 2026-09-14

전체 동결 142쌍을 같은 120초 예산으로 재검사했다. 행동 비교 대상 140쌍 중
{decided}쌍({decided/140:.1%})에서 판정을 완료했다. 나머지는 아래 두 유형에만 남았다.
원래 142쌍을 분모로 유지하면 판정 완료율은 {decided/142:.1%}다.

| 구분 | 쌍 수 | 의미 |
|---|---:|---|
| 판정 완료 | {decided} | EQUIV 또는 구체 재생으로 확인한 DIVERGE |
| 계산된 수치 상태의 관계 추론 | {counts['arithmetic_state_relations']} | 누적·평균 또는 증가 카운터로 계산한 값이 출력이나 기한을 결정함 |
| 유한 곱 상태의 폭증 | {counts['finite_product_state_explosion']} | 저장값·여러 타이머·반복 제어의 조합이 현재 탐색 예산을 초과함 |
| 입력 검증에서 제외 | {len(excluded)} | 구문 부적합 1, service mapping 오류 1 |

## 설명에 사용할 분류

“평가한 유효 프로그램에서는 대부분의 행동 동등성/차이를 판정했다.
미결정 사례는 **계산된 수치 상태의 관계 추론이 필요한 프로그램**과 **복합 제어로 상태가
폭증하는 프로그램**에 한정됐다.”

첫 유형은 시간 비교 구간만으로 동작을 보존할 수 없는 수치 계산이다.
센서값의 누적·평균을 출력하거나, 계속 증가하는 카운터로 기한을 계산하므로
추가 수치 관계 추론이 필요하다. 평균 계산은 매일 초기화되므로 모든 사례의
값이 끝없이 증가한다는 뜻은 아니다. 두 번째는 유한한 값과
제어 상태의 조합이 너무 큰 경우다. 추상화를 더 결합하거나 탐색을 개선할
여지가 있으므로 둘 모두 원리적으로 해결 불가능하다고 표현하지 않는다.

이 두 유형은 **이 E2 평가에서 남은 실패 원인**이다. 임의의 모든 JoI
프로그램이 이 두 유형 외에는 지원된다는 주장은 아니다. 기존 지원 단편의
query/GV/입력 모델/비동기 시간 등의 전제는 계속 적용된다.

## 대상 정리

`e2_population.json`이 새 행동 평가 대상의 규칙과 제외 기록이다.
C03_008/llm의 ACTION 위치 any는 사용자 언어 결정에 따른 파싱 오류다.
C20_011/llm은 TV에 선언되지 않은 Charger를 사용한 LLM service mapping
오류다. 이 두 쌍은 행동 비교 실패율의 분모에서 제외하고 입력 검증 단계에
별도 보고한다. 동결 pairs/histories/runs는 보존했다. 기존 142쌍 결과를
몰래 140쌍 결과로 바꾸지 않고, 이 수정된 모집단을 별도 버전으로 기록한다.

## 개선과 검증

원래 판정 완료 104쌍의 판정 변화: {len(changes)}. 동결 정답기가 차이를
찾은 쌍에 대해 새 EQUIV를 낸 경우: {len(false_equiv)}.
원래 미결정에서 판정 완료로 바뀐 쌍: {len(new)}.

타이머 관계 v1의 5쌍에 더해, 입력 변경 시점을 보존하는 다단계 반례 생성,
나머지 카운터의 정확한 몫 상태, Hour 공통 변화의 과근사, 저장 timestamp의
경과 시간 관계를 구현했다. 양쪽 ACTION이 모든 포함 상태에서 같고 그래프가
닫힌 경우만 EQUIV다. 반례 후보의 인위적인 clock 입력은 제거하고 원래
시작 시각에서 구체 재생한 경우만 DIVERGE다.

지정된 기존 회귀와 timer-zones 회귀는 `results/checks-v3.jsonl`,
추가 use-site/시각/경계/반례 회귀는 `results/checks-extensions-v3.jsonl`에 기록한다.
새 증명 전제와 논증은 `explorer/docs/proof/TIMER_ZONES.md`에 있다.

## 독립 정답기와의 경계

정답기 코드를 읽거나 실행하지 않았다. 결과 비교에는 동결 판정 필드만
사용했다. 새 판정 완료 수치는 Explorer 개발 재평가이며, 새 반례 모두가
독립 정답기에 의해 확인됐다는 뜻은 아니다. 특히 {', '.join(reference_gaps) or '해당 없음'}은
동결 이력에서 차이를 못 찾았지만 새 구체 이력에서 차이를 찾았다.
정답기 담당자가 새 witness를 재실행한 뒤 최종 E2 정확도 수치를 확정해야 한다.

실패 사례를 보고 개선했고 제외 규칙도 이번에 명시했으므로 일반화 성능이나
확증 실험으로 포장하지 않는다. 군별 fault 쌍은 서로 독립 표본이 아니므로
쌍 수의 비율에 독립 표본을 가정한 통계적 신뢰구간을 붙이지 않는다.

## 실행 조건과 재현

별도 worktree `joi-timer-regions`, branch `timer-regions-20260914`.
입력 간격 100ms, 쌍당 120초, 상태 400,000, 전이 2,000,000, worker 4.
동결 비교와 동일하게 E2_BINDING_DECISION=false. 보호된 네 파일은 기준
`580053a`에서 그대로 유지했다. source digest와 실행 설정은
`results/extension-v3.meta.json`, 전체 분류는 `results/extension-v3-classified.json`.

```sh
~/temp/bin/python PerCom/08_Evaluation/E2_fidelity/handoff_timer/evaluate_timer.py --all-pairs --out /tmp/e2-new-full.jsonl --workers 4
~/temp/bin/python -m explorer.tests.test_timer_extensions
```

## 쌍별 원자료

| 쌍 | 이전 | 새 판정 | 상태 | 초 | 분류 |
|---|---|---|---:|---:|---|
'''
    for r in sorted(categorized,key=lambda r:r['pair_id']):
        x=r['explorer']
        text+=f"| {r['pair_id']} | {r['previous']['verdict']} | {x['verdict']} | {x.get('n_states','—')} | {x['seconds']} | {r['category']} |\n"
    (HERE/'EXTENSION_RESULT.md').write_text(text.replace('extension-v3',run).replace('checks-extensions-v3','checks-extensions-v4').replace('checks-v3','checks-v4'))
    # Preserve failed/partial development probes; none substitutes for the full
    # population run. Their sources changed between iterations.
    development=[]
    for candidate in sorted(Path('/tmp').glob('explorer-*-probe*.jsonl')):
        if not candidate.name.startswith(('explorer-extension-', 'explorer-witness-', 'explorer-timestamp-')):
            continue
        destination=RESULTS/('development-'+candidate.name+'.gz')
        with destination.open('wb') as out:
            with gzip.GzipFile(filename='',fileobj=out,mode='wb',mtime=0) as f: f.write(candidate.read_bytes())
        trials=[json.loads(line) for line in candidate.read_text().splitlines()]
        development.append({'run_id':candidate.stem,'artifact':str(destination.relative_to(ROOT)),
                            'rows':len(trials),'sha256':digest(destination),
                            'verdicts':dict(Counter(r['explorer']['verdict'] for r in trials)),
                            'disposition':'superseded development diagnostic; incomplete population and interim implementations'})
    (RESULTS/'development-index.json').write_text(json.dumps(development,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','population')},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
