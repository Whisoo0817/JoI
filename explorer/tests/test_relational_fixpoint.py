"""Relational graph obligations, independent concrete traces and hostile mutants."""
import copy
from dataclasses import asdict
import itertools
import json
from pathlib import Path
import unittest

from explorer.verification.gate import gate_pair
from explorer.runtime.interp import Unsupported
from explorer.runtime.ir_step import IrRunner
from explorer.runtime.integer_text import value_text
from explorer.verification.product import ProductResult, replay_divergence
from explorer.verification.relational_values import PairInt, RelText, reaction, NeedBranch, text
from explorer.verification.state_key import freeze_state
from explorer.tests.test_symbolic_value_flow import case, prepared
from explorer.verification.timed import timed_product
from explorer.verification.gate import selector_binding  # binding decision 2026-09-14


def counter_case(script=None, body=None, *, delay=0, condition=None, wait=False):
    c = case()
    action = {'op': 'call', 'target': 'Speaker.Speak', 'args': {'Text': 'count: $n'}}
    irbody = [action] if body is None else body
    code = 'all(#Speaker).speaker_speak("count: " + k)' if script is None else script
    if condition is not None:
        irbody = [{'op': 'if', 'cond': condition.replace('k', '$n'), 'then': irbody, 'else': []}]
        code = f'if ({condition}) {{ {code} }}'
    if delay:
        irbody = [{'op': 'delay', 'duration': f'{delay} MSEC'}] + irbody
        code = f'delay({delay} MSEC)\n' + code
    if wait:
        c['devices']['Motion'] = {'category': ['MotionSensor'], 'tags': ['MotionSensor']}
        irbody = [{'op': 'wait', 'cond': 'MotionSensor.Motion == true', 'edge': 'none'}] + irbody
        code = 'wait until ((#MotionSensor).motionSensor_motion == true)\n' + code
    c['ir'] = {'timeline': [{'op': 'start_at', 'anchor': 'now'},
        {'op': 'cycle', 'period': '1 SEC', 'count': 'n', 'body': irbody}]}
    c['binding'] = {'Speaker': c['binding']['Speaker']}
    if wait: c['binding']['MotionSensor'] = ['Motion']
    c['joi_block'] = {'period': 1000, 'script': 'k := 0\n' + code + '\nk = k + 1'}
    c['horizon_ms'] = None
    c['verification_mode'] = 'relational'
    return c


def run(c, **caps):
    p = prepared(c)
    return timed_product(p.ir_runner, p.code_runner, verification_mode='relational',
                         max_states=caps.pop('max_states', 500),
                         max_transitions=caps.pop('max_transitions', 5000), **caps)


