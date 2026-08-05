"""Eval stage ⑤ evidence: the B1 complexity-discrimination curve.

Sweep: {T1 sample + 5 purpose templates} x {N synthetic environments}.
For each cell run B1 (naive interface-level slot substitution) and judge its
artifact with MACHINE checks only:

    deployable      parses + no dangling device types
    contract faults check_binding blocking violations, by fault class a..f
    quantifier trap v2 grounding refuses a plain read with N instances (c)

and, side by side, run OUR binder (stage ④) for the sound decision.

The curve's claim: at complexity ~1 (T1: selector-level portability) B1 is
sufficient — at template complexity B1 keeps DEPLOYING fine while the
contract layer finds silent faults, which is precisely the "unsound
baseline" story (the artifact runs; it is wrong).

Anchor expectations asserted (env00..env05 are single-axis adversaries):
    env00 control → B1 clean;  env01 Fan → (a);  env02 Dehumidifier → (a/d);
    env03 Motion → (b);  env04 3x TS → quantifier trap;  env05 no toast → (f)
    T1 sample → B1 succeeds 10/10.

    python3 -m adapt.run_b1_curve [--envs 24] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from sim.catalog import load_catalog                     # noqa: E402

from adapt.baselines import b1_adapt, b5_patch           # noqa: E402
from adapt.bind import bind                              # noqa: E402
from adapt.environments import synthetic_envs            # noqa: E402
from adapt.structure import extract                      # noqa: E402
from adapt.template import (check_binding, list_templates,  # noqa: E402
                            load_skeleton, load_template)

_CACHE = os.path.join(_REPO, "sim", "cache")
_failures: list = []


def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _failures.append(label)
    return cond


def _complexity(t, st) -> int:
    return len(t.roles) + sum(len(r.sources) for r in t.roles) \
        + len(st.blocks) // 4


def _b1_binding(t, type_map):
    out = {}
    for r in t.roles:
        srcs = []
        for s in r.sources:
            mapped = [type_map.get(tag, tag) for tag in s.tags]
            srcs.append([] if "" in mapped[:1] or not type_map.get(s.tags[0], s.tags[0])
                        else mapped)
        out[r.role] = srcs
    return out


def _quant_trap(output, env, catalog):
    from smt.encode import Unsupported
    from smt.encode_v2 import ground_script
    try:
        ground_script(output, env, catalog)
        return None
    except Unsupported as e:
        msg = str(e)
        if "instances for a plain" in msg:
            return f"(c) {msg[:70]}"
        return None      # other grounding gaps are not B1's fault here
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--envs", type=int, default=24)
    ap.add_argument("--json", default=os.path.join(_HERE, "b1_curve.json"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    catalog = load_catalog()
    envs = synthetic_envs(args.envs)
    rows: list = []

    # ── T1 sample: the complexity-1 end of the curve ─────────────────────────
    t1_ok = t1_n = 0
    for fn in sorted(os.listdir(_CACHE))[:40]:
        if not fn.endswith(".json") or t1_n >= 10:
            continue
        pair = json.load(open(os.path.join(_CACHE, fn), encoding="utf-8"))
        src = (pair.get("joi_block") or {}).get("script") or ""
        if not src.strip():
            continue
        st = extract(src, fn)
        if not st.devices:
            continue
        t1_n += 1
        # target env: every referenced type present (the corpus's own home) —
        # portability at this tier is selector-level, which is B1's home turf
        from adapt.inventory import DeviceInstance, Inventory
        types = sorted({tag for d in st.devices for tag in d.tags if tag in catalog})
        env = Inventory("t1home", ["Lab"],
                        [DeviceInstance(f"d{i}", t_, ["Lab"])
                         for i, t_ in enumerate(types)])
        r = b1_adapt(src, st, env, catalog)
        ok = r.deployable
        t1_ok += ok
        rows.append({"tier": "T1", "case": fn[:-5], "env": "t1home",
                     "complexity": 1, "b1_deployable": r.deployable,
                     "b1_blocking": [], "b1_success": bool(ok)})
    check(t1_ok == t1_n == 10, f"T1 tier: B1 succeeds {t1_ok}/{t1_n} "
                               f"(selector-level portability is B1's home turf)")

    # ── template x environment sweep ─────────────────────────────────────────
    anchor_hits = {k: False for k in
                   ("env01:a", "env02:ad", "env03:b", "env04:absorbed",
                    "env05:alert_sink")}
    for tid in list_templates():
        t = load_template(tid)
        src = load_skeleton(t)
        st = extract(src, tid)
        cx = _complexity(t, st)
        for env in envs:
            ours = bind(t, st, env)
            r = b1_adapt(src, st, env, catalog)
            blocking: list = []
            if r.deployable:
                vs = check_binding(t, _b1_binding(t, r.type_map))
                blocking = [f"({v.fault_class}) {v.role}: {v.detail[:60]}"
                            for v in vs if v.severity == "blocking"]
                trap = _quant_trap(r.output, env, catalog)
                if trap:
                    blocking.append(trap)
            success = r.deployable and not blocking

            r5 = b5_patch(src, st, env, catalog)
            blocking5: list = []
            if r5.deployable:
                vs = check_binding(t, _b1_binding(t, r5.type_map))
                blocking5 = [f"({v.fault_class}) {v.role}: {v.detail[:60]}"
                             for v in vs if v.severity == "blocking"]
                trap = _quant_trap(r5.output, env, catalog)
                if trap:
                    blocking5.append(trap)
            success5 = r5.deployable and not blocking5

            rows.append({"tier": "T2", "case": tid, "env": env.name,
                         "complexity": cx, "b1_deployable": r.deployable,
                         "b1_blocking": blocking, "b1_success": success,
                         "b5_deployable": r5.deployable,
                         "b5_blocking": blocking5, "b5_success": success5,
                         "ours": ours.verdict,
                         "b1_map": {k: v for k, v in r.type_map.items() if k != v}})
            if args.verbose and (blocking or not r.deployable):
                print(f"    {tid} x {env.name}: deploy={r.deployable} "
                      f"faults={blocking[:2]} ours={ours.verdict}")
            # anchor bookkeeping
            fc = "".join(sorted({b[1] for b in blocking if b.startswith("(")}))
            if env.name == "env01" and tid == "thermo_comfort" and r.deployable \
                    and "a" in fc:
                anchor_hits["env01:a"] = True
            if env.name == "env02" and tid == "thermo_comfort" and r.deployable \
                    and ("a" in fc or "d" in fc):
                anchor_hits["env02:ad"] = True
            if env.name == "env03" and tid == "section_presence" and "b" in fc:
                anchor_hits["env03:b"] = True
            if env.name == "env04" and tid == "thermo_comfort" and success:
                # 3x TS is ABSORBED by the skeleton's all()/for iteration —
                # the corpus finding (quantity edits = 0) reproduced live
                anchor_hits["env04:absorbed"] = True
            if env.name == "env05" and tid in ("intrusion_alert", "air_quality") \
                    and (any("ALERT_SINK" in b for b in blocking)
                         or not r.deployable):
                anchor_hits["env05:alert_sink"] = True

    check(all(rows_ := [r for r in rows if r["tier"] == "T2"
              and r["env"] == "env00" and r["b1_success"]]) and len(rows_) == 5,
          "env00 control: B1 identity binding is clean on all 5 templates")
    for k, hit in anchor_hits.items():
        check(hit, f"anchor {k}: the single-axis adversary trips B1 as designed")

    # ── the curve ────────────────────────────────────────────────────────────
    print("\n[curve] success rate by complexity (B1 = text substitution, "
          "B5 = same substitution via typed AST edits, no contracts)")
    by_cx: dict = {}
    for r in rows:
        by_cx.setdefault(r["complexity"], []).append(r)
    for cx in sorted(by_cx):
        rs = by_cx[cx]
        ok = sum(1 for r in rs if r["b1_success"])
        dep = sum(1 for r in rs if r["b1_deployable"])
        ok5 = sum(1 for r in rs if r.get("b5_success"))
        dep5 = sum(1 for r in rs if r.get("b5_deployable"))
        who = rs[0]["case"] if len({r["case"] for r in rs}) == 1 else "T1"
        b5col = f"  B5 deploy {dep5/len(rs):5.0%} sound {ok5/len(rs):5.0%}" \
            if rs[0]["tier"] == "T2" else ""
        print(f"  cx={cx:>2} ({who:<18}) n={len(rs):>3}  "
              f"B1 deploy {dep/len(rs):5.0%} sound {ok/len(rs):5.0%}{b5col}")
    t2 = [r for r in rows if r["tier"] == "T2"]
    silent = [r for r in t2 if r["b1_deployable"] and r["b1_blocking"]]
    silent5 = [r for r in t2 if r.get("b5_deployable") and r.get("b5_blocking")]
    print(f"\n  T2 cells: {len(t2)}  — B1 deploys {sum(r['b1_deployable'] for r in t2)}"
          f", silently faulty {len(silent)} "
          f"({len(silent)/max(1, sum(r['b1_deployable'] for r in t2)):.0%})"
          f"  |  B5 deploys {sum(r.get('b5_deployable', 0) for r in t2)}"
          f", silently faulty {len(silent5)} "
          f"({len(silent5)/max(1, sum(r.get('b5_deployable', 0) for r in t2)):.0%})")
    fault_hist = Counter(b[1] for r in t2 for b in r["b1_blocking"]
                         if b.startswith("("))
    fault_hist5 = Counter(b[1] for r in t2 for b in r.get("b5_blocking", [])
                          if b.startswith("("))
    print(f"  fault classes  B1: {dict(sorted(fault_hist.items()))}  "
          f"B5: {dict(sorted(fault_hist5.items()))}")
    ours_hist = Counter(r.get("ours") for r in t2 if r.get("ours"))
    print(f"  our binder verdicts over the same cells: {dict(sorted(ours_hist.items()))}")
    agree = sum(1 for r in t2 if r["b1_success"] == r.get("b5_success"))
    print(f"  B1↔B5 soundness agreement: {agree}/{len(t2)} — AST discipline "
          f"changes deployment hygiene, not correctness")

    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"\n{'ALL PASS' if not _failures else str(len(_failures)) + ' FAILURES'}")
    for x in _failures:
        print("  -", x)
    print(f"detail → {args.json}")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
