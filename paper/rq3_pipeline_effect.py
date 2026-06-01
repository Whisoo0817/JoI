#!/usr/bin/env python3
"""RQ3 -- effect of the verifier in the deployment pipeline (single clean config).

CONFIG (one only, no mixing of gt_ir vs generated-IR): the confirmed IR (= gt_ir
as the confirmed oracle) is lowered to JoI; the deterministic LLM-free verifier
checks JoI <-> IR (trace-equivalence); on a flag, self-correction repairs, else
the candidate is REJECTED (fail-closed, NOT deployed).

We re-aggregate the existing Stage-B run from its per-row intermediate outputs
using ONE consistent behavioral oracle (l2_runtime.check on the FINAL JoI), so
that deployed-correct / silent-wrong / repaired / rejected add up exactly. (The
old _summary.json mixed an attempt-1 detector judgment with a final-JoI grade,
giving a 2-row TP=37 vs OFF-fail=35 discrepancy -- reconciled here.)

Per row we read:
  off/<name>.json : raw JoI (verifier off)
  on/<name>.json  : final JoI + verifier_trace {accepted, n_attempts, attempts[]}

Buckets (verifier ON):
  off_ok            : raw JoI already behaviorally == IR  (verifier not needed)
  repaired          : off wrong -> verifier flagged -> self-correct -> deployed correct
  rejected          : off wrong -> verifier flagged -> self-correct failed -> REJECTED
  silent_wrong_on   : DEPLOYED (accepted) but behaviorally != IR  <-- must be 0 (headline)
  over_reject       : off correct but verifier rejected it (fail-closed FP cost)

Headline: silent-wrong DEPLOYED  OFF (N_off_wrong) -> ON (silent_wrong_on, =0).

Also analyzes the REJECTED-to-the-end cases: per-row category, final + per-attempt
violation kinds, attempt count, to root-cause why self-correction could not fix
them (for prompt strengthening or honest paper explanation).

Run (no LLM, fast):
  PYTHONPATH=/home/gnltnwjstk/joi python3 paper/rq3_pipeline_effect.py
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CSV_PATH = os.path.join(ROOT, "dataset.csv")

# IMPORTANT: we do NOT re-run l2_check here. The verifier/sim code has evolved
# since this run was produced (d886015), so re-grading with current code would
# DISAGREE with the accept/reject decisions the pipeline actually made. We report
# RUN-TIME TRUTH only: the per-row pass/fail verdicts stored in _summary.json
# (graded by the verifier AS OF the run) plus each on-file's verifier_trace
# (accepted flag + per-attempt flagged kinds, recorded at run time).


def load_commands():
    cmd = {}
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            c, idx = (r.get("category_v2") or "").strip(), (r.get("index") or "").strip()
            if c and idx:
                cmd[f"{c}_{idx}"] = (r.get("command_eng") or r.get("command_kor") or "").strip()
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir",
                    default="experiments/stageB_382/20260528_170116__d886015")
    ap.add_argument("--out",
                    default="paper/Final/evaluation/results/rq3_pipeline_effect.json")
    a = ap.parse_args()
    inter = os.path.join(ROOT, a.run_dir, "intermediate")
    on_dir = os.path.join(inter, "on")
    summ = json.load(open(os.path.join(inter, "_summary.json"), encoding="utf-8"))
    grades = summ["grades"]            # {"off":{name:{verdict,msg}}, "on":{...}}
    commands = load_commands()

    def verdict_ok(g):                 # run-time grade -> behavioral correctness
        v = g.get("verdict")
        if v == "pass":
            return True
        if v in ("fail", "error"):     # error = lowering produced no usable JoI
            return False
        return None                    # missing / no_gt -> excluded

    rows = []
    skipped = []
    for name in sorted(grades["off"]):
        cat = name.rsplit("_", 1)[0]
        off_g = grades["off"].get(name, {})
        on_g = grades["on"].get(name, {})
        off_ok = verdict_ok(off_g)
        on_ok = verdict_ok(on_g)
        if off_ok is None or on_ok is None:
            skipped.append(name)
            continue
        # verifier_trace (run-time): accepted flag + per-attempt flagged kinds
        vt = {}
        on_p = os.path.join(on_dir, f"{name}.json")
        if os.path.exists(on_p):
            vt = (json.load(open(on_p, encoding="utf-8")).get("verifier_trace") or {})
        accepted = bool(vt.get("accepted")) if vt.get("enabled") else None
        n_attempts = vt.get("n_attempts")
        attempts = vt.get("attempts") or []
        attempt_kinds = [sorted(set((at.get("l1_kinds") or []) + (at.get("l2_kinds") or [])))
                         for at in attempts]
        # final flagged kinds = last attempt's kinds (run-time verifier view)
        final_kinds = attempt_kinds[-1] if attempt_kinds else []

        rows.append({
            "name": name, "cat": cat, "command": commands.get(name, ""),
            "off_verdict": off_g.get("verdict"), "on_verdict": on_g.get("verdict"),
            "off_ok": off_ok, "on_ok": on_ok,
            "accepted": accepted, "n_attempts": n_attempts,
            "attempt_kinds": attempt_kinds,
            "final_violation_kinds": final_kinds,
            "off_msg": off_g.get("msg", "")[:200],
        })

    # ── classify into clean buckets ──
    off_ok = [r for r in rows if r["off_ok"] is True]
    off_wrong = [r for r in rows if r["off_ok"] is False]
    # ON outcome
    repaired, rejected, silent_wrong_on, over_reject, anomalies = [], [], [], [], []
    for r in rows:
        acc, on_ok = r["accepted"], r["on_ok"]
        if acc is True and on_ok is True:
            if r["off_ok"] is False:
                repaired.append(r)            # was wrong -> deployed correct
            # if off_ok was also True -> verifier correctly passed it (no action)
        elif acc is True and on_ok is False:
            silent_wrong_on.append(r)         # DEPLOYED WRONG -- must be 0
        elif acc is False:
            rejected.append(r)                # fail-closed, not deployed
            if r["off_ok"] is True:
                over_reject.append(r)         # rejected a correct candidate (FP cost)
        else:
            anomalies.append(r)

    n = len(rows)
    n_off_wrong = len(off_wrong)
    deployed_correct_off = len(off_ok)        # what OFF would silently deploy correct
    silent_wrong_off = n_off_wrong            # OFF deploys these wrong, silently
    # ON partitions all n rows into exactly: deployed-correct + rejected + leak.
    deployed_correct_on = sum(1 for r in rows if r["accepted"] is True and r["on_ok"] is True)
    assert deployed_correct_on + len(rejected) + len(silent_wrong_on) + len(anomalies) == n, \
        (deployed_correct_on, len(rejected), len(silent_wrong_on), len(anomalies), n)

    summary = {
        "config": "confirmed-IR (=gt_ir) -> JoI -> verifier(L1/L2) -> self-correct/reject; "
                  "single clean config, no generated-IR mixing. RUN-TIME grades (d886015), "
                  "no re-grading with current code.",
        "n_rows_scored": n, "skipped": skipped,
        "OFF": {
            "deployed_correct": deployed_correct_off,
            "deployed_correct_pct": round(100 * deployed_correct_off / n, 2),
            "silent_wrong_deployed": silent_wrong_off,
            "silent_wrong_pct": round(100 * silent_wrong_off / n, 2),
        },
        "ON": {
            "deployed_correct": deployed_correct_on,
            "deployed_correct_pct": round(100 * deployed_correct_on / n, 2),
            "repaired_from_off_wrong": len(repaired),
            "rejected_fail_closed": len(rejected),
            "over_rejected_correct": len(over_reject),
            "silent_wrong_deployed": len(silent_wrong_on),   # headline: expect 0 (fail-closed)
            "silent_wrong_pct": round(100 * len(silent_wrong_on) / n, 2),
        },
        "headline": f"silent-wrong deployed: OFF {silent_wrong_off}/{n} "
                    f"({100*silent_wrong_off/n:.1f}%) -> ON {len(silent_wrong_on)}/{n} "
                    f"({100*len(silent_wrong_on)/n:.1f}%). Deployed-correct {deployed_correct_off}"
                    f"->{deployed_correct_on} (+{deployed_correct_on-deployed_correct_off}). "
                    f"Of the {n_off_wrong} silent-wrong OFF candidates: {len(repaired)} repaired, "
                    f"{n_off_wrong-len(repaired)} rejected (fail-closed); cost {len(over_reject)} "
                    f"correct candidates over-rejected.",
        "anomalies": [r["name"] for r in anomalies],
        "silent_wrong_on_names": [r["name"] for r in silent_wrong_on],
    }

    # ── reject root-cause analysis ──
    rej_by_cat = Counter(r["cat"] for r in rejected)
    rej_final_kind = Counter()
    for r in rejected:
        for k in (r["final_violation_kinds"] or ["<accepted-but-rejected?>"]):
            rej_final_kind[k] += 1
    # did the repair loop hit its attempt ceiling? did flagged kinds persist/oscillate?
    rej_attempt_hist = Counter(r["n_attempts"] for r in rejected)
    rej_detail = []
    for r in sorted(rejected, key=lambda x: x["name"]):
        # persistence: kinds present in EVERY attempt (never resolved)
        ak = r["attempt_kinds"]
        persistent = sorted(set.intersection(*[set(x) for x in ak])) if ak else []
        rej_detail.append({
            "name": r["name"], "cat": r["cat"], "command": r["command"],
            "n_attempts": r["n_attempts"],
            "final_violation_kinds": r["final_violation_kinds"],
            "persistent_kinds": persistent,
            "attempt_kinds": ak,
            "off_was_wrong": r["off_ok"] is False,
        })

    summary["reject_analysis"] = {
        "n_rejected": len(rejected),
        "by_category": dict(rej_by_cat.most_common()),
        "by_final_violation_kind": dict(rej_final_kind.most_common()),
        "by_n_attempts": dict(sorted(rej_attempt_hist.items())),
        "over_rejected_correct_candidates": [r["name"] for r in over_reject],
        "detail": rej_detail,
    }

    outp = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump({"summary": summary, "rows": rows}, open(outp, "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    # ── console report ──
    print("=" * 72)
    print("RQ3  pipeline effect  (confirmed-IR -> JoI -> verifier -> self-correct/reject)")
    print("=" * 72)
    print(f"rows scored: {n}   (skipped: {len(skipped)})")
    print(f"\nverifier OFF:  deployed-correct {deployed_correct_off}/{n} "
          f"({100*deployed_correct_off/n:.1f}%)   "
          f"SILENT-WRONG deployed {silent_wrong_off}/{n} ({100*silent_wrong_off/n:.1f}%)")
    print(f"verifier ON :  deployed-correct {deployed_correct_on}/{n} "
          f"({100*deployed_correct_on/n:.1f}%)   "
          f"SILENT-WRONG deployed {len(silent_wrong_on)}/{n} ({100*len(silent_wrong_on)/n:.1f}%)"
          f"   rejected(fail-closed) {len(rejected)}/{n} ({100*len(rejected)/n:.1f}%)")
    print(f"\nof the {n_off_wrong} silent-wrong-OFF candidates the verifier caught:")
    print(f"   repaired (self-correct -> deployed correct) : {len(repaired)}")
    print(f"   rejected (fail-closed, not deployed)        : {n_off_wrong-len(repaired)}")
    print(f"   silent-wrong DEPLOYED (LEAK)         : {len(silent_wrong_on)}  <-- headline=0")
    print(f"   over-rejected correct candidates (FP): {len(over_reject)}  {[r['name'] for r in over_reject]}")
    if anomalies:
        print(f"   ANOMALIES (need inspection)          : {[r['name'] for r in anomalies]}")

    print("\n" + "-" * 72)
    print(f"REJECT ROOT-CAUSE  (n={len(rejected)} fail-closed)")
    print("-" * 72)
    print("by category        :", dict(rej_by_cat.most_common()))
    print("by final violation :", dict(rej_final_kind.most_common()))
    print("by #repair attempts:", dict(sorted(rej_attempt_hist.items())))
    print("\nper-row (persistent = kind flagged in EVERY attempt = self-correct never resolved):")
    for d in rej_detail:
        print(f"  {d['name']:<9} {d['cat']:<5} att={d['n_attempts']}  "
              f"final={d['final_violation_kinds']}  persist={d['persistent_kinds']}")
        if d["command"]:
            print(f"            cmd: {d['command'][:90]}")
    print(f"\n-> {a.out}")


if __name__ == "__main__":
    main()
