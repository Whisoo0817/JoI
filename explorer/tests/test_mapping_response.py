"""Regression tests for model response normalization in device mapping."""

from timeline_ir.mapping.extractor import parse_response_json


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


def main() -> None:
    tests = sorted((name, obj) for name, obj in globals().items()
                   if name.startswith("test_") and callable(obj))
    for name, test in tests:
        test()
        print(f"PASS {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
