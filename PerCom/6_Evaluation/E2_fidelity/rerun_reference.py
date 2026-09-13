"""Recompute the reference side of an E2 run from a pinned reference directory.

~/temp/bin/python rerun_reference.py --ref-dir DIR --label LABEL [--run runs/e2_run.jsonl] [--workers N]

Reference outcomes are reported from this recomputation, not from the in-run values: the reference was revised
after the freeze (FREEZE_MANIFEST.md) while the run was in progress, and a worker could import either version.
For every row of the run: the reference side is recomputed with the modules in DIR on the frozen pairs and
histories; the Explorer verdict and witness stored in the run are kept; the witness replay and the agreement are
recomputed with the same reference. Output: runs/e2_run.ref-<LABEL>.jsonl.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent


def work(args):
    ref_dir, row = args
    os.environ["E2_REF_DIR"] = ref_dir
    sys.path.insert(0, ref_dir)
    sys.path.insert(0, str(HERE))
    import run_e2
    pairs, hist = run_e2.load_inputs()
    pair = next(p for p in pairs if p["pair_id"] == row["pair_id"])
    row = dict(row)
    row["reference_in_run"] = row.get("reference")
    row["reference"] = run_e2.reference_side(pair, hist[pair["base_case"]])
    exp = row.get("explorer", {})
    if exp.get("witness"):
        exp["witness_on_reference"] = run_e2.witness_on_reference(pair, exp["witness"])
    row["agreement"] = run_e2.agreement(exp, row["reference"])
    row["reference_dir"] = ref_dir
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-dir", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--run", default=str(HERE / "runs/e2_run.jsonl"))
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    ref_dir = str(Path(a.ref_dir).resolve())
    rows = [json.loads(l) for l in Path(a.run).read_text().splitlines() if l.strip()]
    dst = Path(a.run).with_suffix(f".ref-{a.label}.jsonl")
    out = []
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = [pool.submit(work, (ref_dir, r)) for r in rows]
        for f in as_completed(futs):
            out.append(f.result())
    out.sort(key=lambda r: r["pair_id"])
    dst.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    from collections import Counter
    print(len(out), "rows ->", dst)
    print(Counter(r["agreement"] for r in out))


if __name__ == "__main__":
    main()
