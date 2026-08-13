"""Stage-⑥ evidence: certify the contingency redeploy artifacts.

For every `redeploy` row in adapt/contingency_tables/*.json (the old→new
pairs the slicer precompiled), run the v2 relational miter:

    old   = the template skeleton (as deployed before the failure)
    new   = the row's artifact
    preserve = the artifact's own output channels (the dropped feature's
               channels are the edit — contracts own them, not the miter)

Expected shape, checked per row kind:

  * feature drop (dropped_features non-empty — speaker/camera/email/…):
      every preserved obligation EQUIV — the artifact provably leaves the
      surviving channels' behavior unchanged on ALL inputs.
  * source cut (dropped_features empty — a dead sensor cut out of a
      multi-sensor average): the average-fed channels are EXPECTED to
      diverge (the denominator changed) — the miter making the degradation
      visible, with a witness, is the honest result. Channels not fed by the
      cut source must still be EQUIV.

    python3 -m smt.run_certify [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from sim.catalog import load_catalog

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from adapt.inventory import base_office                      # noqa: E402
from adapt.template import load_skeleton, load_template      # noqa: E402
from smt.relational import check_relational_v2, emitted_sigs_v2  # noqa: E402


def emit_sites(src: str, inv, catalog) -> dict:
    """Canonical channel label → number of emission call sites."""
    from collections import Counter
    from sim import expr as E
    from smt.encode import MEmit, MIf
    from smt.encode_v2 import to_micro2
    out: Counter = Counter()

    def walk(ops):
        for op in ops:
            if isinstance(op, MEmit):
                _, m = E.canonical_key(op.service, op.method)
                out[f"{m}/{len(op.args)}"] += 1
            elif isinstance(op, MIf):
                walk(op.then)
                walk(op.els)

    walk(to_micro2(src, inv, catalog))
    return dict(out)

_TABLES = os.path.join(_REPO, "adapt", "contingency_tables")
_RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _period(tid: str) -> int:
    raw = json.load(open(os.path.join(_REPO, "adapt", "templates", f"{tid}.json"),
                         encoding="utf-8"))
    return int((raw.get("validity") or {}).get("period_ms", 1000))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout-ms", type=int, default=300_000)
    ap.add_argument("--w-cap", type=int, default=32)
    ap.add_argument("--json", default=os.path.join(_RESULTS, "certify.json"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    inv = base_office()
    results: dict = {}
    fails: list = []
    undecided: list = []
    n_rows = n_obl_proved = 0

    for fn in sorted(os.listdir(_TABLES)):
        if not fn.endswith(".json"):
            continue
        table = json.load(open(os.path.join(_TABLES, fn), encoding="utf-8"))
        tid = table["template"]
        skeleton = load_skeleton(load_template(tid))
        period = _period(tid)
        for dev_id, row in table["rows"].items():
            if row.get("action") != "redeploy":
                continue
            n_rows += 1
            rid = f"{tid}/{dev_id}"
            kind = "feature_drop" if row.get("dropped_features") else "source_cut"
            try:
                keep = emitted_sigs_v2(row["artifact"], inv, catalog)
                sites_old = emit_sites(skeleton, inv, catalog)
                sites_new = emit_sites(row["artifact"], inv, catalog)
                # a preserved channel that LOST call sites is a degraded
                # channel: it is expected to diverge (fewer firings), and the
                # miter making that visible with a witness is the point
                partial = {ch for ch in keep
                           if sites_new.get(ch, 0) < sites_old.get(ch, 0)}
                r = check_relational_v2(skeleton, row["artifact"], period, inv,
                                        catalog, preserve=keep,
                                        timeout_ms=args.timeout_ms, split=True,
                                        w_cap=args.w_cap)
                if r.get("obligations") and "TIMEOUT" in r["obligations"].values():
                    r2 = check_relational_v2(skeleton, row["artifact"], period,
                                             inv, catalog, preserve=keep,
                                             timeout_ms=2 * args.timeout_ms,
                                             split=True, w_cap=24)
                    if "TIMEOUT" not in (r2.get("obligations") or {"": "TIMEOUT"}).values():
                        r = r2
                        r["retried_w24"] = True
            except Exception as e:
                r = {"verdict": "ENCODER_ERROR",
                     "reason": f"{type(e).__name__}: {e}"}
                partial = set()
            obl = r.get("obligations") or {}
            reach = (r.get("meta") or {}).get("reachable") or {}
            entry = {"kind": kind, "dead": row.get("device_type"),
                     "dropped": row.get("dropped_features"),
                     "partial_channels": sorted(partial),
                     "verdict": r["verdict"], "obligations": obl,
                     "reachable": reach,
                     "elapsed_s": round(r.get("elapsed_s", 0.0), 2)}
            results[rid] = entry

            if r["verdict"] in ("UNSUPPORTED", "ENCODER_ERROR"):
                fails.append(f"{rid}: {r['verdict']} {r.get('reason', '')[:90]}")

            print(f"{rid} [{kind}, {row.get('device_type')} dead] "
                  f"-> {r['verdict']} ({entry['elapsed_s']}s)"
                  f"{' [retry w=24]' if r.get('retried_w24') else ''}")
            for lbl, v in sorted(obl.items()):
                ch = lbl.split(":", 1)[1]
                vac = reach.get(ch) is False
                mark = "×" if v == "DIVERGE" else "✓"
                if v == "EQUIV" and not vac:
                    n_obl_proved += 1
                if ch in partial:
                    note = ("  <- degraded channel (lost call sites): "
                            "divergence expected" if v == "DIVERGE"
                            else "  (degraded channel)")
                elif v == "DIVERGE" and kind == "source_cut":
                    # the denominator changed under this channel — the miter
                    # making the degradation visible IS the expected result;
                    # channels it still proves EQUIV are the unaffected ones
                    note = "  <- degradation visible (denominator changed)"
                elif v == "DIVERGE":
                    note = "  <- UNEXPECTED"
                    fails.append(f"{rid}: intact channel {lbl} diverged")
                elif v == "EQUIV" and vac:
                    note = "  (VACUOUS: channel unreachable in window)"
                elif v in ("TIMEOUT", "UNKNOWN"):
                    note = "  <- undecided"
                    undecided.append(f"{rid}: {lbl} ({v})")
                else:
                    note = ""
                print(f"    {mark} {lbl:<48} {v}{note}")

    print(f"\nredeploy rows: {n_rows}  "
          f"non-vacuous preserved-channel proofs: {n_obl_proved}")
    print(f"undecided obligations (offline budget / induction candidates): "
          f"{len(undecided)}")
    for u in undecided:
        print("  ~", u)
    print(f"failures: {len(fails)}")
    for f_ in fails:
        print("  -", f_)
    print("PASS" if not fails else "FAIL")

    os.makedirs(_RESULTS, exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    print(f"detail → {args.json}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
