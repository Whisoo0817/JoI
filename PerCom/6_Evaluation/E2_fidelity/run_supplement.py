"""E2 supplementary reference run (PROTOCOL_DRAFT §9).

~/temp/bin/python run_supplement.py [--workers N]

For every pair whose outcome with the current reference (runs/e2_run.ref-current.jsonl) is REF-EQUIV-CHECKED, the
current reference runs the pair on histories/supplement_histories.json. The other pairs already show a reference
difference or are unsupported and are copied unchanged. Explorer verdicts and witness replays are not recomputed.
Output runs/e2_run.ref-current-supp.jsonl:
- `reference_supplement`: the pair outcome on the supplementary histories alone;
- `reference`: combined — REF-DIVERGE when the supplement diverges (first difference taken from the supplement),
  otherwise the frozen-history outcome; a supplementary unsupported/error is kept in `reference_supplement` and
  does not change the combined outcome;
- `agreement`: recomputed from the combined outcome.
"""
import argparse
import gzip
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_PAIRS, _SUPP = None, None


def read_rows(path):
    path = Path(path)
    if not path.exists():
        path = path.with_name(path.name + ".gz")
    text = gzip.open(path, "rt").read() if path.suffix == ".gz" else path.read_text()
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def init():
    global _PAIRS, _SUPP
    _PAIRS = {}
    for f in ("pairs/e1_pairs.json", "pairs/sample_388_pairs.json"):
        _PAIRS.update({p["pair_id"]: p for p in json.loads((HERE / f).read_text())["pairs"]})
    _SUPP = json.loads((HERE / "histories/supplement_histories.json").read_text())["histories"]


def work(pair_id):
    import run_e2
    pair = _PAIRS[pair_id]
    started = time.time()
    res = run_e2.reference_side(pair, _SUPP[pair["base_case"]])
    res["seconds"] = round(time.time() - started, 1)
    return pair_id, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--src", default=str(HERE / "runs/e2_run.ref-current.jsonl"))
    a = ap.parse_args()
    rows = {r["pair_id"]: r for r in read_rows(a.src)}
    todo = sorted(p for p, r in rows.items() if r["reference"]["outcome"] == "REF-EQUIV-CHECKED")
    print(f"{len(todo)} pairs on supplementary histories", flush=True)
    import run_e2
    partial = HERE / "runs/e2_run.ref-current-supp.partial.jsonl"   # one result per finished pair; resumed on restart
    done = {}
    if partial.exists():
        done = {d["pair_id"]: d["result"] for d in map(json.loads, partial.read_text().splitlines()) if d}
    print(f"{len(done)} already done", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers, initializer=init) as pool, partial.open("a") as log:
        futs = [pool.submit(work, p) for p in todo if p not in done]
        finished = [(p, done[p]) for p in todo if p in done]
        for f in as_completed(futs):
            pid, res = f.result()
            log.write(json.dumps({"pair_id": pid, "result": res}, ensure_ascii=False) + "\n")
            log.flush()
            finished.append((pid, res))
        for pid, res in finished:
            row = rows[pid]
            row["reference_supplement"] = res
            row["reference_frozen_histories"] = row["reference"]
            if res["outcome"] == "REF-DIVERGE":
                row["reference"] = dict(row["reference"], outcome="REF-DIVERGE", first_divergence=res["first_divergence"],
                                        divergence_source="supplement")
            row["agreement"] = run_e2.agreement(row.get("explorer", {}), row["reference"])
            print(pid, res["outcome"], res["n_histories"], res["seconds"], row["agreement"], flush=True)
    dst = HERE / "runs/e2_run.ref-current-supp.jsonl"
    dst.write_text("".join(json.dumps(rows[p], ensure_ascii=False) + "\n" for p in sorted(rows)))
    print(len(rows), "rows ->", dst)
    print(Counter(r["agreement"] for r in rows.values()))
    print("supplement outcomes", Counter(r["reference_supplement"]["outcome"] for r in rows.values()
                                         if "reference_supplement" in r))


if __name__ == "__main__":
    main()
