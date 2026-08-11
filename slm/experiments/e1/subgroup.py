# -*- coding: utf-8 -*-
"""Subgroup analysis of E1 results: where (if anywhere) does clause-splitting pay?"""
import json, os, sys, random

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results.json")))
ITEMS = {i["index"]: i for i in json.load(open(os.path.join(HERE, "items_final.json")))}
rows = R["items"]
ARMS = ["batch", "marked", "marked_merged", "interleave", "interleave_merged"]
M = ["fact_recall", "omission", "distortion", "op_recall", "valid_json"]


def get(r, arm, m):
    a = r.get("arms", {}).get(arm) or {}
    v = ((a.get("metrics") or {}).get(m) if m != "valid_json" else a.get("valid"))
    return None if v is None else float(v)


def boot(deltas, n=10000, seed=0):
    if not deltas:
        return (float("nan"),) * 2
    rnd = random.Random(seed)
    k = len(deltas)
    ms = sorted(sum(deltas[rnd.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return ms[int(.025 * n)], ms[int(.975 * n)]


def table(sub, name):
    if not sub:
        print("\n### %s — empty" % name); return
    print("\n### %s   (n=%d)" % (name, len(sub)))
    print("%-18s %8s %8s %8s %8s %8s" % ("arm", "fact_rec", "omiss", "distort", "op_rec", "valid%"))
    for arm in ARMS:
        vals = {m: [get(r, arm, m) for r in sub] for m in M}
        vals = {m: [v for v in vs if v is not None] for m, vs in vals.items()}
        if not vals["fact_recall"]:
            continue
        mean = lambda xs: sum(xs) / len(xs)
        print("%-18s %8.3f %8.3f %8.3f %8.3f %8.1f" % (
            arm, mean(vals["fact_recall"]), mean(vals["omission"]), mean(vals["distortion"]),
            mean(vals["op_recall"]), 100 * mean(vals["valid_json"])))
    for arm in ARMS[1:]:
        d = [get(r, arm, "fact_recall") - get(r, "batch", "fact_recall") for r in sub
             if get(r, arm, "fact_recall") is not None and get(r, "batch", "fact_recall") is not None]
        if not d:
            continue
        lo, hi = boot(d)
        w = sum(1 for x in d if x > 1e-9); l = sum(1 for x in d if x < -1e-9)
        print("   %-18s vs batch  fact_recall %+0.4f  CI[%+0.3f,%+0.3f]  win/loss %d/%d"
              % (arm, sum(d) / len(d), lo, hi, w, l))


# --- subgroups -------------------------------------------------------------
merged_changed = {i["index"] for i in ITEMS.values()
                  if i.get("clauses_merged") != i.get("clauses")}

table(rows, "ALL")
table([r for r in rows if get(r, "batch", "valid_json") == 1.0],
      "batch produced valid JSON (removes the format-failure confound)")
table([r for r in rows if ITEMS[r["idx"]]["n_ops"] >= 5], "hard items: gold n_ops >= 5")
table([r for r in rows if ITEMS[r["idx"]]["n_ops"] == 4], "easy items: gold n_ops == 4")
table([r for r in rows if len(ITEMS[r["idx"]]["clauses"]) >= 4], "clauses >= 4")
table([r for r in rows if len(ITEMS[r["idx"]]["clauses"]) <= 2], "clauses <= 2")
table([r for r in rows if r["idx"] in merged_changed],
      "the 9 items where condition-chain merging fired")

# --- per-turn degradation inside the interleave arm ------------------------
print("\n\n### interleave: per-turn parse failures and state growth")
tot_turns = fails = 0
by_turn = {}
for r in rows:
    a = r.get("arms", {}).get("interleave") or {}
    for c in a.get("calls", []):
        t = c.get("tag", "")
        tot_turns += 1
        ok = c.get("parsed_ok", True)
        d = by_turn.setdefault(t, [0, 0])
        d[0] += 1
        if not ok:
            d[1] += 1; fails += 1
print("turns=%d  parse_failures=%d (%.1f%%)" % (tot_turns, fails, 100 * fails / max(tot_turns, 1)))
for t in sorted(by_turn):
    n, f = by_turn[t]
    print("  %-8s n=%3d  fail=%3d (%.0f%%)" % (t, n, f, 100 * f / n))

# --- what does interleave get right that batch drops? ----------------------
print("\n\n### items where interleave beat batch by >= 0.2 fact_recall")
n = 0
for r in rows:
    b, i_ = get(r, "batch", "fact_recall"), get(r, "interleave", "fact_recall")
    if b is None or i_ is None or i_ - b < 0.2 or n >= 5:
        continue
    n += 1
    it = ITEMS[r["idx"]]
    print("\n cmd    : %s" % it["cmd"])
    print(" clauses: %s" % " | ".join(it["clauses"]))
    print(" gold ops : %s" % r.get("gt_ops"))
    print(" batch    : fr=%.2f ops=%s" % (b, (r["arms"]["batch"] or {}).get("pred_ops")))
    print(" interlv  : fr=%.2f ops=%s" % (i_, (r["arms"]["interleave"] or {}).get("pred_ops")))

print("\n\n### items where batch beat interleave by >= 0.2 fact_recall")
n = 0
for r in rows:
    b, i_ = get(r, "batch", "fact_recall"), get(r, "interleave", "fact_recall")
    if b is None or i_ is None or b - i_ < 0.2 or n >= 5:
        continue
    n += 1
    it = ITEMS[r["idx"]]
    print("\n cmd    : %s" % it["cmd"])
    print(" clauses: %s" % " | ".join(it["clauses"]))
    print(" gold ops : %s" % r.get("gt_ops"))
    print(" batch    : fr=%.2f ops=%s" % (b, (r["arms"]["batch"] or {}).get("pred_ops")))
    print(" interlv  : fr=%.2f ops=%s" % (i_, (r["arms"]["interleave"] or {}).get("pred_ops")))
