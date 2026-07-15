#!/usr/bin/env python3
"""Faithfulness-surfacing measurement (RQ1 human-free substitute, THIS ROUND).

CLAIM under test: the DETERMINISTIC IR->NL renderer is a *faithful confirmation
surface* -- whenever the IR carries a fault (differs from the intended IR), the
rendered plain text differs too, so the fault is LEGIBLE to whoever confirms.
The meaningful failure mode is a BLIND SPOT: two semantically-different IRs that
render to identical text (the fault is hidden). Faithfulness ⇔ ~no blind spots.

This is a property of the renderer (no humans, no LLM). It establishes the
NECESSARY condition for confirmation ("the fault is on the surface"); it does NOT
claim humans detect well (that needs the deferred user study).

Part A: real NL->IR errors (gen IR vs gt IR) from the error-distribution run --
        does rendering surface each REAL fault?
Part B: synthetic per-fault-class IR injection (incl. reactive-mode confusions) --
        per-class surface rate, to cover classes rare in Part A.

Also dumps worked examples (command, render(correct), render(faulty)) for figures.

Run (no LLM, fast):
  PYTHONPATH=/home/gnltnwjstk/joi python3 paper/run_faithfulness_surfacing.py
"""
from __future__ import annotations
import argparse
import copy
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from paper.run_mutation_test import load_meta
from paper.ir_renderer import render_ir_readable

CSV_PATH = os.path.join(ROOT, "dataset.csv")


def norm(s: str) -> str:
    return "\n".join(ln.strip() for ln in s.strip().splitlines() if ln.strip())


def render_or_none(ir):
    try:
        return norm(render_ir_readable(ir))
    except Exception:
        return None


# ── structural helpers ───────────────────────────────────────────────────────
def _find_first(tl, pred):
    """(list, index) of first step (DFS) matching pred, descending then/else/body."""
    for i, s in enumerate(tl):
        if isinstance(s, dict):
            if pred(s):
                return (tl, i)
            for k in ("then", "else", "body"):
                sub = s.get(k)
                if isinstance(sub, list):
                    r = _find_first(sub, pred)
                    if r:
                        return r
    return None


# ── IR-level fault injectors: return faulted deep-copy or None if N/A ─────────
def inj_comparator(ir):
    ir = copy.deepcopy(ir)
    loc = _find_first(ir.get("timeline", []),
                      lambda s: s.get("op") in ("if", "wait") and isinstance(s.get("cond"), str)
                      and re.search(r"(>=|<=|==|!=|>|<)", s["cond"]))
    if not loc:
        return None
    lst, i = loc
    cond = lst[i]["cond"]
    for a, b in [(">=", "<"), ("<=", ">"), ("!=", "=="), ("==", "!="), (">", "<="), ("<", ">=")]:
        if a in cond:
            lst[i]["cond"] = cond.replace(a, b, 1)
            return ir
    return None


def inj_polarity(ir):
    ir = copy.deepcopy(ir)
    loc = _find_first(ir.get("timeline", []),
                      lambda s: s.get("op") in ("if", "wait") and isinstance(s.get("cond"), str)
                      and ("true" in s["cond"] or "false" in s["cond"]))
    if not loc:
        return None
    lst, i = loc
    c = lst[i]["cond"]
    lst[i]["cond"] = (c.replace("true", "\0").replace("false", "true").replace("\0", "false"))
    return ir


def inj_arg_value(ir):
    ir = copy.deepcopy(ir)
    loc = _find_first(ir.get("timeline", []),
                      lambda s: s.get("op") == "call" and isinstance(s.get("args"), dict) and s["args"])
    if not loc:
        return None
    lst, i = loc
    args = lst[i]["args"]
    for k, v in list(args.items()):
        if isinstance(v, (int, float)):
            args[k] = v + 10
            return ir
        if isinstance(v, str) and v:
            args[k] = v + "_X"
            return ir
    return None


