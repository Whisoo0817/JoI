"""E3 feedback run: one counterexample-guided repair of the 68 DIVERGE_CONFIRMED E3 candidates.

Stages (each writes under joi/self_feedback/runs/<run-id>/ and refuses to overwrite):

  preflight  freeze checks, build the 68 counterexample payloads from the recorded E3 final run,
             no model call.  Also copies the 382 original candidates to a new candidate tag.
  repair     one model call per case (settings from protocol_e3_feedback_v1.json), write the
             repaired joi_block into the new candidate tag; invalid output keeps the original.
  evaluate   frozen E3 evaluator (explorer.eval.frozen_contract, H=None, B5, E3 caps) on the
             68 cases of the new candidate tag, then a summary joined with repair statuses.

    ~/temp/bin/python joi/self_feedback/run_e3_feedback.py preflight --run-id e3_feedback_68_<date>
    ~/temp/bin/python joi/self_feedback/run_e3_feedback.py repair    --run-id ...
    ~/temp/bin/python joi/self_feedback/run_e3_feedback.py evaluate  --run-id ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from repair_core import feedback, call_model, parse_block, build_payload, render_payload  # noqa: E402

PROTOCOL = HERE / os.environ.get("FEEDBACK_PROTOCOL", "protocol_e3_feedback_v1.json")
FC = ROOT / "explorer" / "eval" / "frozen_contract.py"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_protocol(tag_override=None):
    p = json.loads(PROTOCOL.read_text())
    if tag_override:  # harness checks only; the real run uses the protocol tag
        p["repaired_candidate_tag"] = tag_override
    prompt = (HERE / p["prompt_path"]).read_text(encoding="utf-8")
    if hashlib.sha256(prompt.encode()).hexdigest() != p["prompt_sha256"]:
        raise SystemExit("prompt changed since the protocol was frozen")
    return p, prompt


def dataset_rows():
    from explorer.eval.e3 import load_rows, key_of
    return {key_of(r): r for r in load_rows()}


def preflight(args):
    p, _ = load_protocol(args.tag)
    out = HERE / "runs" / args.run_id
    (out / "evidence").mkdir(parents=True, exist_ok=False)
    base = ROOT / p["baseline"]["run_dir"]
    if sha(base / "case_outcomes.jsonl") != p["baseline"]["case_outcomes_sha256"]:
        raise SystemExit("baseline case_outcomes.jsonl changed")
    outcomes = {json.loads(l)["id"]: json.loads(l) for l in (base / "case_outcomes.jsonl").open()}
    ids = p["population"]["case_ids"]
    assert len(ids) == p["population"]["n"] and all(outcomes[i]["status"] == "DIVERGE_CONFIRMED" for i in ids)
    src_dir = ROOT / p["baseline"]["candidates"]
    for cid, digest in p["population"]["candidate_sha256"].items():
        if sha(src_dir / f"{cid}.json") != digest:
            raise SystemExit("baseline candidate changed: " + cid)
    # evaluator freeze: same source tree as the E3 final protocol (catalog path differs by worktree only)
    from explorer.eval import frozen_contract as fc
    e3p = json.loads((ROOT / p["evaluator"]["e3_protocol"]).read_text())
    sources = {k if not k.endswith("service_list_ver2.0.7.json") else "files/service_list_ver2.0.7.json": v
               for k, v in e3p["sources"].items()}
    fc.verify(sources)
    rows = dataset_rows()
    # new candidate tag: byte copy of all 382 originals; repair replaces 68 of them later
    dst = ROOT / "explorer" / "candidates" / p["repaired_candidate_tag"]
    if dst.exists():
        raise SystemExit("candidate tag exists: " + str(dst))
    shutil.copytree(src_dir, dst, ignore=shutil.ignore_patterns("_gt_*"))
    n_ev = 0
    for cid in ids:
        e = outcomes[cid]["explorer"]
        w = e["result"]["divergences"][0]
        rep = e["replays"][0]
        assert rep["confirmed"]
        witness = {"t0_ms": w["t0_ms"], "input_step_ms": w["input_step_ms"], "initial_gv": w["initial_gv"],
                   "path": w["path"], "input": w["input_"], "dwell_ms": w["dwell_ms"],
                   "actions_ir": w["actions_a"], "actions_joi": w["actions_b"]}
        cand = json.loads((src_dir / f"{cid}.json").read_text())
        row = rows[cid]
        jb = cand["joi_block"]
        fb = feedback(witness, jb["script"]) if p["evidence"].get("counterexample", True) else None
        payload = build_payload(json.loads(row["ir_gt"]), json.loads(row["binding_gt"] or "{}"),
                                json.loads(row["connected_devices"]),
                                {"name": jb.get("name", "Scenario"), "cron": jb.get("cron", ""),
                                 "period": jb.get("period", 0), "script": jb["script"]},
                                fb, name=jb.get("name", "Scenario"), ir_facts=p["model"]["ir_timing_facts"])
        (out / "evidence" / f"{cid}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        n_ev += 1
    rec = {"run_id": args.run_id, "stage": "preflight", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "protocol_sha256": sha(PROTOCOL), "evidence_built": n_ev, "candidate_tag": p["repaired_candidate_tag"],
           "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip(),
           "git_dirty": subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], text=True, cwd=ROOT).strip().splitlines()}
    (out / "preflight.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print(json.dumps(rec, ensure_ascii=False))


def repair(args):
    p, prompt = load_protocol(args.tag)
    out = HERE / "runs" / args.run_id
    pre = json.loads((out / "preflight.json").read_text())
    if pre["protocol_sha256"] != sha(PROTOCOL):
        raise SystemExit("protocol changed after preflight")
    (out / "responses").mkdir(exist_ok=False)
    dst = ROOT / "explorer" / "candidates" / p["repaired_candidate_tag"]
    m = p["model"]
    ids = p["population"]["case_ids"]

    def one(cid):
        payload = json.loads((out / "evidence" / f"{cid}.json").read_text())
        user = render_payload(payload)
        rec = {"id": cid, "request_sha256": hashlib.sha256((prompt + "\n" + user).encode()).hexdigest()}
        try:
            resp = call_model(prompt, user, m["enable_thinking"], seed=m["seed"], max_tokens=m["max_tokens"],
                              temperature=m["temperature"], top_p=m["top_p"], top_k=m["top_k"])
        except Exception as e:  # transport error: recorded, never retried silently
            rec.update(status="MODEL_ERROR", error=repr(e))
            return rec
        rec["model"] = {k: v for k, v in resp.items() if k not in ("content", "reasoning")}
        rec["response"] = resp["content"]
        name = payload["current_candidate"]["name"]
        parsed, err = parse_block(resp["content"], name)
        if parsed is None:
            rec.update(status="INVALID_OUTPUT", error=err)
            return rec
        rec["repaired"] = parsed["joi_block"]
        rec["diagnosis"] = parsed["diagnosis"]
        orig = payload["current_candidate"]
        rec["status"] = "NO_CHANGE" if (parsed["joi_block"]["script"] == orig["script"]
                                        and parsed["joi_block"]["period"] == orig["period"]
                                        and parsed["joi_block"]["cron"] == orig["cron"]) else "REVISED"
        return rec

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        recs = list(ex.map(one, ids))
    for rec in recs:
        (out / "responses" / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        if rec["status"] == "REVISED":
            path = dst / f"{rec['id']}.json"
            cand = json.loads(path.read_text())
            cand["joi_block"] = rec["repaired"]
            cand["code"] = json.dumps(rec["repaired"], ensure_ascii=False)
            cand["feedback_repair"] = {"run_id": args.run_id, "source_candidate_tag": p["baseline"]["candidates"].rsplit("/", 1)[-1]}
            path.write_text(json.dumps(cand, ensure_ascii=False, indent=2))
        print(f"  {rec['id']} {rec['status']:14s} {rec.get('model', {}).get('usage', {}).get('completion_tokens', '')}tok", flush=True)
    summary = {"run_id": args.run_id, "stage": "repair", "n": len(recs), "statuses": dict(Counter(r["status"] for r in recs)),
               "prompt_tokens": sum(r.get("model", {}).get("usage", {}).get("prompt_tokens", 0) for r in recs),
               "completion_tokens": sum(r.get("model", {}).get("usage", {}).get("completion_tokens", 0) for r in recs),
               "wall_seconds": round(time.time() - t0, 1), "model_settings": m,
               "model_id": next((r["model"]["model"] for r in recs if "model" in r), None)}
    (out / "repair_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


def evaluate(args):
    p, _ = load_protocol(args.tag)
    out = HERE / "runs" / args.run_id
    tag = p["repaired_candidate_tag"]
    cand_dir = ROOT / "explorer" / "candidates" / tag
    res = ROOT / "explorer" / "eval" / "results"
    stem = f"{tag.replace('-', '_')}_{args.run_id}"
    py = sys.executable
    prov = res / f"{stem}_lineage.json"
    subprocess.run([py, "-m", "explorer.eval.e3", "manifest", "--tag", tag, "--output", str(prov)], cwd=ROOT, check=True)
    proto = res / f"{stem}_protocol.json"
    subprocess.run([py, str(FC), "protocol", "--candidates", str(cand_dir.relative_to(ROOT)), "--output", str(proto),
                    "--unbounded", "--model-id", p["baseline"]["generation_model"], "--candidate-provenance", str(prov)],
                   cwd=ROOT, check=True)
    full = res / f"{stem}_manifest_full.json"
    subprocess.run([py, str(FC), "prepare", "--protocol", str(proto), "--output", str(full)], cwd=ROOT, check=True)
    mf = json.loads(full.read_text())
    ids = set(p["population"]["case_ids"])
    mf["cases"] = [c for c in mf["cases"] if c["id"] in ids]
    mf["subset"] = p["population"].get("subset_note", "the DIVERGE_CONFIRMED cases of the baseline run; the other cases are unchanged and not re-run")
    sub = res / f"{stem}_manifest.json"
    sub.write_text(json.dumps(mf, ensure_ascii=False, indent=2) + "\n")
    run_dir = res / f"{stem}_run"
    with (out / "evaluate.log").open("x") as log:
        subprocess.run([py, str(FC), "run", "--protocol", str(proto), "--manifest", str(sub), "--output", str(run_dir)],
                       cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT)
    report(args, p, run_dir, proto, sub)


def report(args, p, run_dir, proto, sub):
    out = HERE / "runs" / args.run_id
    types = json.loads((HERE / "e3_68_divergence_types.json").read_text())
    verdicts = {json.loads(l)["id"]: json.loads(l) for l in (run_dir / "case_outcomes.jsonl").open()}
    rows = []
    for cid in p["population"]["case_ids"]:
        r = json.loads((out / "responses" / f"{cid}.json").read_text()) if (out / "responses" / f"{cid}.json").exists() else {"status": "NOT_RUN"}
        v = verdicts.get(cid, {})
        final = v.get("status", "NOT_EVALUATED") if r["status"] in ("REVISED", "NOT_RUN") else r["status"]
        rows.append({"id": cid, "type": types.get(cid, {}).get("type_label"), "repair": r["status"], "verdict": v.get("status"),
                     "final": final, "explorer_status": v.get("explorer", {}).get("status"),
                     "completion_tokens": r.get("model", {}).get("usage", {}).get("completion_tokens")})
    by_type = {}
    for x in rows:
        t = by_type.setdefault(x["type"], [0, 0]); t[1] += 1; t[0] += x["final"] == "EQUIV-FIXPOINT"
    summary = {"run_id": args.run_id, "n": len(rows), "repaired_equiv": sum(x["final"] == "EQUIV-FIXPOINT" for x in rows),
               "final_statuses": dict(Counter(x["final"] for x in rows)), "by_type": {k: f"{a}/{b}" for k, (a, b) in by_type.items()},
               "protocol": str(proto.relative_to(ROOT)), "manifest": str(sub.relative_to(ROOT)), "run_dir": str(run_dir.relative_to(ROOT)),
               "outcomes_sha256": sha(run_dir / "case_outcomes.jsonl"), "rows": rows}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("preflight", "repair", "evaluate"):
        s = sub.add_parser(name)
        s.add_argument("--run-id", required=True)
        s.add_argument("--tag", default=None, help="candidate tag override for harness checks only")
        if name == "repair":
            s.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    globals()[args.cmd](args)


if __name__ == "__main__":
    main()
