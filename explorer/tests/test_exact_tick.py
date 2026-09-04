"""Regression tests for the bounded tick-by-tick reference search."""

from __future__ import annotations

from explorer.exact_tick import exact_tick_product
from explorer.ab_eval import summarize, wilson_interval
from explorer.gate import prepare_pair
from explorer.product import product_runners
from explorer.runner import JoiRunner


def _run(a: str, b: str, *, horizon: int = 4,
         domains: dict | None = None, **kwargs):
    return exact_tick_product(
        JoiRunner.from_src(a), JoiRunner.from_src(b),
        period_ms=1000,
        input_domains=domains or {},
        horizon_ticks=horizon,
        **kwargs,
    )


def test_identical_programs_are_bounded_equivalent():
    src = '(#Light).light_on()'
    result = _run(src, src, horizon=3)
    assert result.verdict == "EQUIV_BOUNDED"
    assert result.completed_ticks == 3
    assert result.n_transitions == 3


def test_every_input_history_is_explored_until_the_horizon():
    src = """
seen := false
x = (#ContactSensor).contact
if (x == "open") { seen = true }
if (seen == true) { (#Light).light_on() }
"""
    domains = {"contactsensor.contact": ["closed", "open"]}
    result = _run(src, src, horizon=4, domains=domains)
    assert result.verdict == "EQUIV_BOUNDED"
    assert result.completed_ticks == 4
    assert result.n_input_combinations == 2
    # The concrete oracle retains wire values as well as the persistent latch;
    # it deliberately performs no future-equivalence abstraction.
    assert result.max_frontier == 3


def test_history_dependent_divergence_has_a_concrete_tick_path():
    edge = """
was_open := false
open = (#ContactSensor).contact == "open"
if (open == true and was_open == false) { (#Light).light_on() }
was_open = open
"""
    level = """
open = (#ContactSensor).contact == "open"
if (open == true) { (#Light).light_on() }
"""
    domains = {"contactsensor.contact": ["closed", "open"]}
    result = _run(edge, level, horizon=3, domains=domains)
    assert result.verdict == "DIVERGE"
    assert result.divergence is not None
    assert result.divergence.tick == 1
    assert len(result.divergence.path) == 2


def test_same_tick_action_order_is_observable():
    a = '(#Light).light_on()\n(#Speaker).speaker_speak("done")'
    b = '(#Speaker).speaker_speak("done")\n(#Light).light_on()'
    result = _run(a, b, horizon=1)
    assert result.verdict == "DIVERGE"


def test_resource_exhaustion_is_not_reported_as_equivalence():
    src = '(#Light).light_on()'
    result = _run(src, src, horizon=3, max_transitions=1)
    assert result.verdict == "INCOMPLETE"
    assert "transition cap" in result.notes[0]


def test_explorer_bounded_mode_answers_the_same_horizon_question():
    base = """
n := 0
n = n + 1
if (n >= 3) { (#Light).light_on() }
"""
    late = base.replace("n >= 3", "n >= 4")
    exact_two = _run(base, late, horizon=2)
    bounded_two = product_runners(
        JoiRunner.from_src(base), JoiRunner.from_src(late), 1000,
        max_ticks=2,
    )
    assert exact_two.verdict == "EQUIV_BOUNDED"
    assert bounded_two.verdict == "EQUIV"
    assert bounded_two.bounded_horizon_ticks == 2

    exact_four = _run(base, late, horizon=4)
    bounded_four = product_runners(
        JoiRunner.from_src(base), JoiRunner.from_src(late), 1000,
        max_ticks=4,
    )
    assert exact_four.verdict == "DIVERGE"
    assert bounded_four.verdict == "DIVERGE"


def test_bounded_mode_does_not_merge_distinct_timer_ages():
    """Regression for development sweep C10_002's false-accept candidate."""
    ir = {"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "wait", "cond": 'Fan.FanMode == "high"', "edge": "none"},
        {"op": "delay", "duration": "3 SEC"},
        {"op": "call", "target": "Fan.SetFanMode",
         "args": {"Mode": "low"}},
    ]}
    devices = {
        "Kitchen_Fan": {"category": ["Fan"], "tags": ["Kitchen", "Fan"]},
        "Basement_Fan": {"category": ["Fan"], "tags": ["Basement", "Fan"]},
    }
    block = {
        "script": 'wait until(all(#Fan).fan_fanMode ==| "high")\n'
                  'delay(3 SEC)\nall(#Fan).fan_setFanMode("low")',
        "period": 0,
        "cron": "",
    }
    pair = prepare_pair(ir, {"Fan": ["Kitchen_Fan"]}, devices, block)
    domains = {
        "Basement_Fan.fanmode": ["__other__", "high"],
        "Kitchen_Fan.fanmode": ["__other__", "high"],
    }
    exact = exact_tick_product(
        pair.ir_runner, pair.code_runner, period_ms=pair.period_ms,
        input_domains=domains, horizon_ticks=4,
    )
    optimized = product_runners(
        pair.ir_runner, pair.code_runner, pair.period_ms, max_ticks=4,
    )
    assert exact.verdict == "DIVERGE"
    assert optimized.verdict == "DIVERGE"


def test_zero_errors_still_have_a_nonzero_wilson_upper_bound():
    interval = wilson_interval(0, 100)
    assert interval is not None
    assert interval["rate"] == 0.0
    assert interval["lower_95"] == 0.0
    assert 0.036 < interval["upper_95"] < 0.038


def test_ab_summary_uses_direction_specific_denominators():
    rows = [
        {
            "status": "COMPLETED", "gold_label": "DIVERGE",
            "error_class": None,
            "exact": {"n_transitions": 1},
            "explorer": {"pair_transition_evaluations": 1,
                         "seconds": 0.1},
        },
        {
            "status": "COMPLETED", "gold_label": "EQUIV",
            "error_class": "FALSE_REJECT",
            "exact": {"n_transitions": 2},
            "explorer": {"pair_transition_evaluations": 1,
                         "seconds": 0.2},
        },
        {"status": "UNSUPPORTED", "gold_label": "DIVERGE"},
    ]
    summary = summarize(rows, "digest")
    assert summary["false_accept_wilson_95"]["denominator"] == 1
    assert summary["false_reject_wilson_95"]["denominator"] == 1
    assert summary["false_accepts_A"] == 0
    assert summary["false_rejects_B"] == 1
    assert summary["completed_cases"] == 2
    assert summary["selected_cases"] == 3


def main() -> None:
    tests = sorted((name, obj) for name, obj in globals().items()
                   if name.startswith("test_") and callable(obj))
    for name, test in tests:
        test()
        print(f"PASS {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
