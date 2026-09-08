"""Expected traces and exhaustive-search regressions for the agreed contract.

Run: python3 -m explorer.tests.test_contract
"""
from __future__ import annotations

from explorer.tests.oracles.exact_tick import exact_tick_product
from explorer.tests.oracles.exact_timed import exact_timed_product
from explorer.tests.synthetic_gate import gate_pair, prepare_pair
from explorer.verification.input_model import decimal_domain, validate_domains
from explorer.runtime.interp import Action, Unsupported
from explorer.runtime.ir_step import IrRunner
from explorer.verification.observation import actions_observation
from explorer.runtime.oneshot import OneShotRunner
from explorer.runtime.pause import PauseRunner
from explorer.verification.product import product_runners, replay_divergence
from explorer.runtime.runner import JoiRunner
from explorer.verification.timed import timed_product

T0 = 2_419_200_000
DEVICES = {
    "living": {"category": ["Switch"], "tags": ["Switch", "LivingRoom"]},
    "kitchen": {"category": ["Switch"], "tags": ["Switch", "Kitchen"]},
}


def timeline(*steps):
    return {"timeline": [{"op": "start_at", "anchor": "now"}, *steps]}


def call(method="On"):
    return {"op": "call", "target": f"Switch.{method}"}


def pair(ir, code, *, period=0, binding=None, devices=None):
    return prepare_pair(ir, binding or {"Switch": ["living"]}, devices or DEVICES,
                        {"script": code, "period": period, "cron": ""})


def trace(runner, schedule, *, t0=T0):
    values, gv, result = {}, {}, []
    for index, (offset, inputs) in enumerate(schedule):
        stepped = runner.step(values, gv, inputs, t0 + offset, index == 0)
        values, gv = stepped.vars, stepped.gv
        result.extend((offset, action.method, action.args) for action in stepped.actions)
    return result


def test_fanout_reversal_is_equal_across_all_comparators():
    p = pair(timeline(call()), 'all(#Switch).switch_on()', binding={"Switch": ["kitchen", "living"]})
    for search in (timed_product, exact_timed_product):
        result = search(p.ir_runner, p.code_runner, input_domains={}, horizon_ms=0)
        assert result.verdict in ("EQUIV", "EQUIV_BOUNDED")
    assert exact_tick_product(p.ir_runner, p.code_runner, period_ms=100,
                             input_domains={}, horizon_ticks=1).verdict == "EQUIV_BOUNDED"
    assert product_runners(p.ir_runner, p.code_runner, 100, max_ticks=1).verdict == "EQUIV"


def test_sequential_calls_are_not_a_parallel_fanout():
    p = pair(timeline(call()), '(#Switch #LivingRoom).switch_on()\n(#Switch #Kitchen).switch_on()',
             binding={"Switch": ["living", "kitchen"]})
    result = timed_product(p.ir_runner, p.code_runner, input_domains={}, horizon_ms=0)
    assert result.verdict == "DIVERGE"
    assert replay_divergence(p.ir_runner, p.code_runner, result.divergences[0]).confirmed


def test_overlap_preserves_per_device_order_and_duplicates():
    def grouped(sequence):
        return [Action("switch", method, (), (device,), (i, len(sequence)))
                for i, (device, method) in enumerate(sequence)]
    a = grouped([("living", "on"), ("kitchen", "on"), ("living", "off")])
    b = grouped([("kitchen", "on"), ("living", "on"), ("living", "off")])
    bad = grouped([("living", "off"), ("living", "on"), ("kitchen", "on")])
    assert actions_observation(a) == actions_observation(b)
    assert actions_observation(a) != actions_observation(bad)
    duplicate = grouped([("living", "on"), ("living", "on")])
    assert actions_observation(duplicate) != actions_observation([Action("switch", "on", (), ("living",))])


def test_repeated_fanouts_keep_call_boundaries():
    group = [Action("switch", "on", (), (name,), (i, 2))
             for i, name in enumerate(("living", "kitchen"))]
    assert len(actions_observation(group + group)) == 2
    assert actions_observation(group + group) != actions_observation(group)


