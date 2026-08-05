"""Stage ⑥ — behavioral certification of adapted artifacts (miter wiring).

The contingency compiler (stage ⑦) produces redeploy artifacts through
text-level machinery: slicing + splice + static contract checks. Those layers
guarantee structure; behavior of the SURVIVING channels is certified here, by
the JoI↔JoI relational miter (smt.relational), per output channel:

    EQUIV     proved: no input inside the window makes this channel's
              emissions differ from the original's        (certificate)
    VACUOUS   proved, but no input can fire the channel inside the capped
              window — an honest empty certificate, not evidence
    DIVERGE   witness input found — expected for degraded channels (lost
              call sites / changed denominators), a defect for intact ones
    TIMEOUT   undecided within budget — offline escalation candidate

Import note: z3/smt loads lazily so the fast runtime path (table lookup)
never pays for it.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


def certify_artifact(base_src: str, artifact_src: str, period_ms: int,
                     inv, catalog: Optional[dict] = None,
                     timeout_ms: int = 300_000, w_cap: int = 32) -> dict:
    """→ {"verdict", "channels": {label: EQUIV|VACUOUS|DIVERGE|TIMEOUT},
         "degraded": [labels], "proofs": n, "elapsed_s"}

    `degraded` = channels that lost emission call sites in the artifact —
    their divergence is the intended feature loss, not a defect. The overall
    verdict is `certified` when every intact channel is EQUIV (vacuous ones
    labeled but not counted as proofs), `degraded-visible` when only
    degraded/denominator channels diverge, `defect` when an intact channel
    diverges, `undecided` when obligations timed out.
    """
    from sim.catalog import load_catalog
    from smt.relational import check_relational_v2, emitted_sigs_v2
    from smt.run_certify import emit_sites

    catalog = catalog or load_catalog()
    keep = emitted_sigs_v2(artifact_src, inv, catalog)
    sites_old = emit_sites(base_src, inv, catalog)
    sites_new = emit_sites(artifact_src, inv, catalog)
    degraded = sorted(ch for ch in keep
                      if sites_new.get(ch, 0) < sites_old.get(ch, 0))

    r = check_relational_v2(base_src, artifact_src, period_ms, inv, catalog,
                            preserve=keep, timeout_ms=timeout_ms,
                            split=True, w_cap=w_cap)
    if r["verdict"] == "UNSUPPORTED":
        return {"verdict": "unsupported", "reason": r.get("reason"),
                "channels": {}, "degraded": degraded, "proofs": 0,
                "elapsed_s": r.get("elapsed_s", 0.0)}

    reach = (r.get("meta") or {}).get("reachable") or {}
    channels: dict = {}
    proofs = 0
    defect = undecided = visible = False
    for lbl, v in (r.get("obligations") or {}).items():
        ch = lbl.split(":", 1)[1]
        if v == "EQUIV":
            if reach.get(ch) is False:
                channels[lbl] = "VACUOUS"
            else:
                channels[lbl] = "EQUIV"
                proofs += 1
        elif v == "DIVERGE":
            channels[lbl] = "DIVERGE"
            if ch in degraded:
                visible = True
            else:
                defect = True
        else:
            channels[lbl] = v
            undecided = True

    verdict = ("defect" if defect else
               "undecided" if undecided else
               "degraded-visible" if visible else "certified")
    return {"verdict": verdict, "channels": channels, "degraded": degraded,
            "proofs": proofs, "elapsed_s": round(r.get("elapsed_s", 0.0), 2)}


def certify_table_rows(template_id: str, inv=None,
                       timeout_ms: int = 300_000, w_cap: int = 32) -> dict:
    """Certify every redeploy row of one contingency table (offline path).
    Returns {device_id: certificate}; also stamps each certificate into the
    saved table JSON so the runtime deploys artifacts WITH their proofs."""
    import json

    from adapt.inventory import base_office
    from adapt.template import load_skeleton, load_template

    inv = inv or base_office()
    t = load_template(template_id)
    raw = json.load(open(os.path.join(_HERE, "templates", f"{template_id}.json"),
                         encoding="utf-8"))
    period = int((raw.get("validity") or {}).get("period_ms", 1000))
    base_src = load_skeleton(t)

    path = os.path.join(_HERE, "contingency_tables", f"{template_id}.json")
    table = json.load(open(path, encoding="utf-8"))
    out: dict = {}
    for dev_id, row in table["rows"].items():
        if row.get("action") != "redeploy":
            continue
        cert = certify_artifact(base_src, row["artifact"], period, inv,
                                timeout_ms=timeout_ms, w_cap=w_cap)
        row["certificate"] = cert
        out[dev_id] = cert
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=1)
    return out


def main(argv=None) -> int:
    import argparse
    from adapt.template import list_templates

    ap = argparse.ArgumentParser(description="Stage ⑥: certify redeploy artifacts")
    ap.add_argument("--template", help="one template (default: all)")
    ap.add_argument("--timeout-ms", type=int, default=300_000)
    args = ap.parse_args(argv)

    for tid in ([args.template] if args.template else list_templates()):
        certs = certify_table_rows(tid, timeout_ms=args.timeout_ms)
        for dev_id, c in certs.items():
            print(f"{tid}/{dev_id}: {c['verdict']} "
                  f"(proofs={c['proofs']}, degraded={c['degraded']}, "
                  f"{c['elapsed_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
