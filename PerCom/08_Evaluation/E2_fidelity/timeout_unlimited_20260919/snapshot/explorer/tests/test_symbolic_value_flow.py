"""Universal text certificates, concrete counterexamples, and sound refusal."""
import itertools
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from explorer.runtime import expr as e
from explorer.eval.contract_eval import evaluate_case
from explorer.verification.gate import gate_pair, prepare_pair
from explorer.runtime.interp import Unsupported
from explorer.runtime.ir_step import eval_cond
from explorer.verification.symbolic import symbolic_specs
from explorer.verification.symbolic_values import InputSymbol, text_join, substitute
from explorer.verification.timed import timed_product
from explorer.tests.test_reference_contract import rows
from explorer.verification.gate import selector_binding  # binding decision 2026-09-14

ROOT = Path(__file__).resolve().parents[2]


def case(key='C01_009'):
    row = rows()[key]
    candidate = json.loads((ROOT / 'explorer/candidates/gemma4-26b-contract-v1-fresh-v4'
                            / (key + '.json')).read_text())
    return {'id': key, 'ir': json.loads(row['ir_gt']),
            'binding': json.loads(row['binding_gt']),
            'devices': json.loads(row['connected_devices']),
            'joi_block': candidate['joi_block'], 'horizon_ms': 3200}


def prepared(c):
    return prepare_pair(c['ir'], c['binding'], c['devices'], c['joi_block'])


def gate(c, **kwargs):
    return gate_pair(c['ir'], c['binding'], c['devices'], c['joi_block'],
                     horizon_ms=c['horizon_ms'], **kwargs)


def delayed(c, ms, fresh=False):
    c['ir']['timeline'].insert(-1, {'op': 'delay', 'duration': f'{ms} MSEC'})
    read, action = c['joi_block']['script'].split('\n')
    c['joi_block']['script'] = (f'delay({ms} MSEC)\n{read}\n{action}' if fresh
                              else f'{read}\ndelay({ms} MSEC)\n{action}')
    return c


