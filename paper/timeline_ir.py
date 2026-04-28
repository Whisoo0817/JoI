"""Timeline IR: schema, extraction (NL → IR), readable rendering.

This module defines the Timeline IR used by the new reactive-DSL pipeline.
Pipeline stages:
    1. NL (English) → Timeline IR          [extract_ir]  — LLM call
    2. Timeline IR → Korean readable text  [ir_to_readable] — deterministic
    3. Timeline IR → JoI code              [NOT YET]     — planned

Timeline IR shape:
    {
        "devices_referenced": ["Light_1", ...],
        "timeline": [ <step>, <step>, ... ]
    }

Step ops: start_at | wait | delay | read | call | if | cycle | break.
See files/timeline_ir_extractor.md for the full grammar.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from config import get_client, get_model_id


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_EXTRACTOR_PROMPT_PATH = os.path.join(_BASE_DIR, "timeline_ir_extractor.md")
_TRANSLATION_PROMPT_PATH = os.path.join(_BASE_DIR, "..", "files", "translation.md")

_STEP_OPS = {"start_at", "wait", "delay", "read", "call", "if", "cycle", "break"}
_EDGE_VALUES = {"none", "rising", "falling"}
_ANCHOR_VALUES = {"now", "cron"}

# Expression marker characters — if an args-value string contains any of these,
# treat it as an expression to be evaluated at runtime (convention β).
_EXPR_MARKERS = set(".$+-*/()<>=!&|")


# ── Schema validation ────────────────────────────────────────────────────────

class IRValidationError(ValueError):
    """Raised when a Timeline IR object fails structural validation."""


def validate_ir(ir: Any) -> None:
    """Raise IRValidationError if `ir` does not conform to the Timeline IR schema.

    Validates recursively: top-level shape, each step's op/required fields,
    cycle bodies contain at least one delay, branches have step lists, etc.
    Does NOT validate expressions semantically (parser comes later).
    """
    if not isinstance(ir, dict):
        raise IRValidationError(f"IR must be a dict, got {type(ir).__name__}")

    if "error" in ir:
        # extractor rejection path — still structurally valid output
        return

    if "timeline" not in ir or not isinstance(ir["timeline"], list):
        raise IRValidationError("IR must contain 'timeline' list")

    for i, step in enumerate(ir["timeline"]):
        try:
            _validate_step(step)
        except IRValidationError as e:
            raise IRValidationError(f"timeline[{i}]: {e}") from None

    # Timeline-level rule: first step should be start_at.
    first = ir["timeline"][0] if ir["timeline"] else None
    if first is None or first.get("op") != "start_at":
        raise IRValidationError("timeline[0] must be a start_at step")


def _validate_step(step: Any) -> None:
    if not isinstance(step, dict):
        raise IRValidationError(f"step must be dict, got {type(step).__name__}")
    op = step.get("op")
    if op not in _STEP_OPS:
        raise IRValidationError(f"unknown op '{op}'")

    if op == "start_at":
        anchor = step.get("anchor")
        if anchor not in _ANCHOR_VALUES:
            raise IRValidationError(f"start_at.anchor must be one of {_ANCHOR_VALUES}")
        if anchor == "cron" and not isinstance(step.get("cron"), str):
            raise IRValidationError("start_at anchor=cron requires 'cron' string")

    elif op == "wait":
        if not isinstance(step.get("cond"), str):
            raise IRValidationError("wait requires 'cond' string")
        if step.get("edge", "none") not in _EDGE_VALUES:
            raise IRValidationError(f"wait.edge must be one of {_EDGE_VALUES}")

    elif op == "delay":
        ms = step.get("ms")
        if not isinstance(ms, int) or ms < 0:
            raise IRValidationError("delay.ms must be non-negative int")

    elif op == "read":
        if not isinstance(step.get("var"), str) or not isinstance(step.get("src"), str):
            raise IRValidationError("read requires 'var' and 'src' strings")

    elif op == "call":
        if not isinstance(step.get("target"), str):
            raise IRValidationError("call requires 'target' string")
        if not isinstance(step.get("args", {}), dict):
            raise IRValidationError("call.args must be dict")

    elif op == "if":
        if not isinstance(step.get("cond"), str):
            raise IRValidationError("if requires 'cond' string")
        for branch in ("then", "else"):
            body = step.get(branch, [])
            if not isinstance(body, list):
                raise IRValidationError(f"if.{branch} must be list")
            for j, s in enumerate(body):
                try:
                    _validate_step(s)
                except IRValidationError as e:
                    raise IRValidationError(f"{branch}[{j}]: {e}") from None

    elif op == "cycle":
        body = step.get("body", [])
        if not isinstance(body, list) or not body:
            raise IRValidationError("cycle.body must be non-empty list")
        if step.get("until") is not None and not isinstance(step["until"], str):
            raise IRValidationError("cycle.until must be string or null")
        # cycle MUST have some cadence source: either a delay step OR an
        # edge-triggered wait (rising/falling). A delay-less cycle with only a
        # level wait or no wait at all would spin unbounded — that's rejected.
        if not _body_has_cadence(body):
            raise IRValidationError(
                "cycle.body must contain at least one delay or edge-triggered wait"
            )
        for j, s in enumerate(body):
            try:
                _validate_step(s)
            except IRValidationError as e:
                raise IRValidationError(f"body[{j}]: {e}") from None

    elif op == "break":
        pass  # no fields


def _body_has_cadence(steps: list) -> bool:
    """True if `steps` contains a delay or an edge-triggered wait.

    A cycle needs some cadence source to avoid unbounded spinning:
      - `delay` provides time-based cadence.
      - `wait(edge="rising"|"falling")` provides event-based cadence.
      - `wait(edge="none")` alone does NOT (level check would re-pass instantly).

    Traverses into `if` branches but NOT into nested `cycle` bodies (those have
    their own cadence requirement checked independently).
    """
    for s in steps:
        if not isinstance(s, dict):
            continue
        op = s.get("op")
        if op == "delay":
            return True
        if op == "wait" and s.get("edge") in ("rising", "falling"):
            return True
        if op == "if":
            if _body_has_cadence(s.get("then", [])) or _body_has_cadence(s.get("else", [])):
                return True
    return False


# ── Expression helpers ───────────────────────────────────────────────────────

def is_expression_string(value: Any) -> bool:
    """True iff a string arg-value should be interpreted as an expression.

    Convention β: contains any of `.`, `$`, or arithmetic/comparison/logical ops.
    """
    if not isinstance(value, str):
        return False
    return any(c in _EXPR_MARKERS for c in value)


# ── Extraction (NL → IR) ─────────────────────────────────────────────────────

def _load_extractor_prompt() -> str:
    with open(_EXTRACTOR_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _load_translation_prompt() -> str:
    with open(_TRANSLATION_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def translate_to_english(
    korean_command: str,
    base_url: str | None = None,
    debug: bool = False,
) -> str:
    """Translate a Korean IoT command to English using the K→EN prompt.

    Uses files/translation.md which handles morphological cues (if/when/whenever,
    마다 disambiguation, etc.) so the extractor receives clean English input.
    """
    system = _load_translation_prompt()
    client = get_client(base_url)
    model = get_model_id(client)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": korean_command},
        ],
        temperature=0.0,
        max_tokens=512,
        stream=False,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    en = (response.choices[0].message.content or "").strip()
    if debug:
        print(f"[timeline_ir] translated: {en}")
    return en


def _is_korean(text: str) -> bool:
    """Heuristic: any Hangul codepoint present?"""
    return any("\uac00" <= ch <= "\ud7a3" or "\u3130" <= ch <= "\u318f" for ch in text)


def _format_services_block(devices: dict) -> str:
    """Render a compact [Services] block for the prompt.

    Input `devices` is the runtime `connected_devices` dict from context.
    Shape expected:
        { device_id: {"tags": [...], "category": [...], "attrs": {...}, "methods": [...]} }
    We only produce a lean listing; downstream prompt handles parsing.
    """
    if not devices:
        return "(no devices connected)"
    lines = []
    for dev_id, info in devices.items():
        if not isinstance(info, dict):
            lines.append(f"- {dev_id}")
            continue
        tags = info.get("tags", [])
        cats = info.get("category", [])
        lines.append(f"- {dev_id}  tags={tags}  categories={cats}")
        attrs = info.get("attrs") or info.get("values")
        if attrs:
            lines.append(f"    attrs: {attrs}")
        methods = info.get("methods") or info.get("functions")
        if methods:
            lines.append(f"    methods: {methods}")
    return "\n".join(lines)


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` fences if the model wrapped output despite instructions."""
    s = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.DOTALL)
    return m.group(1) if m else s


