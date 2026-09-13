"""E1-local fixture catalog: the global JoI catalog plus typed leaf stubs for the depth additions.

The global file `files/service_list_ver2.0.7.json` is read, never written. `build()` writes the union to
`depth/runs/fixture_catalog.json`, which the runner passes to `load_catalog(path)` and
`prepare_pair(..., service_catalog=path)`.

Stubs are orchestration leaves only (whisoo decision 2026-09-13): a value is an input the history sets,
a function is an observable ACTION. None of them performs timing, history, averaging, counting,
availability reporting or error recovery; those stay inside the automation under test.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE = ROOT / "files" / "service_list_ver2.0.7.json"
OUT = HERE / "runs" / "fixture_catalog.json"


def _value(vid, typ, why):
    return {"id": vid, "descriptor": why, "type": typ}


def _fn(fid, why, *args):
    return {"id": fid, "descriptor": why,
            "arguments": [{"id": a, "descriptor": a, "type": t} for a, t in args],
            "return_type": {"type": "VOID"}}


def _skill(sid, why, values=(), functions=()):
    return {"id": sid, "descriptor": "[E1 stub] " + why, "values": list(values),
            "functions": list(functions), "enums": []}


STUBS = [
    # E1-092
    _skill("House", "shutdown request input", values=[_value("ShutdownRequested", "BOOL", "a shutdown was requested")]),
    _skill("Alexa", "announcement leaf actions", functions=[
        _fn("AnnounceTasks", "announce today's tasks"),
        _fn("AnnounceNews", "announce the news"),
        _fn("AnnounceAlarmSettings", "announce alarm settings")]),
    _skill("Lights", "house lighting leaf action", functions=[_fn("Off", "turn off lights in an area", ("Area", "STRING"))]),
    _skill("Locks", "house lock leaf action", functions=[_fn("Lock", "lock the named doors", ("Doors", "STRING"))]),
    _skill("Alarm", "house alarm leaf action", functions=[_fn("Set", "set the alarm mode", ("Mode", "STRING"))]),
    # E1-095
    _skill("PoolPH", "pool pH reading", values=[_value("Value", "DOUBLE", "current pH")]),
    _skill("PoolChlorine", "pool chlorine reading", values=[_value("Value", "DOUBLE", "current chlorine ppm")]),
    _skill("Pool", "pool report leaf action", functions=[
        _fn("ReportDailyQuality", "report daily means", ("MeanPH", "DOUBLE"), ("MeanChlorine", "DOUBLE"))]),
    # E1-028
    _skill("Feeder", "pet feeder request input and dispense leaf action",
           values=[_value("DispenseRequested", "BOOL", "a dispense request is active")],
           functions=[_fn("Dispense", "dispense a portion", ("Portion", "STRING"))]),
    # E1-034
    _skill("Oven", "oven state input and off leaf action",
           values=[_value("State", "BOOL", "oven is on")], functions=[_fn("Off", "turn the oven off")]),
    _skill("Notify", "overrun alert leaf action and user confirmation input",
           values=[_value("ConfirmContinue", "BOOL", "user confirmed continuing")],
           functions=[_fn("OvenOverrun", "send the oven overrun confirmation alert")]),
]


def build():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    ids = {s["id"].lower() for s in base["skills"]}
    clash = [s["id"] for s in STUBS if s["id"].lower() in ids]
    if clash:
        raise SystemExit(f"stub ids collide with the global catalog: {clash}")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"skills": base["skills"] + STUBS}, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(OUT), hashlib.sha256(OUT.read_bytes()).hexdigest()


if __name__ == "__main__":
    print(*build())
