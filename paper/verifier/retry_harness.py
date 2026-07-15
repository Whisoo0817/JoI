"""Retry harness (paper §6.4 R1).

Orchestrates: run L1 + L2 against a JoI candidate. If violations, build a
retry message and call the user-supplied `lower_fn` again with the
augmented prompt context. Repeat up to `max_attempts`.

Decoupled from `paper/run_local_ir.py` on purpose — the test harness wants
to inject a fake lowering function. The real pipeline wires this in by
passing a closure that knows how to call `joi_from_ir.lower(ir, hints=...)`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from paper.verifier.diagnose import RetryMessage, build_retry_message
from paper.verifier.l1_static import Violation as L1Violation
from paper.verifier.l1_static import analyze as l1_analyze
from paper.verifier.l2_runtime import L2Report, L2Violation, check as l2_check


# Type of the lowering callable. Takes the IR plus an optional `hints` string
# (the retry prompt block) and returns the joi_block dict.
LowerFn = Callable[[dict, Optional[str]], dict]


@dataclass
class AttemptRecord:
    attempt: int
    joi_block: dict
    l1: list[L1Violation] = field(default_factory=list)
    l2: list[L2Violation] = field(default_factory=list)
    retry_message: Optional[RetryMessage] = None


@dataclass
class HarnessResult:
    accepted: bool
    final_joi: Optional[dict]
    attempts: list[AttemptRecord]


def run(
    ir: dict,
    lower_fn: LowerFn,
    connected_devices: Optional[dict] = None,
    catalog: Optional[dict] = None,
    max_attempts: int = 3,
    diagnose_fn: Optional[Callable] = None,
) -> HarnessResult:
    """Run lowering with verification + retry up to `max_attempts` times.

    `diagnose_fn(ir, joi_block, l1, l2) -> Optional[str]` is the optional
    LLM-aided diagnoser (paper §8.3). Its note is APPENDED to the deterministic
    retry message (additive floor) — it never replaces it, and any failure inside
    it is swallowed so the deterministic hint still applies."""
    attempts: list[AttemptRecord] = []
    hints: Optional[str] = None
    final_joi: Optional[dict] = None

    for n in range(1, max_attempts + 1):
        joi_block = lower_fn(ir, hints)
        final_joi = joi_block

        l1 = l1_analyze(joi_block, connected_devices=connected_devices, catalog=catalog)
        # Only run L2 if L1 is clean — running L2 on a script with parse errors
        # would just surface a sim crash. L1 has to pass first.
        l2_list: list[L2Violation] = []
        if not l1:
            report: L2Report = l2_check(ir, joi_block, catalog=catalog)
            l2_list = report.violations

        msg = build_retry_message(l1=l1, l2=l2_list)

        # LLM-aided diagnose (optional): append a targeted note onto the
        # deterministic floor. Never fatal — diagnose_fn returns None on failure.
        if msg is not None and diagnose_fn is not None:
            note = diagnose_fn(ir, joi_block, l1, l2_list)
            if note:
                msg.prompt_block = msg.prompt_block.rstrip() + "\n\n" + note + "\n"

        attempts.append(AttemptRecord(
            attempt=n, joi_block=joi_block, l1=l1, l2=l2_list, retry_message=msg,
        ))

        if msg is None:
            return HarnessResult(accepted=True, final_joi=joi_block, attempts=attempts)
        hints = msg.prompt_block

    return HarnessResult(accepted=False, final_joi=final_joi, attempts=attempts)
