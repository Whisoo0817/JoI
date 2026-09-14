"""Silent interval coverage, dense witnesses, and unbounded completion checks."""
import itertools
import json
from pathlib import Path
import unittest

from explorer.runtime.ir_step import IrRunner
from explorer.runtime.oneshot import OneShotRunner
from explorer.runtime.pause import PauseRunner
from explorer.verification.product import replay_divergence, Divergence
from explorer.verification.time_events import grid_history
from explorer.verification.timed import timed_product
from explorer.tests.test_contract import timeline, call
from explorer.tests.test_search_correctness import exhaustive_traces, X, Y, ON
from explorer.verification.gate import selector_binding  # binding decision 2026-09-14


class TimeElisionTests(unittest.TestCase):
    def compare(self, a, b, domains=None, **kwargs):
        r = timed_product(a, b, input_domains=domains or {}, t0_ms=0,
                          max_states=200, max_transitions=2000, **kwargs)
        if r.verdict == 'DIVERGE':
            self.assertTrue(replay_divergence(a, b, r.divergences[0]).confirmed)
        return r

    def test_hour_delay_has_constant_search_cost(self):
        sizes = []
        for duration in (1000, 3600000, 3600000000):
            a = IrRunner(timeline({'op': 'delay', 'duration': f'{duration} MSEC'}, call()))
            b = OneShotRunner(f'delay({duration} MSEC)\n{ON}')
            r = self.compare(a, b)
            self.assertEqual(r.claim, 'EQUIV-FIXPOINT')
            sizes.append((r.n_states, r.n_steps))
        self.assertEqual(sizes, [(1, 4)] * 3)

    def test_latest_input_after_off_grid_wake_not_entry_input(self):
        a = OneShotRunner(f'x = {X}\ndelay(150 MSEC)\nif (x) {{ {ON} }}')
        b = OneShotRunner(f'delay(150 MSEC)\nif ({X}) {{ {ON} }}')
        r = self.compare(a, b, {'sensor.value': [False, True]})
        self.assertEqual(r.verdict, 'DIVERGE')
        d = r.divergences[0]
        expanded = grid_history(d.path + [(d.input_, d.dwell_ms)], 0, 100)
        self.assertEqual([v for _, v in expanded], [0, 100, 50])

    def test_input_does_not_change_before_first_grid(self):
        a = OneShotRunner(f'x = {X}\ndelay(50 MSEC)\nif (x) {{ {ON} }}')
        b = OneShotRunner(f'delay(50 MSEC)\nif ({X}) {{ {ON} }}')
        self.assertEqual(self.compare(a, b, {'sensor.value': [False, True]}).claim, 'EQUIV-FIXPOINT')

    def test_grid_tie_new_input_first(self):
        a = OneShotRunner(f'x = {X}\ndelay(100 MSEC)\nif (x) {{ {ON} }}')
        b = OneShotRunner(f'delay(100 MSEC)\nif ({X}) {{ {ON} }}')
        self.assertEqual(self.compare(a, b, {'sensor.value': [False, True]}).verdict, 'DIVERGE')

    def test_all_latest_input_combinations_are_compared(self):
        a = OneShotRunner(f'delay(150 MSEC)\nif ({X} and {Y}) {{ {ON} }}')
        b = OneShotRunner(f'delay(150 MSEC)\nif ({X}) {{ {ON} }}')
        r = self.compare(a, b, {'sensor.value': [False, True], 'other.value': [False, True]})
        self.assertEqual(r.verdict, 'DIVERGE')

    def test_different_delay_segmentation_can_be_equivalent(self):
        a = OneShotRunner(f'delay(100 MSEC)\ndelay(100 MSEC)\n{ON}')
        b = OneShotRunner(f'delay(200 MSEC)\n{ON}')
        self.assertEqual(self.compare(a, b).claim, 'EQUIV-FIXPOINT')

    def test_one_sleep_does_not_hide_other_wait_input_history(self):
        a = OneShotRunner(f'delay(150 MSEC)\nif ({X}) {{ {ON} }}')
        b = OneShotRunner(f'wait until({X})\ndelay(150 MSEC)\n{ON}')
        r = self.compare(a, b, {'sensor.value': [False, True]})
        self.assertEqual(r.verdict, 'DIVERGE')

    def test_dense_history_oracle_including_snapshots_and_nested_resume(self):
        programs = [
            OneShotRunner(f'x = {X}\ndelay(3 MSEC)\nif (x and {Y}) {{ {ON} }}'),
            OneShotRunner(f'delay(3 MSEC)\nif ({X} and {Y}) {{ {ON} }}'),
            PauseRunner(f'if ({X}) {{ delay(3 MSEC)\nif ({Y}) {{ {ON} }} }}', False),
            OneShotRunner(f'wait until({X})\ndelay(3 MSEC)\n{ON}'),
            OneShotRunner(f'delay(2 MSEC)\ndelay(1 MSEC)\nif ({Y}) {{ {ON} }}'),
        ]
        domains = {'sensor.value': [False, True], 'other.value': [False, True]}
        for a, b in itertools.product(programs, repeat=2):
            expected, _ = exhaustive_traces(a, b, domains, horizon=4, delta=2)
            r = self.compare(a, b, domains, horizon_ms=4, input_step_ms=2)
            self.assertEqual(r.verdict, 'DIVERGE' if expected else 'EQUIV')

    def test_sustained_edge_and_timeout_waits_keep_events(self):
        for extra in ({'for': '3 MSEC'}, {'edge': 'rising'},
                      {'timeout': '3 MSEC', 'on_timeout': [call('Off')]}):
            a = IrRunner(timeline({'op': 'wait', 'cond': 'Sensor.Value == true', **extra}, call()))
            b = OneShotRunner(f'delay(3 MSEC)\n{ON}')
            domains = {'sensor.value': [False, True]}
            expected, _ = exhaustive_traces(a, b, domains, horizon=6, delta=2)
            r = self.compare(a, b, domains, horizon_ms=6, input_step_ms=2)
            self.assertEqual(r.verdict, 'DIVERGE' if expected else 'EQUIV')

    def test_long_completion_relative_period_closes(self):
        a = IrRunner(timeline({'op': 'cycle', 'period': '1 HOUR', 'body': [
            {'op': 'delay', 'duration': '150 MSEC'}, call()]}))
        b = PauseRunner(f'delay(150 MSEC)\n{ON}', True, 3600000)
        r = self.compare(a, b)
        self.assertEqual(r.claim, 'EQUIV-FIXPOINT')
        self.assertLess(r.n_states, 10)

    def test_clock_wait_is_not_constant_input_silent(self):
        a = OneShotRunner(f'wait until(clock.timestamp >= 1)\ndelay(1 SEC)\n{ON}')
        b = OneShotRunner(f'delay(2 SEC)\n{ON}')
        self.assertEqual(self.compare(a, b).claim, 'EQUIV-FIXPOINT')

    def test_delay_length_fault_after_old_horizon_is_found(self):
        a = OneShotRunner(f'delay(1 HOUR)\n{ON}')
        b = OneShotRunner(f'delay(2 HOUR)\n{ON}')
        self.assertEqual(self.compare(a, b, horizon_ms=3200).claim, 'EQUIV-BOUNDED')
        r = self.compare(a, b)
        self.assertEqual(r.verdict, 'DIVERGE')
        self.assertEqual(r.divergences[0].dwell_ms, 3600000)

    def test_resource_cap_still_prevents_positive_claim(self):
        a = OneShotRunner(f'delay(1 HOUR)\n{ON}')
        r = timed_product(a, a, input_domains={}, max_transitions=1)
        self.assertEqual(r.claim, 'INCONCLUSIVE')

    def test_replay_executes_a_deadline_omitted_from_supplied_path(self):
        a = OneShotRunner(f'delay(100 MSEC)\n{ON}')
        b = OneShotRunner(f'delay(200 MSEC)\n{ON}')
        d = Divergence(1, {}, 200, (), (), [({}, 0)], {}, 0, 100)
        self.assertTrue(replay_divergence(a, b, d).confirmed)

    def test_replay_rejects_input_change_before_first_grid(self):
        a = OneShotRunner(f'delay(50 MSEC)\nif ({X}) {{ {ON} }}')
        b = OneShotRunner('wait until(false)')
        d = Divergence(1, {'sensor.value': True}, 50, (), (),
                       [({'sensor.value': False}, 0)], {}, 0, 100)
        self.assertFalse(replay_divergence(a, b, d).confirmed)

    def test_unknown_wrapper_is_not_assumed_silent_with_its_inner(self):
        from explorer.runtime.interp import Action
        class ExtraAction:
            def __init__(self, inner): self.inner = inner
            def __getattr__(self, name): return getattr(self.inner, name)
            def step(self, values, gv, inputs, now_ms, first_tick=False):
                out = self.inner.step(values, gv, inputs, now_ms, first_tick)
                if now_ms == 100:
                    out.actions.append(Action('switch', 'off', (), ('extra',)))
                return out
        b = OneShotRunner(f'delay(1 SEC)\n{ON}')
        self.assertEqual(self.compare(ExtraAction(b), b, horizon_ms=1000).verdict, 'DIVERGE')

    def test_fixed_input_sustained_counter_fault_replays_at_59_seconds(self):
        a = IrRunner(timeline({'op': 'wait', 'cond': 'Sensor.Value == true',
                              'for': '1 MIN'}, call()))
        b = PauseRunner(f'k := 0\nif ({X}) {{ k = k+1\n'
                        f'if (k >= 60) {{ {ON}\nbreak }} }} else {{ k = 0 }}', True, 1000)
        r = self.compare(a, b, {'sensor.value': [False, True]})
        self.assertEqual(r.verdict, 'DIVERGE')
        d = r.divergences[0]
        self.assertEqual(sum(t for _, t in d.path) + d.dwell_ms, 59000)
        self.assertLess(r.n_steps, 150)

    def test_constant_input_probe_does_not_replace_changed_input_histories(self):
        # Both constant worlds agree (never act / act at1000). The pulse at
        # 100ms breaks the sustained wait but cannot interrupt the plain delay.
        a = IrRunner(timeline({'op': 'wait', 'cond': 'Sensor.Value == true',
                              'for': '1 SEC'}, call()))
        b = OneShotRunner(f'wait until({X})\ndelay(1 SEC)\n{ON}')
        r = self.compare(a, b, {'sensor.value': [False, True]}, horizon_ms=1000)
        self.assertEqual(r.verdict, 'DIVERGE')
        self.assertGreater(len({world['sensor.value'] for world, _ in r.divergences[0].path}), 1)

    def test_auto_selects_proved_counter_relation_only_without_horizon(self):
        from explorer.tests.test_relational_fixpoint import counter_case
        from explorer.tests.test_symbolic_value_flow import prepared
        from explorer.runtime.interp import Unsupported
        c = counter_case(delay=150)
        p = prepared(c)
        r = timed_product(p.ir_runner, p.code_runner, max_states=100, max_transitions=1000)
        self.assertEqual(r.claim, 'EQUIV-FIXPOINT')
        self.assertEqual(r.symbolic_certificate['schema'], 'relational-state-v1')
        with self.assertRaises(Unsupported):
            timed_product(p.ir_runner, p.code_runner, horizon_ms=3200)

    def test_symbolic_latest_epoch_after_off_grid_sleep(self):
        from explorer.tests.test_symbolic_value_flow import case, prepared, delayed
        a = delayed(case(), 3600150, fresh=True)
        # IR captured the sensor before delay; code reads a new epoch afterwards.
        p = prepared(a)
        r = timed_product(p.ir_runner, p.code_runner, max_states=100, max_transitions=1000)
        self.assertEqual(r.verdict, 'DIVERGE')
        self.assertTrue(replay_divergence(p.ir_runner, p.code_runner, r.divergences[0]).confirmed)

    def test_c08_011_actual_candidate_concrete_hour_witness(self):
        with selector_binding(False):  # selector correctness: frozen semantics
            from explorer.verification.gate import prepare_pair
            path = Path(__file__).parents[1] / 'eval/results/unbounded_resource_examples_2026-09-08_v1.json'
            c = json.loads(path.read_text())['cases'][0]
            self.assertEqual(c['id'], 'C08_011')
            p = c['payload']
            pair = prepare_pair(p['ir'], p['binding'], p['devices'], p['joi_block'])
            r = timed_product(pair.ir_runner, pair.code_runner, **c['model'], max_transitions=100)
            self.assertEqual(r.verdict, 'DIVERGE')
            d = r.divergences[0]
            self.assertEqual(d.input_['Main_MB.button3'], None)
            self.assertEqual(d.input_['Hall_MB.button3'], 'pushed')
            self.assertEqual(sum(ms for _, ms in d.path) + d.dwell_ms, 3600000)
            self.assertTrue(replay_divergence(pair.ir_runner, pair.code_runner, d).confirmed)

    def test_smt_terminating_paths_after_long_sleep_need_no_horizon(self):
        from explorer.tests.test_smt_trace import arithmetic_case, run
        c = arithmetic_case('"v=" + ($A+1)', '"v=" + (A+1)', count=1)
        c['horizon_ms'] = None
        c['ir']['timeline'].insert(1, {'op': 'delay', 'duration': '1 HOUR'})
        c['joi_block']['script'] = 'delay(1 HOUR)\n' + c['joi_block']['script']
        r = run(c, max_states=100, max_transitions=100)
        self.assertEqual(r.claim, 'EQUIV-FIXPOINT')
        self.assertTrue(r.symbolic_certificate['both_terminated'])
        self.assertLess(r.n_steps, 50)

    def test_smt_nonterminating_wait_cannot_claim_unbounded_equivalence(self):
        from explorer.tests.test_smt_trace import arithmetic_case, run
        c = arithmetic_case('"v=" + ($A+1)', '"v=" + (A+1)', count=1)
        c['horizon_ms'] = None
        c['ir']['timeline'].insert(1, {'op': 'wait', 'cond': 'false', 'edge': 'none'})
        c['joi_block']['script'] = 'wait until(false)\n' + c['joi_block']['script']
        r = run(c, max_states=10, max_transitions=100)
        self.assertEqual(r.claim, 'INCONCLUSIVE')


if __name__ == '__main__':
    unittest.main()
