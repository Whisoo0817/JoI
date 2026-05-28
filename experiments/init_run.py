#!/usr/bin/env python3
"""Create a timestamped experiment run dir with pinned provenance.

Usage:
  python3 experiments/init_run.py <exp-name> [--dataset dataset.csv] [--model <id>] \
        [--cmd "<command that will be run>"] [--note "<free text>"] [--params k=v ...]

Creates: experiments/<exp-name>/<YYYYMMDD_HHMMSS>__<gitshort>/{run.json, raw/, results/, intermediate/, notes.md}
Prints the run dir path. Pins: git commit, dataset sha256, model+params, command, time.
Run from the repo root (/home/gnltnwjstk/joi).
"""
import argparse, hashlib, json, os, subprocess, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def sh(*a):
    try: return subprocess.check_output(a, cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception: return None

def sha256(path):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p): return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp")
    ap.add_argument("--dataset", default="dataset.csv")
    ap.add_argument("--model", default="")
    ap.add_argument("--cmd", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--params", nargs="*", default=[])
    a = ap.parse_args()

    now = datetime.datetime.now()
    git_short = sh("git", "rev-parse", "--short", "HEAD") or "nogit"
    rundir = os.path.join(ROOT, "experiments", a.exp, f"{now:%Y%m%d_%H%M%S}__{git_short}")
    for sub in ("raw", "results", "intermediate"):
        os.makedirs(os.path.join(rundir, sub), exist_ok=True)

    ds_sha = sha256(a.dataset)
    run = {
        "exp": a.exp,
        "started": now.isoformat(timespec="seconds"),
        "git_commit": sh("git", "rev-parse", "HEAD"),
        "git_short": git_short,
        "git_dirty": bool(sh("git", "status", "--porcelain")),
        "dataset": a.dataset,
        "dataset_sha256": ds_sha,
        "model": a.model,
        "command": a.cmd,
        "params": dict(kv.split("=", 1) for kv in a.params if "=" in kv),
        "note": a.note,
    }
    with open(os.path.join(rundir, "run.json"), "w") as f:
        json.dump(run, f, indent=2)
    with open(os.path.join(rundir, "notes.md"), "w") as f:
        f.write(f"# {a.exp} — {now:%Y-%m-%d %H:%M:%S}\n\n{a.note}\n")
    print(rundir)

if __name__ == "__main__":
    main()
