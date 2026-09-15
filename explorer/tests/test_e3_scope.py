import csv
import json
import unittest
from pathlib import Path

from explorer.eval.e3 import ROOT, has_timeout, key_of, load_rows


class E3ScopeTests(unittest.TestCase):
    def test_timeout_feature_excluded_and_source_preserved(self):
        with (Path(ROOT) / 'dataset.csv').open(encoding='utf-8-sig') as f:
            source = [r for r in csv.DictReader(f) if r.get('category_v2') and r.get('ir_gt')]
        excluded = {key_of(r) for r in source if has_timeout(json.loads(r['ir_gt']))}
        self.assertEqual(len(source), 388)
        self.assertEqual(excluded, {f'C26_{i:03d}' for i in range(1, 7)})
        self.assertEqual({key_of(r) for r in load_rows()}, {key_of(r) for r in source} - excluded)

    def test_nested_timeout_and_handler_are_detected(self):
        self.assertTrue(has_timeout({'timeline': [{'then': [{'on_timeout': []}]}]}))
        self.assertFalse(has_timeout({'timeline': [{'args': {'Text': 'timeout'}}]}))
