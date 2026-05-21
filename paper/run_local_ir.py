"""IR-based JoI generation pipeline (experimental).

Replaces the legacy filter/extractor/router stages with
Timeline IR extraction. The pipeline is:

    [Stage 1] translation (KOR -> ENG)
    [Stage 2] service_plan: command -> ordered service list
    [Stage 3 // parallel]
        - branch A (resolve + ir): enum_cond_check -> enum_resolve -> arg_resolve
                                   -> ir_extract (sequential within branch)
        - branch B (precision): command + selected services -> selector dict
        IR is selector-free, so branch A no longer depends on branch B.
    [Stage 4] joi_from_ir lowering: IR + precision -> JoI (bucket-routed)

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
from loader import SERVICE_DATA, PROMPTS, SUB_SKILL_TAGS, get_device_rules_section
from parser.validator import validate_joi

from pipeline_helpers import (
    JoiGenerationError,
    run_llm_inference,
    extract_service_details,
    inject_value_service,
    _SERVICE_CATEGORY_MAP,
    _apply_service_prefix,
    _normalize_script_newlines,
    _post_process_joi_any_quantifiers,
    _strip_selector_extra_parens,
    _parse_dict_input,
)
from timeline_ir import (
    extract_ir, ir_to_readable, validate_ir, validate_ir_against_devices,
    validate_ir_against_catalog, build_extract_retry_hint,
    IRValidationError, parse_duration_to_ms,
)

# Verifier integration (Phase 2). Activated when env JOI_VERIFY=1 (default off
# during transition so baselines stay reproducible). When on, the lowering
# stage is wrapped by `retry_harness.run` with max_attempts=2; retry hints
# are delivered as a follow-up user turn via `infer_followup`, not as a
# template slot — first-attempt prompt distribution is unchanged.
from paper.verifier.retry_harness import run as _verifier_run
from paper.simulators.catalog import load_catalog as _load_catalog

_VERIFY_ENABLED = os.environ.get("JOI_VERIFY", "0") == "1"
_VERIFY_MAX_ATTEMPTS = int(os.environ.get("JOI_VERIFY_MAX_ATTEMPTS", "2"))

# Bucket-specific lowering prompt is assembled at runtime as
# joi_common.md + joi_<bucket>.md, both loaded from files/ via PROMPTS.
#
# Two buckets only: the IR is either acyclic (sequence) or contains a top-level
# cycle. Within `cycle`, the joi_cycle.md prompt's own switchboard (D-3/D-4/D-5/
# D-6/D-9/B-2) picks the idiom from explicit IR signals — no Python heuristic.
_BUCKET_KEYS = ("noncycle", "cycle")


def classify_ir(ir):
    """Return 'cycle' if any top-level cycle op exists, else 'noncycle'.

    Idiom discrimination (D-3/D-4/D-5/D-6/D-9/B-2) is delegated to the cycle
    prompt's switchboard, which reads explicit IR signals: cycle.until,
    body wait(edge:"rising"), pre-cycle wait(edge:"none"), if{break}, and
    body delay count. This keeps Python free of brittle heuristics.
    """
    if not isinstance(ir, dict):
        return "noncycle"
    timeline = ir.get("timeline") or []
    if not isinstance(timeline, list):
        return "noncycle"
    for s in timeline:
        if isinstance(s, dict) and s.get("op") == "cycle":
            return "cycle"
    return "noncycle"


def _load_lowering_prompt(bucket: str) -> str:
    if bucket not in _BUCKET_KEYS:
        raise ValueError(f"unknown lowering bucket: {bucket!r}")
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


def _build_device_selection_rules(categories) -> str:
    """Concatenate the default ('service_plan') section of each connected
    device's device_rules_*.md. Stage-scoped sections (e.g. `# @ArgResolve`)
    are stripped — those are pulled by their respective stages.
    """
    chunks = []
    for cat in categories:
        rule = get_device_rules_section(cat, "service_plan")
        if rule:
            chunks.append(f"### {cat}\n{rule}")
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


def _build_precision_services_block(svcs) -> str:
    """Annotate each service with kind (value|function) so precision LLM
    does not have to infer cond-context applicability from the name alone.
    """
    lines = []
    for s in svcs:
        if '.' not in s:
            lines.append(s)
            continue
        dev, svc_name = s.split('.', 1)
        svc_name_clean = svc_name.replace("()", "")
        dev_data = SERVICE_DATA.get(dev, {})
        is_value = any(e["id"] == svc_name_clean for e in dev_data.get("values", []))
        kind = "value" if is_value else "function"
        lines.append(f"- {dev}.{svc_name_clean} ({kind})")
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


def _parse_device_match_qids(raw: str):
    """Parse {Service: {"q": "one|all|any", "groups": [[ids], ...]}} from
    Step-1 raw output. Accepts both new (`groups`) and legacy (`ids`) forms.
    Returns (normalized_dict, reasoning_text).
    """
    reasoning_text = _extract_reasoning(raw)
    cleaned = _strip_llm_wrappers(raw)
    out = {}

    def _norm_ids(seq):
        if isinstance(seq, str):
            seq = [seq]
        return [str(x) for x in (seq or []) if isinstance(x, (str, int))]

    def _ingest(obj):
        if not isinstance(obj, dict):
            return
        for k, v in obj.items():
            if isinstance(v, dict):
                q = str(v.get("q", "one")).strip().lower()
                if q not in ("one", "all", "any"):
                    q = "one"
                if "groups" in v and isinstance(v["groups"], list):
                    groups = []
                    for g in v["groups"]:
                        ids = _norm_ids(g)
                        if ids:
                            groups.append(ids)
                    if not groups:
                        groups = [[]]
                else:
                    groups = [_norm_ids(v.get("ids", []))]
                out[k] = {"q": q, "groups": groups}
            elif isinstance(v, list):
                out[k] = {"q": "one", "groups": [_norm_ids(v)]}

    try:
        _ingest(json.loads(cleaned))
    except Exception:
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            try:
                _ingest(json.loads(m.group(0)))
            except Exception:
                pass
    return out, reasoning_text


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


def _parse_list_of_strings_from_llm(raw: str, allowed_prefixes=None) -> list:
    """Parse a JSON list-of-strings from LLM output. Optional filter:
    keep only entries that contain '.' AND whose prefix is in `allowed_prefixes`.
    """
    cleaned = _strip_llm_wrappers(raw)
    items = []
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            items = [s for s in parsed if isinstance(s, str)]
    except Exception:
        m = re.search(r'\[(.*?)\]', cleaned, re.DOTALL)
        if m:
            try:
                parsed = json.loads("[" + m.group(1) + "]")
                if isinstance(parsed, list):
                    items = [s for s in parsed if isinstance(s, str)]
            except Exception:
                pass
    if allowed_prefixes is not None:
        items = [s for s in items if '.' in s and s.split('.')[0] in allowed_prefixes]
    # Dedup while preserving order
    seen = set()
    out = []
    for s in items:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


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
    here. D-3 (cycle body has wait edge="rising") is hardcoded to 100
    regardless of cycle.period. Returns None if IR has no top-level cycle.
    """
    tl = (ir_obj or {}).get("timeline", [])
    for s in tl:
        if isinstance(s, dict) and s.get("op") == "cycle":
            body = s.get("body") or []
            if any(
                isinstance(x, dict) and x.get("op") == "wait" and x.get("edge") == "rising"
                for x in body
            ):
                return 100
            p = s.get("period")
            if isinstance(p, str):
                try:
                    return parse_duration_to_ms(p)
                except ValueError:
                    return None
            return None
    return None


