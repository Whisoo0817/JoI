"""E2 run: independent reference vs Explorer on the frozen pairs and histories.

~/temp/bin/python run_e2.py [--workers N] [--only PAIR_ID_PREFIX] [--out runs/e2_run.jsonl]

Per pair (one worker process each; results appended to the JSONL, finished pair_ids are skipped on restart):
- reference: run the IR (cached per base case + automation) and the JoI block on every history of the base case
  (histories/*.json); per history `equal` / `diverge` / `unsupported` / `error`.
  Pair outcome: REF-DIVERGE if any history with both sides ok differs; otherwise REF-EQUIV-CHECKED if every history
  ran ok on both sides; otherwise REF-UNSUPPORTED / REF-ERROR (the side and reason are kept).
- Explorer: the steps of explorer.verification.gate.gate_pair — prepare_pair, timed_product(horizon_ms=None,
  verification_mode="auto"), replay_divergence, fold_verdict — with t0_ms = 2_419_200_000 + t_start_ms so that
  both tools use the same start time (gate_pair itself has no start-time argument). Budget 120 s per pair
  (TIMEOUT). Exceptions are folded as gate_pair folds them (REFUSED).
- Explorer DIVERGE: the first confirmed witness is converted to reference events and run on the reference.
- agreement: see PROTOCOL_DRAFT §4.
Depth IRs use explicit device atoms; for the Explorer they are lowered with the E1 tool `run_depth.lower`.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REF = Path(os.environ.get("E2_REF_DIR", HERE / "reference"))
DEPTH = ROOT / "PerCom/6_Evaluation/E1_adequacy/breadth/depth"
E1 = ROOT / "PerCom/6_Evaluation/E1_adequacy"
T0_EXPLORER = 2_419_200_000
BUDGET_S = 120


def load_inputs():
    pairs = json.loads((HERE / "pairs/e1_pairs.json").read_text())["pairs"]
    pairs += json.loads((HERE / "pairs/sample_388_pairs.json").read_text())["pairs"]
    hist = json.loads((HERE / "histories/e1_histories.json").read_text())["histories"]
    hist.update(json.loads((HERE / "histories/sample_388_histories.json").read_text())["histories"])
    return pairs, hist


# ── reference ────────────────────────────────────────────────────────────────

def reference_side(pair, histories):
    sys.path.insert(0, str(REF))
    from run import compare, run_ir, run_joi
    cat = str(ROOT / pair["catalog"])
    per, ir_bad, joi_bad, first_div = [], None, None, None
    for h in histories:
        ev = [(int(t), u) for t, u in h["events"]]
        a = run_ir(pair["ir"], pair["binding"], pair["devices"], ev, h["horizon"], catalog_path=cat,
                   t_start_ms=pair["t_start_ms"], cron=pair.get("ir_cron", ""))
        b = run_joi(pair["joi"], pair["devices"], ev, h["horizon"], catalog_path=cat, t_start_ms=pair["t_start_ms"])
        if a["status"] != "ok":
            per.append((h["name"], a["status"] + "-ir"))
            ir_bad = ir_bad or (a["status"], a["detail"][:300])
            continue
        if b["status"] != "ok":
            per.append((h["name"], b["status"] + "-joi"))
            joi_bad = joi_bad or (b["status"], b["detail"][:300])
            continue
        eq, diff = compare(a["trace"], b["trace"])
        per.append((h["name"], "equal" if eq else "diverge"))
        if not eq and first_div is None:
            first_div = {"history": h["name"], "difference": str(diff)[:600],
                         "ir_actions": [list(map(str, x)) for x in a["raw_actions"][:20]],
                         "joi_actions": [list(map(str, x)) for x in b["raw_actions"][:20]]}
    counts = {}
    for _, s in per:
        counts[s] = counts.get(s, 0) + 1
    if first_div:
        outcome = "REF-DIVERGE"
    elif counts.get("equal", 0) == len(histories):
        outcome = "REF-EQUIV-CHECKED"
    elif ir_bad:
        outcome = "REF-" + ir_bad[0].upper() + "-IR"
    else:
        outcome = "REF-" + joi_bad[0].upper() + "-JOI"
    return {"outcome": outcome, "counts": counts, "n_histories": len(histories), "first_divergence": first_div,
            "ir_problem": ir_bad, "joi_problem": joi_bad}


# ── Explorer ─────────────────────────────────────────────────────────────────

class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


def explorer_side(pair):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(E1))
    sys.path.insert(0, str(DEPTH))
    from explorer.runtime.interp import Unsupported
    from explorer.verification.gate import fold_verdict, prepare_pair
    from explorer.verification.product import replay_divergence
    from explorer.verification.timed import timed_product
    ir, binding = pair["ir"], pair["binding"]
    if binding is None:
        from run_depth import lower
        ir, binding = lower(ir)
    catalog = True if pair["catalog"].endswith("service_list_ver2.0.7.json") else str(ROOT / pair["catalog"])
    t0 = T0_EXPLORER + int(pair["t_start_ms"])
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(BUDGET_S)
    started = time.time()
    try:
        prepared = prepare_pair(ir, binding, pair["devices"], pair["joi"], service_catalog=catalog)
        pr = timed_product(prepared.ir_runner, prepared.code_runner, horizon_ms=None, t0_ms=t0,
                           verification_mode="auto")
        replays = [replay_divergence(prepared.ir_runner, prepared.code_runner, dv) for dv in pr.divergences]
        gate = fold_verdict(pr, replays, prepared.notes)
        signal.alarm(0)
    except _Timeout:
        return {"verdict": "TIMEOUT", "seconds": BUDGET_S}
    except (Unsupported, ValueError, KeyError, AttributeError) as e:
        signal.alarm(0)
        return {"verdict": "REFUSED", "stage": "preparation/exploration", "reason": f"{type(e).__name__}: {str(e)[:300]}",
                "seconds": round(time.time() - started, 2)}
    except (TypeError, ArithmeticError) as e:
        signal.alarm(0)
        return {"verdict": "REFUSED", "stage": "execution", "reason": f"{type(e).__name__}: {str(e)[:300]}",
                "seconds": round(time.time() - started, 2)}
    except Exception as e:
        signal.alarm(0)
        return {"verdict": "ERROR", "reason": f"{type(e).__name__}: {str(e)[:300]}",
                "trace": traceback.format_exc(limit=4)[-800:], "seconds": round(time.time() - started, 2)}
    out = {"verdict": gate.verdict, "claim": pr.claim, "closed": pr.closed, "n_states": pr.n_states,
           "seconds": round(time.time() - started, 2), "notes": [str(n)[:200] for n in gate.notes][-4:]}
    if gate.verdict == "DIVERGE":
        for dv, rp in zip(pr.divergences, replays):
            if rp.confirmed:
                out["witness"] = {"path": [[{k: (v if isinstance(v, (bool, int, float, str)) or v is None else str(v))
                                              for k, v in (inp or {}).items()}, int(dw)] for inp, dw in dv.path]
                                  + [[{k: (v if isinstance(v, (bool, int, float, str)) or v is None else str(v))
                                       for k, v in (dv.input_ or {}).items()}, int(dv.dwell_ms)]],
                                  "t0_ms": dv.t0_ms if dv.t0_ms is not None else t0,
                                  "actions_ir": str(rp.actions_a)[:600], "actions_joi": str(rp.actions_b)[:600]}
                break
    return out


def witness_events(witness, devices, catalog_path):
    """Explorer witness path [(inputs, dwell_ms), ...] -> reference events. Runner keys are `device.member` with a
    lowercase member; the member is mapped back to the catalog spelling of the device's categories."""
    cat = json.loads(Path(catalog_path).read_text())["skills"]
    members = {}
    for s in cat:
        for kind in ("values", "functions"):
            for m in s.get(kind, []):
                members.setdefault(s["id"], {})[m["id"].lower()] = m["id"]
    ev, t = [], 0
    last = {}
    for inputs, dwell in witness["path"]:
        t += int(dwell)          # dwell = time elapsed since the previous entry, before these inputs hold
        upd = {}
        for key, val in inputs.items():
            m = re.match(r"^([^.]+)\.([A-Za-z_]\w*)(\(.*\))?$", key)
            if not m or m.group(1) not in devices:
                if key.startswith("@gv:") or key.startswith("clock."):
                    continue
                raise ValueError(f"unconvertible witness key {key!r}")
            did, low, args = m.groups()
            name = None
            for c in devices[did].get("category", []):
                name = name or members.get(c, {}).get(low.lower())
            if not name:
                raise ValueError(f"unknown member in witness key {key!r}")
            rk = f"{did}.{name}{args or ''}"
            if last.get(rk, object()) != val:
                upd[rk] = val
                last[rk] = val
        if upd or t == 0:
            ev.append((t, upd))
    return ev, t


