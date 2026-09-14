"""E2 supplementary histories (after the freeze; PROTOCOL_DRAFT §9, rule fixed on 2026-09-14 before generation).

~/temp/bin/python make_supplement.py      (run from histories/)

Why: the hand inspection of the frozen run (INSPECTION_2026-09-14.md) found two gaps in the frozen histories that
apply to every case: almost every case has a single start state, and at most 300 pulse histories are kept per case.
The rule is the same for every case and reads only the frozen history files and the pairs' base IR, binding,
devices and start time. It never reads a JoI script, a fault, an Explorer verdict or a witness.

Per base case
A. start states. Keys K = the inputs the IR compares with a literal (frozen `stats.compared_values`) plus their
   siblings: the same member on every other device of the case that shares a category with the compared device and
   whose key is in the seed start state. Values per key: BOOL both; numbers the seed start value and every compared
   literal v of the member as v - s, v, v + s (step s as in the frozen generator); strings the seed start value and
   the compared literals. No None. Each seed gets its t = 0 values replaced by every assignment of K (full product)
   when the product has at most CAP_START assignments, otherwise by every single-key change plus seeded random joint
   assignments up to CAP_START. The assignment equal to the seed itself is dropped.
B. more pulses. The pulse histories of the frozen generator (`make_e1_histories.build_case`, same rules) are
   regenerated without the cap; those already in the frozen files are removed; up to CAP_PULSE are sampled with seed
   SUPP_SEED.
Self-check: the frozen generator is first rerun with its own cap from the same inputs and must reproduce the frozen
histories exactly.
"""
import copy
import hashlib
import itertools
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import make_e1_histories as mk  # noqa: E402

CAP_START, CAP_PULSE, SUPP_SEED = 200, 1500, "20260914-supp"
FROZEN = [HERE / "e1_histories.json", HERE / "sample_388_histories.json"]
PAIRS = [HERE.parent / "pairs/e1_pairs.json", HERE.parent / "pairs/sample_388_pairs.json"]


def case_inputs():
    """Base IR (automations merged), binding, devices and start time per base case, from the pair files."""
    cases = {}
    for f in PAIRS:
        for p in json.loads(f.read_text())["pairs"]:
            c = cases.setdefault(p["base_case"], dict(irs={}, binding=p["binding"], devices=p["devices"],
                                                      t_start=p["t_start_ms"]))
            c["irs"].setdefault(p.get("automation") or "main", p["ir"])
    for c in cases.values():
        c["ir"] = {"timeline": [s for ir in c["irs"].values() for s in ir["timeline"]]}
    return cases


def parse_literal(tok, cur):
    if isinstance(cur, bool):
        return tok == "True"
    if isinstance(cur, (int, float)):
        try:
            v = float(tok)
        except ValueError:
            return None
        return int(v) if v.is_integer() else v
    return tok if isinstance(cur, str) else None


