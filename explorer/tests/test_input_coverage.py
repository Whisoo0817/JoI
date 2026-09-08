"""Independent witnesses for automatic domain coverage, not oracle agreement alone.

Run: python3 -m explorer.tests.test_input_coverage
"""
import itertools
import traceback

from explorer.verification.input_coverage import representatives, joi_coverage
from explorer.runtime.interp import Unsupported, parse
from explorer.runtime.ir_step import IrRunner
from explorer.runtime.pause import PauseRunner
from explorer.verification.product import merge_axes, replay_divergence
from explorer.verification.timed import timed_product
from explorer.tests.test_contract import trace, timeline

X = '(#Sensor).sensor_value'
SAY = '(#Speaker).speaker_speak("hit")'
NEVER = 'wait until(false)'
OPS = ('==', '!=', '<', '>', '<=', '>=')


def signature(value, predicates):
    # Intentionally do not call the partitioner's predicate evaluator.
    result = []
    for op, constant in predicates:
        if op == 'truth':
            result.append(bool(value))
        elif op == '==':
            result.append(value == constant)
        elif op == '!=':
            result.append(value != constant)
        elif value is None or constant is None:
            result.append(False)
        elif op == '<':
            result.append(value < constant)
        elif op == '>':
            result.append(value > constant)
        elif op == '<=':
            result.append(value <= constant)
        else:
            result.append(value >= constant)
    return tuple(result)


def test_numeric_partition_covers_joint_truth_vectors_and_missing():
    values = [None, False, True] + [i / 10 for i in range(-120, 121)]
    for left, right in itertools.product(OPS, repeat=2):
        for a, b in ((-1.01, 1.01), (1, 1.1), (1.01, 1.09), (-0.1, 0), (10, 10.4)):
            predicates = [(left, a), (right, b), ('truth', None)]
            reps, _ = representatives(predicates)
            assert {signature(v, predicates) for v in values} <= {signature(v, predicates) for v in reps}


def test_string_partition_covers_lexical_intervals_and_sentinel_collision():
    values = [None, 'aa', '__other__', '__other__x', '\U0010ffff']
    values += [''.join(p) for n in range(4) for p in itertools.product('\0_ab', repeat=n)]
    for left, right in itertools.product(OPS, repeat=2):
        for a, b in (('a', 'b'), ('a', 'a\0'), ('', '\0'), ('__other__', '__other__x')):
            predicates = [(left, a), (right, b), ('truth', None)]
            reps, _ = representatives(predicates)
            assert {signature(v, predicates) for v in values} <= {signature(v, predicates) for v in reps}


def test_scalar_equality_partition_keeps_mixed_types():
    values = [None, False, True, 0, 1, 2, -0.0, 1.0, 9.9, 10, '', 'on', '__other__', 'other']
    predicates = [('==', c) for c in (None, False, True, 10, 'on', '__other__')] + [('truth', None)]
    reps, family = representatives(predicates)
    assert family == 'scalar'
    assert {signature(v, predicates) for v in values} <= {signature(v, predicates) for v in reps}


def test_previously_false_equivalences_have_independent_action_witnesses():
    cases = [
        (f'if ({X} == 10 or {X} == "on") {{ {SAY} }}', f'if ({X} == 10) {{ {SAY} }}', {'sensor.value': 'on'}),
        (f'if ({X} != true and {X} != false) {{ {SAY} }}', NEVER, {'sensor.value': None}),
        (f'if ({X} > "a" and {X} < "b") {{ {SAY} }}', NEVER, {'sensor.value': 'aa'}),
        (f'if ({X} != "__other__") {{ {SAY} }}', NEVER, {'sensor.value': 'another'}),
    ]
    for source, other, witness in cases:
        a, b = PauseRunner(source, False), PauseRunner(other, False)
        assert trace(a, [(0, witness)]) == [(0, 'speak', ('hit',))]
        assert trace(b, [(0, witness)]) == []
        result = timed_product(a, b, horizon_ms=0)
        assert result.verdict == 'DIVERGE'
        assert replay_divergence(a, b, result.divergences[0]).confirmed


def test_initializers_and_long_alias_chains_require_exact_output_inputs():
    source = f'v0 := {X}\n' + '\n'.join(f'v{i} = v{i-1}' for i in range(1, 41))
    source += '\n(#Speaker).speaker_speak(v40)'
    a, b = PauseRunner(source, False), PauseRunner('(#Speaker).speaker_speak(null)', False)
    try:
        timed_product(a, b, horizon_ms=0)
    except Unsupported as error:
        assert 'explicit input domain' in str(error)
    else:
        raise AssertionError('captured input silently omitted')
    assert trace(a, [(0, {'sensor.value': 9.9})]) == [(0, 'speak', (9.9,))]
    assert timed_product(a, b, input_domains={'sensor.value': [None, 9.9]}, horizon_ms=0).verdict == 'DIVERGE'


