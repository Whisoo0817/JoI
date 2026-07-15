#!/usr/bin/env python3
"""Extract the REAL NL->IR error distribution to ground the RQ1 injected-fault set.

For each dataset row we have a generated IR (NL->IR pipeline output, read from an
existing e2e run's intermediate dump) and the ground-truth IR (`ir_gt`). A naive
structural diff over-counts errors because many generated IRs are *behaviorally
equivalent* idiom variants of the GT (label noise / multiplicity). So we decide
"is this a REAL error" BEHAVIORALLY: synthesize boundary scenarios from `ir_gt`,
run BOTH the generated IR and `ir_gt` through the IR simulator, and compare the
action traces. Behaviorally-divergent rows are the real NL->IR errors; we then
classify the STRUCTURAL difference into a fault class (mapped to the RQ1 taxonomy)
to obtain the error distribution (class -> count + example rows).

Equivalent (idiom-variant) rows are reported separately (they are NOT faults).

Run (CPU only, no LLM):
  PYTHONPATH=/home/gnltnwjstk/joi python3 paper/extract_nl2ir_errors.py \
      --gen-dir experiments/e2e_382/20260528_150445__d886015/intermediate/off \
      --out paper/Final/evaluation/results/nl2ir_error_distribution.json
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from paper.run_mutation_test import load_meta
from paper.simulators.catalog import load_catalog
from paper.simulators.event_synth import synthesize_scenarios
from paper.simulators.ir_simulator import run_ir_simulation
from paper.simulators.comparator import _group_and_dedup


# ── behavioral signature ──────────────────────────────────────────────────────
def trace_sig(ir, scenarios, cat):
    """Ordered per-scenario action signature, or None if the sim crashes."""
    out = []
    for scn in scenarios:
        try:
            t = run_ir_simulation(ir, scn, cat, debug=False)
        except Exception:
            return None
        groups = _group_and_dedup(t.records)
        seq = tuple(tuple(sorted(str(rec.key()) for rec in g["records"])) for g in groups)
        out.append(seq)
    return tuple(out)


def behaviorally_equivalent(gen_ir, gt_ir, cat):
    """(equiv: bool|None, reason). None = couldn't decide (gen sim crash)."""
    if not isinstance(gen_ir, dict) or not gen_ir.get("timeline"):
        return False, "gen_invalid_or_empty"
    try:
        scenarios = synthesize_scenarios(gt_ir)
    except Exception:
        scenarios = []
    if not scenarios:
        return None, "no_scenarios"
    gt_sig = trace_sig(gt_ir, scenarios, cat)
    gen_sig = trace_sig(gen_ir, scenarios, cat)
    if gt_sig is None:
        return None, "gt_sim_crash"
    if gen_sig is None:
        return False, "gen_sim_crash"
    return (gt_sig == gen_sig), ("equiv" if gt_sig == gen_sig else "trace_divergent")


# ── structural feature extraction (for classifying the divergence) ────────────
def _walk(timeline):
    """Yield every op dict, descending into if branches and cycle bodies."""
    for step in timeline or []:
        if not isinstance(step, dict):
            continue
        yield step
        for key in ("then", "else", "body", "do"):
            sub = step.get(key)
            if isinstance(sub, list):
                yield from _walk(sub)


