"""adapt — scenario adaptation pipeline (OVLA v2).

Stages (see paper_v2/ideas.md §9):
    ① structure.py   parse + block signatures + role reference table (char spans)
    ② template.py    skeleton + role slots + contract stubs        [M-B]
    ③ effects.py     effect-annotation catalog                     [M-B]
    ④ bind.py        candidate enumeration + contract matching     [M-C]
    ⑤ patch.py       typed edits -> splice (original bytes kept)
    ⑥ check.py       syntax / splice invariant / contract diff / vacuity  [M-D]
    ⑦ certify.py     SMT obligations; contingency.py: failure table [M-E]

Design lock: stage ⑤ never re-emits the program. It replaces byte spans in the
original source, so every byte outside an edit footprint is identical by
construction (verification ladder L1).

Submodules are imported lazily so `python3 -m adapt.structure` stays clean.
"""

from typing import TYPE_CHECKING

__all__ = [
    "Span", "Structure", "extract", "parse_errors",
    "Edit", "apply_edits", "verify_splice", "apply_and_check",
]

if TYPE_CHECKING:  # pragma: no cover
    from .structure import Span, Structure, extract, parse_errors
    from .patch import Edit, apply_edits, apply_and_check, verify_splice


def __getattr__(name: str):
    if name in ("Span", "Structure", "extract", "parse_errors"):
        from . import structure
        return getattr(structure, name)
    if name in ("Edit", "apply_edits", "verify_splice", "apply_and_check"):
        from . import patch
        return getattr(patch, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
