#!/usr/bin/env python3
"""Dense-stimulus replay: validate boundary-scenario verdicts on a sample.

For each sampled row (verifier-PASS and verifier-FAIL), replay the (gt_ir,
generated JoI) pair under K randomized dense scenarios that go far beyond the
boundary set: values sampled across each sensor's whole declared domain (not
just boundaries), event times off the boundary grid, multiple toggles, plus
noise events on unrelated keys. Compare IR-sim and JoI-sim traces with the
same comparator the verifier uses (l2_runtime.check with injected scenarios
is NOT used; we call the two simulators + trace comparison directly so the
scenario source is the only thing that changes).

Purpose (paper §8.2 audit): on PASS rows, dense replay surfacing no
disagreement = the boundary set missed nothing on this sample; on FAIL rows,
dense replay reproducing the divergence = the flag was not a scenario
artifact. Every disagreement is dumped for human adjudication.

Usage:
  PYTHONPATH=. python3 paper/run_dense_replay.py \
      --run-dir experiments/stageB_382/20260528_170116__d886015/intermediate \
      --pass-rows C01_3,C05_2,... --fail-rows C16_3,C18_5,... \
      --k 500 --seed 7 --out paper/Final/evaluation/results/dense_replay.json

Deterministic given --seed. No LLM, CPU only.
"""
import argparse, csv, json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "paper"))
CSV_PATH = os.path.join(ROOT, "dataset.csv")


def load_rows():
    rows = {}
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            c = (r.get("category_v2") or "").strip(); i = (r.get("index") or "").strip()
            if c and i:
                rows[f"{c}_{i}"] = r
    return rows


def ir_sensor_keys(ir):
    """Collect 'service.attr' keys read by the IR (conds + read srcs)."""
    import re
    keys = set()
    def walk(node):
        if isinstance(node, dict):
            for f in ("cond", "until", "src"):
                v = node.get(f)
                if isinstance(v, str):
                    for m in re.finditer(r"([A-Za-z][A-Za-z0-9]*)\.([A-Za-z][A-Za-z0-9]*)", v):
                        svc, attr = m.group(1), m.group(2)
                        if svc.lower() not in ("clock",):
                            keys.add(f"{svc.lower()}.{attr.lower()}")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(ir)
    return sorted(keys)


def sample_value(rng, dom, base_scn_values):
    """Sample a value across the key's whole domain (not just boundaries)."""
    if dom:
        t = (dom.get("type") or "").upper()
        if t == "BOOLEAN":
            return rng.choice([True, False])
        if t == "ENUM" and dom.get("members"):
            return rng.choice(dom["members"])
        b = dom.get("bound")
        if b and len(b) == 2 and all(isinstance(x, (int, float)) for x in b):
            v = rng.uniform(b[0], b[1])
            return round(v, 1) if t == "DOUBLE" else int(v)
    # No domain info: fall back to perturbations of values seen in boundary scenarios
    if base_scn_values:
        v = rng.choice(base_scn_values)
        if isinstance(v, bool):
            return rng.choice([True, False])
        if isinstance(v, (int, float)):
            return type(v)(v + rng.choice([-50, -10, -2, -1, 0, 1, 2, 10, 50]) * rng.random())
        return v
    return rng.choice([True, False, 0, 1, 50, "on", "off"])


def make_dense_scenario(rng, base_scn, keys, domains, horizon_ms):
    """Randomized scenario: dense events on IR keys + noise on unrelated keys."""
    from paper.simulators.scenario import Scenario, ScenarioEvent
    base_values = [e.value for e in base_scn.events]
    events = []
    n_events = rng.randint(8, 40) if keys else 0
    for _ in range(n_events):
        key = rng.choice(keys)
        t = rng.randint(0, max(horizon_ms - 1, 1))
        dom = domains.get(tuple(k.capitalize() for k in key.split(".", 1))) or \
              next((v for (s, a), v in domains.items()
                    if s.lower() == key.split(".")[0] and a.lower() == key.split(".")[1]), None)
        events.append(ScenarioEvent(at_ms=t, key=key, value=sample_value(rng, dom, base_values)))
    # noise events on unrelated keys (robustness: must not change either trace)
    for _ in range(rng.randint(2, 6)):
        t = rng.randint(0, max(horizon_ms - 1, 1))
        events.append(ScenarioEvent(at_ms=t, key="noisesensor.noise", value=rng.randint(0, 100)))
    events.sort(key=lambda e: e.at_ms)
    return Scenario(initial_world=dict(base_scn.initial_world), events=events,
                    start_clock=base_scn.start_clock, start_dow=base_scn.start_dow)