def features(ir):
    if not isinstance(ir, dict):
        return None
    tl = ir.get("timeline", [])
    calls, gates, delays, crons = [], [], [], []
    has_cycle = has_break = False
    for s in _walk(tl):
        op = s.get("op")
        if op == "call":
            calls.append((s.get("target"), json.dumps(s.get("args"), sort_keys=True, default=str)))
        elif op in ("wait", "if"):
            cond = s.get("cond")
            cs = cond if isinstance(cond, str) else json.dumps(cond, sort_keys=True, default=str)
            n_and = cs.count(" and ")
            n_or = cs.count(" or ")
            # op=="if" => one-shot check (evaluate now); op=="wait" => wait-until (block).
            # edge "rising" => event-trigger; "none" => level/until.
            gates.append({"op": op, "edge": s.get("edge"), "cond": cs,
                          "clauses": 1 + n_and + n_or, "has_and": n_and > 0})
            if op == "wait" and s.get("for") is not None:
                delays.append(("wait.for", s.get("for")))
            if op == "wait" and s.get("cron"):
                crons.append(s.get("cron"))
        elif op == "delay":
            delays.append(("delay", s.get("duration", s.get("ms", s.get("seconds")))))
        elif op == "cycle":
            has_cycle = True            # cycle => recurring "whenever / every time"
            if s.get("period"):
                delays.append(("cycle.period", s.get("period")))
        elif op == "break":
            has_break = True
        elif op == "start_at":
            if s.get("cron"):
                crons.append(s.get("cron"))
    return {
        "calls": calls, "targets": [c[0] for c in calls], "n_calls": len(calls),
        "gates": gates, "gate_types": set(g["op"] for g in gates),
        "n_gates": len(gates), "max_clauses": max([g["clauses"] for g in gates], default=0),
        "conds": sorted(g["cond"] for g in gates),
        "has_cycle": has_cycle, "has_break": has_break,
        "delays": delays, "crons": crons,
    }


