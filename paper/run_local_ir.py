"""IR-based JoI generation pipeline (experimental).

Diverges from run_local.py by replacing the filter/extractor/router stages with
Timeline IR extraction. The pipeline is:

    [Stage 0] command_merge (if modification)
    [Stage 1] translation (KOR -> ENG)
    [Stage 2] service_plan: command + full catalogs -> ordered service list
    [Stage 3 // parallel]
        - precision: planned categories -> device selectors
        - IR branch: NL + planned services -> Timeline IR (timeline_ir.extract_ir)
    [Stage 4] joi_from_ir lowering: (IR + precision selectors + service details) -> JoI

Service & post-processing helpers are imported from run_local.py to keep a
single source of truth — DO NOT mutate run_local.py from here.
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
from loader import SERVICE_DATA, PROMPTS
from parser.validator import validate_joi

from run_local import (
    JoiGenerationError,
    run_llm_inference,
    extract_service_details,
    inject_value_service,
    _SERVICE_CATEGORY_MAP,
    _apply_service_prefix,
    _normalize_script_newlines,
    _post_process_joi_any_quantifiers,
    _parse_dict_input,
)
from timeline_ir import extract_ir, ir_to_readable, validate_ir, IRValidationError

# Bucket-specific lowering prompt is assembled at runtime as
# joi_common.md + joi_<bucket>.md, both loaded from files/ via PROMPTS.
_BUCKET_KEYS = (
    "noncycle",
    "simple_periodic",
    "edge_cycle",
    "state_cycle",
    "break_cycle",
)


def classify_ir(ir):
    """Classify the IR into one of the 5 lowering buckets.

    Buckets:
      - noncycle        : no top-level cycle. Covers D-1, D-2, D-7, D-8, B-1b.
      - simple_periodic : cycle{ call(s); ONE trailing delay } with no wait/if/break/until. (B-2)
      - edge_cycle      : cycle whose body contains wait(edge:"rising"). (D-3)
      - state_cycle     : D-4 phase (top-level wait(none) before cycle) or
                          D-5 alternation (cycle body has >=2 delays).
      - break_cycle     : cycle.until non-null, OR cycle body has if{break}. (D-6 / D-9)

    Selection order matters: break_cycle > edge_cycle > state_cycle > simple_periodic.
    """
    if not isinstance(ir, dict):
        return "noncycle"
    timeline = ir.get("timeline") or []
    if not isinstance(timeline, list):
        return "noncycle"

    cycle_idx = next(
        (i for i, s in enumerate(timeline)
         if isinstance(s, dict) and s.get("op") == "cycle"),
        None,
    )
    if cycle_idx is None:
        return "noncycle"

    cyc = timeline[cycle_idx]
    body = cyc.get("body") or []

    # break_cycle: cycle.until set OR explicit if{break} step inside body
    if cyc.get("until"):
        return "break_cycle"

    def _has_break_in_if(steps):
        for s in steps:
            if not isinstance(s, dict):
                continue
            if s.get("op") == "if":
                branches = (s.get("then") or []) + (s.get("else") or [])
                if any(isinstance(c, dict) and c.get("op") == "break" for c in branches):
                    return True
        return False

    if _has_break_in_if(body):
        return "break_cycle"

    # edge_cycle: rising-edge wait inside cycle body
    if any(isinstance(s, dict) and s.get("op") == "wait" and s.get("edge") == "rising"
           for s in body):
        return "edge_cycle"

    # state_cycle: D-4 (wait(none) at top level BEFORE the cycle)
    pre_cycle = timeline[:cycle_idx]
    if any(isinstance(s, dict) and s.get("op") == "wait" and s.get("edge") in (None, "none")
           for s in pre_cycle):
        return "state_cycle"

    # state_cycle: D-5 alternation (>=2 delays in cycle body)
    delay_count = sum(1 for s in body if isinstance(s, dict) and s.get("op") == "delay")
    if delay_count >= 2:
        return "state_cycle"

    # default: simple periodic (cycle with body + ONE trailing delay, no extras)
    return "simple_periodic"


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


def generate_joi_code_ir(
    sentence,
    connected_devices,
    other_params,
    modification=None,
    base_url=None,
):
    """IR-mediated JoI generation. Drop-in compatible return shape with run_local.generate_joi_code."""
    connected_devices = _parse_dict_input(connected_devices, None)
    other_params = _parse_dict_input(other_params, {})

    start = time.perf_counter()
    client = get_client(base_url)
    model = get_model_id(client)

    log_buf = []

    def infer(key, user_input, *, system=None):
        sys_content = system or PROMPTS.get(key, "")
        content, log_line = run_llm_inference(model, client, key, [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_input}
        ])
        log_buf.append(log_line)
        return content

    # ❇️ Stage 0: Command Merge
    merged_command = sentence
    if modification:
        merge_raw = infer("command_merge", f"Original: {sentence}\nModification: {modification}")
        merged_command = (
            merge_raw.split("</Reasoning>")[-1].strip()
            if "</Reasoning>" in merge_raw
            else merge_raw.strip()
        )
        sentence = merged_command

    # ❇️ Stage 1: Translation (KOR -> ENG)
    first_word = sentence.strip().split()[0] if sentence.strip() else ""
    if re.search("[가-힣]", first_word):
        sentence = infer("translation", sentence)

    # ── Stage 2: service_plan (unified category + intent) ──
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

    def _format_arg(a):
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

    def _format_return(svc_info, is_value):
        if is_value:
            v_type = svc_info.get("type", "")
            return v_type or "VOID"
        rt = svc_info.get("return_type")
        if isinstance(rt, dict):
            return rt.get("type", "VOID") or "VOID"
        if isinstance(rt, str) and rt:
            return rt
        return "VOID"

    def _build_full_service_catalog(categories):
        """Build the full service catalog block (all services per category) for service_plan."""
        blocks = []
        for cat in categories:
            data = SERVICE_DATA.get(cat, {})
            if not data:
                continue
            lines = [f"### {cat}"]
            for v in data.get("values", []):
                rt = _format_return(v, is_value=True)
                lines.append(f"{cat}.{v['id']} (value) → {rt}")
                desc = v.get("descriptor", "")
                if desc:
                    lines.append(f"  {desc}")
                if v.get("type") == "ENUM" and v.get("format"):
                    enum_members = data.get("enums_map", {}).get(v["format"], [])
                    if enum_members:
                        vals = [m.split(" - ")[0] for m in enum_members]
                        lines.append(f"  enum values: {{{', '.join(vals)}}}")
            for fn in data.get("functions", []):
                arg_strs = [_format_arg(a) for a in fn.get("arguments", [])]
                rt = _format_return(fn, is_value=False)
                sig = ", ".join(arg_strs)
                lines.append(f"{cat}.{fn['id']}({sig}) → {rt}")
                desc = fn.get("descriptor", "")
                if desc:
                    lines.append(f"  {desc}")
                for a in fn.get("arguments", []):
                    if a.get("type") == "ENUM" and a.get("format"):
                        enum_members = data.get("enums_map", {}).get(a["format"], [])
                        if enum_members:
                            vals = [m.split(" - ")[0] for m in enum_members]
                            lines.append(f"  {a['id']} enum values: {{{', '.join(vals)}}}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks) if blocks else "(no services)"

    def _build_device_selection_rules(categories):
        """Concatenate device_rules_*.md content for the planner to read selection guidance."""
        chunks = []
        for cat in categories:
            rule = PROMPTS.get(f"device_rules_{cat.lower()}", "")
            if rule:
                chunks.append(f"### {cat}\n{rule}")
        return "\n\n".join(chunks) if chunks else "(no device-specific rules)"

    service_catalog_block = _build_full_service_catalog(primary_categories)
    device_rules_block = _build_device_selection_rules(primary_categories)

    plan_sys_prompt = PROMPTS.get("service_plan", "")
    plan_input = (
        f"[Command]\n{sentence}\n\n"
        f"[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}\n\n"
        f"[Service Catalog]\n{service_catalog_block}\n\n"
        f"[Device Selection Rules]\n{device_rules_block}"
    )
    plan_output = infer("service_plan", plan_input, system=plan_sys_prompt)

    plan_clean = re.sub(r'<Reasoning>.*?</Reasoning>', '', plan_output, flags=re.DOTALL).strip()
    plan_clean = re.sub(r'```(?:json)?\s*', '', plan_clean).strip()
    plan_clean = plan_clean.rstrip("`").strip()
    raw_selected_services = []
    try:
        parsed = json.loads(plan_clean)
        if isinstance(parsed, list):
            raw_selected_services = [s for s in parsed if isinstance(s, str)]
    except Exception:
        m = re.search(r'\[(.*?)\]', plan_clean, re.DOTALL)
        if m:
            try:
                parsed = json.loads("[" + m.group(1) + "]")
                if isinstance(parsed, list):
                    raw_selected_services = [s for s in parsed if isinstance(s, str)]
            except Exception:
                pass

    raw_selected_services = [s for s in raw_selected_services if '.' in s and s.split('.')[0] in valid_categories]

    selected_services = []
    for s in raw_selected_services:
        if s not in selected_services:
            selected_services.append(s)
    inject_value_service(selected_services)
    local_service_details = extract_service_details(selected_services, SERVICE_DATA)

    intent_categories = list(set(s.split('.')[0] for s in selected_services if '.' in s))
    if not intent_categories:
        raise JoiGenerationError(
            f"No services found for the command: '{sentence}'.",
            "\n".join(log_buf),
            error_code="no_services",
        )

    # ── Stage 3: precision || ir-extract (parallel, both use intent results) ──
    def _build_intent_services_block(svcs, details):
        """Build a services block for IR extraction from intent results.

        Format per service:
            Dev.Service  (value|function)  [- descriptor]
              args:
                - ArgId: TYPE [(unit/enum)] - descriptor

        IR LLM uses this to:
          - distinguish read ops (value) from call ops (function)
          - know exact argument names, types, units → avoid inventing wrong args
            or adding redundant delays for time already encoded in arguments
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

            descriptor = (svc_info or {}).get("descriptor", "") if isinstance(svc_info, dict) else ""
            header = f"{dev}.{svc_name_clean}  ({svc_type})"
            if descriptor:
                header += f" - {descriptor}"
            lines.append(header)

            args = (svc_info or {}).get("arguments", []) if isinstance(svc_info, dict) else []
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
                if svc_type == "value":
                    v_type = svc_info.get("type", "")
                    if v_type == "ENUM":
                        enum_vals = [str(v).split(" - ")[0] for v in svc_info.get("enum_list", [])]
                        if enum_vals:
                            lines.append(f"  returns: ENUM {{{', '.join(enum_vals)}}}")
                    elif v_type:
                        lines.append(f"  returns: {v_type}")
                else:
                    rt = svc_info.get("return_type")
                    if isinstance(rt, dict):
                        rt_type = rt.get("type", "")
                        if rt_type and rt_type != "VOID":
                            lines.append(f"  returns: {rt_type}")
                    elif isinstance(rt, str) and rt and rt != "VOID":
                        lines.append(f"  returns: {rt}")

        return "\n".join(lines) if lines else "(no services)"

    def run_precision():
        precision_input = (
            f"[Command]\n{sentence}\n[Intent]\n{json.dumps(intent_categories, indent=2, ensure_ascii=False)}"
            f"\n[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}"
        )
        return infer("mapping_precision", precision_input).strip()

    def run_ir_extract():
        intent_services_block = _build_intent_services_block(selected_services, local_service_details)
        # Conditionally inject the color name → xy reference when MoveToColor (or
        # any service taking CIE xy coordinates) is in the planned services.
        # Keeps the extractor prompt lean for the common case.
        augmentations = None
        if any(s.endswith(".MoveToColor") for s in selected_services):
            augmentations = (
                "[Color name → xy (CIE 1931) reference]\n"
                "When a `MoveToColor`-style service requires xy coordinates, look up the color name here and emit numeric doubles. **Do NOT invent xy values.**\n"
                "| Color | x | y |\n"
                "|---|---|---|\n"
                "| red | 0.675 | 0.322 |\n"
                "| green | 0.408 | 0.517 |\n"
                "| blue | 0.167 | 0.040 |\n"
                "| yellow | 0.432 | 0.500 |\n"
                "| cyan | 0.225 | 0.329 |\n"
                "| magenta | 0.385 | 0.157 |\n"
                "| orange | 0.560 | 0.406 |\n"
                "| purple | 0.279 | 0.142 |\n"
                "| pink | 0.461 | 0.249 |\n"
                "| white | 0.313 | 0.329 |\n"
                "If the color isn't in this table, fall back to white (0.313, 0.329)."
            )
        try:
            ir, _prompt_tok, _comp_tok, _elapsed = extract_ir(
                sentence,
                devices=intent_services_block,
                base_url=base_url,
                debug=False,
                auto_translate=False,
                augmentations=augmentations,
            )
        except IRValidationError as e:
            raise JoiGenerationError(
                f"IR extraction failed: {e}",
                "\n".join(log_buf),
                error_code="ir_invalid",
            )
        _decode_tps = _comp_tok / _elapsed if _elapsed > 0 and _comp_tok else 0
        log_buf.append(
            f"➡️ timeline_ir_extract({_prompt_tok}) | Decode: {_decode_tps:.1f} t/s | Total: {_elapsed:.4f}s\n"
            "===================================================\n"
            f"{json.dumps(ir, ensure_ascii=False, indent=2)}"
        )
        if isinstance(ir, dict) and "error" in ir:
            raise JoiGenerationError(
                f"IR extractor rejected the command: {ir.get('error')}",
                "\n".join(log_buf),
                error_code="ir_rejected",
            )
        return ir

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_precision = executor.submit(run_precision)
        f_ir = executor.submit(run_ir_extract)
        precision_output = f_precision.result()
        ir = f_ir.result()

    service_details = local_service_details

    # Auto-inject `bind` on prior calls whose method-name suffix is referenced
    # via `$<MethodName>` in any later step's args/cond. Lets the IR LLM use the
    # natural `$MethodName` convention without writing `bind` explicitly.
    def _inject_implicit_binds(ir_obj):
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
                if step.get("op") == "call" and "bind" not in step:
                    target = step.get("target", "")
                    method = target.rsplit(".", 1)[-1] if "." in target else target
                    if not method:
                        continue
                    later_refs = set()
                    for later in steps[i + 1:]:
                        later_refs |= _collect_refs(later)
                    if method in later_refs:
                        step["bind"] = method

        _walk(timeline)

    _inject_implicit_binds(ir)

    ir_readable = ir_to_readable(ir)
    ir_json_str = json.dumps(ir, ensure_ascii=False, indent=2)

    # 6. JoI generation from IR — pick bucket-specific lowering prompt
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
        f"[IR Readable]\n{ir_readable}\n\n"
        f"[Precision Selectors]\n{precision_output}\n\n"
        f"[Service Details]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
    )
    joi_code_raw = infer(prompt_key, joi_input, system=system_prompt)

    # Reasoning strip
    script = re.sub(r'<Reasoning>.*?</Reasoning>', '', joi_code_raw, flags=re.DOTALL).strip()

    # The lowering prompt is asked to return a full JSON {name, cron, period, script}.
    # Try parsing; if it fails (e.g. raw script returned), wrap it.
    joi_json = {}
    try:
        # Pre-fix literal newlines inside "script" string
        m = re.search(r'"script"\s*:\s*"(.*?)"\s*\}', script, re.DOTALL)
        if m:
            fixed_inner = m.group(1).replace('\n', '\\n')
            script = script[:m.start(1)] + fixed_inner + script[m.end(1):]
        joi_json = json.loads(script)
        if "script" in joi_json:
            joi_json["script"] = _apply_service_prefix(joi_json["script"])
            joi_json["script"] = _normalize_script_newlines(joi_json["script"])
        joi_json.setdefault("name", "Scenario")
        joi_json = {"name": joi_json.pop("name"), **joi_json}
        joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        # Fallback: treat as raw script body
        body = _apply_service_prefix(script)
        joi_json = {
            "name": "Scenario",
            "cron": "",
            "period": 0,
            "script": _normalize_script_newlines(body),
        }
        joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)

    # ❇️ Validation
    try:
        _ = validate_joi(joi_json.get("script", ""), connected_devices, _SERVICE_CATEGORY_MAP)
    except Exception as e:
        log_buf.append(f"⚠️ validate_joi warning: {e}")

    elapsed = time.perf_counter() - start

    # any → all + |
    try:
        joi_json_final = json.loads(joi_code_raw)
        if "script" in joi_json_final:
            joi_json_final["script"] = _post_process_joi_any_quantifiers(joi_json_final["script"])
        joi_code_raw = json.dumps(joi_json_final, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        joi_code_raw = _post_process_joi_any_quantifiers(joi_code_raw)

    # Render escaped \n inside "script" as real newlines for readability.
    # Note: this makes `code` non-strict-JSON; consumers needing valid JSON
    # should parse joi_json_final directly instead.
    code_pretty = re.sub(
        r'("script"\s*:\s*")(.*?)(")',
        lambda m: m.group(1) + m.group(2).replace('\\n', '\n') + m.group(3),
        joi_code_raw,
        count=1,
        flags=re.DOTALL,
    )

    return {
        "code": code_pretty,
        "merged_command": merged_command,
        "ir": ir,
        "ir_readable": ir_readable,
        "precision": precision_output,
        "log": {
            "response_time": f"{elapsed:.4f} seconds",
            "logs": "\n".join(log_buf),
        },
    }


# Alias matching the original name so callers can swap imports easily.
generate_joi_code = generate_joi_code_ir
