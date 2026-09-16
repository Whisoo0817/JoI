"""Recompute the Explorer-witness replay on the reference after the harness correction of 2026-09-14.

~/temp/bin/python recheck_witnesses.py [runs/e2_run.jsonl]

The first run converted Explorer witness paths with the dwell added after an entry's inputs instead of before
(harness bug, see FREEZE_MANIFEST.md "Harness corrections"). Explorer verdicts, reference outcomes and histories
are untouched; only `explorer.witness_on_reference` and `agreement` are recomputed from the stored witness.
Writes <input>.rewitness.jsonl next to the input and keeps the original file.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_e2  # noqa: E402


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "runs/e2_run.jsonl"
    pairs, _ = run_e2.load_inputs()
    by_id = {p["pair_id"]: p for p in pairs}
    out_rows, changed = [], 0
    for line in src.read_text().splitlines():
        row = json.loads(line)
        exp = row.get("explorer", {})
        if exp.get("witness"):
            old = (exp.get("witness_on_reference", {}).get("status"), row.get("agreement"))
            exp["witness_on_reference"] = run_e2.witness_on_reference(by_id[row["pair_id"]], exp["witness"])
            row["agreement"] = run_e2.agreement(exp, row["reference"])
            row["witness_rechecked"] = True
            changed += old != (exp["witness_on_reference"].get("status"), row["agreement"])
        out_rows.append(row)
    dst = src.with_suffix(".rewitness.jsonl")
    dst.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows))
    print(f"{len(out_rows)} rows, {changed} changed -> {dst}")


if __name__ == "__main__":
    main()
