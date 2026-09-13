"""E2 input histories for the E1 20 base cases (protocol D1: boundary-structured, original time scale).

~/temp/bin/python make_e1_histories.py      (run from histories/)

Built from the base IR and the author-audited E1 histories only — never from a JoI script, a fault variant, a
reference result or an Explorer result. Every pair of a base case is later run on the same histories.

Per base case
1. seeds: every E1 history of the case (Stage A `cases.py`, depth v2 `depth_cases_v2.py`), without the E1-092
   fault injection (E2 pairs are single automations without injected failures);
2. shifts: each seed with one input change moved by -100 ms or +100 ms (order and t > 0 preserved);
3. pulses: each seed with one extra excursion of one input — set to an alternative value at instant t and restored
   at t + p — where
   - t comes from anchors (0, seed change instants, instants where a Clock.Hour literal of the IR starts or stops
     holding), each anchor + 1 s / 10 s / 60 s, and each anchor + n*d - 100 / + n*d / + n*d + 100 for every literal
     duration d of the IR, n = 1..10,
   - p is 100 ms, 1 s, or d - 100 / d / d + 100,
   - alternative values: BOOL flip; numbers compared with a literal v take v - s, v, v + s (s = 1 for integers,
     0.1 otherwise) when different from the current value; numbers never compared with a literal (only observed)
     take the current value -s / +s and the seed values; strings take the compared literals and the seed values;
   - a pulse is skipped if the seed changes the same input inside [t, t + p] or t + p exceeds the horizon;
   - additionally, every pair of BOOL inputs is flipped together at an anchor or anchor + 1 s and restored 1 s later
     (same-instant changes, needed to observe ordering within one reaction).
4. cap: seeds and shifts are always kept; pulses are sampled with seed 20260914 down to CAP per case.
All instants are on the 100 ms input grid (R2).
"""
import copy
import hashlib
import importlib.util
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
E1 = ROOT / "PerCom/6_Evaluation/E1_adequacy"
DEPTH = E1 / "breadth/depth"
GRID, CAP, SEED = 100, 300, 20260914
UNIT = {"HOUR": 3_600_000, "MIN": 60_000, "SEC": 1_000, "MSEC": 1}
DUR = re.compile(r"^\s*(\d+)\s+(HOUR|MIN|SEC|MSEC)\s*$")
ATOM = r"([A-Za-z_]\w*(?:\[[^\]]*\])?\.[A-Za-z_]\w*)"
CMP = re.compile(ATOM + r"\s*(==|!=|>=|<=|>|<)\s*(-?\d+(?:\.\d+)?|\"[^\"]*\"|true|false)")
HOUR = re.compile(r"Clock\.Hour\s*(==|!=|>=|<=|>|<)\s*(\d+)")


def load(name, path, extra=None):
    if extra:
        sys.path.insert(0, str(extra))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v)
    elif isinstance(node, str):
        yield node


def durations(ir):
    out = set()

    def walk(n):
        if isinstance(n, dict):
            for key in ("duration", "for", "timeout", "period"):
                m = DUR.match(n.get(key) or "") if isinstance(n.get(key), str) else None
                if m and int(m.group(1)) * UNIT[m.group(2)] > 0:
                    out.add(int(m.group(1)) * UNIT[m.group(2)])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(ir)
    for s in strings(ir):                        # elapsed-time literals in seconds (Clock.Timestamp arithmetic)
        if "Clock.Timestamp" in s:
            out.update(int(x) * 1000 for x in re.findall(r"\b(\d{2,})\b", s))
    base = sorted(out)
    out.update(a + b for a in base for b in base)  # sums of two, e.g. a deadline extended once
    return sorted(d for d in out if d % GRID == 0 or d >= GRID)


