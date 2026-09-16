#!/usr/bin/env python3
"""Pack each judge's per-call responses into one .jsonl.gz (same convention as E2's runs/*.jsonl.gz).

The raw per-call directories stay on disk but are not committed; the packed file is the record.
Rerunning judge.py reads the per-call cache, so unpack before resuming a judge arm.
"""
import gzip
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def pack(run_dir):
    src = os.path.join(run_dir, "responses")
    if not os.path.isdir(src):
        return None
    rows = []
    for name in sorted(os.listdir(src)):
        if name.endswith(".json"):
            rows.append(json.load(open(os.path.join(src, name))))
    out = os.path.join(run_dir, "responses.jsonl.gz")
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    return {"path": os.path.relpath(out, HERE), "calls": len(rows),
            "sha256": hashlib.sha256(open(out, "rb").read()).hexdigest(),
            "bytes": os.path.getsize(out)}


def unpack(run_dir):
    src = os.path.join(run_dir, "responses.jsonl.gz")
    dst = os.path.join(run_dir, "responses")
    os.makedirs(dst, exist_ok=True)
    n = 0
    with gzip.open(src, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            json.dump(r, open(os.path.join(dst, f"{r['sha']}_{r['rep']}.json"), "w"),
                      ensure_ascii=False, indent=1)
            n += 1
    return n


if __name__ == "__main__":
    runs = os.path.join(HERE, "runs")
    dirs = [os.path.join(runs, d) for d in sorted(os.listdir(runs)) if os.path.isdir(os.path.join(runs, d))]
    if len(sys.argv) > 1 and sys.argv[1] == "unpack":
        for d in dirs:
            if os.path.exists(os.path.join(d, "responses.jsonl.gz")):
                print(os.path.basename(d), unpack(d))
    else:
        man = {}
        for d in dirs:
            r = pack(d)
            if r:
                man[os.path.basename(d)] = r
                print(f"{os.path.basename(d):22s} {r['calls']:4d} calls  {r['bytes']/1e6:.1f} MB")
        json.dump(man, open(os.path.join(runs, "responses_manifest.json"), "w"), ensure_ascii=False, indent=1)
