"""Smoke run (not a correctness result): parse and run every candidate JoI block of
explorer/candidates/gemma4-26b-contract-v1-fresh-v4 and every dataset.csv IR (with binding_gt, connected_devices) on
one simple history: all catalog inputs of the connected devices at a type-valid default at t=0, horizon 10 s.
Counts crashes and REF-UNSUPPORTED reasons. Writes SMOKE_388.md and smoke_388_results.json.
Run: ~/temp/bin/python smoke_388.py
"""
import collections
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import REPO, Catalog, DEFAULT_CATALOG     # noqa: E402
from run import run_ir, run_joi                       # noqa: E402

CAND = REPO / "explorer" / "candidates" / "gemma4-26b-contract-v1-fresh-v4"
DATASET = REPO / "dataset.csv"
HORIZON = 10_000


def default_value(cat, service_id, typ, fmt, bound):
    t = (typ or "").upper()
    if t in ("BOOL", "BOOLEAN"):
        return False
    if t in ("INTEGER", "DOUBLE"):
        v = 0
        if bound:
            v = min(max(v, bound[0]), bound[1])
        return int(v) if t == "INTEGER" else float(v)
    if t == "STRING":
        return ""
    if t == "ENUM":
        vals = cat.enum_values(service_id, fmt) if fmt else None
        return vals[0] if vals else None
    return None


def default_events(devices, cat):
    upd = {"Clock.IsHoliday": False}
    for d, info in devices.items():
        for c in info.get("category") or []:
            svc = cat.service(c)
            if svc is None:
                continue
            for m in svc["members"].values():
                key = f"{d}.{m.id}"
                if key in upd:
                    continue
                if m.kind == "value":
                    upd[key] = default_value(cat, svc["id"], m.type, m.format, m.bound)
                elif m.read_role and not m.args:
                    upd[key] = default_value(cat, svc["id"], m.ret, None, None)
    return [(0, upd)]


def main():
    cat = Catalog(DEFAULT_CATALOG)
    results = {"joi": [], "ir": []}
    for f in sorted(CAND.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        block = d.get("joi_block")
        if not block:
            results["joi"].append(dict(id=f.stem, status="no-joi-block", category=d.get("error_code", ""), detail=""))
            continue
        devices = d["connected_devices"]
        res = run_joi(block, devices, default_events(devices, cat), HORIZON)
        results["joi"].append(dict(id=f.stem, status=res["status"], category=res["category"], detail=res["detail"],
                                   actions=len(res["raw_actions"])))
    csv.field_size_limit(10 ** 9)
    with DATASET.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            devices = json.loads(row["connected_devices"])
            res = run_ir(json.loads(row["ir_gt"]), json.loads(row["binding_gt"]), devices,
                         default_events(devices, cat), HORIZON)
            results["ir"].append(dict(id=f"{row['category_v2']}#{row['index']}", status=res["status"],
                                      category=res["category"], detail=res["detail"], actions=len(res["raw_actions"])))
    (HERE / "smoke_388_results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    lines = ["# SMOKE_388 — crash / REF-UNSUPPORTED scan (not a correctness result)", "",
             f"History: every catalog value (and zero-argument read-role function) of each connected device at a "
             f"type-valid default at t=0 (BOOL false, numbers 0 clamped into the declared bound, STRING \"\", ENUM "
             f"first member, other types missing), `Clock.IsHoliday` false, horizon {HORIZON} ms, t_start 0.", "",
             "Artefacts of this single default history (not program faults): `arg-range` for `SetChannel(Channel - 1)` "
             "with Channel 0, and `history-missing-nonnull` where a `MenuProvider.GetMenu(...)` query has no value "
             "(query keys with arguments are not pre-filled). Every other reason is a construct the reference refuses "
             "(see SPEC_GAPS.md).", ""]
    for kind, title in (("joi", "Candidate JoI blocks (388 files)"), ("ir", "Dataset IRs with binding_gt (388 rows)")):
        rows = results[kind]
        st = collections.Counter(r["status"] for r in rows)
        lines += [f"## {title}", "", "| status | count |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in st.most_common()]
        for status in ("unsupported", "error"):
            cats = collections.Counter(r["category"] for r in rows if r["status"] == status)
            if not cats:
                continue
            lines += ["", f"### {status} by reason", "", "| reason | count | example |", "|---|---|---|"]
            for c, n in cats.most_common():
                ex = next(r for r in rows if r["status"] == status and r["category"] == c)
                det = ex["detail"].split("\n")[0].replace("|", "\\|")[:150]
                lines.append(f"| {c} | {n} | {ex['id']}: {det} |")
        no_block = collections.Counter(r["category"] for r in rows if r["status"] == "no-joi-block")
        if no_block:
            lines += ["", "Files without a JoI block (generation error codes): "
                      + ", ".join(f"{k or '?'} {v}" for k, v in no_block.most_common())]
        lines.append("")
    (HERE / "SMOKE_388.md").write_text("\n".join(lines), encoding="utf-8")
    for kind in ("joi", "ir"):
        print(kind, collections.Counter(r["status"] for r in results[kind]))


if __name__ == "__main__":
    main()
