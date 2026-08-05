"""Unit tests for the splice invariant (stage ⑤ / ladder level L1).

Run: python3 -m adapt.test_patch
"""

from __future__ import annotations

from .patch import (Edit, EditConflict, apply_and_check, apply_edits, delete_span,
                    insert_before, replace_argument, replace_member, replace_tag,
                    verify_splice)
from .structure import Span, extract

SRC = (
    "cooldown := 300\n"
    "now = (#Clock).clock_timestamp\n"
    "if (all(#TemperatureSensor #Office).temperatureSensor_temperature > 25) {\n"
    "  (#AirConditioner #Office).switch_on()\n"
    "  delay(500 MSEC)\n"
    "}\n"
)

_failures: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _failures.append(label)


def test_identity() -> None:
    st = extract(SRC, "t")
    res = apply_and_check(st, [])
    check(res.ok and res.output == SRC, "identity: zero edits reproduce the source")


def test_retag_preserves_everything_else() -> None:
    st = extract(SRC, "t")
    edits = replace_tag(st, "Office", "Home")
    res = apply_and_check(st, edits)
    check(res.ok, f"retag: patch accepted ({res.summary})")
    check(res.output.count("#Home") == len(edits) == 2, "retag: both occurrences rewritten")
    check("#Office" not in res.output, "retag: old tag gone")
    check(len(res.output) == len(SRC) + 2 * (len("Home") - len("Office")),
          "retag: byte delta is exactly the substitution delta")
    before, after = st.signature("B0"), res.structure_after.signature("B0")
    diff = {k: v for k, v in before.diff(after).items() if k != "tags"}
    check(not diff, f"retag: signature stable except tags (diff={diff})")


def test_device_type_swap_is_invisible_to_structure() -> None:
    """AC -> Fan keeps the structure identical; only the binding changed.

    This is the thesis in miniature: a structural diff *cannot* catch fault
    class (a) (effect direction / capability). The contract layer (stage ④)
    has to, which is why "slot substitution needs no verification" is false.
    """
    st = extract(SRC, "t")
    res = apply_and_check(st, replace_tag(st, "AirConditioner", "Fan"))
    check(res.ok, "device-type swap: valid splice")
    diff = {k: v for k, v in st.signature("B0").diff(res.structure_after.signature("B0")).items()
            if k != "tags"}
    check(not diff, f"device-type swap: structure unchanged, only tags move (diff={diff})")
    before_tags = st.signature("B0").tags
    after_tags = res.structure_after.signature("B0").tags
    check("Fan" in after_tags and "AirConditioner" in before_tags,
          "device-type swap: the binding *is* visible in the tag set")


def test_threshold_and_delay() -> None:
    st = extract(SRC, "t")
    guard = [g for g in st.guards if g.op][0]
    res = apply_and_check(st, [Edit(guard.rhs_span, "26", "ModifyPredicate", "thr")])
    check(res.ok and "> 26)" in res.output, "threshold: 25 -> 26 spliced")
    check(res.output.replace("> 26)", "> 25)") == SRC, "threshold: nothing else moved")

    st2 = extract(SRC, "t")
    t = st2.times[0]
    res2 = apply_and_check(st2, [Edit(t.span, "2000 MSEC", "ChangeDelay", "d")])
    check(res2.ok and res2.structure_after.times[0].ms == 2000, "delay: 500 -> 2000 MSEC")


def test_member_and_argument() -> None:
    st = extract(SRC, "t")
    call = [d for d in st.devices if d.kind == "call"][0]
    res = apply_and_check(st, [replace_member(call, "switch_off")])
    check(res.ok and "switch_off()" in res.output, "member: switch_on -> switch_off")

    st2 = extract('(#Light).light_setLevel(50, 0)\n', "t2")
    call2 = [d for d in st2.devices if d.kind == "call"][0]
    res2 = apply_and_check(st2, [replace_argument(call2, 0, "80")])
    check(res2.ok and "setLevel(80, 0)" in res2.output, "argument: first arg 50 -> 80")


def test_delete_and_insert() -> None:
    st = extract(SRC, "t")
    delay_stmt = st.times[0]
    line_start = SRC.rfind("\n", 0, delay_stmt.span.start) + 1
    line_end = SRC.find("\n", delay_stmt.span.start) + 1
    res = apply_and_check(st, [delete_span(Span(line_start, line_end), "drop delay")])
    check(res.ok and "delay(" not in res.output, "delete: delay statement removed")

    st2 = extract(SRC, "t")
    res2 = apply_and_check(st2, [insert_before(0, "guard := true\n", "seed")])
    check(res2.ok and res2.output.startswith("guard := true\n"), "insert: prefix added")


def test_conflicts_fail_closed() -> None:
    st = extract(SRC, "t")
    a = Edit(Span(0, 8), "x", "ReplaceSelector", "a")
    b = Edit(Span(4, 12), "y", "ReplaceSelector", "b")
    try:
        apply_edits(SRC, [a, b])
        check(False, "conflict: overlapping edits rejected")
    except EditConflict:
        check(True, "conflict: overlapping edits rejected")

    try:
        Edit(Span(0, 1), "x", "Rewrite", "bad op")
        check(False, "closed op set enforced")
    except ValueError:
        check(True, "closed op set enforced")


def test_verifier_catches_tampering() -> None:
    """verify_splice must not rubber-stamp an output that changed untouched code."""
    st = extract(SRC, "t")
    edits = replace_tag(st, "Office", "Home")
    good = apply_edits(SRC, edits)
    tampered = good.replace("cooldown := 300", "cooldown := 900")
    check(verify_splice(SRC, good, edits).ok, "verify: honest splice accepted")
    rep = verify_splice(SRC, tampered, edits)
    check(not rep.ok, f"verify: tampered preserved region rejected ({rep.detail[:40]})")

    dropped = good.replace("delay(500 MSEC)\n", "")
    check(not verify_splice(SRC, dropped, edits).ok, "verify: silent deletion rejected")


def main() -> int:
    for fn in (test_identity, test_retag_preserves_everything_else,
               test_device_type_swap_is_invisible_to_structure, test_threshold_and_delay,
               test_member_and_argument, test_delete_and_insert,
               test_conflicts_fail_closed, test_verifier_catches_tampering):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{'ALL PASS' if not _failures else str(len(_failures)) + ' FAILURES: ' + str(_failures)}")
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