def test_long_alias_guards_and_all_branch_definitions_are_collected():
    source = f'v0 := {X}\n' + '\n'.join(f'v{i} = v{i-1}' for i in range(1, 41))
    source += f'\nif (v40 > 10) {{ {SAY} }}'
    assert timed_product(PauseRunner(source, False), PauseRunner(NEVER, False), horizon_ms=0).verdict == 'DIVERGE'
    coverage = joi_coverage(parse(f'a = {X}\nif (true) {{ b = a }} else {{ b = (#Other).other_value }}\nif (b == "on") {{ {SAY} }}'))
    for key in ('sensor.value', 'other.value'):
        assert ('==', 'on') in coverage.predicates[key]
    cyc = joi_coverage(parse(f'a = b\nb = a\nb = {X}\nif (a > 10) {{ {SAY} }}'))
    assert ('>', 10) in cyc.predicates['sensor.value']


def test_arithmetic_in_initializer_remains_refused_with_domains():
    a = PauseRunner(f'x := {X} * 2\n(#Speaker).speaker_speak(x)', False)
    try:
        timed_product(a, a, input_domains={'sensor.value': [1, 2]}, horizon_ms=0)
    except Unsupported as error:
        assert 'arith-arg' in str(error)
    else:
        raise AssertionError(':= bypassed D7')


def test_external_numeric_gv_is_not_boolean_only():
    source = f'if ((#GlobalVariable).globalVariable_getFloat("v") > 10) {{ {SAY} }}'
    a, b = PauseRunner(source, False), PauseRunner(NEVER, False)
    assert a.step({}, {'v': 11}, {}, 0, True).actions[0].args == ('hit',)
    result = timed_product(a, b, horizon_ms=0)
    assert result.verdict == 'DIVERGE'
    assert result.divergences[0].input_['@gv:v'] > 10


def test_pair_gv_ownership_and_all_initial_values():
    get = '(#GlobalVariable).globalVariable_getFloat("v")'
    put = '(#GlobalVariable).globalVariable_setFloat("v", 0)'
    a = PauseRunner(f'if ({get} > 10) {{ {SAY} }}\n{put}', False)
    b = PauseRunner(put, False)
    axes = merge_axes(a.axes, b.axes)
    assert '@gv:v' not in axes.cells and any(v is not None and v > 10 for v in axes.initial_cells['v'])
    result = timed_product(a, b, horizon_ms=0)
    assert result.verdict == 'DIVERGE' and result.divergences[0].initial_gv['v'] > 10
    assert replay_divergence(a, b, result.divergences[0]).confirmed
    # Only the other program writes: this is still one fixed initial GV, not
    # an input overwritten independently on every reaction.
    c = PauseRunner(f'if ({get} > 10) {{ {SAY} }}', False)
    assert '@gv:v' not in merge_axes(c.axes, b.axes).cells
    for kwargs in ({'initial_gv_domains': {}}, {'input_domains': {'@gv:v': [0, 11]}}):
        try:
            timed_product(a, b, horizon_ms=0, **kwargs)
        except (ValueError, Unsupported):
            pass
        else:
            raise AssertionError('initial GV coverage/ownership bypass')


def test_observable_initial_gv_requires_explicit_domain():
    get = '(#GlobalVariable).globalVariable_getFloat("v")'
    put = '(#GlobalVariable).globalVariable_setFloat("v", 0)'
    a = PauseRunner(f'(#Speaker).speaker_speak("" + {get})\n{put}', False)
    b = PauseRunner(f'(#Speaker).speaker_speak("1")\n{put}', False)
    try:
        timed_product(a, b, horizon_ms=0)
    except Unsupported as error:
        assert 'initial GV domain' in str(error)
    else:
        raise AssertionError('invented observable initial GV values')
    result = timed_product(a, b, initial_gv_domains={'v': [1, 1.0]}, horizon_ms=0)
    assert result.verdict == 'DIVERGE' and type(result.divergences[0].initial_gv['v']) is float


