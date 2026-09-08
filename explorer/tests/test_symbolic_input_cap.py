"""Input-cap fallback preserves scope, semantic checks and evidence labeling."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from explorer.eval.contract_eval import evaluate_case
from explorer.verification.gate import pair_input_domains
from explorer.verification.symbolic import symbolic_input_cap_fallback
from explorer.verification.timed import timed_product
from explorer.tests.test_symbolic_value_flow import ROOT, case, prepared, gate, delayed


class SymbolicInputCapTests(unittest.TestCase):
    def test_real_pm10_full_catalog_is_certified_at_default_cap(self):
        c = case('C01_014')
        p = prepared(c)
        domains = pair_input_domains(p)
        self.assertEqual(sum(map(len, domains.values())), 110004)
        result = gate(c)
        self.assertEqual(result.verdict, 'EQUIV-BOUNDED', result.notes)
        self.assertEqual(result.product.n_steps, 2)
        self.assertTrue(result.product.symbolic_certificate['both_terminated'])

    def test_explicit_domain_cap_does_not_expand_to_full_catalog(self):
        p = prepared(case('C01_014'))
        domains = pair_input_domains(p)
        with patch('explorer.verification.symbolic.symbolic_product', side_effect=AssertionError('scope expanded')):
            result = timed_product(p.ir_runner, p.code_runner, input_domains=domains, horizon_ms=0)
        self.assertEqual(result.verdict, 'UNKNOWN')
        self.assertIsNone(result.symbolic_certificate)
        self.assertEqual(result.n_steps, 0)

    def test_selection_obeys_both_budget_boundaries(self):
        p = prepared(case('C01_014'))
        domains = pair_input_domains(p)
        count = 110004
        for input_cap, transition_cap, expected in ((count, count, False),
                (count - 1, count, True), (count, count - 1, True)):
            self.assertEqual(symbolic_input_cap_fallback(p.ir_runner, p.code_runner, domains,
                max_input_combinations=input_cap, max_transitions=transition_cap), expected)

    def test_same_source_wrong_value_or_read_epoch_is_not_certified(self):
        constant = case('C01_014')
        constant['joi_block']['script'] = constant['joi_block']['script'].replace('Pm10Weather)', '31)')
        for c in (constant, delayed(case('C01_014'), 100, fresh=True)):
            result = gate(c)
            self.assertEqual(result.verdict, 'DIVERGE', result.notes)
            self.assertTrue(result.confirmed)

    def test_unsupported_control_does_not_get_a_symbolic_certificate(self):
        c = case('C01_014')
        read, action = c['joi_block']['script'].split('\n')
        c['joi_block']['script'] = read + '\nif (Pm10Weather > 0) {\n' + action + '\n}'
        p = prepared(c)
        self.assertFalse(symbolic_input_cap_fallback(p.ir_runner, p.code_runner, pair_input_domains(p)))
        result = gate(c)
        self.assertIn(result.verdict, ('INCONCLUSIVE', 'REFUSED'), result.notes)
        if result.product:
            self.assertIsNone(result.product.symbolic_certificate)

    def test_symbolic_transition_cap_still_stops_delayed_execution(self):
        p = prepared(delayed(case('C01_014'), 150))
        result = timed_product(p.ir_runner, p.code_runner, horizon_ms=200, max_transitions=1)
        self.assertEqual(result.verdict, 'UNKNOWN')
        self.assertFalse(result.closed)
        self.assertEqual(result.n_steps, 2)

    def test_development_evaluator_labels_auto_and_explicit_scopes(self):
        c = case('C01_014')
        result = evaluate_case(c)
        self.assertEqual(result['status'], 'SYMBOLIC_CERTIFIED', result)
        self.assertEqual(result['exact']['verdict'], 'NOT_APPLICABLE')
        c['input_domains'] = pair_input_domains(prepared(c))
        result = evaluate_case(c)
        self.assertEqual(result['status'], 'INCOMPLETE', result)
        self.assertIsNone(result['explorer']['symbolic_certificate'])

    def test_frozen_preparation_and_workers_choose_same_cap_fallback(self):
        from explorer.eval import frozen_contract as f
        protocol = json.loads((ROOT / 'explorer/eval/results/contract_recheck_v4_2026-09-07_v1_protocol.json').read_text())
        protocol.update(case_ids=['C01_014'], sources={})
        with tempfile.TemporaryDirectory() as tmp:
            pp, mp = Path(tmp) / 'protocol.json', Path(tmp) / 'manifest.json'
            pp.write_text(json.dumps(protocol))
            f.prepare(SimpleNamespace(protocol=str(pp), output=str(mp)))
            c = json.loads(mp.read_text())['cases'][0]
        self.assertEqual(c['verification_method'], 'symbolic-value-flow-v1')
        self.assertIsNone(c['model']['input_domains'])
        job = {'case': c, 'caps': protocol['caps'], 'limits': protocol['engine_limits']}
        for engine, expected in (('explorer', 'EQUIV'), ('exact', 'NOT_APPLICABLE')):
            process = subprocess.run([sys.executable, '-m', 'explorer.eval.frozen_contract',
                'worker', '--engine', engine], input=json.dumps(job), text=True,
                capture_output=True, cwd=ROOT, check=True)
            result = json.loads(process.stdout)
            self.assertEqual(result['status'], expected, result)


if __name__ == '__main__':
    unittest.main()
