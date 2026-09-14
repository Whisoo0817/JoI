"""Hand-derived frontend/runner witnesses; no shared search oracle as truth.

Run: python -m explorer.tests.test_frontend_conformance
"""
import copy
import itertools
import math
import unittest

from explorer.verification.gate import reground_ir
from explorer.tests.synthetic_gate import gate_pair, prepare_pair
from explorer.runtime.ground import Dev, ground
from explorer.runtime.interp import Unsupported, parse, step
from explorer.runtime.ir_step import IrRunner, default_to_key, eval_cond, parse_cond
from explorer.runtime.pause import PauseRunner
from explorer.verification.product import check_supported_pair
from explorer.tests.test_contract import call, timeline, trace
from explorer.verification.gate import selector_binding  # binding decision 2026-09-14


DEVICES = {
    'a': {'category': ['Sensor'], 'tags': ['Sensor', 'A']},
    'b': {'category': ['Sensor'], 'tags': ['Sensor', 'B']},
    'lamp': {'category': ['Switch'], 'tags': ['Switch']},
}
INVENTORY = [Dev('a', 'Sensor', tags=('A',)), Dev('b', 'Sensor', tags=('B',)),
             Dev('lamp', 'Switch')]


class FrontendConformance(unittest.TestCase):
    def test_not_precedence_and_boolean_composition(self):
        for value, enabled in itertools.product((None, -1, 0, 10, 11), (False, True)):
            src = 'not Sensor.Value > 10 and Sensor.Enabled == true'
            expected = not (value is not None and value > 10) and enabled
            got_ir = eval_cond(parse_cond(src, default_to_key), {},
                               {'sensor.value': value, 'sensor.enabled': enabled})
            got_joi = step(parse('v = not (#Sensor).sensor_value > 10 and (#Sensor).sensor_enabled == true'),
                           {}, {}, {'sensor.value': value, 'sensor.enabled': enabled}, 0).vars['v']
            self.assertEqual((got_ir, got_joi), (expected, expected))

    def test_any_all_and_exists_compare_every_matching_device(self):
        forms = [('any(#Sensor).sensor_value > 10', any),
                 ('10 < any(#Sensor).sensor_value', any),
                 ('all(#Sensor).sensor_value >| 10', any),
                 ('all(#Sensor).sensor_value > 10', all)]
        for (condition, quant), values in itertools.product(forms, itertools.product((0, 20), repeat=2)):
            for inventory in (INVENTORY, list(reversed(INVENTORY))):
                stmts, _ = ground(parse(f'if ({condition}) {{ (#Switch).switch_on() }}'),
                                  inventory, pick=lambda matches: matches[0])
                result = step(stmts, {}, {}, {'a.value': values[0], 'b.value': values[1]}, 0)
                self.assertEqual(len(result.actions), int(quant(v > 10 for v in values)))

    def test_any_mutated_to_first_device_has_gate_counterexample(self):
        with selector_binding(False):  # selector correctness: frozen semantics
            ir = timeline({'op': 'if', 'cond': 'Sensor.Value > 10', 'then': [call()]})
            binding = {'Sensor': {'any': ['a', 'b']}, 'Switch': ['lamp']}
            good = {'script': 'if (any(#Sensor).sensor_value > 10) { (#Switch).switch_on() }', 'period': 0}
            self.assertEqual(gate_pair(ir, binding, DEVICES, good, horizon_ms=0).verdict, 'EQUIV-BOUNDED')
            bad = {**good, 'script': good['script'].replace('any(#Sensor)', '(#Sensor #A)')}
            result = gate_pair(ir, binding, DEVICES, bad, horizon_ms=0)
            self.assertEqual(result.verdict, 'DIVERGE')
            self.assertTrue(result.confirmed)

    def test_queries_preserve_two_device_identities_and_parameter_types(self):
        ir = timeline(
            {'op': 'call', 'target': 'Sensor.Query', 'args': {'p': 1.0}, 'var': 'x'},
            {'op': 'call', 'target': 'Sensor.Query', 'args': {'p': 1.0}, 'var': 'y'},
            {'op': 'if', 'cond': '$x > 10 and $y < 10', 'then': [call()]})
        binding = {'Sensor': ['a'], 'Sensor#2': ['b'], 'Switch': ['lamp']}
        source = ('x = (#A #Sensor).sensor_query(1.0)\n'
                  'y = (#B #Sensor).sensor_query(1.0)\n'
                  'if (x > 10 and y < 10) { (#Switch).switch_on() }')
        block = {'script': source, 'period': 0}
        pair = prepare_pair(ir, binding, DEVICES, block)
        for runner in (pair.ir_runner, pair.code_runner):
            self.assertEqual(set(runner.axes.cells), {'a.query(1.0)', 'b.query(1.0)'})
            self.assertEqual(trace(runner, [(0, {'a.query(1.0)': 20, 'b.query(1.0)': 0})]),
                             [(0, 'on', ())])
        bad = {**block, 'script': source.replace('#B #Sensor', '#A #Sensor')}
        result = gate_pair(ir, binding, DEVICES, bad, horizon_ms=0)
        self.assertEqual(result.verdict, 'DIVERGE')
        self.assertTrue(result.confirmed)

    def test_unused_query_result_never_becomes_an_action(self):
        ir = IrRunner(timeline({'op': 'call', 'target': 'Sensor.Query', 'var': 'unused'}))
        code = PauseRunner('unused = (#Sensor).sensor_query()', False)
        for runner in (ir, code):
            self.assertEqual(trace(runner, [(0, {'sensor.query': 12})]), [])

    def test_dollar_service_reads_are_grounded(self):
        rewritten, names, _, _ = reground_ir(
            timeline({'op': 'if', 'cond': '$Sensor.Value > 10', 'then': [call()]}),
            {'Sensor': ['a'], 'Switch': ['lamp']})
        self.assertEqual(rewritten['timeline'][1]['cond'], 'a.Value > 10')
        self.assertIn('a.value', names.values())

    def test_argument_grounding_preserves_literal_text_and_template_prefix(self):
        for literal in ('Sensor.Value', 'Hello.World'):
            rewritten, _, _, _ = reground_ir(timeline({'op': 'call', 'target': 'Switch.Say',
                'args': {'text': literal}}), {'Switch': ['lamp']})
            self.assertEqual(rewritten['timeline'][1]['args']['text'], literal)
        rewritten, _, _, _ = reground_ir(timeline({'op': 'call', 'target': 'Switch.Say',
            'args': {'text': 'Sensor.Value is $Sensor.Value'}}),
            {'Switch': ['lamp'], 'Sensor': ['a']})
        self.assertEqual(rewritten['timeline'][1]['args']['text'], 'Sensor.Value is $a.Value')

    def test_missing_offline_or_malformed_binding_is_refused(self):
        blocks = [({}, DEVICES), ({'Switch': []}, DEVICES),
                  ({'Switch': ['ghost']}, DEVICES),
                  ({'Switch': ['lamp']}, {**DEVICES, 'lamp': {**DEVICES['lamp'], 'online': False}}),
                  ({'Switch': {'xor': ['lamp']}}, DEVICES),
                  ({'Switch': {'all': ['lamp'], 'any': ['lamp']}}, DEVICES)]
        for binding, devices in blocks:
            with self.subTest(binding=binding):
                result = gate_pair(timeline(call()), binding, devices,
                                   {'script': '(#Switch).switch_on()', 'period': 0}, horizon_ms=0)
                self.assertEqual(result.verdict, 'REFUSED')

    def test_floating_candidate_selector_is_refused(self):
        with selector_binding(False):  # selector correctness: frozen semantics
            result = gate_pair(timeline(call()), {'Switch': ['lamp']}, DEVICES,
                               {'script': '(#Ghost).switch_on()', 'period': 0}, horizon_ms=0)
            self.assertEqual(result.verdict, 'REFUSED')
            self.assertIn('unresolved selectors', str(result.notes))

    def test_binding_slot_count_must_match_occurrences(self):
        binding = {'Switch': ['lamp'], 'Switch#2': ['lamp']}
        for ir in (timeline(call()), timeline(call(), call(), call())):
            with self.assertRaises(Unsupported):
                reground_ir(ir, binding)
        reground_ir(timeline(call(), call()), binding)
        reground_ir(timeline(call(), call(), call()), {'Switch': ['lamp']})
        _, _, _, notes = reground_ir(timeline(), {'Switch': ['lamp']})
        self.assertEqual(notes, ['unused binding service: Switch'])

    def test_binding_slot_suffix_not_json_key_order_selects_device(self):
        ir = timeline(call(), call('Off'))
        a = reground_ir(ir, {'Switch': ['a'], 'Switch#2': ['b']})
        b = reground_ir(ir, {'Switch#2': ['b'], 'Switch': ['a']})
        self.assertEqual(a, b)
        with self.assertRaises(Unsupported):
            reground_ir(ir, {'Switch': ['a'], 'Switch#3': ['b']})

    def test_parser_rejects_partial_selectors_and_incomplete_conditions(self):
        for source in ('(#Switch garbage).switch_on()', '(#Switch-broken).switch_on()',
                       '(#Switch).switch_on(', 'if (true) {', 'x ='):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse(source)
        for source in ('', '(', 'true and', 'true and )', '(true', 'abs true', 'min(1)'):
            with self.subTest(source=source), self.assertRaises(Unsupported):
                parse_cond(source, default_to_key)

    def test_literal_text_is_not_interpreted_as_a_selector(self):
        literal = 'any(#Sensor).Value'
        self.assertEqual(eval_cond(parse_cond('"' + literal + '"', default_to_key), {}, {}), literal)
        with self.assertRaises(ValueError):
            parse(r'x = "a\nb"')

    def test_negative_float_zero_literal_preserves_its_sign(self):
        value = eval_cond(parse_cond('-0.0', default_to_key), {}, {})
        self.assertIs(type(value), float)
        self.assertEqual(math.copysign(1, value), -1)

    def test_ambiguous_combined_wait_and_multidevice_query_are_refused(self):
        with self.assertRaisesRegex(Unsupported, 'edge and sustain'):
            IrRunner(timeline({'op': 'wait', 'cond': 'true', 'edge': 'rising', 'for': '1 SEC'}))
        with self.assertRaisesRegex(Unsupported, 'exactly one bound device'):
            IrRunner(timeline({'op': 'call', 'target': 'Sensor.Query', 'var': 'v'}),
                     bind={('sensor', 'query'): [[('a',), ('b',)]]})

    def test_fractional_negative_and_boolean_periods_are_refused(self):
        for period in (1.5, -1, True, '1.5'):
            result = gate_pair(timeline(call()), {'Switch': ['lamp']}, DEVICES,
                               {'script': '(#Switch).switch_on()', 'period': period}, horizon_ms=0)
            self.assertEqual(result.verdict, 'REFUSED')

    def test_nested_cycle_counter_restarts_on_each_entry(self):
        runner = IrRunner(timeline({'op': 'cycle', 'period': '100 MSEC', 'count': 2,
            'body': [{'op': 'cycle', 'period': '100 MSEC', 'count': 2, 'body': [call()]}]}))
        self.assertEqual(trace(runner, [(t, {}) for t in range(0, 501, 100)], t0=0),
                         [(0, 'on', ()), (100, 'on', ()), (200, 'on', ()), (300, 'on', ())])

    def test_nested_if_resumes_selected_branch_and_then_outer_continuation(self):
        code = ('if ((#Sensor).sensor_value > 10) { delay(150 MSEC)\n'
                '(#Switch).switch_on() } else { (#Switch).switch_off() }\n'
                '(#Switch).switch_finish()')
        runner = PauseRunner(code, False)
        self.assertEqual(trace(runner, [(0, {'sensor.value': 20}), (100, {'sensor.value': 0}),
                                        (150, {'sensor.value': 0})]),
                         [(150, 'on', ()), (150, 'finish', ())])

    def test_foreach_preserves_order_and_refuses_unproven_control_effects(self):
        stmts, _ = ground(parse('for (v : all(#Sensor).sensor_value) { (#Switch).switch_say(v) }'), INVENTORY)
        result = step(stmts, {}, {}, {'a.value': 1, 'b.value': 2}, 0)
        self.assertEqual([a.args for a in result.actions], [(1,), (2,)])
        for body in ('break', 'delay(1 SEC)', 'v = 3', 'wait until(true)',
                     'for (w : all(#Sensor).sensor_value) { (#Switch).switch_say(v) }'):
            with self.assertRaises(Unsupported):
                ground(parse(f'for (v : all(#Sensor).sensor_value) {{ {body} }}'), INVENTORY)

    def test_gv_writes_in_conditions_are_refused(self):
        runner = PauseRunner('if ((#GlobalVariable).globalVariable_setBool("x", true)) { delay(1 SEC) }', False)
        with self.assertRaisesRegex(Unsupported, 'GV writes in expressions'):
            check_supported_pair(runner, runner)

    def test_reaction_is_deterministic_and_does_not_mutate_arguments(self):
        runners = [IrRunner(timeline({'op': 'delay', 'duration': '150 MSEC'}, call())),
                   PauseRunner('delay(150 MSEC)\n(#Switch).switch_on()', False)]
        for runner in runners:
            state, gv, inputs = {}, {'kept': 1}, {'sensor.value': 20}
            saved = copy.deepcopy((state, gv, inputs))
            a = runner.step(state, gv, inputs, 0, True)
            b = runner.step(state, gv, inputs, 0, True)
            self.assertEqual(a, b)
            self.assertEqual((state, gv, inputs), saved)
            saved_next = copy.deepcopy(a.vars)
            self.assertEqual(runner.step(a.vars, gv, inputs, 150), runner.step(a.vars, gv, inputs, 150))
            self.assertEqual(a.vars, saved_next)

    def test_invalid_program_fuel_never_returns_success(self):
        runner = IrRunner(timeline({'op': 'cycle', 'body': []}))
        with self.assertRaisesRegex(Unsupported, 'fuel exhausted'):
            runner.step({}, {}, {}, 0)


if __name__ == '__main__':
    unittest.main()
