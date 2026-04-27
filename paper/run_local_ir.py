"""IR-based JoI generation pipeline (experimental).

Diverges from run_local.py by replacing the filter/extractor/router stages with
Timeline IR extraction. The pipeline is:

    [Stage 0] command_merge (if modification)
    [Stage 1] translation (KOR -> ENG)
    [Stage 2 // parallel]
        - mapping branch: category -> intent -> precision
        - IR branch: NL -> Timeline IR (timeline_ir.extract_ir)
    [Stage 3] joi_from_ir lowering: (IR + precision selectors + service details) -> JoI

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

_LOWERING_PROMPT_PATH = os.path.join(_BASE_DIR, "joi_from_ir.md")


def _load_lowering_prompt() -> str:
    with open(_LOWERING_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


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

    # ── Mapping branch (kept from run_local.py: category -> intent -> precision) ──
    def run_mapping():
        if not isinstance(connected_devices, dict) or not connected_devices:
            raise JoiGenerationError(
                "No connected devices provided.",
                "\n".join(log_buf),
                error_code="no_devices",
            )
        valid_categories = set()
        for v in connected_devices.values():
            cats = v.get("category", [])
            if isinstance(cats, list):
                valid_categories.update(cats)
            elif isinstance(cats, str):
                valid_categories.add(cats)
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

        # 2-1 category
        exclude_categories = {"Switch", "RotaryControl", "ColorControl", "LevelControl"}
        category_input = (
            f"[Available Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}"
            f"\n\n[Command]\n{sentence}"
        )
        cat_output = infer("mapping_category", category_input)
        clean_cat = re.sub(r'```(?:json)?\s*', '', cat_output).strip()
        try:
            extracted_categories = json.loads(clean_cat)
            if isinstance(extracted_categories, list):
                extracted_categories = {k: "Identify relevant services" for k in extracted_categories}
            elif not isinstance(extracted_categories, dict):
                extracted_categories = {}
        except Exception:
            extracted_categories = {}
        extracted_categories = {k: v for k, v in extracted_categories.items() if k in valid_categories}

        # 2-2 intent per device
        missing_descriptors = [d for d in extracted_categories if not PROMPTS.get(f"device_rules_{d.lower()}", "")]
        if missing_descriptors:
            raise JoiGenerationError(
                f"Mapped device(s) {missing_descriptors} are not registered in the service list.",
                "\n".join(log_buf),
                error_code="missing_descriptor",
            )

        raw_selected_services = []
        for dev, assigned_task in extracted_categories.items():
            device_rules = PROMPTS.get(f"device_rules_{dev.lower()}", "")
            sub_cats = set()
            for info in cd_simple.values():
                cats = info.get("category", [])
                if dev in cats:
                    for c in cats:
                        if c in exclude_categories:
                            sub_cats.add(c)
            for sub_cat in sub_cats:
                sub_rule = PROMPTS.get(f"device_rules_{sub_cat.lower()}", "")
                if sub_rule:
                    sub_rule = re.sub(rf'\b{sub_cat}\b', dev, sub_rule, flags=re.IGNORECASE)
                    device_rules += f"\n\n--- Sub-Component: {sub_cat} ---\n{sub_rule}"

            sys_prompt = f"{PROMPTS.get('mapping_service_common', '')}\n\n{device_rules}"
            dev_input = f"[Command]\n{sentence}\n\n[Assigned Task for {dev}]\n{assigned_task}"
            dev_output = infer(f"intent_{dev.lower()}", dev_input, system=sys_prompt)
            clean_dev = re.sub(r'```(?:json)?\s*', '', dev_output).strip()
            try:
                srv_list = json.loads(clean_dev)
                if isinstance(srv_list, list):
                    raw_selected_services.extend(srv_list)
            except Exception:
                pass

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

        # 2-3 precision
        precision_input = (
            f"[Command]\n{sentence}\n[Intent]\n{json.dumps(intent_categories, indent=2, ensure_ascii=False)}"
            f"\n[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}"
        )
        precision_output = infer("mapping_precision", precision_input).strip()

        local_services_block = (
            f"[Service Tagging]\n{precision_output}\n\n"
            f"[Service Details]\n{json.dumps(local_service_details, indent=2, ensure_ascii=False)}"
        )
        return local_services_block, intent_categories, local_service_details, precision_output

    # ── IR branch ──
    def run_ir_extract():
        # Build an abstract device catalog keyed by category (e.g. "Light", "Door")
        # so the IR extractor works with clean names instead of UUIDs.
        abstract_devices: dict = {}
        if isinstance(connected_devices, dict):
            for info in connected_devices.values():
                for cat in (info.get("category") or []):
                    if cat not in abstract_devices:
                        abstract_devices[cat] = SERVICE_DATA.get(cat, {})

        try:
            ir = extract_ir(
                sentence,
                devices=abstract_devices,
                base_url=base_url,
                debug=False,
                auto_translate=False,
            )
        except IRValidationError as e:
            raise JoiGenerationError(
                f"IR extraction failed: {e}",
                "\n".join(log_buf),
                error_code="ir_invalid",
            )
        log_buf.append(
            "➡️ timeline_ir_extract\n"
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

    # 5. Parallel: mapping || ir-extract
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_mapping = executor.submit(run_mapping)
        f_ir = executor.submit(run_ir_extract)
        services_block, _intent_cats, service_details, precision_output = f_mapping.result()
        ir = f_ir.result()

    ir_readable = ir_to_readable(ir)
    ir_json_str = json.dumps(ir, ensure_ascii=False, indent=2)

    # 6. JoI generation from IR (single prompt key)
    prompt_key = "joi_from_ir"
    try:
        system_prompt = _load_lowering_prompt()
    except FileNotFoundError:
        raise JoiGenerationError(
            f"Lowering prompt 'joi_from_ir.md' is missing from paper/.",
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

    return {
        "code": joi_code_raw,
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
