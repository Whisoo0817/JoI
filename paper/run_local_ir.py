"""IR-based JoI generation pipeline (device-first).

Turns a Korean smart-home command into JoI automation code:

    [Stage 1] device_retrieve  -> target groups (role + verbatim label phrase), command-only
              ground_targets   -> phrase -> matched device ids (LLM, sees devices)
              minimal_tags_for -> tightest selector tags from matched devices (Python)
              device_resolve   -> service per group, echoing the given tags `(#Tag).Cat.Method`
              quantifier_for   -> all/any/one prefix (Python)
    [Stage 2] translation to English (for the IR/lowering prompts)
    [Stage 3 // parallel]
        - branch A (resolve + ir): enum_cond_check -> enum_resolve -> arg_resolve
                                   -> ir_extract (sequential within branch)
        - branch B (precision): the selectors produced by device_resolve
        IR is selector-free, so branch A does not depend on branch B.
    [Stage 4] joi_from_ir lowering: IR + precision -> JoI (bucket-routed)
    [Stage 5] naming: re_translate -> re_translate_kor -> scenario_name

Service & post-processing helpers live in pipeline_helpers.py.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# paper/ is not on sys.path when imported as a package; add it so timeline_ir is found
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from config import get_client, get_model_id
from loader import SERVICE_DATA, PROMPTS, get_device_rules_section
from device_ontology import parse_targets
from parser.validator import validate_joi

from pipeline_helpers import (
    JoiGenerationError,
    run_llm_inference,
    extract_service_details,
    _SERVICE_CATEGORY_MAP,
    _apply_service_prefix,
    _normalize_script_newlines,
    _post_process_joi_any_quantifiers,
    _reapply_precision_quantifiers,
    _strip_selector_extra_parens,
    _parse_dict_input,
)
from timeline_ir import (
    extract_ir, ir_to_readable, validate_ir_against_devices,
    validate_ir_against_catalog, build_extract_retry_hint,
    IRValidationError, parse_duration_to_ms,
)
from feasibility import check_feasibility, FeasibilityError, lowering_bucket
from ir_renderer import render_ir_with_devices

# Verifier integration (Phase 2). Activated when env JOI_VERIFY=1 (default off
# during transition so baselines stay reproducible). When on, the lowering
# stage is wrapped by `retry_harness.run` with max_attempts=2; retry hints
# are delivered as a follow-up user turn via `infer_followup`, not as a
# template slot — first-attempt prompt distribution is unchanged.
from paper.verifier.retry_harness import run as _verifier_run
from paper.verifier.llm_diagnose import make_llm_diagnoser as _make_llm_diagnoser
from paper.simulators.catalog import load_catalog as _load_catalog

_VERIFY_ENABLED = os.environ.get("JOI_VERIFY", "0") == "1"
_VERIFY_MAX_ATTEMPTS = int(os.environ.get("JOI_VERIFY_MAX_ATTEMPTS", "2"))
# LLM-aided diagnose (paper §8.3): adds one reasoning call between violation
# detection and retry. Off by default so the deterministic-diagnose baseline
# stays reproducible; flip JOI_LLM_DIAGNOSE=1 for the ablation's LLM-aided arm.
_LLM_DIAGNOSE_ENABLED = os.environ.get("JOI_LLM_DIAGNOSE", "0") == "1"

# IR-only short-circuit. When JOI_IR_ONLY=1, the pipeline runs through the
# device + resolve + IR-extract stages (+ post-process trio) and then writes
# the IR + supporting state to JOI_IR_DUMP_DIR/<JOI_IR_DUMP_NAME>.json, skipping
# Stage 4 lowering. Used for offline IR-confirm validation prior to lowering.
# (read per-call inside generate_joi_code_ir so in-process callers can toggle
#  them between successive calls.)


# Bucket-specific lowering prompt is assembled at runtime as
# joi_common.md + joi_<bucket>.md, both loaded from files/ via PROMPTS.
#
# Two buckets only: the IR is either acyclic (sequence) or contains a top-level
# cycle. Within `cycle`, the joi_cycle.md prompt's own switchboard (D-3/D-4/D-5/
# D-6/D-9/B-2) picks the idiom from explicit IR signals — no Python heuristic.
_BUCKET_KEYS = ("noncycle", "cycle")


def classify_ir(ir):
    """Routing key for example routing: the coarsest projection of the IR's
    structural class (feasibility.structural_class), i.e. 'cycle' if a
    top-level cycle op exists, else 'noncycle'.

    Idiom discrimination (D-3/D-4/D-5/D-6/D-9/B-2) is delegated to the cycle
    prompt's switchboard, which reads explicit IR signals: cycle.until,
    body wait(edge:"rising"), pre-cycle wait(edge:"none"), if{break}, and
    body delay count. This keeps Python free of brittle heuristics.
    """
    return lowering_bucket(ir)


def _load_lowering_prompt(bucket: str, ir=None) -> str:
    """joi_common.md + the example block routed by the IR's structural class.

    The block comes from the example bank (paper/example_bank.py), seeded with
    the shipped per-class file joi_<bucket>.md — byte-identical to loading the
    file directly unless JOI_EXAMPLE_BANK adds accumulated verified pairs."""
    if bucket not in _BUCKET_KEYS:
        raise ValueError(f"unknown lowering bucket: {bucket!r}")
    if ir is not None:
        try:
            from paper import example_bank
            common = PROMPTS.get("joi_common")
            if not common:
                raise FileNotFoundError("joi_common.md not loaded by PROMPTS")
            return common + "\n\n---\n\n" + example_bank.examples_for(ir, PROMPTS)
        except ImportError:
            pass
    common = PROMPTS.get("joi_common")
    bucket_md = PROMPTS.get(f"joi_{bucket}")
    if not common:
        raise FileNotFoundError("joi_common.md not loaded by PROMPTS")
    if not bucket_md:
        raise FileNotFoundError(f"joi_{bucket}.md not loaded by PROMPTS")
    return common + "\n\n---\n\n" + bucket_md


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers — promoted from nested defs inside generate_joi_code_ir.
# Each helper takes its dependencies explicitly so it is independently testable.
# `SERVICE_DATA` / `get_device_rules_section` come from the module's top-level
# imports (they are catalog/rule lookups, not pipeline state).
# ─────────────────────────────────────────────────────────────────────────────


def _strip_llm_wrappers(raw: str) -> str:
    """Remove <Reasoning> blocks and ```(json)? fences from an LLM string."""
    s = re.sub(r'<Reasoning>.*?</Reasoning>', '', raw, flags=re.DOTALL).strip()
    s = re.sub(r'```(?:json)?\s*', '', s).strip().rstrip("`").strip()
    return s


def _extract_reasoning(raw: str) -> str:
    """Pull <Reasoning>...</Reasoning> content (best-effort)."""
    m = re.search(r'<Reasoning>(.*?)</Reasoning>', raw, flags=re.DOTALL)
    return m.group(1).strip() if m else ""


def _format_arg(a: dict) -> str:
    a_type = a.get("type", "")
    extra = ""
    if a_type == "ENUM":
        enum_id = a.get("format", "")
        extra = f" {{{enum_id}}}" if enum_id else ""
    a_desc = a.get("descriptor", "")
    line = f"{a.get('id', '?')}: {a_type}{extra}"
    if a_desc:
        line += f" — {a_desc}"
    return line


def _format_return(svc_info: dict, is_value: bool) -> str:
    if is_value:
        return svc_info.get("type", "") or "VOID"
    rt = svc_info.get("return_type")
    if isinstance(rt, dict):
        return rt.get("type", "VOID") or "VOID"
    if isinstance(rt, str) and rt:
        return rt
    return "VOID"


def _strip_legacy_examples(rule: str) -> str:
    """Drop the LEGACY few-shot example blocks from a device_rules section.

    device_rules_*.md still carry `[Command] … ["Skill.Method"]` examples in the
    OLD mapping-stage output format (a JSON array of skill methods). device-first
    device_resolve emits `RESULT:\\n(#Tag).Cat.Method` instead, so feeding those
    arrays as context poisons the model into copying the array form (esp. capable
    models that faithfully imitate in-context examples). We keep the `[Device
    Summary]` XML and the prose rules (the actual service-selection knowledge) and
    remove only the `[Command] … [".."]` blocks: a `[Command]` line, then lines up
    to and including the first line containing a `["..."]` array literal.
    """
    lines = rule.split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        if lines[i].strip() == "[Command]":
            j = i + 1
            # scan forward to the array-literal line that ends this example block
            while j < n and '["' not in lines[j] and lines[j].strip() != "[Command]":
                j += 1
            if j < n and '["' in lines[j]:
                i = j + 1  # skip the whole [Command]…[".."] block
                continue
            # no array terminator (not a legacy block) — keep the line as-is
        out.append(lines[i])
        i += 1
    # collapse the blank-line runs the removals leave behind
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _build_device_selection_rules(categories) -> str:
    """Concatenate the default ('service_plan') section of each connected
    device's device_rules_*.md. Stage-scoped sections (e.g. `# @ArgResolve`)
    are stripped — those are pulled by their respective stages. Legacy
    array-format `[Command] … ["..."]` few-shot blocks are also removed so they
    don't override device_resolve's `RESULT:` output contract.
    """
    chunks = []
    for cat in categories:
        rule = get_device_rules_section(cat, "service_plan")
        if rule:
            chunks.append(f"### {cat}\n{_strip_legacy_examples(rule)}")
    return "\n\n".join(chunks) if chunks else "(no device-specific rules)"


