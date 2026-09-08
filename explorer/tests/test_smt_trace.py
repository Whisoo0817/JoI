"""SMT trace preservation, semantic lifting, counterexamples and fail-closed caps."""
import copy
from dataclasses import asdict
import itertools
import json
import math
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import z3

from explorer.runtime import expr as e
from explorer.eval.contract_eval import evaluate_case
from explorer.tests.oracles.exact_timed import exact_timed_product
from explorer.runtime.interp import Unsupported
from explorer.runtime.ir_step import eval_cond, parse_cond, default_to_key
from explorer.verification.product import replay_divergence
from explorer.verification.smt import Context, Incomplete, Input, smt_specs
from explorer.verification.smt_values import SmtNumber, concrete_number, FP
from explorer.tests.test_symbolic_value_flow import case, prepared, gate
from explorer.verification.timed import timed_product


def arithmetic_case(ir_expr='"avg=" + ($A+$B+$C)/3', code_expr='"avg=" + (A+B+C)/3', *, guard=False, count=3):
    c = case()
    c['id'] = 'smt-development'
    template = c['devices']['System_WeatherProvider']
    c['binding'].pop('WeatherProvider')
    reads, code = [], []
    for i, name in enumerate('ABC'[:count]):
        did = f'Weather{i}'
        c['devices'][did] = {**template, 'tags': [did, 'WeatherProvider']}
        c['binding']['WeatherProvider' + (f'#{i+1}' if i else '')] = [did]
        reads.append({'op': 'read', 'var': name, 'src': 'WeatherProvider.TemperatureWeather'})
        code.append(f'{name} = (#{did} #WeatherProvider).weatherProvider_temperatureWeather')
    action = copy.deepcopy(c['ir']['timeline'][-1])
    action['args']['Text'] = 'on' if guard else ir_expr
    tail = {'op': 'if', 'cond': ir_expr, 'then': [action], 'else': []} if guard else action
    c['ir']['timeline'] = c['ir']['timeline'][:1] + reads + [tail]
    c['joi_block']['script'] = '\n'.join(code) + '\n' + (
        f'if ({code_expr}) {{ all(#Speaker).speaker_speak("on") }}' if guard
        else f'all(#Speaker).speaker_speak({code_expr})')
    c['horizon_ms'] = 0
    return c


def run(c, **caps):
    p = prepared(c)
    return timed_product(p.ir_runner, p.code_runner, horizon_ms=c['horizon_ms'], **caps)


