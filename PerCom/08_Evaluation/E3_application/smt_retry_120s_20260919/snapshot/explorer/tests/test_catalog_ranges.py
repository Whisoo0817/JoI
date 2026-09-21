"""Catalog range proof, conservative fallbacks, and timed-trace regressions."""
import copy
import itertools
import json
import operator
from pathlib import Path
import tempfile
import unittest

from explorer.runtime import expr as e
from explorer.verification.gate import prepare_pair
from explorer.runtime.interp import Unsupported, clock_state
from explorer.verification.product import replay_divergence
from explorer.verification.range_analysis import constant_integer_comparison, interval_comparison
from explorer.verification.service_model import ServiceModel
from explorer.verification.timed import reads_clock, timed_product
from explorer.tests.test_contract import timeline, call, DEVICES


def pair(until='clock.time >= 2400', condition='(#Clock).clock_hour >= 24', *, catalog=True):
    ir = timeline({'op': 'cycle', 'period': '1 HOUR', 'until': until, 'body': [call()]})
    block = {'period': 3600000, 'script': f'if ({condition}) {{ break }}\nall(#Switch).switch_on()'}
    return prepare_pair(ir, {'Switch': ['living', 'kitchen']}, DEVICES, block, service_catalog=catalog)


def search(p, **kwargs):
    return timed_product(p.ir_runner, p.code_runner, input_domains={},
                         max_states=20, max_transitions=100, t0_ms=0, **kwargs)


