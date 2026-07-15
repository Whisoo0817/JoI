"""Structure-routed lowering example bank (paper §7).

The lowering prompt is assembled as joi_common.md + the example block for the
IR's structural class (paper §5, feasibility.structural_class). The bank maps
class -> example block. It is SEEDED with the per-class blocks that ship in
files/ (joi_noncycle.md / joi_cycle.md), so prompt assembly is byte-identical
to loading those files directly. Pairs that pass the verifier can additionally
be accumulated under their class with `add()`; accumulated pairs are persisted
to JOI_EXAMPLE_BANK (JSON) and injected only when that env var is set, so the
default pipeline behavior is unchanged.

Routing affects only the generator's prompt; the verifier's accept/reject
decision never reads the bank.
"""
from __future__ import annotations

import json
import os
from typing import Any

from paper.feasibility import lowering_bucket, structural_class

_BANK_ENV = "JOI_EXAMPLE_BANK"


def class_of(ir: Any) -> str:
    """The routing key for an IR under the current 2-class instantiation."""
    return lowering_bucket(ir)


def seed_block(bucket: str, prompts: dict) -> str:
    """The seeded example block for `bucket` (the shipped joi_<bucket>.md)."""
    block = prompts.get(f"joi_{bucket}")
    if not block:
        raise FileNotFoundError(f"joi_{bucket}.md not loaded by PROMPTS")
    return block


def _bank_path() -> str | None:
    return os.environ.get(_BANK_ENV) or None


def _load() -> dict:
    path = _bank_path()
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def add(ir: Any, joi_text: str, meta: dict | None = None) -> None:
    """Record a verifier-passed (IR, JoI) pair under its structural class.

    No-op unless JOI_EXAMPLE_BANK is set (keeps default runs byte-stable)."""
    path = _bank_path()
    if not path:
        return
    bank = _load()
    cls = class_of(ir)
    entry = {
        "class": cls,
        "signature": list(structural_class(ir)),
        "ir": ir,
        "joi": joi_text,
    }
    if meta:
        entry["meta"] = meta
    bank.setdefault(cls, []).append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=1)


def examples_for(ir: Any, prompts: dict, k: int | None = None) -> str:
    """The example block routed by the IR's structural class.

    Always includes the seeded block for the class. When JOI_EXAMPLE_BANK is
    set and holds accumulated pairs for the class, up to `k` of the most
    recent ones are appended after the seed block."""
    bucket = class_of(ir)
    block = seed_block(bucket, prompts)
    accumulated = _load().get(bucket) or []
    if accumulated:
        chosen = accumulated[-(k or len(accumulated)):]
        extra = "\n\n".join(
            "### Verified example\nIR:\n" + json.dumps(e["ir"], ensure_ascii=False)
            + "\nJoI:\n" + e["joi"] for e in chosen
        )
        block = block + "\n\n" + extra
    return block