def inj_wrong_device(ir):
    ir = copy.deepcopy(ir)
    loc = _find_first(ir.get("timeline", []),
                      lambda s: s.get("op") == "call" and isinstance(s.get("target"), str) and "." in s["target"])
    if not loc:
        return None
    lst, i = loc
    svc, _, meth = lst[i]["target"].partition(".")
    lst[i]["target"] = ("Light" if svc != "Light" else "Speaker") + "." + meth
    return ir


def inj_timing(ir):
    ir = copy.deepcopy(ir)
    def pred(s):
        return (s.get("op") == "delay" and isinstance(s.get("duration"), str)) or \
               (s.get("op") == "wait" and isinstance(s.get("for"), str))
    loc = _find_first(ir.get("timeline", []), pred)
    if not loc:
        return None
    lst, i = loc
    fld = "duration" if lst[i].get("op") == "delay" else "for"
    val = lst[i][fld]
    m = re.search(r"\d+", str(val))
    if not m:
        return None
    lst[i][fld] = str(val).replace(m.group(0), str(int(m.group(0)) + 5), 1)
    return ir


def inj_oneshot_vs_waituntil(ir):
    """Flip a one-shot `if` gate into a blocking `wait` (and inline its then-body)."""
    ir = copy.deepcopy(ir)
    loc = _find_first(ir.get("timeline", []),
                      lambda s: s.get("op") == "if" and isinstance(s.get("then"), list))
    if not loc:
        return None
    lst, i = loc
    g = lst[i]
    repl = [{"op": "wait", "cond": g.get("cond"), "edge": "none"}] + list(g.get("then", []))
    lst[i:i + 1] = repl
    return ir


def inj_single_vs_cycle(ir):
    """Wrap a single (no-cycle) body into a recurring cycle (whenever/every-time)."""
    ir = copy.deepcopy(ir)
    tl = ir.get("timeline", [])
    if any(isinstance(s, dict) and s.get("op") == "cycle" for s in tl):
        return None
    if not tl or not (isinstance(tl[0], dict) and tl[0].get("op") == "start_at"):
        return None
    head, body = tl[0], tl[1:]
    if not body:
        return None
    ir["timeline"] = [head, {"op": "cycle", "until": None, "period": "10 MIN", "body": body}]
    return ir


def inj_and_drop(ir):
    """Drop one conjunct of an AND condition."""
    ir = copy.deepcopy(ir)
    loc = _find_first(ir.get("timeline", []),
                      lambda s: s.get("op") in ("if", "wait") and isinstance(s.get("cond"), str)
                      and " and " in s["cond"])
    if not loc:
        return None
    lst, i = loc
    parts = lst[i]["cond"].split(" and ")
    lst[i]["cond"] = " and ".join(parts[:-1]) if len(parts) > 2 else parts[0]
    return ir


INJECTORS = [
    ("comparator", inj_comparator),
    ("polarity", inj_polarity),
    ("wrong_arg_value", inj_arg_value),
    ("wrong_device", inj_wrong_device),
    ("timing_duration", inj_timing),
    ("oneshot_vs_waituntil", inj_oneshot_vs_waituntil),
    ("single_vs_cycle_whenever", inj_single_vs_cycle),
    ("and_conjunct_drop", inj_and_drop),
]


