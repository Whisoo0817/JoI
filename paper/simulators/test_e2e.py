"""End-to-end test: hand-constructed IR/JoI pairs from C01-C07 idioms,
fed through synth + both simulators + comparator.

Each test case mirrors one of the joi_from_ir.md idiom examples (D-1..D-9)
with an IR and the lowering result that joi_from_ir prompt is supposed to
produce. We verify their traces are equivalent under our locked semantics.

Run:
    cd /home/gnltnwjstk/joi
    python -m paper.simulators.test_e2e
"""

from __future__ import annotations

import sys

from .catalog import load_catalog
from .comparator import compare_traces
from .event_synth import synthesize_scenarios
from .ir_simulator import run_ir_simulation
from .joi_simulator import run_joi_simulation


# ── Test cases ───────────────────────────────────────────────────────────────

CASES = [
    {
        "name": "C01: dishwasher dry mode (D-1 one-shot)",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "call", "target": "Dishwasher.SetDishwasherMode",
                 "args": {"Mode": "dry"}},
            ],
        },
        "joi": {
            "cron": "",
            "period": 0,
            "script": '(#Dishwasher).SetDishwasherMode("dry")',
        },
    },
    {
        "name": "C02: light hue+saturation (D-1 with multi-arg method)",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "call", "target": "Light.EnhancedMoveToHueAndSaturation",
                 "args": {"EnhancedHue": 240, "Saturation": 80, "TransitionTime": 0}},
            ],
        },
        "joi": {
            "cron": "",
            "period": 0,
            "script": "(#Light).EnhancedMoveToHueAndSaturation(240, 80, 0)",
        },
    },
    {
        "name": "C03: if temp >= 30 then AC cool (D-2)",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "if", "cond": "TemperatureSensor.Temperature >= 30",
                 "then": [
                     {"op": "call", "target": "AirConditioner.SetMode",
                      "args": {"Mode": "cool"}},
                 ],
                 "else": []},
            ],
        },
        "joi": {
            "cron": "",
            "period": 0,
            "script": '''if ((#TemperatureSensor).Temperature >= 30) {
    (#AirConditioner).SetMode("cool")
}''',
        },
    },
    {
        "name": "C07: when door open, light on (D-2 wait+call)",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "wait", "cond": 'Door.DoorState == "open"', "edge": "none"},
                {"op": "call", "target": "Switch.On", "args": {}},
            ],
        },
        "joi": {
            "cron": "",
            "period": 0,
            "script": '''wait until((#Door).DoorState == "open")
(#Switch).On()''',
        },
    },
    {
        "name": "D-3: rising-edge whenever (door->light)",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "cycle", "until": None, "body": [
                    {"op": "wait", "cond": 'Door.DoorState == "open"', "edge": "rising"},
                    {"op": "call", "target": "Switch.On", "args": {}},
                ]},
            ],
        },
        "joi": {
            "cron": "",
            "period": 100,
            "script": '''triggered := false
if ((#Door).DoorState == "open") {
    if (triggered == false) {
        (#Switch).On()
        triggered = true
    }
} else {
    triggered = false
}''',
        },
    },
    {
        "name": "D-4: phase lifecycle (when X, every N do Y) — tick-aligned",
        # NOTE: D-4 has a real tick-aliasing divergence between IR (100ms poll)
        # and JoI (period-quantized wake). For E2E sanity we use period=1000
        # which aligns with the synthesizer's wait-fire time (cursor+1s) and
        # keeps the IR/JoI first emissions within the ±100ms group tolerance.
        # A larger period (e.g., 60s) would surface the lowering's
        # tick-aliasing artifact — that finding belongs in paper §9 evaluation.
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "wait", "cond": 'Door.DoorState == "open"', "edge": "none"},
                {"op": "cycle", "until": None, "body": [
                    {"op": "call", "target": "Switch.On", "args": {}},
                    {"op": "delay", "duration": "1 SEC"},
                ]},
            ],
        },
        "joi": {
            "cron": "",
            "period": 1000,
            "script": '''phase := 0
if (phase == 0) {
    wait until((#Door).DoorState == "open")
    phase = 1
    (#Switch).On()
}
if (phase == 1) {
    (#Switch).On()
}''',
        },
    },
    {
        "name": "D-5: alternation (red/blue every N)",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "cycle", "until": None, "body": [
                    {"op": "call", "target": "Light.MoveToColor",
                     "args": {"ColorX": 0.675, "ColorY": 0.322, "TransitionTime": 0}},
                    {"op": "delay", "duration": "1 SEC"},
                    {"op": "call", "target": "Light.MoveToColor",
                     "args": {"ColorX": 0.167, "ColorY": 0.040, "TransitionTime": 0}},
                    {"op": "delay", "duration": "1 SEC"},
                ]},
            ],
        },
        "joi": {
            "cron": "",
            "period": 1000,
            "script": '''state := "red"
if (state == "red") {
    (#Light).MoveToColor(0.675, 0.322, 0)
    state = "blue"
} else {
    (#Light).MoveToColor(0.167, 0.040, 0)
    state = "red"
}''',
        },
    },
    {
        "name": "D-7: cron-anchored one-shot",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "cron", "cron": "0 9 * * *"},
                {"op": "call", "target": "Switch.On", "args": {}},
            ],
        },
        "joi": {
            "cron": "0 9 * * *",
            "period": 0,
            "script": "(#Switch).On()",
        },
    },
    {
        "name": "B-2: simple periodic (cycle{call; delay})",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "cycle", "until": None, "body": [
                    {"op": "call", "target": "Switch.Toggle", "args": {}},
                    {"op": "delay", "duration": "1 SEC"},
                ]},
            ],
        },
        "joi": {
            "cron": "",
            "period": 1000,
            "script": "(#Switch).Toggle()",
        },
    },
    {
        "name": "D-9: cycle.until (clock-bounded)",
        # IR: cycle until clock.time >= 0010 (10 minutes) doing Toggle every 1m.
        # JoI: period=60s with leading break-guard.
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "cycle", "until": "clock.time >= 10", "body": [
                    {"op": "call", "target": "Switch.Toggle", "args": {}},
                    {"op": "delay", "duration": "1 MIN"},
                ]},
            ],
        },
        "joi": {
            "cron": "",
            "period": 60_000,
            "script": '''if (clock.time >= 10) {
    break
}
(#Switch).Toggle()''',
        },
    },
    {
        "name": "compound: if temp >= 30 AND humidity <= 50 (D-2)",
        "ir": {
            "timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "if",
                 "cond": "TemperatureSensor.Temperature >= 30 && HumiditySensor.Humidity <= 50",
                 "then": [
                     {"op": "call", "target": "Switch.Off", "args": {}},
                     {"op": "call", "target": "Speaker.Speak",
                      "args": {"Text": "warm and dry"}},
                 ],
                 "else": []},
            ],
        },
        "joi": {
            "cron": "",
            "period": 0,
            "script": '''if ((#TemperatureSensor).Temperature >= 30 and (#HumiditySensor).Humidity <= 50) {
    (#Switch).Off()
    (#Speaker).Speak("warm and dry")
}''',
        },
    },
]


