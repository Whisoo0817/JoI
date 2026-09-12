"""Secondary check: run the Behavioral Explorer (unbounded gate) on every candidate
that passed all hand-written histories, to count divergences those tests missed.

A DIVERGE counts only when its witness replays concretely (gate already requires
this). Exact-time divergences are then re-judged by the 1 s tolerance of the pilot:
the witness input path is replayed through the pilot harness comparator.

python explorer_check.py --model qwen9b   -> runs/explorer_<model>.jsonl
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _gate(args):
    task_id, block, q = args
    try:
        from harness import TASK_BY_ID
        from explorer.verification.gate import gate_pair
        t = TASK_BY_ID[task_id]
        g = gate_pair(t["ir"], t["binding"], t["devices"], block, horizon_ms=None,
                      input_step_ms=2000, input_domains=pilot_domains(t))
        out = {"verdict": g.verdict, "notes": g.notes[-3:]}
        if g.verdict == "DIVERGE" and g.product and g.product.divergences:
            d = g.product.divergences[0]
            rp = next((r for r in g.replays if r.confirmed), None)
            out["witness"] = {"path": [[inp, dwell] for inp, dwell in d.path] + [[d.input_, d.dwell_ms]],
                              "initial_gv": d.initial_gv,
                              "ir_actions": repr(rp.actions_a) if rp else None,
                              "code_actions": repr(rp.actions_b) if rp else None,
                              "at_step": rp.at_step if rp else None}
        q.put(out)
    except Exception as e:  # noqa: BLE001
        q.put({"verdict": "ERROR", "notes": [f"{type(e).__name__}: {e}"]})


def pilot_domains(task):
    """Pilot input model: every value that appears in the task's histories, no missing value."""
    from harness import history_inputs
    doms = {}
    for h in task["histories"]:
        for upd in history_inputs(h["events"]).values():
            for k, v in upd.items():
                if v not in doms.setdefault(k, []):
                    doms[k].append(v)
    return doms


def tolerant_recheck(task_id, block, witness):
    """Replay the Explorer witness as a history; compare IR and code with the 1 s tolerance."""
    from harness import TASK_BY_ID, compare, postprocess_script, replay, replay_step_ms
    from explorer.verification.gate import prepare_pair
    t = TASK_BY_ID[task_id]
    events, now = [], 0
    for inp, dwell in witness["path"]:
        now += dwell
        events.append((now, {k.split(".")[0] + "." + k.split(".", 1)[1]: v for k, v in inp.items()}))
    horizon = now + 10 * 60 * 1000
    pair = prepare_pair(t["ir"], t["binding"], t["devices"], block)
    step = replay_step_ms(json.dumps(t["ir"]), block["script"], period=block["period"])
    step = __import__("math").gcd(step, 1000)
    ir_tr = replay(pair.ir_runner, events, horizon, step)
    code_tr = replay(pair.code_runner, events, horizon, step)
    cmp = compare(ir_tr, code_tr, horizon)
    return {"timing_only_within_1s": cmp["match"], "ir_trace": ir_tr[:6], "code_trace": code_tr[:6]}


def run_with_timeout(task_id, block, seconds):
    q = mp.Queue()
    p = mp.Process(target=_gate, args=((task_id, block, q),))
    p.start()
    p.join(seconds)
    if p.is_alive():
        p.kill()
        return {"verdict": "TIMEOUT", "notes": [f">{seconds}s"]}
    return q.get() if not q.empty() else {"verdict": "ERROR", "notes": ["no result"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--stages", nargs="+", default=["none", "boundary"],
                    help="which candidates: none = passed all histories, boundary = silent divergence")
    args = ap.parse_args()
    rows = [json.loads(l) for l in (HERE / "runs" / f"results_{args.model}.jsonl").read_text().splitlines()]
    out = []
    for r in rows:
        key = "none" if r["stage_failed"] is None else r["stage_failed"]
        if key not in args.stages:
            continue
        res = run_with_timeout(r["task"], r["block"], args.timeout)
        if res["verdict"] == "DIVERGE" and res.get("witness"):
            try:
                res["tolerant"] = tolerant_recheck(r["task"], r["block"], res["witness"])
            except Exception as e:  # noqa: BLE001
                res["tolerant"] = {"error": f"{type(e).__name__}: {e}"}
        rec = {k: r[k] for k in ("model", "condition", "task", "sample", "stage_failed")}
        rec.update(explorer=res)
        out.append(rec)
        print(r["condition"], r["task"], r["sample"], "hist:", key, "explorer:", res["verdict"],
              "timing_only" if res.get("tolerant", {}).get("timing_only_within_1s") else "", flush=True)
    (HERE / "runs" / f"explorer_{args.model}.jsonl").write_text(
        "\n".join(json.dumps(o, ensure_ascii=False, default=str) for o in out) + "\n")


if __name__ == "__main__":
    main()
