"""E2 pairs from the verdict-blind 388 sample (protocol §2 "Scale").

~/temp/bin/python build_388_pairs.py      (run from pairs/)

For each id in sample_388.json: the dataset IR and binding (dataset.csv `ir_gt`, `binding_gt`,
`connected_devices`) and the LLM candidate JoI block (`joi_block` of
explorer/candidates/gemma4-26b-contract-v1-fresh-v4/<id>.json). No Explorer outcome is read.

Start time (model parameter, S11 calendar, t = 0 Monday 00:00): an IR anchored by a daily cron `M H * * *`
starts at Monday H:M; any other IR starts at Monday 12:00. Cron anchors are erased by both tools (one window).
Output: sample_388_pairs.json with sha256 of the inputs.
"""
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAND = ROOT / "explorer/candidates/gemma4-26b-contract-v1-fresh-v4"
HOUR, MIN = 3_600_000, 60_000
DEFAULT_START = 12 * HOUR


def start_of(ir):
    tl = ir.get("timeline") or []
    if tl and tl[0].get("op") == "start_at" and tl[0].get("anchor") == "cron":
        fields = (tl[0].get("cron") or "").split()
        if len(fields) == 5 and fields[0].isdigit() and fields[1].isdigit():
            return int(fields[1]) * HOUR + int(fields[0]) * MIN, tl[0]["cron"]
        return None, tl[0].get("cron")
    return DEFAULT_START, ""


def main():
    rows = {f"{r['category_v2']}_{int(float(r['index'])):03d}": r for r in csv.DictReader(open(ROOT / "dataset.csv"))}
    sample = json.loads((HERE / "sample_388.json").read_text())["sample"]
    pairs, inputs = [], [HERE / "build_388_pairs.py", HERE / "sample_388.json", ROOT / "dataset.csv"]
    for cid in sample:
        r = rows[cid]
        cand_path = CAND / f"{cid}.json"
        inputs.append(cand_path)
        cand = json.loads(cand_path.read_text(encoding="utf-8"))
        ir = json.loads(r["ir_gt"])
        t_start, cron = start_of(ir)
        pairs.append(dict(pair_id=f"{cid}/llm", kind="llm", family=None, base_case=cid, automation="main",
                          description="LLM candidate (gemma4-26b-contract-v1-fresh-v4)",
                          ir=ir, binding=json.loads(r["binding_gt"]), devices=json.loads(r["connected_devices"]),
                          catalog="files/service_list_ver2.0.7.json", t_start_ms=t_start, ir_cron=cron,
                          joi=cand["joi_block"], command_eng=r["command_eng"]))
    inputs.append(ROOT / "files/service_list_ver2.0.7.json")
    out = {"inputs_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
           "start_rule": "daily cron M H -> Monday H:M; otherwise Monday 12:00",
           "n_pairs": len(pairs), "pairs": pairs}
    (HERE / "sample_388_pairs.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    bad = [p["pair_id"] for p in pairs if p["t_start_ms"] is None]
    print(len(pairs), "pairs;", "non-daily cron:", bad)


if __name__ == "__main__":
    main()
