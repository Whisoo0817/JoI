import unittest

from explorer.tests.test_contract import pair, timeline, call
from explorer.verification.product import replay_divergence
from explorer.verification.timed import timed_product


class D3BlockingEdgeTests(unittest.TestCase):
    def test_short_event_between_wrapper_ticks_is_observed(self):
        ir = timeline({"op": "cycle", "period": "1 SEC", "body": [
            {"op": "wait", "cond": "Switch.State == true", "edge": "rising"},
            call(),
        ]})
        binding = {"Switch": ["living"]}
        good = (
            "triggered := false\n"
            "if (triggered == true) {\n"
            "    wait until(not (#Switch #LivingRoom).switch_state)\n"
            "    triggered = false\n"
            "}\n"
            "wait until((#Switch #LivingRoom).switch_state)\n"
            "(#Switch #LivingRoom).switch_on()\n"
            "triggered = true"
        )
        prepared = pair(ir, good, period=1000, binding=binding)
        domain = {"living.state": [False, True]}
        result = timed_product(prepared.ir_runner, prepared.code_runner,
                               input_domains=domain)
        self.assertEqual(result.claim, "EQUIV-FIXPOINT")
        self.assertTrue(result.closed)

        tick_polled = (
            "triggered := false\n"
            "if ((#Switch #LivingRoom).switch_state) {\n"
            "    if (triggered == false) {\n"
            "        (#Switch #LivingRoom).switch_on()\n"
            "        triggered = true\n"
            "    }\n"
            "} else { triggered = false }"
        )
        faulty = pair(ir, tick_polled, period=1000, binding=binding)
        divergence = timed_product(faulty.ir_runner, faulty.code_runner,
                                   input_domains=domain, horizon_ms=1100)
        self.assertEqual(divergence.verdict, "DIVERGE")
        self.assertTrue(replay_divergence(faulty.ir_runner, faulty.code_runner,
                                         divergence.divergences[0]).confirmed)


if __name__ == "__main__":
    unittest.main()
