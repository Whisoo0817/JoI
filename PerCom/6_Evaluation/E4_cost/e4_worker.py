"""One Explorer run in its own process, so peak RSS and a hard budget are per-cell.

  ~/temp/bin/python -m e4_worker '<json params>'

params: {"w","b","t_ms","k","horizon_ms"(null=horizon-free)}
Prints one JSON object on stdout. Any failure is reported, never swallowed.
"""
import json
import resource
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    kw = json.loads(sys.argv[1])
    horizon_ms = kw.pop("horizon_ms", None)
    if kw.pop("no_timer_zones", False):
        # Baseline "explicit": the Explorer with its timer-zone step switched off, so the
        # horizon-free search falls through to exact-state exploration with next-event jumps.
        import explorer.verification.timer_product as tp
        from explorer.runtime.interp import Unsupported

        def _disabled(*a, **k):
            raise Unsupported("timer zones disabled (E4 explicit baseline)")
        tp.timer_product = _disabled
    from gen_grid import make_pair
    from explorer.verification.gate import gate_pair

    cell = make_pair(**kw)
    out = {"cell_id": cell["cell_id"], "params": cell["params"], "horizon_ms": horizon_ms}
    t0 = time.perf_counter()
    try:
        r = gate_pair(cell["ir"], cell["binding"], cell["devices"], cell["joi"],
                      horizon_ms=horizon_ms)
        pr = r.product
        out.update(verdict=r.verdict,
                   claim=getattr(pr, "claim", None),
                   closed=getattr(pr, "closed", None),
                   n_states=getattr(pr, "n_states", None),
                   n_steps=getattr(pr, "n_steps", None),
                   search_seconds=getattr(pr, "seconds", None),
                   symbolic=bool(getattr(pr, "symbolic_certificate", None)),
                   notes=[n[:200] for n in r.notes])
    except MemoryError:
        out.update(verdict="OOM", error="MemoryError")
    except Exception as e:                                    # reported, not hidden
        out.update(verdict="ERROR", error=f"{type(e).__name__}: {e}",
                   traceback=traceback.format_exc()[-1500:])
    out["wall_seconds"] = time.perf_counter() - t0
    out["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
