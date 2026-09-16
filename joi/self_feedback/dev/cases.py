"""Development test set for tuning the repair prompt.

Fresh scenarios, two per error type, each with a hand-written wrong candidate in the shape the
68 E3 divergences take. Disjoint from the worked examples in prompts/repair.md and from
dataset.csv. Used only to choose the prompt; never reported as an experiment result.
"""


def dev(name, cat, *tags):
    return {name: {"category": cat, "tags": list(tags)}}


def merge(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out


def T(*steps):
    return {"timeline": [{"op": "start_at", "anchor": "now"}, *steps]}


CASES = []


def case(cid, family, ir, binding, devices, period, wrong, gold=None, gold_period=None):
    CASES.append({"id": cid, "family": family, "ir": ir, "binding": binding, "devices": devices,
                  "wrong": {"name": "Scenario", "cron": "", "period": period, "script": wrong},
                  "gold": None if gold is None else
                  {"name": "Scenario", "cron": "", "period": period if gold_period is None else gold_period,
                   "script": gold}})


# ---- 1. Edge / Rearm --------------------------------------------------------------
d = merge(dev("Hall_Motion", ["MotionSensor"], "Hallway", "MotionSensor"),
          dev("Hall_Light", ["Light"], "Hallway", "Light"))
case("D1a", "edge_rearm",
     T({"op": "cycle", "until": None, "period": "1 SEC", "body": [
         {"op": "wait", "cond": "MotionSensor.Motion == true", "edge": "rising"},
         {"op": "call", "target": "Light.MoveToBrightness", "args": {"Brightness": 100, "Rate": 0}},
         {"op": "delay", "duration": "3 SEC"},
         {"op": "call", "target": "Light.MoveToBrightness", "args": {"Brightness": 0, "Rate": 0}}]}),
     {"MotionSensor": ["Hall_Motion"], "Light": ["Hall_Light"]}, d, 1000,
     "triggered := false\nif ((#Hall_Motion).motionSensor_motion == true) {\n    if (triggered == false) {\n"
     "        (#Hall_Light).light_moveToBrightness(100, 0)\n        delay(3 SEC)\n"
     "        (#Hall_Light).light_moveToBrightness(0, 0)\n        triggered = true\n    }\n} else {\n    triggered = false\n}",
     "triggered := false\nif (triggered == true) {\n    wait until(not ((#Hall_Motion).motionSensor_motion == true))\n    triggered = false\n}\n"
     "wait until((#Hall_Motion).motionSensor_motion == true)\n(#Hall_Light).light_moveToBrightness(100, 0)\ndelay(3 SEC)\n"
     "(#Hall_Light).light_moveToBrightness(0, 0)\ntriggered = true")

d = merge(dev("Garden_Button", ["Button"], "Garden", "Button"),
          dev("Garden_Valve", ["Valve"], "Garden", "Valve"))
case("D1b", "edge_rearm",
     T({"op": "cycle", "until": None, "period": "1 SEC", "body": [
         {"op": "wait", "cond": "Button.Button == \"pushed\"", "edge": "rising"},
         {"op": "call", "target": "Valve.Open", "args": {}}]}),
     {"Button": ["Garden_Button"], "Valve": ["Garden_Valve"]}, d, 1000,
     "if ((#Garden_Button).button_button == \"pushed\") {\n    (#Garden_Valve).valve_open()\n}",
     "triggered := false\nif (triggered == true) {\n    wait until(not ((#Garden_Button).button_button == \"pushed\"))\n    triggered = false\n}\n"
     "wait until((#Garden_Button).button_button == \"pushed\")\n(#Garden_Valve).valve_open()\ntriggered = true")

# ---- 2. Event vs Duration ---------------------------------------------------------
d = merge(dev("Attic_Temp", ["TemperatureSensor"], "Attic", "TemperatureSensor"),
          dev("Attic_Fan_Plug", ["Switch"], "Attic", "Fan", "Switch"))
case("D2a", "sustain",
     T({"op": "wait", "cond": "TemperatureSensor.Temperature > 28", "edge": "none", "for": "30 SEC"},
       {"op": "call", "target": "Switch.On", "args": {}}),
     {"TemperatureSensor": ["Attic_Temp"], "Switch": ["Attic_Fan_Plug"]}, d, 1000,
     "hold_ticks := 0\nif ((#Attic_Temp).temperatureSensor_temperature > 28) {\n    hold_ticks = hold_ticks + 1\n"
     "    if (hold_ticks >= 30) {\n        (#Attic_Fan_Plug).switch_on()\n        break\n    }\n} else {\n    hold_ticks = 0\n}",
     "hold_ticks := 0\nif ((#Attic_Temp).temperatureSensor_temperature > 28) {\n    hold_ticks = hold_ticks + 1\n"
     "    if (hold_ticks >= 301) {\n        (#Attic_Fan_Plug).switch_on()\n        break\n    }\n} else {\n    hold_ticks = 0\n}", 100)

d = merge(dev("Office_Presence", ["PresenceSensor"], "Office", "PresenceSensor"),
          dev("Office_Monitor_Plug", ["Switch"], "Office", "Monitor", "Switch"))
case("D2b", "sustain",
     T({"op": "wait", "cond": "PresenceSensor.Presence == false", "edge": "none", "for": "1 MIN"},
       {"op": "call", "target": "Switch.Off", "args": {}}),
     {"PresenceSensor": ["Office_Presence"], "Switch": ["Office_Monitor_Plug"]}, d, 1000,
     "hold_ticks := 0\nif ((#Office_Presence).presenceSensor_presence == false) {\n    hold_ticks = hold_ticks + 1\n"
     "    if (hold_ticks >= 60) {\n        (#Office_Monitor_Plug).switch_off()\n        break\n    }\n} else {\n    hold_ticks = 0\n}",
     "hold_ticks := 0\nif ((#Office_Presence).presenceSensor_presence == false) {\n    hold_ticks = hold_ticks + 1\n"
     "    if (hold_ticks >= 601) {\n        (#Office_Monitor_Plug).switch_off()\n        break\n    }\n} else {\n    hold_ticks = 0\n}", 100)

# ---- 3. Absolute vs Delta ---------------------------------------------------------
d = merge(dev("Study_Temp", ["TemperatureSensor"], "Study", "TemperatureSensor"),
          dev("Study_AC", ["AirConditioner"], "Study", "AirConditioner"))
case("D3a", "delta",
     T({"op": "read", "var": "t1", "src": "TemperatureSensor.Temperature"},
       {"op": "delay", "duration": "20 MIN"},
       {"op": "read", "var": "t2", "src": "TemperatureSensor.Temperature"},
       {"op": "if", "cond": "$t2 - $t1 >= 3", "then": [
           {"op": "call", "target": "AirConditioner.SetAirConditionerMode", "args": {"Mode": "cool"}}], "else": []}),
     {"TemperatureSensor": ["Study_Temp"], "AirConditioner": ["Study_AC"]}, d, 0,
     "t1 = (#Study_Temp).temperatureSensor_temperature\ndelay(20 MIN)\nt2 = (#Study_Temp).temperatureSensor_temperature\n"
     "diff = t2 - t1\nif (diff < 0) {\n    diff = t1 - t2\n}\nif (diff >= 3) {\n    (#Study_AC).airConditioner_setAirConditionerMode(\"cool\")\n}",
     "t1 = (#Study_Temp).temperatureSensor_temperature\ndelay(20 MIN)\nt2 = (#Study_Temp).temperatureSensor_temperature\n"
     "if (t2 - t1 >= 3) {\n    (#Study_AC).airConditioner_setAirConditionerMode(\"cool\")\n}")

d = merge(dev("Den_Speaker", ["Speaker"], "Den", "Speaker"))
case("D3b", "delta",
     T({"op": "read", "var": "v1", "src": "Speaker.Volume"},
       {"op": "delay", "duration": "5 MIN"},
       {"op": "read", "var": "v2", "src": "Speaker.Volume"},
       {"op": "if", "cond": "($v1 - $v2) >= 20", "then": [
           {"op": "call", "target": "Speaker.Speak", "args": {"Text": "Volume dropped"}}], "else": []}),
     {"Speaker": ["Den_Speaker"]}, d, 0,
     "v1 = (#Den_Speaker).speaker_volume\ndelay(5 MIN)\nv2 = (#Den_Speaker).speaker_volume\n"
     "if (v2 - v1 >= 20) {\n    (#Den_Speaker).speaker_speak(\"Volume dropped\")\n}",
     "v1 = (#Den_Speaker).speaker_volume\ndelay(5 MIN)\nv2 = (#Den_Speaker).speaker_volume\n"
     "if (v1 - v2 >= 20) {\n    (#Den_Speaker).speaker_speak(\"Volume dropped\")\n}")

# ---- 4. Phase / Order -------------------------------------------------------------
d = merge(dev("Kitchen_Smoke", ["SmokeDetector"], "Kitchen", "SmokeDetector"),
          dev("Kitchen_Siren", ["Siren"], "Kitchen", "Siren"),
          dev("Kitchen_Speaker", ["Speaker"], "Kitchen", "Speaker"))
case("D4a", "phase",
     T({"op": "wait", "cond": "SmokeDetector.Smoke == true", "edge": "none"},
       {"op": "call", "target": "Siren.SetSirenMode", "args": {"Mode": "emergency"}},
       {"op": "cycle", "until": None, "period": "2 MIN", "body": [
           {"op": "call", "target": "Speaker.Speak", "args": {"Text": "Smoke detected in the kitchen"}}]}),
     {"SmokeDetector": ["Kitchen_Smoke"], "Siren": ["Kitchen_Siren"], "Speaker": ["Kitchen_Speaker"]}, d, 120000,
     "phase := 0\nif (phase == 0) {\n    wait until((#Kitchen_Smoke).smokeDetector_smoke == true)\n    phase = 1\n"
     "    (#Kitchen_Siren).siren_setSirenMode(\"emergency\")\n} else {\n    (#Kitchen_Speaker).speaker_speak(\"Smoke detected in the kitchen\")\n}",
     "phase := 0\nif (phase == 0) {\n    wait until((#Kitchen_Smoke).smokeDetector_smoke == true)\n    phase = 1\n"
     "    (#Kitchen_Siren).siren_setSirenMode(\"emergency\")\n    (#Kitchen_Speaker).speaker_speak(\"Smoke detected in the kitchen\")\n"
     "} else {\n    (#Kitchen_Speaker).speaker_speak(\"Smoke detected in the kitchen\")\n}")

d = merge(dev("Laundry_Leak", ["LeakSensor"], "Laundry", "LeakSensor"),
          dev("Laundry_Valve", ["Valve"], "Laundry", "Valve"),
          dev("Mail", ["EmailProvider"], "EmailProvider"))
case("D4b", "phase",
     T({"op": "wait", "cond": "LeakSensor.Leakage == true", "edge": "none"},
       {"op": "call", "target": "Valve.Close", "args": {}},
       {"op": "cycle", "until": None, "period": "1 MIN", "body": [
           {"op": "call", "target": "EmailProvider.SendMail",
            "args": {"ToAddress": "home@example.com", "Title": "Leak", "Body": "Water leak in the laundry room"}}]}),
     {"LeakSensor": ["Laundry_Leak"], "Valve": ["Laundry_Valve"], "EmailProvider": ["Mail"]}, d, 60000,
     "phase := 0\nif (phase == 0) {\n    wait until((#Laundry_Leak).leakSensor_leakage == true)\n    phase = 1\n"
     "    (#Laundry_Valve).valve_close()\n    (#Mail).emailProvider_sendMail(\"home@example.com\", \"Leak\", \"Water leak in the laundry room\")\n"
     "} else {\n    (#Laundry_Valve).valve_close()\n    (#Mail).emailProvider_sendMail(\"home@example.com\", \"Leak\", \"Water leak in the laundry room\")\n}",
     "phase := 0\nif (phase == 0) {\n    wait until((#Laundry_Leak).leakSensor_leakage == true)\n    phase = 1\n"
     "    (#Laundry_Valve).valve_close()\n    (#Mail).emailProvider_sendMail(\"home@example.com\", \"Leak\", \"Water leak in the laundry room\")\n"
     "} else {\n    (#Mail).emailProvider_sendMail(\"home@example.com\", \"Leak\", \"Water leak in the laundry room\")\n}")

# ---- 5. Termination scope ---------------------------------------------------------
d = merge(dev("Living_CO2", ["CarbonDioxideSensor"], "LivingRoom", "CarbonDioxideSensor"),
          dev("Living_Purifier", ["AirPurifier"], "LivingRoom", "AirPurifier"))
case("D5a", "termination",
     T({"op": "cycle", "until": None, "period": "1 HOUR", "body": [
         {"op": "if", "cond": "CarbonDioxideSensor.CarbonDioxide > 1000", "then": [
             {"op": "call", "target": "AirPurifier.SetAirPurifierMode", "args": {"Mode": "auto"}}], "else": []}]}),
     {"CarbonDioxideSensor": ["Living_CO2"], "AirPurifier": ["Living_Purifier"]}, d, 3600000,
     "if ((#Living_CO2).carbonDioxideSensor_carbonDioxide > 1000) {\n    (#Living_Purifier).airPurifier_setAirPurifierMode(\"auto\")\n    break\n}",
     "if ((#Living_CO2).carbonDioxideSensor_carbonDioxide > 1000) {\n    (#Living_Purifier).airPurifier_setAirPurifierMode(\"auto\")\n}")

d = merge(dev("Bedroom_Temp", ["TemperatureSensor"], "Bedroom", "TemperatureSensor"),
          dev("Bedroom_Fan_Plug", ["Switch"], "Bedroom", "Fan", "Switch"))
case("D5b", "termination",
     T({"op": "wait", "cond": "TemperatureSensor.Temperature > 28", "edge": "none"},
       {"op": "call", "target": "Switch.On", "args": {}},
       {"op": "delay", "duration": "15 MIN"},
       {"op": "call", "target": "Switch.Off", "args": {}}),
     {"TemperatureSensor": ["Bedroom_Temp"], "Switch": ["Bedroom_Fan_Plug"]}, d, 0,
     "wait until((#Bedroom_Temp).temperatureSensor_temperature > 28)\n(#Bedroom_Fan_Plug).switch_on()\ndelay(15 MIN)\n"
     "if ((#Bedroom_Temp).temperatureSensor_temperature > 28) {\n    (#Bedroom_Fan_Plug).switch_off()\n}",
     "wait until((#Bedroom_Temp).temperatureSensor_temperature > 28)\n(#Bedroom_Fan_Plug).switch_on()\ndelay(15 MIN)\n(#Bedroom_Fan_Plug).switch_off()")

# ---- 6. Timing / Wait -------------------------------------------------------------
d = merge(dev("Back_Door", ["ContactSensor"], "Backyard", "ContactSensor"),
          dev("Back_Speaker", ["Speaker"], "Backyard", "Speaker"))
case("D6a", "timing",
     T({"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "none", "for": "30 SEC"},
       {"op": "cycle", "until": "n >= 2", "period": "15 SEC", "count": "n", "body": [
           {"op": "call", "target": "Speaker.Speak", "args": {"Text": "Please close the back door"}}]}),
     {"ContactSensor": ["Back_Door"], "Speaker": ["Back_Speaker"]}, d, 15000,
     "hold_ticks := 0\nn := 0\nif ((#Back_Door).contactSensor_contact == false) {\n    hold_ticks = hold_ticks + 1\n"
     "    if (hold_ticks >= 30) {\n        if (n >= 2) {\n            break\n        }\n"
     "        (#Back_Speaker).speaker_speak(\"Please close the back door\")\n        n = n + 1\n    }\n} else {\n    hold_ticks = 0\n}",
     "hold_ticks := 0\nif ((#Back_Door).contactSensor_contact == false) {\n    hold_ticks = hold_ticks + 1\n"
     "    if (hold_ticks >= 301) {\n        (#Back_Speaker).speaker_speak(\"Please close the back door\")\n        delay(15 SEC)\n"
     "        (#Back_Speaker).speaker_speak(\"Please close the back door\")\n        break\n    }\n} else {\n    hold_ticks = 0\n}", 100)

d = merge(dev("Yard_Siren", ["Siren", "Switch"], "Yard", "Siren", "Switch"))
case("D6b", "timing",
     T({"op": "cycle", "until": None, "period": "3 MIN", "body": [
         {"op": "call", "target": "Siren.SetSirenMode", "args": {"Mode": "emergency"}},
         {"op": "delay", "duration": "10 SEC"},
         {"op": "call", "target": "Switch.Off", "args": {}}]}),
     {"Siren": ["Yard_Siren"], "Switch": ["Yard_Siren"]}, d, 0,
     "(#Yard_Siren).siren_setSirenMode(\"emergency\")\ndelay(10 SEC)\n(#Yard_Siren).switch_off()\ndelay(3 MIN)",
     "(#Yard_Siren).siren_setSirenMode(\"emergency\")\ndelay(10 SEC)\n(#Yard_Siren).switch_off()", 180000)

# ---- 7. Argument / string ---------------------------------------------------------
d = merge(dev("Living_Temp", ["TemperatureSensor"], "LivingRoom", "TemperatureSensor"),
          dev("Living_Speaker", ["Speaker"], "LivingRoom", "Speaker"),
          dev("Kitchen_Speaker", ["Speaker"], "Kitchen", "Speaker"))
case("D7a", "argument",
     T({"op": "read", "var": "t", "src": "TemperatureSensor.Temperature"},
       {"op": "call", "target": "Speaker.Speak", "args": {"Text": "The living room is $t degrees"}}),
     {"TemperatureSensor": ["Living_Temp"], "Speaker": ["Living_Speaker", "Kitchen_Speaker"]}, d, 0,
     "t = (#Living_Temp).temperatureSensor_temperature\nall(#Speaker).speaker_speak(\"거실 온도는 \" + t + \"도입니다\")",
     "t = (#Living_Temp).temperatureSensor_temperature\nall(#Speaker).speaker_speak(\"The living room is \" + t + \" degrees\")")

d = merge(dev("Porch_Door", ["ContactSensor"], "Porch", "ContactSensor"),
          dev("Porch_Light", ["Light"], "Porch", "Light"))
case("D7b", "argument",
     T({"op": "wait", "cond": "ContactSensor.Contact == false", "edge": "none"},
       {"op": "call", "target": "Light.MoveToBrightness", "args": {"Brightness": 60, "Rate": 0}}),
     {"ContactSensor": ["Porch_Door"], "Light": ["Porch_Light"]}, d, 0,
     "wait until((#Porch_Door).contactSensor_contact == false)\n(#Porch_Light).light_moveToBrightness(0, 60)",
     "wait until((#Porch_Door).contactSensor_contact == false)\n(#Porch_Light).light_moveToBrightness(60, 0)")
