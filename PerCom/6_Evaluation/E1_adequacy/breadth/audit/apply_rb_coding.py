"""Apply the author's R/B coding (whisoo, 2026-09-13) to rb_adjudicated.

python audit/apply_rb_coding.py      (run from breadth/; idempotent)

Record: audit/AUTHOR_RB_CODING_2026-09-13.md. Changes are appended to audit/changes_2026-09-13_rb_coding.csv.

- AMBIGUOUS / OUT_OF_SCOPE rows: N/A (excluded from the R/B distribution).
- Seeds: the Stage A codes in ../README.md §5.
- Listed exceptions: the author's exact values.
- Other IN_SCOPE rows: rb_preliminary, reviewed and approved by the author.
rb_preliminary, rb_coder_1 and rb_coder_2 are not changed.
"""
import csv
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BREADTH = HERE.parent
CORPUS = BREADTH / "corpus_100.csv"
README = BREADTH.parent / "README.md"
LOG = HERE / "changes_2026-09-13_rb_coding.csv"
SRC = "author R/B coding 2026-09-13"
CODES = [f"R{i}" for i in range(1, 11)] + [f"B{i}" for i in range(1, 6)]

EXCEPTIONS = {
    "E1-020": "R1, R6", "E1-031": "R1, R6", "E1-042": "R1", "E1-050": "R9", "E1-056": "R1",
    "E1-058": "R1, R9", "E1-069": "R1", "E1-071": "R1", "E1-072": "R1, R9", "E1-073": "R1",
    "E1-082": "R1, R3", "E1-088": "R1, R9", "E1-093": "R1, R2, B2", "E1-095": "R5, R8, R9",
    "E1-097": "R1, R6, B2", "E1-099": "R3, R10", "E1-100": "R1",
}


def stage_a_codes():
    codes = {}
    for line in README.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| (C\d+(?:-O)?) \| [^|]* \| ([RB0-9 ]+) \|", line)
        if m:
            codes[m.group(1)] = ", ".join(m.group(2).split())
    assert len(codes) == 12, codes
    return codes


def main():
    seeds = stage_a_codes()
    raw = CORPUS.read_bytes()
    eol = "\r\n" if b"\r\n" in raw[:4096] else "\n"
    with CORPUS.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    changes = []
    for r in rows:
        cid = r["corpus_id"]
        if r["screen_status"] != "IN_SCOPE":
            value, why = "N/A", f"{r['screen_status']}; excluded from the R/B distribution"
        elif r["prior_case_id"]:
            value, why = seeds[r["prior_case_id"]], f"Stage A code for {r['prior_case_id']} (README §5)"
        elif cid in EXCEPTIONS:
            value, why = EXCEPTIONS[cid], "author exception label"
        else:
            value, why = r["rb_preliminary"], "rb_preliminary reviewed and approved by the author"
        if r["rb_adjudicated"] != value:
            changes.append({"file": "corpus_100.csv", "id": cid, "field": "rb_adjudicated",
                            "before": r["rb_adjudicated"], "after": value, "reason": f"{SRC}: {why}"})
            r["rb_adjudicated"] = value

    status = Counter(r["screen_status"] for r in rows)
    assert status == {"IN_SCOPE": 92, "AMBIGUOUS": 6, "OUT_OF_SCOPE": 2}, status
    coded = [r for r in rows if r["screen_status"] == "IN_SCOPE"]
    assert all(r["rb_adjudicated"] not in ("", "N/A") for r in coded)
    assert all(r["rb_adjudicated"] == "N/A" for r in rows if r["screen_status"] != "IN_SCOPE")
    for r in coded:
        toks = [t.strip() for t in r["rb_adjudicated"].split(",")]
        bad = [t for t in toks if t not in CODES]
        assert not bad, (r["corpus_id"], bad)
        assert len(toks) == len(set(toks)), r["corpus_id"]
    assert not any(r["rb_coder_1"] or r["rb_coder_2"] for r in rows)

    if changes:
        with CORPUS.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator=eol)
            w.writeheader()
            w.writerows(rows)
        new = not LOG.exists()
        with LOG.open("a", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["file", "id", "field", "before", "after", "reason"])
            if new:
                w.writeheader()
            w.writerows(changes)
    print(f"{len(changes)} changes" if changes else "no changes (already applied)")
    by = Counter(t.strip() for r in coded for t in r["rb_adjudicated"].split(","))
    print(f"denominator {len(coded)}")
    for c in CODES:
        print(f"{c}\t{by[c]}")


if __name__ == "__main__":
    main()
