"""Harness controls: the gold IR must reproduce every hand-derived trace, every
hand-written correct JoI must pass every history, and known buggy JoI must fail.

python controls.py   (from anywhere; writes runs/controls.json)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import TASK_BY_ID, evaluate_block  # noqa: E402

DOOR = "(#Entrance #ContactSensor).Contact"

CORRECT = {
    "T01": (1000, f"""hold := 0
if ({DOOR} == false) {{
    hold = hold + 1
    if (hold >= 60) {{
        (#Hallway #Speaker).Speak("Please close the front door")
        break
    }}
}} else {{
    hold = 0
}}"""),
    "T04": (0, """wait until((#Garage #ContactSensor).Contact == false)
(#Garage #Light).On()"""),
    "T07": (0, """ch = (#LivingRoom #Television).Channel
(#LivingRoom #Television).SetChannel(7)
delay(30 MIN)
(#LivingRoom #Television).SetChannel(ch)"""),
    "T10": (300000, """n := 0
if (n >= 4) {
    break
}
if ((#LivingRoom #Window).Contact == false) {
    (#LivingRoom #Speaker).Speak("Please close the window")
}
n = n + 1"""),
    "T02": (1000, """hold := 0
fired := false
if ((#LivingRoom #MotionSensor).Motion == false) {
    if (fired == false) {
        hold = hold + 1
        if (hold >= 120) {
            (#LivingRoom #Light).Off()
            fired = true
        }
    }
} else {
    hold = 0
    fired = false
}"""),
    "T05": (1000, """triggered := false
if ((#LivingRoom #TemperatureSensor).Temperature > 28) {
    if (triggered == false) {
        (#LivingRoom #Plug).On()
        triggered = true
    }
} else {
    triggered = false
}"""),
    "T08": (0, """t1 = (#WineCellar #TemperatureSensor).Temperature
delay(10 MIN)
t2 = (#WineCellar #TemperatureSensor).Temperature
if (t2 - t1 >= 2) {
    (#WineCellar #AirConditioner).SetTargetTemperature(t1)
}"""),
    "T11": (1000, """n := 0
triggered := false
if ((#Mailbox #ContactSensor).Contact == false) {
    if (triggered == false) {
        (#Kitchen #Speaker).Speak("Mail has arrived")
        triggered = true
        n = n + 1
        if (n >= 3) {
            break
        }
    }
} else {
    triggered = false
}"""),
    "T03": (1000, f"""t := 0
if ({DOOR} == false) {{
    t = t + 1
    if (t == 180) {{
        (#Hallway #Speaker).Speak("The front door is still open")
    }}
}} else {{
    t = 0
}}"""),
    "T06": (1000, """triggered := false
if ((#Entrance #MotionSensor).Motion == true) {
    if (triggered == false) {
        (#Entrance #Light).On()
        delay(1 MIN)
        (#Entrance #Light).Off()
        triggered = true
    }
} else {
    triggered = false
}"""),
    "T09": (1000, f"""triggered := false
if ({DOOR} == false) {{
    if (triggered == false) {{
        vol = (#LivingRoom #Speaker).Volume
        (#LivingRoom #Speaker).SetVolume(10)
        delay(2 MIN)
        (#LivingRoom #Speaker).SetVolume(vol)
        triggered = true
    }}
}} else {{
    triggered = false
}}"""),
    "T12": (1000, f"""n := 0
hold := 0
fired := false
if ({DOOR} == false) {{
    if (fired == false) {{
        hold = hold + 1
        if (hold >= 60) {{
            (#Hallway #Speaker).Speak("Please close the door")
            fired = true
            n = n + 1
            if (n >= 3) {{
                break
            }}
        }}
    }}
}} else {{
    hold = 0
    fired = false
}}"""),
}

# Known bug patterns with the stage they are expected to fail.
BUGGY = {
    "T01_delay_recheck": ("T01", "boundary", 0, f"""wait until({DOOR} == false)
delay(1 MIN)
if ({DOOR} == false) {{
    (#Hallway #Speaker).Speak("Please close the front door")
}}"""),
    "T09_persistent_snapshot": ("T09", "boundary", 1000, f"""triggered := false
vol := (#LivingRoom #Speaker).Volume
if ({DOOR} == false) {{
    if (triggered == false) {{
        (#LivingRoom #Speaker).SetVolume(10)
        delay(2 MIN)
        (#LivingRoom #Speaker).SetVolume(vol)
        triggered = true
    }}
}} else {{
    triggered = false
}}"""),
    "T05_level_trigger": ("T05", "nominal", 1000, """if ((#LivingRoom #TemperatureSensor).Temperature > 28) {
    (#LivingRoom #Plug).On()
}"""),
    "T02_no_fired_guard": ("T02", "nominal", 1000, """hold := 0
if ((#LivingRoom #MotionSensor).Motion == false) {
    hold = hold + 1
    if (hold >= 120) {
        (#LivingRoom #Light).Off()
    }
} else {
    hold = 0
}"""),
    "T10_off_by_one_count": ("T10", "nominal", 300000, """n := 0
if (n > 4) {
    break
}
if ((#LivingRoom #Window).Contact == false) {
    (#LivingRoom #Speaker).Speak("Please close the window")
}
n = n + 1"""),
}


def main():
    rows, ok = [], True
    for tid, (period, script) in CORRECT.items():
        r = evaluate_block(TASK_BY_ID[tid], block={"cron": "", "period": period, "script": script})
        gold = all(h.get("gold_ir_reproduces_expected") for h in r.histories) and len(r.histories) == len(TASK_BY_ID[tid]["histories"])
        passed = r.stage_failed is None and gold
        ok &= passed
        rows.append({"control": f"{tid}_correct", "expect": "pass", "stage_failed": r.stage_failed,
                     "failure": r.failure, "gold_ok": gold, "ok": passed, "detail": r.to_json()})
        print(f"{tid}_correct            stage_failed={r.stage_failed} gold_ok={gold} exact_all={r.exact_all} {r.failure}")
        if not passed:
            for h in r.histories:
                if not h.get("match") or not h.get("gold_ir_reproduces_expected"):
                    print("   ", h.get("name"), "gold_ok", h.get("gold_ir_reproduces_expected"),
                          "\n     expected", h.get("expected"), "\n     actual  ", h.get("actual"), h.get("error", ""))
    for name, (tid, want, period, script) in BUGGY.items():
        r = evaluate_block(TASK_BY_ID[tid], block={"cron": "", "period": period, "script": script})
        passed = r.stage_failed == want
        ok &= passed
        rows.append({"control": name, "expect": want, "stage_failed": r.stage_failed, "ok": passed, "detail": r.to_json()})
        print(f"{name:24s} want={want} got={r.stage_failed} {r.failure}")
        if not passed:
            for h in r.histories:
                print("   ", h.get("name"), h.get("match"), "\n     expected", h.get("expected"), "\n     actual  ", h.get("actual"))
    out = HERE / "runs" / "controls.json"
    out.write_text(json.dumps({"all_ok": ok, "rows": rows}, ensure_ascii=False, indent=1, default=str))
    print("ALL CONTROLS OK" if ok else "CONTROLS FAILED", "->", out)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
