"""Offline E1 boundary probes; NEVER evidence of an actual JoI runtime run.

python -m explorer.tests.e1_runtime_probe --output <new-result.json>

Expected traces are hand-derived from the adopted target-runtime contract.
They do not describe measured behavior of an existing JoI server. Replay every millisecond,
without Explorer's BFS, deadline scheduler, or pair-equivalence comparator.
Fixtures use catalog-backed preparation, with an empty IR only to obtain the
candidate adapter; no IR/code equivalence claim is made here.
"""
import argparse
import hashlib
import json
from pathlib import Path

from explorer.verification.gate import prepare_pair, pair_input_domains
from explorer.runtime.interp import Unsupported


ROOT = Path(__file__).resolve().parents[2]
DEVICES = {
    'lamp': {'category': ['Switch'], 'tags': ['Lamp']},
    'input': {'category': ['Switch'], 'tags': ['Input']},
    'weather': {'category': ['WeatherProvider'], 'tags': ['Weather']},
    'speaker': {'category': ['Speaker'], 'tags': ['Speaker']},
}
ON = '(#Lamp).switch_on()'
OFF = '(#Lamp).switch_off()'
INPUT = '(#Input).switch_switch'
QUERY = '(#Weather).weatherProvider_forecast(3)'
BRANCH = 'if (x == true) { ' + ON + ' } else { ' + OFF + ' }'


def action(t, method, args=(), target='lamp', service='switch'):
    return {'t_ms': t, 'service': service, 'method': method,
            'args': list(args), 'target': [target]}


CASES = [
    dict(id='delay_150', rule='delay resumes at its exact deadline', period=0,
         horizon_ms=300, script=ON + '\ndelay(150 MSEC)\n' + OFF,
         inputs=[[0, {}]], expected=[action(0, 'on'), action(150, 'off')]),
    dict(id='period_after_completion', rule='period starts after body completion',
         period=1000, horizon_ms=2500, script=ON + '\ndelay(150 MSEC)\n' + OFF,
         inputs=[[0, {}]], expected=[action(0, 'on'), action(150, 'off'),
             action(1150, 'on'), action(1300, 'off'), action(2300, 'on'), action(2450, 'off')]),
    dict(id='wait_preserves_continuation', rule='wait resumes without repeating preceding ACTION',
         period=1000, horizon_ms=1400,
         script=ON + '\nwait until(' + INPUT + ' == true)\n' + OFF,
         inputs=[[0, {'input.switch': False}], [300, {'input.switch': True}]],
         expected=[action(0, 'on'), action(300, 'off'), action(1300, 'on'), action(1300, 'off')]),
    dict(id='nested_delay_keeps_branch', rule='resumption does not re-evaluate outer if',
         period=0, horizon_ms=300,
         script='if (' + INPUT + ' == true) {\n' + ON + '\ndelay(150 MSEC)\n' + OFF + '\n}',
         inputs=[[0, {'input.switch': True}], [100, {'input.switch': False}]],
         expected=[action(0, 'on'), action(150, 'off')]),
    dict(id='input_at_delay_expiry', rule='new input is visible at coincident timer expiry',
         period=0, horizon_ms=300, script='delay(200 MSEC)\nx = ' + INPUT + '\n' + BRANCH,
         inputs=[[0, {'input.switch': True}], [200, {'input.switch': False}]],
         expected=[action(200, 'off')]),
    dict(id='zero_delay', rule='zero delay preserves same-time sequential ACTIONs',
         period=0, horizon_ms=100, script=ON + '\ndelay(0 MSEC)\n' + OFF,
         inputs=[[0, {}]], expected=[action(0, 'on'), action(0, 'off')]),
    dict(id='break_absorbs', rule='top-level break prevents later iterations and statements',
         period=100, horizon_ms=300, script=ON + '\nbreak\n' + OFF,
         inputs=[[0, {}]], expected=[action(0, 'on')]),
    dict(id='initial_value_persists', rule='executed top-level initializer persists',
         period=100, horizon_ms=200, script='x := ' + INPUT + '\n' + BRANCH,
         inputs=[[0, {'input.switch': True}], [100, {'input.switch': False}]],
         expected=[action(0, 'on'), action(100, 'on'), action(200, 'on')]),
    dict(id='edge_latch', rule='initial true fires once; observed false re-arms latch',
         period=100, horizon_ms=400,
         script='fired := false\nif (' + INPUT + ' == true) {\n'
                'if (fired == false) {\n' + ON + '\nfired = true\n}\n'
                '} else { fired = false }',
         inputs=[[0, {'input.switch': True}], [200, {'input.switch': False}],
                 [300, {'input.switch': True}]],
         expected=[action(0, 'on'), action(300, 'on')]),
    dict(id='query_same_snapshot', rule='same query key shares held value within a reaction',
         period=0, horizon_ms=100,
         script='a = ' + QUERY + '\nb = ' + QUERY + '\n'
                'if (a == "rain" and b == "rain") { ' + ON + ' }',
         inputs=[[0, {'weather.forecast(3)': 'rain'}]], expected=[action(0, 'on')]),
    dict(id='query_after_delay', rule='later query sees latest held input and STRING result',
         period=0, horizon_ms=300,
         script='a = ' + QUERY + '\ndelay(150 MSEC)\nb = ' + QUERY + '\n'
                'if (a == "rain" and b == "clear") { (#Speaker).speaker_speak(b) }',
         inputs=[[0, {'weather.forecast(3)': 'rain'}], [100, {'weather.forecast(3)': 'clear'}]],
         expected=[action(150, 'speak', ['clear'], 'speaker', 'speaker')]),
    dict(id='missing_query', rule='model represents missing query result as None',
         period=0, horizon_ms=100,
         script='w = ' + QUERY + '\nif (w == "rain") { ' + ON + ' } else { ' + OFF + ' }',
         inputs=[[0, {'weather.forecast(3)': None}]], expected=[action(0, 'off')]),
    dict(id='effectful_return_refused', rule='return assignment must not erase Toggle ACTION',
         period=0, horizon_ms=0, script='x = (#Lamp).switch_toggle()',
         inputs=[[0, {}]], expected_refusal='silent input'),
    dict(id='initializer_after_delay', rule='initial-iteration assignment reads when reached, including after delay',
         period=100, horizon_ms=400,
         script='delay(150 MSEC)\nx := ' + INPUT + '\n' + BRANCH,
         inputs=[[0, {'input.switch': True}], [100, {'input.switch': False}]],
         expected=[action(150, 'off'), action(400, 'off')]),
    dict(id='initializer_in_late_branch', rule='initializer skipped in first iteration stays skipped in later iterations',
         period=100, horizon_ms=300,
         script='if (' + INPUT + ' == true) { x := true }\n' + BRANCH,
         inputs=[[0, {'input.switch': False}], [100, {'input.switch': True}]],
         expected=[action(0, 'off'), action(100, 'off'), action(200, 'off'), action(300, 'off')]),
]