def _build_device_specific_hints(svcs, section: str) -> str:
    """Collect stage-scoped device hints from device_rules_<cat>.md for each
    distinct category present in `svcs`. Empty string when nothing defined.
    """
    cats = sorted({s.split('.', 1)[0] for s in svcs if '.' in s})
    chunks = []
    for cat in cats:
        hint = get_device_rules_section(cat, section)
        if hint:
            chunks.append(f"### {cat}\n{hint}")
    return "\n\n".join(chunks)


def _is_enum_value_service(s: str) -> bool:
    if '.' not in s:
        return False
    dev, svc_name = s.split('.', 1)
    svc_name_clean = svc_name.replace("()", "")
    for v in SERVICE_DATA.get(dev, {}).get("values", []):
        if v.get("id") == svc_name_clean:
            return v.get("type") == "ENUM"
    return False


def _is_function_service(s: str) -> bool:
    if '.' not in s:
        return False
    dev, svc_name = s.split('.', 1)
    svc_name_clean = svc_name.replace("()", "")
    dev_data = SERVICE_DATA.get(dev, {})
    return not any(e["id"] == svc_name_clean for e in dev_data.get("values", []))


def _build_enum_resolve_input(sentence: str, targets, service_details: dict) -> str:
    lines = [f"[Command]\n{sentence}\n", "[ENUM-Value Services]"]
    for s in targets:
        dev, svc_name = s.split('.', 1)
        svc_name_clean = svc_name.replace("()", "")
        svc_info = (service_details.get(dev) or {}).get(svc_name_clean) or {}
        descriptor = svc_info.get("descriptor", "") if isinstance(svc_info, dict) else ""
        header = f"{s}"
        if descriptor:
            header += f": {descriptor}"
        lines.append(header)
        lines.append("Members:")
        for member in (svc_info.get("enum_list") or []):
            if isinstance(member, str) and " - " in member:
                val, desc = member.split(" - ", 1)
                lines.append(f"  - {val.strip()}: {desc.strip()}")
            else:
                lines.append(f"  - {str(member).strip()}")
        lines.append("")
    return "\n".join(lines)


def _build_arg_resolve_input(svcs, details: dict) -> str:
    """Compact service-detail block for the resolver: id, args+enum, returns."""
    lines = []
    for s in svcs:
        dev, svc_name = s.split('.', 1)
        svc_name_clean = svc_name.replace("()", "")
        svc_info = (details.get(dev) or {}).get(svc_name_clean) or {}
        descriptor = svc_info.get("descriptor", "") if isinstance(svc_info, dict) else ""
        header = f"{dev}.{svc_name_clean}"
        if descriptor:
            header += f" - {descriptor}"
        lines.append(header)

        args = svc_info.get("arguments", []) if isinstance(svc_info, dict) else []
        if args:
            lines.append("  args:")
            for a in args:
                a_type = a.get("type", "")
                extra = ""
                if a_type == "ENUM":
                    enum_vals = [str(v).split(" - ")[0] for v in a.get("enum_list", [])]
                    if enum_vals:
                        extra = f" {{{', '.join(enum_vals)}}}"
                    elif a.get("format"):
                        extra = f" ({a['format']})"
                a_desc = a.get("descriptor", "")
                line = f"    - {a.get('id', '?')}: {a_type}{extra}"
                if a_desc:
                    line += f" — {a_desc}"
                lines.append(line)

        if isinstance(svc_info, dict):
            rt = svc_info.get("return_type")
            rt_type = rt.get("type", "") if isinstance(rt, dict) else (rt if isinstance(rt, str) else "")
            if rt_type and rt_type != "VOID":
                lines.append(f"  returns: {rt_type}")
    return "\n".join(lines) if lines else "(no services)"


def _parse_json_dict_of_str_lists(raw: str):
    """Strip reasoning/fences, parse a JSON dict whose values are list[str]
    (or coerce str → [str]). Returns (parsed_dict, reasoning_text).
    """
    reasoning_text = _extract_reasoning(raw)
    cleaned = _strip_llm_wrappers(raw)
    parsed = {}

    def _ingest(obj):
        if not isinstance(obj, dict):
            return
        for k, v in obj.items():
            if isinstance(v, list):
                parsed[k] = [str(s) for s in v if isinstance(s, str)]
            elif isinstance(v, str):
                parsed[k] = [v]

    try:
        _ingest(json.loads(cleaned))
    except Exception:
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            try:
                _ingest(json.loads(m.group(0)))
            except Exception:
                pass
    return parsed, reasoning_text


def _balance_brackets(text: str) -> str:
    """Best-effort repair of an unbalanced JSON object string. Scans for the
    first `{`, walks the rest tracking `{}`/`[]` depth (ignoring brackets inside
    strings), and appends the closing brackets still open at end-of-input in the
    correct order. Drops any stray closers that would go negative. Returns "" if
    no opening brace is found."""
    start = text.find('{')
    if start < 0:
        return ""
    s = text[start:]
    stack = []
    in_str = False
    esc = False
    out_chars = []
    for ch in s:
        if in_str:
            out_chars.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            out_chars.append(ch)
        elif ch in '{[':
            stack.append(ch)
            out_chars.append(ch)
        elif ch in '}]':
            want = '{' if ch == '}' else '['
            if stack and stack[-1] == want:
                stack.pop()
                out_chars.append(ch)
            # else: stray/mismatched closer → skip it
        else:
            out_chars.append(ch)
    if in_str:
        out_chars.append('"')
    closers = {'{': '}', '[': ']'}
    out_chars.extend(closers[b] for b in reversed(stack))
    return "".join(out_chars)


def _iter_top_level_objects(text: str):
    """Return each balanced top-level `{...}` object substring in `text`.
    Used when an LLM emits several JSON objects back-to-back (one per service)
    instead of one merged object — we parse each rather than failing on the blob.
    Brackets inside strings are ignored; unbalanced tails are simply not yielded.
    """
    objs, depth, start, in_str, esc = [], 0, -1, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    objs.append(text[start:i + 1])
                    start = -1
    return objs


def _parse_dict_from_llm(raw: str) -> dict:
    """Generic LLM-output → dict parser. Strips wrappers, tries strict
    json.loads, falls back to regex-bracketed extraction. Returns empty dict
    on total failure so callers can keep going.
    """
    cleaned = _strip_llm_wrappers(raw)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}


def _build_intent_services_block(svcs, details: dict) -> str:
    """Build a MINIMAL services block for the IR extractor.

    Argument values come from Stage 2.5 (arg_resolve) and ENUM cond comparisons
    come from Stage 2.4 (enum_resolve) — both surfaced via the `[Resolved Args]`
    augmentation. The extractor only needs to know, per service:
      - kind (value or function) — chooses `read` vs `call` op
      - return type (non-VOID, simple type only) — informs chain/bind decisions
      - 1-line descriptor — disambiguates intent

    Argument schemas AND ENUM member lists are intentionally OMITTED to prevent
    the extractor from re-deciding values (those are upstream stages' job).

    Format per service:
        Dev.Service  (value|function)  → ReturnType  - descriptor
    """
    lines = []
    for s in svcs:
        if '.' not in s:
            continue
        dev, svc_name = s.split('.', 1)
        svc_name_clean = svc_name.replace("()", "")

        svc_info = (details.get(dev) or {}).get(svc_name_clean)
        dev_data = SERVICE_DATA.get(dev, {})

        is_value = any(e["id"] == svc_name_clean for e in dev_data.get("values", []))
        svc_type = "value" if is_value else "function"

        # Return type (skip if VOID for functions; values always have a type)
        ret_str = ""
        if isinstance(svc_info, dict):
            if svc_type == "value":
                ret_str = svc_info.get("type", "") or ""
            else:
                rt = svc_info.get("return_type")
                if isinstance(rt, dict):
                    rt_type = rt.get("type", "") or ""
                    if rt_type and rt_type != "VOID":
                        ret_str = rt_type
                elif isinstance(rt, str) and rt and rt != "VOID":
                    ret_str = rt

        descriptor = (svc_info or {}).get("descriptor", "") if isinstance(svc_info, dict) else ""

        header = f"{dev}.{svc_name_clean}  ({svc_type})"
        if ret_str:
            header += f" → {ret_str}"
        if descriptor:
            header += f"  - {descriptor}"
        lines.append(header)

    return "\n".join(lines) if lines else "(no services)"


def _enforce_resolved_args(ir_obj, ra: dict) -> None:
    """Override LLM-emitted `call.args` with arg_resolve's authoritative
    dict (verbatim R3). Mutates `ir_obj` in place. Skips $-expression args
    (Delta exception) since arg_resolve doesn't know derived values.
    """
    if not isinstance(ir_obj, dict) or not isinstance(ra, dict):
        return
    timeline = ir_obj.get("timeline")
    if not isinstance(timeline, list):
        return
    counters = {}

    def _walk(steps):
        for step in steps:
            if not isinstance(step, dict):
                continue
            op = step.get("op")
            if op == "if":
                _walk(step.get("then", []) or [])
                _walk(step.get("else", []) or [])
                continue
            if op == "cycle":
                _walk(step.get("body", []) or [])
                continue
            if op != "call":
                continue
            target = step.get("target", "")
            if target not in ra:
                continue
            resolved = ra[target]
            cur_args = step.get("args", {})
            if isinstance(cur_args, dict) and any(
                isinstance(v, str) and v.startswith("$") for v in cur_args.values()
            ):
                continue
            if isinstance(resolved, list):
                idx = counters.get(target, 0)
                if idx < len(resolved) and isinstance(resolved[idx], dict):
                    step["args"] = resolved[idx]
                    counters[target] = idx + 1
            elif isinstance(resolved, dict):
                step["args"] = resolved
            else:
                step["args"] = {}

    _walk(timeline)