def grid(t):
    return (t // GRID) * GRID


def device_keys(atom, binding):
    """Input keys an IR atom may read: explicit `Svc[d1,...].M`, or binding list / {"any"|"all": [...]}."""
    m = re.match(r"^(\w+)\[([^\]]*)\]\.(\w+)$", atom)
    if m:
        return [f"{d.strip()}.{m.group(3)}" for d in m.group(2).split(",")]
    svc, member = atom.split(".")
    if svc == "Clock" or not binding:
        return []
    devs = []
    for slot, v in binding.items():
        if slot.split("#")[0] == svc:
            vals = v if isinstance(v, list) else [x for q in ("any", "all") for x in (v.get(q) or [])]
            devs += vals
    return [f"{d}.{member}" for d in dict.fromkeys(devs)]


def literal(tok):
    if tok in ("true", "false"):
        return tok == "true"
    if tok.startswith('"'):
        return tok[1:-1]
    return float(tok) if "." in tok else int(tok)


def hour_anchors(ir, t_start, horizon):
    hours = {int(h) for s in strings(ir) for _, h in HOUR.findall(s)}
    out = set()
    for h in hours:
        for boundary in (h, (h + 1) % 24):
            day0 = t_start - t_start % 86_400_000
            for day in range(0, 3):
                abs_t = day0 + day * 86_400_000 + boundary * 3_600_000
                if 0 < abs_t - t_start <= horizon:
                    out.add(grid(abs_t - t_start))
    return out


def state_at(events, key, t):
    val = None
    for et, upd in events:
        if et <= t and key in upd:
            val = upd[key]
    return val


def changes_of(events, key):
    return [et for et, upd in events if key in upd and et > 0]


def with_change(events, t, upd):
    ev = [(et, dict(u)) for et, u in events]
    for et, u in ev:
        if et == t:
            u.update(upd)
            break
    else:
        ev.append((t, dict(upd)))
    ev.sort(key=lambda x: x[0])
    return ev


def build_case(cid, ir, binding, t_start, seeds):
    durs = durations(ir)
    cmp_values = {}
    for s in strings(ir):
        for atom, _, tok in CMP.findall(s):
            for k in device_keys(atom, binding):
                cmp_values.setdefault(k, set()).add(literal(tok))
    out = []
    for si, seed in enumerate(seeds):
        ev = [(int(t), dict(u)) for t, u in seed["events"]]
        horizon = int(seed["horizon"])
        out.append(dict(name=f"{seed['name']}", origin="seed", events=ev, horizon=horizon))
        for i, (t, upd) in enumerate(ev):
            if t == 0:
                continue
            for delta in (-GRID, GRID):
                nt = t + delta
                prev_t = ev[i - 1][0] if i > 0 else 0
                next_t = ev[i + 1][0] if i + 1 < len(ev) else horizon + 1
                if prev_t < nt < next_t:
                    nev = [(nt if j == i else et, dict(u)) for j, (et, u) in enumerate(ev)]
                    out.append(dict(name=f"{seed['name']}~shift{i}{delta:+d}", origin="shift", events=nev,
                                    horizon=horizon))
    pulses = []
    for seed in seeds:
        ev = [(int(t), dict(u)) for t, u in seed["events"]]
        horizon = int(seed["horizon"])
        keys = sorted(ev[0][1])
        anchors = {0} | {t for t, _ in ev} | hour_anchors(ir, t_start, horizon)
        starts = set(anchors)
        for a in anchors:
            starts.update({a + GENERIC for GENERIC in (1000, 10_000, 60_000)})
        for a in anchors:
            for d in durs:
                for n in range(1, 11):
                    if a + n * d - GRID > horizon:
                        break
                    starts.update({a + n * d - GRID, a + n * d, a + n * d + GRID})
        starts = sorted(grid(x) for x in starts if 0 < x <= horizon)
        lengths = sorted({GRID, 1000} | {x for d in durs for x in (d - GRID, d, d + GRID) if x > 0})
        for key in keys:
            for t in starts:
                cur = state_at(ev, key, t)
                if isinstance(cur, bool):
                    alts = [not cur]
                elif isinstance(cur, (int, float)):
                    step = 1 if isinstance(cur, int) and all(isinstance(v, int) for v in cmp_values.get(key, ())) else 0.1
                    lits = [v for v in cmp_values.get(key, ()) if isinstance(v, (int, float))]
                    if lits:
                        cand = {v + dv for v in lits for dv in (-step, 0, step)}
                    else:   # value only observed (e.g. an ACTION argument): one step either side and seed values
                        cand = {cur - step, cur + step} | {u[key] for _, u in ev if key in u}
                    alts = sorted({round(v, 1) if step == 0.1 else v for v in cand} - {cur})
                elif isinstance(cur, str):
                    seen = {u[key] for _, u in ev if key in u}
                    alts = sorted(({v for v in cmp_values.get(key, ()) if isinstance(v, str)} | seen) - {cur})
                else:
                    alts = []
                for alt in alts:
                    for p in lengths:
                        end = t + p
                        if end > horizon or any(t <= c <= end for c in changes_of(ev, key)):
                            continue
                        nev = with_change(with_change(ev, t, {key: alt}), end, {key: cur})
                        pulses.append(dict(name=f"{seed['name']}~pulse:{key}={alt}@{t}+{p}", origin="pulse",
                                           events=nev, horizon=horizon))
        # same-instant changes of two inputs (BOOL flips) at anchors and anchor + 1 s, held for 1 s
        bool_keys = [k for k in keys if isinstance(ev[0][1][k], bool)]
        for i, k1 in enumerate(bool_keys):
            for k2 in bool_keys[i + 1:]:
                for t in sorted(grid(a + off) for a in anchors for off in (0, 1000) if 0 < a + off <= horizon):
                    end = t + 1000
                    if end > horizon or any(t <= c <= end for k in (k1, k2) for c in changes_of(ev, k)):
                        continue
                    c1, c2 = state_at(ev, k1, t), state_at(ev, k2, t)
                    nev = with_change(with_change(ev, t, {k1: not c1, k2: not c2}), end, {k1: c1, k2: c2})
                    pulses.append(dict(name=f"{seed['name']}~pair:{k1},{k2}@{t}+1000", origin="pulse",
                                       events=nev, horizon=horizon))
    rng = random.Random(f"{SEED}:{cid}")
    n_pulses = len(pulses)
    if len(pulses) > CAP:
        pulses = rng.sample(pulses, CAP)
        pulses.sort(key=lambda h: h["name"])
    return out + pulses, dict(durations_ms=durs, compared_values={k: sorted(map(str, v)) for k, v in cmp_values.items()},
                              n_seed_shift=len(out), n_pulses_generated=n_pulses, n_pulses_kept=len(pulses))


def main():
    cases = load("e1_cases", E1 / "cases.py")
    irs = load("e1_irs", E1 / "irs.py")
    dcases = load("depth_cases_v2", DEPTH / "depth_cases_v2.py", DEPTH)
    dattempts = load("depth_attempts_v2", DEPTH / "depth_attempts_v2.py", DEPTH)
    result, stats = {}, {}
    for c in cases.CASES:
        seeds = [dict(name=h.get("name", f"h{i}"), events=h["events"], horizon=h["horizon"])
                 for i, h in enumerate(c["histories"])]
        hs, st = build_case(c["id"], irs.IRS[c["id"]]["ir"], c["binding"], c["t_start_ms"], seeds)
        result[c["id"]], stats[c["id"]] = hs, st
    for c in dcases.CASES:
        seeds = [dict(name=h.get("name", f"h{i}"), events=h["events"], horizon=h["horizon"])
                 for i, h in enumerate(c["histories"])]
        irs_of_case = [a["ir"] for a in dattempts.ATTEMPTS[c["id"]]["automations"]]
        merged_ir = {"timeline": [s for ir in irs_of_case for s in ir["timeline"]]}
        hs, st = build_case(c["id"], merged_ir, None, c["t_start_ms"], seeds)
        result[c["id"]], stats[c["id"]] = hs, st
    for cid, hs in result.items():
        for h in hs:
            for t, _ in h["events"]:
                assert t % GRID == 0 and t >= 0, (cid, h["name"], t)
            assert h["events"][0][0] == 0
    src_files = [HERE / "make_e1_histories.py", E1 / "cases.py", E1 / "irs.py", DEPTH / "depth_cases.py",
                 DEPTH / "depth_cases_v2.py", DEPTH / "depth_attempts.py", DEPTH / "depth_attempts_v2.py"]
    out = {"inputs_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in src_files},
           "grid_ms": GRID, "cap_pulses_per_case": CAP, "seed": SEED, "stats": stats, "histories": result}
    (HERE / "e1_histories.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for cid, st in stats.items():
        print(f"{cid:8s} seeds+shifts {st['n_seed_shift']:3d}  pulses {st['n_pulses_kept']:3d}/{st['n_pulses_generated']:5d}  "
              f"durations {len(st['durations_ms'])}")
    print("total", sum(len(v) for v in result.values()))


if __name__ == "__main__":
    main()
