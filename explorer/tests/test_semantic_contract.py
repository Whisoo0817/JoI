from lowering.run_local_ir import _wrapper_period_from_ir
from timeline_ir.semantic_contract import (
    EDGE_TRIGGER_DEFAULT_PERIOD_MS,
    cycle_period_ms,
)


def _edge(period_marker=True):
    cycle = {
        "op": "cycle",
        "body": [{"op": "wait", "cond": "Button.Pushed == true", "edge": "rising"}],
    }
    if period_marker is True:
        cycle["period"] = "100 MSEC"
    elif isinstance(period_marker, str):
        cycle["period"] = period_marker
    return cycle


def test_missing_edge_period_uses_one_second_default():
    assert cycle_period_ms(_edge(False)) == EDGE_TRIGGER_DEFAULT_PERIOD_MS


def test_explicit_edge_period_is_not_overridden():
    ir = {"timeline": [_edge("100 MSEC")]}
    assert _wrapper_period_from_ir(ir) == 100


def test_explicit_nonedge_period_is_preserved():
    ir = {"timeline": [{"op": "cycle", "period": "30 SEC", "body": [
        {"op": "call", "target": "Switch.On", "args": {}}
    ]}]}
    assert _wrapper_period_from_ir(ir) == 30000
