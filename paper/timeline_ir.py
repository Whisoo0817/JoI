"""Timeline IR: schema, extraction (NL → IR), readable rendering.

This module defines the Timeline IR used by the new reactive-DSL pipeline.
Pipeline stages:
    1. NL (English) → Timeline IR          [extract_ir]  — LLM call
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


# ── Delay duration parsing ───────────────────────────────────────────────────
# IR delay uses the SAME mini-grammar as JoI's `delay(N UNIT)` literal so
# lowering is a near-passthrough. UNIT is one of HOUR/MIN/SEC/MSEC; value is a
# non-negative integer; exactly one space separates them.
_DURATION_UNIT_MS = {"HOUR": 3_600_000, "MIN": 60_000, "SEC": 1_000, "MSEC": 1}
_DURATION_RE = re.compile(r"^(\d+)\s+(HOUR|MIN|SEC|MSEC)$")


def parse_duration_to_ms(s: str) -> int:
    """Parse an IR delay duration string like '5 MIN' or '100 MSEC' into ms.

    Raises ValueError on malformed input. Use this everywhere the simulator /
    validator / FSM derivation needs the millisecond value — never re-implement
    the regex elsewhere.
    """
    if not isinstance(s, str):
        raise ValueError(f"duration must be a string, got {type(s).__name__}")
    m = _DURATION_RE.match(s.strip())
    if not m:
        raise ValueError(
            f"malformed duration {s!r}; expected '<int> <HOUR|MIN|SEC|MSEC>'"
        )
    return int(m.group(1)) * _DURATION_UNIT_MS[m.group(2)]


# ── Schema validation ────────────────────────────────────────────────────────

from dataclasses import dataclass, field as _dc_field


@dataclass
class IRViolation:
    """One structured IR-validation failure.

    `code` is one of a small fixed set so callers can build typed retry hints
    instead of regex-parsing free-text messages:
      - schema_invalid          : structural failure (shape, required fields)
      - service_not_in_catalog  : `Service.Member`'s Service is not a catalog id
      - member_not_in_service   : Service is valid, Member is not its function or value
      - service_not_in_devices  : Service valid but no connected device has it
      - arg_not_in_catalog      : call.args key is not declared by the catalog function
    `hint` is an optional structured suggestion ("did_you_mean":"Switch.Switch")
    used by the retry-hint builder; `message` is the human-readable form.
    """
    code: str
    path: str
    message: str
    hint: dict = _dc_field(default_factory=dict)


class IRValidationError(ValueError):
    """Raised when a Timeline IR object fails structural validation.

    Carries a list of `IRViolation` so callers (e.g. the IR-extract retry
    loop) can map error codes to typed retry instructions, instead of
    parsing the joined message string.
    """
    def __init__(self, message: str, violations: list[IRViolation] | None = None):
        super().__init__(message)
        self.violations: list[IRViolation] = violations or []


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

    # Timeline-level rule: exactly ONE start_at, at index 0. A second start_at
    # mid-timeline encodes two independent scenarios that cannot share one IR.
    extras = [i for i, s in enumerate(ir["timeline"][1:], start=1)
              if isinstance(s, dict) and s.get("op") == "start_at"]
    if extras:
        raise IRValidationError(
            f"start_at may appear only at timeline[0]; found extras at {extras}"
        )


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
        # Optional `for` field: cond must hold CONTINUOUSLY for this duration
        # before wait completes. Timer resets if cond flips false during the
        # window. Format identical to delay.duration ("N UNIT").
        if "for" in step and step["for"] is not None:
            fv = step["for"]
            if not isinstance(fv, str):
                raise IRValidationError("wait.for must be a 'N UNIT' string")
            try:
                parse_duration_to_ms(fv)
            except ValueError as e:
                raise IRValidationError(f"wait.for: {e}")

    elif op == "delay":
        dur = step.get("duration")
        if not isinstance(dur, str):
            raise IRValidationError(
                "delay requires 'duration' string like '5 MIN' (UNIT ∈ HOUR/MIN/SEC/MSEC)"
            )
        try:
            parse_duration_to_ms(dur)
        except ValueError as e:
            raise IRValidationError(f"delay.duration: {e}")

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
        # `period`: REQUIRED per-iteration cadence (e.g. "10 MIN"). Lowering uses
        # it as the wrapper.period. Defaults per convention: D-3 edge cycle (body
        # has wait(rising)) → "100 MSEC"; otherwise the NL cadence `every N <unit>`.
        # Same grammar as delay.duration.
        period = step.get("period")
        if period is None:
            raise IRValidationError(
                "cycle.period is required (use '100 MSEC' for D-3 edge cycles, "
                "or the NL cadence otherwise)"
            )
        if not isinstance(period, str):
            raise IRValidationError("cycle.period must be a string like '10 MIN'")
        try:
            parse_duration_to_ms(period)
        except ValueError as e:
            raise IRValidationError(f"cycle.period: {e}")
        # Optional `count`: tick-index variable name (e.g. "n"). Used for
        # alternation, rotation, or bounded-repeat patterns. Must be a valid
        # identifier string when present.
        count = step.get("count")
        if count is not None:
            if not isinstance(count, str) or not count:
                raise IRValidationError("cycle.count must be a non-empty string identifier")
        for j, s in enumerate(body):
            try:
                _validate_step(s)
            except IRValidationError as e:
                raise IRValidationError(f"body[{j}]: {e}") from None

    elif op == "break":
        pass  # no fields


# ── Device-conformance validation ────────────────────────────────────────────
# Verify that every Service.Attr / call.target / read.src in the IR refers to
# a category present in `connected_devices`. Catches LLM hallucination of
# services the user doesn't have (e.g., IR emits `Pump.Switch` when no device
# has category "Pump"). Attribute-level conformance is NOT checked here — the
# downstream L1 static analyzer + simulator catch that on the JoI side.

# Matches a Service.Attr pair where Service starts with an uppercase letter
# and is not preceded by `$` (variable) or another word char (dotted path).
_SERVICE_ATTR_RE = re.compile(
    r"(?<![$\w.])([A-Z][A-Za-z0-9]*)\.([A-Za-z][A-Za-z0-9_]*)"
)
# Builtin function names (all/any/avg/abs/max/min) and reserved literals are
# capitalized in some legacy forms; exclude these from service detection.
_NON_SERVICE_PREFIXES = {"True", "False", "None", "Null"}


def validate_ir_against_devices(ir: Any, connected_devices: dict) -> None:
    """Raise IRValidationError if the IR references a service that no device in
    `connected_devices` has as a category.

    Implements the catalog-conformance contract at the IR layer (pipeline P1).
    Walks every step recursively. For each Service.Attr reference (in
    call.target, wait/if cond, read.src), checks that `Service` appears in at
    least one device's `category` list.
    """
    if not isinstance(ir, dict) or "timeline" not in ir or "error" in ir:
        return  # reject path or malformed — nothing to check here

    # Collect the set of category strings actually present.
    valid_categories: set[str] = set()
    if isinstance(connected_devices, dict):
        for spec in connected_devices.values():
            if isinstance(spec, dict):
                cats = spec.get("category", [])
                if isinstance(cats, list):
                    for c in cats:
                        if isinstance(c, str):
                            valid_categories.add(c)
                elif isinstance(cats, str):
                    valid_categories.add(cats)

    if not valid_categories:
        return  # no device info — nothing to validate against

    violations: list[str] = []
    _check_steps(ir["timeline"], valid_categories, violations, path="timeline")
    if violations:
        # `violations` here is a flat list of strings (path: 'service') built
        # by _check_steps below; reshape into IRViolation list with code.
        structured: list[IRViolation] = []
        for line in sorted(set(violations)):
            head, _, svc_repr = line.partition(": ")
            svc = svc_repr.strip("'\"")
            structured.append(IRViolation(
                code="service_not_in_devices",
                path=head,
                message=f"{head}: {svc!r} is not a category of any connected device "
                        f"(valid: {sorted(valid_categories)})",
                hint={"service": svc, "valid_categories": sorted(valid_categories)},
            ))
        raise IRValidationError(
            "IR references services not present in connected_devices: "
            + ", ".join(sorted(set(violations))),
            violations=structured,
        )


def _check_steps(steps: list, valid: set, out: list, path: str) -> None:
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        sp = f"{path}[{i}]"
        op = s.get("op")
        if op == "call":
            target = s.get("target", "")
            if isinstance(target, str) and "." in target:
                svc = target.split(".", 1)[0]
                if svc and svc not in valid:
                    out.append(f"{sp}.target: {svc!r}")
        elif op == "read":
            src = s.get("src", "")
            _scan_expr(src, valid, out, f"{sp}.src")
        elif op == "wait":
            _scan_expr(s.get("cond", ""), valid, out, f"{sp}.cond")
        elif op == "if":
            _scan_expr(s.get("cond", ""), valid, out, f"{sp}.cond")
            _check_steps(s.get("then", []) or [], valid, out, f"{sp}.then")
            _check_steps(s.get("else", []) or [], valid, out, f"{sp}.else")
        elif op == "cycle":
            _check_steps(s.get("body", []) or [], valid, out, f"{sp}.body")
            if s.get("until"):
                _scan_expr(s["until"], valid, out, f"{sp}.until")


def _scan_expr(src: Any, valid: set, out: list, path: str) -> None:
    if not isinstance(src, str):
        return
    for svc, _attr in _SERVICE_ATTR_RE.findall(src):
        if svc == "clock" or svc in _NON_SERVICE_PREFIXES:
            continue
        if svc not in valid:
            out.append(f"{path}: {svc!r}")


# ── Catalog-membership validation ───────────────────────────────────────────
# `validate_ir_against_devices` only checks Service-level presence in the
# user's connected_devices categories. That accepts `FaceRecognizer.Switch`
# whenever a device has both FaceRecognizer and Switch in its category list —
# but the IR is still semantically wrong: `Switch` is a sibling subskill, not
# a member of the FaceRecognizer service. The capability lives at
# `Switch.Switch`. This validator catches that class of malformed reference
# at the IR layer (Python-side, pre-lowering) so the extractor is held to a
# catalog-grounded contract.

def validate_ir_against_catalog(ir: Any, catalog: dict) -> None:
    """Raise IRValidationError if any `Service.Member` in the IR is not a real
    function/value of that catalog service, OR if any call.args key is not
    declared by the catalog function's argument list.

    Produces structured violations with codes:
      - service_not_in_catalog
      - member_not_in_service       (with did_you_mean hint when possible)
      - arg_not_in_catalog          (with valid_args hint)
    """
    if not isinstance(ir, dict) or "timeline" not in ir or "error" in ir:
        return
    if not isinstance(catalog, dict) or not catalog:
        return

    # Reverse indexes for hint generation.
    member_to_services: dict[str, list[str]] = {}
    for svc, entry in catalog.items():
        if not isinstance(entry, dict):
            continue
        for m in list(entry.get("functions", {}).keys()) + list(entry.get("values", {}).keys()):
            member_to_services.setdefault(m, []).append(svc)

    violations: list[IRViolation] = []
    _check_steps_catalog(
        ir["timeline"], catalog, member_to_services, violations, path="timeline",
    )
    if violations:
        raise IRValidationError(
            "IR references service.member pairs not in catalog: "
            + "; ".join(v.message for v in violations),
            violations=violations,
        )


def _check_steps_catalog(steps: list, catalog: dict,
                         member_to_services: dict, out: list, path: str) -> None:
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        sp = f"{path}[{i}]"
        op = s.get("op")
        if op == "call":
            target = s.get("target", "")
            _check_pair(target, catalog, member_to_services, out, f"{sp}.target",
                        expect_function=True, args=s.get("args"))
        elif op == "read":
            _scan_expr_catalog(s.get("src", ""), catalog, member_to_services, out, f"{sp}.src")
        elif op == "wait":
            _scan_expr_catalog(s.get("cond", ""), catalog, member_to_services, out, f"{sp}.cond")
        elif op == "if":
            _scan_expr_catalog(s.get("cond", ""), catalog, member_to_services, out, f"{sp}.cond")
            _check_steps_catalog(s.get("then", []) or [], catalog, member_to_services, out, f"{sp}.then")
            _check_steps_catalog(s.get("else", []) or [], catalog, member_to_services, out, f"{sp}.else")
        elif op == "cycle":
            _check_steps_catalog(s.get("body", []) or [], catalog, member_to_services, out, f"{sp}.body")
            if s.get("until"):
                _scan_expr_catalog(s["until"], catalog, member_to_services, out, f"{sp}.until")


def _check_pair(target: Any, catalog: dict, member_to_services: dict,
                out: list, path: str,
                expect_function: bool = False, args: Any = None) -> None:
    if not isinstance(target, str) or "." not in target:
        return
    svc, _, member = target.partition(".")
    if not svc or not member:
        return
    if svc not in catalog:
        out.append(IRViolation(
            code="service_not_in_catalog",
            path=path,
            message=f"{path}: {target!r} — service {svc!r} not in catalog",
            hint={"service": svc, "target": target},
        ))
        return
    entry = catalog.get(svc) or {}
    funcs = entry.get("functions", {}) or {}
    vals = entry.get("values", {}) or {}
    if member not in funcs and member not in vals:
        candidates = sorted(member_to_services.get(member, []))
        msg = f"{path}: {target!r} — member {member!r} not in {svc!r}"
        hint = {"service": svc, "member": member, "target": target}
        if candidates:
            msg += f" — did you mean {candidates[0]}.{member}?"
            hint["did_you_mean"] = f"{candidates[0]}.{member}"
            hint["candidates"] = candidates
        out.append(IRViolation(
            code="member_not_in_service", path=path, message=msg, hint=hint,
        ))
        return
    # Member valid. If this is a call.target with args, check arg keys too.
    if expect_function and member in funcs and isinstance(args, dict):
        fn_arg_order = funcs[member]  # list of declared arg ids
        valid_keys = set(fn_arg_order) if isinstance(fn_arg_order, list) else set()
        for k in args.keys():
            if k not in valid_keys:
                out.append(IRViolation(
                    code="arg_not_in_catalog",
                    path=path,
                    message=f"{path}: arg {k!r} not declared for {target!r} "
                            f"(valid: {sorted(valid_keys)})",
                    hint={
                        "target": target, "bad_arg": k,
                        "valid_args": sorted(valid_keys),
                    },
                ))


def _scan_expr_catalog(src: Any, catalog: dict, member_to_services: dict,
                       out: list, path: str) -> None:
    if not isinstance(src, str):
        return
    for svc, member in _SERVICE_ATTR_RE.findall(src):
        if svc == "clock" or svc in _NON_SERVICE_PREFIXES:
            continue
        _check_pair(f"{svc}.{member}", catalog, member_to_services, out, path)
    # Additionally detect `<Service>.<EnumAttr> == <bare_identifier>` — the
    # bare identifier becomes a VarRef at evaluation time and silently
    # resolves to None, so the comparison never matches the intended enum
    # value. Walk the parsed AST instead of regex-matching so we recognize
    # the comparison context (BinaryOp ==/!=) reliably.
    try:
        from paper.simulators import expr as _expr_mod
        ast = _expr_mod.parse(src)
    except Exception:
        return
    _walk_for_enum_unquoted(ast, catalog, out, path)


def _walk_for_enum_unquoted(node: Any, catalog: dict, out: list, path: str) -> None:
    """Recurse the expression AST; flag enum-typed device-attr comparisons
    whose RHS is a bare identifier (parsed as VarRef)."""
    from paper.simulators import expr as _expr_mod
    if node is None:
        return
    if isinstance(node, _expr_mod.BinaryOp):
        if node.op in ("==", "!="):
            for side, other in ((node.left, node.right), (node.right, node.left)):
                if isinstance(side, _expr_mod.DeviceRef) and isinstance(other, _expr_mod.VarRef):
                    key = side.key  # canonical "service.attr"
                    if "." not in key:
                        continue
                    svc, attr = key.split(".", 1)
                    # The DeviceRef stored canonical (lowercase). Find the
                    # catalog entry case-insensitively.
                    cat_svc = next(
                        (s for s in catalog if s.lower() == svc), None
                    )
                    if not cat_svc:
                        continue
                    vals = catalog[cat_svc].get("values", {}) or {}
                    cat_attr = next(
                        (a for a in vals if a.lower() == attr), None
                    )
                    if not cat_attr:
                        continue
                    if vals[cat_attr] == "ENUM":
                        out.append(IRViolation(
                            code="enum_value_unquoted",
                            path=path,
                            message=(f"{path}: comparison `{cat_svc}.{cat_attr} == "
                                     f"{other.name}` uses a bare identifier on the RHS — "
                                     f"`{other.name}` is silently treated as a "
                                     f"variable and resolves to None. Wrap the enum "
                                     f"value in double quotes."),
                            hint={
                                "service": cat_svc, "attr": cat_attr,
                                "bare_ident": other.name,
                                "did_you_mean": f"\"{other.name}\"",
                            },
                        ))
        _walk_for_enum_unquoted(node.left, catalog, out, path)
        _walk_for_enum_unquoted(node.right, catalog, out, path)
        return
    if isinstance(node, _expr_mod.UnaryOp):
        _walk_for_enum_unquoted(node.operand, catalog, out, path)
        return


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
    source_command: str,
    base_url: str | None = None,
    debug: bool = False,
) -> str:
    """Translate a Hangul IoT command to English using the translation prompt.

    Uses files/translation.md, which handles structural cues such as
    if/when/whenever and recurring-event disambiguation so the extractor
    receives clean English input.
    """
    system = _load_translation_prompt()
    client = get_client(base_url)
    model = get_model_id(client)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": source_command},
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


def _contains_hangul(text: str) -> bool:
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


def build_extract_retry_hint(violations: list[IRViolation]) -> str:
    """Map structured violations into a follow-up user message for the extractor.

    The message instructs the LLM what *kind* of fix is required for each
    violated reference, using catalog-grounded suggestions when available.
    """
    lines: list[str] = [
        "## Previous IR failed catalog validation — fix and resubmit",
        "",
        "The IR you produced references services/members/args that are not in "
        "the service catalog. Each bullet names one issue and the kind of fix.",
        "",
    ]
    for v in violations:
        if v.code == "service_not_in_catalog":
            lines.append(
                f"- {v.path}: service `{v.hint.get('service')}` is not a catalog "
                f"service id. Use a real service id from the [Services] block."
            )
        elif v.code == "member_not_in_service":
            dym = v.hint.get("did_you_mean")
            svc = v.hint.get("service")
            mem = v.hint.get("member")
            if dym:
                lines.append(
                    f"- {v.path}: `{svc}.{mem}` is wrong — `{mem}` is a member of "
                    f"`{v.hint['candidates'][0]}`, not `{svc}`. Use `{dym}`. "
                    f"(`{svc}` is a parent device category; the capability lives "
                    f"on its sibling sub-service.)"
                )
            else:
                lines.append(
                    f"- {v.path}: `{svc}.{mem}` — `{mem}` is not a function or "
                    f"value of `{svc}`. Look up the right service in the catalog."
                )
        elif v.code == "service_not_in_devices":
            valid = v.hint.get("valid_categories") or []
            valid_str = ", ".join(f"`{c}`" for c in valid) if valid else "(see [Connected Devices])"
            lines.append(
                f"- {v.path}: service `{v.hint.get('service')}` is not present in "
                f"connected_devices. ONLY use services from these categories: "
                f"{valid_str}."
            )
        elif v.code == "arg_not_in_catalog":
            lines.append(
                f"- {v.path}: arg `{v.hint.get('bad_arg')}` is not declared for "
                f"`{v.hint.get('target')}`. Valid args: "
                f"{v.hint.get('valid_args')}. Remove or rename."
            )
        elif v.code == "enum_value_unquoted":
            lines.append(
                f"- {v.path}: `{v.hint.get('service')}.{v.hint.get('attr')} == "
                f"{v.hint.get('bare_ident')}` — the RHS is a bare identifier "
                f"that would be parsed as a variable (which resolves to None). "
                f"Wrap the enum value in double quotes: `== {v.hint.get('did_you_mean')}`."
            )
        else:
            lines.append(f"- {v.path}: {v.message}")
    lines.append("")
    lines.append("Produce a corrected Timeline IR JSON. Do not repeat the same "
                 "service/member/arg ids you just used.")
    return "\n".join(lines)


def extract_ir(
    command: str,
    devices: dict | str,
    base_url: str | None = None,
    debug: bool = False,
    auto_translate: bool = True,
    augmentations: str | None = None,
    retry_context: tuple[str, str, str] | None = None,
) -> dict:
    """Call the local LLM to extract a Timeline IR from a command.

    If `command` contains Hangul characters and `auto_translate` is True, the
    command is first translated to English via the translation.md prompt, then
    extracted. Otherwise the command is passed straight to the extractor.

    `devices` can be:
      - dict: raw device catalog (legacy, passed through _format_services_block)
      - str: pre-formatted services block (e.g. intent-based "Dev.Svc  (value|function)" lines)

    Returns a tuple (ir_dict, prompt_tokens, completion_tokens, elapsed_sec).
    ir_dict is either a valid IR or `{"error": "...", ...}` on rejection.
    Raises IRValidationError if the model returned structurally invalid IR.
    """
    if auto_translate and _contains_hangul(command):
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

    # Build chat history. On first attempt: single user turn. On retry, replay
    # the original (user, assistant) and append the hint as the next user turn
    # — same shape as the lowering retry path so KV cache hits on the shared
    # prefix and the model sees its own prior output before the correction.
    if retry_context is not None:
        prior_user, prior_assistant, hint = retry_context
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prior_user},
            {"role": "assistant", "content": prior_assistant},
            {"role": "user", "content": hint},
        ]
        # Replayed user message is what the caller should pass back on the
        # next retry — preserve the original prompt for traceability.
        out_user = prior_user
    else:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        out_user = user

    import time as _time
    _t0 = _time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
        max_tokens=2048,
        stream=False,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    _elapsed = _time.perf_counter() - _t0
    raw = (response.choices[0].message.content or "").strip()
    raw_assistant = raw  # preserve for retry replay BEFORE fence-strip mutates it
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
        return ir, _prompt_tokens, _completion_tokens, _elapsed, out_user, raw_assistant

    # If the LLM dropped start_at (a recurring failure mode for simple commands
    # like "Tell me the temperature."), one-shot retry with prefix-prefilling:
    # force the assistant response to begin with `{"timeline":[{"op":"start_at"`
    # via continue_final_message=True so the start_at step is decode-time
    # guaranteed; the model freely completes anchor + the rest. Reject path
    # (`{"error": ...}`) only fires on first attempt, preserving multi-cron
    # rejection. Prefix stops before `,"anchor":...` so cron-anchored cases
    # can still emit anchor="cron" + cron string.
    try:
        validate_ir(ir)
    except IRValidationError as e:
        if "timeline[0] must be a start_at step" in str(e):
            _PREFIX = '{"timeline":[{"op":"start_at"'
            messages_prefill = messages + [{"role": "assistant", "content": _PREFIX}]
            _t1 = _time.perf_counter()
            response = client.chat.completions.create(
                model=model,
                messages=messages_prefill,
                temperature=0.0,
                max_tokens=2048,
                stream=False,
                extra_body={
                    "chat_template_kwargs": {"enable_thinking": False},
                    "add_generation_prompt": False,
                    "continue_final_message": True,
                },
            )
            _elapsed += _time.perf_counter() - _t1
            raw_continuation = (response.choices[0].message.content or "").strip()
            raw = _strip_json_fences(_PREFIX + raw_continuation)
            raw_assistant = raw
            try:
                ir = json.loads(raw)
                validate_ir(ir)
            except (json.JSONDecodeError, IRValidationError) as e2:
                raise IRValidationError(
                    f"{e2}\n--- raw model output (after prefix-prefill retry) ---\n{raw}"
                ) from None
        else:
            raise IRValidationError(
                f"{e}\n--- raw model output ---\n{raw_assistant}"
            ) from None
    _usage = response.usage
    _prompt_tokens = _usage.prompt_tokens if _usage else 0
    _completion_tokens = _usage.completion_tokens if _usage else 0
    return ir, _prompt_tokens, _completion_tokens, _elapsed, out_user, raw_assistant


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
    ir_result = extract_ir(cmd, devices=DEFAULT_TEST_DEVICES, debug=True)
    ir = ir_result[0] if isinstance(ir_result, tuple) else ir_result
    print("\n--- IR ---")
    print(json.dumps(ir, ensure_ascii=False, indent=2))