def test_decimal_lattice_and_non_lattice_thresholds():
    from explorer.analysis.explore import reps_from_preds
    assert decimal_domain(9.8, 10) == [9.8, 9.9, 10.0]
    reps = reps_from_preds([(">", 10.01), ("<", 10.09)])
    assert not any(10.01 < value < 10.09 for value in reps)
    assert all(round(value * 10) == value * 10 for value in reps)
    try:
        validate_domains({"temperature": [9.99]})
    except ValueError:
        pass
    else:
        raise AssertionError("off-lattice input accepted")


def test_speaker_counterexample_requires_domain_and_finds_9_9():
    ir = timeline({"op": "read", "src": "TemperatureSensor.Temperature", "var": "t"},
        {"op": "if", "cond": "$t < 10", "then": [
            {"op": "call", "target": "Speaker.Speak", "args": {"text": "$t"}}]})
    binding = {"TemperatureSensor": ["sensor"], "Speaker": ["speaker"]}
    devices = {"sensor": {"category": ["TemperatureSensor"], "tags": ["TemperatureSensor"]},
               "speaker": {"category": ["Speaker"], "tags": ["Speaker"]}}
    source = 't = (#TemperatureSensor).temperatureSensor_temperature\nu = t\nif (u < 10) { (#Speaker).speaker_speak(9) }'
    block = {"script": source, "period": 0}
    refused = gate_pair(ir, binding, devices, block, horizon_ms=0)
    assert refused.verdict == "REFUSED" and "explicit input domain" in str(refused.notes)
    result = gate_pair(ir, binding, devices, block,
        input_domains={"sensor.temperature": [9.0, 9.9, 10.0]}, horizon_ms=0)
    assert result.verdict == "DIVERGE" and result.confirmed
    assert result.product.divergences[0].input_["sensor.temperature"] == 9.9
    good = {**block, "script": source.replace('speaker_speak(9)', 'speaker_speak(u)')}
    assert gate_pair(ir, binding, devices, good,
        input_domains={"sensor.temperature": [9.0, 9.9, 10.0]}, horizon_ms=200).verdict == "EQUIV-BOUNDED"


def test_existing_arithmetic_refusal_is_not_overridden_by_domains():
    a = PauseRunner('t = (#TemperatureSensor).temperatureSensor_temperature\n(#Speaker).speaker_speak(t * 2)', repeat=False)
    try:
        timed_product(a, a, input_domains={"temperaturesensor.temperature": [0, 1]}, horizon_ms=0)
    except Unsupported as error:
        assert "arith-arg" in str(error)
    else:
        raise AssertionError("arithmetic support was silently expanded")


def test_exact_delay_and_completion_relative_period_expected_trace():
    ir = timeline({"op": "cycle", "period": "1 SEC", "body": [call(),
                  {"op": "delay", "duration": "1.5 SEC"}, call("Off")]})
    p = pair(ir, '(#Switch #LivingRoom).switch_on()\ndelay(1.5 SEC)\n(#Switch #LivingRoom).switch_off()', period=1000)
    schedule = [(t, {}) for t in (0, 1000, 1499, 1500, 2000, 2499, 2500, 4000, 5000)]
    expected = [(0, "on", ()), (1500, "off", ()), (2500, "on", ()), (4000, "off", ()), (5000, "on", ())]
    assert trace(p.ir_runner, schedule) == expected
    assert trace(p.code_runner, schedule) == expected
    result = timed_product(p.ir_runner, p.code_runner, input_domains={})
    assert result.claim == "EQUIV-FIXPOINT" and result.closed


