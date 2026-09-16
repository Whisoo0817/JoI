"""E4 follow-ups (decided with whisoo 2026-09-16).

  ~/temp/bin/python run_followup.py solo   -> runs/e4_boundary_solo.jsonl
  ~/temp/bin/python run_followup.py long   -> runs/e4_free_long.jsonl

solo: the two boundary cells of the main run (1/3 completed there under 12 parallel
      workers), re-run one at a time with the same 120 s budget, 3 repeats.
long: every cell the horizon-free mode did not finish in the main run, once, with a
      30 min budget, to see whether it finishes, stops at the Explorer's own search
      caps (max_states / max_transitions), or is still running.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_e4

SOLO = [{"w": 2, "b": 2, "t_ms": 120000, "k": 200}, {"w": 5, "b": 5, "t_ms": 120000, "k": 20}]
LONG = SOLO + [{"w": 6, "b": 6, "t_ms": 120000, "k": 50}, {"w": 7, "b": 6, "t_ms": 120000, "k": 100}]


def cid(kw):
    return f"W{kw['w']}_B{kw['b']}_T{kw['t_ms']}_K{kw['k']}"


def main():
    what = sys.argv[1]
    if what == "solo":
        out, cells, reps = HERE / "runs/e4_boundary_solo.jsonl", SOLO, 3
    else:
        out, cells, reps = HERE / "runs/e4_free_long.jsonl", LONG, 1
        run_e4.BUDGET_S = 1800
    with out.open("a") as fh:
        for kw in cells:
            for rep in range(reps):
                job = {"cell_id": cid(kw), "mode": "free", "rep": rep, "kw": dict(kw, horizon_ms=None)}
                r = run_e4.run_one(job)
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"{r['cell_id']:<22} r{rep} {r['verdict']:<8} {r.get('wall_seconds', 0):8.1f}s "
                      f"states={r.get('n_states')} transitions={r.get('n_steps')}", flush=True)


if __name__ == "__main__":
    main()
