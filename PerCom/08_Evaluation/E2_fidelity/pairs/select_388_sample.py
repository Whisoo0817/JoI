"""Verdict-blind sample of 40 LLM candidates for E2 (protocol §2 "Scale").

~/temp/bin/python select_388_sample.py      (run from pairs/)

Reads only the candidate files (generation output). No Explorer outcome or result file is read.
Eligible: status "ok" with a non-empty joi_block.script. Seed 20260914; up to 1 per task category
(C01..C26, sorted ids), then the remainder uniformly at random from the eligible rest.
"""
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "explorer/candidates/gemma4-26b-contract-v1-fresh-v4"
SEED, TOTAL, PER_CAT = 20260914, 40, 1


def main():
    eligible = []
    for f in sorted(CAND.glob("C*_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("status") == "ok" and (d.get("joi_block") or {}).get("script"):
            eligible.append(f.stem)
    rng = random.Random(SEED)
    by_cat = defaultdict(list)
    for cid in eligible:
        by_cat[cid.split("_")[0]].append(cid)
    chosen = []
    for cat in sorted(by_cat):
        chosen += rng.sample(by_cat[cat], min(PER_CAT, len(by_cat[cat])))
    rest = [c for c in eligible if c not in chosen]
    chosen += rng.sample(rest, TOTAL - len(chosen))
    out = {"seed": SEED, "rule": __doc__.strip().splitlines()[3:], "eligible": len(eligible),
           "categories_with_eligible": len(by_cat), "sample": sorted(chosen)}
    (Path(__file__).with_name("sample_388.json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(len(eligible), "eligible;", len(by_cat), "categories;", len(chosen), "chosen")


if __name__ == "__main__":
    main()
