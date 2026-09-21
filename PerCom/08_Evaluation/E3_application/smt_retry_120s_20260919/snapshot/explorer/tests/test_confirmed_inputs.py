import unittest

from lowering.confirmed_inputs import ConfirmedInputError, pipeline_contract


DEVICES = {
    "button": {"category": ["Button"], "tags": ["Button"]},
    "light1": {"category": ["Switch"], "tags": ["Light"]},
    "light2": {"category": ["Switch"], "tags": ["Light"]},
    "menu1": {"category": ["MenuProvider"], "tags": ["MenuProvider"]},
    "menu2": {"category": ["MenuProvider"], "tags": ["MenuProvider"]},
}


def test_confirmed_binding_bypasses_selector_inference_shape():
    ir = {"timeline": [
        {"op": "wait", "cond": "Button.Button == true", "edge": "none"},
        {"op": "call", "target": "Switch.On", "args": {}},
    ]}
    out = pipeline_contract(ir, {"Button": ["button"], "Switch": ["light1", "light2"]}, DEVICES)
    assert out["df_selectors"] == {
        "Button.Button": ["(#button)"],
        "Switch.On": ["all(#Switch)"],
    }


def test_scalar_query_rejects_multiple_providers():
    ir = {"timeline": [{"op": "call", "target": "MenuProvider.GetMenu",
                        "args": {"Command": "lunch"}, "var": "menu"}]}
    try:
        pipeline_contract(ir, {"MenuProvider": ["menu1", "menu2"]}, DEVICES)
    except ConfirmedInputError as exc:
        assert "needs one provider" in str(exc)
    else:
        raise AssertionError("multi-provider scalar query was accepted")


def test_distinct_binding_slots_follow_ir_occurrence_order():
    devices = dict(DEVICES, light3={"category": ["Switch"], "tags": ["Light"]})
    ir = {"timeline": [
        {"op": "call", "target": "Switch.On", "args": {}},
        {"op": "call", "target": "Switch.On", "args": {}},
    ]}
    out = pipeline_contract(ir, {"Switch": ["light1"], "Switch#2": ["light3"]}, devices)
    assert out["df_selectors"]["Switch.On"] == ["(#light1)", "(#light3)"]
