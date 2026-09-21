import unittest

from explorer.runtime.pause import PauseRunner
from explorer.verification.product import replay_divergence
from explorer.verification.timed import timed_product


class ExactArithmeticActionTests(unittest.TestCase):
    def test_bounded_min_is_equivalent_to_guard_lowering(self):
        direct = PauseRunner(
            'tmp = (#Sensor).sensor_value + 10\n'
            'if (tmp > 100) { tmp = 100 }\n'
            'all(#Light).light_moveToBrightness(tmp, 0)', False)
        guarded = PauseRunner(
            'value = (#Sensor).sensor_value + 10\n'
            'if (100 < value) { value = 100 }\n'
            'all(#Light).light_moveToBrightness(value, 0)', False)
        domain = {'sensor.value': [0, 1, 90, 99, 100]}
        result = timed_product(direct, guarded, input_domains=domain, horizon_ms=0)
        self.assertEqual(result.verdict, 'EQUIV')

    def test_missing_clamp_has_replayed_counterexample(self):
        direct = PauseRunner(
            'tmp = (#Sensor).sensor_value + 10\n'
            'if (tmp > 100) { tmp = 100 }\n'
            'all(#Light).light_moveToBrightness(tmp, 0)', False)
        faulty = PauseRunner(
            'all(#Light).light_moveToBrightness((#Sensor).sensor_value + 10, 0)', False)
        result = timed_product(direct, faulty,
            input_domains={'sensor.value': [0, 90, 100]}, horizon_ms=0)
        self.assertEqual(result.verdict, 'DIVERGE')
        self.assertTrue(replay_divergence(direct, faulty, result.divergences[0]).confirmed)


if __name__ == '__main__':
    unittest.main()
