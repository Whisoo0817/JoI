"""E1 Stage A runner: fills columns A-frontend, C (execution match), D (reference runner), E (Explorer self-product).

python run_e1.py [CASE_ID ...]      -> runs/e1_stageA.json + table on stdout

Column B (semantic audit) and G (JoI feasibility) are human columns and are NOT filled here.
Column E is informational only: it runs the Explorer on the IR against itself and reports whether the
verification path completes; it is not the E1 ground truth.
"""
from __future__ import annotations

import json
import signal
import sys
import time
import traceback
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from cases import CASES, CASE_BY_ID, TOLERANCE_MS  # noqa: E402
from irs import IRS  # noqa: E402

from timeline_ir.timeline_ir import validate_ir, validate_ir_against_catalog, IRValidationError  # noqa: E402
from timeline_ir.catalog import load_catalog  # noqa: E402
from explorer.runtime.interp import Unsupported  # noqa: E402
from explorer.verification.gate import prepare_pair  # noqa: E402

STEP_MS = 100
EXPLORER_BUDGET_S = 120


def _lower_first(s):
    return s[:1].lower() + s[1:]


def _num(x):
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float, Fraction)):
        return float(x)
    return x


def history_inputs(events):
    """'Device.Attr' -> runner world key. The runner spells attributes in canonical lowercase
    (ir_step.default_to_key / interp.canonical_key), e.g. CarbonDioxide -> carbondioxide."""
    out = {}
    for t, upd in events:
        out.setdefault(t, {}).update({f"{k.split('.')[0]}.{k.split('.')[1].lower()}": v for k, v in upd.items()})
    return out


def replay(runner, events, t_start, horizon_ms, step_ms=STEP_MS):
    """Concrete replay on the reference IR runner from absolute t_start. Returns relative-time trace."""
    changes = history_inputs(events)
    for t in changes:
        if t % step_ms:
            raise ValueError(f"input change at {t} off the {step_ms} ms grid")
    values, gv, inputs, trace = {}, {}, {}, []
    for rel in range(0, horizon_ms + 1, step_ms):
        if rel in changes:
            inputs.update(changes[rel])
        t = t_start + rel
        res = runner.step(values, gv, dict(inputs), t, first_tick=(rel == 0))
        values, gv = res.vars, res.gv
        for a in res.actions:
            targets = tuple(a.target) if isinstance(a.target, (list, tuple)) else (a.target,)
            trace.append((rel, str(a.service).lower(), str(a.method).lower(), tuple(_num(x) for x in a.args), targets))
    return trace


def expected_trace(hist):
    out = []
    for t, sm, args, dev in hist["expected"]:
        svc, meth = sm.split(".")
        out.append((t, svc.lower(), meth.lower(), tuple(_num(a) for a in args), (dev,)))
    return out


def compare(expected, actual):
    sig = lambda a: a[1:]
    exact = expected == actual
    tolerant = (len(expected) == len(actual)
                and all(sig(e) == sig(a) and abs(e[0] - a[0]) <= TOLERANCE_MS for e, a in zip(expected, actual)))
    first_diff = None
    if not tolerant:
        for i in range(max(len(expected), len(actual))):
            e = expected[i] if i < len(expected) else None
            a = actual[i] if i < len(actual) else None
            if e is None or a is None or sig(e) != sig(a) or abs(e[0] - a[0]) > TOLERANCE_MS:
                first_diff = {"index": i, "expected": e, "actual": a}
                break
    return {"exact": exact, "match": tolerant, "first_diff": first_diff}


def erase_cron(ir):
    tl = [dict(s) for s in ir["timeline"]]
    if tl and tl[0].get("anchor") == "cron":
        tl[0] = {"op": "start_at", "anchor": "now"}
        return {**ir, "timeline": tl}, True
    return ir, False


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


def explorer_self_product(pair):
    """Column E (informational): can the Explorer complete on IR x IR?"""
    from explorer.verification.timed import timed_product
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(EXPLORER_BUDGET_S)
    t0 = time.time()
    try:
        pr = timed_product(pair.ir_runner, pair.ir_runner, horizon_ms=None, verification_mode="auto")
        signal.alarm(0)
        return {"verdict": pr.verdict, "claim": getattr(pr, "claim", None), "closed": getattr(pr, "closed", None),
                "notes": [str(n)[:200] for n in (getattr(pr, "notes", None) or [])][:6], "seconds": round(time.time() - t0, 2)}
    except _Timeout:
        return {"verdict": "TIMEOUT", "seconds": EXPLORER_BUDGET_S}
    except Unsupported as e:
        signal.alarm(0)
        return {"verdict": "REFUSED", "reason": f"Unsupported: {e}"}
    except Exception as e:  # informational column: never abort the run
        signal.alarm(0)
        return {"verdict": "ERROR", "reason": f"{type(e).__name__}: {e}"}


def run_case(case, entry, catalog, do_explorer=True):
    ir = entry["ir"]
    row = {"id": case["id"], "lang_claim": entry["lang"], "elements": case["elements"], "boundary_intent": case["boundary_intent"]}

    # A-frontend
    try:
        validate_ir(ir)
        validate_ir_against_catalog(ir, catalog)
        row["A_frontend"] = "accepted"
    except IRValidationError as e:
        row["A_frontend"] = f"rejected: {str(e)[:300]}"

    # D: reference runner compile (cron anchor erased if present)
    ir_exec, erased = erase_cron(ir)
    row["cron_erased_for_execution"] = erased
    jb = {"cron": "", "period": 0, "script": ""}
    try:
        pair = prepare_pair(ir_exec, case["binding"], case["devices"], jb)
        row["D_runner"] = "compiled" + (" (cron anchor erased; one firing window executed)" if erased else "")
    except Exception as e:
        row["D_runner"] = f"refused: {type(e).__name__}: {str(e)[:300]}"
        row["C_histories"] = []
        row["E_explorer"] = {"verdict": "n/a (runner refused)"}
        return row

    # C: execution match per history
    hist_rows, n_match, n_exact = [], 0, 0
    for h in case["histories"]:
        exp = expected_trace(h)
        try:
            act = replay(pair.ir_runner, h["events"], case["t_start_ms"], h["horizon"])
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
    row["C_match"] = f"{n_match}/{len(case['histories'])}"
    row["C_exact"] = f"{n_exact}/{len(case['histories'])}"

    # E: Explorer self-product (informational)
    row["E_explorer"] = explorer_self_product(pair) if do_explorer else {"verdict": "skipped"}
    return row


def main(argv):
    ids = [a for a in argv if not a.startswith("--")] or [c["id"] for c in CASES]
    do_explorer = "--no-explorer" not in argv
    catalog = load_catalog()
    rows = []
    for cid in ids:
        case, entry = CASE_BY_ID[cid], IRS[cid]
        try:
            row = run_case(case, entry, catalog, do_explorer)
        except Exception:
            row = {"id": cid, "crash": traceback.format_exc()[-1500:]}
        rows.append(row)
        print(f"{cid}: A_frontend={row.get('A_frontend','?')[:60]} | D={row.get('D_runner','?')[:70]} | "
              f"C={row.get('C_match','-')} (exact {row.get('C_exact','-')}) | E={row.get('E_explorer',{}).get('verdict','-')}")
        for h in row.get("C_histories", []):
            if not h.get("match"):
                print(f"    ✗ {h['name']}: {h.get('error') or h.get('first_diff')}")
    out = HERE / "runs" / "e1_stageA.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
