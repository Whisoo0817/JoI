"""API response schema for the JoI LLM pipeline (paper deployment).

The pipeline raises `JoiGenerationError` with a *string* `error_code`
(`"no_services"`, `"device_not_connected"`, …). For external consumers we expose
a stable numeric `JoiErrorCode` enum and a typed `JoiLLMResponse`. The string →
enum mapping lives in `ERROR_CODE_MAP`; IR/lowering internals are deliberately
collapsed into a single `REASONING_FAILED` so callers never need to know about
the IR layer — the specifics go into `error_message` / `details` instead.
"""
from enum import IntEnum
from typing import List, Optional, Union

from pydantic import BaseModel


class JoiErrorCode(IntEnum):
    SUCCESS = 0

    # 1xxx: input / request
    INVALID_REQUEST = 1001
    NO_DEVICES = 1002          # no connected devices supplied
    NO_SERVICES = 1004         # planner found no action for the command
    MULTIPLE_SCENARIOS = 1005  # command bundles ≥2 independent trigger→action scenarios
    AMBIGUOUS_CONDITION = 1006  # magnitude condition with no concrete threshold (더우면/높아지면…)

    # 12xx: device resolution
    DEVICE_NOT_CONNECTED = 1201  # required device category not connected at all
    DEVICE_NOT_IN_SCOPE = 1202   # category exists but none in the named location/scope

    # 2xxx: vLLM / infrastructure
    VLLM_TIMEOUT = 2001
    VLLM_UNAVAILABLE = 2002
    EMPTY_GENERATION = 2003

    # 3xxx: code-generation reasoning (IR extract / validation / feasibility /
    # lowering are ALL folded here — external callers don't model the IR layer).
    REASONING_FAILED = 3001
    REASONING_OVERFLOW = 3002  # a model stage hit its token budget mid-output (truncated)

    # 9xxx: catch-all
    INTERNAL_ERROR = 9999


# Pipeline's internal string error_code → public JoiErrorCode.
# Anything not listed (the IR/lowering codes: ir_invalid, ir_rejected,
# ir_infeasible, missing_lowering_prompt, catalog-validation codes, …) maps to
# REASONING_FAILED via ERROR_CODE_MAP.get(code, REASONING_FAILED) — but ONLY for
# codes that originate downstream of planning. Use `map_error_code()` so unknown
# pre-planning codes still surface as INTERNAL_ERROR rather than silently
# masquerading as a reasoning failure.
ERROR_CODE_MAP = {
    "no_devices": JoiErrorCode.NO_DEVICES,
    "no_services": JoiErrorCode.NO_SERVICES,
    "device_not_connected": JoiErrorCode.DEVICE_NOT_CONNECTED,
    "no_device_in_scope": JoiErrorCode.DEVICE_NOT_IN_SCOPE,
    "multiple_scenarios": JoiErrorCode.MULTIPLE_SCENARIOS,
    "ambiguous_condition": JoiErrorCode.AMBIGUOUS_CONDITION,
    "reasoning_overflow": JoiErrorCode.REASONING_OVERFLOW,
}

# Internal codes that should collapse into REASONING_FAILED (IR + lowering +
# device-match producing no parseable result — a model failure, not a scope miss).
_REASONING_CODES = {
    "ir_invalid", "ir_rejected", "ir_infeasible", "missing_lowering_prompt",
    "service_not_in_catalog", "member_not_in_service",
    "gt_ir_load_failed", "device_match_failed",
}


def map_error_code(raw: str) -> "JoiErrorCode":
    """Map a pipeline string `error_code` to a public JoiErrorCode.

    - Known input/device codes → their explicit enum.
    - IR/lowering codes (and any catalog-validation primary code) → REASONING_FAILED.
    - Anything else → INTERNAL_ERROR (unexpected; do not hide it as reasoning).
    """
    if not raw:
        return JoiErrorCode.INTERNAL_ERROR
    if raw in ERROR_CODE_MAP:
        return ERROR_CODE_MAP[raw]
    if raw in _REASONING_CODES:
        return JoiErrorCode.REASONING_FAILED
    # Catalog validation emits a dynamic `primary` code; treat unknown
    # downstream-looking codes as reasoning failures only if they smell like IR.
    if raw.startswith("ir_") or "catalog" in raw or "lowering" in raw:
        return JoiErrorCode.REASONING_FAILED
    return JoiErrorCode.INTERNAL_ERROR


class JoiCodeItem(BaseModel):
    """One generated JoI scenario. Mirrors the JSON the lowering stage emits."""
    name: str = "Scenario"
    cron: str = ""
    period: int = -1
    # Field name is `code` (the scenario body) to match the joi-agent proxy's
    # JoiCodeItem. The pipeline's raw dict still uses key "script" (see _code_item).
    code: str = ""


class JoiLog(BaseModel):
    response_time: Optional[str] = None
    translated_sentence: Optional[str] = None
    logs: str = ""


class JoiLLMResponse(BaseModel):
    success: bool
    error_code: int = JoiErrorCode.SUCCESS
    error_message: str = ""
    # Free-form detail string for failures: which stage / what was missing.
    # External callers read `error_code`; `details` is for humans debugging.
    details: str = ""

    # Structured generated code (None on failure). A list of `JoiCodeItem` so
    # callers get name/cron/period/script as typed fields. Emitted as a list
    # (not a single object) to match the joi-agent proxy's JoiLLMResponse,
    # which validates `code` as Union[List[JoiCodeItem], str].
    code: Optional[Union[List[JoiCodeItem], str]] = None
    command: Optional[str] = None
    log: Optional[JoiLog] = None
