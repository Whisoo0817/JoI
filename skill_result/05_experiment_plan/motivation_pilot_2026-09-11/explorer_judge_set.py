"""Run the Behavioral Explorer on the judge program set (runs/judge/programs.json).

Explorer contract is exact-time. A DIVERGE is re-judged with the pilot's 1 s tolerance
by replaying its witness through the harness; if the witness differs only within 1 s it
is reported as `timing_only` (inconclusive about other, larger differences).

python explorer_judge_set.py [--step 1000] [--timeout 300] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explorer_check as ec  # noqa: E402


def _gate_step(args):
    task_id, block, q, step = args
    try:
        from harness import TASK_BY_ID
        from explorer.verification.gate import gate_pair
        t = TASK_BY_ID[task_id]
        g = gate_pair(t["ir"], t["binding"], t["devices"], block, horizon_ms=None,
                      input_step_ms=step, input_domains=ec.pilot_domains(t))
        out = {"verdict": g.verdict, "notes": [str(n)[:400] for n in g.notes[-3:]],
               "search_seconds": round(g.product.seconds or 0.0, 3) if g.product else None,
               "n_states": g.product.n_states if g.product else None}
        if g.verdict == "DIVERGE" and g.product and g.product.divergences:
            d = g.product.divergences[0]
            rp = next((r for r in g.replays if r.confirmed), None)
            out["witness"] = {"path": [[inp, dwell] for inp, dwell in d.path] + [[d.input_, d.dwell_ms]],
                              "ir_actions": repr(rp.actions_a) if rp else None,
                              "code_actions": repr(rp.actions_b) if rp else None}
        q.put(out)
    except Exception as e:  # noqa: BLE001
        q.put({"verdict": "ERROR", "notes": [f"{type(e).__name__}: {e}"]})


def run_one(pid, prog, step, timeout):
    import multiprocessing as mp
    import queue as queue_mod
    import time as time_mod
    # spawn, not fork: forking from worker threads can copy held locks into the
    # child and hang it (observed as spurious TIMEOUTs). Drain the queue before
    # join so a large witness cannot block the child on a full pipe.
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_gate_step, args=((prog["task"], prog["block"], q, step),))
    started = time_mod.perf_counter()
    p.start()
    try:
        res = q.get(timeout=timeout)
    except queue_mod.Empty:
        res = {"verdict": "TIMEOUT", "notes": [f">{timeout}s"]}
    p.join(5)
    if p.is_alive():
        p.kill()
    res["wall_seconds"] = round(time_mod.perf_counter() - started, 2)
    if res["verdict"] == "DIVERGE" and res.get("witness"):
        try:
            res["tolerant"] = ec.tolerant_recheck(prog["task"], prog["block"], res["witness"])
        except Exception as e:  # noqa: BLE001
            res["tolerant"] = {"error": f"{type(e).__name__}: {e}"}
    return {"program": pid, "task": prog["task"], "label": prog["label"], "kind": prog["kind"], "explorer": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, default=1000)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    progs = json.loads((HERE / "runs" / "judge" / "programs.json").read_text())
    items = [(pid, p) for pid, p in progs.items() if not a.only or pid in a.only]
    out_path = HERE / "runs" / "judge" / f"explorer_step{a.step}.jsonl"
    done = {}
    if out_path.exists() and not a.only:
        for line in out_path.read_text().splitlines():
            r = json.loads(line)
            done[r["program"]] = r
    todo = [(pid, p) for pid, p in items if pid not in done]
    print(f"{len(todo)} programs to check (step {a.step} ms)", flush=True)
    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(lambda it: run_one(it[0], it[1], a.step, a.timeout), todo):
            e = r["explorer"]
            tag = ""
            if "tolerant" in e:
                tag = "timing_only" if e["tolerant"].get("timing_only_within_1s") else ("real" if "error" not in e["tolerant"] else "recheck_error")
            print(r["program"], r["label"], "explorer:", e["verdict"], tag, e.get("wall_seconds"), "s", flush=True)
            if not a.only:
                with out_path.open("a") as f:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            else:
                print(json.dumps(e, default=str)[:1500])


if __name__ == "__main__":
    main()