class CatalogRangeTests(unittest.TestCase):
    def test_declared_time_ranges_and_runtime_rollover(self):
        model = ServiceModel({})
        for field, hi in [('Hour', 23), ('Minute', 59), ('Second', 59)]:
            spec = model.resolve('Clock', field, 'value')
            self.assertEqual((spec['type'], spec['bound']), ('INTEGER', [0, hi]))
            model.validate_value(hi, spec, field)
            for bad in (-1, hi + 1, 0.0, None):
                with self.assertRaises(Unsupported):
                    model.validate_value(bad, spec, field, missing=False)
        for t in (-1, 0, 3599999, 3600000, 86399999, 86400000, 10**15):
            c = clock_state(t)
            self.assertTrue(0 <= c['clock.hour'] <= 23)
            self.assertTrue(0 <= c['clock.minute'] <= 59)
        self.assertEqual(clock_state(86400000)['clock.hour'], 0)

    def test_hhmm_range_is_derived_and_catalog_string_is_preserved(self):
        model = ServiceModel({})
        self.assertEqual(model.clock_integer_range('clock.time'), (0, 2359))
        self.assertEqual(model.resolve('Clock', 'Time', 'value')['type'], 'STRING')
        node = e.BinaryOp('>=', e.ClockRef('time'), e.Lit(2400))
        self.assertIs(constant_integer_comparison(node, model.clock_integer_range), False)
        node.left = e.DeviceRef('clock.time')
        self.assertIsNone(constant_integer_comparison(node, model.clock_integer_range))

    def test_interval_proofs_agree_with_full_small_integer_domains(self):
        intervals = [(lo, hi) for lo in range(-2, 3) for hi in range(lo, 3)]
        for op, evaluate in [('<', operator.lt), ('<=', operator.le), ('>', operator.gt),
                             ('>=', operator.ge), ('==', operator.eq), ('!=', operator.ne)]:
            for left, right in itertools.product(intervals, repeat=2):
                proof = interval_comparison(op, left, right)
                if proof is not None:
                    values = {evaluate(a, b) for a in range(left[0], left[1] + 1)
                              for b in range(right[0], right[1] + 1)}
                    self.assertEqual(values, {proof}, (op, left, right))
        self.assertIsNone(interval_comparison('==', (0, 23), (12, 12)))
        self.assertIsNone(interval_comparison('!=', (0, 23), (12, 12)))

    def test_impossible_hour_and_hhmm_guards_close_without_horizon(self):
        p = pair()
        for r in (p.ir_runner, p.code_runner):
            self.assertTrue(reads_clock(r))
            self.assertFalse(reads_clock(r, catalog_ranges=True))
        result = search(p)
        self.assertEqual((result.claim, result.n_states, result.n_steps), ('EQUIV-FIXPOINT', 1, 4))
        self.assertIn('catalog-range-v1', str(result.notes))

    def test_minute_comparison_and_reversed_literal_use_same_range_rule(self):
        p = pair('60 <= clock.minute', '60 <= (#Clock).clock_minute')
        self.assertEqual(search(p).claim, 'EQUIV-FIXPOINT')

    def test_always_true_condition_preserves_termination(self):
        p = pair('clock.time <= 2359', '(#Clock).clock_hour < 24')
        result = search(p)
        self.assertEqual(result.claim, 'EQUIV-FIXPOINT')
        for runner in (p.ir_runner, p.code_runner):
            first = runner.step({}, {}, {}, 0, True)
            self.assertEqual(first.actions, [])
            self.assertIsNone(runner.next_wakeup_ms(first.vars, 0, 100))

    def test_real_hour_boundary_still_diverges_and_replays(self):
        p = pair(condition='(#Clock).clock_hour >= 1')
        self.assertTrue(reads_clock(p.code_runner, catalog_ranges=True))
        result = search(p)
        self.assertEqual(result.verdict, 'DIVERGE')
        self.assertTrue(replay_divergence(p.ir_runner, p.code_runner, result.divergences[0]).confirmed)
        self.assertEqual(result.divergences[0].dwell_ms, 3600000)

    def test_midnight_stop_is_distinct_from_impossible_24_guard(self):
        p = pair(condition='(#Clock).clock_hour == 0')
        # Start at 23:00; the candidate stops at midnight, IR keeps acting.
        result = timed_product(p.ir_runner, p.code_runner, input_domains={},
                               t0_ms=23 * 3600000, max_states=20, max_transitions=100)
        self.assertEqual(result.verdict, 'DIVERGE')
        self.assertTrue(replay_divergence(p.ir_runner, p.code_runner, result.divergences[0]).confirmed)

    def test_no_catalog_keeps_conservative_absolute_time(self):
        p = pair(catalog=False)
        self.assertTrue(reads_clock(p.ir_runner, catalog_ranges=True))
        self.assertEqual(search(p).claim, 'INCONCLUSIVE')

    def test_custom_catalog_bounds_control_proof_and_invalid_bounds_disable_it(self):
        raw = ServiceModel({}).snapshot['skills']
        for bounds, typ in [([0, 24], 'INTEGER'), ([0, 22], 'INTEGER'),
                            ([0, 23], 'DOUBLE'), (None, 'INTEGER'), ([23, 0], 'INTEGER')]:
            data = copy.deepcopy(raw)
            hour = next(v for s in data if s['id'] == 'Clock' for v in s['values'] if v['id'] == 'Hour')
            hour.update(bound=bounds, type=typ)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'catalog.json'
                path.write_text(json.dumps({'skills': data}))
                p = pair(catalog=str(path))
                self.assertTrue(reads_clock(p.code_runner, catalog_ranges=True))
                self.assertEqual(search(p).claim, 'INCONCLUSIVE')
                expected = (0, 24) if bounds == [0, 24] else None
                self.assertEqual(p.service_model.clock_integer_range('clock.hour'), expected)

    def test_timestamp_and_saved_hour_are_not_discarded(self):
        from explorer.verification.service_model import CatalogRunner
        from explorer.runtime.pause import PauseRunner
        for source in ['x = (#Clock).clock_hour\nif (x >= 24) { break }',
                       'x = (#Clock).clock_timestamp\nall(#Switch).switch_on()',
                       'if ((#Clock).clock_hour >= 24) { x = (#Clock).clock_timestamp }']:
            r = CatalogRunner(PauseRunner(source, True, 3600000), ServiceModel(DEVICES))
            self.assertTrue(reads_clock(r, catalog_ranges=True))

    def test_unknown_wrapper_cannot_get_new_range_proof(self):
        class Wrapper:
            def __init__(self, inner): self.inner = inner
            def __getattr__(self, name): return getattr(self.inner, name)
        self.assertTrue(reads_clock(Wrapper(pair().code_runner), catalog_ranges=True))

    def test_original_programs_execute_unchanged_over_midnight(self):
        p = pair()
        before_ir = copy.deepcopy(p.ir_runner.prog.ins)
        from explorer.verification.timed import unwrap
        before_code = copy.deepcopy(unwrap(p.code_runner).stmts)
        self.assertEqual(search(p).claim, 'EQUIV-FIXPOINT')
        self.assertEqual(p.ir_runner.prog.ins, before_ir)
        self.assertEqual(unwrap(p.code_runner).stmts, before_code)
        for runner in (p.ir_runner, p.code_runner):
            values, gv = {}, {}
            for hour in range(23, 27):
                result = runner.step(values, gv, {}, hour * 3600000, hour == 23)
                self.assertEqual(len(result.actions), 2)
                values, gv = result.vars, result.gv

    def test_horizon_and_resource_cap_are_not_upgraded(self):
        p = pair()
        self.assertEqual(search(p, horizon_ms=3200).claim, 'EQUIV-BOUNDED')
        result = timed_product(p.ir_runner, p.code_runner, input_domains={}, max_transitions=1)
        self.assertEqual(result.claim, 'INCONCLUSIVE')

    def test_clock_override_is_still_rejected(self):
        p = pair()
        with self.assertRaises(ValueError):
            timed_product(p.ir_runner, p.code_runner, input_domains={'clock.hour': [24]})


if __name__ == '__main__':
    unittest.main()
