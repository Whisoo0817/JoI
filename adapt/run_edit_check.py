"""editir evidence run: NL edit requests → typed edits → patched artifacts.

Over `edit_requests.json` (the 3 request types + ambiguity/essential traps):

1. classification — every case lands on the expected kind; ambiguous
   constants and essential-role drops are REJECTED (with candidates /
   reason), never guessed;
2. realization — param/swap edits apply through the normal gate
   (apply_and_check: splice + parse), drops go through the slicer; the
   patched output contains / no longer contains what the request implies;
3. (--e2e) certification — the E01 param edit's artifact runs through the
   v2 relational miter: the edited channel diverges (the edit is real) and
   an unrelated channel is proved unchanged — the full NL→edit→proof path.

    python3 -m adapt.run_edit_check [--e2e] [--verbose]
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

from adapt.editir import classify                        # noqa: E402
from adapt.patch import apply_and_check                  # noqa: E402
from adapt.slicer import plan_drop                       # noqa: E402
from adapt.structure import extract                      # noqa: E402
from adapt.template import load_skeleton, load_template  # noqa: E402

_failures: list[str] = []


def check(cond: bool, label: str) -> bool:
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _failures.append(label)
    return cond


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--e2e", action="store_true",
                    help="also certify E01's artifact with the relational miter")
    ap.add_argument("--llm", action="store_true",
                    help="also run the free-form cases through the sLLM backend")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    bench = json.load(open(os.path.join(_HERE, "edit_requests.json"),
                           encoding="utf-8"))
    artifacts: dict = {}

    for case in bench["cases"]:
        cid, tid, nl = case["id"], case["template"], case["nl"]
        exp = case["expect"]
        if case.get("backend") == "llm" and not args.llm:
            continue
        t = load_template(tid)
        src = load_skeleton(t)
        st = extract(src, tid)
        if case.get("backend") == "llm":
            from adapt.editir import classify_with_llm
            d = classify_with_llm(nl, st, template=t, catalog=catalog)
        else:
            d = classify(nl, st, template=t, catalog=catalog)
        print(f"[{cid}] {nl!r}")
        check(d.kind == exp["kind"], f"{cid}: kind {d.kind} == {exp['kind']}"
              + (f"  ({d.reason[:60]})" if d.kind == "reject" else ""))
        if d.kind != exp["kind"]:
            continue

        if "candidates_min" in exp:
            check(len(d.candidates) >= exp["candidates_min"],
                  f"{cid}: ambiguity surfaced {len(d.candidates)} candidates")
        if "reason_contains" in exp:
            check(exp["reason_contains"] in d.reason,
                  f"{cid}: reason mentions {exp['reason_contains']!r}")
        if "anchor_contains" in exp:
            check(exp["anchor_contains"] in d.anchor,
                  f"{cid}: anchor {d.anchor[:60]!r}")

        out = None
        if d.edits:
            res = apply_and_check(st, d.edits)
            check(res.ok, f"{cid}: edits apply (splice+parse) — {res.summary}")
            out = res.output if res.ok else None
        elif d.kind == "feature_drop" and exp.get("drop_applies"):
            plan = plan_drop(t, st, d.drop_roles)
            check(plan.ok, f"{cid}: slicer plans drop of {d.drop_roles}"
                           + ("" if plan.ok else f" — {plan.reason}"))
            if plan.ok:
                res = apply_and_check(st, plan.edits)
                check(res.ok, f"{cid}: drop applies — {res.summary}")
                out = res.output if res.ok else None

        if out is not None:
            for s in exp.get("contains", []):
                check(s in out, f"{cid}: output contains {s!r}")
            for s in exp.get("absent", []):
                check(s not in out, f"{cid}: output no longer mentions {s!r}")
            artifacts[cid] = (tid, src, out, case)

    if args.e2e and "E01" in artifacts:
        from adapt.inventory import base_office
        from smt.relational import check_relational_v2
        tid, src, out, case = artifacts["E01"]
        spec = case["e2e"]
        raw = json.load(open(os.path.join(_HERE, "templates", f"{tid}.json"),
                             encoding="utf-8"))
        period = int((raw.get("validity") or {}).get("period_ms", 1000))
        print(f"[E2E] certify E01 artifact (relational miter, {tid})")
        r = check_relational_v2(src, out, period, base_office(), catalog,
                                timeout_ms=120_000, split=True, w_cap=32)
        obl = r.get("obligations") or {}
        viol = [l.split(":", 1)[1] for l in (r.get("violated") or [])]
        check(r["verdict"] == "DIVERGE" and
              any(ch in viol for ch in spec["affected_any"]),
              f"E2E: the edit is behaviorally real — diverges on {sorted(set(viol))}")
        un = spec["unaffected"]
        check(all(v == "EQUIV" for l, v in obl.items() if l.endswith(un)),
              f"E2E: unrelated channel {un} proved unchanged")

    print(f"\n{'ALL PASS' if not _failures else str(len(_failures)) + ' FAILURES'}")
    for f in _failures:
        print("  -", f)
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
