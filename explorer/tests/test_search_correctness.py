"""Search proof obligations checked against unmerged, dense input histories.

This reference deliberately uses neither state keys nor deadline scheduling.
It shares the concrete interpreters/observation, whose evidence is separate E1.
Run: python -m explorer.tests.test_search_correctness
"""
import copy
from fractions import Fraction
import itertools
import unittest

from explorer.runtime.ir_step import IrRunner
from explorer.verification.observation import actions_observation
from explorer.runtime.oneshot import OneShotRunner
from explorer.runtime.pause import PauseRunner
from explorer.verification.product import replay_divergence
from explorer.runtime.runner import TerminalRunner
from explorer.verification.state_key import freeze_state
from explorer.tests.test_contract import timeline, call
from explorer.verification.timed import timed_product, next_time, reads_clock, internal_timers

X = '(#Sensor).sensor_value'
Y = '(#Other).other_value'
ON = '(#Switch).switch_on()'
DOMAINS = {'sensor.value': [False, True], 'other.value': [False, True]}


def snapshots(domains):
    return [dict(zip(domains, vs)) for vs in itertools.product(*domains.values())]


def exhaustive_traces(a, b, domains, horizon=6, delta=2, initials=({},), t0=0):
    """Restart from scratch for EVERY full history, even after a mismatch."""
    mismatch, histories = False, 0
    for initial in initials:
        for history in itertools.product(snapshots(domains), repeat=horizon // delta + 1):
            histories += 1
            left, right = TerminalRunner(a), TerminalRunner(b)
            av, bv, ag, bg = {}, {}, dict(initial), dict(initial)
            for t in range(horizon + 1):
                world = history[t // delta]
                ra = left.step(av, ag, world, t0 + t, t == 0)
                rb = right.step(bv, bg, world, t0 + t, t == 0)
                mismatch |= actions_observation(ra.actions) != actions_observation(rb.actions)
                av, ag, bv, bg = ra.vars, ra.gv, rb.vars, rb.gv
    return mismatch, histories


class SearchCorrectnessTests(unittest.TestCase):
    def test_bfs_against_every_unmerged_history(self):
        sources = [
            f'x = {X}\ndelay(3 MSEC)\nif (x and {Y}) {{ {ON} }}',
            f'delay(3 MSEC)\nif ({X} and {Y}) {{ {ON} }}',
            f'wait until({X})\ndelay(1 MSEC)\nif ({Y}) {{ {ON} }}',
        ]
        checked = 0
        for sa, sb in itertools.product(sources, repeat=2):
            a, b = OneShotRunner(sa), OneShotRunner(sb)
            divergent, count = exhaustive_traces(a, b, DOMAINS)
            checked += count
            result = timed_product(a, b, input_domains=DOMAINS,
                                   input_step_ms=2, horizon_ms=6, t0_ms=0)
            self.assertEqual(result.verdict, 'DIVERGE' if divergent else 'EQUIV')
            if divergent:
                self.assertTrue(replay_divergence(a, b, result.divergences[0]).confirmed)
        self.assertEqual(checked, 9 * 4**4)

    def test_initial_gv_product_and_inclusive_horizon(self):
        get = '(#GlobalVariable).globalVariable_getFloat("g")'
        put = '(#GlobalVariable).globalVariable_setFloat("g", 0)'
        a = PauseRunner(f'x = {get}\n{put}\ndelay(6 MSEC)\n'
                        f'if (x == 1 and {X}) {{ {ON} }}', False)
        b = PauseRunner(f'{put}\nwait until(false)', False)
        domains = {'sensor.value': [False, True]}
        for h, expected in ((5, False), (6, True)):
            divergent, count = exhaustive_traces(a, b, domains, horizon=h,
                                                 initials=({'g': 0}, {'g': 1}))
            self.assertEqual(divergent, expected)
            self.assertEqual(count, 2 * 2**(h // 2 + 1))
            result = timed_product(a, b, input_domains=domains, horizon_ms=h,
                                   input_step_ms=2, initial_gv_domains={'g': [0, 1]}, t0_ms=0)
            self.assertEqual(result.verdict, 'DIVERGE' if expected else 'EQUIV')
            if expected:
                self.assertEqual(result.divergences[0].initial_gv, {'g': 1})
                self.assertTrue(replay_divergence(a, b, result.divergences[0]).confirmed)

    def test_every_skipped_millisecond_is_a_silent_unchanged_state(self):
        runners = [
            OneShotRunner(f'delay(3 MSEC)\nwait until({X})\n{ON}'),
            PauseRunner(f'if ({X}) {{ delay(3 MSEC)\n{ON} }}', True, 3),
            IrRunner(timeline({'op': 'cycle', 'period': '3 MSEC', 'body': [
                {'op': 'wait', 'cond': 'Sensor.Value == true', 'for': '3 MSEC'}, call()]})),
            IrRunner(timeline({'op': 'wait', 'cond': 'Sensor.Value == true',
                'timeout': '3 MSEC', 'on_timeout': [call('Off')]}, call())),
            IrRunner(timeline({'op': 'cycle', 'period': '3 MSEC', 'body': [
                {'op': 'wait', 'cond': 'Sensor.Value == true', 'edge': 'rising'}, call()]})),
            OneShotRunner('wait until(clock.timestamp > 0)\n' + ON),
        ]
        silent = TerminalRunner(OneShotRunner('wait until(false)'))
        probes = 0
        for runner in runners:
            r = TerminalRunner(runner)
            for history in itertools.product((False, True), repeat=4):
                values, gv = {}, {}
                for offset in range(10):
                    now = 997 + offset  # second boundary is between grid points
                    world = {'sensor.value': history[offset // 3]}
                    before = copy.deepcopy((values, gv, world))
                    out = r.step(values, gv, world, now, offset == 0)
                    self.assertEqual((values, gv, world), before)
                    deadline = next_time(r, silent, out.vars, {}, now, 997, 3, reads_clock(r))
                    for t in range(now + 1, min(deadline, 1007)):
                        again = r.step(out.vars, out.gv, world, t)
                        self.assertEqual(again.actions, [])
                        self.assertEqual((again.vars, again.gv), (out.vars, out.gv))
                        probes += 1
                    values, gv = out.vars, out.gv
        self.assertGreater(probes, 0)

    def test_time_translation_on_reachable_timer_states(self):
        runners = [PauseRunner(f'delay(3 MSEC)\n{ON}', True, 2),
                   IrRunner(timeline({'op': 'cycle', 'period': '2 MSEC', 'body': [
                       {'op': 'wait', 'cond': 'Sensor.Value == true', 'for': '3 MSEC'},
                       {'op': 'delay', 'duration': '1 MSEC'}, call()]}))]
        shift = 10**16  # even: preserves the 2ms external input phase
        for raw in runners:
            runner = TerminalRunner(raw)
            self.assertFalse(reads_clock(runner))
            timers = internal_timers(runner)
            av, bv, ag, bg = {}, {}, {}, {}
            for t in range(25):
                world = {'sensor.value': t < 12 or t >= 16}
                a = runner.step(av, ag, world, t, t == 0)
                b = runner.step(bv, bg, world, t + shift, t == 0)
                self.assertEqual(actions_observation(a.actions), actions_observation(b.actions))
                translated = dict(b.vars)
                for k in timers & translated.keys():
                    if translated[k] is not None:
                        translated[k] -= Fraction(shift, 1000)
                self.assertEqual(freeze_state(a.vars), freeze_state(translated))
                self.assertEqual(a.gv, b.gv)
                wa = runner.next_wakeup_ms(a.vars, t, 2)
                wb = runner.next_wakeup_ms(b.vars, t + shift, 2)
                self.assertEqual(wb, None if wa is None else wa + shift)
                av, ag, bv, bg = a.vars, a.gv, b.vars, b.gv

    def test_each_resource_cap_prevents_positive_claim(self):
        a = PauseRunner(f'if ({X}) {{ {ON} }}', True, 2)
        for caps in ({'max_states': 1}, {'max_transitions': 1}, {'max_input_combinations': 1}):
            result = timed_product(a, a, input_domains={'sensor.value': [False, True]},
                                   input_step_ms=2, horizon_ms=6, **caps)
            self.assertEqual(result.verdict, 'UNKNOWN')
            self.assertFalse(result.closed)


if __name__ == '__main__':
    unittest.main()