def classify(gen_ir, gt_ir, reason):
    """Return a list of fault-class labels for a behaviorally-divergent row."""
    if reason == "gen_invalid_or_empty":
        return ["INVALID_OR_EMPTY_IR"]
    if reason == "gen_sim_crash":
        return ["INVALID_IR_SIM_CRASH"]
    fg, ft = features(gen_ir), features(gt_ir)
    if fg is None or ft is None:
        return ["UNCLASSIFIED"]
    labels = []
    # ── reactive-mode confusions (user-reported, the high-value RQ1 classes) ──
    # one-shot check (if) <-> wait-until (wait) swap, same recurrence
    if fg["gate_types"] != ft["gate_types"] and ({"if", "wait"} & fg["gate_types"]) \
            and ({"if", "wait"} & ft["gate_types"]) and fg["has_cycle"] == ft["has_cycle"]:
        labels.append("ONESHOT_CHECK_vs_WAITUNTIL")
    # single (no cycle) <-> recurring "whenever/every time" (cycle)
    if fg["has_cycle"] != ft["has_cycle"]:
        labels.append("SINGLE_vs_RECURRING_WHENEVER")
    # AND-conjunction collapsed into sequential gates (and reverse)
    if ft["max_clauses"] >= 2 and fg["max_clauses"] <= 1 and fg["n_gates"] > ft["n_gates"]:
        labels.append("AND_collapsed_to_SEQUENTIAL")
    if fg["max_clauses"] >= 2 and ft["max_clauses"] <= 1 and ft["n_gates"] > fg["n_gates"]:
        labels.append("SEQUENTIAL_merged_to_AND")
    mode_hit = any(L in labels for L in
                   ("ONESHOT_CHECK_vs_WAITUNTIL", "AND_collapsed_to_SEQUENTIAL",
                    "SEQUENTIAL_merged_to_AND"))
    # ── action / target / value ──
    if fg["n_calls"] < ft["n_calls"]:
        labels.append("MISSING_ACTION")            # Under-Automation
    if fg["n_calls"] > ft["n_calls"]:
        labels.append("EXTRA_ACTION")              # Over-Automation
    gt_tn = sorted(str(t).split(".")[0] if t else t for t in ft["targets"])
    gn_tn = sorted(str(t).split(".")[0] if t else t for t in fg["targets"])
    if gn_tn != gt_tn and fg["n_calls"] == ft["n_calls"]:
        labels.append("WRONG_DEVICE_TARGET")
    elif fg["n_calls"] == ft["n_calls"]:
        if sorted(t for t, _ in fg["calls"]) != sorted(t for t, _ in ft["calls"]):
            labels.append("WRONG_METHOD")
        elif sorted(a for _, a in fg["calls"]) != sorted(a for _, a in ft["calls"]):
            labels.append("WRONG_ARG_VALUE")
    # ── condition / timing / schedule (condition only if not mode-explained) ──
    if fg["conds"] != ft["conds"] and not mode_hit:
        labels.append("WRONG_CONDITION")
    if sorted(map(str, fg["delays"])) != sorted(map(str, ft["delays"])):
        labels.append("WRONG_TIMING_DURATION")
    if sorted(fg["crons"]) != sorted(ft["crons"]):
        labels.append("WRONG_SCHEDULE")
    if not labels:
        labels.append("OTHER_BEHAVIORAL")
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-dir", default="experiments/e2e_382/20260528_150445__d886015/intermediate/off")
    ap.add_argument("--out", default="paper/Final/evaluation/results/nl2ir_error_distribution.json")
    a = ap.parse_args()
    gen_dir = os.path.join(ROOT, a.gen_dir) if not os.path.isabs(a.gen_dir) else a.gen_dir

    meta = load_meta()
    cat = load_catalog()

    n_total = n_missing_gen = n_equiv = n_error = n_undecided = 0
    class_counts = Counter()
    class_examples = defaultdict(list)
    by_cat_error = Counter()
    rows = []

    for name, m in sorted(meta.items()):
        gt_ir = m["ir_gt"]
        if not isinstance(gt_ir, dict):
            continue
        n_total += 1
        gpath = os.path.join(gen_dir, f"{name}.json")
        if not os.path.exists(gpath):
            n_missing_gen += 1
            continue
        try:
            gen_ir = json.load(open(gpath, encoding="utf-8")).get("ir")
        except Exception:
            gen_ir = None
        equiv, reason = behaviorally_equivalent(gen_ir, gt_ir, cat)  # cat = catalog dict
        rec = {"name": name, "cat": m["cat"], "reason": reason}
        if equiv is None:
            n_undecided += 1
            rec["verdict"] = "undecided"
        elif equiv:
            n_equiv += 1
            rec["verdict"] = "equivalent"
        else:
            n_error += 1
            labels = classify(gen_ir, gt_ir, reason)
            rec["verdict"] = "error"
            rec["labels"] = labels
            by_cat_error[m["cat"]] += 1
            for L in labels:
                class_counts[L] += 1
                if len(class_examples[L]) < 8:
                    class_examples[L].append(name)
        rows.append(rec)

    summary = {
        "gen_dir": a.gen_dir,
        "n_total_rows": n_total,
        "n_missing_gen": n_missing_gen,
        "n_behaviorally_equivalent": n_equiv,       # idiom variants, NOT faults
        "n_real_errors": n_error,
        "n_undecided": n_undecided,
        "real_error_rate": round(n_error / max(1, n_total - n_missing_gen), 4),
        "fault_class_counts": dict(class_counts.most_common()),
        "fault_class_examples": {k: class_examples[k] for k in class_counts},
        "errors_by_category": dict(by_cat_error.most_common()),
        "rows": rows,
    }
    outp = os.path.join(ROOT, a.out) if not os.path.isabs(a.out) else a.out
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump(summary, open(outp, "w"), indent=1, ensure_ascii=False)

    print("=" * 64)
    print(f"rows={n_total} (gen missing {n_missing_gen}) | equivalent(idiom)={n_equiv} "
          f"| REAL errors={n_error} | undecided={n_undecided}")
    print(f"real-error rate = {summary['real_error_rate']:.1%} of rows with a gen IR")
    print("\nFAULT CLASS distribution (multi-label; real errors only):")
    for k, v in class_counts.most_common():
        print(f"  {v:3d}  {k:24s}  e.g. {', '.join(class_examples[k][:5])}")
    print(f"\n-> {a.out}")


if __name__ == "__main__":
    main()