# Independent local sources, not actual runtime attestations. Hash exactly the
# inspected files; no environment files, credentials, or network are accessed.
SOURCES = {
    'local_language_description': ROOT / 'docs/JOI_SPEC.md',
    'lowering_rules': ROOT / 'files/joi_common.md',
    'lowering_cycle_rules': ROOT / 'files/joi_cycle.md',
    'local_grammar': ROOT / 'lowering/parser/JOILang.g4',
    'generated_lexer': ROOT / 'lowering/parser/generated/JOILangLexer.py',
    'generated_parser': ROOT / 'lowering/parser/generated/JOILangParser.py',
    'legacy_simulator': ROOT / 'sensys/simulators/joi_simulator.py',
    'hub_api_client': ROOT.parent / 'joi-agent/mcp_server/tools.py',
    'other_project_mock': ROOT.parent / 'mysmax/execution/mock.py',
    'catalog': ROOT / 'files/service_list_ver2.0.7.json',
    'target_runtime_contract': ROOT / 'explorer/docs/model/RUNTIME_CONTRACT.md',
}


def grammar_check(script):
    # Call ANTLR directly: the generation validator silently skips grammar when
    # the dependency is absent, which cannot count as conformance evidence.
    try:
        from antlr4 import InputStream, CommonTokenStream
        from antlr4.error.ErrorListener import ErrorListener
        from lowering.parser.generated.JOILangLexer import JOILangLexer
        from lowering.parser.generated.JOILangParser import JOILangParser
    except ImportError as exc:
        return {'status': 'UNAVAILABLE', 'reason': str(exc)}
    errors = []

    class Listener(ErrorListener):
        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
            errors.append({'line': line, 'column': column, 'message': msg})

    lexer = JOILangLexer(InputStream(script))
    lexer.removeErrorListeners()
    lexer.addErrorListener(Listener())
    parser = JOILangParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(Listener())
    parser.scenario()
    return {'status': 'REJECTED' if errors else 'ACCEPTED', 'errors': errors}