def _normalize_logical_ops(ir_obj) -> None:
    """Rewrite C-style `&& || !` to JoI keywords (`and or not`) in
    `cond`/`until` expressions. IR-extractor occasionally slips despite the
    prompt.
    """
    if not isinstance(ir_obj, dict):
        return

    def _fix(s):
        if not isinstance(s, str):
            return s
        s = re.sub(r'\s*&&\s*', ' and ', s)
        s = re.sub(r'\s*\|\|\s*', ' or ', s)
        s = re.sub(r'(^|[\s(])!\s*(?=[A-Za-z_$(])', r'\1not ', s)
        return s

    def _walk(steps):
        for step in steps:
            if not isinstance(step, dict):
                continue
            for k in ("cond", "until"):
                if k in step:
                    step[k] = _fix(step[k])
            op = step.get("op")
            if op == "if":
                _walk(step.get("then", []) or [])
                _walk(step.get("else", []) or [])
            elif op == "cycle":
                _walk(step.get("body", []) or [])

    tl = ir_obj.get("timeline")
    if isinstance(tl, list):
        _walk(tl)


def _inject_implicit_vars(ir_obj) -> None:
    """Auto-inject `var` on prior calls whose method-name suffix is referenced
    via `$<MethodName>` in any later step. Backstop for cases where the
    extractor LLM forgets to declare `var`.
    """
    if not isinstance(ir_obj, dict):
        return
    timeline = ir_obj.get("timeline")
    if not isinstance(timeline, list):
        return

    def _collect_refs(node):
        refs = set()
        if isinstance(node, str):
            for m in re.finditer(r'\$([A-Za-z_][A-Za-z0-9_]*)', node):
                refs.add(m.group(1))
        elif isinstance(node, dict):
            for v in node.values():
                refs |= _collect_refs(v)
        elif isinstance(node, list):
            for v in node:
                refs |= _collect_refs(v)
        return refs

    def _walk(steps):
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            if step.get("op") == "if":
                _walk(step.get("then", []) or [])
                _walk(step.get("else", []) or [])
            elif step.get("op") == "cycle":
                _walk(step.get("body", []) or [])
            if step.get("op") == "call" and "var" not in step and "bind" not in step:
                target = step.get("target", "")
                method = target.rsplit(".", 1)[-1] if "." in target else target
                if not method:
                    continue
                later_refs = set()
                for later in steps[i + 1:]:
                    later_refs |= _collect_refs(later)
                if method in later_refs:
                    step["var"] = method

    _walk(timeline)


def _wrapper_period_from_ir(ir_obj):
    """Deterministic wrapper.period override from IR.cycle.period.

    LLM is unreliable at unit arithmetic ("30 SEC" → 1800000); we compute
    here. D-3 (cycle body has wait edge="rising") is hardcoded to 1000 (1 SEC
    polling) regardless of cycle.period. Returns None if IR has no top-level cycle.
    """
    tl = (ir_obj or {}).get("timeline", [])
    for s in tl:
        if isinstance(s, dict) and s.get("op") == "cycle":
            body = s.get("body") or []
            if any(
                isinstance(x, dict) and x.get("op") == "wait" and x.get("edge") == "rising"
                for x in body
            ):
                return 1000
            p = s.get("period")
            if isinstance(p, str):
                try:
                    return parse_duration_to_ms(p)
                except ValueError:
                    return None
            return None
    return None


def _render_precision_block(precision_output) -> str:
    """Render the precision stage's selectors into the documented
    `[Precision Selectors]` format the lowering prompt expects — one line per
    service, `Service.Method: (#sel) / (#sel2)` — instead of dumping the raw
    `{selectors, resolved, reasoning}` dict via str(). ONLY `selectors` is fed:
    `resolved` (which carries long real device ids) and `reasoning` are pipeline
    bookkeeping the LLM must not see — the real ids are noise the model could
    copy, and selectors already carry the #tags / #dN it needs.
    """
    sels = (precision_output.get("selectors", {})
            if isinstance(precision_output, dict) else {}) or {}
    lines = [f"{svc}: " + " / ".join(sel_list)
             for svc, sel_list in sels.items() if sel_list]
    return "\n".join(lines) if lines else "(none)"


def _normalize_edit_code(raw) -> str:
    """Normalize a client-supplied JoI code block into the `{cron,period,script}`
    JSON shape the re_translate prompt expects.

    Accepts a dict, a JSON string, or a bare script string. The API RESPONSE uses
    key `code` for the script body while the pipeline internally uses `script` —
    accept either. Anything unparseable is treated as a bare script."""
    obj = raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw.strip(), strict=False)
        except Exception:
            obj = None
        if not isinstance(obj, dict):
            return json.dumps({"cron": "", "period": 0, "script": raw.strip()},
                              ensure_ascii=False)
    if isinstance(obj, dict):
        return json.dumps({
            "cron": str(obj.get("cron", "")),
            "period": obj.get("period", 0),
            "script": obj.get("script", obj.get("code", "")),
        }, ensure_ascii=False)
    return json.dumps({"cron": "", "period": 0, "script": str(raw)}, ensure_ascii=False)