def test_150ms_delay_is_not_rounded_to_200ms():
    p = pair(timeline({"op": "delay", "duration": "150 MSEC"}, call()),
             'delay(200 MSEC)\n(#Switch #LivingRoom).switch_on()')
    fast = timed_product(p.ir_runner, p.code_runner, input_domains={}, horizon_ms=200)
    exact = exact_timed_product(p.ir_runner, p.code_runner, input_domains={}, horizon_ms=200)
    assert fast.verdict == exact.verdict == "DIVERGE"
    assert sum(d for _, d in fast.divergences[0].path) + fast.divergences[0].dwell_ms == 150
    assert exact.divergence_ms == 150
    assert replay_divergence(p.ir_runner, p.code_runner, fast.divergences[0]).confirmed


def test_zero_origin_and_zero_delay_do_not_add_a_tick():
    for milliseconds in (0, 150):
        ir = IrRunner(timeline({"op": "delay", "duration": f"{milliseconds} MSEC"}, call()))
        source = f'delay({milliseconds} MSEC)\n(#Switch).switch_on()'
        for runner in (ir, OneShotRunner(source), PauseRunner(source, repeat=False)):
            got = trace(runner, [(0, {}), (100, {}), (150, {})], t0=0)
            assert [t for t, _, _ in got] == [milliseconds]


def test_input_wins_sustained_condition_expiry_tie():
    runner = IrRunner(timeline({"op": "wait", "cond": "MotionSensor.Motion == false", "for": "200 MSEC"}, call("Off")))
    schedule = [(0, {"motionsensor.motion": False}), (100, {"motionsensor.motion": False}),
                (200, {"motionsensor.motion": True}), (300, {"motionsensor.motion": False}),
                (500, {"motionsensor.motion": False})]
    assert trace(runner, schedule) == [(500, "off", ())]


def test_sustain_expiry_between_input_ticks_uses_held_input():
    ir = IrRunner(timeline({"op": "wait", "cond": "MotionSensor.Motion == false", "for": "150 MSEC"}, call("Off")))
    silent = IrRunner(timeline({"op": "wait", "cond": "false"}))
    domains = {"motionsensor.motion": [False]}
    fast = timed_product(ir, silent, input_domains=domains, horizon_ms=200)
    exact = exact_timed_product(ir, silent, input_domains=domains, horizon_ms=200)
    assert exact.divergence_ms == 150
    divergence = fast.divergences[0]
    assert sum(ms for _, ms in divergence.path) + divergence.dwell_ms == 150
    assert replay_divergence(ir, silent, divergence).confirmed


def test_rising_initial_true_once_and_later_false_true():
    runner = IrRunner(timeline({"op": "cycle", "period": "100 MSEC", "body": [
        {"op": "wait", "cond": "MotionSensor.Motion == true", "edge": "rising"}, call()]}))
    schedule = [(0, True), (100, True), (200, False), (300, True), (400, True)]
    assert trace(runner, [(t, {"motionsensor.motion": value}) for t, value in schedule]) == [(0, "on", ()), (300, "on", ())]


def test_termination_alone_is_not_divergence_and_future_actions_survive():
    terminated = JoiRunner.from_src('break')
    silent = JoiRunner.from_src('x := false')
    assert exact_tick_product(terminated, silent, period_ms=100,
                             input_domains={}, horizon_ticks=4).verdict == "EQUIV_BOUNDED"
    assert product_runners(terminated, silent, 100, max_ticks=4).verdict == "EQUIV"
    delayed = JoiRunner.from_src('n := 0\nn = n + 1\nif (n >= 3) { (#Switch).switch_on() }')
    result = product_runners(terminated, delayed, 100, max_ticks=4)
    assert result.verdict == "DIVERGE"
    assert replay_divergence(terminated, delayed, result.divergences[0]).confirmed


def test_timed_termination_vs_wait_and_later_action():
    done = OneShotRunner('(#Switch).switch_on()')
    waiting = OneShotRunner('(#Switch).switch_on()\nwait until(false)')
    assert timed_product(done, waiting, input_domains={}).claim == "EQUIV-FIXPOINT"
    later = OneShotRunner('(#Switch).switch_on()\ndelay(150 MSEC)\n(#Switch).switch_off()')
    result = timed_product(done, later, input_domains={}, horizon_ms=200)
    assert result.verdict == "DIVERGE"
    assert replay_divergence(done, later, result.divergences[0]).confirmed