def replay(case):
    pair = prepare_pair({'timeline': [{'op': 'start_at', 'anchor': 'now'}]}, {},
                        DEVICES, {'script': case['script'], 'period': case['period'], 'cron': ''})
    # Validate supplied values against catalog and coverage requirements, but
    # retain their explicit schedule rather than generate BFS input sequences.
    declared = {}
    for _, update in case['inputs']:
        for key, value in update.items():
            if value not in declared.setdefault(key, []):
                declared[key].append(value)
    pair_input_domains(pair, declared)
    updates = dict(case['inputs'])
    values, gv, inputs, trace = {}, {}, {}, []
    for t in range(case['horizon_ms'] + 1):
        inputs.update(updates.get(t, {}))
        result = pair.code_runner.step(values, gv, inputs, t, first_tick=(t == 0))
        values, gv = result.vars, result.gv
        for a in result.actions:
            if a.fanout is not None:
                raise ValueError('these singleton probes do not implement fanout normalization')
            trace.append({'t_ms': t, 'service': a.service, 'method': a.method,
                          'args': list(a.args), 'target': list(a.target)})
    return trace


def evaluate(case):
    row = {'id': case['id'], 'probe': case, 'grammar': grammar_check(case['script']),
           'actual_runtime_status': 'UNAVAILABLE'}
    try:
        row['observed_model_trace'] = replay(case)
        if 'expected_refusal' in case:
            row['model_status'] = 'FAIL'
        elif 'expected' in case:
            row['model_status'] = 'PASS' if row['observed_model_trace'] == case['expected'] else 'FAIL'
        else:
            row['model_status'] = 'CHARACTERIZED_OPEN_RULE'
    except Unsupported as exc:
        row['reason'] = str(exc)
        row['model_status'] = ('EXPECTED_REFUSAL' if case.get('expected_refusal')
                               and case['expected_refusal'] in str(exc) else 'UNEXPECTED_REFUSAL')
    except Exception as exc:
        row.update(model_status='ERROR', reason=f'{type(exc).__name__}: {exc}')
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    rows = [evaluate(case) for case in CASES]
    # Changed candidate programs are diagnostic controls, NOT independently
    # implemented runtime/interpreter mutants or additional real-runtime tests.
    controls = []
    for case_id, old, new in [('delay_150', '150 MSEC', '200 MSEC'),
                             ('wait_preserves_continuation',
                              'wait until(' + INPUT + ' == true)\n' + OFF,
                              'if (' + INPUT + ' == true) { ' + OFF + ' }'),
                             ('initial_value_persists', ':=', '=')]:
        base = next(c for c in CASES if c['id'] == case_id)
        mutant = dict(base, script=base['script'].replace(old, new))
        row = evaluate(mutant)
        controls.append({'id': case_id, 'replacement': [old, new],
                         'detected': row['model_status'] == 'FAIL', 'observation': row})
    source_rows = {}
    for name, path in SOURCES.items():
        source_rows[name] = {'path': str(path), 'available': path.is_file()}
        if path.is_file():
            source_rows[name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    source_hash = hashlib.sha256()
    for path in sorted((ROOT / 'explorer').rglob('*.py')):
        source_hash.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
    source_hash.update(b'timeline_ir/catalog.py\0' + (ROOT / 'timeline_ir/catalog.py').read_bytes() + b'\0')
    result = {
        'evidence_class': 'development_only_model_boundary_probes',
        'actual_runtime_status': 'UNAVAILABLE', 'actual_runtime_runs': 0,
        'target_runtime_contract': 'runtime-contract-v1',
        'e1_complete': False, 'semantics': 'contract-v1',
        'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'evaluator_sha256': source_hash.hexdigest(),
        'sources': source_rows, 'devices': DEVICES, 'input_step_ms': 100,
        'timer_step_ms': 1, 'cases': rows, 'program_mutation_controls': controls,
        'grammar_boundary': {'script': 'delay(1.5 SEC)\n' + ON,
                             'local_antlr': grammar_check('delay(1.5 SEC)\n' + ON)},
    }
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    counts = {s: sum(r['model_status'] == s for r in rows) for s in sorted({r['model_status'] for r in rows})}
    print(json.dumps({'model': counts, 'controls_detected': sum(c['detected'] for c in controls),
                      'actual_runtime_runs': 0, 'e1_complete': False}))
    if any(r['model_status'] in ('FAIL', 'ERROR', 'UNEXPECTED_REFUSAL') for r in rows) or not all(c['detected'] for c in controls):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
