"""E1 depth additions — v2 runner (after the author semantic audit).

python depth/run_depth_v2.py [CASE_ID ...] [--explorer]   -> depth/runs/e1_depth_v2.json

Uses depth_cases_v2 / fixture_v2 / depth_attempts_v2. Replay, comparison (T5) and fault injection (T7) are the
v1 functions in run_depth.py, unchanged. A case may deploy several automations: all of them run side by side on
the same history, their action traces are merged, and the merged trace is compared with the expected trace.
v1 runs (runs/e1_depth.json) are not touched.
"""
from __future__ import annotations

import json
import signal
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
E1 = HERE.parents[1]
ROOT = HERE.parents[4]
for p in (ROOT, E1, HERE):
    sys.path.insert(0, str(p))

import run_depth as R  # noqa: E402
import fixture_v2  # noqa: E402
from depth_cases_v2 import CASES, CASE_BY_ID  # noqa: E402
from depth_attempts_v2 import ATTEMPTS, V1_EVIDENCE  # noqa: E402
from depth_attempts import ATTEMPTS as V1  # noqa: E402
from run_e1 import explorer_self_product, _Timeout, _alarm, EXPLORER_BUDGET_S  # noqa: E402

from timeline_ir.timeline_ir import validate_ir, validate_ir_against_catalog, IRValidationError  # noqa: E402
from timeline_ir.catalog import load_catalog  # noqa: E402
from explorer.runtime.interp import Unsupported  # noqa: E402


def ir_vs_joi(pair):
    """Auxiliary: does the Explorer relate an automation's IR to its lowered JoI block?"""
    from explorer.verification.timed import timed_product
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(EXPLORER_BUDGET_S)
    t0 = time.time()
    try:
        pr = timed_product(pair.ir_runner, pair.code_runner, horizon_ms=None, verification_mode="auto")
        signal.alarm(0)
        return {"verdict": pr.verdict, "claim": getattr(pr, "claim", None), "closed": getattr(pr, "closed", None),
                "seconds": round(time.time() - t0, 2)}
    except _Timeout:
        return {"verdict": "TIMEOUT", "seconds": EXPLORER_BUDGET_S}
    except Unsupported as e:
        signal.alarm(0)
        return {"verdict": "REFUSED", "reason": f"Unsupported: {str(e)[:300]}"}
    except Exception as e:
        signal.alarm(0)
        return {"verdict": "ERROR", "reason": f"{type(e).__name__}: {str(e)[:300]}"}


def run_case(case, entry, path, catalog, do_explorer):
    row = {"id": case["id"], "label": entry["label"], "label_reason": entry["label_reason"],
           "source": entry["source"], "v2_changes": case.get("v2_changes", []), "automations": []}
    lowered = []
    for a in entry["automations"]:
        ir, binding = R.lower(a["ir"])
        info = {"name": a["name"], "ir": ir, "binding": binding}
        try:
            validate_ir(ir)
            validate_ir_against_catalog(ir, catalog)
            info["frontend"] = "accepted"
        except IRValidationError as e:
            info["frontend"] = f"rejected: {str(e)[:300]}"
        try:
            R.compile_pair(ir, binding, case["devices"], path)
            info["runner"] = "compiled"
        except Exception as e:
            info["runner"] = f"refused: {type(e).__name__}: {str(e)[:300]}"
        lowered.append((a, ir, binding))
        row["automations"].append(info)
    if any(i["runner"] != "compiled" for i in row["automations"]):
        return row

    def ir_factory():
        return [R.compile_pair(ir, b, case["devices"], path)[0].ir_runner for _, ir, b in lowered]
    row["histories"], row["match"], row["exact"] = R.run_histories(case, ir_factory)

    if all(a.get("joi") for a, _, _ in lowered):
        def joi_factory():
            return [R.compile_pair(ir, b, case["devices"], path, a["joi"]["script"], a["joi"].get("period", 0))[0].code_runner
                    for a, ir, b in lowered]
        try:
            hist, m, x = R.run_histories(case, joi_factory)
            row["joi"] = {"blocks": [a["joi"]["name"] for a, _, _ in lowered], "histories": hist, "match": m, "exact": x}
        except Exception as e:
            row["joi"] = {"error": f"{type(e).__name__}: {str(e)[:400]}"}

    if case["id"] in V1_EVIDENCE:
        ir1, b1 = R.lower(V1[case["id"]]["ir"])
        sub = dict(case, histories=[h for h in case["histories"] if h["name"] in V1_EVIDENCE[case["id"]]])
        hist, m, x = R.run_histories(sub, lambda: [R.compile_pair(ir1, b1, case["devices"], path)[0].ir_runner])
        row["v1_on_added_histories"] = {"histories": hist, "match": m, "exact": x}

    if do_explorer:
        for info, (a, ir, b) in zip(row["automations"], lowered):
            pair = R.compile_pair(ir, b, case["devices"], path, a["joi"]["script"] if a.get("joi") else "",
                                  a["joi"].get("period", 0) if a.get("joi") else 0)[0]
            info["explorer_self"] = explorer_self_product(pair)
            if a.get("joi"):
                info["explorer_ir_vs_joi"] = ir_vs_joi(pair)
    return row


def main(argv):
    ids = [a for a in argv if not a.startswith("--")] or [c["id"] for c in CASES]
    do_explorer = "--explorer" in argv
    path, sha = fixture_v2.build()
    catalog = load_catalog(path)
    out = HERE / "runs" / "e1_depth_v2.json"
    old = {r["id"]: r for r in json.loads(out.read_text())} if out.exists() else {}
    for cid in ids:
        try:
            row = run_case(CASE_BY_ID[cid], ATTEMPTS[cid], path, catalog, do_explorer)
        except Exception:
            row = {"id": cid, "crash": traceback.format_exc()[-2000:]}
        row["fixture_catalog_sha256"] = sha
        old[cid] = row
        autos = row.get("automations", [])
        print(f"{cid}: {row.get('label','?')} | automations={len(autos)} "
              f"frontend={[a.get('frontend','?')[:20] for a in autos]} runner={[a.get('runner','?')[:20] for a in autos]} | "
              f"IR={row.get('match','-')} (exact {row.get('exact','-')}) | "
              f"JoI={(row.get('joi') or {}).get('match', (row.get('joi') or {}).get('error', '-'))} | "
              f"v1-on-added={(row.get('v1_on_added_histories') or {}).get('match','-')} | "
              f"E={[(a.get('explorer_self') or {}).get('verdict','-') for a in autos]} "
              f"IRvsJoI={[(a.get('explorer_ir_vs_joi') or {}).get('verdict','-') for a in autos]}")
        if row.get("crash"):
            print(row["crash"])
        for src, hs in (("IR", row.get("histories", [])), ("JoI", (row.get("joi") or {}).get("histories", [])),
                        ("v1", (row.get("v1_on_added_histories") or {}).get("histories", []))):
            for h in hs:
                if not h.get("match"):
                    print(f"    ✗ {src} {h['name']}: {h.get('error') or {'missing': h['missing'], 'extra': h['extra']}}")
                if h.get("faults"):
                    print(f"      {src} faults: {h['faults']}")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps([old[c["id"]] for c in CASES if c["id"] in old], ensure_ascii=False, indent=1, default=str))
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
