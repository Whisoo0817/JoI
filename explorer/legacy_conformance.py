"""E1 pilot against the separately retained SenSys simulators.

This is deliberately limited to constructs whose old and new execution
contracts overlap.  The legacy implementations have separate parsers,
expression evaluators, worlds, and control-flow interpreters.  The pilot does
not cover grounding, targets, reentry, cancellation, or the full Timeline IR.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter

from sensys.simulators.ir_simulator import run_ir_simulation
from sensys.simulators.joi_simulator import run_joi_simulation
from sensys.simulators.scenario import Scenario, ScenarioEvent

from .expr import canonical_key
from .interp import Action
from .ir_step import IrRunner
from .oneshot import OneShotRunner
from .runner import JoiRunner


T0_MS = 28 * 24 * 60 * 60 * 1000  # Monday 00:00, nonzero timer sentinel


def _canon_current(action: Action, relative_ms: int) -> tuple:
    service, method = canonical_key(action.service, action.method)
    args = tuple(int(v) if isinstance(v, float) and v.is_integer() else v
                 for v in action.args)
    return relative_ms, service, method, args


def _canon_legacy(record) -> tuple:
    return record.timestamp_ms, record.service, record.method, tuple(record.args)


def _current_trace(runner, scenario: Scenario, *, period_ms: int,
                   horizon_ticks: int) -> list[tuple]:
    world = dict(scenario.initial_world)
    pending = sorted(scenario.events, key=lambda event: event.at_ms)
    variables, global_variables = {}, {}
    trace = []
    for tick in range(horizon_ticks):
        relative = tick * period_ms
        while pending and pending[0].at_ms <= relative:
            event = pending.pop(0)
            world[event.key] = event.value
        result = runner.step(variables, global_variables, world,
                             T0_MS + relative, first_tick=(tick == 0))
        variables, global_variables = result.vars, result.gv
        trace.extend(_canon_current(action, relative)
                     for action in result.actions)
        if result.terminated:
            break
    return trace


def _legacy_trace(kind: str, program, scenario: Scenario,
                  horizon_ms: int) -> list[tuple]:
    if kind == "ir":
        trace = run_ir_simulation(program, scenario, catalog=None)
    else:
        trace = run_joi_simulation(program, scenario, catalog=None)
    return [_canon_legacy(record) for record in trace.records
            if record.timestamp_ms <= horizon_ms]


def _scenario(initial: dict, events: list[tuple]) -> Scenario:
    return Scenario(
        initial_world=initial,
        events=[ScenarioEvent(at, key, value) for at, key, value in events],
    )


def cases() -> list[dict]:
    return [
        {
            "id": "E1-IMMEDIATE",
            "constructs": ["start_at", "call"],
            "ir": {"timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "call", "target": "Light.On", "args": {}},
            ]},
            "joi": {"script": "(#Light).light_on()",
                    "period": 0, "cron": ""},
            "scenario": _scenario({}, []),
            "period_ms": 1000,
            "horizon_ticks": 1,
            "code_runner": "oneshot",
        },
        {
            "id": "E1-LEVEL",
            "constructs": ["cycle", "level condition", "numeric boundary"],
            "ir": {"timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "cycle", "period": "1 SEC", "until": None,
                 "body": [
                    {"op": "if", "cond": "TemperatureSensor.Temperature > 25",
                     "then": [
                        {"op": "call", "target": "AirConditioner.On", "args": {}}
                     ], "else": []},
                 ]},
            ]},
            "joi": {"script": "t = (#TemperatureSensor).temperature\n"
                               "if (t > 25) { (#AirConditioner).airConditioner_on() }",
                    "period": 1000, "cron": ""},
            "scenario": _scenario(
                {"temperaturesensor.temperature": 20},
                [(1000, "temperaturesensor.temperature", 26),
                 (3000, "temperaturesensor.temperature", 20)],
            ),
            "period_ms": 1000,
            "horizon_ticks": 5,
            "code_runner": "periodic",
        },
        {
            "id": "E1-RISING-EDGE",
            "constructs": ["cycle", "rising edge", "persistent latch"],
            "ir": {"timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "cycle", "period": "1 SEC", "until": None,
                 "body": [
                    {"op": "wait", "cond": 'ContactSensor.Contact == "open"',
                     "edge": "rising"},
                    {"op": "call", "target": "Light.On", "args": {}},
                 ]},
            ]},
            "joi": {"script": "was_open := false\n"
                               "x = (#ContactSensor).contact\n"
                               "if (x == \"open\" and was_open == false) { (#Light).light_on() }\n"
                               "if (x != \"open\") { was_open = false }\n"
                               "if (x == \"open\") { was_open = true }",
                    "period": 1000, "cron": ""},
            "scenario": _scenario(
                {"contactsensor.contact": "closed"},
                [(1000, "contactsensor.contact", "open"),
                 (3000, "contactsensor.contact", "closed"),
                 (4000, "contactsensor.contact", "open")],
            ),
            "period_ms": 1000,
            "horizon_ticks": 6,
            "code_runner": "periodic",
        },
        {
            "id": "E1-IF-ELSE",
            "constructs": ["cycle", "if", "else", "action argument"],
            "ir": {"timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "cycle", "period": "1 SEC", "until": None,
                 "body": [
                    {"op": "if", "cond": "MotionSensor.Motion == true",
                     "then": [{"op": "call", "target": "Light.MoveToBrightness",
                               "args": {"Brightness": 80}}],
                     "else": [{"op": "call", "target": "Light.MoveToBrightness",
                               "args": {"Brightness": 20}}]},
                 ]},
            ]},
            "joi": {"script": "m = (#MotionSensor).motion\n"
                               "if (m == true) { (#Light).light_moveToBrightness(80) } "
                               "else { (#Light).light_moveToBrightness(20) }",
                    "period": 1000, "cron": ""},
            "scenario": _scenario(
                {"motionsensor.motion": False},
                [(2000, "motionsensor.motion", True),
                 (4000, "motionsensor.motion", False)],
            ),
            "period_ms": 1000,
            "horizon_ticks": 5,
            "code_runner": "periodic",
        },
        {
            "id": "E1-DELAY",
            "constructs": ["delay", "one-shot continuation"],
            "ir": {"timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "delay", "duration": "3 SEC"},
                {"op": "call", "target": "Light.On", "args": {}},
            ]},
            "joi": {"script": "delay(3 SEC)\n(#Light).light_on()",
                    "period": 0, "cron": ""},
            "scenario": _scenario({}, []),
            "period_ms": 1000,
            "horizon_ticks": 5,
            "code_runner": "oneshot",
        },
        {
            "id": "E1-ACTION-ORDER",
            "constructs": ["action order", "multiple calls"],
            "ir": {"timeline": [
                {"op": "start_at", "anchor": "now"},
                {"op": "call", "target": "Camera.TakePicture", "args": {}},
                {"op": "call", "target": "Speaker.Speak",
                 "args": {"Text": "done"}},
            ]},
            "joi": {"script": "(#Camera).camera_takePicture()\n"
                               "(#Speaker).speaker_speak(\"done\")",
                    "period": 0, "cron": ""},
            "scenario": _scenario({}, []),
            "period_ms": 1000,
            "horizon_ticks": 1,
            "code_runner": "oneshot",
        },
    ]


def evaluate(case: dict) -> dict:
    started = time.perf_counter()
    horizon_ms = (case["horizon_ticks"] - 1) * case["period_ms"]
    scenario = case["scenario"]
    ir_runner = IrRunner(case["ir"])
    code_runner = (OneShotRunner(case["joi"]["script"])
                   if case["code_runner"] == "oneshot"
                   else JoiRunner.from_src(case["joi"]["script"]))
    traces = {
        "current_ir": _current_trace(
            ir_runner, scenario, period_ms=case["period_ms"],
            horizon_ticks=case["horizon_ticks"]),
        "legacy_ir": _legacy_trace("ir", case["ir"], scenario, horizon_ms),
        "current_code": _current_trace(
            code_runner, scenario, period_ms=case["period_ms"],
            horizon_ticks=case["horizon_ticks"]),
        "legacy_code": _legacy_trace(
            "code", case["joi"], scenario, horizon_ms),
    }
    checks = {
        "ir_conforms": traces["current_ir"] == traces["legacy_ir"],
        "code_conforms": traces["current_code"] == traces["legacy_code"],
        "legacy_pair_agrees": traces["legacy_ir"] == traces["legacy_code"],
        "current_pair_agrees": traces["current_ir"] == traces["current_code"],
    }
    return {
        "case_id": case["id"],
        "constructs": case["constructs"],
        "status": "PASS" if all(checks.values()) else "DISCREPANCY",
        "checks": checks,
        "traces": {key: [list(record) for record in value]
                   for key, value in traces.items()},
        "seconds": time.perf_counter() - started,
    }


def run(output_dir: str) -> dict:
    outcomes = [evaluate(case) for case in cases()]
    counts = Counter(outcome["status"] for outcome in outcomes)
    summary = {
        "evidence_class": "development-only",
        "oracle": "separately retained SenSys simulators",
        "scope": "common-subset interpreter conformance pilot",
        "selected_cases": len(outcomes),
        "outcomes": dict(sorted(counts.items())),
        "all_pass": counts.get("DISCREPANCY", 0) == 0,
        "limitations": [
            "Legacy and current observations are compared without device targets.",
            "The pilot excludes grounding, reentry, cancellation, cron, and unsupported legacy constructs.",
            "The legacy simulators are independent implementation evidence, not a normative semantics oracle.",
        ],
    }
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "case_outcomes.jsonl"), "w",
              encoding="utf-8") as target:
        for outcome in outcomes:
            target.write(json.dumps(outcome, ensure_ascii=False,
                                    sort_keys=True) + "\n")
    with open(os.path.join(output_dir, "summary.json"), "w",
              encoding="utf-8") as target:
        json.dump(summary, target, ensure_ascii=False, indent=2,
                  sort_keys=True)
        target.write("\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), ensure_ascii=False,
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
