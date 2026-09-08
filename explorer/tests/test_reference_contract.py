"""Reference repair and upper-validator regressions under the actual catalog."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from explorer.verification.gate import gate_pair, prepare_pair, pair_input_domains
from explorer.runtime.interp import Unsupported
from timeline_ir.catalog import load_catalog
from timeline_ir.timeline_ir import validate_ir_against_catalog, IRValidationError

ROOT = Path(__file__).resolve().parents[2]
IDS = ('C01_006', 'C01_017', 'C14_001', 'C14_005', 'C14_006', 'C03_002')


def rows():
    with (ROOT / 'dataset.csv').open() as f:
        return {f"{r['category_v2']}_{int(r['index']):03d}": r
                for r in csv.DictReader(f)}


def cloud():
    r = rows()['C03_002']
    fixture = json.loads((ROOT / 'explorer/eval/fixtures/cloud_available_main_v1.json').read_text())
    return (json.loads(r['ir_gt']), json.loads(r['binding_gt']),
            json.loads(r['connected_devices']), fixture['joi_block'])


class ReferenceContractTests(unittest.TestCase):
    def assert_violation(self, ir, code, catalog=None):
        with self.assertRaises(IRValidationError) as caught:
            validate_ir_against_catalog(ir, catalog if catalog is not None else load_catalog())
        self.assertIn(code, [v.code for v in caught.exception.violations])

    def test_catalog_loader_preserves_both_void_return_encodings(self):
        for return_type in ('VOID', {'type': 'VOID'}):
            data = {'skills': [{'id': 'Test', 'functions': [
                {'id': 'Act', 'arguments': [], 'return_type': return_type}]}]}
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'catalog.json'
                path.write_text(json.dumps(data))
                catalog = load_catalog(str(path))
                ir = {'timeline': [{'op': 'call', 'target': 'Test.Act', 'args': {}, 'var': 'x'}]}
                self.assert_violation(ir, 'void_return_assignment', catalog)
                del ir['timeline'][0]['var']
                validate_ir_against_catalog(ir, catalog)

    def test_upper_validator_catches_all_five_historical_void_assignments(self):
        manifest = json.loads((ROOT / 'explorer/eval/results/contract_fresh_v4_2026-09-07_manifest.json').read_text())
        for c in manifest['cases']:
            if c['id'] in IDS[:-1]:
                with self.subTest(case=c['id']):
                    self.assert_violation(c['payload']['ir'], 'void_return_assignment')
        current = rows()
        for key in IDS:
            validate_ir_against_catalog(json.loads(current[key]['ir_gt']), load_catalog())

    def test_missing_arguments_rejected_in_nested_and_omitted_args(self):
        for args in (None, {}, {'Brightness': 10.0}):
            call = {'op': 'call', 'target': 'Light.MoveToBrightness'}
            if args is not None:
                call['args'] = args
            ir = {'timeline': [{'op': 'if', 'cond': 'true == true', 'then': [call]}]}
            self.assert_violation(ir, 'missing_required_arg')
        ir['timeline'][0]['then'][0]['args'] = {'Brightness': 10.0, 'Rate': 0.0}
        validate_ir_against_catalog(ir, load_catalog())

    def test_cloud_no_argument_read_preserves_two_boolean_actions(self):
        ir, binding, devices, jb = cloud()
        # Put Backup first: singleton selection must still find unique Main.
        devices = dict(reversed(list(devices.items())))
        jb['script'] = jb['script'].replace('#Main #CloudServiceProvider', '#CloudServiceProvider')
        pair = prepare_pair(ir, binding, devices, jb)
        domains = pair_input_domains(pair)
        self.assertEqual(len(domains), 1)
        key = next(iter(domains))
        self.assertTrue(key.startswith('Main_CloudServiceProvider.'))
        self.assertEqual(domains[key], [False, True])
        for available in (False, True):
            for runner in (pair.ir_runner, pair.code_runner):
                result = runner.step({}, {}, {key: available}, 0, first_tick=True)
                self.assertEqual(len(result.actions), int(available))
                if available:
                    self.assertEqual(result.actions[0].target, ('Main_CloudServiceProvider',))
                    self.assertEqual(result.actions[0].args, ('test.png',))
                with self.assertRaises(Unsupported):
                    runner.step({}, {}, {key: None}, 0, first_tick=True)
        result = gate_pair(ir, binding, devices, jb, horizon_ms=3200)
        self.assertEqual(result.verdict, 'EQUIV-BOUNDED', result.notes)

    def test_cloud_wrong_upload_target_has_confirmed_counterexample(self):
        ir, binding, devices, jb = cloud()
        jb['script'] = jb['script'].replace(
            '(#Main #CloudServiceProvider).cloudServiceProvider_uploadFile',
            '(#Backup #CloudServiceProvider).cloudServiceProvider_uploadFile')
        result = gate_pair(ir, binding, devices, jb, horizon_ms=0)
        self.assertEqual(result.verdict, 'DIVERGE', result.notes)
        self.assertTrue(result.confirmed)

    def test_cloud_old_argument_is_rejected_on_either_side(self):
        ir, binding, devices, jb = cloud()
        ir['timeline'][1]['args'] = {'ServiceName': True}
        self.assert_violation(ir, 'arg_not_in_catalog')
        self.assertEqual(gate_pair(ir, binding, devices, jb, horizon_ms=0).verdict, 'REFUSED')
        ir['timeline'][1]['args'] = {}
        jb['script'] = jb['script'].replace('isAvailable()', 'isAvailable(true)')
        self.assertEqual(gate_pair(ir, binding, devices, jb, horizon_ms=0).verdict, 'REFUSED')


if __name__ == '__main__':
    unittest.main()
