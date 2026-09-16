"""Apply whisoo's 2026-09-13 post-audit decisions to the corpus files.

python audit/apply_decisions.py      (run from breadth/; idempotent)

Decision 1: C15 (E1-008) is not `elicited`. The protocol defines elicited as a participant-authored
statement directly checkable in released study data; C15 is a participant remark quoted in the body of
Ur et al. (CHI 2014) and has no released-data locator. It moves to `research`. No item is added or
removed to restore equal strata: counts become official 25 / research 26 / elicited 24 / community 25.

Changes are appended to audit/changes_2026-09-13_decisions.csv (the provenance-audit log is not rewritten).
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
BREADTH = HERE.parent
CORPUS = BREADTH / "corpus_100.csv"
LOG = HERE / "changes_2026-09-13_decisions.csv"

DECISION = "whisoo decision 2026-09-13: paper-quoted participant remark has no released-data locator"
EDITS = {"E1-008": {"source_stratum": "research",
                    "provenance_type": "paper-reported participant quote"}}


def main():
    raw = CORPUS.read_bytes()
    eol = "\r\n" if b"\r\n" in raw[:4096] else "\n"
    with CORPUS.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    changes = []
    for r in rows:
        for field, value in EDITS.get(r["corpus_id"], {}).items():
            if r[field] != value:
                changes.append({"file": "corpus_100.csv", "id": r["corpus_id"], "field": field,
                                "before": r[field], "after": value, "reason": DECISION})
                r[field] = value
    if not changes:
        print("no changes (already applied)")
        return
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
    counts = {}
    for r in rows:
        counts[r["source_stratum"]] = counts.get(r["source_stratum"], 0) + 1
    print(f"{len(changes)} changes; strata now {counts}")


if __name__ == "__main__":
    main()
