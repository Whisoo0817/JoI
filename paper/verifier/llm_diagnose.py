"""LLM-aided diagnose (paper §8.3).

An OPTIONAL enrichment layer on top of the deterministic retry message
(`diagnose.build_retry_message`). The deterministic hint is always the floor;
this module only APPENDS a targeted, evidence-grounded note that names the exact
fix. It branches by violation type because the available evidence differs:

  - L1 parse error  → there is NO trace (the script does not parse). Input is the
    JoI code + the exact parser error. The model pinpoints the broken fragment
    and the minimal syntactic fix.
  - L2 violation    → there IS a reference trace. Input is the IR, the JoI, and
    the per-obligation divergence (expected vs observed). The model names the
    exact wrong call/arg/timing and the correct value, lifted from `expected`.
    For timing_drift the correct tick count is pre-computed so the regeneration
    only has to copy a number (the failure mode we saw was the model oscillating
    between 10x-too-small and 10x-too-large when only told to "recompute").

Hurt-guard: the LLM text is additive (never replaces the deterministic floor),
length-capped, and reasoning tags are stripped. A contradiction check drops the
LLM note if it argues the opposite direction of the detected violation kinds.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from paper.verifier.l1_static import Violation as L1Violation
from paper.verifier.l2_runtime import L2Violation


# Inference callable: (key, user_input, *, system, max_tokens) -> str
InferFn = Callable[..., str]

_MAX_HINT_CHARS = 700
_DEFAULT_POLL_MS = 100


_SYSTEM_PARSE = (
    "You are a JoI syntax fixer. The previous JoI script failed to parse. You are "
    "given the script and the EXACT parser error (token + position). Find the single "
    "smallest syntactic fix.\n"
    "Quote the broken fragment verbatim, then give the corrected fragment. Be concrete "
    "about where it is. Do not restate the whole script; do not add new behavior.\n\n"
    "JoI grammar reminders:\n"
    "- A condition must be a parenthesized boolean expression: `if (<expr>) { ... }`.\n"
    "- Quantified selectors `all(#Tag)` / `any(#Tag)` are valid as the SUBJECT of a "
    "statement or inside an expression, e.g. `if (any(#Pump).switch == true) { ... }` — "
    "the quantifier goes INSIDE the condition parentheses, not before `(`.\n"
    "- A bare attribute read (e.g. `(#Lock).doorLockState`) is an expression, not a "
    "statement; it must be used in a condition or assigned to a variable.\n\n"
    "Output: 1-3 short sentences naming the broken fragment and the exact corrected "
    "form. No preamble, no code fences."
)

_SYSTEM_L2 = (
    "You are a JoI lowering fixer. The previous JoI runs but DIVERGES from the intended "
    "specification (the IR). You are given the IR, the JoI script, and the exact "
    "divergences as expected-vs-observed facts. For each divergence, state the concrete "
    "edit to the JoI, taking the correct value from `expected`.\n"
    "- arg_mismatch: the call has the wrong arguments. Change the observed args to the "
    "expected args, in order. Keep every argument (do not drop trailing ones).\n"
    "- missing_call: a required call was dropped. Add it at the named IR position.\n"
    "- extra_call: a call not in the spec was emitted. Remove it or tighten its guard.\n"
    "- timing_drift: a polling-counter threshold (`hold_ticks >= N`) or a duration is "
    "wrong. The facts give the EXACT target tick count and name the line to change — "
    "substitute that number verbatim; do NOT recompute, and do NOT touch any "
    "`delay(...)` or `period` value the facts do not mention.\n\n"
    "Stay consistent with the listed violation kinds — do not propose adding a call for "
    "an arg_mismatch, or removing one for a missing_call.\n"
    "Output: a short bullet list (one bullet per divergence) of concrete edits. No "
    "preamble, no code fences."
)


def _strip(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?Reasoning>", "", text)
    return text.strip()


def _poll_ms_from_ir(ir: dict) -> int:
    """Best-effort polling period (ms) for tick math. Defaults to 100ms unless a
    cycle op names a sub-second period that the wrapper would adopt."""
    try:
        for s in (ir.get("timeline") or []):
            if isinstance(s, dict) and s.get("op") == "cycle":
                p = str(s.get("period", "")).strip().upper()
                m = re.match(r"(\d+)\s*MSEC", p)
                if m:
                    return max(1, int(m.group(1)))
    except Exception:
        pass
    return _DEFAULT_POLL_MS


def _parse_input(script: str, parse_viols: list[L1Violation]) -> str:
    errs = "\n".join(f"- {v.message}" for v in parse_viols)
    return (
        f"[Parser errors]\n{errs}\n\n"
        f"[JoI script]\n{script}\n"
    )


_UNIT_MS = {"MSEC": 1, "SEC": 1000, "MIN": 60000, "HOUR": 3600000}


def _dur_ms(s) -> Optional[int]:
    m = re.match(r"\s*(\d+)\s*(MSEC|SEC|MIN|HOUR)", str(s).upper())
    return int(m.group(1)) * _UNIT_MS[m.group(2)] if m else None


def _wait_for_dur(ir: dict) -> Optional[str]:
    """The `for` duration string of the first `wait` op carrying one (the sustain
    window). Returns None if the IR has no sustained-condition wait."""
    def walk(steps):
        for s in steps or []:
            if not isinstance(s, dict):
                continue
            if s.get("op") == "wait" and s.get("for"):
                return s["for"]
            for k in ("body", "then", "else"):
                if isinstance(s.get(k), list):
                    r = walk(s[k])
                    if r:
                        return r
        return None
    return walk(ir.get("timeline") or [])


def _l2_input(ir: dict, joi_block: dict, l2: list[L2Violation]) -> str:
    script = (joi_block or {}).get("script", "") or ""
    # Convert with the period the GENERATED script actually polls at (not the
    # IR's) — the counter threshold is `for_ms / script_period`.
    period = (joi_block or {}).get("period") or _poll_ms_from_ir(ir) or _DEFAULT_POLL_MS
    timing = [v for v in l2 if v.kind == "timing_drift"]
    facts: list[str] = []

    # Sustained-condition consolidation: when the IR has a `wait.for` window and
    # the script uses a `hold_ticks` polling counter, ALL timing_drift come from
    # one wrong threshold. Compute the exact target from the sustain duration and
    # the script's own period, name the current value, and tell the model to
    # substitute it — leaving any `delay(...)` / `period` untouched (they are
    # already correct; fixing the threshold corrects every downstream call time).
    handled_timing = False
    if timing:
        for_dur = _wait_for_dur(ir)
        for_ms = _dur_ms(for_dur) if for_dur else None
        cur = re.findall(r"hold_ticks\s*>=\s*(\d+)", script)
        if for_ms and cur:
            tgt = round(for_ms / period)
            facts.append(
                f"- timing_drift (sustain window): the `wait.for` window is {for_dur} "
                f"= {for_ms}ms. The script polls at period={period}ms, so the counter "
                f"threshold MUST be {for_ms} / {period} = {tgt} ticks. Change "
                f"`hold_ticks >= {cur[0]}` to `hold_ticks >= {tgt}` exactly. Do NOT "
                f"change any `delay(...)` or the `period` value — they are already "
                f"correct, and fixing this threshold corrects every timing_drift here."
            )
            handled_timing = True

    for v in l2:
        if v.kind == "timing_drift":
            if handled_timing:
                continue
            exp = (v.expected or {}).get("t_ms")
            obs = (v.observed or {}).get("t_ms")
            line = f"- timing_drift on `{v.target}` (IR path {v.ir_path})."
            if isinstance(exp, (int, float)):
                tgt = round(int(exp) / period)
                line += (f" Must fire at {int(exp)}ms = {tgt} ticks at period={period}ms. "
                         f"Set the controlling threshold/duration to EXACTLY {tgt} ticks.")
            if isinstance(obs, (int, float)):
                line += f" (Currently fires at {int(obs)}ms = {round(int(obs)/period)} ticks — wrong.)"
            facts.append(line)
        elif v.kind == "arg_mismatch":
            facts.append(f"- arg_mismatch on `{v.target}`: expected args {v.expected}, "
                         f"observed {v.observed}. Use the expected args.")
        elif v.kind == "missing_call":
            facts.append(f"- missing_call `{v.target}` at IR path {v.ir_path}: the IR "
                         f"requires {v.expected} here but the JoI emitted nothing.")
        elif v.kind == "extra_call":
            facts.append(f"- extra_call `{v.target}` at IR path {v.ir_path}: the JoI "
                         f"emitted {v.observed} but the IR has no such call here.")
        else:
            facts.append(f"- {v.kind} on `{v.target}` (IR path {v.ir_path}): "
                         f"expected={v.expected} observed={v.observed}")
    return (
        "[IR]\n" + _compact_ir(ir) + "\n\n"
        "[JoI script]\n" + script + "\n\n"
        "[Divergences]\n" + "\n".join(facts) + "\n"
    )


def _compact_ir(ir: dict) -> str:
    import json
    tl = ir.get("timeline", ir)
    try:
        return json.dumps(tl, ensure_ascii=False)
    except Exception:
        return str(tl)


def _contradicts(text: str, l2: list[L2Violation]) -> bool:
    """Light hurt-guard: drop the note if it argues the opposite direction of the
    sole detected kind (e.g. tells the model to ADD a call when the only problem
    is an extra_call, or to REMOVE one when the only problem is a missing_call)."""
    kinds = {v.kind for v in l2}
    low = text.lower()
    if kinds == {"extra_call"} and re.search(r"\badd\b|\binsert\b|\bemit a", low):
        return True
    if kinds == {"missing_call"} and re.search(r"\bremove\b|\bdelete\b|\bdrop\b", low):
        return True
    return False


def make_llm_diagnoser(infer_fn: InferFn) -> Callable[..., Optional[str]]:
    """Return a `diagnose(ir, joi_block, l1, l2) -> Optional[str]` closure that
    produces an additive retry note via `infer_fn`. Returns None on no-op / failure
    so the harness silently falls back to the deterministic hint."""

    def diagnose(ir: dict, joi_block: dict,
                 l1: list[L1Violation], l2: list[L2Violation]) -> Optional[str]:
        script = (joi_block or {}).get("script", "") or ""
        try:
            parse_v = [v for v in (l1 or []) if v.kind == "parse"]
            if parse_v:
                raw = infer_fn("llm_diagnose", _parse_input(script, parse_v),
                               system=_SYSTEM_PARSE, max_tokens=300)
                note = _strip(raw)[:_MAX_HINT_CHARS]
                if not note:
                    return None
                return "## Targeted syntax diagnosis\n" + note
            if l2:
                raw = infer_fn("llm_diagnose", _l2_input(ir, joi_block, l2),
                               system=_SYSTEM_L2, max_tokens=400)
                note = _strip(raw)[:_MAX_HINT_CHARS]
                if not note or _contradicts(note, l2):
                    return None
                return "## Targeted divergence diagnosis\n" + note
        except Exception:
            return None
        return None

    return diagnose
