"""Relational-miter harness over T1: self-equivalence, seeded-edit
sensitivity, and the R4 projection proof.

For every cached JoI block (one-shot + a sample of periodic; cron skipped
until the new-syntax encoding lands):

    self   check_relational(jb, jb)                → EQUIV on every obligation
           (encoder-run-twice + shared-input plumbing is sound)
    arg    mutate ONE literal argument in the script → DIVERGE, and the
           violated obligations name exactly the mutated channel
           (sensitivity + localization)
    drop   delete one call line:
             without preserve                      → DIVERGE   (sensitivity)
             preserve = sigs of the mutated code   → EQUIV     (projection:
           every surviving channel individually proved unchanged — the
           artifact-certification query of stage ⑥)

    python3 -m smt.run_relational [--m2-sample 8] [--only ...] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

from sim.catalog import load_catalog

from smt.encode import MEmit, MIf, joi_to_micro
from smt.encode2 import joi_to_micro2
from smt.relational import check_relational, emitted_sigs, sig_label

_CACHE = os.path.join(os.path.dirname(__file__), "..", "sim", "cache")
_RESULTS = os.path.join(os.path.dirname(__file__), "results")

_CALL_LINE = re.compile(r"^\s*\(#[^)]*\)\.\w+\(.*\)\s*$")
_NUM_ARG = re.compile(r"(?<=[(,\s])(\d+)(?=[),\s.])")
_STR_ARG = re.compile(r'"([^"]*)"')


def _micro(jb: dict) -> list:
    period = int(jb.get("period", 0) or 0)
    return joi_to_micro2(jb)[0] if period > 0 else joi_to_micro(jb)


def _emit_diff(a_ops: list, b_ops: list, out: set) -> set:
    """Signatures whose emitted args differ, walking both trees in lockstep
    (the mutation changes one literal, so the shapes match)."""
    from sim import expr as E
    for a, b in zip(a_ops, b_ops):
        if isinstance(a, MEmit) and isinstance(b, MEmit):
            if repr(a.args) != repr(b.args):
                _, method_c = E.canonical_key(a.service, a.method)
                out.add(sig_label(method_c, len(a.args)))
        elif isinstance(a, MIf) and isinstance(b, MIf):
            _emit_diff(a.then, b.then, out)
            _emit_diff(a.els, b.els, out)
    return out


def _mutate_arg(script: str):
    """Change one literal argument in the LAST call line → (mutated, line#)."""
    lines = script.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if not _CALL_LINE.match(lines[i]):
            continue
        head, _, args = lines[i].partition("(")
        head2, _, args = args.partition("(")   # selector paren, then arg paren
        prefix = head + "(" + head2 + "("
        m = _NUM_ARG.search(" " + args)
        if m:
            new_args = (" " + args)[:m.start()] + str(int(m.group(1)) + 7) \
                + (" " + args)[m.end():]
            lines[i] = prefix + new_args[1:]
            return "\n".join(lines), i
        m = _STR_ARG.search(args)
        if m:
            new_args = args[:m.start()] + f'"{m.group(1)}__mut"' + args[m.end():]
            lines[i] = prefix + new_args
            return "\n".join(lines), i
    return None, -1


def _drop_line(script: str):
    """Delete one bare-call line whose signature is unique in the script."""
    lines = script.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if not _CALL_LINE.match(lines[i]):
            continue
        meth = re.search(r"\)\.(\w+)\(", lines[i])
        if meth and sum(1 for ln in lines if f".{meth.group(1)}(" in ln) == 1:
            return "\n".join(lines[:i] + lines[i + 1:]), i
    return None, -1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--m2-sample", type=int, default=8)
    ap.add_argument("--json", default=os.path.join(_RESULTS, "relational.json"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    only = set(x.strip() for x in args.only.split(",") if x.strip())

    results: dict = {}
    fails: list = []
    stats = Counter()
    n_m2 = 0

    for fn in sorted(os.listdir(_CACHE)):
        if not fn.endswith(".json"):
            continue
        pid = fn[:-5]
        if only and pid not in only:
            continue
        with open(os.path.join(_CACHE, fn), encoding="utf-8") as f:
            pair = json.load(f)
        jb = pair.get("joi_block") or {}
        if (jb.get("cron") or "").strip():
            stats["skip_cron"] += 1
            continue
        periodic = int(jb.get("period", 0) or 0) > 0
        if periodic:
            if n_m2 >= args.m2_sample:
                stats["skip_m2_sampled"] += 1
                continue
            n_m2 += 1
        cls = "M2" if periodic else "M1"
        tmo = 120_000 if periodic else 0
        row: dict = {"class": cls}

        def fail(tag, detail):
            fails.append(f"{pid}/{tag}: {detail}")
            row[tag + "_fail"] = detail

        # 1) self-equivalence
        r = check_relational(jb, jb, catalog, timeout_ms=tmo)
        row["self"] = r["verdict"]
        stats[f"{cls}_self_{r['verdict']}"] += 1
        if r["verdict"] != "EQUIV":
            fail("self", f"{r['verdict']} {r.get('violated') or r.get('reason', '')}")

        # 2) seeded argument edit → localized DIVERGE
        mut, _ = _mutate_arg(jb.get("script", "") or "")
        if mut is not None:
            jb2 = dict(jb, script=mut)
            try:
                expected = _emit_diff(_micro(jb), _micro(jb2), set())
            except Exception:
                expected = set()
            if expected:
                r = check_relational(jb, jb2, catalog, timeout_ms=tmo)
                row["arg"] = r["verdict"]
                row["arg_violated"] = r.get("violated")
                stats[f"{cls}_arg_{r['verdict']}"] += 1
                if r["verdict"] != "DIVERGE":
                    fail("arg", f"seeded edit not caught: {r['verdict']}")
                else:
                    allowed = {p + lbl for lbl in expected
                               for p in ("sig:", "align:", "count:")}
                    if not set(r.get("violated") or []) <= allowed:
                        fail("arg_loc", f"violated {r.get('violated')} "
                                        f"outside {sorted(allowed)}")
                    else:
                        stats[f"{cls}_arg_localized"] += 1
            else:
                stats[f"{cls}_arg_nochange"] += 1
        else:
            stats[f"{cls}_arg_nosite"] += 1

        # 3) drop one channel: caught bare, proved away under projection
        dropped, _ = _drop_line(jb.get("script", "") or "")
        if dropped is not None:
            jb3 = dict(jb, script=dropped)
            try:
                keep = emitted_sigs(jb3)
                old_sigs = emitted_sigs(jb)
            except Exception:
                keep = old_sigs = None
            if keep is not None and keep != old_sigs:
                r = check_relational(jb, jb3, catalog, timeout_ms=tmo)
                row["drop_bare"] = r["verdict"]
                stats[f"{cls}_drop_{r['verdict']}"] += 1
                if r["verdict"] != "DIVERGE":
                    fail("drop", f"dropped channel not caught: {r['verdict']}")
                r = check_relational(jb, jb3, catalog, preserve=keep,
                                     timeout_ms=tmo)
                row["drop_proj"] = r["verdict"]
                row["proj_obligations"] = len(r.get("obligations") or {})
                stats[f"{cls}_proj_{r['verdict']}"] += 1
                if r["verdict"] != "EQUIV":
                    fail("proj", f"projection not proved: {r['verdict']} "
                                 f"{r.get('violated')}")
                elif keep and not r.get("obligations"):
                    # preserve didn't bite a single channel — a label-scheme
                    # slip would make every projection proof vacuously EQUIV
                    fail("proj_vacuous", f"preserve={sorted(keep)} matched "
                                         f"no obligations")
            else:
                stats[f"{cls}_drop_nosite"] += 1
        else:
            stats[f"{cls}_drop_nosite"] += 1

        results[pid] = row
        if args.verbose:
            print(f"{pid} [{cls}] self={row.get('self')} arg={row.get('arg', '-')}"
                  f" drop={row.get('drop_bare', '-')}/{row.get('drop_proj', '-')}")

    print(f"\npairs: {len(results)}  (+{stats['skip_cron']} cron skipped, "
          f"{stats['skip_m2_sampled']} M2 beyond sample)")
    for k in sorted(stats):
        if not k.startswith("skip"):
            print(f"  {k:<24} {stats[k]:>4}")
    print(f"failures: {len(fails)}")
    for f_ in fails:
        print("  -", f_)
    print("PASS" if not fails else "FAIL")

    os.makedirs(_RESULTS, exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=str)
    print(f"detail → {args.json}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
