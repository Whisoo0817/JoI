"""E1 internal semantics differential suite; no deployment measurements required.

python -m explorer.tests.e1_internal_conformance --output <new-file.json>
"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
from unittest.mock import patch

from explorer.verification.gate import prepare_pair
from explorer.runtime.ir_step import IrRunner
from explorer.runtime.pause import PauseRunner
from explorer.tests.semantic_reference import Reference

ROOT = Path(__file__).resolve().parents[2]
DEVICES = {
    'sensor': {'category': ['ContactSensor'], 'tags': ['Sensor']},
    'lamp': {'category': ['Switch'], 'tags': ['Lamp']},
    'speaker': {'category': ['Speaker'], 'tags': ['Speaker']},
    'weather': {'category': ['WeatherProvider'], 'tags': ['Weather']},
}
BINDING = {'ContactSensor': ['sensor'], 'Switch': ['lamp'],
           'Speaker': ['speaker'], 'WeatherProvider': ['weather']}
X = ('input', 'sensor.contact')
W = ('input', 'weather.forecast(3)')
TRUE = ('eq', X, ('literal', True))
ON = ('call', 'switch', 'on', 'lamp', ())
OFF = ('call', 'switch', 'off', 'lamp', ())


def branch(expr=TRUE, yes=(ON,), no=(OFF,)):
    return ('if', expr, yes, no)


PROGRAMS = [
    ('delay', (ON, ('delay', 150), OFF), 0),
    ('zero_delay', (ON, ('delay', 0), OFF), 0),
    ('period', (ON, ('delay', 150), OFF), 100),
    ('wait', (ON, ('wait', TRUE), OFF), 0),
    ('period_wait', (ON, ('wait', TRUE), OFF), 100),
    ('branch_resume', (branch(yes=(ON, ('delay', 150), OFF), no=()),), 0),
    ('nested_wait', (branch(yes=(('delay', 50), ('wait', TRUE), OFF), no=()), ON), 0),
    ('tie', (('delay', 200), branch()), 0),
    ('stored_read', (('read', 'saved', X), ('delay', 150),
                     branch(('eq', ('variable', 'saved'), ('literal', True)))), 0),
    ('break', (ON, ('break',), OFF), 100),
    ('query_string', (('read', 'w', W), ('delay', 150),
        branch(('eq', ('variable', 'w'), ('literal', 'rain')),
               (('call', 'speaker', 'speak', 'speaker', (('variable', 'w'),)),), ())), 0),
]


def expression(expr, joi=False):
    kind, *args = expr
    if kind == 'literal':
        return json.dumps(args[0])
    if kind == 'variable':
        return ('' if joi else '$') + args[0]
    if kind == 'input':
        if args[0] == 'sensor.contact':
            return '(#Sensor).contactSensor_contact' if joi else 'ContactSensor.Contact'
        raise ValueError('query must be rendered in a read statement')
    if kind == 'eq':
        return '(' + expression(args[0], joi) + ' == ' + expression(args[1], joi) + ')'
    raise ValueError(kind)


def ir_nodes(body):
    result = []
    for node in body:
        kind = node[0]
        if kind == 'call':
            _, service, method, _, args = node
            target = 'Speaker.Speak' if service == 'speaker' else 'Switch.' + method.title()
            result.append({'op': 'call', 'target': target,
                           'args': {'Text': expression(args[0])} if args else {}})
        elif kind == 'read':
            if node[2] == W:
                result.append({'op': 'call', 'target': 'WeatherProvider.Forecast',
                               'args': {'Hour': 3}, 'var': node[1]})
            else:
                result.append({'op': 'read', 'src': expression(node[2]), 'var': node[1]})
        elif kind == 'if':
            result.append({'op': 'if', 'cond': expression(node[1]),
                           'then': ir_nodes(node[2]), 'else': ir_nodes(node[3])})
        elif kind == 'delay':
            result.append({'op': 'delay', 'duration': str(node[1]) + ' MSEC'})
        elif kind == 'wait':
            result.append({'op': 'wait', 'cond': expression(node[1])})
        elif kind == 'break':
            result.append({'op': 'break'})
        elif kind == 'cycle':
            result.append({'op': 'cycle', 'count': node[1],
                           'period': str(node[2]) + ' MSEC', 'body': ir_nodes(node[3])})
        else:
            raise ValueError(kind)
    return result


def joi_source(body):
    lines = []
    for node in body:
        kind = node[0]
        if kind == 'call':
            _, service, method, target, args = node
            lines.append('(#' + target.title() + ').' + service + '_' + method +
                         '(' + ', '.join(expression(x, True) for x in args) + ')')
        elif kind == 'read':
            rhs = '(#Weather).weatherProvider_forecast(3)' if node[2] == W else expression(node[2], True)
            lines.append(node[1] + ' = ' + rhs)
        elif kind == 'if':
            # JoI's local grammar requires a nonempty block.
            lines.append('if (' + expression(node[1], True) + ') {\n' +
                         (joi_source(node[2]) or 'unused = false') + '\n} else {\n' +
                         (joi_source(node[3]) or 'unused = false') + '\n}')
        elif kind == 'delay':
            lines.append('delay(' + str(node[1]) + ' MSEC)')
        elif kind == 'wait':
            lines.append('wait until(' + expression(node[1], True) + ')')
        elif kind == 'break':
            lines.append('break')
        else:
            raise ValueError('not part of paired JoI renderer: ' + kind)
    return '\n'.join(lines)


def prepare(body, period):
    nodes = ir_nodes(body)
    if period:
        nodes = [{'op': 'cycle', 'period': str(period) + ' MSEC', 'body': nodes}]
    ir = {'timeline': [{'op': 'start_at', 'anchor': 'now'}, *nodes]}
    block = {'script': joi_source(body), 'period': period}
    return prepare_pair(ir, BINDING, DEVICES, block), ir, block


def compare(body, period, runners, history, horizon=400):
    reference = Reference(body, period)
    stores = [({}, {}) for _ in runners]
    held = {}
    # Hash full per-ms observations (including silence), while retaining the
    # first mismatch. Compare exact singleton records, not shared normalization.
    digest = hashlib.sha256()
    for t in range(horizon + 1):
        if t % 100 == 0:
            held = history[t // 100]
        expected = reference.step(t, held)
        actual = []
        for i, runner in enumerate(runners):
            v, g = stores[i]
            before = copy.deepcopy((v, g, held))
            r = runner.step(v, g, held, t, first_tick=t == 0)
            if (v, g, held) != before:
                return {'t_ms': t, 'error': 'runner mutated caller state', 'runner': i}
            stores[i] = (r.vars, r.gv)
            records = []
            for a in r.actions:
                if a.fanout is not None or len(a.target) != 1:
                    raise ValueError('singleton observation required')
                records.append((t, a.service, a.method, a.target[0], a.args))
            actual.append(records)
        if any(x != expected for x in actual):
            return {'t_ms': t, 'expected': expected, 'observed': actual}
        digest.update(json.dumps([t, expected, actual], sort_keys=True).encode() + b'\n')
    return {'trace_sha256': digest.hexdigest()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    rows, failures = [], []
    for name, body, period in PROGRAMS:
        pair, ir, block = prepare(body, period)
        key, domain = ('weather.forecast(3)', (None, 'clear', 'rain')) if name == 'query_string' else ('sensor.contact', (False, True))
        summaries = hashlib.sha256()
        count = 0
        for sequence in itertools.product(domain, repeat=5):
            history = [{key: x} for x in sequence]
            outcome = compare(body, period, [pair.ir_runner, pair.code_runner], history)
            count += 1
            if 'trace_sha256' not in outcome:
                failures.append({'id': name, 'history': history, **outcome})
            summaries.update(json.dumps([history, outcome], sort_keys=True).encode() + b'\n')
        rows.append({'id': name, 'ir': ir, 'joi': block, 'body': body, 'period_ms': period,
                     'domain': {key: domain}, 'input_step_ms': 100, 'horizon_ms': 400,
                     'histories': count, 'comparisons_per_history': 2,
                     'observations_sha256': summaries.hexdigest()})

    # IR-only compositional constructor: nested finite cycles must reset their
    # iteration count on every entry. JoI has no internal cycle equivalent.
    nested = (('cycle', 2, 100, (('cycle', 2, 50, (ON,)),)), OFF)
    ir = {'timeline': [{'op': 'start_at', 'anchor': 'now'}, *ir_nodes(nested)]}
    pair = prepare_pair(ir, BINDING, DEVICES, {'script': 'unused = false', 'period': 0})
    nested_result = compare(nested, 0, [pair.ir_runner], [{}] * 6, horizon=500)
    if 'trace_sha256' not in nested_result:
        failures.append({'id': 'nested_cycle', **nested_result})

    # Mutate actual execution code in memory, restoring each original afterward.
    # This does not alter source files, fixtures or the independent oracle.
    mutants = []
    import importlib
    ir_module = importlib.import_module('explorer.runtime.ir_step')
    fixtures = [
        ('joi_period_too_early', PauseRunner, 'step', 'period', 'now_ms + self.period_ms', 'now_ms + 1'),
        ('ir_delay_early', ir_module, 'ir_step', 'delay',
         'if now_ms - round(vars_[reg] * 1000) >= round(x.for_sec * 1000):', 'if True:'),
    ]
    import inspect
    for name, owner, attribute, fixture, old, new in fixtures:
        original = getattr(owner, attribute)
        source = inspect.getsource(original)
        import textwrap
        if source.count(old) != 1:
            raise AssertionError('mutation anchor changed: ' + name)
        namespace = {}
        globals_ = original.__globals__
        exec(compile(textwrap.dedent(source.replace(old, new)), '<E1 mutant ' + name + '>', 'exec'), globals_, namespace)
        _, body, period = next(p for p in PROGRAMS if p[0] == fixture)
        pair, _, _ = prepare(body, period)
        with patch.object(owner, attribute, namespace[attribute]):
            outcome = compare(body, period, [pair.ir_runner, pair.code_runner],
                              [{'sensor.contact': True}] * 5)
        detected = 'expected' in outcome
        mutants.append({'id': name, 'owner': owner.__name__, 'attribute': attribute, 'replacement': [old, new],
                        'detected': detected, 'witness': outcome})
        if not detected:
            failures.append({'id': name, 'error': 'interpreter mutant survived'})

    hashes = {}
    for path in [Path(__file__), Path(__file__).with_name('semantic_reference.py'),
                 ROOT / 'explorer/docs/model/RUNTIME_CONTRACT.md', ROOT / 'files/service_list_ver2.0.7.json',
                 ROOT / 'timeline_ir/catalog.py', *sorted((ROOT / 'explorer').rglob('*.py'))]:
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = {'evidence_class': 'development_internal_semantics', 'semantics': 'contract-v1',
              'boolean_input_policy': 'strict-two-valued-v1',
              'scope': 'defined-model ACTION trace equivalence; deployment measurement not required',
              'all_supported_constructs_exhausted': False, 'source_sha256': hashes,
              'devices': DEVICES, 'binding': BINDING, 'cases': rows,
              'nested_cycle': {'ir': ir, 'body': nested, 'result': nested_result},
              'interpreter_mutants': mutants, 'failures': failures}
    with Path(args.output).open('x') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({'programs': len(rows), 'paired_histories': sum(r['histories'] for r in rows),
                      'ir_only_histories': 1, 'interpreter_mutants_detected': sum(m['detected'] for m in mutants),
                      'failures': len(failures)}))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