def concrete(c, horizon=3200, world=None):
    p = prepared(c)
    outputs = []
    for runner in (p.ir_runner, p.code_runner):
        v, log = {}, []
        # Independent, deliberately fine schedule for testing, not certifying.
        for now in range(horizon+1):
            s = runner.step(v, {}, (world or {}).get(now//100, {}), now, first_tick=now==0)
            v = s.vars
            log += [(now, a.args) for a in s.actions]
        outputs.append(log)
    return outputs


class RelationalTests(unittest.TestCase):
    def assert_certified(self, c, **caps):
        r = run(c, **caps)
        self.assertEqual(r.claim, 'EQUIV-FIXPOINT', r.notes)
        cert = r.symbolic_certificate
        self.assertTrue(r.closed and cert['complete'])
        self.assertTrue(cert['initial_relation'])
        self.assertTrue(all(x['post_equal'] and x['action_equal'] for x in cert['events']))
        json.dumps(asdict(r))
        return r

    def assert_not_certified(self, c):
        try: r = run(c)
        except Unsupported: return
        self.assertNotEqual(r.verdict, 'EQUIV', r.notes)
        self.assertFalse(r.symbolic_certificate['complete'])
        if r.verdict == 'DIVERGE':
            p = prepared(c)
            self.assertTrue(all(replay_divergence(p.ir_runner, p.code_runner, d).confirmed for d in r.divergences))

    def test_named_counter_raw_ir_trace_012(self):
        c = counter_case()
        a, b = concrete(c, 2200)
        self.assertEqual(a, [item for item in [(0, ('count: 0',)), (1000, ('count: 1',)), (2000, ('count: 2',))] for _ in range(2)])
        self.assertEqual(a, b)

    def test_renamed_counter_closes_without_horizon(self):
        c = counter_case()
        r = self.assert_certified(c)
        self.assertLessEqual(r.n_states, 10)  # Silent periods no longer need ten grid states.
        self.assertEqual(r.symbolic_certificate['mapping']['code_name'], 'k')
        self.assertTrue(any(x[0] == 'increment' for ev in r.symbolic_certificate['events'] for x in ev['ir_observations']))

    def test_delay_keeps_exact_timing_and_closes(self):
        c = counter_case(delay=150)
        r = self.assert_certified(c)
        self.assertLess(r.n_states, 100)
        a, b = concrete(c, 2600)
        self.assertEqual(a, [item for item in [(150, ('count: 0',)), (1300, ('count: 1',)), (2450, ('count: 2',))] for _ in range(2)])
        self.assertEqual(a, b)

    def test_same_counter_guard_explores_both_truths(self):
        r = self.assert_certified(counter_case(condition='k >= 3'))
        values = {answer for ev in r.symbolic_certificate['events'] for _, answer in ev['choices']}
        self.assertEqual(values, {False, True})

    def test_guard_with_blocking_continuation(self):
        c = counter_case(condition='k >= 3')
        c['ir']['timeline'][1]['body'][0]['then'].insert(0, {'op': 'delay', 'duration': '150 MSEC'})
        c['joi_block']['script'] = c['joi_block']['script'].replace('{ all', '{ delay(150 MSEC)\n all')
        self.assert_certified(c)

    def test_external_wait_full_boolean_domain(self):
        c = counter_case(wait=True)
        r = self.assert_certified(c)
        self.assertEqual(set(r.symbolic_certificate['input_domains']['Motion.motion']), {False, True})
        self.assertEqual({ev['input']['Motion.motion'] for ev in r.symbolic_certificate['events']}, {False, True})
        for bits in itertools.product((False, True), repeat=3):
            worlds = {i: {'Motion.motion': bits[min(i, 2)]} for i in range(13)}
            a, b = concrete(c, 1200, worlds)
            self.assertEqual(a, b)

    def test_joint_two_sensor_guards_keep_full_cartesian_product(self):
        c = counter_case(wait=True)
        c['devices']['Motion2'] = {'category': ['MotionSensor'], 'tags': ['MotionSensor', 'Other']}
        c['binding']['MotionSensor'] = {'all': ['Motion', 'Motion2']}
        c['joi_block']['script'] = c['joi_block']['script'].replace('(#MotionSensor)', 'all(#MotionSensor)')
        r = self.assert_certified(c)
        inputs = {tuple(sorted(ev['input'].items())) for ev in r.symbolic_certificate['events']}
        self.assertEqual(len(inputs), 4)

    def test_initialization_update_text_and_order_mutations(self):
        for old, new in [('k := 0', 'k := 1'), ('k + 1', 'k + 2'),
                         ('count: ', 'wrong: '), ('k := 0', 'k = 0'),
                         ('k = k + 1', 'k = k + 1\nk = k + 1')]:
            c = counter_case(); c['joi_block']['script'] = c['joi_block']['script'].replace(old, new)
            with self.subTest(new=new): self.assert_not_certified(c)
        c = counter_case(); c['joi_block']['script'] = 'k := 0\nk = k + 1\nall(#Speaker).speaker_speak("count: " + k)'
        self.assert_not_certified(c)

    def test_fault_only_after_iteration_1000_is_not_certified(self):
        c = counter_case(script='if (k >= 1000) { all(#Speaker).speaker_speak("wrong") } else { all(#Speaker).speaker_speak("count: " + k) }')
        a, b = concrete(c)
        self.assertEqual(a, b)  # All former 3.2-second observations agree.
        self.assert_not_certified(c)

    def test_different_guard_is_not_assumed_equal(self):
        c = counter_case(condition='k >= 3')
        c['joi_block']['script'] = c['joi_block']['script'].replace('k >= 3', 'k >= 4')
        self.assert_not_certified(c)

    def test_branch_only_missing_increment_is_not_certified(self):
        c = counter_case()
        c['joi_block']['script'] = c['joi_block']['script'].replace('k = k + 1', 'if (k < 1000) { k = k + 1 }')
        self.assert_not_certified(c)

    def test_wait_then_missing_update_is_not_certified(self):
        c = counter_case(wait=True)
        c['joi_block']['script'] = c['joi_block']['script'].replace('k = k + 1', '')
        self.assert_not_certified(c)

    def test_local_copy_is_killed_only_when_dead_at_next_entry(self):
        c = counter_case(script='old = k\nall(#Speaker).speaker_speak("count: " + old)')
        r = self.assert_certified(c)
        self.assertTrue(any('old' in ev['dead_locals'] for ev in r.symbolic_certificate['events']))

    def test_live_old_snapshot_is_never_rebased_as_current(self):
        c = counter_case(script='if (k >= 1) { all(#Speaker).speaker_speak("count: " + old) } else { all(#Speaker).speaker_speak("count: " + k) }\nold = k')
        self.assert_not_certified(c)

    def test_wrong_variable_same_type_is_not_assumed_paired(self):
        c = counter_case(script='x = 0\nall(#Speaker).speaker_speak("count: " + x)')
        self.assert_not_certified(c)

    def test_modulo_guard_does_not_fold_observable_count(self):
        c = counter_case(condition='k % 2 == 0')
        a, b = concrete(c, 4200)
        self.assertEqual(a, [item for item in [(0, ('count: 0',)), (2000, ('count: 2',)), (4000, ('count: 4',))] for _ in range(2)])
        self.assertEqual(a, b)
        self.assert_not_certified(c)  # modulo is explicitly outside new v1.

    def test_reentry_initializes_counter_again(self):
        inner = counter_case()['ir']['timeline'][1]
        inner['until'] = '$n >= 2'
        ir = {'timeline': [{'op': 'start_at', 'anchor': 'now'},
                          {'op': 'cycle', 'count': 2, 'period': '100 MSEC', 'body': [inner]}]}
        r = IrRunner(ir); v = {}; log = []
        for now in range(4301):
            s = r.step(v, {}, {}, now, first_tick=now==0); v = s.vars
            log.extend(a.args[0] for a in s.actions)
        self.assertEqual(log, ['count: 0', 'count: 1', 'count: 0', 'count: 1'])

    def test_float_raw_string_and_unimplemented_arithmetic_fail_closed(self):
        for script in ['all(#Speaker).speaker_speak(k)',
                       'all(#Speaker).speaker_speak("count: " + k*1)',
                       'all(#Speaker).speaker_speak("count: " + k/1)']:
            self.assert_not_certified(counter_case(script=script))
        c = counter_case(); c['joi_block']['script'] = c['joi_block']['script'].replace('k := 0', 'k := 0.0')
        self.assert_not_certified(c)

    def test_limits_are_inconclusive_and_horizon_is_not_removed(self):
        for caps in ({'max_states': 1}, {'max_transitions': 1}):
            r = run(counter_case(delay=150), **caps)  # Still needs multiple distinct phases.
            self.assertEqual(r.claim, 'INCONCLUSIVE')
            self.assertFalse(r.closed)
        with self.assertRaises(Unsupported): run(counter_case(), horizon_ms=3200)
        r = run(counter_case(wait=True), max_input_combinations=1)
        self.assertEqual(r.claim, 'INCONCLUSIVE')

    def test_gv_clock_and_nested_cycle_are_refused(self):
        for script in ['x = gv.get("x")', 'x = clock.timestamp', 'loop (true) { k = k+1 }']:
            self.assert_not_certified(counter_case(script=script))
        c = counter_case(); c['ir']['timeline'][1]['body'] = [copy.deepcopy(c['ir']['timeline'][1])]
        self.assert_not_certified(c)

    def test_integer_decimal_conversion_has_no_hidden_digit_bound(self):
        n = 10**5000
        self.assertEqual(value_text(n), '1'+'0'*5000)
        self.assertEqual(value_text(-n), '-1'+'0'*5000)
        from explorer.runtime.expr import evaluate, BinaryOp, Lit, EvalContext
        self.assertEqual(evaluate(BinaryOp('+', Lit('v='), Lit(n)), EvalContext({}, {}, {})), 'v=1'+'0'*5000)

    def test_symbolic_operations_never_use_identity_or_typeerror_fallback(self):
        x = PairInt()
        for operation in [lambda: str(x), lambda: float(x), lambda: x*2,
                          lambda: text([x]) == '1', lambda: x+True]:
            with self.assertRaises(Unsupported): operation()
        with reaction({}):
            with self.assertRaises(NeedBranch): bool(x == 0)
        self.assertEqual(freeze_state(x), freeze_state(PairInt()))

    def test_default_gate_remains_fail_closed_for_observable_counter(self):
        c = counter_case()
        g = gate_pair(c['ir'], c['binding'], c['devices'], c['joi_block'], horizon_ms=3200)
        self.assertEqual(g.verdict, 'REFUSED')
        g = gate_pair(c['ir'], c['binding'], c['devices'], c['joi_block'], verification_mode='relational')
        self.assertEqual(g.product.claim, 'EQUIV-FIXPOINT')

    def test_independent_fanout_order_still_commutes(self):
        with selector_binding(False):  # selector correctness: frozen semantics
            c = counter_case()
            c['binding']['Speaker'].reverse()
            self.assert_certified(c)
            c['joi_block']['script'] = c['joi_block']['script'].replace('all(#Speaker)', '(#Speaker)')
            self.assert_not_certified(c)

    def test_numeric_input_guards_use_joint_catalog_partition(self):
        c = counter_case()
        c['binding']['WeatherProvider'] = ['System_WeatherProvider']
        body = c['ir']['timeline'][1]['body']
        c['ir']['timeline'][1]['body'] = [{'op': 'if', 'cond': 'WeatherProvider.TemperatureWeather > 25.3', 'then': body, 'else': []}]
        old = 'all(#Speaker).speaker_speak("count: " + k)'
        c['joi_block']['script'] = c['joi_block']['script'].replace(old, 'if ((#WeatherProvider).weatherProvider_temperatureWeather > 25.3) { ' + old + ' }')
        r = self.assert_certified(c)
        self.assertGreaterEqual(len(r.symbolic_certificate['input_domains']['System_WeatherProvider.temperatureweather']), 2)
        c['joi_block']['script'] = c['joi_block']['script'].replace('25.3', '26.3')
        self.assert_not_certified(c)

    def test_bounded_string_signature_cannot_certify_arbitrary_count(self):
        c = counter_case()
        p = prepared(c)
        domain = p.service_model.resolve('speaker', 'speak', 'function')['arguments'][0]
        domain['members'] = ['count: 0', 'count: 1']
        try:
            r = timed_product(p.ir_runner, p.code_runner, verification_mode='relational')
        except Unsupported:
            return
        self.assertNotEqual(r.verdict, 'EQUIV')

    def test_contract_evaluator_uses_explicit_unbounded_mode(self):
        from explorer.eval.contract_eval import evaluate_case
        c = counter_case()
        r = evaluate_case(c)
        self.assertEqual(r['status'], 'RELATIONAL_CERTIFIED', r)
        self.assertEqual(r['exact']['verdict'], 'NOT_APPLICABLE')

    def test_unclosed_result_cannot_claim_fixpoint(self):
        self.assertEqual(ProductResult('EQUIV', closed=False).claim, 'INCONCLUSIVE')


if __name__ == '__main__': unittest.main()
