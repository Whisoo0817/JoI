"""M2.6 feasibility runner: certified-template coverage + engine agreement.

    --prove : discharge the offline template obligations (library build)
    batch   : over periodic cached pairs, try template certification;
              CERTIFIED pairs must agree with the gate verdict (EQUIV) —
              matching latency is the whole online cost (no solver).

Usage:
    python3 -m etc.smt.run_m26 --prove
    python3 -m etc.smt.run_m26 [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

from sim.catalog import load_catalog

from etc.smt.fragment import classify_pair
from etc.smt.templates import certify, PROOFS

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")
_RESULTS = os.path.join(os.path.dirname(__file__), "results")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prove", action="store_true")
    ap.add_argument("--json", default=os.path.join(_RESULTS, "m26.json"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    if args.prove:
        for name, fn in PROOFS.items():
            res = fn()
            ok = all(o["valid"] for o in res.values())
            detail = "  ".join(f"{k}:{'VALID' if o['valid'] else 'INVALID'}"
                               f"({o['ms']:.1f}ms)" for k, o in res.items())
            print(f"{name:<8} {'OK' if ok else '** FAILED **'}  {detail}")
        return 0

    catalog = load_catalog()
    gate = {}
    for fn in ("m2.json",):
        p = os.path.join(_RESULTS, fn)
        if os.path.exists(p):
            gate.update({k: v.get("verdict")
                         for k, v in json.load(open(p, encoding="utf-8")).items()})

    rows = {}
    by_template = Counter()
    agree = Counter()
    lat = []
    n_m2 = 0
    for fn in sorted(os.listdir(_CACHE)):
        if not fn.endswith(".json"):
            continue
        pid = fn[:-5]
        pair = json.load(open(os.path.join(_CACHE, fn), encoding="utf-8"))
        ir, jb = pair.get("ir") or {}, pair.get("joi_block") or {}
        try:
            if classify_pair(ir, jb)["verdict"] != "M2":
                continue
        except Exception:
            continue
        n_m2 += 1
        t0 = time.perf_counter()
        cert = certify(ir, jb, catalog)
        ms = (time.perf_counter() - t0) * 1000
        lat.append(ms)
        gv = gate.get(pid, "-")
        if cert is None:
            rows[pid] = {"cert": None, "gate": gv, "match_ms": ms}
            continue
        by_template[cert.template] += 1
        status = "AGREE" if gv == "EQUIV" else f"CONFLICT(gate={gv})"
        agree[status] += 1
        rows[pid] = {"cert": cert.template, "slots": {k: v for k, v in cert.slots.items()
                                                      if k != "calls"},
                     "assumptions": cert.assumptions, "gate": gv, "match_ms": ms}
        if args.verbose:
            print(f"{pid}: CERT {cert.template} ({ms:.2f}ms) gate={gv} → {status}")

    certified = sum(by_template.values())
    print(f"\nM2 pairs: {n_m2}  certified: {certified} ({certified/max(n_m2,1):.1%})")
    for t, n in by_template.most_common():
        print(f"  {t:<8} {n}")
    print("agreement with gate verdicts:")
    for k, v in agree.most_common():
        print(f"  {k:<20} {v}")
    ls = sorted(lat)
    print(f"matching latency: median {ls[len(ls)//2]:.2f}ms  max {ls[-1]:.2f}ms")

    os.makedirs(_RESULTS, exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1, default=str)
    print(f"detail → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
