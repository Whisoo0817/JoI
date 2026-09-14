"""Binding decision (whisoo 2026-09-14, E2 BINDING_DECISION_2026-09-14.md B1/B2).

Selectors, device counts, tags and any/all do not decide EQUIV/DIVERGE; order of
separately written IR calls still does.

Run: python -m explorer.tests.test_binding_decision
"""
from __future__ import annotations

from explorer.runtime.interp import Action
from explorer.tests.synthetic_gate import prepare_pair
from explorer.verification.observation import actions_observation
from explorer.verification.product import replay_divergence
from explorer.verification.timed import timed_product

DEVICES = {
    "hall1": {"category": ["Light", "Switch"], "tags": ["Hallway", "Light"]},
    "hall2": {"category": ["Light", "Switch"], "tags": ["Hallway", "Light"]},
    "lr1": {"category": ["Light", "Switch"], "tags": ["LivingRoom", "Light"]},
    "lr2": {"category": ["Light", "Switch"], "tags": ["LivingRoom", "Light"]},
    "kitchen": {"category": ["Light", "Switch"], "tags": ["Kitchen", "Light"]},
    "zone1": {"category": ["Valve"], "tags": ["Zone1", "Valve"]},
    "zone2": {"category": ["Valve"], "tags": ["Zone2", "Valve"]},
    "s1": {"category": ["MotionSensor"], "tags": ["Living", "MotionSensor"]},
    "s2": {"category": ["MotionSensor"], "tags": ["Bedroom", "MotionSensor"]},
}
FOUR = ["hall1", "hall2", "lr1", "lr2"]


def timeline(*steps):
    return {"timeline": [{"op": "start_at", "anchor": "now"}, *steps]}


def verdict(ir, code, binding, **kw):
    p = prepare_pair(ir, binding, DEVICES, {"script": code, "period": 0, "cron": ""})
    result = timed_product(p.ir_runner, p.code_runner, horizon_ms=0, **kw)
    return p, result


def test_device_id_lines_equal_one_bound_call():
    code = "\n".join(f"({'#' + d}).switch_on()" for d in FOUR)
    _, r = verdict(timeline({"op": "call", "target": "Switch.On"}), code, {"Switch": FOUR}, input_domains={})
    assert r.verdict in ("EQUIV", "EQUIV_BOUNDED"), r.verdict


def test_wider_selector_uses_binding():
    _, r = verdict(timeline({"op": "call", "target": "Switch.On"}), "all(#Light).switch_on()",
                   {"Switch": ["kitchen"]}, input_domains={})
    assert r.verdict in ("EQUIV", "EQUIV_BOUNDED"), r.verdict


def test_order_of_separate_calls_still_counts():
    ir = timeline({"op": "call", "target": "Valve.Close"}, {"op": "call", "target": "Valve.Close"})
    p, r = verdict(ir, "(#Zone2 #Valve).valve_close()\n(#Zone1 #Valve).valve_close()",
                   {"Valve": ["zone1"], "Valve#2": ["zone2"]}, input_domains={})
    assert r.verdict == "DIVERGE", r.verdict
    assert replay_divergence(p.ir_runner, p.code_runner, r.divergences[0]).confirmed


def test_missing_call_still_counts():
    ir = timeline({"op": "call", "target": "Switch.On"}, {"op": "call", "target": "Switch.Off"})
    _, r = verdict(ir, "all(#Light).switch_on()", {"Switch": FOUR}, input_domains={})
    assert r.verdict == "DIVERGE", r.verdict


def test_binding_quantifier_decides_reads():
    ir = timeline({"op": "if", "cond": "MotionSensor.Motion == true",
                   "then": [{"op": "call", "target": "Switch.On"}], "else": []})
    code = "if ((#Living #MotionSensor).motionSensor_motion == true) {\n(#Kitchen #Light).switch_on()\n}"
    _, r = verdict(ir, code, {"MotionSensor": {"any": ["s1", "s2"]}, "Switch": ["kitchen"]})
    assert r.verdict in ("EQUIV", "EQUIV_BOUNDED", "EQUIV-FIXPOINT"), r.verdict


def test_duplicate_call_still_counts():
    code = "all(#Light).switch_on()\nall(#Light).switch_on()"
    _, r = verdict(timeline({"op": "call", "target": "Switch.On"}), code, {"Switch": ["hall1", "hall2"]}, input_domains={})
    assert r.verdict == "DIVERGE", r.verdict


def test_partial_selector_uses_binding():
    _, r = verdict(timeline({"op": "call", "target": "Switch.On"}), "(#hall1).switch_on()",
                   {"Switch": ["hall1", "hall2"]}, input_domains={})
    assert r.verdict in ("EQUIV", "EQUIV_BOUNDED"), r.verdict


def test_explicit_joi_quantifier_is_kept():
    ir = timeline({"op": "if", "cond": "MotionSensor.Motion == false",
                   "then": [{"op": "call", "target": "Switch.On"}], "else": []})
    code = "if (not (any(#MotionSensor).motionSensor_motion == true)) {\n(#Kitchen #Light).switch_on()\n}"
    # BOOL inputs only (the synthetic model would also allow a missing value, where the two differ)
    _, r = verdict(ir, code, {"MotionSensor": {"all": ["s1", "s2"]}, "Switch": ["kitchen"]},
                   input_domains={"s1.motion": [False, True], "s2.motion": [False, True]})
    assert r.verdict in ("EQUIV", "EQUIV_BOUNDED", "EQUIV-FIXPOINT"), r.verdict


def test_merge_needs_binding_sets_and_consecutive_calls():
    on = lambda d: Action("switch", "on", (), (d,))
    off = Action("switch", "off", (), ("kitchen",))
    sets = (frozenset(FOUR),)
    split = [on(d) for d in FOUR]
    fan = [Action("switch", "on", (), (d,), (i, 4)) for i, d in enumerate(reversed(FOUR))]
    assert actions_observation(split, sets) == actions_observation(fan, sets)
    assert actions_observation(split) != actions_observation(fan)
    interrupted = [on("hall1"), off, on("hall2"), on("lr1"), on("lr2")]
    assert actions_observation(interrupted, sets) != actions_observation(fan, sets)
    other_args = [Action("light", "movetobrightness", (10, 0), ("hall1",)),
                  Action("light", "movetobrightness", (20, 0), ("hall2",))]
    assert len(actions_observation(other_args, sets)) == 2
    partial = [on("hall1")]
    assert actions_observation(partial, sets) == actions_observation(fan, sets)
    assert actions_observation(split + split, sets) != actions_observation(fan, sets)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")


if __name__ == "__main__":
    main()
