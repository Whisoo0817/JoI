"""E2 input histories for the 40 sampled 388 pairs (protocol D1).

~/temp/bin/python make_388_histories.py      (run from histories/)

Seed per pair: every catalog input of the connected devices at a type-valid default at t = 0 (the reference's
smoke-test default history, reference/smoke_388.py `default_events`), horizon = max(10 s, 3 x longest literal
duration of the IR + 10 s), capped at 6 h. Shifts and pulses: the same rules as make_e1_histories.py
(`build_case`), from the dataset IR and binding only — the candidate JoI script is not read.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REF = HERE.parent / "reference"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REF))

import make_e1_histories as mk          # noqa: E402
from common import Catalog, DEFAULT_CATALOG  # noqa: E402
from smoke_388 import default_events     # noqa: E402

CAP_HORIZON = 6 * 3_600_000


def main():
    pairs = json.loads((HERE.parent / "pairs/sample_388_pairs.json").read_text())["pairs"]
    cat = Catalog(str(DEFAULT_CATALOG))
    result, stats = {}, {}
    for p in pairs:
        durs = mk.durations(p["ir"])
        horizon = min(CAP_HORIZON, max(10_000, 3 * (max(durs) if durs else 0) + 10_000))
        horizon = mk.grid(horizon)
        seed = dict(name="default", events=default_events(p["devices"], cat), horizon=horizon)
        hs, st = mk.build_case(p["base_case"], p["ir"], p["binding"], p["t_start_ms"], [seed])
        st["horizon_ms"] = horizon
        result[p["base_case"]], stats[p["base_case"]] = hs, st
    files = [HERE / "make_388_histories.py", HERE / "make_e1_histories.py", REF / "smoke_388.py",
             HERE.parent / "pairs/sample_388_pairs.json"]
    out = {"inputs_sha256": {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
           "grid_ms": mk.GRID, "cap_pulses_per_case": mk.CAP, "seed": mk.SEED, "stats": stats, "histories": result}
    (HERE / "sample_388_histories.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for cid, st in stats.items():
        print(f"{cid}  horizon {st['horizon_ms']:>9d}  seed+shift {st['n_seed_shift']:2d}  pulses {st['n_pulses_kept']:3d}/{st['n_pulses_generated']}")
    print("total", sum(len(v) for v in result.values()))


if __name__ == "__main__":
    main()