def load_commands():
    cmd = {}
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            c, idx = (r.get("category_v2") or "").strip(), (r.get("index") or "").strip()
            if c and idx:
                cmd[f"{c}_{idx}"] = r.get("command_eng") or r.get("command_kor") or ""
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-dir", default="experiments/e2e_382/20260528_150445__d886015/intermediate/off")
    ap.add_argument("--dist", default="paper/Final/evaluation/results/nl2ir_error_distribution.json")
    ap.add_argument("--out", default="paper/Final/evaluation/results/faithfulness_surfacing.json")
    ap.add_argument("--examples-out", default="paper/Final/evaluation/results/rendering_worked_examples.json")
    a = ap.parse_args()
    gen_dir = os.path.join(ROOT, a.gen_dir)
    meta = load_meta()
    commands = load_commands()
    examples = []

    # ── Part A: real NL->IR errors ──
    dist = json.load(open(os.path.join(ROOT, a.dist), encoding="utf-8"))
    err_names = [r["name"] for r in dist["rows"] if r.get("verdict") == "error"]
    a_surf = a_total = 0
    a_blind = []
    upstream_rejected = []
    for name in err_names:
        gt = meta.get(name, {}).get("ir_gt")
        gp = os.path.join(gen_dir, f"{name}.json")
        if not isinstance(gt, dict) or not os.path.exists(gp):
            continue
        gen = json.load(open(gp, encoding="utf-8")).get("ir")
        # Apply the pipeline's static catalog gate: IRs it rejects (e.g. a
        # selector leaked into call args) never reach rendering, so they are
        # not part of the rendering-surfacing population.
        try:
            from paper.run_local_ir import _load_catalog
            from paper.timeline_ir import validate_ir_against_catalog
            validate_ir_against_catalog(gen, _load_catalog())
        except Exception:
            upstream_rejected.append(name)
            continue
        rgt, rgen = render_or_none(gt), render_or_none(gen)
        if rgt is None or rgen is None:
            continue
        a_total += 1
        if rgt != rgen:
            a_surf += 1
        else:
            a_blind.append(name)
        if len(examples) < 12:
            examples.append({"part": "A_real", "name": name, "command": commands.get(name, ""),
                             "render_correct": rgt, "render_faulty": rgen, "surfaced": rgt != rgen})

    # ── Part B: synthetic per-class injection on gt IRs ──
    b_stats = {k: [0, 0] for k, _ in INJECTORS}     # class -> [surfaced, applicable]
    b_blind = defaultdict(list)
    for name, m in sorted(meta.items()):
        gt = m.get("ir_gt")
        if not isinstance(gt, dict):
            continue
        rgt = render_or_none(gt)
        if rgt is None:
            continue
        for cls, fn in INJECTORS:
            faulted = fn(gt)
            if faulted is None or faulted == gt:
                continue
            rfa = render_or_none(faulted)
            if rfa is None:
                continue
            b_stats[cls][1] += 1
            if rfa != rgt:
                b_stats[cls][0] += 1
            else:
                b_blind[cls].append(name)
            if cls in ("oneshot_vs_waituntil", "single_vs_cycle_whenever", "and_conjunct_drop") \
                    and sum(1 for e in examples if e.get("cls") == cls) < 2:
                examples.append({"part": "B_synth", "cls": cls, "name": name,
                                 "command": commands.get(name, ""), "render_correct": rgt,
                                 "render_faulty": rfa, "surfaced": rfa != rgt})

    summary = {
        "claim": "deterministic renderer surfaces faults in plain text (no blind spots); "
                 "necessary condition for confirmation, human-free. Does NOT claim humans detect well.",
        "part_A_real_errors": {
            "n": a_total, "surfaced": a_surf,
            "surface_rate": round(a_surf / max(1, a_total), 4),
            "blind_spots": a_blind, "upstream_rejected": upstream_rejected,
        },
        "part_B_synthetic_by_class": {
            cls: {"applicable": tot, "surfaced": surf,
                  "surface_rate": round(surf / max(1, tot), 4),
                  "blind_spots": b_blind[cls][:8]}
            for cls, (surf, tot) in b_stats.items()
        },
    }
    outp = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump(summary, open(outp, "w"), indent=1, ensure_ascii=False)
    json.dump(examples, open(os.path.join(ROOT, a.examples_out), "w"), indent=1, ensure_ascii=False)

    print("=" * 64)
    print(f"PART A (real NL->IR errors): {a_surf}/{a_total} surfaced "
          f"= {summary['part_A_real_errors']['surface_rate']:.1%}"
          + (f"  | BLIND SPOTS: {a_blind}" if a_blind else "  | 0 blind spots"))
    print("\nPART B (synthetic per-class surface rate):")
    for cls, (surf, tot) in b_stats.items():
        bs = b_blind[cls]
        print(f"  {cls:26s} {surf:3d}/{tot:<3d} = {surf/max(1,tot):5.1%}"
              + (f"  BLIND: {bs[:5]}" if bs else "  (0 blind)"))
    print(f"\n-> {a.out}\n-> {a.examples_out} ({len(examples)} worked examples for figures)")


if __name__ == "__main__":
    main()
