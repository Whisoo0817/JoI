"""Reproduce the predeclared LLM extension without executing either engine."""
import csv
import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E2 = HERE.parents[1]
ROOT = E2.parents[2]
CAND = ROOT / 'explorer/candidates/gemma4-26b-contract-v1-fresh-v4'
sys.path[:0] = [str(E2 / 'reference'), str(E2 / 'histories')]
from common import Catalog, RefUnsupported, check_typed, resolve_device_member, parse_binding_slots
from joi_ref import parse_script, conv_scenario, _is_clock
import make_e1_histories as mk
import make_supplement as supp
from smoke_388 import default_events

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

builder = module('pair_builder', E2 / 'pairs/build_388_pairs.py')

def write(name, data):
    (HERE / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')

def hashes(paths):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def selectors(node):
    if isinstance(node, tuple):
        if node and node[0] in ('action', 'prop'):
            yield node
        for child in node[1:]:
            yield from selectors(child)
    elif isinstance(node, list):
        for child in node:
            yield from selectors(child)

def screen(block, devices, binding, cat):
    ast = conv_scenario(parse_script(block['script']))
    slots = parse_binding_slots(binding)
    checks = []
    for node in selectors(ast):
        action = node[0] == 'action'
        tags, name = (node[3], node[4]) if action else (node[2], node[3])
        if _is_clock(tags, name):
            checks.append(dict(member=name, tags=tags, clock=True))
            continue
        matched = [d for d, info in devices.items() if all(t == d or t in (info.get('tags') or []) or t in (info.get('category') or []) for t in tags)]
        service = None
        if '_' in name:
            pre, member = name.split('_', 1)
            if cat.service(pre) and cat.member(pre, member):
                service = pre.lower()
        bound = list(dict.fromkeys(d for s in slots if s['service'] == service for d in s['devices']))
        # All static possible bound devices plus concrete tag matches must have the named capability.
        targets = list(dict.fromkeys(bound + matched))
        if not targets:
            raise RefUnsupported('selector-no-device', f'{tags}: {name}')
        for dev in targets:
            member = resolve_device_member(cat, devices, dev, name)
            if action:
                if member.kind != 'function':
                    raise RefUnsupported('call-of-value', str(member))
                args = node[5]
                if len(args) != len(member.args):
                    raise RefUnsupported('arg-count', f'{member}: {len(args)} versus {len(member.args)}')
                for arg, spec in zip(args, member.args):
                    if arg[0] == 'lit':
                        check_typed(cat, member.service, spec.get('type'), spec.get('format'), spec.get('bound'), arg[1], f'{member}.{spec["id"]}')
        checks.append(dict(member=name, tags=tags, devices_checked=targets))
    return checks

def main():
    csv.field_size_limit(10**9)
    rows = {f"{r['category_v2']}_{int(float(r['index'])):03d}": r for r in csv.DictReader((ROOT / 'dataset.csv').open())}
    original = json.loads((E2 / 'pairs/sample_388.json').read_text())['sample']
    candidates = {f.stem: json.loads(f.read_text()) for f in sorted(CAND.glob('C*_*.json'))}
    eligible = sorted(cid for cid, d in candidates.items() if cid not in original and d.get('status') == 'ok' and (d.get('joi_block') or {}).get('script'))
    order = eligible.copy()
    random.Random(20260918).shuffle(order)
    write('draw_order.json', dict(seed=20260918, excluded_original40=original, n_remaining_eligible=len(eligible), order=order))
    cat = Catalog(str(ROOT / 'files/service_list_ver2.0.7.json'))
    selected, log, pairs = [], [], []
    for rank, cid in enumerate(order, 1):
        r, candidate = rows[cid], candidates[cid]
        ir, binding, devices = (json.loads(r[k]) for k in ('ir_gt', 'binding_gt', 'connected_devices'))
        try:
            checks = screen(candidate['joi_block'], devices, binding, cat)
        except RefUnsupported as exc:
            log.append(dict(rank=rank, candidate_id=cid, admissible=False, reason=str(exc)))
            continue
        selected.append(cid)
        log.append(dict(rank=rank, candidate_id=cid, admissible=True, reason='grammar and static catalog/device checks passed', checks=checks))
        start, cron = builder.start_of(ir)
        pairs.append(dict(pair_id=f'{cid}/llm', kind='llm', family=None, base_case=cid, automation='main', description='LLM candidate (gemma4-26b-contract-v1-fresh-v4)', ir=ir, binding=binding, devices=devices, catalog='files/service_list_ver2.0.7.json', t_start_ms=start, ir_cron=cron, joi=candidate['joi_block'], command_eng=r['command_eng']))
        if len(selected) == 12:
            break
    assert len(selected) == 12
    sources = [HERE / 'prepare.py', HERE / 'SELECTION_PROTOCOL.md', E2 / 'pairs/sample_388.json', E2 / 'pairs/build_388_pairs.py', ROOT / 'dataset.csv', ROOT / 'files/service_list_ver2.0.7.json', E2 / 'reference/joi_ref.py', E2 / 'reference/common.py', E2 / 'reference/smoke_388.py', E2 / 'histories/make_388_histories.py', E2 / 'histories/make_e1_histories.py', E2 / 'histories/make_supplement.py']
    sources += sorted((E2 / 'reference/grammar').glob('*.py')) + [E2 / 'reference/grammar/JOILang.g4']
    sources += sorted(CAND.glob('C*_*.json'))
    source_hashes = hashes(sources)
    write('source_hashes.json', source_hashes)
    write('selection.json', dict(seed=20260918, sample=selected, n_selected=12, n_inspected=len(log), n_rejected=len(log)-12, static_log=log, inputs_sha256=source_hashes))
    write('pairs.json', dict(inputs_sha256=source_hashes, start_rule='daily cron M H -> Monday H:M; otherwise Monday 12:00', n_pairs=12, pairs=pairs))
    print('SELECTED', selected, flush=True)
    print('STATIC REJECTIONS', [(x['candidate_id'],x['reason']) for x in log if not x['admissible']], flush=True)
    hist, stats, supplements, suppstats = {}, {}, {}, {}
    for p in pairs:
        cid = p['base_case']
        durs = mk.durations(p['ir'])
        horizon = mk.grid(min(6 * 3_600_000, max(10_000, 3 * (max(durs) if durs else 0) + 10_000)))
        seed = dict(name='default', events=default_events(p['devices'], cat), horizon=horizon)
        mk.CAP = 300
        hs, st = mk.build_case(cid, p['ir'], p['binding'], p['t_start_ms'], [seed])
        hist[cid] = json.loads(json.dumps(hs))
        st['horizon_ms'] = horizon
        stats[cid] = st
        seeds = [dict(name=h['name'], events=h['events'], horizon=h['horizon']) for h in hist[cid] if h['origin'] == 'seed']
        again, _ = mk.build_case(cid, p['ir'], p['binding'], p['t_start_ms'], seeds)
        assert json.loads(json.dumps(again)) == hist[cid]
        mk.CAP = 10**9
        every, _ = mk.build_case(cid, p['ir'], p['binding'], p['t_start_ms'], seeds)
        kept = {h['name'] for h in hist[cid]}
        extra = [h for h in every if h['origin'] == 'pulse' and h['name'] not in kept]
        n_extra = len(extra)
        if len(extra) > supp.CAP_PULSE:
            extra = random.Random(f'{supp.SUPP_SEED}:{cid}:pulse').sample(extra, supp.CAP_PULSE)
            extra.sort(key=lambda h: h['name'])
        for h in extra:
            h['origin'] = 'supp-pulse'
        starts, domains = [], {}
        for seed in seeds:
            hs, dom = supp.start_variants(cid, seed, st['compared_values'], p['devices'])
            starts += hs
            domains[seed['name']] = {k:list(map(str,v)) for k,v in dom.items()}
        supplements[cid] = json.loads(json.dumps(starts + extra))
        suppstats[cid] = dict(n_start=len(starts), start_domains=domains, n_pulse_candidates=n_extra, n_pulse=len(extra), original_reproduction_passed=True)
        print(cid, 'original',len(hist[cid]),'supplement',len(supplements[cid]), 'horizon',horizon, flush=True)
    write('histories.json', dict(inputs_sha256=source_hashes, grid_ms=mk.GRID, cap_pulses_per_case=300, seed=mk.SEED, stats=stats, histories=hist))
    write('supplement_histories.json', dict(inputs_sha256=source_hashes, cap_start_per_seed=supp.CAP_START, cap_pulse_per_case=supp.CAP_PULSE, seed=supp.SUPP_SEED, stats=suppstats, histories=supplements))
    combined = {cid:hist[cid]+supplements[cid] for cid in selected}
    write('histories_combined.json', dict(inputs_sha256=hashes([HERE/'histories.json',HERE/'supplement_histories.json']), stats={cid:dict(original=len(hist[cid]), supplement=len(supplements[cid]), combined=len(combined[cid])) for cid in selected}, histories=combined))
    write('ARTIFACT_HASHES.json', hashes([HERE/n for n in ('prepare.py','SELECTION_PROTOCOL.md','draw_order.json','source_hashes.json','selection.json','pairs.json','histories.json','supplement_histories.json','histories_combined.json')]))

if __name__ == '__main__':
    main()