def extract_ir(
    command: str,
    devices: dict | str,
    base_url: str | None = None,
    debug: bool = False,
    auto_translate: bool = True,
    augmentations: str | None = None,
) -> dict:
    """Call the local LLM to extract a Timeline IR from a command.

    If `command` contains Korean characters and `auto_translate` is True, the
    command is first translated to English via the translation.md prompt, then
    extracted. Otherwise the command is passed straight to the extractor.

    `devices` can be:
      - dict: raw device catalog (legacy, passed through _format_services_block)
      - str: pre-formatted services block (e.g. intent-based "Dev.Svc  (value|function)" lines)

    Returns a tuple (ir_dict, prompt_tokens, completion_tokens, elapsed_sec).
    ir_dict is either a valid IR or `{"error": "...", ...}` on rejection.
    Raises IRValidationError if the model returned structurally invalid IR.
    """
    if auto_translate and _is_korean(command):
        english_command = translate_to_english(command, base_url=base_url, debug=debug)
    else:
        english_command = command

    system = _load_extractor_prompt()
    services = devices if isinstance(devices, str) else _format_services_block(devices)
    user = f"[Command]\n{english_command}\n\n[Services]\n{services}"
    if augmentations:
        user += f"\n\n{augmentations}"

    client = get_client(base_url)
    model = get_model_id(client)

    if debug:
        print("[timeline_ir] model =", model)
        print("[timeline_ir] command =", english_command)

    import time as _time
    _t0 = _time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        max_tokens=2048,
        stream=False,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    _elapsed = _time.perf_counter() - _t0
    raw = (response.choices[0].message.content or "").strip()
    raw = _strip_json_fences(raw)

    if debug:
        print("[timeline_ir] raw =", raw)

    try:
        ir = json.loads(raw)
    except json.JSONDecodeError as e:
        raise IRValidationError(f"model output is not valid JSON: {e}\n--- raw ---\n{raw}") from None

    # Reject path is allowed as-is.
    if isinstance(ir, dict) and "error" in ir:
        _usage = response.usage
        _prompt_tokens = _usage.prompt_tokens if _usage else 0
        _completion_tokens = _usage.completion_tokens if _usage else 0
        return ir, _prompt_tokens, _completion_tokens, _elapsed

    validate_ir(ir)
    _usage = response.usage
    _prompt_tokens = _usage.prompt_tokens if _usage else 0
    _completion_tokens = _usage.completion_tokens if _usage else 0
    return ir, _prompt_tokens, _completion_tokens, _elapsed