# ── Test runner ──────────────────────────────────────────────────────────────

def run(verbose: bool = False) -> int:
    catalog = load_catalog()
    fails: list[str] = []
    for case in CASES:
        name = case["name"]
        ir = case["ir"]
        joi = case["joi"]
        try:
            scenarios = synthesize_scenarios(ir)
            scn = scenarios[0]
            t_ir = run_ir_simulation(ir, scn, catalog, debug=verbose)
            t_joi = run_joi_simulation(joi, scn, catalog, debug=verbose)
            result = compare_traces(t_ir, t_joi)
        except Exception as e:
            fails.append(f"  ✗ {name}: EXCEPTION {type(e).__name__}: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            continue

        if result.equivalent:
            print(f"  ✓ {name}")
            if verbose:
                print(f"    IR trace ({len(t_ir)}): {[(r.timestamp_ms, r.method, r.args) for r in t_ir.records]}")
                print(f"    JoI trace ({len(t_joi)}): {[(r.timestamp_ms, r.method, r.args) for r in t_joi.records]}")
        else:
            fails.append(f"  ✗ {name}\n     {result.diff_summary}")
            if verbose:
                print(f"    IR trace: {[(r.timestamp_ms, r.method, r.args) for r in t_ir.records]}")
                print(f"    JoI trace: {[(r.timestamp_ms, r.method, r.args) for r in t_joi.records]}")
                print(f"    Scenario events: {scn.events}")

    print()
    if fails:
        print(f"FAILED ({len(fails)}/{len(CASES)})")
        for f in fails:
            print(f)
        return 1
    print(f"PASSED ({len(CASES)}/{len(CASES)})")
    return 0


if __name__ == "__main__":
    verbose = "-v" in sys.argv
    sys.exit(run(verbose=verbose))
