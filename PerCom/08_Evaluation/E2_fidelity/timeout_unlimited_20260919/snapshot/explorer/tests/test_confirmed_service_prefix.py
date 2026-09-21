import unittest

from explorer.eval.e3 import load_rows, row_payload, key_of
from lowering.confirmed_inputs import pipeline_contract
from timeline_ir.pipeline_helpers import _apply_service_prefix, JoiGenerationError


class ConfirmedServicePrefixTests(unittest.TestCase):
    def test_colliding_members_keep_ir_skill(self):
        for skill, member, device in (
            ('TemperatureSensor', 'Temperature', 'LivingRoom_Temp'),
            ('HumiditySensor', 'Humidity', 'LivingRoom_Humidity'),
            ('WindowCovering', 'CurrentPosition', 'LivingRoom_Shade'),
            ('Charger', 'Voltage', 'Garage_Charger'),
            ('Plug', 'Power', 'Office_Printer'),
        ):
            selector = f'(#{device})'
            with self.subTest(skill=skill):
                self.assertEqual(
                    _apply_service_prefix(f'{selector}.{member}',
                        confirmed_selectors={f'{skill}.{member}': [selector]}),
                    f'{selector}.{skill[0].lower()}{skill[1:]}_{member[0].lower()}{member[1:]}')

    def test_all_382_confirmed_contracts(self):
        rows = load_rows()
        self.assertEqual(len(rows), 382)
        for row in rows:
            p = row_payload(row)
            selectors = pipeline_contract(p['ir'], p['binding'], p['connected_devices'])['df_selectors']
            for full, values in selectors.items():
                skill, member = full.split('.')
                for selector in values:
                    with self.subTest(case=key_of(row), full=full, selector=selector):
                        expected = f'{selector}.{skill[0].lower()}{skill[1:]}_{member[0].lower()}{member[1:]}'
                        self.assertEqual(_apply_service_prefix(f'{selector}.{member}',
                            confirmed_selectors=selectors), expected)

    def test_string_arguments_and_nested_calls(self):
        selectors = {'Speaker.Speak': ['(#speaker)'], 'TemperatureSensor.Temperature': ['(#temp)']}
        script = '(#speaker).Speak("(#temp).Temperature", f((#temp).Temperature))'
        expected = '(#speaker).speaker_speak("(#temp).Temperature", f((#temp).temperatureSensor_temperature))'
        self.assertEqual(_apply_service_prefix(script, confirmed_selectors=selectors), expected)
        self.assertEqual(_apply_service_prefix(expected, confirmed_selectors=selectors), expected)

    def test_missing_or_ambiguous_contract_does_not_guess(self):
        for selectors in ({}, {'Plug.Power': ['(#d)'], 'Charger.Power': ['(#d)']}):
            with self.assertRaises(JoiGenerationError):
                _apply_service_prefix('(#d).Power', confirmed_selectors=selectors)

    def test_explicit_model_prefix_is_preserved_for_evaluation(self):
        script = '(#temp).airQualitySensor_temperature'
        self.assertEqual(_apply_service_prefix(script,
            confirmed_selectors={'TemperatureSensor.Temperature': ['(#temp)']}), script)

    def test_ambient_clock_member_resolves_without_binding(self):
        # Clock is never bound; the catalog fixes the skill (C18_005 harness failure, 2026-09-15).
        selectors = {'Switch.Off': ['(#Fac_Pump_1)']}
        script = 'if ((#Clock).Weekday == "monday") {\nbreak\n}\n(#Fac_Pump_1).Off()'
        self.assertEqual(_apply_service_prefix(script, confirmed_selectors=selectors),
                         'if ((#Clock).clock_weekday == "monday") {\nbreak\n}\n(#Fac_Pump_1).switch_off()')
        with self.assertRaises(JoiGenerationError):
            _apply_service_prefix('(#Clock).NoSuchMember', confirmed_selectors=selectors)


if __name__ == '__main__':
    unittest.main()