# ── Readable rendering (IR → Korean) ─────────────────────────────────────────

_UNIT_TABLE = [
    (3600000, "시간"),
    (60000,   "분"),
    (1000,    "초"),
    (1,       "밀리초"),
]

_DOW_KR = {"MON": "월", "TUE": "화", "WED": "수", "THU": "목",
           "FRI": "금", "SAT": "토", "SUN": "일"}


def _ms_to_kr(ms: int) -> str:
    for unit_ms, label in _UNIT_TABLE:
        if ms % unit_ms == 0 and ms >= unit_ms:
            return f"{ms // unit_ms}{label}"
    return f"{ms}밀리초"


def _cron_to_kr(cron: str) -> str:
    """Render a 5-field cron ('min hour day month dow') as a Korean phrase."""
    parts = cron.split()
    if len(parts) != 5:
        return f"cron '{cron}'"
    m, h, day, mon, dow = parts

    if dow != "*" and dow.upper() in _DOW_KR:
        return f"매주 {_DOW_KR[dow.upper()]}요일 {h}시 {m}분"
    if day != "*" and mon != "*":
        return f"매년 {mon}월 {day}일 {h}시 {m}분"
    if day != "*":
        return f"매월 {day}일 {h}시 {m}분"
    return f"매일 {h}시 {m}분"