class SmtTraceTests(unittest.TestCase):
    def assert_divergence(self, c, **caps):
        r = run(c, **caps)
        self.assertEqual(r.verdict, 'DIVERGE', r.notes)
        p = prepared(c)
        self.assertTrue(all(replay_divergence(p.ir_runner, p.code_runner, d).confirmed for d in r.divergences))
        return r

    def test_three_sensor_average_certifies_without_numeric_enumeration(self):
        r = run(arithmetic_case())
        self.assertEqual(r.claim, 'EQUIV-BOUNDED', r.notes)
        self.assertEqual(r.symbolic_certificate['schema'], 'smt-linear-trace-v1')
        self.assertEqual(len(r.symbolic_certificate['queries']), 0)
        self.assertLess(r.n_steps, 200)
        self.assertTrue(r.symbolic_certificate['complete'])
        json.dumps(asdict(r))

    def test_wrong_average_divisor_has_concrete_counterexample(self):
        self.assert_divergence(arithmetic_case(code_expr='"avg=" + (A+B+C)/2'))

    def test_joint_guard_identical_covers_both_paths(self):
        r = run(arithmetic_case('$A+$B>40', 'A+B>40', guard=True, count=2))
        self.assertEqual(r.verdict, 'EQUIV', r.notes)
        self.assertGreater(len(r.symbolic_certificate['events']), 2)

    def test_wrong_joint_guard_and_boundary_operator_are_replayed(self):
        for code in ('A>40', 'A+B>=40'):
            self.assert_divergence(arithmetic_case('$A+$B>40', code, guard=True, count=2))

    def test_abs_difference_ir_guard_detects_missing_negative_branch(self):
        self.assert_divergence(arithmetic_case('abs($A-$B)>=1', 'A-B>=1', guard=True, count=2))

    def test_integer_algebra_uses_solver_when_terms_are_not_identical(self):
        # Restrict the catalog fixture to INTEGER without changing production.
        c = arithmetic_case('"v=" + ($A+10)', '"v=" + (10+A)', count=1)
        p = prepared(c)
        spec = p.service_model.input_spec('Weather0.temperatureweather')
        spec.update(type='INTEGER', bound=[-10, 10])
        r = timed_product(p.ir_runner, p.code_runner, horizon_ms=0)
        self.assertEqual(r.verdict, 'EQUIV', r.notes)

    def test_integer_guard_rearrangement_has_unsat_path_queries(self):
        c = arithmetic_case('$A+$B>40', 'A>40-B', guard=True, count=2)
        p = prepared(c)
        for key in p.ir_runner.axes.cells:
            p.service_model.input_spec(key).update(type='INTEGER', bound=[0, 100], nullable=False)
        r = timed_product(p.ir_runner, p.code_runner, horizon_ms=0)
        self.assertEqual(r.verdict, 'EQUIV', r.notes)
        queries = r.symbolic_certificate['queries']
        self.assertTrue(queries)
        self.assertTrue(all(q['result'] == 'unsat' for q in queries))
        # Replay saved solver problems independently of the product traversal.
        for query in queries:
            solver = z3.Solver()
            solver.from_string(query['smt2'])
            self.assertEqual(solver.check(), z3.unsat)

    def test_numeric_action_range_requires_universal_inclusion(self):
        c = arithmetic_case(count=1, ir_expr='$A+10', code_expr='A+10')
        c['ir']['timeline'][-1].update(target='Speaker.SetVolume', args={'Volume': '$A+10'})
        c['joi_block']['script'] = c['joi_block']['script'].replace('speaker_speak', 'speaker_setVolume')
        for hi, expected in ((90, 'EQUIV'), (100, 'REFUSED')):
            p = prepared(c)
            p.service_model.input_spec('Weather0.temperatureweather').update(type='INTEGER', bound=[0, hi], nullable=False)
            if expected == 'REFUSED':
                with self.assertRaises(Unsupported):
                    timed_product(p.ir_runner, p.code_runner, horizon_ms=0)
            else:
                r = timed_product(p.ir_runner, p.code_runner, horizon_ms=0)
                self.assertEqual(r.verdict, expected, r.notes)

    def test_string_int_float_and_signed_zero_are_not_collapsed(self):
        for ir, code in (('"v=" + ($A+0)', '"v=" + (A+0.0)'),
                         ('"v=" + ($A*1)', '"v=" + (A+0.0)')):
            self.assert_divergence(arithmetic_case(ir, code, count=1))

    def test_real_number_algebra_does_not_erase_float_rounding(self):
        self.assert_divergence(arithmetic_case(
            '"v=" + (($A+10000000000000000.0)-10000000000000000.0)',
            '"v=" + (A+0.0)', count=1))

    def test_numeric_action_domain_is_checked(self):
        c = arithmetic_case('$A+10', 'A+10', count=1)
        self.assertEqual(gate(c).verdict, 'REFUSED')  # Speaker requires STRING.

    def test_symbolic_text_guard_cannot_use_python_identity_equality(self):
        c = arithmetic_case('("v="+$A)=="v=1"', 'false', guard=True, count=1)
        p = prepared(c)
        exact = exact_timed_product(p.ir_runner, p.code_runner, horizon_ms=0,
            input_domains={k: [1] for k in p.ir_runner.axes.cells})
        self.assertEqual(exact.verdict, 'DIVERGE')
        self.assertEqual(gate(c).verdict, 'REFUSED')

    def test_symbolic_boolean_arithmetic_cannot_turn_typeerror_into_none(self):
        c = arithmetic_case('"v="+(($A>0)-1)', '"v="', count=1)
        read = c['joi_block']['script'].split('\n')[0]
        c['joi_block']['script'] = read + '\nif(A==null) { all(#Speaker).speaker_speak("v=-1") } else { all(#Speaker).speaker_speak("v=") }'
        p = prepared(c)
        exact = exact_timed_product(p.ir_runner, p.code_runner, horizon_ms=0,
            input_domains={k: [1] for k in p.ir_runner.axes.cells})
        self.assertEqual(exact.verdict, 'DIVERGE')
        self.assertEqual(gate(c).verdict, 'REFUSED')

    def test_non_numeric_input_fallback_is_not_silently_enabled(self):
        c = case('C01_018')
        c['joi_block']['script'] += '\nx = GetMenu * 2'
        p = prepared(c)
        self.assertIsNone(smt_specs(p.ir_runner, p.code_runner))
        self.assertEqual(gate(c).verdict, 'REFUSED')

    def test_nonlinear_dynamic_divisor_modulo_and_loop_stay_refused(self):
        for ir, code in (('$A*$B', 'A*B'), ('$A/$B', 'A/B'), ('$A%3', 'A%3')):
            c = arithmetic_case('"v=" + (' + ir + ')', '"v=" + (' + code + ')', count=2)
            self.assertEqual(gate(c).verdict, 'REFUSED')
        c = arithmetic_case()
        c['joi_block']['script'] += '\nloop (true) { A = A+1 }'
        self.assertEqual(gate(c).verdict, 'REFUSED')

    def test_periodic_refused_but_terminated_paths_need_no_horizon(self):
        c = arithmetic_case()
        c['joi_block']['period'] = 100
        self.assertEqual(gate(c).verdict, 'REFUSED')
        c = arithmetic_case()
        c['horizon_ms'] = None
        r = run(c)
        self.assertEqual(r.claim, 'EQUIV-FIXPOINT')
        self.assertTrue(r.symbolic_certificate['both_terminated'])
        self.assertEqual(r.symbolic_certificate['closure_kind'], 'all-paths-terminated')

    def test_explicit_domains_and_initial_gv_are_not_expanded(self):
        c = arithmetic_case()
        p = prepared(c)
        domains = {k: [1] for k in p.ir_runner.axes.cells}
        with patch('explorer.verification.smt.smt_product', side_effect=AssertionError('scope expansion')):
            with self.assertRaises(Unsupported):
                timed_product(p.ir_runner, p.code_runner, input_domains=domains, horizon_ms=0)
            with self.assertRaises(Unsupported):
                timed_product(p.ir_runner, p.code_runner, initial_gv_domains={'x': [0]}, horizon_ms=0)

    def test_state_transition_and_query_caps_never_certify(self):
        for caps in ({'max_states': 1}, {'max_transitions': 1}):
            r = run(arithmetic_case(), **caps)
            self.assertEqual(r.verdict, 'UNKNOWN')
            self.assertFalse(r.closed)
            self.assertFalse(r.symbolic_certificate['complete'])
        ctx = Context(100, 1000, 1)
        self.assertIsNotNone(ctx.solve(z3.Int('q') == 1))
        with self.assertRaises(Incomplete): ctx.solve(z3.Int('q') == 2)

    def test_unknown_solver_without_witness_never_certifies(self):
        c = arithmetic_case('$A+$B>40', 'B+A>40', guard=True, count=2)
        with patch.object(Context, 'solve', side_effect=Incomplete('forced unknown')):
            r = run(c)
        self.assertEqual(r.verdict, 'UNKNOWN')
        self.assertFalse(r.closed)

    def test_same_captured_epoch_survives_delay_and_fresh_read_differs(self):
        for delay in (50, 100, 150):
            c = arithmetic_case('"v=" + ($A+1)', '"v=" + (A+1)', count=1)
            c['ir']['timeline'].insert(-1, {'op': 'delay', 'duration': f'{delay} MSEC'})
            c['joi_block']['script'] = f'delay({delay} MSEC)\n' + c['joi_block']['script']
            c['horizon_ms'] = delay
            r = run(c)
            if delay < 100:
                self.assertEqual(r.verdict, 'EQUIV', r.notes)
            else:
                self.assertEqual(r.verdict, 'DIVERGE', r.notes)

    def test_inclusive_horizon_observes_timing_difference(self):
        c = arithmetic_case(count=1, ir_expr='"v=" + ($A+1)', code_expr='"v=" + (A+1)')
        c['ir']['timeline'].insert(-1, {'op': 'delay', 'duration': '100 MSEC'})
        read, action = c['joi_block']['script'].split('\n')
        c['joi_block']['script'] = read + '\ndelay(101 MSEC)\n' + action
        c['horizon_ms'] = 99
        self.assertEqual(run(c).verdict, 'EQUIV')
        c['horizon_ms'] = 100
        self.assert_divergence(c)

    def test_wait_carries_full_history_and_resumes_at_input_event(self):
        c = arithmetic_case('$A+$B>40', 'A+B>40', guard=True, count=2)
        action = c['ir']['timeline'][-1]['then'][0]
        c['ir']['timeline'] = c['ir']['timeline'][:1] + [
            {'op': 'wait', 'cond': 'WeatherProvider.TemperatureWeather + WeatherProvider.TemperatureWeather > 40'}, action]
        c['joi_block']['script'] = 'wait until ((#Weather0 #WeatherProvider).weatherProvider_temperatureWeather + (#Weather1 #WeatherProvider).weatherProvider_temperatureWeather > 40)\nall(#Speaker).speaker_speak("on")'
        c['horizon_ms'] = 100
        r = run(c)
        self.assertEqual(r.verdict, 'EQUIV', r.notes)
        self.assertTrue(any(e['offset_ms'] == 100 for e in r.symbolic_certificate['events']))

    def test_fanout_order_target_and_multiplicity_are_preserved(self):
        c = arithmetic_case(count=1, ir_expr='"v=" + ($A+1)', code_expr='"v=" + (A+1)')
        c['binding']['Speaker'].reverse()
        self.assertEqual(run(c).verdict, 'EQUIV')
        c['joi_block']['script'] += '\n' + c['joi_block']['script'].split('\n')[-1]
        self.assert_divergence(c)

    def test_development_evaluator_labels_smt_separately_from_exact_oracle(self):
        r = evaluate_case(arithmetic_case())
        self.assertEqual(r['status'], 'SYMBOLIC_CERTIFIED', r)
        self.assertEqual(r['verification_method'], 'smt-linear-trace-v1')
        self.assertEqual(r['exact']['verdict'], 'NOT_APPLICABLE')

    def test_frozen_selection_and_separate_workers(self):
        from explorer.eval import frozen_contract as f
        from explorer.tests.test_symbolic_value_flow import ROOT
        protocol = json.loads((ROOT / 'explorer/eval/results/contract_recheck_v4_2026-09-07_v2_protocol.json').read_text())
        protocol.update(case_ids=['C01_006'], sources={})
        with tempfile.TemporaryDirectory() as tmp:
            pp, mp = Path(tmp) / 'protocol.json', Path(tmp) / 'manifest.json'
            pp.write_text(json.dumps(protocol))
            f.prepare(SimpleNamespace(protocol=str(pp), output=str(mp)))
            selected = json.loads(mp.read_text())['cases'][0]
        self.assertEqual(selected['verification_method'], 'smt-linear-trace-v1')
        self.assertIsNone(selected['model']['input_domains'])
        # A real old arithmetic case is eligible but emits an invalid channel
        # at the domain minimum. Same invalid ACTIONs must not be certified.
        fixtures = [(selected, 'REFUSED')]
        avg = arithmetic_case()
        fixtures.append(({'payload': {k: avg[k] for k in ('ir', 'binding', 'devices', 'joi_block')},
                         'verification_method': 'smt-linear-trace-v1',
                         'model': {'input_domains': None, 'horizon_ms': 0}}, 'EQUIV'))
        for fixture, expected in fixtures:
            job = {'case': fixture, 'caps': protocol['caps'], 'limits': protocol['engine_limits']}
            for engine, want in (('explorer', expected), ('exact', 'NOT_APPLICABLE')):
                result = subprocess.run([sys.executable, '-m', 'explorer.eval.frozen_contract', 'worker', '--engine', engine],
                    input=json.dumps(job), text=True, capture_output=True, cwd=ROOT, check=True)
                self.assertEqual(json.loads(result.stdout)['status'], want, result.stdout)

    def test_exact_small_domain_crosscheck(self):
        for bad in (False, True):
            c = arithmetic_case('$A+$B>40', 'A>40' if bad else 'A+B>40', guard=True, count=2)
            p = prepared(c)
            domains = {k: [None, 0, 20, 20.0, 20.1, 40] for k in p.ir_runner.axes.cells}
            exact = exact_timed_product(p.ir_runner, p.code_runner, input_domains=domains, horizon_ms=0)
            self.assertEqual(exact.verdict, 'DIVERGE' if bad else 'EQUIV_BOUNDED')
            self.assertEqual(run(c).verdict, 'DIVERGE' if bad else 'EQUIV')

    def test_concrete_lift_matches_both_interpreters_and_binary64(self):
        ctx = Context(100, 1000, 100)
        expressions = ['(A+B)/3', '(A-B)*2', 'A/(-3)', 'A+0.0', 'abs(A-B)']
        values = [None, -1, 0, 1, -0.0, 0.0, 0.1, 0.2, 1.0]
        checked = 0
        for expression, (a, b) in itertools.product(expressions, itertools.product(values, repeat=2)):
            ast = parse_cond(expression, default_to_key)
            concrete = eval_cond(ast, {'A': a, 'B': b}, {})
            symbolic = {}
            for key, val in (('A', a), ('B', b)):
                symbolic[key] = None if val is None else SmtNumber(ctx,
                    z3.IntVal(val) if type(val) is int else z3.FPVal(val, FP),
                    'int' if type(val) is int else 'float', 2, True)
            lifted = eval_cond(ast, symbolic, {})
            if isinstance(lifted, SmtNumber):
                lifted.dependent = False
                lifted = concrete_number(lifted)
            expected = e.evaluate(e.parse(expression), e.EvalContext({}, {'A': a, 'B': b}, {}))
            self.assertEqual(type(lifted), type(concrete), (expression, a, b))
            self.assertEqual(lifted, concrete, (expression, a, b))
            self.assertEqual(concrete, expected, (expression, a, b))
            if type(lifted) is float:
                self.assertEqual(struct.pack('>d', lifted), struct.pack('>d', concrete))
            checked += 1
        self.assertEqual(checked, 405)

    def test_input_grid_representation_round_trip(self):
        ctx = Context(100, 1000, 100)
        inp = Input(ctx, 'sensor.temperature', 0, {'type': 'DOUBLE', 'bound': [-1, 1]})
        for kind, n, neg in itertools.product([0, 1, 2], [-10, -1, 0, 1, 10], [False, True]):
            ctx.known = {(inp.kind == 0).sexpr(): kind == 0, (inp.kind == 2).sexpr(): kind == 2}
            term = inp.force()
            solver = z3.Solver()
            solver.add(*ctx.domains.values(), inp.kind == kind, inp.n == n, inp.negzero == neg)
            if kind == 1 and n % 10:
                self.assertEqual(solver.check(), z3.unsat)
                continue
            self.assertEqual(solver.check(), z3.sat)
            val = inp.concrete(solver.model())
            if term is None:
                self.assertIsNone(val)
            else:
                evaluated = solver.model().eval(term.term, model_completion=True)
                got = concrete_number(SmtNumber(ctx, evaluated, term.kind, 2, False))
                self.assertEqual(type(got), type(val))
                self.assertEqual(str(got), str(val))

    def test_comparison_lift_matches_both_interpreters(self):
        ctx = Context(100, 1000, 100)
        values = [None, -1, 0, 1, -0.0, 0.0, 0.1, 0.2, 1.0]
        checked = 0
        for op, (a, b) in itertools.product(['==', '!=', '<', '<=', '>', '>='], itertools.product(values, repeat=2)):
            expression = 'A' + op + 'B'
            ast = parse_cond(expression, default_to_key)
            symbolic = {key: None if value is None else SmtNumber(ctx,
                z3.IntVal(value) if type(value) is int else z3.FPVal(value, FP),
                'int' if type(value) is int else 'float', 2, True)
                for key, value in (('A', a), ('B', b))}
            expected = eval_cond(ast, {'A': a, 'B': b}, {})
            self.assertEqual(bool(eval_cond(ast, symbolic, {})), expected, (op, a, b))
            self.assertEqual(bool(e.evaluate(e.parse(expression), e.EvalContext({}, symbolic, {}))), expected)
            checked += 1
        self.assertEqual(checked, 486)


if __name__ == '__main__': unittest.main()
