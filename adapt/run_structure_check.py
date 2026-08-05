"""M-A evidence run: structural extraction + splice fidelity over both corpora.

Checks, per scenario:

1. **parse**       — ANTLR accepts the script (L0 coverage of each tier).
2. **identity**    — applying zero edits reproduces the source byte for byte.
3. **retag**       — renaming one tag everywhere: the splice invariant holds, the
   output re-parses, occurrence counts match, and the block signatures differ in
   **nothing but the tag set**. That last property is the L2 claim in miniature:
   a pure re-binding must not perturb reads / writes / calls / guards / time
   constants, because capability keys come from the *member* (`switch_on` ->
   switch/on), not from the tags. Two cases are tracked apart rather than scored
   as failures: `#GlobalVariable` (a namespace, not a role) is never picked, and
   references with a bare member (no `svc_` prefix) take their capability from
   the tag, so renaming it is a real capability change that *should* show up.

   Note what this means for the thesis: swapping `#AirConditioner` -> `#Fan`
   leaves the signature stable. A structural diff cannot see fault class (a);
   only the contract layer (stage ④) can. "Slot substitution needs no
   verification" is exactly the belief this measurement refutes.
4. **byte delta**  — output length changes exactly by occurrences x (len(new)-len(old)).

This harness doubles as baseline **B5** (deterministic AST patcher with no
contracts and no verification): the same machinery, minus stages ③④⑥⑦.

    python3 -m adapt.run_structure_check            # both tiers
    python3 -m adapt.run_structure_check --tier t2  # hand-written only
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

from .patch import apply_and_check, replace_tag
from .structure import GV_TAG, Structure, extract

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_T2 = os.path.join(_REPO, "paper_v2", "joi_automation_codes.json")
_T1_GLOB = os.path.join(_REPO, "sim", "cache", "*.json")

SIGNATURE_FIELDS = ("reads", "writes", "gv_reads", "gv_writes", "calls", "guards", "times")


@dataclass
class Case:
    tier: str
    name: str
    chars: int
    parsed: bool
    errors: list[str] = field(default_factory=list)
    devices: int = 0
    blocks: int = 0
    tags: int = 0
    identity_ok: Optional[bool] = None
    retag_tag: Optional[str] = None
    retag_occurrences: int = 0
    retag_ok: Optional[bool] = None
    retag_service_tag: bool = False
    capability_from_tag: bool = False
    signature_clean: Optional[bool] = None
    signature_diff: dict = field(default_factory=dict)
    note: str = ""


def _identity(st: Structure) -> bool:
    res = apply_and_check(st, [])
    return res.ok and res.output == st.src


def _pick_tag(st: Structure) -> Optional[str]:
    """Most frequent tag; prefer a non-service (location-like) tag so the
    signature-invariance property is exercised in its strict form.

    `#GlobalVariable` is skipped: it is a language-level namespace, not a
    bindable role, so renaming it *should* change the signature (the GV keys
    stop being recognised) and would be a false alarm here.
    """
    tags = {t: v for t, v in st.tags.items() if t != GV_TAG}
    if not tags:
        return None
    service_tags = {d.service for d in st.devices}
    ranked = sorted(tags.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for tag, _ in ranked:
        if tag not in service_tags:
            return tag
    return ranked[0][0]


def _capability_from_tag(st: Structure, tag: str) -> bool:
    """True when some reference under `tag` has a bare member (no `svc_` prefix),
    so its capability key is derived from the tag itself. Renaming such a tag is
    a genuine capability change, not a pure re-binding."""
    return any("_" not in d.member for d in st.refs_for_tag(tag))


def _retag(st: Structure, tag: str, new: str) -> tuple[bool, bool, dict, str]:
    """Returns (patch_ok, signature_clean, diff, note)."""
    edits = replace_tag(st, tag, new)
    res = apply_and_check(st, edits)
    if not res.ok:
        return False, False, {}, res.summary
    after = res.structure_after
    if after is None:
        return False, False, {}, "no structure after patch"

    expected_len = len(st.src) + len(edits) * (len(new) - len(tag))
    if len(res.output) != expected_len:
        return False, False, {}, f"byte delta {len(res.output)-len(st.src)} != {len(edits)*(len(new)-len(tag))}"
    if tag in after.tags:
        return False, False, {}, f"old tag still present ({len(after.tags[tag])}x)"
    if len(after.tags.get(new, [])) != len(edits):
        return False, False, {}, "new tag occurrence count mismatch"

    before_sig, after_sig = st.signature("B0"), after.signature("B0")
    diff = before_sig.diff(after_sig)          # abstract view: raw guard text ignored
    non_tag_diff = {k: v for k, v in diff.items() if k != "tags"}
    return True, not non_tag_diff, non_tag_diff, ""


def run_case(tier: str, name: str, src: str, *, new_tag: str = "Zzz") -> Case:
    if not src.strip():
        # An empty program is a corpus artifact, not a parser limitation; keep it
        # out of the parse denominator instead of scoring it as a failure.
        return Case(tier=tier, name=name, chars=0, parsed=False, note="empty script")

    errs_only = extract(src, name)
    case = Case(tier=tier, name=name, chars=len(src), parsed=not errs_only.errors,
                errors=errs_only.errors[:2], devices=len(errs_only.devices),
                blocks=len(errs_only.blocks), tags=len(errs_only.tags))
    if not case.parsed:
        case.note = "parse failed"
        return case

    case.identity_ok = _identity(errs_only)

    tag = _pick_tag(errs_only)
    if tag is None:
        case.note = "no tags"
        return case
    case.retag_tag = tag
    case.retag_occurrences = len(errs_only.tags[tag])
    case.retag_service_tag = tag in {d.service for d in errs_only.devices}
    case.capability_from_tag = _capability_from_tag(errs_only, tag)
    ok, clean, diff, note = _retag(errs_only, tag, new_tag)
    case.retag_ok = ok
    case.signature_clean = clean
    case.signature_diff = diff
    case.note = note
    return case


def load_t2() -> list[tuple[str, str]]:
    with open(_T2, encoding="utf-8") as f:
        rows = json.load(f)
    return [(r.get("name", f"#{i}"), r["code"]) for i, r in enumerate(rows)]


def load_t1(limit: Optional[int] = None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(glob.glob(_T1_GLOB)):
        with open(path, encoding="utf-8") as f:
            pair = json.load(f)
        script = (pair.get("joi_block") or {}).get("script") or ""
        out.append((os.path.basename(path)[:-5], script))
        if limit and len(out) >= limit:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M-A: structure + splice fidelity check")
    ap.add_argument("--tier", choices=["t1", "t2", "both"], default="both")
    ap.add_argument("--limit", type=int, default=None, help="cap T1 cases")
    ap.add_argument("--json", help="write per-case results here")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    cases: list[Case] = []
    if args.tier in ("t2", "both"):
        for name, src in load_t2():
            cases.append(run_case("T2", name, src))
    if args.tier in ("t1", "both"):
        for name, src in load_t1(args.limit):
            cases.append(run_case("T1", name, src))

    for tier in ("T2", "T1"):
        all_sub = [c for c in cases if c.tier == tier]
        empty = [c for c in all_sub if c.note == "empty script"]
        sub = [c for c in all_sub if c.note != "empty script"]
        if not sub:
            continue
        parsed = [c for c in sub if c.parsed]
        tested = [c for c in parsed if c.retag_ok is not None]
        ident = [c for c in parsed if c.identity_ok]
        retag_ok = [c for c in tested if c.retag_ok]
        pure = [c for c in tested if not c.capability_from_tag]   # pure re-binding
        pure_clean = [c for c in pure if c.signature_clean]
        derived = [c for c in tested if c.capability_from_tag]     # capability rides on the tag
        derived_flagged = [c for c in derived if not c.signature_clean]

        print(f"\n=== {tier} ({len(sub)} scenarios"
              + (f", {len(empty)} empty skipped" if empty else "") + ") ===")
        print(f"  parse            {len(parsed)}/{len(sub)}")
        print(f"  identity splice  {len(ident)}/{len(parsed)}")
        print(f"  retag splice+L0  {len(retag_ok)}/{len(tested)}")
        print(f"  signature stable {len(pure_clean)}/{len(pure)} pure re-bindings"
              + (f"   [+{len(derived_flagged)}/{len(derived)} tag-derived capability correctly flagged]"
                 if derived else ""))
        print(f"  totals: {sum(c.devices for c in parsed)} device refs, "
              f"{sum(c.blocks for c in parsed)} blocks, "
              f"{sum(c.retag_occurrences for c in tested)} tag occurrences rewritten")

        bad = [c for c in sub if (not c.parsed) or c.identity_ok is False or c.retag_ok is False
               or (c.retag_ok and not c.signature_clean and not c.capability_from_tag)]
        if bad:
            print(f"  !! {len(bad)} problem cases:")
            for c in bad[:12]:
                reason = c.note or (c.errors[0] if c.errors else "signature drift")
                print(f"     {c.name:<24} {reason}"
                      + (f" diff={c.signature_diff}" if c.signature_diff else ""))
        if args.verbose:
            for c in sub:
                print(f"     {c.name:<24} parse={c.parsed} ident={c.identity_ok} "
                      f"retag={c.retag_ok}({c.retag_tag} x{c.retag_occurrences}) "
                      f"sig_clean={c.signature_clean}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([asdict(c) for c in cases], f, ensure_ascii=False, indent=1, default=str)
        print(f"\ndetail -> {args.json}")

    failures = [c for c in cases if c.parsed and (c.identity_ok is False or c.retag_ok is False)]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
