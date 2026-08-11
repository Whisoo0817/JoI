# -*- coding: utf-8 -*-
"""Finalize E1 items: attach the [Services] catalog block and merged clauses.

Two additions on top of seg.py's items.json, both applied IDENTICALLY to every arm:

1. `devices` is rewritten as "device_id: [Category, ...]" lines (the format prompts.py
   documents) followed by a [Services] block listing ONLY the categories this command owns.
   Without it every arm has to invent service names it was never shown — an artificial
   floor that compresses the between-arm signal.

2. `clauses_merged` = condition-chain merging (segmerge). The item audit found that 11/60
   items over-split a composite `if`/`wait` condition ("A이고 | B이면"); the merged arms
   measure how much of the segmentation effect is destroyed by that over-splitting.
"""
import json, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import services_block          # noqa: E402
from segmerge import merge_condition_chain  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "items.json")
DST = os.path.join(HERE, "items_final.json")


def device_lines(devices_str):
    try:
        dev = json.loads(devices_str, strict=False)
    except Exception:
        return devices_str.strip()
    if not isinstance(dev, dict):
        return devices_str.strip()
    out = []
    for did, meta in dev.items():
        cats = (meta or {}).get("category", []) or []
        out.append("%s: [%s]" % (did, ", ".join(cats)))
    return "\n".join(out)


def main():
    items = json.load(open(SRC))
    n_merged = 0
    for it in items:
        raw = it["devices"]
        it["devices_raw"] = raw
        it["devices"] = "%s\n\n[Services]\n%s" % (device_lines(raw), services_block(raw))
        merged = merge_condition_chain(it["clauses"])
        it["clauses_merged"] = merged
        if merged != it["clauses"]:
            n_merged += 1
    json.dump(items, open(DST, "w"), ensure_ascii=False, indent=1)

    sizes = sorted(len(it["devices"]) for it in items)
    print("wrote %s  (n=%d)" % (DST, len(items)))
    print("env block chars: min=%d p50=%d p90=%d max=%d"
          % (sizes[0], sizes[len(sizes) // 2], sizes[int(len(sizes) * .9)], sizes[-1]))
    print("condition-chain merge changed %d/%d items" % (n_merged, len(items)))
    from collections import Counter
    print("clause count  plain :", dict(sorted(Counter(len(i["clauses"]) for i in items).items())))
    print("clause count  merged:", dict(sorted(Counter(len(i["clauses_merged"]) for i in items).items())))
    print("\n--- items where merging fired ---")
    shown = 0
    for it in items:
        if it["clauses_merged"] != it["clauses"] and shown < 6:
            print("\n plain : %s" % " | ".join(it["clauses"]))
            print(" merged: %s" % " | ".join(it["clauses_merged"]))
            shown += 1
    print("\n--- example env block ---")
    print(items[0]["devices"][:900])


if __name__ == "__main__":
    main()
