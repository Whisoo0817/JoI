"""Baseline B3 evidence run: full LLM re-emission over the anchor environments.

Sweep: 5 templates x 6 anchor envs (env00..env05). Per cell, machine checks:

    parse / dangling refs     can the artifact even deploy?
    lines preserved           how much untouched code survives byte-identical —
                              B1/ours preserve it BY CONSTRUCTION (splice), B3
                              re-emits everything and hopes
    env00 identity + miter    the control cell: same home, nothing to adapt.
                              A sound adapter returns the program unchanged;
                              every behavioral difference the relational miter
                              finds here is gratuitous rewrite damage.

    python3 -m adapt.run_b3_check [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from sim.catalog import load_catalog                     # noqa: E402

from adapt.baselines import b3_regen                     # noqa: E402
from adapt.environments import synthetic_envs            # noqa: E402
from adapt.template import (list_templates, load_skeleton,  # noqa: E402
                            load_template)

_failures: list = []


def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _failures.append(label)
    return cond


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(_HERE, "b3_check.json"))
    ap.add_argument("--miter-timeout-ms", type=int, default=120_000)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    envs = synthetic_envs(6)      # the six single-axis anchors
    rows: list = []

    n_deploy = n_cells = 0
    pres_num = pres_den = 0
    for tid in list_templates():
        t = load_template(tid)
        src = load_skeleton(t)
        for env in envs:
            n_cells += 1
            try:
                r = b3_regen(src, env, catalog)
            except Exception as e:
                rows.append({"case": tid, "env": env.name, "error": str(e)[:120]})
                print(f"  !! {tid} x {env.name}: {type(e).__name__}: {str(e)[:80]}")
                continue
            kept = r.member_map.get("_lines_preserved", "0/1")
            a, b = kept.split("/")
            pres_num += int(a)
            pres_den += int(b)
            n_deploy += r.deployable
            rows.append({"case": tid, "env": env.name,
                         "deployable": r.deployable,
                         "lines_preserved": kept,
                         "issues": r.issues[:3]})
            print(f"  {tid:<20} x {env.name}: deploy={r.deployable} "
                  f"preserved={kept} {r.issues[:1]}")

    print(f"\n[b3] deployable {n_deploy}/{n_cells}  "
          f"verbatim line survival {pres_num}/{pres_den} "
          f"({pres_num / max(1, pres_den):.0%}) — splice gives 100% off the "
          f"edit footprint by construction")

    # ── identity control: miter the env00 cells ──────────────────────────────
    print("\n[env00 identity control] rewrite for the SAME home → miter vs original")
    from adapt.inventory import base_office
    from smt.relational import check_relational_v2, emitted_sigs_v2
    inv = base_office()
    id_ok = id_run = 0
    for tid in list_templates():
        t = load_template(tid)
        src = load_skeleton(t)
        row = next((r for r in rows if r["case"] == tid and r["env"] == "env00"), None)
        cell = None
        for r_ in rows:
            if r_["case"] == tid and r_["env"] == "env00":
                cell = r_
        if cell is None or not cell.get("deployable"):
            print(f"  {tid}: not deployable — cannot even enter certification")
            continue
        out_src = None
        # regenerate once more deterministically for the miter (cells above
        # did not keep the artifact text in rows to keep the JSON small)
        try:
            out_src = b3_regen(src, envs[0], catalog).output
        except Exception as e:
            print(f"  {tid}: regen failed {e}")
            continue
        raw = json.load(open(os.path.join(_HERE, "templates", f"{tid}.json"),
                             encoding="utf-8"))
        period = int((raw.get("validity") or {}).get("period_ms", 1000))
        try:
            keep = emitted_sigs_v2(src, inv, catalog) \
                & emitted_sigs_v2(out_src, inv, catalog)
            r = check_relational_v2(src, out_src, period, inv, catalog,
                                    preserve=keep, split=True,
                                    timeout_ms=args.miter_timeout_ms, w_cap=32)
        except Exception as e:
            print(f"  {tid}: miter entry failed — {type(e).__name__}: {str(e)[:80]}")
            cell["identity_miter"] = f"unverifiable: {str(e)[:80]}"
            id_run += 1
            continue
        id_run += 1
        verdict = r["verdict"]
        cell["identity_miter"] = {"verdict": verdict,
                                  "violated": r.get("violated"),
                                  "obligations": r.get("obligations")}
        mark = "ok  " if verdict == "EQUIV" else "!!  "
        if verdict == "EQUIV":
            id_ok += 1
        print(f"  {mark}{tid}: {verdict} "
              f"{('violated=' + str(r.get('violated'))) if verdict == 'DIVERGE' else ''}")

    check(id_run >= 3, f"identity control ran on {id_run}/5 templates")
    print(f"\n  identity-preserving: {id_ok}/{id_run} "
          f"(ours/B1 are identity here BY CONSTRUCTION)")

    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"\n{'DONE' if not _failures else str(len(_failures)) + ' FAILURES'}")
    print(f"detail → {args.json}")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
