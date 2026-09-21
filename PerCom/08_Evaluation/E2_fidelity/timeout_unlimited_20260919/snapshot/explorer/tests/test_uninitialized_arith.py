"""RUNTIME_CONTRACT R14 — arithmetic on a variable that was never assigned is a runtime error.

Run: python3 -m explorer.tests.test_uninitialized_arith
"""
import unittest

from explorer.runtime.interp import ERROR_ACTION_SERVICE, parse, step
from explorer.runtime.pause import PauseRunner
from explorer.verification.timed import timed_product


def one_step(script, inputs=None, vars_=None):
    return step(parse(script), vars_ or {}, {}, inputs or {}, 0, first_tick=True)


class UninitializedArithTests(unittest.TestCase):
    def test_never_assigned_variable_in_arithmetic_stops_the_instance(self):
        r = one_step('n = n + 1\nall(#Light).light_on()')
        self.assertTrue(r.terminated)
        self.assertEqual([a.service for a in r.actions], [ERROR_ACTION_SERVICE])

    def test_actions_before_the_error_are_kept(self):
        r = one_step('all(#Light).light_on()\nn = n + 1')
        self.assertEqual([a.service for a in r.actions], ['light', ERROR_ACTION_SERVICE])

    def test_assignment_in_an_untaken_branch_does_not_count(self):
        script = 'if ((#Sensor).sensor_value > 100) { n := 0 }\nn = n + 1'
        r = one_step(script, {'sensor.value': 0})
        self.assertTrue(r.terminated)
        r_assigned = one_step(script, {'sensor.value': 200})
        self.assertFalse(r_assigned.terminated)
        self.assertEqual(r_assigned.vars['n'], 1)

    def test_a_variable_holding_a_missing_input_is_not_an_error(self):
        # R10 allows a non-BOOL input to have no value; the variable IS assigned, so R14 does not apply.
        r = one_step('v = (#Sensor).sensor_value\nx = v + 1', {'sensor.value': None})
        self.assertFalse(r.terminated)
        self.assertEqual([a.service for a in r.actions], [])

    def test_text_concatenation_with_an_unassigned_variable_is_not_arithmetic(self):
        r = one_step('all(#Speaker).speaker_speak("level " + level)')
        self.assertFalse(r.terminated)
        self.assertEqual([a.service for a in r.actions], ['speaker'])

    def test_the_error_makes_the_two_sides_differ(self):
        good = PauseRunner('n = 0\nx = n + 1\nall(#Light).light_on()', False)
        broken = PauseRunner('if (false) { n = 0 }\nx = n + 1\nall(#Light).light_on()', False)
        self.assertEqual(timed_product(good, broken, horizon_ms=0).verdict, 'DIVERGE')


if __name__ == '__main__':
    unittest.main()
