"""Apply the 2026-09-13 provenance-audit corrections to corpus_100.csv and screening_log_150.csv.

python audit/apply_audit_fixes.py      (run from breadth/; idempotent)

Only provenance fields are corrected: source_title, source_locator, accessed_date (seeds),
source_verification, and one incomplete community normalization (E1-099). Screening status,
source_stratum, provenance_type and every R/B field are NOT touched — those are coding decisions
that remain pre-audit. Every change is written to audit/changes_2026-09-13.csv with before/after.
Evidence for each rule is in audit/PROVENANCE_AUDIT.md.
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BREADTH = HERE.parent
sys.path.insert(0, str(BREADTH.parent))
from cases import CASES  # noqa: E402  (Stage A source records, read-only)

AUDIT_DATE = "2026-09-13"
CORPUS = BREADTH / "corpus_100.csv"
SCREEN = BREADTH / "screening_log_150.csv"

# Seed rows carried the Stage A case id as their locator. These are the real locators.
SEED_LOCATOR = {
    "C01": "blueprint.description; input.no_motion_wait.description; mode; actions",
    "C03": "§V-D, extended-action violation example, applet r_i",
    "C04": "§V-D, extended-action violation example, applet r_j",
    "C05": "opening post (created 2023-01-17 UTC)",
    "C07": "opening post (created 2024-10-18 UTC)",
    "C09": ("§III template (g) Event-Event Conditional sample response; same statement in "
            "User Study 1 data, Result sheet, Excel row 16, column AM (header 1_Q25, statement 1)"),
    "C11": "§VI-A Task 11, with the authors' rule explanation",
    "C15": "Results, trigger/action structure paragraph ('one participant specified')",
    "C16": "Table 1, Task I",
    "C18": "Table 5, Q3",
    "C19": "Table 4, P3",
    "C20-O": ("Table 1, Event-Event paradigm, second example "
              "(full text: https://par.nsf.gov/servlets/purl/10106413)"),
}

# source_title for community rows: real thread title (the pre-audit value appended a researcher label).
THREAD = {
    "E1-004": ("520305", "How to set notifications when door is left open?", "2023-01-17"),
    "E1-005": ("783900", "How to automate open door notifications?", "2024-10-18"),
    "E1-078": ("995590", "Combination of motion and illuminance sensor to control light bulb", "2026-03-14"),
    "E1-079": ("864628", "Trigger automation every minute, unless it has been triggered by something else", "2025-03-16"),
    "E1-080": ("408113", "Automation - Arm Alarm when everyone is away?", "2022-04-03"),
    "E1-081": ("721406", "How to reliably design making an announcement every 5 mins until a binary sensor is OFF", "2024-04-24"),
    "E1-082": ("600389", "Help with Door Close Automation", "2023-08-07"),
    "E1-083": ("958200", 'Delayed entity, AKA "turn this on for X minutes"', "2025-12-03"),
    "E1-084": ("566330", "Automation to turn ON/OFF devices at different times/days", "2023-05-01"),
    "E1-085": ("485629", "How to trigger an automation based on temperature hysteresis", "2022-11-07"),
    "E1-086": ("878961", "Stop an automation mid-run via an input boolean?", "2025-04-17"),
    "E1-087": ("367362", "Understanding automations with time delays and how to control them", "2021-12-15"),
    "E1-088": ("712624", "How to enable an automation between times", "2024-04-03"),
    "E1-089": ("302465", "Evolution of an automation. Turn a light on/off at sunset/sunrise", "2021-04-24"),
    "E1-090": ("670621", "Turn something on for a set time", "2024-01-10"),
    "E1-091": ("987759", "Automation to run every 5 minutes", "2026-02-17"),
    "E1-092": ("955561", "Running groups of actions in Parallel", "2025-11-26"),
    "E1-093": ("555703", "[solved] Automation w/ 3 actions (notification scripts): how to make them run in parallel?", "2023-04-03"),
    "E1-094": ("585191", "Trying to create action in parallel with delays for certain actions that need to occur sequentially", "2023-06-24"),
    "E1-095": ("654561", "Getting an average reading of a sensor during certain hours", "2023-12-12"),
    "E1-096": ("653754", "🪫 Low Battery Notifications & Actions", "2023-12-11"),
    "E1-097": ("892319", "🔔 Smart Doorbell Button (Zigbee) with Sound, Lights, Notifications & Presence Awareness", "2025-05-19"),
    "E1-098": ("1024799", "Simple Washing Machine Finished Notification – power sensor + helper, beginner friendly", "2026-09-12"),
    "E1-099": ("729908", "Need help with light automation", "2024-05-16"),
    "E1-100": ("641504", "Automation that triggers when all residents are not home", "2023-11-16"),
}

# Google Home section names that the pre-audit file had paraphrased.
GOOGLE_SECTION = {
    "E1-074": ("Section: When I walk through my corridor first time (motion sensor) in the morning "
               "open all my blinds and suppress the trigger for 20 hours"),
    "E1-075": "Section: Send a notification when movement is detected at home on a weekday",
}

# The opening post states two off conditions; the pre-audit normalization kept only one.
E1_099_BEFORE = ("A manually switched-on light stays on at least 5 minutes; "
                 "each motion event extends the on time by 2 minutes.")
E1_099_AFTER = (E1_099_BEFORE[:-1] + "; the light is turned off only when no motion has been "
                "detected for 2 minutes.")

AUTOTAP = json.loads((HERE / "autotap_locators.json").read_text())


def autotap_locator(m):
    n = m["header"].split("_")[0]
    return f"Result sheet, Excel row {m['excel_row']}, column {m['column']} (header {m['header']}, statement {n})"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def write(path, fields, rows):
    eol = "\r\n" if b"\r\n" in path.read_bytes()[:4096] else "\n"   # keep each file's own line ending
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator=eol)
        w.writeheader()
        w.writerows(rows)


def main():
    changes = []

    def setf(fname, rid, row, field, value, reason):
        if row[field] != value:
            changes.append({"file": fname, "id": rid, "field": field,
                            "before": row[field], "after": value, "reason": reason})
            row[field] = value

    repo = {c["id"]: c for c in CASES}
    cfields, corpus = read(CORPUS)
    for r in corpus:
        cid, before = r["corpus_id"], len(changes)
        if r["cohort"] == "seed":
            pid = r["prior_case_id"]
            setf("corpus_100.csv", cid, r, "source_locator", SEED_LOCATOR[pid],
                 "seed locator held the Stage A case id, not a location in the source")
            setf("corpus_100.csv", cid, r, "accessed_date", repo[pid]["accessed"],
                 "Stage A source record (cases.py) gives the original access date")
        if cid in THREAD:
            tid, title, created = THREAD[cid]
            setf("corpus_100.csv", cid, r, "source_title", f"Home Assistant Community thread {tid}: {title}",
                 "title after the colon was a researcher label, not the thread title")
            if r["cohort"] == "new":
                setf("corpus_100.csv", cid, r, "source_locator", f"opening post (created {created} UTC)",
                     "add opening-post creation date from the thread JSON")
        if cid in GOOGLE_SECTION:
            reason = "pre-audit section name does not exist on the page; replaced with the actual heading"
            setf("corpus_100.csv", cid, r, "source_locator", GOOGLE_SECTION[cid], reason)
            setf("corpus_100.csv", cid, r, "source_title",
                 "Google Home example scripted automations — " + GOOGLE_SECTION[cid].removeprefix("Section: "), reason)
        if cid in AUTOTAP:
            setf("corpus_100.csv", cid, r, "source_locator", autotap_locator(AUTOTAP[cid]),
                 "'participant Pnn' equalled Excel row minus 2 for all 73 AutoTap rows, not a participant id")
        if cid == "E1-099" and r["original_text"] == E1_099_BEFORE:
            setf("corpus_100.csv", cid, r, "original_text", E1_099_AFTER,
                 "opening post also requires 'No motion detected by motion sensor for 2 minutes'")
        if not r["source_verification"].startswith("SERVER_CHECKED"):   # already applied on a rerun
            status = f"SERVER_CHECKED_{AUDIT_DATE}" + ("; CORRECTED" if len(changes) > before else "")
            setf("corpus_100.csv", cid, r, "source_verification", status,
                 "pre-audit value was GPT-side; replaced by the server-side check result")

    by_id = {r["corpus_id"]: r for r in corpus}
    sfields, screen = read(SCREEN)
    for s in screen:
        sid = s["candidate_id"]
        if s["decision"] == "RETAIN":
            src = by_id[s["final_corpus_id"]]
            for k in ("source_url", "source_locator", "original_text"):
                setf("screening_log_150.csv", sid, s, k, src[k], "keep retained log row identical to corpus row")
        elif sid in AUTOTAP:
            setf("screening_log_150.csv", sid, s, "source_locator", autotap_locator(AUTOTAP[sid]),
                 "'participant Pnn' equalled Excel row minus 2, not a participant id")

    write(CORPUS, cfields, corpus)
    write(SCREEN, sfields, screen)
    log = HERE / f"changes_{AUDIT_DATE}.csv"
    if changes:
        with log.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["file", "id", "field", "before", "after", "reason"])
            w.writeheader()
            w.writerows(changes)
    by_field = {}
    for c in changes:
        by_field[(c["file"], c["field"])] = by_field.get((c["file"], c["field"]), 0) + 1
    for k, v in sorted(by_field.items()):
        print(f"{k[0]:24} {k[1]:20} {v}")
    print(f"-> {log.name}: {len(changes)} changes")


if __name__ == "__main__":
    main()
