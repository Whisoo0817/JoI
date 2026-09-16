#!/usr/bin/env python3
"""Check every rewrite against the confirmed IR with the frozen E3 evaluator (same snapshot,
H=None, B5, E3 caps). A rewrite is a Fig2 pair only if it is EQUIV-FIXPOINT.

Per rewrite type this runs explorer.eval.frozen_contract protocol -> prepare -> run on the
candidate dir explorer/candidates/fig2-rw-<type>, restricted to the seeds that have that rewrite.
Outputs: rewrites/verified_pairs.json and explorer/eval/results/fig2_rw_<type>_* artifacts.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FC = os.path.join(ROOT, "explorer/eval/frozen_contract.py")
RES = os.path.join(ROOT, "explorer/eval/results")
PY = sys.executable
STAMP = time.strftime("%Y%m%d")


def run_type(name, ids):
    tag = "fig2-rw-" + name
    stem = f"fig2_rw_{name}_{STAMP}"
    prov = os.path.join(RES, stem + "_lineage.json")
    proto = os.path.join(RES, stem + "_protocol.json")
    full = os.path.join(RES, stem + "_manifest_full.json")
    sub = os.path.join(RES, stem + "_manifest.json")
    run_dir = os.path.join(RES, stem + "_run")
    if os.path.exists(run_dir):
        print(f"[{name}] run dir exists, reusing", flush=True)
    else:
        # provenance: which seed each rewrite came from (e3 manifest needs a full 382-row dir, so write it here)
        cdir = os.path.join(ROOT, "explorer/candidates", tag)
        lineage = {"candidate_tag": tag, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "reason": f"behavior-preserving rewrite '{name}' of E3 EQUIV-FIXPOINT seeds (build_rewrites.py)",
                   "records": []}
        for cid in sorted(ids):
            f = os.path.join(cdir, cid + ".json")
            d = json.load(open(f))
            lineage["records"].append({"id": cid, "path": f, "sha256": hashlib.sha256(open(f, "rb").read()).hexdigest(),
                                       "seed_tag": d["rewrite"]["seed_tag"], "rewrite": name})
        json.dump(lineage, open(prov, "w"), ensure_ascii=False, indent=1)
        subprocess.run([PY, FC, "protocol", "--candidates", "explorer/candidates/" + tag, "--output", proto,
                        "--unbounded", "--model-id", "rewrite:" + name, "--candidate-provenance", prov], cwd=ROOT, check=True)
        subprocess.run([PY, FC, "prepare", "--protocol", proto, "--output", full], cwd=ROOT, check=True)
        mf = json.load(open(full))
        mf["cases"] = [c for c in mf["cases"] if c["id"] in ids]
        mf["subset"] = f"seeds that have the {name} rewrite; other rows have no candidate"
        json.dump(mf, open(sub, "w"), ensure_ascii=False, indent=2)
        with open(os.path.join(RES, stem + "_run.log"), "w") as log:
            subprocess.run([PY, FC, "run", "--protocol", proto, "--manifest", sub, "--output", run_dir],
                           cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT)
    out = {}
    for line in open(os.path.join(run_dir, "case_outcomes.jsonl")):
        r = json.loads(line)
        out[r["id"]] = r["status"]
    return out, os.path.relpath(run_dir, ROOT)


def main():
    rw = json.load(open(os.path.join(HERE, "rewrites", "rewrites.json")))
    by_type = {}
    for g in rw["groups"]:
        for t in g["variants"]:
            by_type.setdefault(t, set()).add(g["id"])
    verified = {"seed_run": rw["seed_run"], "types": rw["types"], "runs": {}, "outcomes": {}, "pairs": []}
    for name in rw["types"]:
        ids = by_type.get(name, set())
        if not ids:
            continue
        t0 = time.time()
        out, run_dir = run_type(name, ids)
        c = Counter(out.values())
        print(f"[{name}] {len(ids)} rewrites -> {dict(c)}  ({time.time() - t0:.0f}s)", flush=True)
        verified["runs"][name] = run_dir
        verified["outcomes"][name] = out
    for g in rw["groups"]:
        for t, v in g["variants"].items():
            st = verified["outcomes"].get(t, {}).get(g["id"])
            if st == "EQUIV-FIXPOINT":
                verified["pairs"].append({"id": g["id"], "type": t, "band": rw["types"][t],
                                          "command": g["command"], "base": g["base"], "variant": v})
    json.dump(verified, open(os.path.join(HERE, "rewrites", "verified_pairs.json"), "w"), ensure_ascii=False, indent=1)
    print("verified pairs:", len(verified["pairs"]), dict(Counter(p["type"] for p in verified["pairs"])))


if __name__ == "__main__":
    main()
