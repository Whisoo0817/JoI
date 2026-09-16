"""Self-test of R14 (RUNTIME_CONTRACT.md, author decision 2026-09-16): arithmetic on a variable that was never
assigned is a runtime error. Cases written from the rule text only.
Run: ~/temp/bin/python test_uninitialized_arith.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

from run import run_joi                                          # noqa: E402

FAIL = []
DEVICES = {"L": {"category": ["Light", "Switch"], "tags": ["Light", "Switch"]},
           "S": {"category": ["Speaker"], "tags": ["Speaker"]},
           "T": {"category": ["TemperatureSensor"], "tags": ["TemperatureSensor"]}}


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {info}"))
    if not cond:
        FAIL.append(name)


def run(script, events=None, period=0, horizon=1000):
    events = events or [(0, {"T.Temperature": 20})]
    return run_joi({"name": "T", "cron": "", "period": period, "script": script}, DEVICES, events, horizon)


r = run("n = n + 1\n(#Light).switch_on()")
check("never assigned: runtime error", r["status"] == "runtime-error" and r["category"] == "uninitialized-arith", r)
check("never assigned: no ACTION after the stop", r["raw_actions"] == [], r["raw_actions"])

r = run("(#Light).switch_on()\nn = n + 1")
check("ACTIONs before the error are kept", r["status"] == "runtime-error" and len(r["raw_actions"]) == 1, r)

r = run("if ((#TemperatureSensor).temperatureSensor_temperature > 100) { n := 0 }\nn = n + 1")
check("assignment in an untaken branch does not count", r["status"] == "runtime-error", r)

r = run("n := 0\nn = n + 1\n(#Light).switch_on()")
check("assigned first: ok", r["status"] == "ok" and len(r["raw_actions"]) == 1, r)

r = run("v = (#TemperatureSensor).temperatureSensor_temperature\nx = v - 1\n(#Light).switch_on()",
        events=[(0, {})])
check("missing input read is assigned, so not R14 (G4 IR rule untouched)", r["status"] != "runtime-error", r)

r = run('(#Speaker).speaker_speak("level " + level)')
check("`+` with a STRING operand is concatenation, not arithmetic",
      r["status"] == "ok" and len(r["raw_actions"]) == 1, r)

for op in ("-", "*", "/", "%"):
    r = run(f"n = n {op} 2\n(#Light).switch_on()")
    check(f"`{op}` with a never-assigned operand", r["status"] == "runtime-error", r)

print("PASS: 0 failed" if not FAIL else f"FAIL: {len(FAIL)} failed {FAIL}")
sys.exit(1 if FAIL else 0)