def generate_joi_code_ir(
    sentence,
    connected_devices,
    other_params,
    base_url=None,
    current_code=None,
):
    """IR-mediated JoI generation. Drop-in compatible return shape with run_local.generate_joi_code.

    `current_code` (optional): an already-generated JoI block the user wants to
    EDIT. When supplied, `sentence` is treated as the edit request (feedback) and
    a `feedback_fuse` pre-stage merges (current_code + feedback) into one complete
    standalone command; the rest of the pipeline runs unchanged on that command.
    When `current_code` is empty, behavior is identical to a fresh generation."""
    connected_devices = _parse_dict_input(connected_devices, None)
    other_params = _parse_dict_input(other_params, {})

    start = time.perf_counter()
    client = get_client(base_url)
    model = get_model_id(client)

    # Env switches are read per-call (not at import) so in-process callers can
    # toggle them between successive generate_joi_code() invocations.
    _IR_ONLY = os.environ.get("JOI_IR_ONLY", "0") == "1"
    _IR_DUMP_DIR = os.environ.get("JOI_IR_DUMP_DIR", "/tmp/joi_ir_dump")
    _IR_DUMP_NAME = os.environ.get("JOI_IR_DUMP_NAME", "")

    log_buf = []

    def infer(key, user_input, *, system=None, enable_thinking=False, max_tokens=512, prefill=None):
        sys_content = system or PROMPTS.get(key, "")
        content, log_line = run_llm_inference(model, client, key, [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_input}
        ], enable_thinking=enable_thinking, max_tokens=max_tokens, prefill=prefill)
        log_buf.append(log_line)
        if enable_thinking:
            content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL).strip()
        return content

    def infer_followup(key, user_input, *, system, prior_user, prior_assistant):
        """Multi-turn inference that reuses a prior (user, assistant) exchange so
        the KV cache hits on the shared prefix. The follow-up question goes in as
        the next user turn."""
        content, log_line = run_llm_inference(model, client, key, [
            {"role": "system", "content": system},
            {"role": "user", "content": prior_user},
            {"role": "assistant", "content": prior_assistant},
            {"role": "user", "content": user_input},
        ])
        log_buf.append(log_line)
        return content

    # ── Device prep — the dN aliasing built here is reused by every device stage.
    if not isinstance(connected_devices, dict) or not connected_devices:
        raise JoiGenerationError(
            "No connected devices provided.",
            "\n".join(log_buf),
            error_code="no_devices",
        )
    cd_simple = {}
    for k, v in connected_devices.items():
        raw_tags = v.get("tags", [])
        tags = [t for t in raw_tags if isinstance(t, str)]
        raw_cat = v.get("category", [])
        if isinstance(raw_cat, str):
            cats = [raw_cat]
        elif isinstance(raw_cat, list):
            cats = [c for c in raw_cat if isinstance(c, str)]
        else:
            cats = []
        cd_simple[k] = {"category": cats, "tags": [t for t in tags if t not in cats]}

    # ── ID aliasing: anonymize device ids as d1/d2/... once, shared across the
    # device stages (grounding returns dN ids; minimal_tags derives selector tags
    # from them; real_of maps any dN that survives into the selector back to real).
    real_ids = list(cd_simple.keys())
    alias_of = {real: f"d{i+1}" for i, real in enumerate(real_ids)}
    real_of = {a: r for r, a in alias_of.items()}
    # dN-aliased device dict shared with the device stages.
    cd_aliased = {
        alias_of[r]: {
            "category": cd_simple[r]["category"],
            "tags": list(cd_simple[r]["tags"]),
        }
        for r in real_ids
    }

    # ── Device-first pipeline (the only path). Runs on the raw Korean command:
    # device_retrieve (command-only) → ground_targets (LLM, devices) → minimal_tags
    # (Python) → device_resolve → quantifier (Python) → translation → arg_resolve/IR
    # → lowering → naming. Produces `selected_services` + `_df_precision` (selectors)
    # directly, so run_precision returns them instead of a device-match LLM call.
    # `original_sentence` keeps the Korean wording for arg_resolve's human-facing
    # text (Speaker/Toast); the device stages read it directly (no preprocess/MT).

    # ── Stage 0 (optional): feedback edit. When the caller passes an existing
    # `current_code` block, `sentence` is an EDIT request. Instead of blindly
    # fusing code + feedback, we split it into two steps:
    #   1. UNDERSTAND the code — re_translate (code → EN NL) → re_translate_kor
    #      (→ KO NL). This recovers what the current automation does, in words.
    #   2. PARTIAL EDIT — feedback_edit applies ONLY the requested change to that
    #      NL command, keeping everything else.
    # The resulting command flows through the normal pipeline unchanged. Empty
    # current_code → skip entirely (fresh-generation path is byte-identical).
    # (The edit-prompt still needs work for complex commands; re_translate is the
    # interim code-understanding step.)
    if current_code:
        code_block = _normalize_edit_code(current_code)
        current_nl = ""
        try:
            _cur_en = infer("re_translate", f"[Code]\n{code_block}", max_tokens=512).strip()
            log_buf.append(f"📝 edit re_translate (EN): {_cur_en}")
            _cur_ko = infer("re_translate_kor", _cur_en, max_tokens=1024).strip() if _cur_en else ""
            if _cur_ko:
                log_buf.append(f"📝 edit re_translate (KO): {_cur_ko}")
            current_nl = _cur_ko or _cur_en
        except Exception as _e:
            log_buf.append(f"⚠️ edit code-understanding failed ({_e}) — editing raw feedback")
        if current_nl:
            edited = infer(
                "feedback_edit",
                f"[Current Command]\n{current_nl}\n\n[Edit Request]\n{sentence}",
                max_tokens=512,
            ).strip()
            # Fail open: on empty output keep the raw feedback as the command.
            if edited:
                log_buf.append(
                    f"✏️ feedback_edit: {sentence!r} on {current_nl!r} → {edited!r}")
                sentence = edited
            else:
                log_buf.append("⚠️ feedback_edit produced empty output — using raw feedback")

    original_sentence = sentence

    # cd_named: dN-keyed device dict (nickname + real category/tags). Shared with
    # the GROUNDING stage. device_retrieve itself no longer sees devices.
    cd_named = {
        a: {"category": cd_aliased[a]["category"],
            "tags": cd_aliased[a]["tags"],
            "nickname": connected_devices.get(real_of[a], {}).get("nickname", "")}
        for a in cd_aliased
    }

    # ── Stage 1: device_retrieve (LLM, COMMAND ONLY) — parses the language into
    # target groups: role | by=label:<verbatim phrase> / channel:… | scope. It does
    # NOT see devices and never decides existence (no NONE here — that's grounding).
    targets = []
    for _attempt in range(2):  # retrieve occasionally emits an empty/malformed block
        retr_raw = infer("device_retrieve", f"[Command]\n{sentence}", max_tokens=512).strip()
        _tm = re.search(r'<targets>(.*?)</targets>', retr_raw, re.DOTALL)
        targets_spec = (_tm.group(1).strip() if _tm else retr_raw).strip()
        targets = parse_targets(targets_spec)
        if targets:
            break
        log_buf.append("⚠️ device_retrieve produced no targets — retrying once")
    if not targets:
        raise JoiGenerationError(
            "No target groups parsed from device_retrieve.",
            "\n".join(log_buf), error_code="reasoning_failed",
        )

    # ── Stage 2: grounding. The ground_targets LLM maps each label phrase to a
    # CRITERION (tag/category/nickname tokens, `+`=AND, `;`=OR-cluster) — NOT a raw
    # device list. Python then resolves the criterion to device sets deterministically
    # (exact, no LLM mis-pick), one selector CLUSTER per OR-group. A `channel:` target
    # is resolved by category in Python.
    from device_ontology import (quantifier_for as _qf, _CHANNEL_CATEGORY as _CHCAT,
                                  minimal_tags_for as _min_tags,
                                  resolve_criterion as _resolve_crit)
    label_targets = [t for t in targets if t["by_kind"] == "label"]
    grounded = {}   # label-target-index → criterion string
    if label_targets:
        _phrases = "\n".join(f"{i+1}. {t['by_val']}" for i, t in enumerate(label_targets))
        # Prefix-cache layout: the (near-constant within a session) [Devices] dump
        # goes FIRST so `system + [Devices]` forms a shared prefix that vLLM's
        # prefix cache reuses across commands. The per-command [Command]/[Phrases]
        # — the only parts that vary request-to-request — go LAST so they never
        # invalidate the cached device-block prefix.
        ground_user = (
            f"[Devices]\n{json.dumps(cd_named, indent=2, ensure_ascii=False)}\n\n"
            f"[Command]\n{sentence}\n\n"
            f"[Phrases]\n{_phrases}"
        )
        ground_raw = infer("ground_targets", ground_user, max_tokens=512).strip()
        _gm = re.search(r'<grounded>(.*?)</grounded>', ground_raw, re.DOTALL)
        for ln in (_gm.group(1) if _gm else ground_raw).splitlines():
            m = re.match(r'\s*(\d+)\.\s*.*?\|\s*(.+?)\s*$', ln)
            if m:
                grounded[int(m.group(1)) - 1] = m.group(2).strip()

    def _mk_group(t, ids, sel_tags):
        cats = sorted({c for a in ids for c in cd_named.get(a, {}).get("category", [])})
        return {**t, "ids": ids, "categories": cats, "sel_tags": sel_tags or list(ids)}

    groups, li = [], 0
    for t in targets:
        if t["by_kind"] == "channel":
            # ONE group PER channel (speaker,toast → a Speaker group AND a
            # ToastPublisher group), each with its own single-category selector.
            # Never one (#Speaker #Toast) group — that intersection selects nothing.
            for ch in t["by_val"].split(","):
                cat = _CHCAT.get(ch.strip().lower())
                cids = [a for a in cd_named if cat and cat in cd_named[a]["category"]]
                if cids:
                    st, _ = _min_tags(cids, cd_named)
                    groups.append(_mk_group(t, cids, st))
            continue
        # label → criterion → OR-groups of device ids (one selector cluster each)
        crit = grounded.get(li, "")
        li += 1
        or_groups = _resolve_crit(crit, cd_named) if crit.upper() != "NONE" else []
        if not or_groups:
            raise JoiGenerationError(
                f"Cannot fulfill command — no connected device for {t['by_val']!r}",
                "\n".join(log_buf), error_code="device_not_connected",
            )
        for grp_ids in or_groups:
            sel_tags, _ = _min_tags(grp_ids, cd_named)
            groups.append(_mk_group(t, grp_ids, sel_tags))

    # ── Stage 3: device_resolve — pick the SERVICE per group; echo the given tags.
    target_lines = [
        f"- role={g['role']} | tags={' '.join('#'+x for x in g['sel_tags'])} | "
        f"{len(g['ids'])} devices matched" for g in groups]
    resolve_cats = sorted({c for g in groups for c in g["categories"]})
    resolve_user = (
        f"[Command]\n{sentence}\n\n"
        f"[Targets]\n" + "\n".join(target_lines) + "\n\n"
        f"[Device Summary]\n{_build_device_selection_rules(resolve_cats)}"
    )
    # Force the `<Reasoning>` header so the model can't slip into the legacy
    # `["Skill.Method"]` array form or drop the RESULT: block.
    resolve_raw = infer("device_resolve", resolve_user,
                        system=PROMPTS.get("device_resolve", ""),
                        prefill="<Reasoning>\n").strip()
    _err = re.search(r'(?im)^\s*ERROR:\s*(.+?)\s*$', resolve_raw)
    if _err:
        log_buf.append(f"⛔ device_resolve ERROR: {_err.group(1)}")
        raise JoiGenerationError(
            f"Cannot fulfill command — {_err.group(1)}",
            "\n".join(log_buf), error_code="device_not_connected",
        )
    # Split on the `RESULT` header tolerantly — the model sometimes drops the
    # trailing colon (`RESULT` vs `RESULT:`), which otherwise zeroes the block
    # and yields a spurious "no usable calls" (non-deterministic failure).
    _rmatch = re.search(r"RESULT\s*:?\s*\n", resolve_raw)
    result_block = resolve_raw[_rmatch.end():].strip() if _rmatch else ""
    # New RESULT format: one line per service, `Cat.Method: (#a), (#b)` — the
    # service is chosen by the model, the tag(s) are COPIED from [Targets] (given
    # to it), so the model can no longer invent a wrong tag (e.g. `#Switch`). We
    # expand each `service: tags` line back into per-tag `(#tag).Cat.Method`
    # selector strings so the deterministic skill-filter / quantifier loop below
    # is unchanged. Legacy `(#tag).Cat.Method` lines are still accepted verbatim.
    # Normalize the `<service>:` key each RESULT line into a clean `Cat.Method`:
    # the model sometimes drops the category (`Open:` → find its owner Valve) or
    # duplicates the method (`SetFanMode.SetFanMode:` → `Fan.SetFanMode`). We
    # resolve the owning category from the catalog (SERVICE_DATA) by method name.
    def _method_owner(method):
        for cat in resolve_cats:
            d = SERVICE_DATA.get(cat, {})
            if any(e.get("id") == method for e in d.get("values", [])) or \
               any(e.get("id") == method for e in d.get("functions", [])):
                return cat
        return None

    def _canonical_svc(raw_svc):
        parts = raw_svc.split(".")
        method = parts[-1]
        owner = _method_owner(method)
        if owner:
            return f"{owner}.{method}"
        # method not found under any target category — keep a 2-part form as-is
        return raw_svc if "." in raw_svc else None

    raw_selectors = []
    for ln in result_block.splitlines():
        ln = ln.strip()
        if not ln or "(" not in ln:
            continue
        # `<service>: (#a), (#b)` — service may be `Cat.Method`, bare `Method`,
        # or a duplicated `Method.Method`; all normalized to `Cat.Method`.
        m = re.match(r'^([A-Za-z][\w.]*)\s*:\s*(.+)$', ln)
        if m and "(" in m.group(2):
            svc = _canonical_svc(m.group(1))
            if svc:
                for sel in re.findall(r'(?:all|any|one)?\s*\(#[^)]*\)', m.group(2)):
                    raw_selectors.append(f"{sel.strip()}.{svc}")
                continue
        if ")" in ln:  # legacy `(#tag).Cat.Method`
            raw_selectors.append(ln)

    # ── Deterministic quantifier: resolve emits NO prefix; we add all/any/one from
    # each group's scope + role + match count. Map a selector's tag → its group.
    tag_to_group = {}
    for g in groups:
        for t in g["sel_tags"]:
            tag_to_group[t] = g
    selectors = []
    # Deterministic on/off fallback: when a Light cluster has NO `Switch`
    # sub-category, `Switch.On/Off` is undeliverable. Instead of dropping (→
    # "no usable calls" error), rewrite to `Light.MoveToBrightness` with forced
    # args (ON→100, OFF→0, Rate 0.0) — collected here, merged into resolved_args
    # after arg_resolve so `_enforce_resolved_args` writes them verbatim.
    _fallback_args = {}
    for s in raw_selectors:
        s = re.sub(r'^\s*(all|any|one)\s*\(', '(', s)  # drop any LLM-emitted prefix
        first_tag = re.search(r'#([A-Za-z0-9_\-]+)', s)
        g = tag_to_group.get(first_tag.group(1)) if first_tag else None
        # Skill filter (DEVICE-level): a call's `.Category.` is the capability it needs.
        # Keep only the group's devices that ACTUALLY have that category, then rebuild
        # the selector for that subset. A whole-group miss drops the call. e.g. a #Tuya
        # group spans sensors+switches → `Switch.Off` narrows to `(#Tuya #Switch)` (the
        # 8 switchable), not all 16; `Light.MoveToBrightness` onto a Switch-only cluster
        # → empty → dropped. (Cluster-level checks missed partial-capability groups.)
        _svc = re.search(r'\)\.([A-Za-z]\w*)\.', s)
        if g and _svc:
            cat = _svc.group(1)
            capable = [a for a in g["ids"] if cat in cd_named[a]["category"]]
            if not capable:
                # Light-only fallback: Switch.On/Off onto a Switch-less Light
                # cluster → Light.MoveToBrightness(ON 100 / OFF 0, Rate 0.0).
                method = s.rsplit(".", 1)[-1].strip("()")
                light_ids = [a for a in g["ids"] if "Light" in cd_named[a]["category"]]
                if cat == "Switch" and method in ("On", "Off") and light_ids:
                    bright = 100.0 if method == "On" else 0.0
                    nt, _ = _min_tags(light_ids, cd_named)
                    nt = nt or light_ids
                    s = re.sub(r'\(#[^)]*\)\.\w+\.\w+',
                               "(#" + " #".join(nt) + ").Light.MoveToBrightness", s, count=1)
                    g = {**g, "ids": light_ids, "sel_tags": nt,
                         "categories": sorted({c for a in light_ids
                                               for c in cd_named[a]["category"]})}
                    _fallback_args.setdefault("Light.MoveToBrightness", []).append(
                        {"Brightness": bright, "Rate": 0.0})
                    log_buf.append(
                        f"↩️ fallback Switch.{method} → Light.MoveToBrightness({bright}, 0.0): {s}")
                else:
                    log_buf.append(f"🚫 drop call (no {cat} device in cluster): {s}")
                    continue
            elif len(capable) < len(g["ids"]):
                new_tags, _ = _min_tags(capable, cd_named)
                new_tags = new_tags or capable
                s = re.sub(r'\(#[^)]*\)', "(#" + " #".join(new_tags) + ")", s, count=1)
                g = {**g, "ids": capable, "sel_tags": new_tags,
                     "categories": sorted({c for a in capable
                                           for c in cd_named[a]["category"]})}
        q = _qf(g["scope"], g["role"], len(g["ids"])) if g else ""
        full = (q + s) if q else s
        selectors.append((full, g))

    # ── Adapt device-first selectors → the IR pipeline's contract ──
    # Split `<quant>(#tags).Cat.Method` into selected_services (Cat.Method, in
    # order) + precision_output ({selectors:{svc:[<quant>(#tags)]}, resolved}).
    # Then translate the command to English (IR/lowering prompts are English;
    # original_sentence stays Korean for arg_resolve's human-facing text), and
    # fall through to the shared arg_resolve → IR → lowering → naming path.
    selected_services = []
    df_selectors, df_resolved = {}, {}
    _df_read_services = set()
    # A nickname target resolves to the device's internal dN handle; the FINAL
    # selector must carry the device's REAL id (which is one of its own tags in
    # the payload), not the alias, or it matches nothing on the hub. Label/channel
    # tags (#Light, #Tuya, #Speaker) are already real tags and pass through.
    def _restore_ids(sel: str) -> str:
        return re.sub(r'#(d\d+)\b',
                      lambda mm: '#' + real_of.get(mm.group(1), mm.group(1)), sel)
    _sel_re = re.compile(r'^\s*(all|any)?\s*(\(#[^)]*\))\.([A-Za-z]\w*\.[A-Za-z]\w*)')
    for full, g in selectors:
        m = _sel_re.match(full)
        if not m:
            continue
        # Keep dN aliases in the selector through IR/lowering — the LLM only ever
        # copies a short `#dN`, not a 36-char real id (transcription-safe). They are
        # restored to real ids once, post-lowering, in _finalize.
        quant, sel_tags, svc = (m.group(1) or ""), m.group(2), m.group(3)
        selected_services.append(svc)
        df_selectors.setdefault(svc, []).append(f"{quant}{sel_tags}")
        if g:
            df_resolved[svc] = {"q": (quant or "one"),
                                "devices": [real_of.get(a, a) for a in g["ids"]]}
            if g.get("role") == "read":
                _df_read_services.add(svc)
    if not selected_services:
        raise JoiGenerationError(
            "device_resolve produced no usable calls.",
            "\n".join(log_buf), error_code="reasoning_failed",
        )
    _df_precision = {"selectors": df_selectors, "resolved": df_resolved,
                     "reasoning": "[device-first] selectors from device_resolve"}
    # Korean → English for the downstream IR/lowering stages. original_sentence
    # (Korean) is already captured; keep it for arg_resolve language routing.
    if re.search(r"[가-힣]", sentence):
        sentence = infer("translation", sentence)
    # (fall through — no early return; shared pipeline below builds the JoI code)


    local_service_details = extract_service_details(selected_services, SERVICE_DATA)

    intent_categories = list(set(s.split('.')[0] for s in selected_services if '.' in s))
    if not intent_categories:
        raise JoiGenerationError(
            f"No services found for the command: '{sentence}'.",
            "\n".join(log_buf),
            error_code="no_services",
        )

    # ── Resolve / precision / ir-extract input prep ──
    enum_value_targets = [s for s in selected_services if _is_enum_value_service(s)]

    def _has_arguments(s: str) -> bool:
        """True only if this function takes at least one argument. VOID/no-arg
        functions (e.g. Switch.Off, DoorLock.Lock) need nothing resolved, so we
        skip the arg_resolve LLM call for them entirely."""
        if '.' not in s:
            return False
        dev, method = s.split('.', 1)
        method = method.replace("()", "")
        info = (local_service_details.get(dev) or {}).get(method) or {}
        return bool(isinstance(info, dict) and info.get("arguments"))

    # Only functions that ACTUALLY take args go to arg_resolve. A no-arg function
    # still needs to appear downstream (IR `call` op), but its args are just `{}`.
    arg_services = [s for s in selected_services
                    if _is_function_service(s) and _has_arguments(s)]
    # Value-reads to surface to arg_resolve as `[Readable Values]` (referenced via
    # `$<Method>` inside a text arg, e.g. $Hour). Scoped to `read`-role services
    # (Clock.Hour/Minute) so condition-gate reads (ContactSensor.Contact, etc.) are
    # NOT exposed — otherwise arg_resolve mis-grabs them for unrelated $<ref> args
    # (e.g. a mail File arg). Legacy path (no role info) falls back to all reads.
    if _df_read_services is not None:
        value_reads_in_scope = [s for s in selected_services if s in _df_read_services]
    else:
        value_reads_in_scope = [s for s in selected_services if not _is_function_service(s)]

    # ── Resolve branch: enum_cond_check → enum_resolve → arg_resolve (sequential within branch) ──
    def run_resolve_branch():
        resolved_enum_conds_local = {}
        if enum_value_targets:
            yesno_user = (
                f"[Command]\n{sentence}\n\n"
                "[ENUM-Value Targets]\n"
                f"{json.dumps(enum_value_targets, ensure_ascii=False)}\n\n"
                "For any of these value services, does the command imply a "
                "condition expression that compares the read value to a SPECIFIC "
                "enum member (e.g., `Service == \"someMember\"`)? Answer with one "
                "lowercase word: yes or no."
            )
            yesno_raw = infer(
                "enum_cond_check",
                yesno_user,
                system=PROMPTS.get("enum_cond_check", ""),
            )
            need_enum_resolve = yesno_raw.strip().lower().startswith("yes")
            log_buf.append(f"🔎 enum_cond_check → {yesno_raw.strip()}")

            if need_enum_resolve:
                enum_input = _build_enum_resolve_input(
                    sentence, enum_value_targets, local_service_details
                )
                enum_hints = _build_device_specific_hints(enum_value_targets, "enum_resolve")
                if enum_hints:
                    enum_input += f"\n\n[Device-specific Enum Hints]\n{enum_hints}"
                enum_raw = infer(
                    "enum_resolve",
                    enum_input,
                    system=PROMPTS.get("enum_resolve", ""),
                )
                parsed_er = _parse_dict_from_llm(enum_raw)
                for k, v in parsed_er.items():
                    if v is None:
                        continue
                    if isinstance(v, dict) and "value" in v:
                        resolved_enum_conds_local[k] = {
                            "op": v.get("op", "=="),
                            "value": v["value"],
                        }

        resolved_args_local = {}
        if arg_services:
            # Language-routed device hints: Korean input pulls the `# @ArgResolveKo`
            # section (Korean honorific examples), English pulls `# @ArgResolve`
            # (English examples). Feeding the model ONE language of few-shot prevents
            # English commands from drifting into Korean text (and vice versa). Falls
            # back to the default section when a category has no Ko-specific block.
            is_ko = original_sentence != sentence
            arg_hints = _build_device_specific_hints(
                arg_services, "arg_resolve_ko" if is_ko else "arg_resolve"
            )
            if is_ko and not arg_hints:
                arg_hints = _build_device_specific_hints(arg_services, "arg_resolve")
            # When the input was translated (Korean → English), also pass the
            # verbatim original so human-facing text args (ToastPublisher Title/
            # Message, Speaker Text, MenuProvider) can be written in the user's own
            # language/wording. English-only input: omit (it would duplicate [Command]).
            orig_block = (
                f"[User Command (original, verbatim)]\n{original_sentence}\n\n"
                if is_ko else ""
            )
            readable_block = (
                "\n\n[Readable Values] (in scope — reference inside a text arg via "
                "`$<Method>`, e.g. `$Hour`; do NOT add them as separate output keys)\n"
                f"{json.dumps(value_reads_in_scope, ensure_ascii=False)}"
                if value_reads_in_scope else ""
            )
            arg_resolve_input = (
                f"[Command]\n{sentence}\n\n"
                + orig_block
                + f"[Selected Services]\n{json.dumps(arg_services, ensure_ascii=False)}\n\n"
                f"[Service Details]\n{_build_arg_resolve_input(arg_services, local_service_details)}"
                + readable_block
                + (f"\n\n[Device-specific Arg Hints]\n{arg_hints}" if arg_hints else "")
            )
            arg_resolve_raw = infer(
                "arg_resolve",
                arg_resolve_input,
                system=PROMPTS.get("arg_resolve", ""),
            )
            resolved_args_local = _parse_dict_from_llm(arg_resolve_raw)

        return resolved_args_local, resolved_enum_conds_local

    # ── Precision branch: command + selected services → JSON dict of selectors ──
    def run_precision():
        # device-first already produced the selectors via device_resolve.
        return _df_precision

    # ── IR extract (sequential, after both branches finish) ──
    def run_ir_extract():
        intent_services_block = _build_intent_services_block(selected_services, local_service_details)

        # Build the [Resolved Args] augmentation block from arg_resolve output.
        # Format expected by the extractor prompt:
        #   Service.Method: {arg: value, ...}
        # The extractor copies these values verbatim into call.args (no re-decision).
        aug_parts = []
        if (isinstance(resolved_args, dict) and resolved_args) or resolved_enum_conds:
            ra_lines = ["[Resolved Args]",
                        "Use these argument values verbatim in matching `call` ops. Do NOT invent or override.",
                        "Services with `{}` have no arguments — emit `args: {}` exactly."]
            if isinstance(resolved_args, dict):
                for svc, vals in resolved_args.items():
                    ra_lines.append(f"  {svc}: {json.dumps(vals, ensure_ascii=False)}")
            if resolved_enum_conds:
                ra_lines.append("")
                ra_lines.append(
                    "Value-service condition specs (slot directly into `wait`/`if` "
                    "expressions; do NOT re-decide the operator or right-hand value):"
                )
                for svc, spec in resolved_enum_conds.items():
                    ra_lines.append(f"  {svc}: {json.dumps(spec, ensure_ascii=False)}")
            aug_parts.append("\n".join(ra_lines))

            # Bind Hints: methods referenced via $<Method> in any later arg value.
            # arg_resolve is the chain-decision authority; we just propagate.
            bind_methods = set()
            _ref_re = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)')
            for vals in resolved_args.values():
                if isinstance(vals, dict):
                    for v in vals.values():
                        if isinstance(v, str):
                            bind_methods.update(_ref_re.findall(v))
            hints_body = "\n".join(sorted(bind_methods)) if bind_methods else "(none)"
            aug_parts.append("[Bind Hints]\n" + hints_body)

        # NOTE: Color name → xy table is owned by arg_resolve (§5.5 in
        # arg_resolve.md). It populates ColorX/ColorY directly into [Resolved
        # Args]; the extractor copies them verbatim via R3 and never sees the
        # table.

        augmentations = "\n\n".join(aug_parts) if aug_parts else None
        # IR-extract with structural-validation retry loop. Each attempt:
        # 1. Call the LLM (single-turn first, multi-turn on retry).
        # 2. Run `validate_ir_against_devices` + `validate_ir_against_catalog`
        #    against the produced IR.
        # 3. On IRValidationError, derive a typed retry hint from the
        #    structured violations and re-run with (prior_user, prior_assistant,
        #    hint) — only the extract stage retries; upstream/downstream
        #    stages remain single-call.
        from paper.simulators.catalog import load_catalog as _load_cat
        catalog_obj = _load_cat()
        _IR_MAX_ATTEMPTS = int(os.environ.get("JOI_IR_EXTRACT_MAX_ATTEMPTS", "2"))

        ir = None
        retry_ctx: tuple[str, str, str] | None = None
        last_violations: list = []
        last_err: Exception | None = None
        for _attempt in range(1, _IR_MAX_ATTEMPTS + 1):
            try:
                ir, _prompt_tok, _comp_tok, _elapsed, _user_msg, _assistant_msg = extract_ir(
                    sentence,
                    devices=intent_services_block,
                    base_url=base_url,
                    debug=False,
                    auto_translate=False,
                    augmentations=augmentations,
                    retry_context=retry_ctx,
                )
            except IRValidationError as e:
                raise JoiGenerationError(
                    f"IR extraction failed: {e}",
                    "\n".join(log_buf),
                    error_code="ir_invalid",
                )
            _decode_tps = _comp_tok / _elapsed if _elapsed > 0 and _comp_tok else 0
            log_buf.append(
                f"➡️ timeline_ir_extract({_prompt_tok}) | attempt {_attempt} | "
                f"Decode: {_decode_tps:.1f} t/s | Total: {_elapsed:.4f}s\n"
                "===================================================\n"
                f"{json.dumps(ir, ensure_ascii=False, indent=2)}"
            )
            if isinstance(ir, dict) and "error" in ir:
                raise JoiGenerationError(
                    f"IR extractor rejected the command: {ir.get('error')}",
                    "\n".join(log_buf),
                    error_code="ir_rejected",
                )
            try:
                validate_ir_against_devices(ir, connected_devices)
                validate_ir_against_catalog(ir, catalog_obj)
                last_violations = []
                break  # all validators passed
            except IRValidationError as e:
                last_err = e
                last_violations = list(e.violations)
                log_buf.append(
                    f"⚠️ IR-extract attempt {_attempt} validator: "
                    + "; ".join(v.code for v in last_violations)
                )
                if _attempt >= _IR_MAX_ATTEMPTS:
                    break
                hint = build_extract_retry_hint(last_violations)
                retry_ctx = (_user_msg, _assistant_msg, hint)

        if last_violations:
            # All attempts exhausted while still failing validation. Surface
            # the kind that failed last as the error_code so callers can
            # branch on it.
            kinds = sorted({v.code for v in last_violations})
            primary = "ir_catalog_member_mismatch" if any(
                v.code in ("member_not_in_service", "service_not_in_catalog",
                           "arg_not_in_catalog") for v in last_violations
            ) else "ir_catalog_mismatch"
            raise JoiGenerationError(
                f"IR catalog validation failed after {_IR_MAX_ATTEMPTS} attempts: "
                f"codes={kinds}; {last_err}",
                "\n".join(log_buf),
                error_code=primary,
            )
        return ir

    # ── Stage 3: (resolve → ir_extract) || precision (parallel) ──
    # Branch A (resolve+ir): enum_cond_check → enum_resolve → arg_resolve → ir_extract
    #   (sequential within branch; IR is selector-free so no precision dependency).
    # Branch B (precision): command + selected services → selector dict.
    # Branches are fully parallel — IR no longer waits for precision.
    def run_resolve_and_ir_branch():
        resolved_args_local, resolved_enum_conds_local = run_resolve_branch()
        # Deterministic on/off fallback args (Light.MoveToBrightness) win over
        # anything arg_resolve produced for that service.
        for _svc, _vals in _fallback_args.items():
            resolved_args_local[_svc] = _vals[0] if len(_vals) == 1 else _vals
        # Stash on enclosing names so run_ir_extract picks them up.
        nonlocal resolved_args, resolved_enum_conds
        resolved_args = resolved_args_local
        resolved_enum_conds = resolved_enum_conds_local
        return run_ir_extract()

    resolved_args = {}
    resolved_enum_conds = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_branch_a = executor.submit(run_resolve_and_ir_branch)
        f_precision = executor.submit(run_precision)
        ir = f_branch_a.result()
        precision_output = f_precision.result()

    service_details = local_service_details

    # IR post-process trio. See module-level helper docstrings for semantics:
    # _enforce_resolved_args (R3 verbatim override), _normalize_logical_ops
    # (C-style → JoI keywords), _inject_implicit_vars (`var` backstop).
    _enforce_resolved_args(ir, resolved_args)
    _normalize_logical_ops(ir)
    _inject_implicit_vars(ir)

    # Structural feasibility gate (grammar G membership): reject IRs that are
    # malformed (break outside a cycle, mis-anchored start_at) or that JoI
    # cannot express (nested / multiple top-level loops). Fail closed before
    # lowering — no JoI is generated for an infeasible IR.
    try:
        check_feasibility(ir)
    except FeasibilityError as e:
        log_buf.append(f"⛔ feasibility: {e}")
        raise JoiGenerationError(
            f"IR infeasible: {e}", "\n".join(log_buf), error_code="ir_infeasible",
        )

    ir_readable = ir_to_readable(ir)
    # Device-scoped confirmation rendering: the selector-free IR plus the
    # precision stage's resolved devices, naming the actual devices the rule
    # acts on. Falls back to the plain readable when no devices were resolved.
    _resolved_devs = (
        precision_output.get("resolved", {})
        if isinstance(precision_output, dict) else {}
    )
    try:
        ir_readable_scoped = (
            render_ir_with_devices(ir, _resolved_devs) if _resolved_devs else ir_readable
        )
    except Exception:
        ir_readable_scoped = ir_readable
    ir_json_str = json.dumps(ir, ensure_ascii=False, indent=2)

    bucket = classify_ir(ir)

    # === IR-only short-circuit ===
    # When JOI_IR_ONLY=1, persist all state needed to resume lowering later
    # and return without running Stage 4. The dump captures the exact inputs
    # that lowering would have consumed (sentence, ir, precision_output,
    # service_details, connected_devices, bucket) plus IR provenance (the
    # resolved_args / resolved_enum_conds that were folded into IR).
    if _IR_ONLY:
        os.makedirs(_IR_DUMP_DIR, exist_ok=True)
        dump_name = _IR_DUMP_NAME or f"row_{int(time.time()*1000)}"
        dump_path = os.path.join(_IR_DUMP_DIR, f"{dump_name}.json")
        precision_for_dump = (
            precision_output if isinstance(precision_output, dict)
            else {"selectors": {}, "reasoning": str(precision_output)}
        )
        elapsed = time.perf_counter() - start
        dump_obj = {
            "sentence": sentence,
            "connected_devices": connected_devices,
            "ir": ir,
            "ir_readable": ir_readable,
            "ir_readable_scoped": ir_readable_scoped,
            "bucket": bucket,
            "precision": precision_for_dump,
            "service_details": service_details,
            "resolved_args": resolved_args,
            "resolved_enum_conds": resolved_enum_conds,
            "elapsed_seconds": elapsed,
            "log": "\n".join(log_buf),
        }
        with open(dump_path, "w", encoding="utf-8") as _f:
            json.dump(dump_obj, _f, ensure_ascii=False, indent=2)
        log_buf.append(f"💾 IR-only dump: {dump_path}")
        return {
            "code": "",
            "ir": ir,
            "ir_readable": ir_readable,
            "ir_readable_scoped": ir_readable_scoped,
            "precision": precision_for_dump.get("selectors", {}),
            "precision_reasoning": precision_for_dump.get("reasoning", ""),
            "ir_dump_path": dump_path,
            "log": {
                "response_time": f"{elapsed:.4f} seconds",
                "logs": "\n".join(log_buf),
            },
        }

    # === Stage 4 (joi_from_ir lowering) ===
    log_buf.append(f"📦 IR bucket: {bucket}")
    prompt_key = f"joi_from_ir_{bucket}"
    try:
        system_prompt = _load_lowering_prompt(bucket, ir=ir)
    except FileNotFoundError as e:
        raise JoiGenerationError(
            f"Lowering prompt missing: {e}",
            "\n".join(log_buf),
            error_code="missing_lowering_prompt",
        )

    joi_input = (
        f"[Command]\n{sentence}\n\n"
        f"[Timeline IR]\n{ir_json_str}\n\n"
        f"[Precision Selectors]\n{_render_precision_block(precision_output)}\n\n"
        f"[Service Details]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
    )
    def _finalize(raw: str) -> dict:
        """Parse + post-process raw LLM output into final joi_block dict.
        Used by both the verifier-on path (per attempt) and verifier-off path."""
        script = re.sub(r'<Reasoning>.*?</Reasoning>', '', raw, flags=re.DOTALL).strip()
        joi_json = {}
        try:
            m = re.search(r'"script"\s*:\s*"(.*?)"\s*\}', script, re.DOTALL)
            if m:
                fixed_inner = m.group(1).replace('\n', '\\n')
                script = script[:m.start(1)] + fixed_inner + script[m.end(1):]
            joi_json = json.loads(script)
            if "script" in joi_json:
                joi_json["script"] = _strip_selector_extra_parens(joi_json["script"])
                joi_json["script"] = _apply_service_prefix(joi_json["script"])
                joi_json["script"] = _normalize_script_newlines(joi_json["script"])
            joi_json.setdefault("name", "Scenario")  # overwritten by naming stage below
            joi_json = {"name": joi_json.pop("name"), **joi_json}
        except (json.JSONDecodeError, TypeError):
            body = _apply_service_prefix(_strip_selector_extra_parens(script))
            joi_json = {
                "name": "Scenario",
                "cron": "",
                "period": 0,
                "script": _normalize_script_newlines(body),
            }

        try:
            _ = validate_joi(joi_json.get("script", ""), connected_devices, _SERVICE_CATEGORY_MAP)
        except Exception as e:
            log_buf.append(f"⚠️ validate_joi warning: {e}")

        _override_ms = _wrapper_period_from_ir(ir)
        if _override_ms is not None and joi_json.get("period") != _override_ms:
            log_buf.append(f"🔧 wrapper.period override: {joi_json.get('period')} → {_override_ms} (from IR cycle.period)")
            joi_json["period"] = _override_ms

        if "script" in joi_json:
            # Re-apply any/all the lowering LLM may have dropped from the precision
            # selectors, THEN canonicalize `any(...) ==` → `all(...) ==|`.
            _sel_map = (precision_output.get("selectors", {})
                        if isinstance(precision_output, dict) else {})
            joi_json["script"] = _reapply_precision_quantifiers(joi_json["script"], _sel_map)
            joi_json["script"] = _post_process_joi_any_quantifiers(joi_json["script"])
            # All prior steps ran in dN space (script + _sel_map consistent); now
            # swap dN aliases → real device ids once, for the final deployed script.
            joi_json["script"] = _restore_ids(joi_json["script"])

        return joi_json

    if _VERIFY_ENABLED:
        # Verifier-on: wrap the lowering call in retry_harness. Retry hints are
        # delivered as a follow-up user turn (B-design): first attempt is a
        # plain `infer(...)` so the prompt distribution is unchanged; only on
        # retry does the prior (user, assistant) exchange get replayed and the
        # retry message appear as the next user turn.
        prev_raw = {"text": None}

        def _lower_fn(ir_arg, hints):
            if hints is None:
                # Paired-design support: when JOI_SEED_JOI_PATH is set, attempt 1
                # returns the pre-generated candidate (e.g. the ungated arm's
                # lowering) instead of calling the LLM, so the verifier+repair
                # loop operates on the exact same candidate the ungated arm
                # deployed. Behavior is unchanged when the env var is unset.
                _seed_path = os.environ.get("JOI_SEED_JOI_PATH")
                if _seed_path:
                    try:
                        with open(_seed_path, encoding="utf-8") as _sf:
                            _seed = json.load(_sf)
                        _seed_joi = _seed.get("joi_block")
                        if isinstance(_seed_joi, dict):
                            prev_raw["text"] = _seed.get("code_raw") or json.dumps(
                                _seed_joi, ensure_ascii=False)
                            log_buf.append(f"🌱 attempt-1 seeded from {_seed_path}")
                            return _seed_joi
                        log_buf.append("⚠️ seed has no joi_block; fresh generation")
                    except Exception as _e:
                        log_buf.append(f"⚠️ seed load failed ({_e}); fresh generation")
                raw = infer(prompt_key, joi_input, system=system_prompt)
            else:
                raw = infer_followup(
                    prompt_key, hints,
                    system=system_prompt,
                    prior_user=joi_input,
                    prior_assistant=prev_raw["text"] or "",
                )
            prev_raw["text"] = raw
            return _finalize(raw)

        try:
            catalog_obj = _load_catalog()
        except Exception as e:
            log_buf.append(f"⚠️ verifier disabled (catalog load failed): {e}")
            catalog_obj = None

        # Debug: show the synthesized scenarios the verifier will exercise
        # (currently event_synth returns a single scenario; cap at 2 for future).
        try:
            from paper.simulators.event_synth import synthesize_scenarios as _synth
            _scns = _synth(ir)[:2]
            for _i, _scn in enumerate(_scns):
                _evs = ", ".join(
                    f"@{e.at_ms}ms {e.key}={e.value!r}" for e in _scn.events[:8]
                ) or "(none)"
                _suffix = f" (+{len(_scn.events) - 8} more)" if len(_scn.events) > 8 else ""
                log_buf.append(f"🎬 Scenario {_i}: {_evs}{_suffix}")
        except Exception as _e:
            log_buf.append(f"⚠️ scenario synth (debug) failed: {_e}")

        _diagnoser = _make_llm_diagnoser(infer) if _LLM_DIAGNOSE_ENABLED else None
        if _diagnoser is not None:
            log_buf.append("🧠 LLM-aided diagnose: ON")
        v_result = _verifier_run(
            ir, _lower_fn,
            connected_devices=connected_devices,
            catalog=catalog_obj,
            max_attempts=_VERIFY_MAX_ATTEMPTS,
            diagnose_fn=_diagnoser,
        )
        for rec in v_result.attempts:
            tag = rec.retry_message.summary if rec.retry_message else "clean"
            log_buf.append(
                f"🔁 Attempt {rec.attempt}: L1={len(rec.l1)} L2={len(rec.l2)} — {tag}"
            )
            # L1 detail — one bullet per violation (kind, where, message)
            for v in rec.l1:
                log_buf.append(f"     L1 {v.kind} @ {v.where}: {v.message}")
            # L2 detail — kind, ir_path, target, expected/observed
            for v in rec.l2:
                bits = [f"L2 {v.kind} @ {v.ir_path} target={v.target}"]
                if v.expected is not None:
                    bits.append(f"exp={v.expected}")
                if v.observed is not None:
                    bits.append(f"obs={v.observed}")
                if v.occurrences > 1:
                    bits.append(f"×{v.occurrences}")
                log_buf.append("     " + " ".join(bits))
            # Retry hint (the prompt block actually injected on the next turn).
            # Dump the FULL block (deterministic floor + any LLM-aided note) so
            # the exact message handed to the lowering LLM is auditable.
            if rec.retry_message is not None and rec.attempt < len(v_result.attempts):
                log_buf.append(
                    f"     ↪ retry hint: {rec.retry_message.bullet_count} bullets — "
                    f"{rec.retry_message.summary}"
                )
                log_buf.append("     ┌─ FULL retry hint passed to next attempt ─")
                for _ln in rec.retry_message.prompt_block.splitlines():
                    log_buf.append(f"     │ {_ln}")
                log_buf.append("     └────────────────────────────────────────")

        # Trace-equivalence debug: re-run sims on the final accepted/rejected
        # JoI under the synthesized scenario and dump the trace records so a
        # human can eyeball IR vs JoI emit divergence. Capped to keep log
        # readable; cycle-heavy rows will repeat many times.
        try:
            from paper.simulators.ir_simulator import run_ir_simulation
            from paper.simulators.joi_simulator import run_joi_simulation
            if _scns and v_result.final_joi:
                _scn0 = _scns[0]
                _t_ir = run_ir_simulation(ir, _scn0, catalog_obj).records[:6]
                _t_joi = run_joi_simulation(v_result.final_joi, _scn0, catalog_obj).records[:6]
                log_buf.append(
                    f"📜 IR trace ({len(_t_ir)} shown): " + "; ".join(
                        f"@{r.timestamp_ms} {r.service}.{r.method}{r.args}" for r in _t_ir
                    ) if _t_ir else "📜 IR trace: (empty)"
                )
                log_buf.append(
                    f"📜 JoI trace ({len(_t_joi)} shown): " + "; ".join(
                        f"@{r.timestamp_ms} {r.service}.{r.method}{r.args}" for r in _t_joi
                    ) if _t_joi else "📜 JoI trace: (empty)"
                )
        except Exception as _e:
            log_buf.append(f"⚠️ trace dump (debug) failed: {_e}")

        log_buf.append(
            f"🏁 Verifier: {'accepted' if v_result.accepted else 'fail (kept last attempt)'}"
        )
        joi_json = v_result.final_joi or {}

        # Structured verifier decision trace for post-hoc confusion-matrix
        # aggregation (paper §7.5 / §8.5). We dump each attempt's parsed
        # joi_block so the eval grader can score attempt-1 vs final against
        # ir_gt without re-invoking the LLM — this is what separates the
        # detector matrix (did the internal verifier flag a wrong attempt-1?)
        # from the outcome matrix (did retry recover / regress?).
        verifier_trace = {
            "enabled": True,
            "accepted": v_result.accepted,
            "n_attempts": len(v_result.attempts),
            "attempts": [
                {
                    "attempt": rec.attempt,
                    "l1_count": len(rec.l1),
                    "l1_kinds": [v.kind for v in rec.l1],
                    "l2_count": len(rec.l2),
                    "l2_kinds": [v.kind for v in rec.l2],
                    "joi_block": rec.joi_block,
                }
                for rec in v_result.attempts
            ],
        }
        code_plan = ""
    else:
        raw = infer(prompt_key, joi_input, system=system_prompt)
        joi_json = _finalize(raw)
        code_plan = _extract_reasoning(raw)  # lowering's control-flow notes for re_translate
        verifier_trace = {"enabled": False}

    joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)

    def _unescape_script(code_json: str) -> str:
        return re.sub(
            r'("script"\s*:\s*")(.*?)(")',
            lambda m: m.group(1) + m.group(2).replace('\\n', '\n') + m.group(3),
            code_json, count=1, flags=re.DOTALL,
        )
    code_pretty = _unescape_script(joi_code_raw)

    # ── Final naming (main-branch flow): re-translate the generated code back to
    # natural language, then derive the scenario `name` in the USER's language.
    #   Code → English NL (re_translate) → [Korean input] Korean NL
    #   (re_translate_kor) → short label (scenario_name).
    # The label is the joi `name`; spaces are turned into `_` (hub disallows them)
    # while Korean characters are preserved. Skip all of this with JOI_SKIP_NAME=1.
    # Deterministic duration hints: the LLM is bad at multiplying tick thresholds
    # by `period`. A sustained-state counter (`hold_ticks >= N` / `n >= N`) with
    # period=P ms represents N×P/1000 real seconds. Compute every such threshold in
    # Python and feed the result as a hint so re_translate never does the arithmetic.
    def _duration_hints(code_obj) -> str:
        try:
            period = int(code_obj.get("period") or 0)
            script = code_obj.get("script") or ""
        except Exception:
            return ""
        if period <= 0:
            return ""
        def _fmt(sec: float) -> str:
            if sec < 1:
                return f"{sec:g} seconds"
            sec = int(round(sec))
            if sec % 3600 == 0:
                h = sec // 3600
                return f"{h} hour" + ("s" if h != 1 else "")
            if sec % 60 == 0:
                m = sec // 60
                return f"{m} minute" + ("s" if m != 1 else "")
            return f"{sec} second" + ("s" if sec != 1 else "")
        # Only a SUSTAIN counter (variable name contains "ticks") is a DURATION:
        # threshold × period = real time. A plain `n >= K` is a COUNT (repeat K
        # times), NOT a duration — must NOT be converted, or "after 10 times"
        # becomes a bogus "for 50 minutes".
        seen = []
        for m in re.finditer(r'\b(\w*ticks)\b\s*>=\s*(\d+)', script):
            n = int(m.group(2))
            if n <= 1:
                continue
            real = _fmt(n * period / 1000.0)
            line = f"- threshold {n} at period {period}ms = {real}"
            if line not in seen:
                seen.append(line)
        if not seen:
            return ""
        return "\n\n[Duration Hints] (already computed — use verbatim, do NOT recompute)\n" + "\n".join(seen)

    # User-facing naming (re_translate → name) should read a device by its
    # nickname, not the raw tc0_… id. Swap id→nickname in the re_translate INPUT
    # only (spaces → _ so the selector isn't misparsed as multiple tags); the
    # final code keeps real ids. Category/feature tags (#Light) aren't ids → left.
    _id2nick = {rid: info["nickname"]
                for rid, info in (connected_devices or {}).items()
                if isinstance(info, dict) and info.get("nickname")}
    def _ids_to_nick(text: str) -> str:
        return re.sub(r'#([\w\-]+)',
                      lambda m: ('#' + _id2nick[m.group(1)].replace(' ', '_'))
                      if m.group(1) in _id2nick else m.group(0), text)

    translated_sentence = ""
    translated_sentence_kor = ""
    if os.environ.get("JOI_SKIP_NAME") != "1":
        is_korean = bool(re.search(r"[가-힣]", original_sentence))
        try:
            _eng_plan = f"\n\n[Code Plan]\n{code_plan}" if code_plan else ""
            _dur_hints = _duration_hints(joi_json)
            _re_in = (
                f"[Code]\n{_ids_to_nick(joi_code_raw)}{_eng_plan}{_dur_hints}\n\n"
                f"[Service Descriptions]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
            )
            translated_sentence = infer("re_translate", _re_in).strip()
            log_buf.append(f"📝 re_translate (EN): {translated_sentence}")
        except Exception as _e:
            log_buf.append(f"⚠️ re_translate failed ({_e})")
        if is_korean and translated_sentence:
            try:
                # Extra token headroom: if the backend still emits a <think>
                # block (stripped post-hoc), 512 can truncate before the answer.
                translated_sentence_kor = infer(
                    "re_translate_kor", translated_sentence, max_tokens=1024).strip()
                log_buf.append(f"📝 re_translate (KO): {translated_sentence_kor}")
            except Exception as _e:
                log_buf.append(f"⚠️ re_translate_kor failed ({_e})")
        scenario_name = ""
        try:
            _name_in = translated_sentence_kor if is_korean else (translated_sentence or original_sentence)
            if _name_in:
                scenario_name = infer("scenario_name", _name_in).strip()
        except Exception as _e:
            log_buf.append(f"⚠️ scenario_name failed ({_e})")
        if not scenario_name:  # fallback: snake_case the English re-translation
            scenario_name = re.sub(r'[^\w\s]', '', (translated_sentence or "").strip())
        # spaces → `_`; keep unicode word chars (Korean survives) + `:` for HH:MM
        # clock times, drop other punctuation.
        scenario_name = re.sub(r'\s+', '_', scenario_name.strip())
        scenario_name = re.sub(r'[^\w:]', '', scenario_name).strip('_') or "Scenario"
        log_buf.append(f"🏷️ scenario name: {scenario_name}")
        try:  # inject name into the final code dict and re-serialize
            _cj = json.loads(joi_code_raw)
            _cj = {"name": scenario_name, **{k: v for k, v in _cj.items() if k != "name"}}
            joi_code_raw = json.dumps(_cj, indent=2, ensure_ascii=False)
            code_pretty = _unescape_script(joi_code_raw)
        except (json.JSONDecodeError, TypeError):
            pass

    elapsed = time.perf_counter() - start

    return {
        "code": code_pretty,
        "ir": ir,
        "ir_readable": ir_readable,
        "ir_readable_scoped": ir_readable_scoped,
        "precision": precision_output.get("selectors", {}) if isinstance(precision_output, dict) else {},
        "precision_reasoning": precision_output.get("reasoning", "") if isinstance(precision_output, dict) else "",
        "verifier_trace": verifier_trace,
        "log": {
            "response_time": f"{elapsed:.4f} seconds",
            "translated_sentence": translated_sentence_kor or translated_sentence,
            "logs": "\n".join(log_buf),
        },
    }


# Alias matching the original name so callers can swap imports easily.
generate_joi_code = generate_joi_code_ir
