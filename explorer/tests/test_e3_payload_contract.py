from explorer.eval.e3 import candidate_matches_row, payload_sha256, row_payload


ROW = {
    "category_v2": "C01", "index": "1", "command_kor": "켜줘",
    "command_eng": "turn it on",
    "connected_devices": '{"lamp":{"category":["Switch"],"tags":["Light"]}}',
    "ir_gt": '{"timeline":[{"op":"call","target":"Switch.On","args":{}}]}',
    "binding_gt": '{"Switch":["lamp"]}',
}


def test_candidate_payload_must_match_all_confirmed_inputs():
    payload = row_payload(ROW)
    candidate = dict(payload, input_payload_sha256=payload_sha256(payload))
    assert candidate_matches_row(candidate, ROW)
    candidate["binding"] = {"Switch": ["other"]}
    assert not candidate_matches_row(candidate, ROW)
