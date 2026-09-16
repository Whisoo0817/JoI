"""Checks the worked examples in repair.md against the Explorer gate.

Every *-gold script must be EQUIV-FIXPOINT and every *-wrong script a confirmed DIVERGE,
except the binding variants (G4*, G8*-one-target), which are EQUIV under the B1/B5 binding
contract and are therefore not used as examples. Not an experiment result.

    ~/temp/bin/python joi/self_feedback/prompts/fewshot_check.py [CASE ...]
    B5=1 ... prints the verdict per selector assignment as well.
"""
import json, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = str(Path(__file__).resolve().parents[3])  # this checkout, the same tree the evaluator uses
PY = '/home/gnltnwjstk/temp/bin/python'

def dev(name, cat, *tags):
    return {name: {"category": cat, "tags": list(tags)}}

def merge(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out

T = lambda *steps: {"timeline": [{"op": "start_at", "anchor": "now"}, *steps]}

CASES = []

# G1 Edge/Rearm
g1_dev = merge(dev("Warehouse_Door", ["ContactSensor"], "Warehouse", "ContactSensor"),
               dev("Garage_Door", ["ContactSensor"], "Garage", "ContactSensor"),
               dev("Warehouse_Speaker", ["Speaker"], "Warehouse", "Speaker"))
g1_ir = T({"op": "cycle", "until": None, "period": "1 SEC", "body": [
    {"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "rising"},
    {"op": "call", "target": "Speaker.Speak", "args": {"Text": "Warehouse door opened"}}]})
g1_bind = {"ContactSensor": ["Warehouse_Door"], "Speaker": ["Warehouse_Speaker"]}
CASES.append(("G1-gold", g1_ir, g1_bind, g1_dev, 1000,
    "triggered := false\n"
    "if (triggered == true) {\n    wait until(not ((#Warehouse_Door).contactSensor_contact == false))\n    triggered = false\n}\n"
    "wait until((#Warehouse_Door).contactSensor_contact == false)\n"
    "(#Warehouse_Speaker).speaker_speak(\"Warehouse door opened\")\n"
    "triggered = true"))
CASES.append(("G1-wrong-polling", g1_ir, g1_bind, g1_dev, 1000,
    "triggered := false\n"
    "if ((#Warehouse_Door).contactSensor_contact == false) {\n    if (triggered == false) {\n"
    "        (#Warehouse_Speaker).speaker_speak(\"Warehouse door opened\")\n        triggered = true\n    }\n"
    "} else {\n    triggered = false\n}"))

# G2 Event vs Duration
g2_dev = merge(dev("Living_Lux", ["LightSensor"], "LivingRoom", "LightSensor"),
               dev("Living_Light", ["Switch"], "LivingRoom", "Light", "Switch"))
g2_ir = T({"op": "wait", "cond": "LightSensor.Brightness < 100", "edge": "none", "for": "10 SEC"},
          {"op": "call", "target": "Switch.On", "args": {}})
g2_bind = {"LightSensor": ["Living_Lux"], "Switch": ["Living_Light"]}
def g2(th, period=100):
    return ("hold := 0\n"
            "if ((#Living_Lux).lightSensor_brightness < 100) {\n    hold = hold + 1\n"
            f"    if (hold >= {th}) {{\n        (#Living_Light).switch_on()\n        break\n    }}\n"
            "} else {\n    hold = 0\n}")
CASES.append(("G2-gold-ge100", g2_ir, g2_bind, g2_dev, 100, g2(100)))
CASES.append(("G2-gold-ge101", g2_ir, g2_bind, g2_dev, 100, g2(101)))
CASES.append(("G2-wrong-D10n", g2_ir, g2_bind, g2_dev, 1000, g2(10)))

# G3 Absolute vs Delta (decrease)
g3_dev = merge(dev("Bath_Hum", ["HumiditySensor"], "Bathroom", "HumiditySensor"),
               dev("Bath_Fan_Plug", ["Switch"], "Bathroom", "Fan", "Switch"))
g3_ir = T({"op": "read", "var": "h1", "src": "HumiditySensor.Humidity"},
          {"op": "delay", "duration": "10 MIN"},
          {"op": "read", "var": "h2", "src": "HumiditySensor.Humidity"},
          {"op": "if", "cond": "($h1 - $h2) >= 10", "then": [{"op": "call", "target": "Switch.Off", "args": {}}], "else": []})
g3_bind = {"HumiditySensor": ["Bath_Hum"], "Switch": ["Bath_Fan_Plug"]}
CASES.append(("G3-gold", g3_ir, g3_bind, g3_dev, 0,
    "h1 = (#Bath_Hum).humiditySensor_humidity\ndelay(10 MIN)\nh2 = (#Bath_Hum).humiditySensor_humidity\n"
    "if (h1 - h2 >= 10) {\n    (#Bath_Fan_Plug).switch_off()\n}"))

CASES.append(("G3-wrong-abs", g3_ir, g3_bind, g3_dev, 0,
    "h1 = (#Bath_Hum).humiditySensor_humidity\ndelay(10 MIN)\nh2 = (#Bath_Hum).humiditySensor_humidity\n"
    "diff = h2 - h1\nif (diff < 0) {\n    diff = h1 - h2\n}\nif (diff >= 10) {\n    (#Bath_Fan_Plug).switch_off()\n}"))
CASES.append(("G3-wrong-reread", g3_ir, g3_bind, g3_dev, 0,
    "h1 = (#Bath_Hum).humiditySensor_humidity\ndelay(10 MIN)\n"
    "if ((#Bath_Hum).humiditySensor_humidity - h1 >= 10) {\n    (#Bath_Fan_Plug).switch_off()\n}"))

# G4 Binding/Selector (two slots of one service)
g4_dev = merge(dev("Entrance_Presence", ["PresenceSensor"], "Entrance", "PresenceSensor"),
               dev("Entrance_Light", ["Switch"], "Entrance", "Light", "Switch"),
               dev("Living_Light", ["Switch"], "LivingRoom", "Light", "Switch"))
g4_ir = T({"op": "if", "cond": "PresenceSensor.Presence == true", "then": [
    {"op": "call", "target": "Switch.On", "args": {}}, {"op": "call", "target": "Switch.Off", "args": {}}], "else": []})
g4_bind = {"PresenceSensor": ["Entrance_Presence"], "Switch": ["Entrance_Light"], "Switch#2": ["Living_Light"]}
CASES.append(("G4-gold", g4_ir, g4_bind, g4_dev, 0,
    "if ((#Entrance_Presence).presenceSensor_presence == true) {\n    (#Entrance_Light).switch_on()\n    (#Living_Light).switch_off()\n}"))
g4_dev_x = merge(g4_dev, dev("Garage_Light", ["Switch"], "Garage", "Light", "Switch"))
CASES.append(("G4x-gold", g4_ir, g4_bind, g4_dev_x, 0,
    "if ((#Entrance_Presence).presenceSensor_presence == true) {\n    (#Entrance_Light).switch_on()\n    (#Living_Light).switch_off()\n}"))
CASES.append(("G4x-wrong-unbound-device", g4_ir, g4_bind, g4_dev_x, 0,
    "if ((#Entrance_Presence).presenceSensor_presence == true) {\n    (#Entrance_Light).switch_on()\n    (#Garage_Light).switch_off()\n}"))
CASES.append(("G4x-wrong-tag-too-broad", g4_ir, g4_bind, g4_dev_x, 0,
    "if ((#Entrance_Presence).presenceSensor_presence == true) {\n    (#Entrance_Light).switch_on()\n    all(#Light).switch_off()\n}"))
CASES.append(("G4-wrong-swap", g4_ir, g4_bind, g4_dev, 0,
    "if ((#Entrance_Presence).presenceSensor_presence == true) {\n    (#Living_Light).switch_on()\n    (#Entrance_Light).switch_off()\n}"))

# G5 Phase/Order
g5_dev = merge(dev("Front_Door", ["ContactSensor"], "Entrance", "ContactSensor"),
               dev("Front_Light", ["Switch"], "Entrance", "Light", "Switch"),
               dev("Front_Camera", ["Camera"], "Entrance", "Camera"))
g5_ir = T({"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "none"},
          {"op": "call", "target": "Switch.On", "args": {}},
          {"op": "cycle", "until": None, "period": "10 MIN", "body": [{"op": "call", "target": "Camera.CaptureImage", "args": {}}]})
g5_bind = {"ContactSensor": ["Front_Door"], "Switch": ["Front_Light"], "Camera": ["Front_Camera"]}
CASES.append(("G5-gold", g5_ir, g5_bind, g5_dev, 600000,
    "phase := 0\nif (phase == 0) {\n    wait until((#Front_Door).contactSensor_contact == false)\n    phase = 1\n"
    "    (#Front_Light).switch_on()\n    (#Front_Camera).camera_captureImage()\n} else {\n    (#Front_Camera).camera_captureImage()\n}"))

CASES.append(("G5-wrong-first-body-delayed", g5_ir, g5_bind, g5_dev, 600000,
    "phase := 0\nif (phase == 0) {\n    wait until((#Front_Door).contactSensor_contact == false)\n    phase = 1\n"
    "    (#Front_Light).switch_on()\n} else {\n    (#Front_Camera).camera_captureImage()\n}"))

# H Quantifier preserved when a condition is rewritten (any slot)
h_dev = merge(dev("Hall_Motion_1", ["MotionSensor"], "Hallway", "MotionSensor"),
              dev("Hall_Motion_2", ["MotionSensor"], "Hallway", "MotionSensor"),
              dev("Hall_Light", ["Switch", "Light"], "Hallway", "Light", "Switch"))
h_ir = T({"op": "cycle", "until": None, "period": "1 SEC", "body": [
    {"op": "wait", "cond": "MotionSensor.Motion == true", "edge": "rising"},
    {"op": "call", "target": "Switch.On", "args": {}}]})
h_bind = {"MotionSensor": {"any": ["Hall_Motion_1", "Hall_Motion_2"]}, "Switch": ["Hall_Light"]}
def h(op):
    return ("triggered := false\n"
            f"if (triggered == true) {{\n    wait until(not (all(#MotionSensor).motionSensor_motion {op} true))\n"
            "    triggered = false\n}\n"
            f"wait until(all(#MotionSensor).motionSensor_motion {op} true)\n"
            "(#Hall_Light).switch_on()\ntriggered = true")
CASES.append(("H-gold", h_ir, h_bind, h_dev, 1000, h("==|")))
CASES.append(("H-wrong-dropped-pipe", h_ir, h_bind, h_dev, 1000,
    "triggered := false\n"
    "if (triggered == true) {\n    wait until(all(#MotionSensor).motionSensor_motion == false)\n"
    "    triggered = false\n}\n"
    "wait until(all(#MotionSensor).motionSensor_motion == true)\n"
    "(#Hall_Light).switch_on()\ntriggered = true"))

# G6 Termination Scope
g6_dev = dev("Living_Blind", ["WindowCovering"], "LivingRoom", "WindowCovering")
g6_ir = T({"op": "cycle", "until": None, "period": "30 MIN", "body": [
    {"op": "if", "cond": "WindowCovering.CurrentPosition > 50", "then": [
        {"op": "call", "target": "WindowCovering.SetLevel", "args": {"Level": 50}}], "else": []}]})
g6_bind = {"WindowCovering": ["Living_Blind"]}
CASES.append(("G6-gold", g6_ir, g6_bind, g6_dev, 1800000,
    "if ((#Living_Blind).windowCovering_currentPosition > 50) {\n    (#Living_Blind).windowCovering_setLevel(50)\n}"))

CASES.append(("G6-wrong-break", g6_ir, g6_bind, g6_dev, 1800000,
    "if ((#Living_Blind).windowCovering_currentPosition > 50) {\n    (#Living_Blind).windowCovering_setLevel(50)\n    break\n}"))

# G7 Timing/Wait: sustain then counted cycle
g7_dev = merge(dev("Basement_Hum", ["HumiditySensor"], "Basement", "HumiditySensor"),
               dev("Basement_Dehum", ["Dehumidifier"], "Basement", "Dehumidifier"))
g7_ir = T({"op": "wait", "cond": "HumiditySensor.Humidity >= 70", "edge": "none", "for": "10 SEC"},
          {"op": "cycle", "until": "n >= 3", "period": "20 SEC", "count": "n", "body": [
              {"op": "call", "target": "Dehumidifier.SetDehumidifierMode", "args": {"Mode": "drying"}}]})
g7_bind = {"HumiditySensor": ["Basement_Hum"], "Dehumidifier": ["Basement_Dehum"]}
CASES.append(("G7-gold", g7_ir, g7_bind, g7_dev, 100,
    "hold := 0\n"
    "if ((#Basement_Hum).humiditySensor_humidity >= 70) {\n    hold = hold + 1\n    if (hold >= 101) {\n"
    "        (#Basement_Dehum).dehumidifier_setDehumidifierMode(\"drying\")\n        delay(20 SEC)\n"
    "        (#Basement_Dehum).dehumidifier_setDehumidifierMode(\"drying\")\n        delay(20 SEC)\n"
    "        (#Basement_Dehum).dehumidifier_setDehumidifierMode(\"drying\")\n        break\n    }\n"
    "} else {\n    hold = 0\n}"))

CASES.append(("G7-wrong-period-as-tick", g7_ir, g7_bind, g7_dev, 20000,
    "hold := 0\nn := 0\n"
    "if ((#Basement_Hum).humiditySensor_humidity >= 70) {\n    hold = hold + 1\n    if (hold >= 10) {\n"
    "        if (n >= 3) {\n            break\n        }\n"
    "        (#Basement_Dehum).dehumidifier_setDehumidifierMode(\"drying\")\n        n = n + 1\n    }\n"
    "} else {\n    hold = 0\n}"))

# G8 Argument: read value passed into text, fan-out to two speakers, exact English string
g8_dev = merge(dev("Nursery_Hum", ["HumiditySensor"], "Nursery", "HumiditySensor"),
               dev("Nursery_Speaker", ["Speaker"], "Nursery", "Speaker"),
               dev("Kitchen_Speaker", ["Speaker"], "Kitchen", "Speaker"))
g8_ir = T({"op": "read", "var": "h", "src": "HumiditySensor.Humidity"},
          {"op": "call", "target": "Speaker.Speak", "args": {"Text": "Nursery humidity is $h percent"}})
g8_bind = {"HumiditySensor": ["Nursery_Hum"], "Speaker": ["Nursery_Speaker", "Kitchen_Speaker"]}
CASES.append(("G8-gold", g8_ir, g8_bind, g8_dev, 0,
    "h = (#Nursery_Hum).humiditySensor_humidity\n"
    "all(#Speaker).speaker_speak(\"Nursery humidity is \" + h + \" percent\")"))
CASES.append(("G8-wrong-korean", g8_ir, g8_bind, g8_dev, 0,
    "h = (#Nursery_Hum).humiditySensor_humidity\n"
    "all(#Speaker).speaker_speak(\"아기방 습도는 \" + h + \" 퍼센트입니다\")"))
CASES.append(("G8-wrong-one-target", g8_ir, g8_bind, g8_dev, 0,
    "h = (#Nursery_Hum).humiditySensor_humidity\n"
    "(#Nursery_Speaker).speaker_speak(\"Nursery humidity is \" + h + \" percent\")"))
g8_bind_all = {"HumiditySensor": ["Nursery_Hum"], "Speaker": {"all": ["Nursery_Speaker", "Kitchen_Speaker"]}}
CASES.append(("G8all-gold", g8_ir, g8_bind_all, g8_dev, 0,
    "h = (#Nursery_Hum).humiditySensor_humidity\n"
    "all(#Speaker).speaker_speak(\"Nursery humidity is \" + h + \" percent\")"))
CASES.append(("G8all-wrong-one-target", g8_ir, g8_bind_all, g8_dev, 0,
    "h = (#Nursery_Hum).humiditySensor_humidity\n"
    "(#Nursery_Speaker).speaker_speak(\"Nursery humidity is \" + h + \" percent\")"))

WORKER = r'''
import json, sys, os
sys.path.insert(0, os.environ["ROOT"]); os.chdir(os.environ["ROOT"])
from explorer.verification.gate import gate_pair
ir, bind, devs, jb = json.loads(sys.stdin.read())
g = gate_pair(ir, bind, devs, jb)
pr = g.product
if os.environ.get("B5"):
    import itertools
    from explorer.verification.gate import prepare_pair
    from explorer.verification.timed import timed_product
    base = prepare_pair(ir, bind, devs, jb)
    doms = list(getattr(base, "selector_domains", []))
    per = {}
    for a in itertools.product(*[range(n) for n in doms]):
        p2 = prepare_pair(ir, bind, devs, jb, selector_assignment=a)
        r = timed_product(p2.ir_runner, p2.code_runner, horizon_ms=None, verification_mode="auto")
        per[str(a)] = (r.verdict, r.claim)
    print(json.dumps({"B5_domains": doms, "tag_choice": list(getattr(base, "selector_choice", ())), "per_assignment": per}))
out = {"verdict": g.verdict, "confirmed": g.confirmed,
       "claim": getattr(pr, "claim", None), "closed": getattr(pr, "closed", None),
       "n_states": getattr(pr, "n_states", None), "notes": (g.notes or [])[-2:] + ((pr.notes or [])[-2:] if pr else [])}
if pr and pr.divergences:
    d = pr.divergences[0]
    out["witness"] = str(d)[:600]
print(json.dumps(out, ensure_ascii=False, default=repr))
'''

def run(case):
    name, ir, bind, devs, period, script = case
    jb = {"name": "Scenario", "cron": "", "period": period, "script": script}
    try:
        p = subprocess.run([PY, "-c", WORKER], input=json.dumps([ir, bind, devs, jb]), text=True,
                           capture_output=True, timeout=180, env={"ROOT": ROOT, "PATH": "/usr/bin:/bin", **({"B5": "1"} if __import__("os").environ.get("B5") else {})})
        res = p.stdout.strip() if p.stdout.strip() else ("CRASH " + p.stderr[-800:])
    except subprocess.TimeoutExpired:
        res = "TIMEOUT 180s"
    return name, res

if __name__ == "__main__":
    only = set(sys.argv[1:])
    todo = [c for c in CASES if not only or c[0] in only]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, res in ex.map(run, todo):
            print(f"== {name}\n{res}\n", flush=True)