def witness_on_reference(pair, witness):
    sys.path.insert(0, str(REF))
    from run import compare, run_ir, run_joi
    cat = str(ROOT / pair["catalog"])
    try:
        ev, end = witness_events(witness, pair["devices"], cat)
    except ValueError as e:
        return {"status": "unconvertible", "detail": str(e)}
    horizon = end + 1000
    a = run_ir(pair["ir"], pair["binding"], pair["devices"], ev, horizon, catalog_path=cat,
               t_start_ms=pair["t_start_ms"], cron=pair.get("ir_cron", ""))
    b = run_joi(pair["joi"], pair["devices"], ev, horizon, catalog_path=cat, t_start_ms=pair["t_start_ms"])
    if a["status"] != "ok" or b["status"] != "ok":
        return {"status": f"ir:{a['status']} joi:{b['status']}", "detail": (a["detail"] or b["detail"])[:300],
                "events": ev[:30]}
    eq, diff = compare(a["trace"], b["trace"])
    return {"status": "equal" if eq else "diverge", "difference": str(diff)[:600], "events": ev[:30]}


def agreement(exp, ref):
    e, r = exp["verdict"], ref["outcome"]
    if e == "EQUIV" and r == "REF-DIVERGE":
        return "FALSE-EQUIV-CANDIDATE"
    if e == "DIVERGE":
        w = exp.get("witness_on_reference", {}).get("status")
        if w == "diverge":
            return "AGREE-DIVERGE" if r == "REF-DIVERGE" else "EXPLORER-DIVERGE-CONFIRMED-BY-REF-ON-WITNESS"
        return "FALSE-DIVERGE-CANDIDATE" if r == "REF-EQUIV-CHECKED" else f"DIVERGE-WITNESS-{w}"
    if e in ("EQUIV", "EQUIV-BOUNDED") and r == "REF-EQUIV-CHECKED":
        return "AGREE-EQUIV-ON-CHECKED"
    if e in ("REFUSED", "TIMEOUT", "ERROR"):
        return f"EXPLORER-{e}"
    return f"REF-{r.split('-', 1)[1]}"