def test_input_grid_does_not_change_at_a_timer_only_event():
    source = 'delay(150 MSEC)\nif ((#MotionSensor).motionSensor_motion == true) { (#Switch).switch_on() }'
    runner = OneShotRunner(source)
    result = timed_product(runner, OneShotRunner('wait until(false)'),
                           input_domains={"motionsensor.motion": [False, True]}, horizon_ms=200)
    dv = result.divergences[0]
    assert dv.input_ == dv.path[-1][0]
    assert sum(d for _, d in dv.path) + dv.dwell_ms == 150


def test_all_initial_and_simultaneous_input_states_are_explored():
    source = 'wait until((#A).a_on == true and (#B).b_on == true)\n(#Switch).switch_on()'
    runner = OneShotRunner(source)
    domains = {"a.on": [False, True], "b.on": [False, True]}
    result = timed_product(runner, OneShotRunner('wait until(false)'), input_domains=domains, horizon_ms=0)
    assert result.verdict == "DIVERGE"
    assert result.divergences[0].input_ == {"a.on": True, "b.on": True}


def test_caps_and_bounded_results_are_distinct_from_fixpoint():
    runner = OneShotRunner('delay(150 MSEC)\n(#Switch).switch_on()')
    cap = timed_product(runner, runner, input_domains={}, max_transitions=1)
    assert cap.claim == "INCONCLUSIVE" and not cap.closed
    bounded = timed_product(runner, runner, input_domains={}, horizon_ms=100)
    assert bounded.claim == "EQUIV-BOUNDED"
    assert exact_timed_product(runner, runner, input_domains={}, horizon_ms=200,
                               max_transitions=1).verdict == "INCOMPLETE"


def test_event_search_matches_millisecond_oracle_on_delay_mutations():
    for left, right in ((0, 0), (50, 50), (50, 100), (150, 150), (150, 200)):
        a = OneShotRunner(f'delay({left} MSEC)\n(#Switch).switch_on()')
        b = OneShotRunner(f'delay({right} MSEC)\n(#Switch).switch_on()')
        fast = timed_product(a, b, input_domains={}, horizon_ms=250)
        exact = exact_timed_product(a, b, input_domains={}, horizon_ms=250)
        assert (fast.verdict == "DIVERGE") == (exact.verdict == "DIVERGE")


def test_event_search_covers_history_dependent_wait_delay_combinations():
    sources = [
        'wait until((#MotionSensor).motionSensor_motion == true)\ndelay(50 MSEC)\n(#Switch).switch_on()',
        'wait until((#MotionSensor).motionSensor_motion == true)\ndelay(150 MSEC)\n(#Switch).switch_on()',
        'delay(50 MSEC)\nwait until((#MotionSensor).motionSensor_motion == true)\n(#Switch).switch_on()',
    ]
    domains = {"motionsensor.motion": [False, True]}
    for left in sources:
        for right in sources:
            a, b = OneShotRunner(left), OneShotRunner(right)
            fast = timed_product(a, b, input_domains=domains, horizon_ms=250)
            exact = exact_timed_product(a, b, input_domains=domains, horizon_ms=250)
            assert (fast.verdict == "DIVERGE") == (exact.verdict == "DIVERGE")
            if fast.divergences:
                assert replay_divergence(a, b, fast.divergences[0]).confirmed


def test_clock_boundary_between_input_ticks_is_not_skipped():
    a = OneShotRunner('wait until(clock.timestamp >= 2419201)\n(#Switch).switch_on()')
    b = OneShotRunner('wait until(false)')
    fast = timed_product(a, b, input_domains={}, horizon_ms=1050, input_step_ms=700)
    exact = exact_timed_product(a, b, input_domains={}, horizon_ms=1050, input_step_ms=700)
    assert exact.divergence_ms == 1000
    dv = fast.divergences[0]
    assert sum(d for _, d in dv.path) + dv.dwell_ms == 1000


