"""Reproduce the C20-O/correct timer probes of the handoff (README.md §3). Exploratory, not an E2 result.

~/temp/bin/python probe_c20.py --list
~/temp/bin/python probe_c20.py <variant> [--budget SECONDS] [--no-reference]

Each variant edits the frozen pair in memory, checks it on the independent reference over the C20-O histories
(unless --no-reference), then runs the Explorer the way run_e2.py does. Pairs and histories are not changed.
"""
import argparse
import copy
import json
import signal
import sys
import time
from pathlib import Path

E2 = Path(__file__).resolve().parents[1]
ROOT = E2.parents[2]
sys.path[:0] = [str(ROOT), str(E2)]

NOOP = '[{"op": "read", "var": "_noop", "src": "Clock.Hour"}]'
TS_JOI = """armed := true
state := 0
t_in := 0
p = (#Bedroom #PresenceSensor).Presence
lux = (#Outdoor #LightSensor).Brightness
ts = (#Clock).Timestamp
if (state == 0) {
    if (p == true) {
        if (armed == true) {
            armed = false
            if (lux >= 50) {
                state = 1
                t_in = ts
            }
        }
    } else {
        armed = true
    }
} else {
    if (lux < 50 or p == false) {
        if (lux < 50 and p == true) {
            (#Bedroom #Switch).On()
        }
        state = 0
    } else if (ts - t_in >= 7200) {
        state = 0
    }
}"""


def window(ir, joi, text, ticks):
    ir = json.loads(json.dumps(ir).replace('"2 HOUR"', '"%s"' % text))
    joi["script"] = joi["script"].replace("ticks >= 72000", "ticks >= %d" % ticks)
    return ir, joi


def no_noop(ir):
    return json.loads(json.dumps(ir).replace(NOOP, "[]"))


# name -> (description, edit(ir, joi) -> (ir, joi, input_domains, input_step_ms))
VARIANTS = {
    "original": ("frozen pair", lambda ir, joi: (ir, joi, None, 100)),
    "window-2min": ("2 HOUR -> 2 MIN, JoI ticks 1200", lambda ir, joi: (*window(ir, joi, "2 MIN", 1200), None, 100)),
    "window-10min": ("2 HOUR -> 10 MIN, JoI ticks 6000", lambda ir, joi: (*window(ir, joi, "10 MIN", 6000), None, 100)),
    "window-1sec": ("2 HOUR -> 1 SEC, JoI ticks 10", lambda ir, joi: (*window(ir, joi, "1 SEC", 10), None, 100)),
    "lux-two-values": ("inputs limited to lux {20,500}", lambda ir, joi: (
        ir, joi, {"Outdoor_Lux.brightness": [20.0, 500.0], "Bed_Presence.presence": [False, True]}, 100)),
    "no-noop": ("IR _noop clock read removed", lambda ir, joi: (no_noop(ir), joi, None, 100)),
    "no-noop-2min": ("_noop removed + 2 MIN window (closes)", lambda ir, joi: (
        *window(no_noop(ir), joi, "2 MIN", 1200), None, 100)),
    "timestamp": ("JoI uses Clock.Timestamp instead of ticks", lambda ir, joi: (ir, dict(joi, script=TS_JOI), None, 100)),
    "timestamp-no-noop": ("timestamp JoI + _noop removed", lambda ir, joi: (
        no_noop(ir), dict(joi, script=TS_JOI), None, 100)),
    "minute-grid": ("IR period 1 MIN, JoI period 60000 ticks 120, input grid 60 s", lambda ir, joi: (
        json.loads(json.dumps(ir).replace('"period": "100 MSEC"', '"period": "1 MIN"')),
        dict(joi, period=60000, script=joi["script"].replace("ticks >= 72000", "ticks >= 120")), None, 60000)),
}


def load_pair(pair_id="C20-O/correct"):
    d = json.load(open(E2 / "pairs/e1_pairs.json"))["pairs"]
    items = d.values() if isinstance(d, dict) else d
    return copy.deepcopy(next(q for q in items if isinstance(q, dict) and q.get("pair_id") == pair_id))


def reference_check(p, ir, joi, grid):
    sys.path.insert(0, str(E2 / "reference"))
    from run import compare, run_ir, run_joi
    hs = json.load(open(E2 / "histories/e1_histories.json"))["histories"][p["base_case"]]
    hs = hs if isinstance(hs, list) else hs["histories"]
    cat = str(ROOT / p["catalog"])
    same = 0
    first = None
    for h in hs:
        ev = {}
        for t, u in h["events"]:
            ev.setdefault((int(t) // grid) * grid, {}).update(u)
        ev = sorted(ev.items())
        a = run_ir(ir, p["binding"], p["devices"], ev, h["horizon"], catalog_path=cat, t_start_ms=p["t_start_ms"])
        b = run_joi(joi, p["devices"], ev, h["horizon"], catalog_path=cat, t_start_ms=p["t_start_ms"])
        ok = a["status"] == "ok" and b["status"] == "ok" and compare(a["trace"], b["trace"])[0]
        same += ok
        if not ok and first is None:
            first = (h["name"], [x[0] for x in a["raw_actions"]][:3], [x[0] for x in b["raw_actions"]][:3])
    return same, len(hs), first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--budget", type=int, default=300)
    ap.add_argument("--no-reference", action="store_true")
    args = ap.parse_args()
    if args.list or not args.variant:
        for k, (desc, _) in VARIANTS.items():
            print(f"{k:20s} {desc}")
        return
    p = load_pair()
    ir, joi, domains, step = VARIANTS[args.variant][1](copy.deepcopy(p["ir"]), copy.deepcopy(p["joi"]))
    if not args.no_reference:
        same, n, first = reference_check(p, ir, joi, step)
        print(f"reference: same on {same}/{n} histories (input grid {step} ms); first difference {first}", flush=True)
    import run_e2
    from explorer.verification.gate import prepare_pair
    from explorer.verification.timed import timed_product
    prep = prepare_pair(ir, p["binding"], p["devices"], joi, service_catalog=True)

    def alarm(signum, frame):
        raise TimeoutError

    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(args.budget)
    started = time.time()
    try:
        pr = timed_product(prep.ir_runner, prep.code_runner, horizon_ms=None,
                           t0_ms=run_e2.T0_EXPLORER + int(p["t_start_ms"]), input_domains=domains,
                           input_step_ms=step, verification_mode="auto")
        signal.alarm(0)
        print(f"Explorer: {pr.claim} closed={pr.closed} states={pr.n_states} {time.time() - started:.1f}s "
              f"notes={[str(n)[:120] for n in pr.notes][-2:]}")
    except TimeoutError:
        print(f"Explorer: TIMEOUT after {args.budget}s")


if __name__ == "__main__":
    main()
