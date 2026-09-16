"""E1 boundary probes runner.

python run_probes.py [PROBE_ID ...]     -> runs/e1_probes.json

Probes are reported separately from the Stage A corpus and never enter its denominator.
For P3 the refused attempt A is compiled too, so the refusal message is recorded rather than quoted.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from probes import PROBES, PROBE_BY_ID  # noqa: E402
from probe_attempts import ATTEMPTS  # noqa: E402
from run_e1 import replay, expected_trace, compare, erase_cron, explorer_self_product  # noqa: E402

from timeline_ir.timeline_ir import validate_ir, validate_ir_against_catalog, IRValidationError  # noqa: E402
from timeline_ir.catalog import load_catalog  # noqa: E402
from explorer.verification.gate import prepare_pair  # noqa: E402


def compile_or_message(ir, probe, catalog):
    """Return (pair, message). pair is None when the reference runner refuses."""
    jb = {"cron": "", "period": 0, "script": ""}
    ir_exec, erased = erase_cron(ir)
    try:
        return prepare_pair(ir_exec, probe["binding"], probe["devices"], jb), (
            "compiled" + (" (cron anchor erased; one firing window executed)" if erased else ""))
    except Exception as e:
        return None, f"refused: {type(e).__name__}: {str(e)[:300]}"


def run_probe(probe, entry, catalog, do_explorer=True):
    row = {"id": probe["id"], "probe_of": probe["probe_of"], "lang_claim": entry["lang"],
           "verdict_claim": entry.get("verdict_claim", ""), "elements": probe["elements"]}

    try:
        validate_ir(entry["ir"])
        validate_ir_against_catalog(entry["ir"], catalog)
        row["A_frontend"] = "accepted"
    except IRValidationError as e:
        row["A_frontend"] = f"rejected: {str(e)[:300]}"

    # a refused attempt is evidence, so compile it and keep the message
    if entry.get("attempt_a") is not None:
        _, msg = compile_or_message(entry["attempt_a"], probe, catalog)
        row["attempt_a_runner"] = msg

    pair, msg = compile_or_message(entry["ir"], probe, catalog)
    row["D_runner"] = msg
    if pair is None:
        row["C_histories"], row["E_explorer"] = [], {"verdict": "n/a (runner refused)"}
        return row

    hist_rows, n_match, n_exact = [], 0, 0
    for h in probe["histories"]:
        exp = expected_trace(h)
        try:
            act = replay(pair.ir_runner, h["events"], probe["t_start_ms"], h["horizon"])
        except Exception as e:
            hist_rows.append({"name": h["name"], "kind": h["kind"], "error": f"{type(e).__name__}: {e}", "match": False})
            continue
        cmp = compare(exp, act)
        n_match += cmp["match"]
        n_exact += cmp["exact"]
        hist_rows.append({"name": h["name"], "kind": h["kind"], **cmp,
                          "n_expected": len(exp), "n_actual": len(act),
                          "expected": exp if len(exp) <= 12 else exp[:6] + ["..."] + exp[-3:],
                          "actual": act if len(act) <= 12 else act[:6] + ["..."] + act[-3:]})
    row["C_histories"] = hist_rows
    row["C_match"] = f"{n_match}/{len(probe['histories'])}"
    row["C_exact"] = f"{n_exact}/{len(probe['histories'])}"
    row["E_explorer"] = explorer_self_product(pair) if do_explorer else {"verdict": "skipped"}
    return row


def main(argv):
    ids = [a for a in argv if not a.startswith("--")] or [p["id"] for p in PROBES]
    do_explorer = "--no-explorer" not in argv
    catalog = load_catalog()
    rows = []
    for pid in ids:
        probe, entry = PROBE_BY_ID[pid], ATTEMPTS[pid]
        try:
            row = run_probe(probe, entry, catalog, do_explorer)
        except Exception:
            row = {"id": pid, "crash": traceback.format_exc()[-1500:]}
        rows.append(row)
        print(f"{pid} ({row.get('probe_of','?')}): A_frontend={row.get('A_frontend','?')[:40]} | "
              f"D={row.get('D_runner','?')[:60]} | C={row.get('C_match','-')} (exact {row.get('C_exact','-')}) | "
              f"E={row.get('E_explorer',{}).get('verdict','-')}")
        if row.get("attempt_a_runner"):
            print(f"    attempt A: {row['attempt_a_runner'][:120]}")
        for h in row.get("C_histories", []):
            if not h.get("match"):
                print(f"    ✗ {h['name']}: {h.get('error') or h.get('first_diff')}")
    out = HERE / "runs" / "e1_probes.json"
    out.parent.mkdir(exist_ok=True)
    if len(ids) < len(PROBES) and out.exists():
        old = {r["id"]: r for r in json.loads(out.read_text())}
        old.update({r["id"]: r for r in rows})
        rows = [old[p["id"]] for p in PROBES if p["id"] in old]
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
