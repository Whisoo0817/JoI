"""Real-catalog witnesses and independent full-domain partition checks."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from explorer.verification.gate import gate_pair, prepare_pair, pair_input_domains
from explorer.runtime.expr import Lit
from explorer.verification.input_coverage import predicate_value
from explorer.runtime.interp import Unsupported
from explorer.verification.service_model import ServiceModel, REVIEWED_CATALOG_SHA256
from explorer.verification.state_key import freeze_state


DEVICES = {name: {'category': [service], 'tags': [service]}
           for name, service in [('lamp', 'Switch'), ('temp', 'TemperatureSensor'),
                                 ('weather', 'WeatherProvider'), ('light', 'Light'),
                                 ('speaker', 'Speaker')]}


def timeline(*steps):
    return {'timeline': [{'op': 'start_at', 'anchor': 'now'}, *steps]}


def call(target='Switch.On', args=None, **kw):
    return {'op': 'call', 'target': target, 'args': args or {}, **kw}


def run(ir, script, binding, **kw):
    return gate_pair(ir, binding, DEVICES, {'script': script, 'period': 0}, horizon_ms=0, **kw)


class ServiceModelTests(unittest.TestCase):
    def test_real_catalog_default_and_unknown_service_refusal(self):
        good = run(timeline(call()), '(#Switch).switch_on()', {'Switch': ['lamp']})
        self.assertEqual(good.verdict, 'EQUIV-BOUNDED')
        self.assertIn(REVIEWED_CATALOG_SHA256, str(good.notes))
        bad = run(timeline(call('Switch.Nonexistent')), '(#Switch).switch_nonexistent()', {'Switch': ['lamp']})
        self.assertEqual(bad.verdict, 'REFUSED')
        self.assertIn('unknown catalog', str(bad.notes))

    def test_named_arguments_ordered_after_binding_walk(self):
        ir = timeline(call('Light.MoveToColor', {'TransitionTime': 3.0, 'ColorY': 0.2, 'ColorX': 0.1}))
        pair = prepare_pair(ir, {'Light': ['light']}, DEVICES,
                            {'script': '(#Light).light_moveToColor(0.1, 0.2, 3.0)'})
        for runner in (pair.ir_runner, pair.code_runner):
            self.assertEqual(runner.step({}, {}, {}, 0, first_tick=True).actions[0].args, (0.1, 0.2, 3.0))
        self.assertEqual(list(ir['timeline'][1]['args']), ['TransitionTime', 'ColorY', 'ColorX'])

    def test_arg_reordering_does_not_rebind_repeated_reads(self):
        devices = {**DEVICES, 'temp2': {'category': ['TemperatureSensor'], 'tags': ['TemperatureSensor', 'Second']}}
        ir = timeline(call('Light.MoveToColor', {'ColorY': '$TemperatureSensor.Temperature',
              'ColorX': '$TemperatureSensor.Temperature', 'TransitionTime': 0.0}))
        pair = prepare_pair(ir, {'Light': ['light'], 'TemperatureSensor': ['temp'],
                            'TemperatureSensor#2': ['temp2']}, devices,
                            {'script': '(#Light).light_moveToColor(0.2, 0.1, 0.0)'})
        action = pair.ir_runner.step({}, {}, {'temp.temperature': 0.1, 'temp2.temperature': 0.2}, 0, first_tick=True).actions[0]
        self.assertEqual(action.args, (0.2, 0.1, 0.0))

    def test_argument_names_count_type_and_bound(self):
        for args in ({'Brightness': 3.0}, {'Brightness': 3.0, 'Rate': 2.0, 'Extra': 1},
                     {'Brightness': 'three', 'Rate': 2.0}, {'Brightness': 101.0, 'Rate': 2.0},
                     {'Brightness': 3.0, 'brightness': 3.0, 'Rate': 2.0}):
            result = run(timeline(call('Light.MoveToBrightness', args)),
                         '(#Light).light_moveToBrightness(3.0, 2.0)', {'Light': ['light']})
            self.assertEqual(result.verdict, 'REFUSED', args)

    def test_case_and_prefix_aliases(self):
        result = run(timeline(call('sWiTcH.switch_ON')), '(#Switch).switch_on()', {'sWiTcH': ['lamp']})
        self.assertEqual(result.verdict, 'EQUIV-BOUNDED', result.notes)

    def test_capability_checked_for_ir_and_joi(self):
        for binding, script in [({'Switch': ['light']}, '(#Switch).switch_on()'),
                                ({'Switch': ['lamp']}, '(#Light).switch_on()')]:
            result = run(timeline(call()), script, binding)
            self.assertEqual(result.verdict, 'REFUSED')
            self.assertIn('capability', str(result.notes))

    def test_effectful_return_assignment_is_never_silent(self):
        for target, args, source, bind in [
                ('Switch.Toggle', {}, '(#Switch).switch_toggle()', {'Switch': ['lamp']}),
                ('Speaker.SetVolume', {'Volume': 30}, '(#Speaker).speaker_setVolume(30)', {'Speaker': ['speaker']})]:
            result = run(timeline(call(target, args, var='x')), 'x = ' + source, bind)
            self.assertEqual(result.verdict, 'REFUSED')
            self.assertIn('silent input', str(result.notes))
            # As an ACTION, the same returning function is preserved.
            result = run(timeline(call(target, args)), source, bind)
            self.assertEqual(result.verdict, 'EQUIV-BOUNDED', result.notes)

    def test_effectful_return_assignment_on_candidate_alone_refused(self):
        result = run(timeline(call('Switch.Toggle')), 'x = (#Switch).switch_toggle()', {'Switch': ['lamp']})
        self.assertEqual(result.verdict, 'REFUSED')

    def test_forecast_string_domain_and_weather_mutation(self):
        ir = timeline(call('WeatherProvider.Forecast', {'Hour': 3}, var='w'),
                      {'op': 'if', 'cond': '$w == "rain"', 'then': [call()]})
        script = 'w = (#WeatherProvider).weatherProvider_forecast(3)\nif (w == "rain") { (#Switch).switch_on() }'
        binding = {'WeatherProvider': ['weather'], 'Switch': ['lamp']}
        pair = prepare_pair(ir, binding, DEVICES, {'script': script})
        domain = pair_input_domains(pair)['weather.forecast(3)']
        self.assertIn('rain', domain)
        self.assertTrue(all(v is None or isinstance(v, str) for v in domain))
        self.assertEqual(run(ir, script, binding).verdict, 'EQUIV-BOUNDED')
        mutated = run(ir, script.replace('== "rain"', '== "clear"'), binding)
        self.assertEqual(mutated.verdict, 'DIVERGE')
        self.assertTrue(mutated.confirmed)

    def test_forecast_arguments_and_declared_return_domain_validated(self):
        for hour in (121, 3.0, True):
            result = run(timeline(call('WeatherProvider.Forecast', {'Hour': hour}, var='w')),
                         'w = (#WeatherProvider).weatherProvider_forecast(3)', {'WeatherProvider': ['weather']})
            self.assertEqual(result.verdict, 'REFUSED')
        ir = timeline(call('WeatherProvider.Forecast', {'Hour': 3}, var='w'))
        for values in ([3], ['made-up-weather']):
            result = run(ir, 'w = (#WeatherProvider).weatherProvider_forecast(3)',
                         {'WeatherProvider': ['weather']}, input_domains={'weather.forecast(3)': values})
            self.assertEqual(result.verdict, 'REFUSED')

    def test_function_without_parentheses_is_not_property(self):
        result = run(timeline(), 'x = (#WeatherProvider).weatherProvider_forecast', {})
        self.assertEqual(result.verdict, 'REFUSED')

    def test_observable_enum_return_enumerates_every_value(self):
        model = ServiceModel(DEVICES)
        spec = model.resolve('WeatherProvider', 'Forecast', 'function')['return_spec']
        got = model.representatives(spec, [], exact=True)
        self.assertEqual(set(got), {None, *spec['members']})

    def test_observable_forecast_string_has_complete_finite_domain(self):
        ir = timeline(call('WeatherProvider.Forecast', {'Hour': 3}, var='w'),
                      {'op': 'if', 'cond': '$w == "rain"',
                       'then': [call('Speaker.Speak', {'Text': '$w'})]})
        script = ('w = (#WeatherProvider).weatherProvider_forecast(3)\n'
                  'if (w == "rain") { (#Speaker).speaker_speak(w) }')
        result = run(ir, script, {'WeatherProvider': ['weather'], 'Speaker': ['speaker']})
        self.assertEqual(result.verdict, 'EQUIV-BOUNDED', result.notes)

    def test_template_placeholders_inside_quotes_still_normalize(self):
        model = ServiceModel(DEVICES)
        ir, _ = model.normalize_ir(timeline(call('Speaker.Speak',
            {'Text': "weather says '$weatherprovider.weather'"})),
            {'WeatherProvider': ['weather'], 'Speaker': ['speaker']})
        self.assertEqual(ir['timeline'][1]['args']['Text'], "weather says '$WeatherProvider.Weather'")

    def test_partitions_cover_full_catalog_domains(self):
        model = ServiceModel(DEVICES)
        for spec, full in [({'type': 'INTEGER', 'bound': [-4, 7]}, [None, *range(-4, 8)]),
                           ({'type': 'DOUBLE', 'bound': [-4, 7]}, [None, *[v / 10 for v in range(-40, 71)]]),
                           ({'type': 'BOOL'}, [False, True]),
                           ({'type': 'BOOLEAN'}, [False, True]),
                           ({'type': 'ENUM', 'members': ['rain', 'clear', 'snow']}, [None, 'rain', 'clear', 'snow'])]:
            choices = [('truth', None), ('==', None), ('==', 0), ('!=', 3), ('==', 'rain')]
            if spec['type'] in ('INTEGER', 'DOUBLE'):
                choices += [('>', 0.05), ('<', 1.1), ('<=', 6.95), ('>=', -3.9)]
            for first in choices:
                for second in choices:
                    predicates = [first, second]
                    reps = model.representatives(spec, predicates)
                    vector = lambda value: tuple(predicate_value(op, value, c) for op, c in predicates)
                    self.assertEqual({vector(v) for v in full}, {vector(v) for v in reps}, (spec, predicates, reps))
                    for value in reps:
                        model.validate_value(value, spec, 'test')

    def test_zero_representative_has_catalog_type(self):
        reps = ServiceModel.representatives({'type': 'INTEGER', 'bound': [0, 100]}, [('==', 0), ('==', None)])
        self.assertTrue(any(type(v) is int and v == 0 for v in reps))
        self.assertFalse(any(type(v) is bool for v in reps))

    def test_exact_double_retains_signed_zero(self):
        got = ServiceModel.representatives({'type': 'DOUBLE', 'bound': [0, 0.1]}, [], True)
        self.assertIn(freeze_state(-0.0), [freeze_state(v) for v in got])
        self.assertIn(freeze_state(0.0), [freeze_state(v) for v in got])

    def test_exact_double_covers_integer_and_float_representations(self):
        spec = {'type': 'DOUBLE', 'bound': [-1.1, 1.1]}
        got = ServiceModel.representatives(spec, [], True)
        expected = [None, *[n / 10 for n in range(-11, 12)], -0.0, -1, 0, 1]
        self.assertEqual({freeze_state(v) for v in got},
                         {freeze_state(v) for v in expected})
        for value in got:
            ServiceModel.validate_value(value, spec, 'exact DOUBLE')

    def test_automatic_double_finds_integer_string_conversion_counterexample(self):
        ir = timeline({'op': 'read', 'src': 'Light.CurrentBrightness', 'var': 'x'},
                      {'op': 'if', 'cond': '$x == 1',
                       'then': [call('Speaker.Speak', {'Text': 'value=$x'})]})
        script = ('x = (#Light).light_currentBrightness\n'
                  'if (x == 1) { (#Speaker).speaker_speak("value=1.0") }')
        binding = {'Light': ['light'], 'Speaker': ['speaker']}
        # Independent direct trace: the accepted integer input produces "1",
        # whereas the candidate emits "1.0". Former automatic domain missed it.
        pair = prepare_pair(ir, binding, DEVICES, {'script': script})
        world = {'light.currentbrightness': 1}
        self.assertEqual(pair.ir_runner.step({}, {}, world, 0, True).actions[0].args,
                         ('value=1',))
        self.assertEqual(pair.code_runner.step({}, {}, world, 0, True).actions[0].args,
                         ('value=1.0',))
        for domain in (None, {'light.currentbrightness': [1]}):
            result = run(ir, script, binding, input_domains=domain)
            self.assertEqual(result.verdict, 'DIVERGE', result.notes)
            self.assertTrue(result.confirmed)

    def test_dynamic_action_type_error_is_refused(self):
        ir = timeline({'op': 'read', 'src': 'TemperatureSensor.Temperature', 'var': 't'},
                      call('Speaker.Speak', {'Text': '$t'}))
        result = run(ir, 't = (#TemperatureSensor).temperatureSensor_temperature\n(#Speaker).speaker_speak(t)',
                     {'TemperatureSensor': ['temp'], 'Speaker': ['speaker']}, input_domains={'temp.temperature': [20.0]})
        self.assertEqual(result.verdict, 'REFUSED')
        self.assertIn('STRING', str(result.notes))

    def test_snapshot_provenance_and_stale_read_review(self):
        model = ServiceModel(DEVICES)
        self.assertEqual(model.snapshot['sha256'], REVIEWED_CATALOG_SHA256)
        data = {'skills': copy.deepcopy(model.snapshot['skills'])}
        data['skills'].append({'id': 'Extra', 'functions': []})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'catalog.json'
            path.write_text(json.dumps(data))
            altered = ServiceModel(DEVICES, str(path))
            with self.assertRaisesRegex(Unsupported, 'stale'):
                altered.call(altered.resolve('WeatherProvider', 'Forecast', 'function'),
                             [Lit(3)], True)

    def test_direct_timed_engines_validate_catalog_domains(self):
        from explorer.verification.timed import timed_product
        from explorer.tests.oracles.exact_timed import exact_timed_product
        ir = timeline({'op': 'if', 'cond': 'TemperatureSensor.Temperature > 10', 'then': [call()]})
        pair = prepare_pair(ir, {'TemperatureSensor': ['temp'], 'Switch': ['lamp']}, DEVICES,
                            {'script': 'if ((#TemperatureSensor).temperatureSensor_temperature > 10) { (#Switch).switch_on() }'})
        for engine in (timed_product, exact_timed_product):
            with self.assertRaisesRegex(Unsupported, 'bound mismatch'):
                engine(pair.ir_runner, pair.code_runner, input_domains={'temp.temperature': [100.0]}, horizon_ms=0)
            self.assertIn('EQUIV', engine(pair.ir_runner, pair.code_runner,
                                         input_domains=None, horizon_ms=0).verdict)

    def test_catalog_alias_collision_fails_closed(self):
        data = {'skills': [{'id': 'Switch', 'functions': [{'id': 'On'}, {'id': 'switch_on'}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'catalog.json'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(Unsupported, 'collision'):
                ServiceModel(DEVICES, str(path))

    def test_boolean_sensor_is_total_two_valued_on_all_entrypoints(self):
        from explorer.verification.timed import timed_product
        from explorer.tests.oracles.exact_timed import exact_timed_product
        ir = timeline({'op': 'if', 'cond': 'Switch.Switch == false', 'then': [call()]})
        pair = prepare_pair(ir, {'Switch': ['lamp']}, DEVICES,
                            {'script': 'if ((#Switch).switch_switch == false) { (#Switch).switch_on() }'})
        self.assertEqual(pair_input_domains(pair), {'lamp.switch': [False, True]})
        for invalid in (None, 0, 1, 'false'):
            with self.assertRaises(Unsupported):
                pair_input_domains(pair, {'lamp.switch': [False, invalid]})
            for engine in (timed_product, exact_timed_product):
                with self.assertRaises(Unsupported):
                    engine(pair.ir_runner, pair.code_runner,
                           input_domains={'lamp.switch': [invalid]}, horizon_ms=0)
        for runner in (pair.ir_runner, pair.code_runner):
            for snapshot in ({}, {'lamp.switch': None}, {'lamp.switch': 0}):
                with self.assertRaisesRegex(Unsupported, 'BOOL input'):
                    runner.step({}, {}, snapshot, 0, first_tick=True)
            self.assertEqual(len(runner.step({}, {}, {'lamp.switch': False}, 0, True).actions), 1)
            self.assertEqual(len(runner.step({}, {}, {'lamp.switch': True}, 0, True).actions), 0)
        self.assertEqual(pair.service_model.evidence()['boolean_input_policy'], 'strict-two-valued-v1')

    def test_boolean_query_result_rejects_missing_and_keeps_both_values(self):
        devices = {**DEVICES, 'cloud': {'category': ['CloudServiceProvider'], 'tags': ['Cloud']}}
        ir = timeline(call('CloudServiceProvider.IsAvailable', var='ok'),
                      {'op': 'if', 'cond': '$ok == true', 'then': [call()]})
        script = 'ok = (#Cloud).cloudServiceProvider_isAvailable()\nif (ok == true) { (#Switch).switch_on() }'
        pair = prepare_pair(ir, {'CloudServiceProvider': ['cloud'], 'Switch': ['lamp']},
                            devices, {'script': script})
        domains = pair_input_domains(pair)
        self.assertEqual(len(domains), 1)
        key = next(iter(domains))
        self.assertEqual(domains[key], [False, True])
        with self.assertRaises(Unsupported):
            pair_input_domains(pair, {key: [None, False, True]})
        for runner in (pair.ir_runner, pair.code_runner):
            with self.assertRaises(Unsupported):
                runner.step({}, {}, {key: None}, 0, True)
            self.assertEqual(len(runner.step({}, {}, {key: True}, 0, True).actions), 1)

    def test_all_false_equals_not_any_true_for_two_boolean_sensors(self):
        devices = {**DEVICES, 'a': {'category': ['MotionSensor'], 'tags': ['MotionSensor', 'A']},
                   'b': {'category': ['MotionSensor'], 'tags': ['MotionSensor', 'B']}}
        ir = timeline({'op': 'if', 'cond': 'MotionSensor.Motion == false', 'then': [call()]})
        binding = {'MotionSensor': {'all': ['a', 'b']}, 'Switch': ['lamp']}
        script = 'if (not (any(#MotionSensor).motionSensor_motion == true)) { (#Switch).switch_on() }'
        pair = prepare_pair(ir, binding, devices, {'script': script})
        self.assertEqual(pair_input_domains(pair), {'a.motion': [False, True], 'b.motion': [False, True]})
        for a in (False, True):
            for b in (False, True):
                for runner in (pair.ir_runner, pair.code_runner):
                    r = runner.step({}, {}, {'a.motion': a, 'b.motion': b}, 0, True)
                    self.assertEqual(len(r.actions), int(not a and not b))
        self.assertEqual(gate_pair(ir, binding, devices, {'script': script}, horizon_ms=0).verdict,
                         'EQUIV-BOUNDED')

    def test_boolean_alias_and_holiday_reject_missing_other_types_keep_it(self):
        from explorer.verification.input_model import validate_domains
        for typ in ('BOOL', 'BOOLEAN'):
            self.assertEqual(ServiceModel.representatives({'type': typ}, []), [False, True])
            with self.assertRaises(Unsupported):
                ServiceModel.validate_value(None, {'type': typ}, 'boolean')
        self.assertEqual(ServiceModel(DEVICES).input_spec('clock.isholiday'), {'type': 'BOOL'})
        with self.assertRaises(ValueError):
            validate_domains({'clock.isholiday': [None, False, True]})
        for spec in ({'type': 'INTEGER', 'bound': [0, 1]}, {'type': 'DOUBLE', 'bound': [0, 0.1]},
                     {'type': 'STRING', 'members': ['rain']}):
            self.assertIn(None, ServiceModel.representatives(spec, [], exact=True))


if __name__ == '__main__':
    unittest.main()
