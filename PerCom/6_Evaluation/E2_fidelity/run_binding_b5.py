"""E2 rerun, binding decision B5 (selector assignments), for the pairs it applies to.

~/temp/bin/python run_binding_b5.py [--workers N]

Pairs: those whose JoI has a selector occurrence over a service with several binding device sets (Explorer or
reference selector space non-empty). Each is rerun exactly like run_binding_v1.py with E2_BINDING_ASSIGN=1.
Output runs/e2_run.binding-b5.partial.jsonl (per pair, resumed) and, once runs/e2_run.binding-v1.jsonl exists,
runs/e2_run.binding-final.jsonl = binding-v1 rows with these pairs replaced.
"""
import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ["E2_BINDING_DECISION"] = "1"
os.environ["E2_BINDING_ASSIGN"] = "1"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_binding_v1 as V1  # noqa: E402


def space(pair_id):
    import run_e2
    pair = V1._PAIRS[pair_id]
    doms = []
    try:
        doms += run_e2.selector_space(pair)[0]
    except Exception:
        pass
    sys.path.insert(0, str(run_e2.REF))
    from run import selector_space as ref_space
    doms += ref_space(pair["joi"], pair["devices"], pair["binding"], pair["ir"], str(run_e2.ROOT / pair["catalog"])).get("domains") or []
    return pair_id, bool(doms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    V1.init()
    ids = sorted(p for p, ok in map(space, sorted(V1._PAIRS)) if ok)
    print(len(ids), "pairs with selector assignments:", ids, flush=True)
    partial = HERE / "runs/e2_run.binding-b5.partial.jsonl"
    done = {}
    if partial.exists():
        done = {r["pair_id"]: r for r in map(json.loads, partial.read_text().splitlines()) if r}
    with ProcessPoolExecutor(max_workers=a.workers, initializer=V1.init) as pool, partial.open("a") as log:
        futs = {pool.submit(V1.work, p): p for p in ids if p not in done}
        for f in as_completed(futs):
            row = f.result()
            done[row["pair_id"]] = row
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            print(row["pair_id"], row.get("agreement"), row["explorer"].get("verdict"), row["reference"]["outcome"],
                  row["explorer"].get("selector_assignment", {}).get("tried"), row.get("wall_seconds"), flush=True)
    v1 = HERE / "runs/e2_run.binding-v1.jsonl"
    if v1.exists():
        rows = {r["pair_id"]: r for r in map(json.loads, v1.read_text().splitlines()) if r}
        rows.update({p: done[p] for p in ids})
        dst = HERE / "runs/e2_run.binding-final.jsonl"
        dst.write_text("".join(json.dumps(rows[p], ensure_ascii=False) + "\n" for p in sorted(rows)))
        print(len(rows), "rows ->", dst)
        print(Counter(r.get("agreement") for r in rows.values()))
    else:
        print("binding-v1 not finished; rerun this script afterwards to merge (finished pairs are kept)")


if __name__ == "__main__":
    main()