def _render_cond_kr(cond: str) -> str:
    """Light-touch humanization of an expression string.

    We don't fully translate — just soften some operators so Korean readers
    can skim it. The expression stays mostly as-is for technical fidelity.
    """
    s = cond
    s = s.replace("&&", " 그리고 ").replace("||", " 또는 ")
    s = s.replace("==", "==").replace("!=", "≠")
    s = s.replace(">=", "≥").replace("<=", "≤")
    return s.strip()


def _render_step_kr(step: dict, indent: int = 0) -> list[str]:
    pad = "  " * indent
    op = step.get("op")
    out: list[str] = []

    if op == "start_at":
        if step["anchor"] == "now":
            out.append(f"{pad}• 지금부터 시작")
        else:
            out.append(f"{pad}• {_cron_to_kr(step['cron'])}에 시작")

    elif op == "wait":
        edge = step.get("edge", "none")
        cond = _render_cond_kr(step["cond"])
        if edge == "rising":
            out.append(f"{pad}• [{cond}]이(가) 참으로 **바뀔 때까지** 대기 (상승 엣지)")
        elif edge == "falling":
            out.append(f"{pad}• [{cond}]이(가) 거짓으로 **바뀔 때까지** 대기 (하강 엣지)")
        else:
            out.append(f"{pad}• [{cond}]이(가) 참인 상태가 될 때까지 대기")

    elif op == "delay":
        out.append(f"{pad}• {_ms_to_kr(step['ms'])} 대기")

    elif op == "read":
        out.append(f"{pad}• {step['src']} 값을 읽어 `${step['var']}`에 저장")

    elif op == "call":
        args = step.get("args") or {}
        if args:
            arg_strs = [f"{k}={v}" for k, v in args.items()]
            out.append(f"{pad}• 실행: {step['target']}({', '.join(arg_strs)})")
        else:
            out.append(f"{pad}• 실행: {step['target']}()")

    elif op == "if":
        out.append(f"{pad}• 만약 [{_render_cond_kr(step['cond'])}]이면:")
        for s in step.get("then", []):
            out.extend(_render_step_kr(s, indent + 1))
        else_body = step.get("else", [])
        if else_body:
            out.append(f"{pad}  그렇지 않으면:")
            for s in else_body:
                out.extend(_render_step_kr(s, indent + 2))

    elif op == "cycle":
        until = step.get("until")
        if until:
            out.append(f"{pad}• 반복 (종료 조건: [{_render_cond_kr(until)}]):")
        else:
            out.append(f"{pad}• 반복:")
        for s in step.get("body", []):
            out.extend(_render_step_kr(s, indent + 1))

    elif op == "break":
        out.append(f"{pad}• 반복 중단")

    else:
        out.append(f"{pad}• (알 수 없는 단계: {op})")

    return out


def ir_to_readable(ir: dict) -> str:
    """Render a Timeline IR as a Korean bullet-list outline for user feedback.

    Deterministic (no LLM). Designed so a non-developer can confirm or correct
    the system's understanding of their command.
    """
    if not isinstance(ir, dict):
        return "(invalid IR)"
    if "error" in ir:
        return f"❌ 변환 실패: {ir['error']}"

    try:
        validate_ir(ir)
    except IRValidationError as e:
        return f"❌ IR 스키마 오류: {e}"

    lines: list[str] = []
    lines.append("📋 실행 순서:")
    for step in ir["timeline"]:
        lines.extend(_render_step_kr(step, indent=0))
    return "\n".join(lines)


