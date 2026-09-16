"""Why did the horizon-free mode not finish some cells? (whisoo question, 2026-09-16)

  ~/temp/bin/python diag_unfinished.py W6_B6_T120000_K50 real|lifted

Runs gate_pair(horizon_ms=None) with a wrapper around the timer-zone proof
(explorer.verification.timer_product.timer_product) that records how that proof ended
and then stops the run, so the concrete fallback search is not measured here.

real   - the Explorer as it is.
lifted - DIAGNOSTIC ONLY: the timer-zone module sees a clock running 1000x slower,
         so its 30 s / 90 s wall-clock give-ups never trigger; the count caps
         (max_states, max_transitions) stay as they are. Shows whether the proof
         would finish given time, or hits a count cap. Not a reported E4 mode.
"""
import json, re, sys, time, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_grid import make_pair
import explorer.verification.timer_product as tp
from explorer.verification.gate import gate_pair


class Stop(BaseException):
    pass


def main():
    cell, mode = sys.argv[1], sys.argv[2]
    w, b, t, k = map(int, re.fullmatch(r"W(\d+)_B(\d+)_T(\d+)_K(\d+)", cell).groups())
    if mode == "lifted":
        tp.time = types.SimpleNamespace(perf_counter=lambda: time.perf_counter() / 1000)
    inner, rec = tp.timer_product, {"cell_id": cell, "mode": mode}

    def wrapped(*a, **kw):
        t0 = time.perf_counter()
        try:
            r = inner(*a, **kw)
            rec.update(outcome=r.verdict, closed=r.closed, n_states=r.n_states, n_steps=r.n_steps)
        except tp.Unsupported as e:
            rec.update(outcome="GAVE-UP", reason=str(e))
        rec["timer_zone_seconds"] = time.perf_counter() - t0
        raise Stop

    tp.timer_product = wrapped
    c = make_pair(w=w, b=b, t_ms=t, k=k)
    try:
        gate_pair(c["ir"], c["binding"], c["devices"], c["joi"], horizon_ms=None)
        rec.setdefault("outcome", "timer-zone proof not attempted")
    except Stop:
        pass
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