def compare(tr_ir, tr_joi):
    """Use the verifier's own comparator (grouping/dedup/tolerance identical)."""
    from paper.simulators.comparator import compare_traces as _ct
    res = _ct(tr_ir, tr_joi)
    return res.equivalent, (res.diff_summary or "")[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--arm", default="off")
    ap.add_argument("--pass-rows", default="")
    ap.add_argument("--fail-rows", default="")
    ap.add_argument("--k", type=int, default=500)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="/tmp/dense_replay.json")
    a = ap.parse_args()

    from paper.simulators.event_synth import synthesize_scenarios
    from paper.simulators.ir_simulator import run_ir_simulation
    from paper.simulators.joi_simulator import run_joi_simulation
    from paper.simulators.catalog import value_domains as load_value_domains
    from paper.run_local_ir import _load_catalog

    cat = _load_catalog()
    try:
        domains = load_value_domains()
    except Exception:
        domains = {}
    rows = load_rows()
    targets = ([(n, "pass") for n in a.pass_rows.split(",") if n.strip()] +
               [(n, "fail") for n in a.fail_rows.split(",") if n.strip()])

    report = []
    for name, side in targets:
        r = rows[name]
        ir = json.loads(r["ir_gt"])
        d = json.load(open(os.path.join(a.run_dir, a.arm, f"{name}.json"), encoding="utf-8"))
        joi = d.get("joi_block")
        base_scns = synthesize_scenarios(ir)
        keys = ir_sensor_keys(ir)
        # horizon: end of boundary scenario events + a margin, capped
        ev_max = max([e.at_ms for s in base_scns for e in s.events], default=0)
        horizon = min(max(ev_max + 3_600_000, 7_200_000), 48 * 3_600_000)
        rng = random.Random(f"{a.seed}:{name}")
        disagreements, n_ok, n_err = [], 0, 0
        for k in range(a.k):
            scn = make_dense_scenario(rng, base_scns[0], keys, domains, horizon)
            try:
                tr_ir = run_ir_simulation(ir, scn, cat)
                tr_joi = run_joi_simulation(joi, scn, cat)
                t_ir, t_joi = tr_ir.records, tr_joi.records
            except Exception as e:
                n_err += 1
                disagreements.append({"k": k, "kind": "sim-error",
                                      "detail": f"{type(e).__name__}: {str(e)[:120]}"})
                continue
            same, why = compare(tr_ir, tr_joi)
            if same:
                n_ok += 1
            else:
                disagreements.append({
                    "k": k, "kind": "trace-mismatch", "detail": why,
                    "events": [(e.at_ms, e.key, e.value) for e in scn.events][:20],
                    "ir_trace": [(t.timestamp_ms, t.service, t.method, list(t.args)) for t in t_ir][:10],
                    "joi_trace": [(t.timestamp_ms, t.service, t.method, list(t.args)) for t in t_joi][:10],
                })
        report.append({"name": name, "side": side, "k": a.k, "agree": n_ok,
                       "sim_errors": n_err,
                       "n_disagree": len([x for x in disagreements if x["kind"] == "trace-mismatch"]),
                       "disagreements": disagreements[:25]})
        print(f"{name} [{side}] agree {n_ok}/{a.k}  mismatch "
              f"{len([x for x in disagreements if x['kind']=='trace-mismatch'])}  err {n_err}")

    meta = {"seed": a.seed, "k": a.k, "run_dir": a.run_dir, "arm": a.arm}
    json.dump({"meta": meta, "rows": report}, open(a.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