class SymbolicValueFlowTests(unittest.TestCase):
    def test_real_temperature_and_arbitrary_menu_text_are_certified_without_enumeration(self):
        for key in ('C01_009', 'C01_017', 'C01_018'):
            with self.subTest(key=key):
                result = gate(case(key))
                self.assertEqual(result.verdict, 'EQUIV-BOUNDED', result.notes)
                self.assertEqual(result.product.n_steps, 2)
                cert = result.product.symbolic_certificate
                self.assertTrue(cert['both_terminated'])
                self.assertTrue(all(event['equal'] for event in cert['events']))
                json.dumps(cert)  # Evidence must be serializable without repr fallbacks.

    def test_chat_string_identity_forwarding_and_seeded_fault(self):
        c = case('C01_019')
        result = gate(c)
        self.assertEqual(result.verdict, 'EQUIV-BOUNDED', result.notes)
        self.assertEqual(result.product.symbolic_certificate['schema'], 'symbolic-value-flow-v1')
        c['joi_block']['script'] = c['joi_block']['script'].replace(
            'speaker_speak(ChatWithAI)', 'speaker_speak("fixed")')
        faulty = gate(c)
        self.assertEqual(faulty.verdict, 'DIVERGE', faulty.notes)
        self.assertTrue(faulty.confirmed)

    def test_variable_names_and_copy_chains_do_not_determine_identity(self):
        c = case()
        read, action = c['joi_block']['script'].split('\n')
        c['joi_block']['script'] = read + '\nx = TemperatureWeather\ny = x\n' + action.replace('TemperatureWeather)', 'y)')
        self.assertEqual(gate(c).verdict, 'EQUIV-BOUNDED')

    def test_reassignment_and_constant_output_have_replayed_counterexamples(self):
        for change in ('constant', 'overwrite'):
            c = case()
            read, action = c['joi_block']['script'].split('\n')
            c['joi_block']['script'] = (read + '\n' + action.replace('TemperatureWeather)', '31)')
                if change == 'constant' else read + '\nTemperatureWeather = 31\n' + action)
            result = gate(c)
            self.assertEqual(result.verdict, 'DIVERGE', result.notes)
            self.assertTrue(result.confirmed)

    def test_same_type_from_different_device_is_not_equal(self):
        with selector_binding(False):  # selector correctness: frozen semantics
            c = case()
            c['devices']['OtherWeather'] = {'category': ['WeatherProvider'], 'tags': ['Other', 'WeatherProvider']}
            c['joi_block']['script'] = c['joi_block']['script'].replace('(#WeatherProvider)', '(#Other #WeatherProvider)')
            result = gate(c)
            self.assertEqual(result.verdict, 'DIVERGE', result.notes)
            self.assertTrue(result.confirmed)

    def test_query_arguments_are_part_of_source_identity(self):
        c = case('C01_018')
        # Explicit conversion fixture; the catalog query now returns non-null text.
        c['ir']['timeline'][-1]['args']['Text'] = 'menu: $GetMenu'
        c['joi_block']['script'] = c['joi_block']['script'].replace('speaker_speak(GetMenu)', 'speaker_speak("menu: " + GetMenu)')
        self.assertEqual(gate(c).verdict, 'EQUIV-BOUNDED')
        c['joi_block']['script'] = c['joi_block']['script'].replace('301동식당', '302동식당')
        result = gate(c)
        self.assertEqual(result.verdict, 'DIVERGE', result.notes)
        self.assertTrue(result.confirmed)

    def test_query_and_property_are_different_sources(self):
        c = case('C01_017')
        c['joi_block']['script'] = c['joi_block']['script'].replace(
            'menuProvider_todayMenu', 'menuProvider_getMenu("today")')
        result = gate(c)
        self.assertEqual(result.verdict, 'DIVERGE', result.notes)
        self.assertTrue(result.confirmed)

    def test_read_epoch_respects_100ms_hold_and_exact_deadlines(self):
        for ms, expected in ((50, 'EQUIV-BOUNDED'), (99, 'EQUIV-BOUNDED'),
                             (100, 'DIVERGE'), (150, 'DIVERGE')):
            with self.subTest(ms=ms):
                result = gate(delayed(case(), ms, fresh=True))
                self.assertEqual(result.verdict, expected, result.notes)
                if expected == 'DIVERGE':
                    self.assertTrue(result.confirmed)

    def test_captured_value_survives_delay_without_becoming_fresh(self):
        result = gate(delayed(case(), 150))
        self.assertEqual(result.verdict, 'EQUIV-BOUNDED', result.notes)
        event = result.product.symbolic_certificate['events'][-1]
        self.assertEqual(event['offset_ms'], 150)
        self.assertIn('"epoch": 0', json.dumps(event))

    def test_symbol_epoch_and_replay_use_custom_large_time_origin(self):
        c = delayed(case(), 150, fresh=True)
        p = prepared(c)
        from explorer.verification.product import replay_divergence
        for t0 in (0, 10**16 + 17):
            result = timed_product(p.ir_runner, p.code_runner, horizon_ms=150, t0_ms=t0)
            self.assertEqual(result.verdict, 'DIVERGE', result.notes)
            self.assertEqual(result.divergences[0].t0_ms, t0)
            self.assertTrue(replay_divergence(p.ir_runner, p.code_runner, result.divergences[0]).confirmed)

    def test_timing_difference_at_inclusive_horizon_is_observable(self):
        c = delayed(case(), 100)
        c['joi_block']['script'] = c['joi_block']['script'].replace('100 MSEC', '101 MSEC')
        c['horizon_ms'] = 99
        self.assertEqual(gate(c).verdict, 'EQUIV-BOUNDED')
        c['horizon_ms'] = 100
        result = gate(c)
        self.assertEqual(result.verdict, 'DIVERGE', result.notes)
        self.assertTrue(result.confirmed)

    def test_fanout_order_commutes_but_target_omission_does_not(self):
        with selector_binding(False):  # selector correctness: frozen semantics
            c = case()
            c['binding']['Speaker'].reverse()
            self.assertEqual(gate(c).verdict, 'EQUIV-BOUNDED')
            c['joi_block']['script'] = c['joi_block']['script'].replace('all(#Speaker)', '(#LivingRoom #Speaker)')
            self.assertTrue(gate(c).confirmed)

    def test_duplicate_calls_remain_observable(self):
        c = case()
        c['joi_block']['script'] += '\n' + c['joi_block']['script'].split('\n')[-1]
        result = gate(c)
        self.assertEqual(result.verdict, 'DIVERGE', result.notes)
        self.assertTrue(result.confirmed)

    def test_string_normalization_preserves_literal_and_variable_order(self):
        c = case()
        c['joi_block']['script'] = c['joi_block']['script'].replace(
            '"The outdoor temperature is " + TemperatureWeather',
            '"The outdoor " + ("temperature is " + TemperatureWeather)')
        self.assertEqual(gate(c).verdict, 'EQUIV-BOUNDED')
        c['joi_block']['script'] = c['joi_block']['script'].replace(
            '"temperature is " + TemperatureWeather', 'TemperatureWeather + "temperature is "')
        result = gate(c)
        self.assertEqual(result.verdict, 'DIVERGE', result.notes)
        self.assertTrue(result.confirmed)

    def test_lift_commutes_with_concrete_evaluation_including_missing_and_representations(self):
        a = InputSymbol('a', 0, 'DOUBLE', True)
        b = InputSymbol('b', 1, 'STRING', True)
        # Independent source ASTs, not a test that just calls the same helper.
        joi = e.BinaryOp('+', e.BinaryOp('+', e.Lit('v='), e.VarRef('a')), e.VarRef('b'))
        ir = ('bin', '+', ('bin', '+', ('lit', 'v='), ('var', 'a')), ('var', 'b'))
        sj = e.evaluate(joi, e.EvalContext({}, {'a': a, 'b': b}, {}))
        si = eval_cond(ir, {'a': a, 'b': b}, {})
        self.assertEqual(si, sj)
        for x, y in itertools.product([None, -470.0, 10000.0, 0, 0.0, -0.0, 1, 1.0, 0.1],
                                      [None, '', 'a', '메뉴', '\0', '1.0']):
            expected = ('v=' + ('' if x is None else str(x))) + ('' if y is None else str(y))
            self.assertEqual(substitute(si, {a: x, b: y}), expected)
            self.assertEqual(eval_cond(ir, {'a': x, 'b': y}, {}), expected)
            self.assertEqual(e.evaluate(joi, e.EvalContext({}, {'a': x, 'b': y}, {})), expected)
        self.assertNotEqual(substitute(si, {a: 1, b: ''}), substitute(si, {a: 1.0, b: ''}))
        self.assertNotEqual(substitute(si, {a: 0.0, b: ''}), substitute(si, {a: -0.0, b: ''}))

    def test_raw_nullable_string_is_not_certified_as_valid_action(self):
        c = case('C01_017')
        c['ir']['timeline'][-1]['args']['Text'] = '$TodayMenu'
        c['joi_block']['script'] = c['joi_block']['script'].split('\n')[0] + '\nall(#Speaker).speaker_speak(TodayMenu)'
        result = gate(c)
        self.assertEqual(result.verdict, 'REFUSED')
        self.assertIn('missing/None', str(result.notes))
        p = prepared(c)
        key = next(iter(symbolic_specs(p.ir_runner, p.code_runner)))
        self.assertEqual(gate(c, input_domains={key: ['menu']}).verdict, 'EQUIV-BOUNDED')
        self.assertEqual(gate(c, input_domains={key: [None]}).verdict, 'REFUSED')

    def test_menu_return_contract_excludes_none_in_all_input_paths(self):
        from explorer.verification.service_model import ServiceModel
        from explorer.verification.symbolic import witness_values
        c = case('C01_018')
        p = prepared(c)
        specs = symbolic_specs(p.ir_runner, p.code_runner)
        key, spec = next(iter(specs.items()))
        self.assertEqual(spec['type'], 'STRING')
        self.assertFalse(spec['nullable'])
        self.assertNotIn(None, ServiceModel.representatives(spec, [('==', '')]))
        self.assertNotIn(None, witness_values(spec))
        self.assertEqual(gate(c, input_domains={key: ['', '점심', 'None']}).verdict, 'EQUIV-BOUNDED')
        self.assertEqual(gate(c, input_domains={key: [None]}).verdict, 'REFUSED')
        for runner in (p.ir_runner, p.code_runner):
            for world in ({}, {key: None}, {key: 1}):
                with self.assertRaises(Unsupported):
                    runner.step({}, {}, world, 0, first_tick=True)
            self.assertTrue(runner.step({}, {}, {key: ''}, 0, first_tick=True).actions)

    def test_raw_menu_constant_and_wrong_query_have_valid_string_witnesses(self):
        for replacement in ('"fixed menu"', '(#MenuProvider).menuProvider_getMenu("different")'):
            c = case('C01_018')
            c['joi_block']['script'] = c['joi_block']['script'].replace('speaker_speak(GetMenu)',
                'speaker_speak(' + replacement + ')')
            result = gate(c)
            self.assertEqual(result.verdict, 'DIVERGE', result.notes)
            self.assertTrue(result.confirmed)
            for divergence in result.product.divergences:
                self.assertTrue(all(isinstance(v, str) for v in divergence.input_.values()))

    def test_symbolic_to_enum_or_nonstring_action_is_not_silently_accepted(self):
        from explorer.verification.service_model import ServiceModel
        value = text_join(['value=', InputSymbol('a', 0, 'DOUBLE', True)])
        for spec in ({'type': 'INTEGER'}, {'type': 'STRING', 'members': ['a']}):
            with self.assertRaises(Unsupported):
                ServiceModel.validate_value(value, spec, 'test', missing=False)

    def test_symbolic_numeric_addition_and_implicit_stringification_fail_closed(self):
        a = InputSymbol('a', 0, 'STRING', True)
        with self.assertRaises(Unsupported):
            e.evaluate(e.BinaryOp('+', e.Lit(a), e.Lit(a)), e.EvalContext({}, {}, {}))
        with self.assertRaises(Unsupported):
            str(a)
        with self.assertRaises(Unsupported):
            bool(a)

    def test_arithmetic_uses_smt_but_copy_only_control_keeps_old_policy(self):
        for suffix in (' * 2', ''):
            c = case()
            if suffix:
                c['joi_block']['script'] = c['joi_block']['script'].replace('TemperatureWeather)', '(TemperatureWeather * 2))')
            else:
                read, action = c['joi_block']['script'].split('\n')
                c['joi_block']['script'] = read + '\nif (TemperatureWeather > 0) {\n' + action + '\n}'
            result = gate(c)
            self.assertEqual(result.verdict, 'DIVERGE' if suffix else 'REFUSED')
            if suffix:
                self.assertTrue(result.confirmed)
                self.assertEqual(result.product.symbolic_certificate['schema'], 'smt-linear-trace-v1')

    def test_periodic_schedule_is_not_certified_by_one_shot_path(self):
        c = case()
        c['joi_block']['period'] = 1000
        self.assertEqual(gate(c).verdict, 'REFUSED')

    def test_explicit_domains_retain_concrete_bfs_and_scope(self):
        c = case()
        p = prepared(c)
        key = next(iter(symbolic_specs(p.ir_runner, p.code_runner)))
        result = timed_product(p.ir_runner, p.code_runner,
                               input_domains={key: [None, 1, 1.0, -0.0, 0.0]}, horizon_ms=100)
        self.assertEqual(result.claim, 'EQUIV-BOUNDED')
        self.assertIsNone(result.symbolic_certificate)
        self.assertEqual(result.n_steps, 10)

    def test_state_transition_and_witness_caps_do_not_certify_equality(self):
        c = delayed(case(), 150)
        p = prepared(c)
        for caps in ({'max_states': 1}, {'max_transitions': 1}):
            result = timed_product(p.ir_runner, p.code_runner, horizon_ms=200, **caps)
            self.assertEqual(result.verdict, 'UNKNOWN')
            self.assertFalse(result.closed)
        c = case()
        # Baseline T=0 agrees, but witness cap prevents trying another value.
        c['joi_block']['script'] = c['joi_block']['script'].replace('TemperatureWeather)', '0)')
        p = prepared(c)
        result = timed_product(p.ir_runner, p.code_runner, horizon_ms=0, max_input_combinations=1)
        self.assertEqual(result.verdict, 'UNKNOWN')
        self.assertFalse(result.closed)

    def test_failed_replay_never_certifies_divergence(self):
        c = case()
        c['joi_block']['script'] = c['joi_block']['script'].replace('TemperatureWeather)', '31)')
        p = prepared(c)
        from explorer.verification.product import ReplayResult
        with patch('explorer.verification.symbolic.replay_divergence', return_value=ReplayResult(False)):
            result = timed_product(p.ir_runner, p.code_runner, horizon_ms=0)
        self.assertEqual(result.verdict, 'UNKNOWN')
        self.assertFalse(result.closed)

    def test_development_evaluation_distinguishes_symbolic_certificate_from_oracle_agreement(self):
        result = evaluate_case(case())
        self.assertEqual(result['status'], 'SYMBOLIC_CERTIFIED', result)
        self.assertEqual(result['exact']['verdict'], 'NOT_APPLICABLE')
        self.assertEqual(result['explorer']['claim'], 'EQUIV-BOUNDED')

    def test_full_runners_concretize_symbolic_captured_history(self):
        from dataclasses import replace
        from explorer.verification.observation import actions_observation
        c = delayed(case(), 150)
        p = prepared(c)
        key = next(iter(symbolic_specs(p.ir_runner, p.code_runner)))
        s0 = InputSymbol(key, 0, 'DOUBLE', True)
        s1 = InputSymbol(key, 1, 'DOUBLE', True)
        values = [None, -470.0, 10000.0, 0, 0.0, -0.0, 1, 1.0, 0.1]
        for runner in (p.ir_runner, p.code_runner):
            sv, sg = {}, {}
            symbolic_actions = []
            for now, symbol in ((0, s0), (100, s1), (150, s1)):
                res = runner.step(sv, sg, {key: symbol}, now, first_tick=now == 0)
                symbolic_actions.append(res.actions)
                sv, sg = res.vars, res.gv
            # 81 histories per runner; representations and missing kept distinct.
            for initial, later in itertools.product(values, repeat=2):
                cv, cg = {}, {}
                for index, (now, value) in enumerate(((0, initial), (100, later), (150, later))):
                    res = runner.step(cv, cg, {key: value}, now, first_tick=now == 0)
                    materialized = [replace(a, args=tuple(substitute(v, {s0: initial, s1: later})
                                                          for v in a.args))
                                    for a in symbolic_actions[index]]
                    self.assertEqual(actions_observation(res.actions), actions_observation(materialized))
                    cv, cg = res.vars, res.gv

    def test_frozen_workers_keep_symbolic_results_separate_from_exact_oracle(self):
        c = case()
        payload = {k: c[k] for k in ('ir', 'binding', 'devices', 'joi_block')}
        job = {'limits': {'address_space_mib': 768}, 'caps': {},
               'case': {'payload': payload, 'verification_method': 'symbolic-value-flow-v1',
                        'model': {'input_domains': None, 'horizon_ms': 0}}}
        for engine, expected in (('explorer', 'EQUIV'), ('exact', 'NOT_APPLICABLE')):
            process = subprocess.run([sys.executable, '-m', 'explorer.eval.frozen_contract',
                                      'worker', '--engine', engine], input=json.dumps(job),
                                     text=True, capture_output=True, cwd=ROOT, check=True)
            result = json.loads(process.stdout)
            self.assertEqual(result['status'], expected, result)
            if engine == 'explorer':
                self.assertEqual(result['claim'], 'EQUIV-BOUNDED')


if __name__ == '__main__':
    unittest.main()
