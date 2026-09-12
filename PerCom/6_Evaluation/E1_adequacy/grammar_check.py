"""Column A-extractor: which constructs in an encoding are outside the documented NL->IR grammar.

`files/timeline_ir/extractor.md` is the grammar handed to the generator. The reference runner and
`timeline_ir.validate_ir` accept strictly more than it documents, so an encoding can be valid Timeline
and still be unreachable through the current NL->IR path. E1 reports that separately from the language
verdict: it is a frontend/tooling gap, not evidence that Timeline cannot express the requirement.

Each rule below cites the line of extractor.md it is derived from (checked 2026-09-12).
"""

# construct -> (predicate over a step dict, short label, why it is outside)
_REASONS = {
    "wait.timeout": "extractor.md §2 lists wait as {cond, edge, for} only; timeout/on_timeout are absent",
    "nested cycle": "extractor.md line 20 lists 'Nested loops are requested' as a refusal reason",
    "Clock.Timestamp": "extractor.md documents Clock.Hour/Minute/Day/Month; Timestamp is not among them",
    "null operand": "extractor.md uses JSON null only as cycle.until; null is not a condition operand",
    "period 0 MSEC": "extractor.md §D7b requires a period and prescribes 1 SEC / N UNIT values",
    "edge falling": "extractor.md §D4 forbids edge:'falling' (negate the condition instead)",
}


def _cond_strings(step):
    for k in ("cond", "until"):
        v = step.get(k)
        if isinstance(v, str):
            yield v
    if isinstance(step.get("src"), str):
        yield step["src"]
    for v in (step.get("args") or {}).values():
        if isinstance(v, str):
            yield v


def check_ir(ir):
    """Return a sorted list of constructs used that extractor.md does not document."""
    found = set()

    def walk(steps, in_cycle=False):
        for st in steps or []:
            op = st.get("op")
            if op == "wait":
                if st.get("timeout") or st.get("on_timeout"):
                    found.add("wait.timeout")
                if st.get("edge") == "falling":
                    found.add("edge falling")
            if op == "cycle":
                if in_cycle:
                    found.add("nested cycle")
                if str(st.get("period") or "").strip().upper() in ("0 MSEC", "0 SEC", "0 MIN"):
                    found.add("period 0 MSEC")
            for s in _cond_strings(st):
                if "Clock.Timestamp" in s:
                    found.add("Clock.Timestamp")
                if "null" in s.split():
                    found.add("null operand")
            walk(st.get("then"), in_cycle)
            walk(st.get("else"), in_cycle)
            walk(st.get("on_timeout"), in_cycle)
            walk(st.get("body"), True if op == "cycle" else in_cycle)

    walk(ir.get("timeline"))
    return sorted(found)


def reason(construct):
    return _REASONS.get(construct, "")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from irs import IRS
    from probe_attempts import ATTEMPTS
    for name, table in (("Stage A", IRS), ("probes", ATTEMPTS)):
        print(f"== {name}")
        for cid, entry in table.items():
            out = check_ir(entry["ir"])
            print(f"  {cid:7} {', '.join(out) if out else 'within extractor.md'}")
