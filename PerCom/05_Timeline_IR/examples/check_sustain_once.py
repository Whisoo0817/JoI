"""Check the manuscript example, not the general determinism theorem.

Run from the repository root:
  PYTHONPATH=. python3.12 PerCom/05_Timeline_IR/examples/check_sustain_once.py
"""

import copy
import json
from pathlib import Path
import unittest

from explorer.verification.gate import prepare_pair


EXAMPLE = Path(__file__).with_name("sustain_once.json")
IR = json.loads(EXAMPLE.read_text())


class ManuscriptExample(unittest.TestCase):
    def runner(self):
        devices = {
            "temp": {"category": ["TemperatureSensor"], "tags": ["TemperatureSensor"]},
            "ac": {"category": ["AirConditioner"], "tags": ["AirConditioner"]},
        }
        binding = {"TemperatureSensor": ["temp"], "AirConditioner": ["ac"]}
        # Preparation checks actual catalog names/types and binding. This code
        # only supplies the paired preparation interface; no equivalence claim
        # is made for this unconditional code and the conditional example IR.
        code = {"script": '(#AirConditioner).airconditioner_setairconditionermode("cool")',
                "period": 0, "cron": ""}
        return prepare_pair(IR, binding, devices, code).ir_runner

    def run_history(self, updates, end_ms):
        runner = self.runner()
        values, globals_, trace = {}, {}, []
        held = updates[0]
        for t in range(0, end_ms + 1, 100):
            held = updates.get(t, held)
            before = copy.deepcopy((values, globals_))
            snapshot = {"temp.temperature": held}
            step = runner.step(values, globals_, snapshot, t, t == 0)
            repeat = runner.step(values, globals_, snapshot, t, t == 0)
            self.assertEqual(step, repeat)
            self.assertEqual((values, globals_), before)
            values, globals_ = step.vars, step.gv
            trace.extend((t, a.method, a.args) for a in step.actions)
        return trace

    def test_preparation_catalog_and_body_listing(self):
        draft = EXAMPLE.parents[1] / "PerCom_version.md"
        listing = draft.read_text().split("```json\n", 1)[1].split("```", 1)[0]
        self.assertEqual(json.loads(listing), IR)
        self.runner()

    def test_sustained_true_fires_once(self):
        self.assertEqual(self.run_history({0: 26}, 400000),
                         [(180000, "setairconditionermode", ("cool",))])

    def test_interruption_restarts_duration(self):
        self.assertEqual(self.run_history({0: 26, 120000: 25, 150000: 26}, 400000),
                         [(330000, "setairconditionermode", ("cool",))])

    def test_false_at_deadline_cancels_completion(self):
        self.assertEqual(self.run_history({0: 26, 180000: 25, 180100: 26}, 400000),
                         [(360100, "setairconditionermode", ("cool",))])

    def test_threshold_is_strict(self):
        self.assertEqual(self.run_history({0: 25}, 400000), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