def test_nonboolean_initial_gv_and_custom_origin_replay_exactly():
    a = OneShotRunner('x = (#GlobalVariable).globalVariable_getValue("v")\nif (x == 7) { (#Switch).switch_on() }\n(#GlobalVariable).globalVariable_setValue("v", 0)')
    b = OneShotRunner('(#GlobalVariable).globalVariable_setValue("v", 0)')
    result = timed_product(a, b, input_domains={}, initial_gv_domains={"v": [0, 7]},
                           horizon_ms=0, t0_ms=0)
    assert result.verdict == "DIVERGE"
    assert result.divergences[0].initial_gv == {"v": 7}
    assert replay_divergence(a, b, result.divergences[0]).confirmed


def test_argument_types_and_numeric_precision_are_preserved():
    def output(arg):
        return actions_observation([Action("speaker", "speak", (arg,), ("speaker",))])
    assert output(True) != output(1)
    assert output(1.0) == output(1)
    assert output(1.01) != output(1.0)  # inputs' precision is not output rounding


def test_delay_parsing_does_not_truncate_binary_float_error():
    from explorer.runtime.interp import parse
    from explorer.runtime.ir_step import parse_duration
    assert parse('delay(1.001 SEC)')[0].ms == 1001
    assert parse_duration('1.001 SEC') * 1000 == 1001
    for construct in (lambda: parse('delay(0.1 MSEC)'), lambda: parse_duration('0.1 MS')):
        try:
            construct()
        except (ValueError, Unsupported):
            pass
        else:
            raise AssertionError("sub-millisecond duration silently rounded")


def test_timeout_fires_at_exact_deadline():
    a = IrRunner(timeline({"op": "wait", "cond": "false", "timeout": "150 MS", "on_timeout": [call("Off")]}))
    b = OneShotRunner('wait until(false)')
    fast = timed_product(a, b, input_domains={}, horizon_ms=200)
    exact = exact_timed_product(a, b, input_domains={}, horizon_ms=200)
    assert exact.divergence_ms == 150
    assert sum(d for _, d in fast.divergences[0].path) + fast.divergences[0].dwell_ms == 150


def test_bare_wait_and_boolean_composition_keep_all_input_axes():
    silent = OneShotRunner('wait until(false)')
    sources = [
        'wait until((#MotionSensor).motionSensor_motion)',
        'wait until(not (#MotionSensor).motionSensor_motion)',
        'x = (#MotionSensor).motionSensor_motion\ny = x\nwait until(y)',
        'wait until((#MotionSensor).motionSensor_motion and (#A).a_on)',
    ]
    for source in sources:
        runner = OneShotRunner(source + '\n(#Switch).switch_on()')
        assert "motionsensor.motion" in runner.axes.cells
        result = timed_product(runner, silent, horizon_ms=0)
        assert result.verdict == "DIVERGE", source
        assert replay_divergence(runner, silent, result.divergences[0]).confirmed
        try:
            timed_product(runner, silent, input_domains={}, horizon_ms=0)
        except ValueError as error:
            assert "missing keys" in str(error)
        else:
            raise AssertionError("explicit model omitted a required wait input")


def test_truthiness_and_numeric_partition_are_merged_across_programs():
    # The numeric predicate alone has one representative below 10, but the
    # other program must also observe the special false value zero there.
    a = OneShotRunner('if ((#Sensor).sensor_value < 10) { (#Switch).switch_on() }')
    b = OneShotRunner('if ((#Sensor).sensor_value and (#Sensor).sensor_value < 10) { (#Switch).switch_on() }')
    result = timed_product(a, b, horizon_ms=0)
    assert result.verdict == "DIVERGE"
    assert result.divergences[0].input_["sensor.value"] == 0


