"""Apply the author's manual screening of the 100-item corpus (whisoo, 2026-09-13).

python audit/apply_author_screening.py      (run from breadth/; idempotent)

Record of the decisions: audit/AUTHOR_SCREENING_2026-09-13.md.
Changes are appended to audit/changes_2026-09-13_author_screening.csv (earlier logs are not rewritten).

- screen_status: the author's final values (92 IN_SCOPE, 6 AMBIGUOUS, 2 OUT_OF_SCOPE, 0 UNMATCHED).
- duplicate_family: cleared everywhere; the author found no retained duplicate. The former similar-topic groups
  move to a new `topic_family` column.
- Class columns: only the corrections the author stated.
- rb_adjudicated: only rows whose R/B set follows directly from the author's statement and the README
  definitions. All other rows stay blank (open questions in the record).
"""
import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BREADTH = HERE.parent
CORPUS = BREADTH / "corpus_100.csv"
LOG = HERE / "changes_2026-09-13_author_screening.csv"
SRC = "author manual screening 2026-09-13"

AMBIGUOUS = {"E1-015", "E1-017", "E1-018", "E1-027", "E1-083", "E1-091"}
OUT_OF_SCOPE = {"E1-036", "E1-037"}

EDITS = {
    "E1-020": {"notes": ("Author interpretation: if one of the two appliances is already running, a later start "
                         "request for the other is not started. No notification action is added.",
                         "minimal operational interpretation")},
    "E1-027": {"screen_reason": ("The clock meaning of 'between 7 and 12 pm' is unclear; the original text is "
                                 "kept without normalization.", "time range unclear"),
               "ambiguity_for_user": ("Which time range 'between 7 and 12 pm' denotes.", "time range unclear")},
    "E1-031": {"screen_reason": ("", "UNMATCHED reason no longer applies"),
               "notes": ("Author interpretation: a backend history/count service provides the day's toothbrush use "
                         "count and the automation reads it as a guard. This is not a claim that the IR performs "
                         "internal accumulation.", "backend count read as guard")},
    "E1-091": {"screen_reason": ("The source does not state the content of the joint condition over the valve "
                                 "positions.", "joint condition unspecified")},
    "E1-095": {"ambiguity_for_user": ("", "interpretation fixed"),
               "notes": ("Author interpretation: read pH and chlorine at 10:00, 11:00, 12:00, 13:00 and 14:00 "
                         "(five samples) and report each mean at 15:00.", "interpretation fixed")},
    "E1-042": {"trigger_class": ("event/state", "presence sync; no time condition in the source")},
    "E1-050": {"trigger_class": ("clock/calendar", "fixed clock time turns lights on")},
    "E1-056": {"trigger_class": ("event/state", "first arrival is an event; no time condition")},
    "E1-058": {"trigger_class": ("event/state; clock/calendar", "'after dark' is a time/environment guard"),
               "temporal_class": ("immediate/unspecified", "'after dark' is a guard, not a delay")},
    "E1-069": {"trigger_class": ("event/state", "whole-home vacancy state change; no time condition")},
    "E1-071": {"trigger_class": ("manual", "manual voice command followed by several actions")},
    "E1-072": {"trigger_class": ("event/state; clock/calendar", "'after dark' is a time/environment guard"),
               "temporal_class": ("immediate/unspecified", "'after dark' is a guard, not a delay")},
    "E1-073": {"action_cardinality": ("single", "one notification")},
    "E1-082": {"action_cardinality": ("single", "one notification")},
    "E1-100": {"action_cardinality": ("single", "one notification")},
    "E1-088": {"temporal_class": ("immediate/unspecified", "sunset-2h..sunset is a sun-based time guard, not a duration")},
    "E1-093": {"trigger_class": ("event/state", "no time condition")},
    "E1-097": {"trigger_class": ("event/state", "doorbell event; not a clock or manual condition"),
               "control_class": ("sequence/composition; guard/branch; parallel", "presence/zone guard")},
}

# R/B sets that follow directly from the author's statement (README §1 definitions).
RB = {
    "E1-042": ("R1", "presence changes switch the light immediately; no time condition"),
    "E1-050": ("R9", "fixed clock time"),
    "E1-056": ("R1", "first-arrival event; no time condition"),
    "E1-058": ("R1, R9", "TV-on event under an after-dark time guard; no delay"),
    "E1-069": ("R1", "vacancy state change; no time condition"),
    "E1-071": ("R1", "manual voice command, actions follow at once"),
    "E1-072": ("R1, R9", "arrival/vacancy events under a time/environment guard; no delay"),
    "E1-088": ("R1, R9", "weather event under a sun-based time guard; no duration"),
}


def main():
    raw = CORPUS.read_bytes()
    eol = "\r\n" if b"\r\n" in raw[:4096] else "\n"
    with CORPUS.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = list(reader.fieldnames), list(reader)
    changes = []

    def put(r, field, value, why):
        if r[field] != value:
            changes.append({"file": "corpus_100.csv", "id": r["corpus_id"], "field": field,
                            "before": r[field], "after": value, "reason": f"{SRC}: {why}"})
            r[field] = value

    if "topic_family" not in fields:
        fields.append("topic_family")
        for r in rows:
            r["topic_family"] = ""
            put(r, "topic_family", r["duplicate_family"], "similar topic kept outside the duplicate field")

    for r in rows:
        cid = r["corpus_id"]
        status = "AMBIGUOUS" if cid in AMBIGUOUS else "OUT_OF_SCOPE" if cid in OUT_OF_SCOPE else "IN_SCOPE"
        put(r, "screen_status", status, "final status")
        put(r, "duplicate_family", "", "no retained duplicate under protocol §2")
        for field, (value, why) in EDITS.get(cid, {}).items():
            if field == "notes" and value:
                if value in r["notes"]:
                    continue
                value = f"{r['notes']} {value}".strip()
            put(r, field, value, why)
        if cid in RB:
            put(r, "rb_adjudicated", RB[cid][0], RB[cid][1])

    counts = Counter(r["screen_status"] for r in rows)
    assert counts == {"IN_SCOPE": 92, "AMBIGUOUS": 6, "OUT_OF_SCOPE": 2}, counts
    assert not any(r["duplicate_family"] for r in rows)

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
    print(f"{len(changes)} changes; status {dict(counts)}")
    by = Counter((r["source_stratum"], r["screen_status"]) for r in rows)
    for s in ("official", "research", "elicited", "community"):
        print(s, {k: by[(s, k)] for k in ("IN_SCOPE", "AMBIGUOUS", "OUT_OF_SCOPE")})


if __name__ == "__main__":
    main()