def test_query_parameter_types_and_complete_sources_match_ir():
    ir = IrRunner(timeline({'op': 'call', 'target': 'WeatherProvider.Forecast', 'args': {'hour': 1.0}, 'var': 'v'},
        {'op': 'if', 'cond': '$v > 10', 'then': [{'op': 'call', 'target': 'Speaker.Speak', 'args': {'text': 'hit'}}]}))
    code = PauseRunner(f'v = (#WeatherProvider).weatherProvider_forecast(1.0)\nif (v > 10) {{ {SAY} }}', False)
    key = 'weatherprovider.forecast(1.0)'
    assert set(ir.axes.cells) == set(code.axes.cells) == {key}
    assert trace(ir, [(0, {key: 11})]) == trace(code, [(0, {key: 11})]) == [(0, 'speak', ('hit',))]
    assert timed_product(ir, code, horizon_ms=0).verdict == 'EQUIV'
    reads = PauseRunner(f'a = (#WeatherProvider).weatherProvider_forecast(1)\nb = (#WeatherProvider).weatherProvider_forecast(2)\nif (a > 10 and b < 5) {{ {SAY} }}', False)
    assert set(reads.axes.cells) == {'weatherprovider.forecast(1)', 'weatherprovider.forecast(2)'}


def test_dynamic_query_keys_fail_closed_even_with_declared_domains():
    a = PauseRunner('n = 1\nv = (#WeatherProvider).weatherProvider_forecast(n)', False)
    try:
        timed_product(a, a, input_domains={'weatherprovider.forecast(1)': [0, 1]}, horizon_ms=0)
    except Unsupported as error:
        assert 'literal arguments' in str(error)
    else:
        raise AssertionError('unproven query range accepted')


def test_numeric_order_model_is_recorded_and_extreme_thresholds_need_domains():
    a = PauseRunner(f'if ({X} > 10) {{ {SAY} }}', False)
    result = timed_product(a, a, horizon_ms=0)
    assert any('numeric' in note and 'sensor.value' in note for note in result.notes)
    huge = PauseRunner(f'if ({X} > 100000000000000000000) {{ {SAY} }}', False)
    try:
        timed_product(huge, huge, horizon_ms=0)
    except Unsupported as error:
        assert 'explicit input domain' in str(error)
    else:
        raise AssertionError('uncertified float boundary silently accepted')
    assert timed_product(huge, PauseRunner(NEVER, False),
        input_domains={'sensor.value': [10**20, 10**20+1]}, horizon_ms=0).verdict == 'DIVERGE'


def test_candidate_cannot_silently_drop_reference_string_inputs():
    a = PauseRunner(f'if ({X} == "on") {{ {SAY} }}', False)
    b = PauseRunner(f'if ({X} > 10 and {X} < 0) {{ {SAY} }}', False)
    try:
        timed_product(a, b, horizon_ms=0)
    except Unsupported as error:
        assert 'explicit input domain' in str(error)
    else:
        raise AssertionError('candidate numeric guard narrowed away reference string inputs')


def test_explicit_mistyped_order_input_is_refused_by_gate():
    from explorer.tests.synthetic_gate import gate_pair
    ir = timeline({'op': 'if', 'cond': 'Sensor.Value > 10', 'then': [
        {'op': 'call', 'target': 'Speaker.Speak', 'args': {'text': 'hit'}}]})
    binding = {'Sensor': ['sensor'], 'Speaker': ['speaker']}
    devices = {k: {'category': [v], 'tags': [v]} for k, v in [('sensor', 'Sensor'), ('speaker', 'Speaker')]}
    result = gate_pair(ir, binding, devices,
        {'script': f'if ({X} > 10) {{ {SAY} }}', 'period': 0},
        input_domains={'sensor.value': ['bad']}, horizon_ms=0)
    assert result.verdict == 'REFUSED' and 'TypeError' in str(result.notes)


def test_missing_value_edge_reset_has_independent_history_witness():
    # JoI periodic reference and mutation differ only on the missing interval.
    prefix = f'armed := false\nt = {X}\nif (t > 25 and armed == false) {{ {SAY}\narmed = true }}\n'
    correct = PauseRunner(prefix + 'if (not (t > 25)) { armed = false }', True, period_ms=100)
    wrong = PauseRunner(prefix + 'if (t <= 25) { armed = false }', True, period_ms=100)
    schedule = [(0, {'sensor.value': 26}), (100, {'sensor.value': None}), (200, {'sensor.value': 26})]
    assert trace(correct, schedule) == [(0, 'speak', ('hit',)), (200, 'speak', ('hit',))]
    assert trace(wrong, schedule) == [(0, 'speak', ('hit',))]
    assert timed_product(correct, wrong, horizon_ms=200).verdict == 'DIVERGE'


def main():
    tests = sorted((name, value) for name, value in globals().items() if name.startswith('test_'))
    failures = 0
    for name, function in tests:
        try:
            function()
            print('PASS', name)
        except Exception:
            failures += 1
            print('FAIL', name)
            traceback.print_exc()
    print(f'{len(tests)-failures}/{len(tests)} passed')
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
