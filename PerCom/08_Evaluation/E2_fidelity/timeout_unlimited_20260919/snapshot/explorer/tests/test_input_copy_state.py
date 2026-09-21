"""Carried copies of external reads (prev/curr idioms) and exact-domain guards.

2026-09-11: a carried variable whose every definition is a read, literal, bool
result or copy of such a variable is finite over the declared input domain, and
joint/derived guards whose sources are all exactly enumerated are admitted.
Each positive or negative result below also has an independent concrete witness.

Run: python3 -m explorer.tests.test_input_copy_state
"""
import traceback

from explorer.runtime.interp import Unsupported
from explorer.runtime.pause import PauseRunner
from explorer.verification.product import replay_divergence
from explorer.verification.timed import timed_product
from explorer.tests.test_contract import trace

X = '(#Sensor).sensor_value'
Y = '(#Other).other_value'
SAY = '(#Speaker).speaker_speak("hit")'
NEVER = 'wait until(false)'


def periodic(source, period_ms=1000):
    return PauseRunner(source, True, period_ms=period_ms)


def schedule(values, step=1000):
    return [(i * step, {'sensor.value': v}) for i, v in enumerate(values)]


def equivalent(a, b, domains):
    result = timed_product(a, b, input_domains=domains)
    assert result.verdict == 'EQUIV' and result.closed, (result.verdict, result.notes)


def diverges(a, b, domains):
    result = timed_product(a, b, input_domains=domains)
    assert result.verdict == 'DIVERGE', (result.verdict, result.notes)
    assert replay_divergence(a, b, result.divergences[0]).confirmed
    return result


def test_bool_prev_copy_edge_matches_flag_edge_and_differs_from_level():
    prev_curr = periodic(f'last := {X}\ncur = {X}\nif (last == false and cur == true) {{ {SAY} }}\nlast = cur')
    flag = periodic(f'armed := {X} == false\nif ({X} == true) {{\n if (armed) {{ {SAY}\n armed = false }}\n}} else {{ armed = true }}')
    level = periodic(f'if ({X} == true) {{ {SAY} }}')
    history = schedule([False, True, True, False, True])
    assert trace(prev_curr, history) == trace(flag, history) == [(1000, 'speak', ('hit',)), (4000, 'speak', ('hit',))]
    assert len(trace(level, history)) == 3
    domains = {'sensor.value': [False, True]}
    equivalent(prev_curr, flag, domains)
    diverges(prev_curr, level, domains)


def test_numeric_prev_copy_rise_matches_flag_and_boundary_operator_differs():
    rise = periodic(f'prev := {X}\ncur = {X}\nif (prev <= 28 and cur > 28) {{ {SAY} }}\nprev = cur')
    flag = periodic(f'armed := {X} <= 28\nif ({X} > 28) {{\n if (armed) {{ {SAY}\n armed = false }}\n}} else {{ armed = true }}')
    strict = periodic(f'prev := {X}\ncur = {X}\nif (prev < 28 and cur > 28) {{ {SAY} }}\nprev = cur')
    history = schedule([25, 28, 29])
    assert trace(rise, history) == [(2000, 'speak', ('hit',))]
    assert trace(strict, history) == []
    domains = {'sensor.value': [25, 28, 28.5, 29]}
    equivalent(rise, flag, domains)
    witness = diverges(rise, strict, domains)
    assert any(inp.get('sensor.value') == 28 for inp, _ in witness.divergences[0].path + [(witness.divergences[0].input_, 0)])


def test_relation_between_read_and_its_copy_needs_an_exact_domain():
    changed = periodic(f'prev := {X}\nif ({X} != prev) {{ {SAY} }}\nprev = {X}')
    assert trace(changed, schedule([1, 1, 2, 2, 1])) == [(2000, 'speak', ('hit',)), (4000, 'speak', ('hit',))]
    try:
        timed_product(changed, periodic(NEVER))
    except Unsupported:
        pass
    else:
        raise AssertionError('relation over partitioned representatives was admitted')
    diverges(changed, periodic(NEVER), {'sensor.value': [1, 2]})


def test_joint_guard_over_exact_domains_is_searched_exhaustively():
    a = PauseRunner(f't = {X}\nh = {Y}\nif (t - h >= 2) {{ {SAY} }}', False)
    same = PauseRunner(f'if ({X} >= {Y} + 2) {{ {SAY} }}', False)
    edge = PauseRunner(f't = {X}\nh = {Y}\nif (t - h > 2) {{ {SAY} }}', False)
    domains = {'sensor.value': [14, 15, 16, 17], 'other.value': [14, 15]}
    try:
        timed_product(a, edge, horizon_ms=0)
    except Unsupported:
        pass
    else:
        raise AssertionError('joint guard without exact domains was admitted')
    assert timed_product(a, same, input_domains=domains, horizon_ms=0).verdict in ('EQUIV', 'EQUIV_BOUNDED')
    witness = [(0, {'sensor.value': 16, 'other.value': 14})]
    assert trace(a, witness) == [(0, 'speak', ('hit',))] and trace(edge, witness) == []
    result = timed_product(a, edge, input_domains=domains, horizon_ms=0)
    assert result.verdict == 'DIVERGE' and replay_divergence(a, edge, result.divergences[0]).confirmed


def test_computed_copy_remains_refused():
    shifted = periodic(f'prev := {X} + 1\nif ({X} > prev) {{ {SAY} }}\nprev = {X} + 1')
    try:
        timed_product(shifted, periodic(NEVER), input_domains={'sensor.value': [1, 2]})
    except Unsupported as error:
        assert 'unbounded carried vars' in str(error) or 'fail-closed' in str(error), error
    else:
        raise AssertionError('arithmetic carried state was admitted')


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
