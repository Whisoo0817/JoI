"""T1 edit-benchmark authoring: the 382 corpus as verified edit bases.

The corpus's original NL commands are discarded (locked decision); each cached
scenario becomes an EDIT BASE, and this tool authors modification requests
with machine ground truth:

    param  a UNIQUE numeric constant in the scenario → "X를 Y로 바꿔줘"
           (Y deterministic: int +1 / float +0.5), gt = the anchor
    swap   a referenced device type with a Korean name and a catalog
           alternative → "A 말고 B로 교체해줘", gt = the type pair
    (drop requests need purpose templates — T2 only, by design: essential /
     feature closure is a contract fact no bare scenario carries)

Every authored case is ROUND-TRIP VALIDATED before it enters the bench:
editir must recover exactly the intended kind + anchor and the typed edit
must apply through the splice gate. Unrecoverable candidates are dropped and
counted — the bench ships only cases whose ground truth the machinery can
adjudicate.

    python3 -m adapt.make_t1_bench [--out adapt/t1_edit_bench.json]
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

from adapt.editir import DEVICE_WORDS, classify, find_number_anchors  # noqa: E402
from adapt.patch import apply_and_check                  # noqa: E402
from adapt.structure import extract                      # noqa: E402

_CACHE = os.path.join(_REPO, "sim", "cache")

# ko word per type (first match in DEVICE_WORDS, which maps word -> type)
_TYPE_KO = {}
for w, t_ in DEVICE_WORDS.items():
    if not w.isascii():
        _TYPE_KO.setdefault(t_, w)

_SWAP_ALTS = {"AirConditioner": "Fan", "Fan": "AirConditioner",
              "Humidifier": "Dehumidifier", "Dehumidifier": "Humidifier",
              "PresenceSensor": "MotionSensor", "MotionSensor": "PresenceSensor"}


def _bump(lit: str) -> str:
    return str(int(lit) + 1) if lit.isdigit() else f"{float(lit) + 0.5:g}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(_HERE, "t1_edit_bench.json"))
    args = ap.parse_args(argv)

    catalog = load_catalog()
    cases: list = []
    stats = Counter()

    for fn in sorted(os.listdir(_CACHE)):
        if not fn.endswith(".json"):
            continue
        pid = fn[:-5]
        pair = json.load(open(os.path.join(_CACHE, fn), encoding="utf-8"))
        src = (pair.get("joi_block") or {}).get("script") or ""
        if not src.strip():
            stats["empty"] += 1
            continue
        st = extract(src, pid)
        if st.errors:
            stats["noparse"] += 1
            continue

        # ── param request: first UNIQUE numeric literal ──────────────────────
        seen: set = set()
        made_param = False
        import re
        for lit in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", src):
            if lit in seen:
                continue
            seen.add(lit)
            anchors = find_number_anchors(st, lit)
            if len(anchors) != 1:
                continue
            new = _bump(lit)
            if new in src:            # keep the contains-check unambiguous
                continue
            nl = f"{lit}를 {new}로 바꿔줘"
            d = classify(nl, st, catalog=catalog)
            if d.kind != "param_change" or not d.edits:
                stats["param_unrecovered"] += 1
                continue
            res = apply_and_check(st, d.edits)
            if not res.ok or new not in res.output:
                stats["param_gate_fail"] += 1
                continue
            cases.append({"id": f"{pid}/param", "base": pid, "nl": nl,
                          "gt": {"kind": "param_change", "old": lit,
                                 "new": new, "anchor": d.anchor}})
            made_param = True
            break
        if not made_param:
            stats["no_param_site"] += 1

        # ── swap request: first swappable referenced type ────────────────────
        types = sorted({t for dref in st.devices for t in dref.tags
                        if t in catalog})
        made_swap = False
        for t_ in types:
            alt = _SWAP_ALTS.get(t_)
            ko = _TYPE_KO.get(t_)
            ko_alt = _TYPE_KO.get(alt) if alt else None
            if not (alt and ko and ko_alt) or alt in types:
                continue
            nl = f"{ko} 말고 {ko_alt}로 교체해줘"
            d = classify(nl, st, catalog=catalog)
            if d.kind != "device_swap" or not d.edits:
                stats["swap_unrecovered"] += 1
                continue
            res = apply_and_check(st, d.edits)
            if not res.ok or f"#{alt}" not in res.output \
                    or f"#{t_}" in res.output:
                stats["swap_gate_fail"] += 1
                continue
            cases.append({"id": f"{pid}/swap", "base": pid, "nl": nl,
                          "gt": {"kind": "device_swap", "old": t_, "new": alt}})
            made_swap = True
            break
        if not made_swap:
            stats["no_swap_site"] += 1

    bases = {c["base"] for c in cases}
    by_kind = Counter(c["gt"]["kind"] for c in cases)
    print(f"authored: {len(cases)} cases over {len(bases)} bases "
          f"({dict(by_kind)})")
    print(f"skips/drops: {dict(stats)}")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"comment": "T1 edit bench v0 — machine-authored, "
                              "round-trip validated (editir recovers gt and "
                              "the typed edit passes the splice gate).",
                   "cases": cases}, f, ensure_ascii=False, indent=1)
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