def key_values(cur, literals):
    if isinstance(cur, bool):
        return [False, True]
    if isinstance(cur, (int, float)):
        lits = [v for v in literals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        step = 1 if isinstance(cur, int) and all(isinstance(v, int) for v in lits) else 0.1
        vals = {cur} | {v + d for v in lits for d in (-step, 0, step)}
        return sorted({round(v, 1) if step == 0.1 else v for v in vals})
    if isinstance(cur, str):
        return sorted({cur} | {v for v in literals if isinstance(v, str)})
    return []


def start_keys(compared, devices, t0):
    keys = {}
    for key, toks in compared.items():
        dev, member = key.split(".", 1)
        cats = set((devices.get(dev) or {}).get("category") or [])
        for other in t0:
            odev, omember = other.split(".", 1)
            if other == key or (omember == member and cats & set((devices.get(odev) or {}).get("category") or [])):
                keys.setdefault(other, set()).update(toks)
    return {k: v for k, v in sorted(keys.items()) if k in t0}


def start_variants(cid, seed, compared, devices):
    t0 = seed["events"][0][1]
    keys = start_keys(compared, devices, t0)
    domains = {k: key_values(t0[k], [parse_literal(x, t0[k]) for x in toks]) for k, toks in keys.items()}
    domains = {k: v for k, v in domains.items() if len(v) > 1}
    names = list(domains)
    size = 1
    for k in names:
        size *= len(domains[k])
    base = tuple(t0[k] for k in names)
    if size <= CAP_START:
        combos = [c for c in itertools.product(*(domains[k] for k in names)) if c != base]
    else:
        combos = []
        for i, k in enumerate(names):
            for v in domains[k]:
                if v != t0[k]:
                    combos.append(base[:i] + (v,) + base[i + 1:])
        rng = random.Random(f"{SUPP_SEED}:{cid}:{seed['name']}:start")
        seen = set(combos) | {base}
        tries = 0
        while len(combos) < CAP_START and tries < 100 * CAP_START:
            tries += 1
            c = tuple(rng.choice(domains[k]) for k in names)
            if c not in seen:
                seen.add(c)
                combos.append(c)
        combos = combos[:CAP_START]
    out = []
    for c in combos:
        ev = copy.deepcopy(seed["events"])
        ev[0][1].update(dict(zip(names, c)))
        label = ",".join(f"{k}={v}" for k, v, b in zip(names, c, base) if v != b)
        out.append(dict(name=f"{seed['name']}~start:{label}", origin="supp-start", events=ev, horizon=seed["horizon"]))
    return out, {k: domains[k] for k in names}


def main():
    frozen_hist, frozen_stats = {}, {}
    for f in FROZEN:
        d = json.loads(f.read_text())
        frozen_hist.update(d["histories"])
        frozen_stats.update(d["stats"])
    cases = case_inputs()
    assert set(cases) == set(frozen_hist)
    result, stats = {}, {}
    for cid in sorted(cases):
        c = cases[cid]
        seeds = [dict(name=h["name"], events=h["events"], horizon=h["horizon"])
                 for h in frozen_hist[cid] if h["origin"] == "seed"]
        mk.CAP = 300
        again, _ = mk.build_case(cid, c["ir"], c["binding"], c["t_start"], seeds)
        assert json.loads(json.dumps(again)) == frozen_hist[cid], f"frozen generator not reproduced for {cid}"
        mk.CAP = 10 ** 9
        every, _ = mk.build_case(cid, c["ir"], c["binding"], c["t_start"], seeds)
        kept = {h["name"] for h in frozen_hist[cid]}
        extra = [h for h in every if h["origin"] == "pulse" and h["name"] not in kept]
        n_extra = len(extra)
        if len(extra) > CAP_PULSE:
            extra = random.Random(f"{SUPP_SEED}:{cid}:pulse").sample(extra, CAP_PULSE)
            extra.sort(key=lambda h: h["name"])
        for h in extra:
            h["origin"] = "supp-pulse"
        starts, domains = [], {}
        for s in seeds:
            hs, dom = start_variants(cid, s, frozen_stats[cid]["compared_values"], c["devices"])
            starts += hs
            domains[s["name"]] = {k: list(map(str, v)) for k, v in dom.items()}
        result[cid] = json.loads(json.dumps(starts + extra))
        stats[cid] = dict(n_start=len(starts), start_domains=domains, n_pulse_candidates=n_extra, n_pulse=len(extra))
        print(f"{cid:10s} start {len(starts):4d}  pulses {len(extra):4d}/{n_extra}")
    files = [HERE / "make_supplement.py", HERE / "make_e1_histories.py", *FROZEN, *PAIRS]
    out = {"inputs_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
           "cap_start_per_seed": CAP_START, "cap_pulse_per_case": CAP_PULSE, "seed": SUPP_SEED,
           "stats": stats, "histories": result}
    (HERE / "supplement_histories.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("total", sum(len(v) for v in result.values()))


if __name__ == "__main__":
    main()
