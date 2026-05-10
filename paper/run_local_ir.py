"""IR-based JoI generation pipeline (experimental).

Diverges from run_local.py by replacing the filter/extractor/router stages with
Timeline IR extraction. The pipeline is:

    [Stage 0] command_merge (if modification)
    [Stage 1] translation (KOR -> ENG)
    [Stage 2] service_plan: command -> ordered service list
    [Stage 3 // parallel]
        - branch A (resolve + ir): enum_cond_check -> enum_resolve -> arg_resolve
                                   -> ir_extract (sequential within branch)
        - branch B (precision): command + selected services -> selector dict
        IR is selector-free, so branch A no longer depends on branch B.
    [Stage 4] joi_from_ir lowering (currently DISABLED): IR + precision -> JoI

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

    def _build_device_selection_rules(categories):
        """Concatenate device_rules_*.md content for the planner to read selection guidance."""
        chunks = []
        for cat in categories:
            rule = PROMPTS.get(f"device_rules_{cat.lower()}", "")
            if rule:
                chunks.append(f"### {cat}\n{rule}")
        return "\n\n".join(chunks) if chunks else "(no device-specific rules)"

    device_rules_block = _build_device_selection_rules(primary_categories)

    plan_sys_prompt = PROMPTS.get("service_plan", "")
    plan_input = (
        f"[Command]\n{sentence}\n\n"
        f"[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}\n\n"
        f"[Device Rules]\n{device_rules_block}"
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

    # ── Helper builders for resolve / precision / ir-extract stages ──
    def _is_enum_value_service(s):
        if '.' not in s:
            return False
        dev, svc_name = s.split('.', 1)
        svc_name_clean = svc_name.replace("()", "")
        for v in SERVICE_DATA.get(dev, {}).get("values", []):
            if v.get("id") == svc_name_clean:
                return v.get("type") == "ENUM"
        return False

    def _build_enum_resolve_input(targets):
        lines = [f"[Command]\n{sentence}\n", "[ENUM-Value Services]"]
        for s in targets:
            dev, svc_name = s.split('.', 1)
            svc_name_clean = svc_name.replace("()", "")
            svc_info = (local_service_details.get(dev) or {}).get(svc_name_clean) or {}
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

    def _is_function_service(s):
        if '.' not in s:
            return False
        dev, svc_name = s.split('.', 1)
        svc_name_clean = svc_name.replace("()", "")
        dev_data = SERVICE_DATA.get(dev, {})
        return not any(e["id"] == svc_name_clean for e in dev_data.get("values", []))

    def _build_arg_resolve_input(svcs, details):
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
                enum_input = _build_enum_resolve_input(enum_value_targets)
                enum_raw = infer("enum_resolve", enum_input)
                er_clean = re.sub(r'```(?:json)?\s*', '', enum_raw).strip().rstrip("`").strip()
                try:
                    parsed_er = json.loads(er_clean)
                    if isinstance(parsed_er, dict):
                        for k, v in parsed_er.items():
                            if v is None:
                                continue
                            if isinstance(v, dict) and "value" in v:
                                resolved_enum_conds_local[k] = {
                                    "op": v.get("op", "=="),
                                    "value": v["value"],
                                }
                except Exception:
                    m_er = re.search(r'\{.*\}', er_clean, re.DOTALL)
                    if m_er:
                        try:
                            parsed_er = json.loads(m_er.group(0))
                            if isinstance(parsed_er, dict):
                                for k, v in parsed_er.items():
                                    if v is None:
                                        continue
                                    if isinstance(v, dict) and "value" in v:
                                        resolved_enum_conds_local[k] = {
                                            "op": v.get("op", "=="),
                                            "value": v["value"],
                                        }
                        except Exception:
                            pass

        resolved_args_local = {}
        if arg_services:
            arg_resolve_input = (
                f"[Command]\n{sentence}\n\n"
                f"[Selected Services]\n{json.dumps(arg_services, ensure_ascii=False)}\n\n"
                f"[Service Details]\n{_build_arg_resolve_input(arg_services, local_service_details)}"
            )
            arg_resolve_raw = infer("arg_resolve", arg_resolve_input)
            _ar_clean = re.sub(r'<Reasoning>.*?</Reasoning>', '', arg_resolve_raw, flags=re.DOTALL).strip()
            _ar_clean = re.sub(r'```(?:json)?\s*', '', _ar_clean).strip().rstrip("`").strip()
            try:
                parsed_ar = json.loads(_ar_clean)
                if isinstance(parsed_ar, dict):
                    resolved_args_local = parsed_ar
            except Exception:
                m = re.search(r'\{.*\}', _ar_clean, re.DOTALL)
                if m:
                    try:
                        parsed_ar = json.loads(m.group(0))
                        if isinstance(parsed_ar, dict):
                            resolved_args_local = parsed_ar
                    except Exception:
                        pass

        return resolved_args_local, resolved_enum_conds_local

    # ── Precision branch: command + selected services → JSON dict of selectors ──
    def _build_precision_services_block(svcs):
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

    def _precision_one_service(svc):
        """Run precision LLM for ONE service. Returns (svc, [selectors], reasoning_text)."""
        if '.' not in svc:
            return svc, [], ""
        dev, svc_name = svc.split('.', 1)
        svc_name_clean = svc_name.replace("()", "")
        is_value = any(e["id"] == svc_name_clean for e in SERVICE_DATA.get(dev, {}).get("values", []))
        kind = "value" if is_value else "function"

        per_input = (
            f"[Command]\n{sentence}\n\n"
            f"[Service]\n{dev}.{svc_name_clean} ({kind})\n\n"
            f"[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}"
        )
        raw = infer("mapping_precision", per_input).strip()

        reasoning_local = ""
        m_r = re.search(r'<Reasoning>(.*?)</Reasoning>', raw, flags=re.DOTALL)
        if m_r:
            reasoning_local = m_r.group(1).strip()

        cleaned = re.sub(r'<Reasoning>.*?</Reasoning>', '', raw, flags=re.DOTALL).strip()
        cleaned = re.sub(r'```(?:json)?\s*', '', cleaned).strip().rstrip('`').strip()

        sel_list = []
        # Try parsing as JSON list directly
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, list):
                sel_list = [str(x) for x in obj if isinstance(x, str)]
            elif isinstance(obj, dict):
                # Backward-compat: model emitted dict — extract values for THIS svc
                for k, v in obj.items():
                    if k == f"{dev}.{svc_name_clean}":
                        if isinstance(v, list):
                            sel_list = [str(x) for x in v if isinstance(x, str)]
                        elif isinstance(v, str):
                            sel_list = [v]
                        break
        except Exception:
            m = re.search(r'\[.*?\]', cleaned, re.DOTALL)
            if m:
                try:
                    obj = json.loads(m.group(0))
                    if isinstance(obj, list):
                        sel_list = [str(x) for x in obj if isinstance(x, str)]
                except Exception:
                    pass

        return svc, sel_list, reasoning_local

    def run_precision():
        # Fan out: one LLM call per service in parallel.
        if not selected_services:
            return {"selectors": {}, "reasoning": ""}
        results = {}
        reasoning_blocks = []
        with ThreadPoolExecutor(max_workers=max(1, len(selected_services))) as px:
            futures = [px.submit(_precision_one_service, s) for s in selected_services]
            for f in futures:
                svc, sel_list, rs = f.result()
                if sel_list:
                    results[svc] = sel_list
                if rs:
                    reasoning_blocks.append(f"{svc}:\n  {rs}")
        return {"selectors": results, "reasoning": "\n".join(reasoning_blocks)}

    # ── IR extract (sequential, after both branches finish) ──
    def _build_intent_services_block(svcs, details):
        """Build a MINIMAL services block for the IR extractor.

        Argument values come from Stage 2.5 (arg_resolve) and ENUM cond
        comparisons come from Stage 2.4 (enum_resolve) — both surfaced via the
        `[Resolved Args]` augmentation. The extractor only needs to know, per
        service:
          - kind (value or function) — chooses `read` vs `call` op
          - return type (non-VOID, simple type only) — informs chain/bind decisions
          - 1-line descriptor — disambiguates intent

        Argument schemas AND ENUM member lists are intentionally OMITTED to
        prevent the extractor from re-deciding values (those are upstream stages'
        job).

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
                    v_type = svc_info.get("type", "") or ""
                    ret_str = v_type
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

    # Auto-inject `var` on prior calls whose method-name suffix is referenced
    # via `$<MethodName>` in any later step's args/cond. Backstop for cases
    # where the extractor LLM forgets to declare `var`.
    def _inject_implicit_vars(ir_obj):
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

    _inject_implicit_vars(ir)

    ir_readable = ir_to_readable(ir)
    ir_json_str = json.dumps(ir, ensure_ascii=False, indent=2)

    # ── Stage 4 (JoI lowering) DISABLED for stage-by-stage IR validation ──
    # Re-enable by uncommenting the block below.
    code_pretty = ""
    elapsed = time.perf_counter() - start
    # bucket = classify_ir(ir)
    # log_buf.append(f"📦 IR bucket: {bucket}")
    # prompt_key = f"joi_from_ir_{bucket}"
    # try:
    #     system_prompt = _load_lowering_prompt(bucket)
    # except FileNotFoundError as e:
    #     raise JoiGenerationError(
    #         f"Lowering prompt missing: {e}",
    #         "\n".join(log_buf),
    #         error_code="missing_lowering_prompt",
    #     )
    #
    # joi_input = (
    #     f"[Command]\n{sentence}\n\n"
    #     f"[Timeline IR]\n{ir_json_str}\n\n"
    #     f"[IR Readable]\n{ir_readable}\n\n"
    #     f"[Precision Selectors]\n{precision_output}\n\n"
    #     f"[Service Details]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
    # )
    # joi_code_raw = infer(prompt_key, joi_input, system=system_prompt)
    #
    # script = re.sub(r'<Reasoning>.*?</Reasoning>', '', joi_code_raw, flags=re.DOTALL).strip()
    #
    # joi_json = {}
    # try:
    #     m = re.search(r'"script"\s*:\s*"(.*?)"\s*\}', script, re.DOTALL)
    #     if m:
    #         fixed_inner = m.group(1).replace('\n', '\\n')
    #         script = script[:m.start(1)] + fixed_inner + script[m.end(1):]
    #     joi_json = json.loads(script)
    #     if "script" in joi_json:
    #         joi_json["script"] = _apply_service_prefix(joi_json["script"])
    #         joi_json["script"] = _normalize_script_newlines(joi_json["script"])
    #     joi_json.setdefault("name", "Scenario")
    #     joi_json = {"name": joi_json.pop("name"), **joi_json}
    #     joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
    # except (json.JSONDecodeError, TypeError):
    #     body = _apply_service_prefix(script)
    #     joi_json = {
    #         "name": "Scenario",
    #         "cron": "",
    #         "period": 0,
    #         "script": _normalize_script_newlines(body),
    #     }
    #     joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
    #
    # try:
    #     _ = validate_joi(joi_json.get("script", ""), connected_devices, _SERVICE_CATEGORY_MAP)
    # except Exception as e:
    #     log_buf.append(f"⚠️ validate_joi warning: {e}")
    #
    # elapsed = time.perf_counter() - start
    #
    # try:
    #     joi_json_final = json.loads(joi_code_raw)
    #     if "script" in joi_json_final:
    #         joi_json_final["script"] = _post_process_joi_any_quantifiers(joi_json_final["script"])
    #     joi_code_raw = json.dumps(joi_json_final, indent=2, ensure_ascii=False)
    # except (json.JSONDecodeError, TypeError):
    #     joi_code_raw = _post_process_joi_any_quantifiers(joi_code_raw)
    #
    # code_pretty = re.sub(
    #     r'("script"\s*:\s*")(.*?)(")',
    #     lambda m: m.group(1) + m.group(2).replace('\\n', '\n') + m.group(3),
    #     joi_code_raw,
    #     count=1,
    #     flags=re.DOTALL,
    # )

    return {
        "code": code_pretty,
        "merged_command": merged_command,
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
