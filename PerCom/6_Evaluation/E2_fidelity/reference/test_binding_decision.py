"""Self-test of the binding decision of 2026-09-14 (BINDING_DECISION_2026-09-14.md, SPEC_GAPS B1/B2).

Hand-written cases derived from the decision text only (no Explorer output). Pair shape as in the E2 pairs:
IR {"timeline": [...]}, binding, devices {id: {"category", "tags"}}, JoI block {name, cron, period, script},
events [(t_ms, {"Device.Member": value})], global catalog files/service_list_ver2.0.7.json.
Run: ~/temp/bin/python test_binding_decision.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import itertools                                   # noqa: E402

from run import compare, run_ir, run_joi, selector_space          # noqa: E402

START = {"op": "start_at", "anchor": "now"}
FAIL = []


def block(script, period=0):
    return {"name": "T", "cron": "", "period": period, "script": script}


def light(tags):
    return {"category": ["Light", "Switch"], "tags": tags}


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {info}"))
    if not cond:
        FAIL.append(name)


def pair_run(ir, binding, devices, script, events, horizon=1000):
    ri = run_ir(ir, binding, devices, events, horizon, binding_decision=True)
    rj = run_joi(block(script), devices, events, horizon, binding=binding, ir=ir)
    return ri, rj


# (a) IR one call on a 4-device slot vs JoI four lines naming each device by its ID -> equal (B1 + B2)
A_DEV = {"Hall_Light_1": light(["Hallway", "Light"]), "Hall_Light_2": light(["Hallway", "Light"]),
         "LR_Light_1": light(["LivingRoom", "Light"]), "LR_Light_2": light(["LivingRoom", "Light"]),
         "Kitchen_Light": light(["Kitchen", "Light"])}
A_IR = {"timeline": [START, {"op": "call", "target": "Switch.On", "args": {}}]}
A_BIND = {"Switch": ["Hall_Light_1", "Hall_Light_2", "LR_Light_1", "LR_Light_2"]}
A_JOI = "\n".join(f"(#{d}).switch_on()" for d in ["LR_Light_2", "Hall_Light_1", "LR_Light_1", "Hall_Light_2"])
A_EV = [(0, {})]


def case_a():
    ri, rj = pair_run(A_IR, A_BIND, A_DEV, A_JOI, A_EV)
    eq, diff = compare(ri["trace"], rj["trace"])
    check("(a) status ok", ri["status"] == rj["status"] == "ok", (ri["detail"], rj["detail"]))
    check("(a) 4-device slot vs four ID lines: equal", eq, diff)
    check("(a) one set unit of 4 devices", ri["trace"] == [{"t": 0, "units": [
        {"kind": "set", "service": "Switch", "method": "On", "args": [],
         "devices": sorted(A_BIND["Switch"])}]}], ri["trace"])
    # revised B1.3: each ID line calls only the named light; revised B2: the run's target is the one binding set
    # holding the called lights, so naming only part of the bound devices is not a difference
    rj3 = run_joi(block("\n".join(A_JOI.split("\n")[:3])), A_DEV, A_EV, 1000, binding=A_BIND, ir=A_IR)
    check("(a') three of four ID lines: equal (B2 target = the binding set)",
          compare(ri["trace"], rj3["trace"])[0], rj3["trace"])
    check("(a') each ID line called only its device", [a[4] for a in rj["raw_actions"]] ==
          ["LR_Light_2", "Hall_Light_1", "LR_Light_1", "Hall_Light_2"], rj["raw_actions"])
    # B2 alone, on hand-built previous-form traces: one fan-out group of 4 vs four one-call groups in another order
    sig = lambda d: {"service": "Switch", "method": "On", "args": [], "device": d}          # noqa: E731
    fan = [{"t": 0, "groups": [[sig(d) for d in sorted(A_BIND["Switch"])]]}]
    lines = [{"t": 0, "groups": [[sig(d)] for d in ["LR_Light_2", "Hall_Light_1", "LR_Light_1", "Hall_Light_2"]]}]
    three = [{"t": 0, "groups": lines[0]["groups"][:3]}]
    gap = [{"t": 0, "groups": lines[0]["groups"][:2] + [[{**sig("Kitchen_Light"), "method": "Off"}]]
            + lines[0]["groups"][2:]}]
    sets = [{"service": "switch", "slot": "Switch", "quantifier": None, "devices": A_BIND["Switch"]}]
    check("(a-B2) fan-out of 4 vs four lines: equal", compare(fan, lines, device_sets=sets)[0])
    check("(a-B2) fan-out of 4 vs three lines: equal (target = binding set)", compare(fan, three, device_sets=sets)[0])
    check("(a-B2) another call between the lines: NOT equal", not compare(fan, gap, device_sets=sets)[0])
    check("(a-B2) without device_sets: NOT equal (previous rule)", not compare(fan, lines)[0])
    # a line repeated: duplicates removed inside the unit
    rjd = run_joi(block(A_JOI + "\n(#Hall_Light_1).switch_on()"), A_DEV, A_EV, 1000, binding=A_BIND, ir=A_IR)
    check("(a'') repeated consecutive line: NOT equal (B2 multiplicity 2)", not compare(ri["trace"], rjd["trace"])[0])
    # compare(device_sets=...) on previous-form traces gives the same verdict
    check("(a) compare with device_sets on trace_groups", compare(ri["trace_groups"], rj["trace_groups"],
                                                                  device_sets=ri["device_sets"])[0])


# (b) IR call on a single speaker vs JoI all(#Speaker) over three speakers -> equal (B1.1: count/all ignored)
def case_b():
    dev = {f"{r}_Speaker": {"category": ["Speaker"], "tags": [r, "Speaker"]} for r in ("Warehouse", "Office", "Lobby")}
    ir = {"timeline": [START, {"op": "call", "target": "Speaker.Speak", "args": {"Text": "hello"}}]}
    bind = {"Speaker": ["Warehouse_Speaker"]}
    ri, rj = pair_run(ir, bind, dev, 'all(#Speaker).speaker_speak("hello")', [(0, {})])
    check("(b) status ok", ri["status"] == rj["status"] == "ok", (ri["detail"], rj["detail"]))
    check("(b) single speaker vs all(#Speaker): equal", compare(ri["trace"], rj["trace"])[0],
          (ri["trace"], rj["trace"]))
    check("(b) JoI called only the bound speaker", [a[4] for a in rj["raw_actions"]] == ["Warehouse_Speaker"],
          rj["raw_actions"])


# (c) IR Zone1 then Zone2 on separate single-device slots vs JoI Zone2 then Zone1, same instant -> NOT equal
C_DEV = {"Zone1_Valve": {"category": ["Valve"], "tags": ["Zone1", "Valve"]},
         "Zone2_Valve": {"category": ["Valve"], "tags": ["Zone2", "Valve"]}}
C_JOI = "(#Zone2 #Valve).Close()\n(#Zone1 #Valve).Close()"


def case_c():
    variants = {
        "binding slots Valve / Valve#2": (
            {"timeline": [START, {"op": "call", "target": "Valve.Close", "args": {}},
                          {"op": "call", "target": "Valve.Close", "args": {}}]},
            {"Valve": ["Zone1_Valve"], "Valve#2": ["Zone2_Valve"]}),
        "binding None, explicit forms": (
            {"timeline": [START, {"op": "call", "target": "Valve[Zone1_Valve].Close", "args": {}},
                          {"op": "call", "target": "Valve[Zone2_Valve].Close", "args": {}}]},
            None),
    }
    for label, (ir, bind) in variants.items():
        ri, rj = pair_run(ir, bind, C_DEV, C_JOI, [(0, {})])
        check(f"(c) {label}: status ok", ri["status"] == rj["status"] == "ok", (ri["detail"], rj["detail"]))
        check(f"(c) {label}: reversed order NOT equal", not compare(ri["trace"], rj["trace"])[0],
              (ri["trace"], rj["trace"]))
        rj_same = run_joi(block("(#Zone1 #Valve).Close()\n(#Zone2 #Valve).Close()"), C_DEV, [(0, {})], 1000,
                          binding=bind, ir=ir)
        check(f"(c) {label}: same order equal", compare(ri["trace"], rj_same["trace"])[0],
              (ri["trace"], rj_same["trace"]))


# (d) IR {"any": [s1, s2]} read in a comparison vs JoI singular selector naming only s1 -> equal when only s2 holds
def case_d():
    dev = {"S1": {"category": ["TemperatureSensor"], "tags": ["Living", "TemperatureSensor"]},
           "S2": {"category": ["TemperatureSensor"], "tags": ["Bedroom", "TemperatureSensor"]},
           "Lamp": {"category": ["Switch"], "tags": ["Lamp"]}}
    ir = {"timeline": [START, {"op": "if", "cond": "TemperatureSensor.Temperature > 30",
                               "then": [{"op": "call", "target": "Switch.On", "args": {}}], "else": []}]}
    bind = {"TemperatureSensor": {"any": ["S1", "S2"]}, "Switch": ["Lamp"]}
    script = "if ((#S1).temperatureSensor_temperature > 30) {\n(#Lamp).switch_on()\n}"
    ev = [(0, {"S1.Temperature": 20, "S2.Temperature": 35})]
    ri, rj = pair_run(ir, bind, dev, script, ev)
    check("(d) status ok", ri["status"] == rj["status"] == "ok", (ri["detail"], rj["detail"]))
    check("(d) IR any-slot fired", len(ri["raw_actions"]) == 1, ri["raw_actions"])
    check("(d) any slot vs singular (#S1): equal", compare(ri["trace"], rj["trace"])[0], (ri["trace"], rj["trace"]))


# (f) IR one call on a 2-device slot vs JoI calling that line twice -> NOT equal (B2 multiplicity)
F_DEV = {"a": light(["Light"]), "b": light(["Light"])}
F_IR = {"timeline": [START, {"op": "call", "target": "Switch.On", "args": {}}]}
F_BIND = {"Switch": ["a", "b"]}


def case_f():
    ri = run_ir(F_IR, F_BIND, F_DEV, [(0, {})], 1000, binding_decision=True)
    for label, script in (("all(#Switch) twice", "all(#Switch).switch_on()\nall(#Switch).switch_on()"),
                          ("(#a) twice", "(#a).switch_on()\n(#a).switch_on()")):
        rj = run_joi(block(script), F_DEV, [(0, {})], 1000, binding=F_BIND, ir=F_IR)
        check(f"(f) {label}: status ok", ri["status"] == rj["status"] == "ok", (ri["detail"], rj["detail"]))
        check(f"(f) 2-device slot once vs {label}: NOT equal", not compare(ri["trace"], rj["trace"])[0],
              (ri["trace"], rj["trace"]))
    rj1 = run_joi(block("all(#Switch).switch_on()"), F_DEV, [(0, {})], 1000, binding=F_BIND, ir=F_IR)
    check("(f) control: all(#Switch) once: equal", compare(ri["trace"], rj1["trace"])[0])


# (g) IR one call on {"Switch": [a, b]} vs JoI (#a).switch_on() only -> equal (B1.3 calls a, B2 target = {a, b})
def case_g():
    ri = run_ir(F_IR, F_BIND, F_DEV, [(0, {})], 1000, binding_decision=True)
    rj = run_joi(block("(#a).switch_on()"), F_DEV, [(0, {})], 1000, binding=F_BIND, ir=F_IR)
    check("(g) status ok", ri["status"] == rj["status"] == "ok", (ri["detail"], rj["detail"]))
    check("(g) JoI called only a", [x[4] for x in rj["raw_actions"]] == ["a"], rj["raw_actions"])
    check("(g) {a, b} slot vs (#a) only: equal", compare(ri["trace"], rj["trace"])[0], (ri["trace"], rj["trace"]))


# (h) IR {"all": [a, b]} read `m == false` vs JoI `not (any(#S).m == true)` -> equal on all four inputs (B1.4)
def case_h():
    dev = {"s1": {"category": ["PresenceSensor"], "tags": ["PresenceSensor"]},
           "s2": {"category": ["PresenceSensor"], "tags": ["PresenceSensor"]},
           "Lamp": {"category": ["Switch"], "tags": ["Lamp"]}}
    ir = {"timeline": [START, {"op": "if", "cond": "PresenceSensor.Presence == false",
                               "then": [{"op": "call", "target": "Switch.On", "args": {}}], "else": []}]}
    bind = {"PresenceSensor": {"all": ["s1", "s2"]}, "Switch": ["Lamp"]}
    # JOILang.g4: `not` applies to one condition_atom, so `not (any(...).m == true)` with inner parentheses is a
    # syntax error; `not any(#S).m == true` is the grammar-valid form of the same condition.
    paren = "if (not (any(#PresenceSensor).presenceSensor_presence == true)) {\n(#Lamp).switch_on()\n}"
    rp = run_joi(block(paren), dev, [(0, {"s1.Presence": False, "s2.Presence": False})], 1000, binding=bind, ir=ir)
    check("(h) parenthesised `not (...)` form is refused by the grammar", rp["category"] == "syntax", rp["detail"])
    script = "if (not any(#PresenceSensor).presenceSensor_presence == true) {\n(#Lamp).switch_on()\n}"
    fired = []
    for v1 in (False, True):
        for v2 in (False, True):
            ev = [(0, {"s1.Presence": v1, "s2.Presence": v2})]
            ri, rj = pair_run(ir, bind, dev, script, ev)
            ok = ri["status"] == rj["status"] == "ok"
            check(f"(h) s1={v1} s2={v2}: status ok", ok, (ri["detail"], rj["detail"]))
            check(f"(h) s1={v1} s2={v2}: equal", ok and compare(ri["trace"], rj["trace"])[0],
                  (ri["trace"], rj["trace"]))
            fired.append(len(ri["raw_actions"]))
    check("(h) IR fires only when both are false", fired == [1, 0, 0, 0], fired)


# (i)-(iii) B5: a service with two or more distinct binding device sets; the pair is equal if SOME assignment of a
# device set to each JoI selector occurrence makes the traces equal, different only if EVERY assignment differs.
I_DEV = {"Living_Motion": {"category": ["MotionSensor"], "tags": ["LivingRoom", "MotionSensor"]},
         "Bedroom_Motion": {"category": ["MotionSensor"], "tags": ["Bedroom", "MotionSensor"]},
         "Spk": {"category": ["Speaker"], "tags": ["Speaker"]}}
I_IR = {"timeline": [START, {"op": "if", "cond": "MotionSensor.Motion == true or MotionSensor.Motion == true",
                             "then": [{"op": "call", "target": "Speaker.Speak", "args": {"Text": "motion"}}],
                             "else": []}]}
I_BIND = {"MotionSensor": ["Living_Motion"], "MotionSensor#2": ["Bedroom_Motion"], "Speaker": ["Spk"]}


def joi_i(op):
    sel = "(#Bedroom #MotionSensor).motionSensor_motion"
    return f'if ({sel} {op} true or {sel} {op} true) {{\n(#Speaker).speaker_speak("motion")\n}}'


def verdicts(ir, bind, dev, script, ev):
    """equal? for every assignment in the selector space (itertools.product order)."""
    ri = run_ir(ir, bind, dev, ev, 1000, binding_decision=True)
    space = selector_space(block(script), dev, bind, ir)
    out = {}
    for a in itertools.product(*[range(n) for n in space["domains"]]):
        rj = run_joi(block(script), dev, ev, 1000, binding=bind, ir=ir, selector_assignment=list(a))
        out[a] = (ri["status"] == rj["status"] == "ok" and compare(ri["trace"], rj["trace"])[0], rj["status"])
    return ri, space, out


# (i) IR reads slot 1 (living) or slot 2 (bedroom); JoI reads (#Bedroom ...) twice
def case_i():
    ev = [(0, {"Living_Motion.Motion": True, "Bedroom_Motion.Motion": False})]
    ri, space, out = verdicts(I_IR, I_BIND, I_DEV, joi_i("=="), ev)
    check("(i) selector space: two occurrences of two sets, tag rule picks bedroom", space ==
          {"domains": [2, 2], "tag_choice": [1, 1]}, space)
    rj_tag = run_joi(block(joi_i("==")), I_DEV, ev, 1000, binding=I_BIND, ir=I_IR)
    check("(i) no assignment given: tag rule, traces differ", rj_tag["status"] == "ok"
          and not compare(ri["trace"], rj_tag["trace"])[0], (ri["trace"], rj_tag["trace"]))
    check("(i) assignment = tag_choice: differs (same as no assignment)", out[tuple(space["tag_choice"])][0] is False)
    check("(i) assignment [living set, bedroom set]: equal", out[(0, 1)][0] is True, out)
    check("(i) all assignments ran", all(st == "ok" for _, st in out.values()), out)


# (ii) IR reads slot 1 (L) and calls slot 2 (T); JoI reads (#Lamp) and calls (#Lamp)
def case_ii():
    dev = {"L": {"category": ["Switch"], "tags": ["Lamp", "Switch"]},
           "T": {"category": ["Switch"], "tags": ["Tv", "Switch"]}}
    ir = {"timeline": [START, {"op": "if", "cond": "Switch.Switch == true",
                               "then": [{"op": "call", "target": "Switch.Off", "args": {}}], "else": []}]}
    bind = {"Switch": ["L"], "Switch#2": ["T"]}
    script = "if ((#Lamp).switch_switch == true) {\n(#Lamp).switch_off()\n}"
    ev = [(0, {"L.Switch": True, "T.Switch": False})]
    ri, space, out = verdicts(ir, bind, dev, script, ev)
    check("(ii) selector space [2, 2], tag rule [0, 0]", space == {"domains": [2, 2], "tag_choice": [0, 0]}, space)
    check("(ii) IR calls T", [a[4] for a in ri["raw_actions"]] == ["T"], ri["raw_actions"])
    check("(ii) tag-rule assignment differs", out[(0, 0)][0] is False, out)
    check("(ii) some assignment is equal ([L set, T set])", any(v for v, _ in out.values()) and out[(0, 1)][0], out)


# (iii) logic change (JoI != where IR ==) that no assignment can fix
def case_iii():
    ev = [(0, {"Living_Motion.Motion": True, "Bedroom_Motion.Motion": True})]
    ri, space, out = verdicts(I_IR, I_BIND, I_DEV, joi_i("!="), ev)
    check("(iii) IR fires", len(ri["raw_actions"]) == 1, ri["raw_actions"])
    check("(iii) four assignments, all ran", len(out) == 4 and all(st == "ok" for _, st in out.values()), out)
    check("(iii) every assignment differs", not any(v for v, _ in out.values()), out)


def case_b5_api():
    rbad = run_joi(block(joi_i("==")), I_DEV, [(0, {})], 1000, binding=I_BIND, ir=I_IR, selector_assignment=[0])
    check("(B5 api) wrong assignment length -> error selector-assignment",
          rbad["status"] == "error" and rbad["category"] == "selector-assignment", rbad["detail"])
    one = selector_space(block("(#Speaker).speaker_speak(\"x\")"), I_DEV, I_BIND, I_IR)
    check("(B5 api) service with one device set is not an occurrence", one == {"domains": [], "tag_choice": []}, one)


# (e) without the new keywords, (a) behaves as before (G1 tags only, previous normal form)
def case_e():
    ri = run_ir(A_IR, A_BIND, A_DEV, A_EV, 1000)
    rj = run_joi(block(A_JOI), A_DEV, A_EV, 1000)
    check("(e) IR trace in previous normal form", ri["trace"] == [{"t": 0, "groups": [[
        {"service": "Switch", "method": "On", "args": [], "device": d} for d in sorted(A_BIND["Switch"])]]}]
        and "device_sets" not in ri and "trace_groups" not in ri, ri["trace"])
    check("(e) JoI selector by device ID unsupported (G1 tags only)",
          rj["status"] == "unsupported" and rj["category"] == "selector-no-device", rj["detail"])
    check("(e) no device_sets key on JoI result", "device_sets" not in rj)


if __name__ == "__main__":
    for f in (case_a, case_b, case_c, case_d, case_e, case_f, case_g, case_h, case_i, case_ii, case_iii, case_b5_api):
        f()
    print(f"{'FAIL' if FAIL else 'PASS'}: {len(FAIL)} failed")
    raise SystemExit(1 if FAIL else 0)
