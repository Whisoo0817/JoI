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
    [Stage 4] joi_from_ir lowering: IR + precision -> JoI (bucket-routed)

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
from loader import SERVICE_DATA, PROMPTS, SUB_SKILL_TAGS, get_device_rules_section
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
    _strip_selector_extra_parens,
    _parse_dict_input,
)
from timeline_ir import extract_ir, ir_to_readable, validate_ir, IRValidationError, parse_duration_to_ms

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
        """Concatenate the default ('service_plan') section of each connected device's
        device_rules_*.md. Stage-scoped sections (e.g. `# @ArgResolve`) are stripped —
        those are pulled by their respective stages.
        """
        chunks = []
        for cat in categories:
            rule = get_device_rules_section(cat, "service_plan")
            if rule:
                chunks.append(f"### {cat}\n{rule}")
        return "\n\n".join(chunks) if chunks else "(no device-specific rules)"

    def _build_device_specific_hints(svcs, section):
        """Collect stage-scoped device hints from device_rules_<cat>.md for each
        distinct category present in `svcs`. Returns scoped block text or empty
        string if no hints are defined.
        """
        cats = sorted({s.split('.', 1)[0] for s in svcs if '.' in s})
        chunks = []
        for cat in cats:
            hint = get_device_rules_section(cat, section)
            if hint:
                chunks.append(f"### {cat}\n{hint}")
        return "\n\n".join(chunks)

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
    # NOTE: inject_value_service(selected_services) removed 2026-05-11.
    # service_plan now decides companion-read inclusion semantically (see Rule 10
    # in files/service_plan.md). Absolute setters get setter-only; relative
    # adjustments get read + setter. No Python-level auto-injection.
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

    def _parse_json_dict_of_str_lists(raw):
        """Strip reasoning/fences, parse a JSON dict whose values are list[str] (or coerce str→[str])."""
        reasoning_text = ""
        m_r = re.search(r'<Reasoning>(.*?)</Reasoning>', raw, flags=re.DOTALL)
        if m_r:
            reasoning_text = m_r.group(1).strip()
        cleaned = re.sub(r'<Reasoning>.*?</Reasoning>', '', raw, flags=re.DOTALL).strip()
        cleaned = re.sub(r'```(?:json)?\s*', '', cleaned).strip().rstrip('`').strip()
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

    def _parse_device_match_qids(raw):
        """Parse {Service: {"q": "one|all|any", "groups": [[ids], ...]}} from Step 1 raw output.
        Accepts both new (`groups`) and legacy (`ids`) forms. Returns normalized {q, groups}.
        """
        reasoning_text = ""
        m_r = re.search(r'<Reasoning>(.*?)</Reasoning>', raw, flags=re.DOTALL)
        if m_r:
            reasoning_text = m_r.group(1).strip()
        cleaned = re.sub(r'<Reasoning>.*?</Reasoning>', '', raw, flags=re.DOTALL).strip()
        cleaned = re.sub(r'```(?:json)?\s*', '', cleaned).strip().rstrip('`').strip()
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
                        # legacy: ids → single group
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

    # Enforce [Resolved Args] verbatim: strip any LLM-hallucinated keys from
    # `call.args` (e.g. `Selector`, `Scope`, `Filter`) by overriding with
    # what arg_resolve produced. Skip overrides when the LLM used the R3
    # "Delta exception" ($var arithmetic), since arg_resolve doesn't know
    # those derived values.
    def _enforce_resolved_args(ir_obj, ra):
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

    _enforce_resolved_args(ir, resolved_args)

    # Normalize logical operators in cond/until expressions to JoI keywords.
    # IR-extractor occasionally emits C-style `&&`/`||`/`!` despite the prompt.
    def _normalize_logical_ops(ir_obj):
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

    _normalize_logical_ops(ir)

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
    joi_code_raw = infer(prompt_key, joi_input, system=system_prompt)

    script = re.sub(r'<Reasoning>.*?</Reasoning>', '', joi_code_raw, flags=re.DOTALL).strip()

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
        joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        body = _apply_service_prefix(_strip_selector_extra_parens(script))
        joi_json = {
            "name": "Scenario",
            "cron": "",
            "period": 0,
            "script": _normalize_script_newlines(body),
        }
        joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)

    try:
        _ = validate_joi(joi_json.get("script", ""), connected_devices, _SERVICE_CATEGORY_MAP)
    except Exception as e:
        log_buf.append(f"⚠️ validate_joi warning: {e}")

    # Deterministic wrapper.period override from IR.cycle.period.
    # LLM is unreliable at unit arithmetic ("30 SEC" → 1800000); compute it here.
    # D-3 (cycle body has wait edge="rising") is hardcoded to 100 regardless of cycle.period value.
    def _wrapper_period_from_ir(ir_obj):
        tl = (ir_obj or {}).get("timeline", [])
        for s in tl:
            if isinstance(s, dict) and s.get("op") == "cycle":
                body = s.get("body") or []
                if any(isinstance(x, dict) and x.get("op") == "wait" and x.get("edge") == "rising" for x in body):
                    return 100
                p = s.get("period")
                if isinstance(p, str):
                    try:
                        return parse_duration_to_ms(p)
                    except ValueError:
                        return None
                return None
        return None  # no cycle → keep LLM's value (typically 0 for noncycle)
    _override_ms = _wrapper_period_from_ir(ir)
    if _override_ms is not None and joi_json.get("period") != _override_ms:
        log_buf.append(f"🔧 wrapper.period override: {joi_json.get('period')} → {_override_ms} (from IR cycle.period)")
        joi_json["period"] = _override_ms
        joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)

    try:
        joi_json_final = json.loads(joi_code_raw)
        if "script" in joi_json_final:
            joi_json_final["script"] = _post_process_joi_any_quantifiers(joi_json_final["script"])
        joi_code_raw = json.dumps(joi_json_final, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        joi_code_raw = _post_process_joi_any_quantifiers(joi_code_raw)

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
