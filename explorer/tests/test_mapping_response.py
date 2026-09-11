"""Regression tests for model response normalization in device mapping."""

from timeline_ir.mapping.extractor import parse_response_json
from timeline_ir.mapping.adapter import to_pipeline_contract
from lowering.run_local_ir import _live_binding


PAYLOAD = {
    "groups": [{
        "role": "action",
        "device_hint": "dehumidifier",
        "device_hard": True,
        "effect_hint": "set drying mode",
        "quantifier": None,
        "args_text": "drying mode",
    }]
}


def test_plain_json_object():
    import json
    assert parse_response_json(json.dumps(PAYLOAD)) == PAYLOAD


def test_markdown_fenced_json_object():
    import json
    raw = "```json\n" + json.dumps(PAYLOAD) + "\n```"
    assert parse_response_json(raw) == PAYLOAD


def test_explanatory_prefix_uses_first_json_object():
    import json
    raw = "Here is the result:\n" + json.dumps(PAYLOAD)
    assert parse_response_json(raw) == PAYLOAD


def _mapping(*clusters):
    return {"groups": [{"role": "action", "clusters": list(clusters)}],
            "errors": []}


def test_pipeline_contract_deduplicates_the_same_selector():
    cluster = {"svc": "Switch.On", "sel": ["Light"], "quant": "all",
               "ids": {"lamp1", "lamp2"}}
    out = to_pipeline_contract(_mapping(cluster, dict(cluster)))
    assert out["df_selectors"] == {"Switch.On": ["all(#Light)"]}
    assert out["errors"] == []


def test_pipeline_contract_rejects_multiple_selectors_for_one_service():
    out = to_pipeline_contract(_mapping(
        {"svc": "Switch.On", "sel": ["LivingRoom", "Light"], "quant": "all",
         "ids": {"lamp1"}},
        {"svc": "Switch.On", "sel": ["Kitchen", "Light"], "quant": "all",
         "ids": {"lamp2"}},
    ))
    assert out["df_selectors"]["Switch.On"] == [
        "all(#LivingRoom #Light)", "all(#Kitchen #Light)"]
    assert len(out["errors"]) == 1
    assert "multiple selectors" in out["errors"][0]


def test_live_binding_preserves_one_all_selector_quantifier():
    resolved = {"PresenceSensor.Presence": {
        "q": "all", "devices": ["p1", "p2"]}}
    ir = {"timeline": [
        {"op": "start_at", "anchor": "now"},
        {"op": "if", "cond": "PresenceSensor.Presence == false",
         "then": [], "else": []},
    ]}
    assert _live_binding(resolved, ir, {"p1": {}, "p2": {}}) == {
        "PresenceSensor": {"all": ["p1", "p2"]}}


def main() -> None:
    tests = sorted((name, obj) for name, obj in globals().items()
                   if name.startswith("test_") and callable(obj))
    for name, test in tests:
        test()
        print(f"PASS {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
