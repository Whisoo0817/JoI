"""Diagnose: convert L1/L2 violations into retry messages (paper §6.4 R1).

`build_retry_message(ir, l1, l2)` produces a structured message — both a
human-readable summary and an LLM-targeted instruction block — that the
retry harness feeds back into the lowering prompt. The intent is to be
*specific*: name the IR feature (path), name the kind of fix, and avoid
generic "try again" loops.

Messages are grouped by kind so the prompt sees one bullet per distinct
problem. Multiple violations of the same kind/target collapse to one bullet
with a count.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from paper.verifier.l1_static import Violation as L1Violation
from paper.verifier.l2_runtime import L2Violation


@dataclass
class RetryMessage:
    """Structured retry feedback. `prompt_block` is appended to the lowering
    prompt; `summary` is for logs / user display."""
    summary: str
    prompt_block: str
    bullet_count: int


# ── Per-kind templates ──────────────────────────────────────────────────────

_L1_HINTS = {
    "parse": "The previous JoI script failed to parse. Fix the syntax error.",
    "catalog_service": "The selector references a service not in connected_devices. "
                       "Use one of the available services instead.",
    "catalog_method": "The method does not exist for this service in the catalog. "
                      "Use the exact method id from the service catalog.",
    "catalog_attr": "The attribute does not exist for this service in the catalog. "
                    "Use the exact attribute id.",
    "cron_slot": "The cron expression has an out-of-range slot.",
    "use_before_init": "A variable is assigned with `=` before any `:=` initializer. "
                       "Initialize with `:=` first.",
    "selector_form": "Selector form is invalid. Use `(#Tag)`, `all(#Tag)`, or `any(#Tag)`.",
}

_L2_HINTS = {
    "missing_call": "The lowered JoI did not emit a required call at this IR step. "
                    "Each `call` op in the IR must lower to its OWN JoI statement — "
                    "do not collapse two sequential calls into one. If the IR has "
                    "`call A; call B`, emit two separate statements (assign A's return "
                    "to a variable if B references it via `$var`).",
    "extra_call": "The lowered JoI emitted a call that the IR does not require. "
                  "Remove the spurious call or restrict its guard.",
    "arg_mismatch": "The lowered JoI emitted the right method but with wrong arguments. "
                    "Match the IR's args dict positionally per the catalog order. "
                    "Do NOT drop or empty the argument list — copy each value from "
                    "the IR's args dict, including string literals.",
    "trace_empty": "The lowered JoI did not emit anything for a scenario where the IR does. "
                   "Check that the top-level guard / cron / period actually fires.",
    "timing_drift": "The lowered JoI emitted the right call but at the wrong time. "
                    "This usually means a duration was scaled incorrectly — most often "
                    "a `wait.for` sustain converted to tick-count off by a factor of 10 "
                    "(e.g. 30 SEC lowered as 3000 ticks instead of 300 at the default "
                    "100ms polling period), or a `delay`/`cycle.period` unit mismatch. "
                    "Recompute: `ticks = duration_ms / polling_period_ms`. The polling "
                    "period defaults to 100ms when the IR does not name a different "
                    "cadence; if the script sets `period: 100`, then 30 SEC = 30000/100 "
                    "= 300 ticks (NOT 3000).",
}


# ── Builder ─────────────────────────────────────────────────────────────────

def build_retry_message(
    l1: Optional[list[L1Violation]] = None,
    l2: Optional[list[L2Violation]] = None,
) -> Optional[RetryMessage]:
    """Build a retry message. Returns None if there are no violations."""
    l1 = l1 or []
    l2 = l2 or []
    if not l1 and not l2:
        return None

    # Group L1 by (kind, message-prefix) and L2 by (kind, ir_path, target)
    l1_groups: "OrderedDict[tuple, list[L1Violation]]" = OrderedDict()
    for v in l1:
        key = (v.kind, v.where)
        l1_groups.setdefault(key, []).append(v)

    l2_groups: "OrderedDict[tuple, list[L2Violation]]" = OrderedDict()
    for v in l2:
        key = (v.kind, v.ir_path, v.target)
        l2_groups.setdefault(key, []).append(v)

    bullets: list[str] = []
    summary_lines: list[str] = []

    for (kind, where), vs in l1_groups.items():
        hint = _L1_HINTS.get(kind, "")
        head = f"[L1 {kind}] at {where}: {vs[0].message}"
        if len(vs) > 1:
            head += f"  (and {len(vs) - 1} similar)"
        bullets.append(f"- {head}\n  → {hint}" if hint else f"- {head}")
        summary_lines.append(f"L1 {kind} @ {where}")

    for (kind, ir_path, target), vs in l2_groups.items():
        hint = _L2_HINTS.get(kind, "")
        head = f"[L2 {kind}] IR path `{ir_path}` target `{target}`"
        if vs and vs[0].expected is not None:
            head += f"  expected={vs[0].expected}"
        if vs and vs[0].observed is not None:
            head += f"  observed={vs[0].observed}"
        if len(vs) > 1:
            head += f"  (×{len(vs)})"
        bullets.append(f"- {head}\n  → {hint}" if hint else f"- {head}")
        summary_lines.append(f"L2 {kind} @ {ir_path}: {target}")

    prompt_block = (
        "## Previous attempt failed verification — fix and retry\n\n"
        "Below are the obligations from the validated IR that the previous "
        "JoI lowering violated. Each bullet names the IR path that owns the "
        "obligation and the kind of fix required. Address every bullet.\n\n"
        + "\n".join(bullets)
        + "\n\nProduce a corrected JoI block.\n"
    )

    return RetryMessage(
        summary="; ".join(summary_lines),
        prompt_block=prompt_block,
        bullet_count=len(bullets),
    )