def generate_joi_code_ir(
    sentence,
    connected_devices,
    other_params,
    base_url=None,
):
    """IR-mediated JoI generation. Drop-in compatible return shape with run_local.generate_joi_code."""
    connected_devices = _parse_dict_input(connected_devices, None)
    other_params = _parse_dict_input(other_params, {})

    start = time.perf_counter()
    client = get_client(base_url)
    model = get_model_id(client)

    log_buf = []

    def infer(key, user_input, *, system=None, enable_thinking=False, max_tokens=512):
        sys_content = system or PROMPTS.get(key, "")
        content, log_line = run_llm_inference(model, client, key, [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_input}
        ], enable_thinking=enable_thinking, max_tokens=max_tokens)
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

    # ❇️ Stage 1: Translation (KOR -> ENG)
    if re.search("[가-힣]", sentence):
        sentence = infer("translation", sentence)

    # ── Stage 2 pre-work: build cd_simple + device categories early so pre_analysis
    # can see them (pre_analysis is now kitchen-sink — full verbatim + device + service
    # analysis in one caveman pass).
    if not isinstance(connected_devices, dict) or not connected_devices:
        raise JoiGenerationError(
            "No connected devices provided.",
            "\n".join(log_buf),
            error_code="no_devices",
        )
    cd_simple = {}
    valid_categories = set()
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
        valid_categories.update(cats)

    # Include all categories (including sub-skills like Switch / LevelControl /
    # ColorControl / RotaryControl). Service planner sees the full skill set so
    # it can prefer Switch.On / Switch.Off for plain power-toggle commands even
    # when the parent device (e.g. Humidifier) also exposes a Set...Mode action.
    primary_categories = sorted(valid_categories)

    device_rules_block = _build_device_selection_rules(primary_categories)

    # ❇️ Stage 1.5: Pre-analysis — verbatim-grounded caveman dump.
    # Sees [Command] + [Connected Devices] + [Device Summary] as REFERENCE for
    # awareness (so it can recognize service/tag/quantifier/trigger dimensions),
    # but must not pre-commit to specific d-ids / Cat.Method / enum values.
    # Downstream stages may ignore or override.
    pre_input = (
        f"[Command]\n{sentence}\n\n"
        f"[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}\n\n"
        f"[Device Summary]\n{device_rules_block}"
    )
    command_hints_raw = infer("pre_analysis", pre_input, max_tokens=512)
    # Strip only the <Reasoning> wrapper tags; keep the caveman content for downstream.
    command_hints = re.sub(r'</?Reasoning>\s*', '', command_hints_raw).strip()

    plan_sys_prompt = PROMPTS.get("service_plan", "")
    plan_input = (
        f"[Command]\n{sentence}\n\n"
        f"[Command Hints]\n{command_hints}\n\n"
        f"[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}\n\n"
        f"[Device Rules]\n{device_rules_block}"
    )
    plan_output = infer("service_plan", plan_input, system=plan_sys_prompt)

    # Parse + dedup + filter to known categories in one step.
    # NOTE: inject_value_service(selected_services) removed 2026-05-11.
    # service_plan now decides companion-read inclusion semantically (see Rule 10
    # in files/service_plan.md). Absolute setters get setter-only; relative
    # adjustments get read + setter. No Python-level auto-injection.
    selected_services = _parse_list_of_strings_from_llm(
        plan_output, allowed_prefixes=valid_categories
    )
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
    arg_services = [s for s in selected_services if _is_function_service(s)]

    # ── Resolve branch: enum_cond_check → enum_resolve → arg_resolve (sequential within branch) ──
    def run_resolve_branch():
        resolved_enum_conds_local = {}
        if enum_value_targets:
            yesno_user = (
                "[ENUM-Value Targets]\n"
                f"{json.dumps(enum_value_targets, ensure_ascii=False)}\n\n"
                "For any of these value services, does the command imply a "
                "condition expression that compares the read value to a SPECIFIC "
                "enum member (e.g., `Service == \"someMember\"`)? Answer with one "
                "lowercase word: yes or no."
            )
            yesno_raw = infer_followup(
                "enum_cond_check",
                user_input=yesno_user,
                system=PROMPTS.get("enum_cond_check", ""),
                prior_user=plan_input,
                prior_assistant=plan_output,
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
                enum_raw = infer_followup(
                    "enum_resolve",
                    enum_input,
                    system=PROMPTS.get("enum_resolve", ""),
                    prior_user=plan_input,
                    prior_assistant=plan_output,
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
            arg_hints = _build_device_specific_hints(arg_services, "arg_resolve")
            arg_resolve_input = (
                f"[Command]\n{sentence}\n\n"
                f"[Selected Services]\n{json.dumps(arg_services, ensure_ascii=False)}\n\n"
                f"[Service Details]\n{_build_arg_resolve_input(arg_services, local_service_details)}"
                + (f"\n\n[Device-specific Arg Hints]\n{arg_hints}" if arg_hints else "")
            )
            arg_resolve_raw = infer_followup(
                "arg_resolve",
                arg_resolve_input,
                system=PROMPTS.get("arg_resolve", ""),
                prior_user=plan_input,
                prior_assistant=plan_output,
            )
            resolved_args_local = _parse_dict_from_llm(arg_resolve_raw)

        return resolved_args_local, resolved_enum_conds_local

    # ── Precision branch: command + selected services → JSON dict of selectors ──
    def run_precision():
        # Two-step LLM call with id-aliasing + selector validator + retry:
        #   1. Build alias map (d1, d2, ...) for cd_simple keys; rewrite [Connected Devices].
        #   2. Step 1 (mapping_device_match): {Service: {q, ids}}.
        #   3. Step 2 (mapping_selector, multi-turn): {Service: ["(#Tag ...)"]}.
        #   4. Python validator: apply each selector to cd_aliased, check it matches exactly target ids.
        #   5. If mismatch, send mismatch info as follow-up user msg; retry up to 2 times.
        #   6. If still mismatch, fall back to deterministic minimum-tag-set selector.
        if not selected_services:
            return {"selectors": {}, "reasoning": ""}

        # ---- alias the device ids so the LLM sees short, stable tokens ----
        real_ids = list(cd_simple.keys())
        alias_of = {real: f"d{i+1}" for i, real in enumerate(real_ids)}
        real_of = {a: r for r, a in alias_of.items()}
        cd_aliased = {alias_of[r]: cd_simple[r] for r in real_ids}

        # Pre-compute alias → tags array (category + tags merged)
        alias_tags = {}
        for a, dev in cd_aliased.items():
            seen = set()
            arr = []
            for t in list(dev.get("category", [])) + list(dev.get("tags", [])):
                if t not in seen:
                    seen.add(t)
                    arr.append(t)
            alias_tags[a] = arr

        step1_user = (
            f"[Command]\n{sentence}\n\n"
            f"[Command Hints]\n{command_hints}\n\n"
            f"[Selected Services]\n{json.dumps(selected_services, ensure_ascii=False)}\n\n"
            f"[Connected Devices]\n{json.dumps(cd_aliased, indent=2, ensure_ascii=False)}"
        )
        step1_raw = infer("mapping_device_match", step1_user).strip()
        match_qids, step1_reasoning = _parse_device_match_qids(step1_raw)
        # Flatten groups for downstream consumers that still expect a flat id list per service
        matches = {
            svc: [a for g in entry.get("groups", []) for a in g]
            for svc, entry in match_qids.items()
        }

        # Build [Targets] block for logging/reasoning trail
        target_lines = []
        for svc in selected_services:
            entry = match_qids.get(svc, {"q": "one", "groups": [[]]})
            q = entry.get("q", "one")
            groups = entry.get("groups", [[]])
            groups_str = " | ".join("[" + ", ".join(g) + "]" for g in groups)
            target_lines.append(f"{svc}: q={q}, groups={groups_str}")
        targets_block = "\n".join(target_lines)

        # ---- Deterministic Python selector generation ----
        # For each service, for each group: take group's tag intersection; wrap with quantifier.
        # Each group → one selector. Multi-group → multiple selectors in list.
        # The mapping_selector LLM step is disabled; this Python path is the sole producer.
        # Sub-skill capability tags ({{SUB_SKILLS}} per loader.SUB_SKILL_TAGS) are
        # kept ONLY when the service's prefix matches the sub-skill (e.g. Switch.Off keeps
        # #Switch; Television.SetChannel drops #Switch even if device has Switch in its tags).

        def _selector_for_group(group_ids, q, service_prefix):
            wrap = "" if q == "one" else q
            tag_lists = [alias_tags.get(a, []) for a in group_ids if a in alias_tags]
            if not tag_lists:
                return None
            inter_set = set(tag_lists[0])
            for tl in tag_lists[1:]:
                inter_set &= set(tl)
            # Filter out sub-skill capability tags that don't match the service prefix
            filtered = [
                t for t in tag_lists[0]
                if t in inter_set and (t not in SUB_SKILL_TAGS or t == service_prefix)
            ]
            if not filtered:
                return None
            return f"{wrap}(#{' #'.join(filtered)})"

        selectors = {}
        for svc in selected_services:
            entry = match_qids.get(svc, {"q": "one", "groups": [[]]})
            q = entry.get("q", "one")
            groups = entry.get("groups", [[]])
            service_prefix = svc.split(".", 1)[0]
            sel_list = []
            for g in groups:
                if not g:
                    continue
                s = _selector_for_group(g, q, service_prefix)
                if s:
                    sel_list.append(s)
            if not sel_list:
                wrap = "" if q == "one" else q
                sel_list = [f"{wrap}(#{service_prefix})"]
            selectors[svc] = sel_list

        # Restore real ids inside selectors when the alias represented an id-literal-in-tags case
        def _restore_alias_in_selector(s):
            for a, r in real_of.items():
                real_dev = cd_simple.get(r, {})
                real_tags = list(real_dev.get("category", [])) + list(real_dev.get("tags", []))
                if r in real_tags:
                    s = re.sub(rf'(?<=#){re.escape(a)}\b', r, s)
                else:
                    s = re.sub(rf'(?<=#){re.escape(a)}\b', '', s)
            return s
        for svc in list(selectors.keys()):
            selectors[svc] = [_restore_alias_in_selector(s) for s in selectors[svc]]

        combined_reasoning = (
            f"[Step1 device match]\n{step1_reasoning}\n\n"
            f"[Targets]\n{targets_block}\n\n"
            f"[Selectors generated deterministically by Python (intersection of target tags)]"
        )
        return {"selectors": selectors, "reasoning": combined_reasoning}

    # ── IR extract (sequential, after both branches finish) ──
    def run_ir_extract():
        intent_services_block = _build_intent_services_block(selected_services, local_service_details)

        # Build the [Resolved Args] augmentation block from arg_resolve output.
        # Format expected by the extractor prompt:
        #   Service.Method: {arg: value, ...}
        # The extractor copies these values verbatim into call.args (no re-decision).
        aug_parts = []
        if command_hints:
            aug_parts.append("[Command Hints]\n" + command_hints.strip())
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

    ir_readable = ir_to_readable(ir)
    ir_json_str = json.dumps(ir, ensure_ascii=False, indent=2)

    # === Stage 4 (joi_from_ir lowering) ===
    bucket = classify_ir(ir)
    log_buf.append(f"📦 IR bucket: {bucket}")
    prompt_key = f"joi_from_ir_{bucket}"
    try:
        system_prompt = _load_lowering_prompt(bucket)
    except FileNotFoundError as e:
        raise JoiGenerationError(
            f"Lowering prompt missing: {e}",
            "\n".join(log_buf),
            error_code="missing_lowering_prompt",
        )

    joi_input = (
        f"[Command]\n{sentence}\n\n"
        f"[Timeline IR]\n{ir_json_str}\n\n"
        f"[Precision Selectors]\n{precision_output}\n\n"
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
            joi_json.setdefault("name", "Scenario")
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
            joi_json["script"] = _post_process_joi_any_quantifiers(joi_json["script"])

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

        v_result = _verifier_run(
            ir, _lower_fn,
            connected_devices=connected_devices,
            catalog=catalog_obj,
            max_attempts=_VERIFY_MAX_ATTEMPTS,
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
            # Retry hint (the prompt block actually injected on the next turn)
            if rec.retry_message is not None and rec.attempt < len(v_result.attempts):
                log_buf.append(
                    f"     ↪ retry hint: {rec.retry_message.bullet_count} bullets — "
                    f"{rec.retry_message.summary}"
                )

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
    else:
        raw = infer(prompt_key, joi_input, system=system_prompt)
        joi_json = _finalize(raw)

    joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
    code_pretty = re.sub(
        r'("script"\s*:\s*")(.*?)(")',
        lambda m: m.group(1) + m.group(2).replace('\\n', '\n') + m.group(3),
        joi_code_raw,
        count=1,
        flags=re.DOTALL,
    )

    elapsed = time.perf_counter() - start

    return {
        "code": code_pretty,
        "ir": ir,
        "ir_readable": ir_readable,
        "precision": precision_output.get("selectors", {}) if isinstance(precision_output, dict) else {},
        "precision_reasoning": precision_output.get("reasoning", "") if isinstance(precision_output, dict) else "",
        "log": {
            "response_time": f"{elapsed:.4f} seconds",
            "logs": "\n".join(log_buf),
        },
    }


# Alias matching the original name so callers can swap imports easily.
generate_joi_code = generate_joi_code_ir