def run_pair(pair, histories):
    started = time.time()
    row = {"pair_id": pair["pair_id"], "kind": pair["kind"], "family": pair.get("family"),
           "base_case": pair["base_case"], "automation": pair.get("automation")}
    try:
        row["reference"] = reference_side(pair, histories)
    except Exception as e:
        row["reference"] = {"outcome": "REF-HARNESS-ERROR", "reason": f"{type(e).__name__}: {e}",
                            "trace": traceback.format_exc(limit=4)[-800:]}
    row["explorer"] = explorer_side(pair)
    if row["explorer"].get("witness"):
        row["explorer"]["witness_on_reference"] = witness_on_reference(pair, row["explorer"]["witness"])
    row["agreement"] = agreement(row["explorer"], row["reference"])
    row["wall_seconds"] = round(time.time() - started, 2)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=str(HERE / "runs/e2_run.jsonl"))
    args = ap.parse_args()
    pairs, hist = load_inputs()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {json.loads(l)["pair_id"] for l in out.read_text().splitlines() if l.strip()}
    todo = [p for p in pairs if p["pair_id"].startswith(args.only) and p["pair_id"] not in done]
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD:explorer"], capture_output=True, text=True).stdout.strip()
    meta = out.with_suffix(".meta.json")
    if not meta.exists():
        meta.write_text(json.dumps({"repo_head": head, "explorer_tree": tree, "budget_s": BUDGET_S,
                                    "t0_explorer": T0_EXPLORER, "workers": args.workers,
                                    "started": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1))
    print(f"{len(todo)} pairs to run ({len(done)} done), workers={args.workers}", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool, out.open("a") as f:
        futs = {pool.submit(run_pair, p, hist[p["base_case"]]): p["pair_id"] for p in todo}
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception as e:
                row = {"pair_id": futs[fut], "agreement": "HARNESS-ERROR", "reason": f"{type(e).__name__}: {e}"}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(row["pair_id"], row.get("agreement"), row.get("explorer", {}).get("verdict"),
                  row.get("reference", {}).get("outcome"), row.get("wall_seconds"), flush=True)


if __name__ == "__main__":
    main()
