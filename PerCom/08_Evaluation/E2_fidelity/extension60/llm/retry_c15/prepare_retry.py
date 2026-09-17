"""Prepare a single-candidate technical retry; never execute either engine."""
import copy
import hashlib
import importlib.util
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
spec = importlib.util.spec_from_file_location('llm_extension_prepare', PARENT / 'prepare.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

def write(name, data):
    (HERE / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')

def expand(field, lo, hi):
    values = set()
    for part in field.split(','):
        bounds, sep, step_text = part.partition('/')
        step = int(step_text) if sep else 1
        assert step > 0
        if bounds == '*':
            first, last = lo, hi
        elif '-' in bounds:
            first, last = map(int, bounds.split('-'))
        else:
            first = int(bounds)
            last = hi if sep else first
        assert lo <= first <= last <= hi
        values.update(range(first, last + 1, step))
    return values

def weekly_start(cron):
    minute, hour, day, month, weekday = cron.split()
    assert day == month == '*', 'Only weekly schedules with unrestricted month/day are covered'
    minutes, hours = expand(minute, 0, 59), expand(hour, 0, 23)
    weekdays = {x % 7 for x in expand(weekday, 0, 7)}
    for day_index in range(7):
        if (day_index + 1) % 7 in weekdays:
            return (day_index * 1440 + min(hours) * 60 + min(minutes)) * 60000
    raise ValueError('No occurrence in canonical week')

def main():
    frozen_pairs = json.loads((PARENT / 'pairs.json').read_text())
    affected = [p['base_case'] for p in frozen_pairs['pairs'] if p['t_start_ms'] is None]
    assert affected == ['C15_002']
    old = next(p for p in frozen_pairs['pairs'] if p['base_case'] == 'C15_002')
    pair = copy.deepcopy(old)
    assert old['ir_cron'] == old['joi']['cron'] == '0 */2 * * 6,7'
    pair['t_start_ms'] = weekly_start(old['ir_cron'])
    assert pair['t_start_ms'] == 432000000
    assert {k for k in old if old[k] != pair[k]} == {'t_start_ms'}
    source_paths = [HERE / 'prepare_retry.py', HERE / 'CORRECTION.md', PARENT / 'prepare.py', PARENT / 'pairs.json', PARENT / 'histories.json', PARENT / 'supplement_histories.json', PARENT / 'ARTIFACT_HASHES.json', base.E2 / 'pairs/build_388_pairs.py', base.E2 / 'histories/make_388_histories.py', base.E2 / 'histories/make_e1_histories.py', base.E2 / 'histories/make_supplement.py', base.E2 / 'reference/smoke_388.py', base.E2 / 'reference/common.py', base.ROOT / 'files/service_list_ver2.0.7.json']
    hashes = base.hashes(source_paths)
    write('pairs.json', dict(inputs_sha256=hashes, n_pairs=1, start_rule='Preserve daily numeric cron rule; weekly nonliteral cron with month/day * uses first matching minute of Monday-Sunday canonical week', pairs=[pair]))
    mk, supp = base.mk, base.supp
    cat = base.Catalog(str(base.ROOT / 'files/service_list_ver2.0.7.json'))
    cid = pair['base_case']
    durations = mk.durations(pair['ir'])
    horizon = mk.grid(min(6 * 3600000, max(10000, 3 * (max(durations) if durations else 0) + 10000)))
    seed = dict(name='default', events=base.default_events(pair['devices'], cat), horizon=horizon)
    mk.CAP = 300
    histories, stats = mk.build_case(cid, pair['ir'], pair['binding'], pair['t_start_ms'], [seed])
    histories = json.loads(json.dumps(histories))
    stats['horizon_ms'] = horizon
    seeds = [dict(name=h['name'], events=h['events'], horizon=h['horizon']) for h in histories if h['origin'] == 'seed']
    again, _ = mk.build_case(cid, pair['ir'], pair['binding'], pair['t_start_ms'], seeds)
    assert json.loads(json.dumps(again)) == histories
    mk.CAP = 10**9
    every, _ = mk.build_case(cid, pair['ir'], pair['binding'], pair['t_start_ms'], seeds)
    kept = {h['name'] for h in histories}
    extra = [h for h in every if h['origin'] == 'pulse' and h['name'] not in kept]
    extra_count = len(extra)
    if len(extra) > supp.CAP_PULSE:
        extra = random.Random(f'{supp.SUPP_SEED}:{cid}:pulse').sample(extra, supp.CAP_PULSE)
        extra.sort(key=lambda h:h['name'])
    for h in extra:
        h['origin'] = 'supp-pulse'
    starts, domains = [], {}
    for seed in seeds:
        hs, dom = supp.start_variants(cid, seed, stats['compared_values'], pair['devices'])
        starts += hs
        domains[seed['name']] = {k:list(map(str,v)) for k,v in dom.items()}
    supplements = json.loads(json.dumps(starts + extra))
    supplementary_stats = dict(n_start=len(starts), start_domains=domains, n_pulse_candidates=extra_count, n_pulse=len(extra), original_reproduction_passed=True)
    write('histories.json', dict(inputs_sha256=hashes, grid_ms=mk.GRID, cap_pulses_per_case=300, seed=mk.SEED, stats={cid:stats}, histories={cid:histories}))
    write('supplement_histories.json', dict(inputs_sha256=hashes, cap_start_per_seed=supp.CAP_START, cap_pulse_per_case=supp.CAP_PULSE, seed=supp.SUPP_SEED, stats={cid:supplementary_stats}, histories={cid:supplements}))
    write('histories_combined.json', dict(inputs_sha256=base.hashes([HERE/'histories.json', HERE/'supplement_histories.json']), histories={cid:histories+supplements}))
    same_original = histories == json.loads((PARENT/'histories.json').read_text())['histories'][cid]
    same_supplement = supplements == json.loads((PARENT/'supplement_histories.json').read_text())['histories'][cid]
    audit = dict(candidate_id=cid, correction_type='technical retry of same frozen candidate', affected_new_llm_candidates=affected, inspected_new_llm_candidates=12, changed_pair_fields={'t_start_ms':{'old':None,'new':pair['t_start_ms']}}, cron=pair['ir_cron'], canonical_start='Saturday 00:00', original_histories=len(histories), supplement_histories=len(supplements), regenerated_original_equal_frozen=same_original, regenerated_supplement_equal_frozen=same_supplement, generator_reproduction_passed=True, evaluation_engine_executed=False, inputs_sha256=hashes)
    write('audit.json', audit)
    write('ARTIFACT_HASHES.json', base.hashes([HERE/name for name in ('prepare_retry.py','CORRECTION.md','pairs.json','histories.json','supplement_histories.json','histories_combined.json','audit.json')]))
    print(json.dumps({k:v for k,v in audit.items() if k != 'inputs_sha256'}, indent=2))

if __name__ == '__main__':
    main()