def test_ir_bare_register_and_all_branch_sources_are_covered():
    runner = IrRunner(timeline(
        {"op": "if", "cond": "A.On", "then": [
            {"op": "read", "src": "B.On", "var": "x"}], "else": [
            {"op": "read", "src": "C.On", "var": "x"}]},
        {"op": "wait", "cond": "$x"}, call()))
    assert set(runner.axes.cells) == {"a.on", "b.on", "c.on"}
    domains = {"a.on": [True], "b.on": [True], "c.on": [False]}
    assert timed_product(runner, OneShotRunner('wait until(false)'),
                         input_domains=domains, horizon_ms=0).verdict == "DIVERGE"


def test_concrete_states_preserve_future_string_conversion():
    for values in ([1, 1.0], [0.0, -0.0], [True, 1]):
        a = OneShotRunner('x = (#Sensor).sensor_value\ndelay(100 MSEC)\n(#Speaker).speaker_speak("" + x)')
        b = OneShotRunner('delay(100 MSEC)\n(#Speaker).speaker_speak("' + str(values[0]) + '")')
        domains = {"sensor.value": values}
        # A hand trace is independent of both search implementations' keys.
        assert trace(a, [(0, {"sensor.value": values[1]}),
                         (100, {"sensor.value": values[0]})])[-1][2] == (str(values[1]),)
        fast = timed_product(a, b, input_domains=domains, horizon_ms=100)
        assert fast.verdict == "DIVERGE"
        assert replay_divergence(a, b, fast.divergences[0]).confirmed
        assert exact_timed_product(a, b, input_domains=domains, horizon_ms=100).verdict == "DIVERGE"
        assert exact_tick_product(a, b, input_domains=domains, period_ms=100,
                                  horizon_ticks=2).verdict == "DIVERGE"
        assert product_runners(a, b, 100, input_domains=domains, max_ticks=2).verdict == "DIVERGE"


def test_holiday_action_flow_is_an_external_boolean_input():
    runners = [OneShotRunner('(#Speaker).speaker_speak(clock.isholiday)'),
               IrRunner(timeline({"op": "call", "target": "Speaker.Speak",
                                  "args": {"text": "$Clock.IsHoliday"}}))]
    for runner in runners:
        assert "clock.isholiday" in runner.axes.observable_reads


def test_ir_derived_clock_guard_does_not_become_an_external_axis():
    runner = IrRunner(timeline({"op": "wait", "cond": "Clock.Timestamp >= 2419201"}, call()))
    assert not runner.axes.cells
    silent = OneShotRunner('wait until(false)')
    fast = timed_product(runner, silent, input_domains={}, horizon_ms=1000, input_step_ms=700)
    assert fast.verdict == "DIVERGE"
    assert sum(d for _, d in fast.divergences[0].path) + fast.divergences[0].dwell_ms == 1000


def test_time_translation_preserves_exact_milliseconds_at_large_origins():
    ir = IrRunner(timeline({"op": "cycle", "period": "1 MSEC", "body": [
        {"op": "delay", "duration": "1 MSEC"}, call()]}))
    code = PauseRunner('delay(1 MSEC)\n(#Switch).switch_on()', repeat=True, period_ms=1)
    for origin in (0, T0, 10**20 + 1):
        for runner in (ir, code):
            got = trace(runner, [(i, {}) for i in range(6)], t0=origin)
            assert [t for t, _, _ in got] == [1, 3, 5]
        result = timed_product(ir, code, input_domains={}, input_step_ms=10,
                               t0_ms=origin)
        assert result.claim == "EQUIV-FIXPOINT"


def test_read_only_internal_timer_names_are_refused():
    for build in (OneShotRunner, lambda src: PauseRunner(src, repeat=False)):
        try:
            build('(#Speaker).speaker_speak(__dstart)')
        except Unsupported as error:
            assert "reserved" in str(error)
        else:
            raise AssertionError("program can observe interpreter-private time")


def main():
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
