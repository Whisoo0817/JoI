"""E2 rerun under the binding decision (BINDING_DECISION_2026-09-14.md, whisoo).

~/temp/bin/python run_binding_v1.py [--workers N]

Both tools use the decision (E2_BINDING_DECISION=1): the Explorer after the binding change (gate.selector_binding
on, observation B2), the reference after its B1/B2 update. Pairs, histories, budget and start times are the frozen
ones. Per pair:
- run_e2.run_pair on the frozen histories (reference, Explorer, witness replay, agreement);
- when the frozen-history outcome is REF-EQUIV-CHECKED and the base case has supplementary histories
  (PROTOCOL_DRAFT §9), the reference also runs them and the outcomes are combined as in run_supplement.py.
Finished pairs go to runs/e2_run.binding-v1.partial.jsonl (resumed on restart); the full table to
runs/e2_run.binding-v1.jsonl. The frozen results are not changed.
"""
import argparse
import gzip
import json
import os
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ["E2_BINDING_DECISION"] = "1"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_HIST, _SUPP, _PAIRS = None, None, None


def init():
    global _HIST, _SUPP, _PAIRS
    import run_e2
    pairs, _HIST = run_e2.load_inputs()
    _PAIRS = {p["pair_id"]: p for p in pairs}
    supplement = HERE / "histories/supplement_histories.json"
    if supplement.exists():
        payload = json.loads(supplement.read_text())
    else:
        with gzip.open(supplement.with_suffix(".json.gz"), "rt") as source:
            payload = json.load(source)
    _SUPP = payload["histories"]


def work(pair_id):
    import run_e2
    pair = _PAIRS[pair_id]
    row = run_e2.run_pair(pair, _HIST[pair["base_case"]])
    supp = _SUPP.get(pair["base_case"])
    supp = supp if isinstance(supp, list) else (supp or {}).get("histories", supp)
    if row.get("reference", {}).get("outcome") == "REF-EQUIV-CHECKED" and supp:
        started = time.time()
        res = run_e2.reference_side(pair, supp)
        res["seconds"] = round(time.time() - started, 1)
        row["reference_supplement"] = res
        row["reference_frozen_histories"] = row["reference"]
        if res["outcome"] == "REF-DIVERGE":
            row["reference"] = dict(row["reference"], outcome="REF-DIVERGE",
                                    first_divergence=res["first_divergence"], divergence_source="supplement")
        row["agreement"] = run_e2.agreement(row.get("explorer", {}), row["reference"])
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    import run_e2
    assert run_e2.BINDING_DECISION
    pairs, _ = run_e2.load_inputs()
    ids = [p["pair_id"] for p in pairs]
    partial = HERE / "runs/e2_run.binding-v1.partial.jsonl"
    done = {}
    if partial.exists():
        done = {r["pair_id"]: r for r in map(json.loads, partial.read_text().splitlines()) if r}
    meta = HERE / "runs/e2_run.binding-v1.meta.json"
    if not meta.exists():
        root = HERE.parents[2]
        git = lambda *c: subprocess.run(["git", "-C", str(root), *c], capture_output=True, text=True).stdout.strip()
        meta.write_text(json.dumps({"repo_head": git("rev-parse", "HEAD"), "dirty_files": git("status", "--short").splitlines(),
                                    "budget_s": run_e2.BUDGET_S, "workers": a.workers, "binding_decision": True,
                                    "started": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1))
    todo = [p for p in ids if p not in done]
    print(f"{len(todo)} pairs to run ({len(done)} done), workers={a.workers}", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers, initializer=init) as pool, partial.open("a") as log:
        futs = {pool.submit(work, p): p for p in todo}
        for f in as_completed(futs):
            try:
                row = f.result()
            except Exception as e:
                row = {"pair_id": futs[f], "agreement": "HARNESS-ERROR", "reason": f"{type(e).__name__}: {e}"}
            done[row["pair_id"]] = row
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            print(len(done), row["pair_id"], row.get("agreement"), row.get("explorer", {}).get("verdict"),
                  row.get("reference", {}).get("outcome"), row.get("wall_seconds"), flush=True)
    dst = HERE / "runs/e2_run.binding-v1.jsonl"
    dst.write_text("".join(json.dumps(done[p], ensure_ascii=False) + "\n" for p in sorted(done)))
    print(len(done), "rows ->", dst)
    print(Counter(r.get("agreement") for r in done.values()))


if __name__ == "__main__":
    main()