# ── Default test devices ─────────────────────────────────────────────────────

# Reasonable default device catalog for smoke testing and development when no
# live device context is available. Shapes mirror what the runtime provides.
DEFAULT_TEST_DEVICES = {
    "Light_1": {
        "tags": ["Light"], "category": ["Light", "Switch", "LevelControl", "ColorControl"],
        "attrs": {"value": "on|off", "brightness": "0-100", "color": "string"},
        "methods": ["on", "off", "toggle", "setBrightness(value)", "setColor(color)"],
    },
    "Light_2": {
        "tags": ["Light"], "category": ["Light", "Switch"],
        "attrs": {"value": "on|off"},
        "methods": ["on", "off", "toggle"],
    },
    "AirConditioner_1": {
        "tags": ["AirConditioner"], "category": ["AirConditioner", "Switch"],
        "attrs": {"value": "on|off", "mode": "cool|heat|auto|dry", "targetTemp": "number"},
        "methods": ["on", "off", "setMode(mode)", "setTargetTemp(value)"],
    },
    "TempSensor_1": {
        "tags": ["TempSensor"], "category": ["TempSensor"],
        "attrs": {"temperature": "number(C)"},
        "methods": [],
    },
    "HumiditySensor_1": {
        "tags": ["HumiditySensor"], "category": ["HumiditySensor"],
        "attrs": {"humidity": "number(%)"},
        "methods": [],
    },
    "MotionSensor_1": {
        "tags": ["MotionSensor"], "category": ["MotionSensor"],
        "attrs": {"detected": "true|false"},
        "methods": [],
    },
    "SmokeSensor_1": {
        "tags": ["SmokeSensor"], "category": ["SmokeSensor"],
        "attrs": {"detected": "true|false"},
        "methods": [],
    },
    "Door_1": {
        "tags": ["Door"], "category": ["Door", "ContactSensor"],
        "attrs": {"value": "open|closed"},
        "methods": ["open", "close"],
    },
    "Window_1": {
        "tags": ["Window"], "category": ["Window"],
        "attrs": {"value": "open|closed"},
        "methods": ["open", "close"],
    },
    "Curtain_1": {
        "tags": ["Curtain"], "category": ["Curtain", "WindowCovering"],
        "attrs": {"position": "0-100"},
        "methods": ["open", "close", "setPosition(value)"],
    },
    "Speaker_1": {
        "tags": ["Speaker"], "category": ["Speaker"],
        "attrs": {"value": "on|off", "volume": "0-100"},
        "methods": ["on", "off", "say(text)", "sayTime", "setVolume(value)"],
    },
    "Siren_1": {
        "tags": ["Siren"], "category": ["Siren", "Switch"],
        "attrs": {"value": "on|off"},
        "methods": ["on", "off"],
    },
    "TV_1": {
        "tags": ["TV"], "category": ["TV", "Switch"],
        "attrs": {"value": "on|off", "channel": "int"},
        "methods": ["on", "off", "setChannel(value)"],
    },
    "Button_1": {
        "tags": ["Button"], "category": ["MultiButton"],
        "attrs": {"Button1": "pushed|long_pushed|idle"},
        "methods": [],
    },
}


# ── CLI smoke test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python timeline_ir.py '<english command>'")
        sys.exit(1)
    cmd = sys.argv[1]
    ir = extract_ir(cmd, devices=DEFAULT_TEST_DEVICES, debug=True)
    print("\n--- IR ---")
    print(json.dumps(ir, ensure_ascii=False, indent=2))
    print("\n--- Readable (KR) ---")
    print(ir_to_readable(ir))
