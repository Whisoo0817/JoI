"""E4 cost run: Explorer cost and completion across the scale grid.

  ~/temp/bin/python run_e4.py [--workers 8] [--repeats 3] [--modes free,fixed10,fixedT] [--out ...]

Worker count matters for the horizon-free mode, not only for its wall time: the
Explorer's timer-zone proof gives up after 30 s of wall clock (timer_product.py) and
falls back to the concrete search, so an overloaded machine turns a 20 s proof into a
TIMEOUT. The horizon-free mode is therefore run with --workers 1. The fixed-horizon
modes have no wall-clock budget inside the Explorer and are run with 4 workers on the
8-core machine. runs/e4_run.jsonl (12 workers, all modes) is kept only as the record
of the overloaded first run and is not the reported result.

Each (program, horizon mode, repeat) runs in its own process (e4_worker) under a
120 s budget - the same budget the E2 run used, so the two are read on one scale.
A run that exceeds it is recorded as TIMEOUT and stays in the denominator; so do
ERROR, OOM, REFUSED and UNKNOWN. Nothing is dropped.

Three horizon modes, reported separately (confirmed_ir_evaluation_2026-09-10 §E4):
  free    horizon_ms=None   - the closure the Explorer actually claims
  fixed10 horizon_ms=10 s   - a cheap bounded horizon that covers only the opening
  fixedT  horizon_ms=2*T+5s - a bounded horizon wide enough to cover the behaviour
A bounded run that finishes returns EQUIV-BOUNDED, which holds only up to H; it is
never merged with the unbounded EQUIV.

This measures cost and completion only. Verdict correctness is E2's question, so
no independent reference oracle runs here.
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = str(Path.home() / "temp/bin/python")
BUDGET_S = 120


MODES = ("free", "fixed10", "fixedT")


def jobs(repeats, modes=MODES):
    sys.path.insert(0, str(HERE))
    from gen_grid import grid
    seen, out = {}, []
    for c in grid():
        seen.setdefault(c["cell_id"], c)          # same program can sit on two sweeps
    for cell_id, c in seen.items():
        for mode, h in (("free", None), ("fixed10", 10_000),
                        ("fixedT", 2 * c["kw"]["t_ms"] + 5000)):
            if mode not in modes:
                continue
            for rep in range(repeats):
                out.append({"cell_id": cell_id, "mode": mode, "rep": rep,
                            "kw": dict(c["kw"], horizon_ms=h)})
    return out, seen


def run_one(job):
    t0 = time.perf_counter()
    try:
        p = subprocess.run([PY, str(HERE / "e4_worker.py"), json.dumps(job["kw"])],
                           capture_output=True, text=True, timeout=BUDGET_S + 15)
    except subprocess.TimeoutExpired:
        return {**_tag(job), "verdict": "TIMEOUT", "closed": False,
                "wall_seconds": time.perf_counter() - t0, "budget_s": BUDGET_S}
    line = (p.stdout or "").strip().splitlines()
    if p.returncode != 0 or not line:
        return {**_tag(job), "verdict": "ERROR", "closed": False,
                "error": (p.stderr or "")[-500:] or f"exit {p.returncode}",
                "wall_seconds": time.perf_counter() - t0}
    rec = json.loads(line[-1])
    if rec.get("wall_seconds", 0) > BUDGET_S:
        rec["verdict"], rec["closed"] = "TIMEOUT", False
    return {**_tag(job), **rec, "budget_s": BUDGET_S}


def _tag(job):
    return {"cell_id": job["cell_id"], "mode": job["mode"], "rep": job["rep"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default=str(HERE / "runs/e4_run.jsonl"))
    ap.add_argument("--modes", default=",".join(MODES))
    a = ap.parse_args()

    todo, cells = jobs(a.repeats, tuple(a.modes.split(",")))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():                                  # restartable
        for ln in out.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                done.add((r["cell_id"], r["mode"], r["rep"]))
    todo = [j for j in todo if (j["cell_id"], j["mode"], j["rep"]) not in done]
    print(f"{len(cells)} programs, {len(todo)} runs to go "
          f"({len(done)} already recorded), {a.workers} workers, {BUDGET_S}s budget",
          flush=True)

    t0, n = time.perf_counter(), 0
    with out.open("a") as fh, ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(run_one, j): j for j in todo}
        for f in as_completed(futs):
            r = f.result()
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            print(f"[{n}/{len(todo)}] {r['cell_id']:<24} {r['mode']:<5} r{r['rep']} "
                  f"{r['verdict']:<8} {r.get('wall_seconds', 0):7.2f}s "
                  f"rss={r.get('peak_rss_mb', 0):6.1f}MB", flush=True)
    print(f"done in {time.perf_counter() - t0:.1f}s -> {out}")


if __name__ == "__main__":
    main()
