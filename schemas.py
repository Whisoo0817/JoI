"""API response schema for the JoI LLM pipeline.

The pipeline raises `JoiGenerationError` with a *string* `error_code`
(`"no_devices"`, `"no_suitable_device"`, …). For external consumers we expose
a stable numeric `JoiErrorCode` enum and a typed `JoiLLMResponse`. The string →
enum mapping lives in `ERROR_CODE_MAP`; IR/lowering internals are deliberately
collapsed into a single `REASONING_FAILED` so callers never need to know about
the IR layer — the specifics go into `error_message` / `details` instead.
"""
from enum import IntEnum
from typing import List, Optional, Union

from pydantic import BaseModel


class JoiErrorCode(IntEnum):
    """Mirrored in joi-agent's `agent/joi_llm_schemas.py` — change both together.

    INVALID_REQUEST and EMPTY_GENERATION are never produced here: joi-agent's MCP
    layer emits them for an HTTP 4xx from this service and for a 200 whose `code`
    came back blank. Grep finds no local producer; they are still live.

    1003 (MISSING_DESCRIPTOR) and 1004 (NO_SERVICES) named pre-IR stages that no
    longer exist. Both numbers are retired, not free — joi-agent's copy still
    defines them, and 1004 in particular must not be reused for something else
    until that copy is updated.
    """

    SUCCESS = 0

    # 1xxx: input / request
    INVALID_REQUEST = 1001     # emitted by joi-agent (HTTP 4xx from this service)
    NO_DEVICES = 1002          # request carried no connected devices at all

    # 12xx: device resolution
    # Devices were supplied, but none of them can carry out the command — whether
    # the category is absent, the named device isn't there, or device_resolve
    # found no service on them that fits. One code: the caller's remedy is the
    # same in every case. NOTE: joi-agent's mirror does not define 1201 yet, so a
    # proxied caller still sees 9999 until it does.
    NO_SUITABLE_DEVICE = 1201

    # 2xxx: vLLM / infrastructure
    VLLM_TIMEOUT = 2001
    VLLM_UNAVAILABLE = 2002
    EMPTY_GENERATION = 2003    # emitted by joi-agent (blank `code` in our 200)

    # 3xxx: code-generation reasoning (IR extract / validation / feasibility /
    # lowering are ALL folded here — external callers don't model the IR layer).
    REASONING_FAILED = 3001
    REASONING_OVERFLOW = 3002  # a model stage hit its token budget mid-output (truncated)

    # 9xxx: catch-all
    INTERNAL_ERROR = 9999


# Pipeline's internal string error_code → public JoiErrorCode. Every key below is
# raised somewhere in `joi/generate.py` or `pipeline_helpers.py`; keep it
# that way, and reach for `map_error_code()` rather than indexing this directly.
ERROR_CODE_MAP = {
    "no_devices": JoiErrorCode.NO_DEVICES,
    "no_suitable_device": JoiErrorCode.NO_SUITABLE_DEVICE,
    "reasoning_overflow": JoiErrorCode.REASONING_OVERFLOW,
}

# Internal codes that collapse into REASONING_FAILED: the model produced nothing
# usable. `ir_*` also matches the prefix rule in map_error_code(), but the
# catalog-validation codes it emits are dynamic, so the prefix rule is load-bearing.
_REASONING_CODES = {
    "reasoning_failed", "ir_invalid", "ir_rejected", "ir_infeasible",
    "missing_lowering_prompt",
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
