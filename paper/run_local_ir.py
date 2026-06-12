"""IR-based JoI generation pipeline (experimental).

Replaces the legacy filter/extractor/router stages with
Timeline IR extraction. The pipeline is:

    [Stage 1] translation to English when needed
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
from device_ontology import (
    build_nickname_index, resolve_nicknames, select_categories_for_command,
    parse_targets, resolve_targets,
)
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
    _reapply_precision_quantifiers,
    _strip_selector_extra_parens,
    _parse_dict_input,
)
from timeline_ir import (
    extract_ir, ir_to_readable, validate_ir, validate_ir_against_devices,
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

# IR-only short-circuit. When JOI_IR_ONLY=1, the pipeline runs through
# Stage 1-3 (translation → service_plan → resolve/precision → IR extract
# → post-process trio) and then writes the IR + supporting state to
# JOI_IR_DUMP_DIR/<JOI_IR_DUMP_NAME>.json, skipping Stage 4 lowering.
# Used for offline IR-confirm validation prior to running lowering.
# (read per-call inside generate_joi_code_ir so in-process callers — e.g. the
#  test.py IR-confirm flow — can toggle them between successive calls; subprocess
#  callers that export the env before launch are unaffected.)

# GT-IR injection (paper §7.3 Stage B: lowering correctness given gold IR).
# When JOI_GT_IR_PATH points to a JSON file containing the GT IR, the
# pipeline skips service_plan + arg_resolve + enum_resolve + extract_ir,
# deriving `selected_services` directly from the GT IR's references and
# using GT IR verbatim. Precision (device-match) still runs so selectors
# align with the GT IR's services. Stage 4 lowering proceeds as usual.
# (JOI_GT_IR_PATH also read per-call inside generate_joi_code_ir.)


def _services_from_ir(ir_obj):
    """Walk IR tree, collect every 'Cat.Method' reference (call.target,
    read.src, and any Service.Member token inside cond/until/cron-free
    string fields). Returns a deduped list in DFS order."""
    seen, ordered = set(), []
    _ref_rx = re.compile(r'\b([A-Z][A-Za-z0-9_]+\.[A-Za-z_][A-Za-z0-9_]+)\b')
    def add(tok):
        if tok and tok not in seen and tok in SERVICE_DATA \
                or tok and tok.split('.', 1)[0] in SERVICE_DATA and tok not in seen:
            seen.add(tok); ordered.append(tok)
    def walk(steps):
        for s in steps or []:
            if not isinstance(s, dict): continue
            op = s.get("op")
            if op == "call":
                tgt = s.get("target", "")
                if "." in tgt: add(tgt)
            elif op == "read":
                src = s.get("src", "")
                if "." in src: add(src)
            for fld in ("cond", "until"):
                v = s.get(fld) or ""
                if isinstance(v, str):
                    for m in _ref_rx.findall(v): add(m)
            for k in ("body", "then", "else"):
                if isinstance(s.get(k), list): walk(s[k])
    walk(ir_obj.get("timeline") or [])
    return ordered

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
                # `sel`: per-group selector tags chosen by the LLM (the narrowing
                # signals — device-class / brand / location). Parallel to groups.
                # Falls back to [] per group → Python uses tag-intersection.
                sel_raw = v.get("sel", v.get("tags", []))
                sel = []
                if isinstance(sel_raw, list):
                    for tg in sel_raw:
                        sel.append([str(t) for t in tg] if isinstance(tg, list)
                                   else ([str(tg)] if isinstance(tg, (str, int)) else []))
                # Pad / trim sel to match groups length.
                while len(sel) < len(groups):
                    sel.append([])
                sel = sel[:len(groups)]
                out[k] = {"q": q, "groups": groups, "sel": sel}
            elif isinstance(v, list):
                out[k] = {"q": "one", "groups": [_norm_ids(v)], "sel": [[]]}

    def _try(text):
        try:
            _ingest(json.loads(text))
            return bool(out)
        except Exception:
            return False

    if not _try(cleaned):
        # device_match often returns ONE {Service: {...}} object PER service as
        # separate concatenated blocks (especially without Command Hints) rather
        # than a single merged object — `json.loads` of the whole blob then fails.
        # Ingest EACH top-level {...} object (balancing per object) so we keep
        # every service's mapping instead of losing them all.
        objs = _iter_top_level_objects(cleaned)
        if len(objs) > 1:
            for obj_str in objs:
                if not _try(obj_str):
                    cand = _balance_brackets(obj_str)
                    if cand:
                        _try(cand)
        if not out:
            m = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if m:
                _try(m.group(0))
    # Recovery: the nested `sel: [[...]]` lists make the model drop or add a
    # closing bracket fairly often (e.g. `"sel": [["Speaker"]}}` — one `]`
    # short), which kills the whole object. Re-balance trailing brackets and
    # retry rather than losing every service's mapping.
    if not out:
        cand = _balance_brackets(cleaned)
        if cand:
            _try(cand)
    return out, reasoning_text


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


def _parse_list_of_strings_from_llm(raw: str, allowed_prefixes=None):
    """Parse a JSON list-of-strings from LLM output. Optional filter:
    keep only entries that contain '.' AND whose prefix is in `allowed_prefixes`.

    Returns (kept_items, unconnected_prefixes). Drop has TWO causes, kept
    distinct so callers can error vs ignore:
      - prefix NOT in `allowed_prefixes`  → the device category is simply not
        connected (e.g. command asks for a curtain but no WindowCovering exists).
        These prefixes are collected into `unconnected` so the caller can raise an
        explicit "device not connected" error instead of silently proceeding.
      - method not in the catalog          → a service_plan hallucination
        (`Light.MaxLevel` from NL "max"). Silently dropped, as before — the
        descriptor-derived literal is the natural fallback. NOT reported.
    When `allowed_prefixes is None`, no filtering and `unconnected` is empty.
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
    unconnected = []
    if allowed_prefixes is not None:
        def _method_in_catalog(svc: str) -> bool:
            if '.' not in svc:
                return False
            dev, method = svc.split('.', 1)
            method = method.replace("()", "")
            entry = SERVICE_DATA.get(dev)
            if not isinstance(entry, dict):
                return False
            for kind in ("values", "functions"):
                for item in entry.get(kind, []) or []:
                    if isinstance(item, dict) and item.get("id") == method:
                        return True
            return False
        kept = []
        for s in items:
            if '.' not in s:
                continue
            prefix = s.split('.')[0]
            if prefix not in allowed_prefixes:
                unconnected.append(prefix)   # category not connected → Gate A
            elif _method_in_catalog(s):
                kept.append(s)
            # else: hallucinated method → silent drop (literal fallback)
        items = kept
    # Preserve duplicates: service_plan may legitimately list the same service
    # multiple times (alternation, staged on/off, sequential multi-call). Dedup
    # would collapse [X, X] → [X] and silently kill arg_resolve's list form.
    return items, unconnected


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

    # Env switches are read per-call (not at import) so in-process callers can
    # toggle them between successive generate_joi_code() invocations.
    _IR_ONLY = os.environ.get("JOI_IR_ONLY", "0") == "1"
    _IR_DUMP_DIR = os.environ.get("JOI_IR_DUMP_DIR", "/tmp/joi_ir_dump")
    _IR_DUMP_NAME = os.environ.get("JOI_IR_DUMP_NAME", "")
    _GT_IR_PATH = os.environ.get("JOI_GT_IR_PATH", "")

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

    # ── Device prep — built BEFORE preprocess/translation so (a) the grounding
    # stage can resolve a specific-device nickname to its dN alias before MT can
    # mangle the name, and (b) every later stage reuses the SAME d1/d2… numbering.
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
    # [Device Rules] block is built LATER (after pre_analysis) from the
    # embedding-narrowed category subset — see the JOI_DEVICE_NARROW block.

    # ── ID aliasing: anonymize device ids as d1/d2/... once, share across every
    # LLM stage that sees the device dict (grounding, pre_analysis, service_plan,
    # mapping_device_match). Keeps reasoning consistent and prevents raw IDs from
    # leaking into reasoning that downstream stages would then have to undo.
    # real_of / alias_of are also reused by the precision selector validator.
    real_ids = list(cd_simple.keys())
    alias_of = {real: f"d{i+1}" for i, real in enumerate(real_ids)}
    real_of = {a: r for r, a in alias_of.items()}
    # Device grounding (nickname → dN handle) is DISABLED by default: real
    # deployment payloads don't carry nicknames, so there is nothing to ground.
    # Enable with JOI_DEVICE_GROUNDING=1. When on, we also alias device-id
    # literals that appear INSIDE tags to the SAME dN, so device_match can pin a
    # specific device by putting its handle in `sel` (the handle is then also that
    # device's own tag). When off, cd_aliased is exactly as before (raw id-in-tags).
    _grounding_on = os.environ.get("JOI_DEVICE_GROUNDING") == "1"
    cd_aliased = {
        alias_of[r]: {
            "category": cd_simple[r]["category"],
            "tags": ([alias_of.get(t, t) for t in cd_simple[r]["tags"]]
                     if _grounding_on else list(cd_simple[r]["tags"])),
        }
        for r in real_ids
    }

    # ── Deterministic nickname pinning (replaces the flaky device_grounding
    # LLM). A command that names a device by its exact nickname is matched to
    # that device's real id by normalized-substring lookup — no LLM, no
    # hallucination. The hits feed (a) the category narrower's force-include set
    # so a pinned device's category is never narrowed away, and (b) future
    # exact-pin in device_match. Generic words match nothing and fall through.
    # Gated on JOI_NICKNAME_PIN (default on); set to 0 to disable.
    nickname_hits = []
    if os.environ.get("JOI_NICKNAME_PIN", "1") == "1":
        nickname_hits = resolve_nicknames(sentence, build_nickname_index(connected_devices))
        if nickname_hits:
            _hl = ", ".join(f"{alias_of.get(r, r)}({nn})" for r, nn in nickname_hits)
            log_buf.append(f"📌 nickname pin: {_hl}")

    # Stage 0: Preprocess — runs on the RAW pre-translation input (usually Korean).
    # Lightly normalizes the command (makes a channel-less notification explicit,
    # turns a vague time-of-day like "저녁에" into a concrete "오후 6시부터 9시까지"
    # range) or REJECTS inputs that can't be automated as-is:
    #   - multiple_scenarios:  ≥2 independent trigger→action scenarios in one command
    #   - ambiguous_condition: a threshold-less magnitude condition ("더우면" …)
    # Everything else is kept verbatim. Skip with JOI_SKIP_PREPROCESS=1 (tests).
    # device-first experiment: preprocess OFF. It was mangling commands (adding
    # 토스트/스피커 channels to "메일 보내줘", etc.). retrieve/resolve handle the
    # raw command directly.
    # device-first is the DEFAULT (unset → on); JOI_DEVICE_FIRST=0 forces legacy.
    # Computed HERE (before preprocess/translation) so all the skip gates below
    # agree with it — checking `== "1"` would miss the unset-default case.
    _device_first = os.environ.get("JOI_DEVICE_FIRST", "1") != "0"
    if os.environ.get("JOI_SKIP_PREPROCESS") == "1" or _device_first:
        log_buf.append("➡️ preprocess SKIPPED (device-first / JOI_SKIP_PREPROCESS)")
    else:
        pre_raw = infer("preprocess", f"[Command]\n{sentence}", max_tokens=256).strip()
        _err_m = re.search(r'<error\s+code="([^"]+)"\s*>(.*?)</error>', pre_raw, re.DOTALL)
        if _err_m and _err_m.group(1).strip() in ("multiple_scenarios", "ambiguous_condition"):
            raise JoiGenerationError(
                _err_m.group(2).strip() or "Command cannot be automated as-is.",
                "\n".join(log_buf),
                error_code=_err_m.group(1).strip(),
            )
        _out_m = re.search(r'<out>(.*?)</out>', pre_raw, re.DOTALL)
        if _out_m and _out_m.group(1).strip():
            sentence = _out_m.group(1).strip()

    # `original_sentence` snapshots the natural-language (preprocessed) command
    # BEFORE device grounding, so arg_resolve can still author human-facing text
    # (Speaker/Toast) from the real wording — not from the dN handles. It also
    # feeds downstream stages that emit text in the user's language.
    original_sentence = sentence

    # Stage 0.5: Device grounding — resolve an explicit SPECIFIC-device reference
    # (one named by its nickname) to that device's dN alias, BEFORE translation.
    # This (a) stops MT from mangling a device name (e.g. "…스위치 6구 1" → "…6-way
    # 1" → a phantom quantity that becomes all(#Light)), and (b) lets device_match
    # pin the exact device instead of firing the whole category. Generic
    # type/location/brand words are deliberately left alone by the prompt.
    # Python guard: every dN the model emits must be a REAL alias — otherwise the
    # whole grounding is discarded so no hallucinated handle reaches translation.
    # DISABLED by default (deployment payloads have no nicknames); enable with
    # JOI_DEVICE_GROUNDING=1. JOI_SKIP_GROUNDING=1 also forces it off.
    if not _grounding_on or os.environ.get("JOI_SKIP_GROUNDING") == "1":
        log_buf.append("➡️ device_grounding DISABLED (set JOI_DEVICE_GROUNDING=1 to enable)")
    else:
        names_table = "\n".join(
            f"{a} = {connected_devices.get(real_of[a], {}).get('nickname', '')}"
            for a in cd_aliased
        )
        g_raw = infer(
            "device_grounding",
            f"[Device Names]\n{names_table}\n\n[Command]\n{sentence}",
            max_tokens=256,
        ).strip()
        # Error: the command singled out a SPECIFIC device by name, but no
        # connected device matches it → fail fast with DEVICE_NOT_FOUND instead of
        # letting device_match force-pin some unrelated device.
        _g_err = re.search(r'<error\s+code="([^"]+)"\s*>(.*?)</error>', g_raw, re.DOTALL)
        if _g_err and _g_err.group(1).strip() == "device_not_found":
            raise JoiGenerationError(
                _g_err.group(2).strip() or "Named device is not connected.",
                "\n".join(log_buf),
                error_code="device_not_found",
            )
        _g_out = re.search(r'<out>(.*?)</out>', g_raw, re.DOTALL)
        if _g_out and _g_out.group(1).strip():
            grounded = _g_out.group(1).strip()
            unknown = [t for t in re.findall(r'(?<![A-Za-z0-9])d\d+\b', grounded)
                       if t not in real_of]
            if unknown:
                log_buf.append(
                    f"⚠️ device_grounding emitted unknown handles {unknown} — grounding discarded")
            elif grounded != sentence:
                log_buf.append(f"🔗 device_grounding: {sentence!r} → {grounded!r}")
                sentence = grounded

    # Stage 1: Translation to English when needed.
    # Skip entirely when JOI_SKIP_TRANSLATION=1 to test the pipeline on raw Hangul.
    if os.environ.get("JOI_SKIP_TRANSLATION") == "1":
        log_buf.append("\u27a1\ufe0f translation SKIPPED (JOI_SKIP_TRANSLATION=1) \u2014 raw input passed through")
    elif re.search(r"[\uac00-\ud7a3]", sentence) and not _device_first:
        # device-first: keep ORIGINAL Korean so nicknames match device.nickname.
        sentence = infer("translation", sentence)

    # ❇️ Stage 1.5: Pre-analysis — caveman intent / capability-action·read / quantifier dump.
    # Command-only input: no [Connected Devices], no [Device Summary]. It does NOT
    # name categories/services/devices (those rule-sheets leaked example commands and
    # tempted Cat.Method picks); downstream stages own all category/device/service
    # choices. Just the system prompt + the per-command [Command].
    # device-first experiment runs WITHOUT pre_analysis — device_retrieve/resolve
    # read the command directly. Skip the call and use empty hints.
    if _device_first:
        command_hints = ""
    else:
        pre_input = f"[Command]\n{sentence}"
        # pre_analysis emits a plain caveman dump (no <Reasoning> wrapper), no parsing.
        command_hints = infer("pre_analysis", pre_input, max_tokens=512).strip()

    # Device-first (Stage 2 / device_resolve) injects the MATCH dict so
    # run_precision can skip its own device_match LLM call. None in legacy mode.
    injected_match_qids = None
    # Device-first is now the DEFAULT path (retrieve → resolve_targets → resolve →
    # quantifier → translation → IR → lowering → naming); `_device_first` is
    # computed above (before preprocess). Set JOI_DEVICE_FIRST=0 for the legacy
    # embedding-narrow → service_plan → device_match path.
    # device-first builds its precision_output (selectors/resolved) directly from
    # device_resolve, so run_precision returns this instead of doing its own LLM.
    _df_precision = None
    # Services from `read`-role targets (e.g. Clock.Hour/Minute) — the ONLY value
    # reads arg_resolve may weave into text args. None in legacy mode. Keeping it
    # scoped to read-role avoids exposing condition-gate reads (e.g. ContactSensor.
    # Contact) that arg_resolve would otherwise mis-grab for a $<ref> argument.
    _df_read_services = None

    # Three ways to produce `selected_services`:
    #   (1) GT-IR mode — derive from a ground-truth IR (eval only).
    #   (2) JOI_DEVICE_FIRST — retrieve candidate device ids (Stage 1) then resolve
    #       PLAN+MATCH over just those candidates (Stage 2). No embedding, nickname
    #       and tag targeting unified, narrowing automatic.
    #   (3) legacy — embedding category-narrow → service_plan, then a separate
    #       device_match LLM inside run_precision.
    _gt_ir_obj = None
    if _GT_IR_PATH:
        try:
            with open(_GT_IR_PATH, encoding="utf-8") as _f:
                _gt_ir_obj = json.load(_f)
        except Exception as e:
            raise JoiGenerationError(
                f"JOI_GT_IR_PATH set but failed to load {_GT_IR_PATH}: {e}",
                "\n".join(log_buf), error_code="gt_ir_load_failed",
            )
        selected_services = _services_from_ir(_gt_ir_obj)
        log_buf.append(f"🧪 GT-IR mode: derived selected_services = {selected_services}")

    elif _device_first:
        # ── EXPERIMENT (stops after device_resolve; arg/enum/IR/lowering skipped). ──
        # Stage 1 device_retrieve → semi-structured target groups (role + by-criterion).
        # Python resolve_targets applies each criterion → matched ids + categories
        # (free, exact narrowing). Stage 2 device_resolve sees only those targets +
        # their category summaries → final selectors `<quant>(#Tag).Cat.Method`.
        cd_named = {
            a: {"category": cd_aliased[a]["category"],
                "tags": cd_aliased[a]["tags"],
                "nickname": connected_devices.get(real_of[a], {}).get("nickname", "")}
            for a in cd_aliased
        }
        retrieve_user = (
            f"[Connected Devices]\n{json.dumps(cd_named, indent=2, ensure_ascii=False)}\n\n"
            f"[Command]\n{sentence}"
        )
        retr_raw = infer("device_retrieve", retrieve_user, max_tokens=512).strip()
        # Missing device → retrieve emits a single `NONE:` line. Fail fast.
        _none = re.search(r'(?im)^\s*NONE:\s*(.+?)\s*$', retr_raw)
        if _none:
            log_buf.append(f"⛔ device_retrieve NONE: {_none.group(1)}")
            raise JoiGenerationError(
                f"Cannot fulfill command — {_none.group(1)}",
                "\n".join(log_buf), error_code="device_not_connected",
            )
        _tm = re.search(r'<targets>(.*?)</targets>', retr_raw, re.DOTALL)
        targets_spec = (_tm.group(1).strip() if _tm else retr_raw).strip()

        # Deterministic: apply each target's by-criterion over cd_named (dN ids,
        # incl. nickname — cd_aliased has no nickname field so label/nickname
        # matching must use cd_named).
        groups = resolve_targets(parse_targets(targets_spec), cd_named)
        if not groups:
            raise JoiGenerationError(
                "No target devices identified.",
                "\n".join(log_buf), error_code="device_not_connected",
            )
        # ANY group that matched zero devices means the command named a device kind
        # that isn't connected (e.g. retrieve emitted label:WindowCovering for 커튼
        # but none exists). That target can't be fulfilled → fail, don't let
        # device_resolve hallucinate a call on an empty selector.
        empty = [f"{g['by_kind']}:{g['by_val']}" for g in groups if not g["ids"]]
        if empty:
            raise JoiGenerationError(
                f"No connected device for: {', '.join(empty)}",
                "\n".join(log_buf), error_code="device_not_connected",
            )
        # [Targets] block for device_resolve: role + criterion + match count + (nickname) tag.
        target_lines = []
        for g in groups:
            crit = f"{g['by_kind']}:{g['by_val']}"
            tagsfx = f" | tags={g['ids']}" if g["by_kind"] == "nickname" else ""
            target_lines.append(
                f"- role={g['role']} | {crit} | {len(g['ids'])} devices matched{tagsfx}")
        resolve_cats = sorted({c for g in groups for c in g["categories"]})
        resolve_user = (
            f"[Command]\n{sentence}\n\n"
            f"[Targets]\n" + "\n".join(target_lines) + "\n\n"
            f"[Device Summary]\n{_build_device_selection_rules(resolve_cats)}"
        )
        resolve_raw = infer("device_resolve", resolve_user,
                            system=PROMPTS.get("device_resolve", "")).strip()
        _err = re.search(r'(?im)^\s*ERROR:\s*(.+?)\s*$', resolve_raw)
        if _err:
            log_buf.append(f"⛔ device_resolve ERROR: {_err.group(1)}")
            raise JoiGenerationError(
                f"Cannot fulfill command — {_err.group(1)}",
                "\n".join(log_buf), error_code="device_not_connected",
            )
        result_block = resolve_raw.split("RESULT:", 1)[1].strip() if "RESULT:" in resolve_raw else ""
        raw_selectors = [ln.strip() for ln in result_block.splitlines()
                         if ln.strip() and "(" in ln and ")" in ln]

        # ── Deterministic quantifier: resolve emits NO prefix; we add all/any/one
        # from each group's scope + role + match count. Map a selector's first
        # #Tag back to the group that owns it.
        from device_ontology import quantifier_for as _qf, _CHANNEL_CATEGORY as _CHCAT
        tag_to_group = {}
        for g in groups:
            owned = []
            if g["by_kind"] == "label":
                owned = [g["by_val"]]
            elif g["by_kind"] == "nickname":
                owned = list(g["ids"])  # the dN handle(s)
            elif g["by_kind"] == "channel":
                owned = [_CHCAT.get(c.strip().lower())
                         for c in g["by_val"].split(",") if c.strip()]
            for t in owned:
                if t:
                    tag_to_group[t] = g
        selectors = []
        for s in raw_selectors:
            s = re.sub(r'^\s*(all|any|one)\s*\(', '(', s)  # drop any LLM-emitted prefix
            first_tag = re.search(r'#([A-Za-z0-9_\-]+)', s)
            g = tag_to_group.get(first_tag.group(1)) if first_tag else None
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
        _sel_re = re.compile(r'^\s*(all|any)?\s*(\(#[^)]*\))\.([A-Za-z]\w*\.[A-Za-z]\w*)')
        for full, g in selectors:
            m = _sel_re.match(full)
            if not m:
                continue
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

    else:
        # ── Embedding category narrowing → service_plan (legacy 2-stage) ──
        # Narrow [Device Rules] to the categories most relevant to the command so
        # service_plan sees ~3 blocks not ~27 (-19k tokens). Gate A still validates
        # against the FULL connected set (valid_categories). Falls back to the full
        # set when the embedding server is down. Gated JOI_DEVICE_NARROW (default on).
        plan_categories = primary_categories
        if os.environ.get("JOI_DEVICE_NARROW", "1") == "1":
            _pinned_cats = [c for r, _nn in nickname_hits
                            for c in cd_simple.get(r, {}).get("category", [])]
            _narrow_query = (sentence if os.environ.get("JOI_NARROW_NO_HINTS") == "1"
                             else f"{sentence}\n{command_hints}")
            plan_categories, _narrow_info = select_categories_for_command(
                _narrow_query, primary_categories,
                pinned_categories=_pinned_cats,
                top_k=int(os.environ.get("JOI_NARROW_TOPK", "10")),
            )
            log_buf.append(f"🔍 {_narrow_info}")
        device_rules_block = _build_device_selection_rules(plan_categories)
        plan_sys_prompt = PROMPTS.get("service_plan", "")
        plan_input = (
            f"[Connected Devices]\n{json.dumps(cd_aliased, indent=2, ensure_ascii=False)}\n\n"
            f"[Device Rules]\n{device_rules_block}\n\n"
            f"[Command]\n{sentence}\n\n"
            f"[Command Hints]\n{command_hints}"
        )
        plan_output = infer("service_plan", plan_input, system=plan_sys_prompt)
        _missing = re.search(r'(?im)^\s*MISSING:\s*(.+?)\s*$', plan_output)
        if _missing:
            log_buf.append(f"⛔ service_plan declared MISSING: {_missing.group(1)}")
            raise JoiGenerationError(
                f"Cannot fulfill command — no connected device for: {_missing.group(1)}",
                "\n".join(log_buf),
                error_code="device_not_connected",
            )
        selected_services, unconnected_prefixes = _parse_list_of_strings_from_llm(
            plan_output, allowed_prefixes=valid_categories
        )
        if unconnected_prefixes:
            missing = ", ".join(sorted(set(unconnected_prefixes)))
            raise JoiGenerationError(
                f"Required device category not connected: {missing}",
                "\n".join(log_buf),
                error_code="device_not_connected",
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
        # Two-step LLM call with id-aliasing + selector validator + retry:
        #   1. Build alias map (d1, d2, ...) for cd_simple keys; rewrite [Connected Devices].
        #   2. Step 1 (mapping_device_match): {Service: {q, ids}}.
        #   3. Step 2 (mapping_selector, multi-turn): {Service: ["(#Tag ...)"]}.
        #   4. Python validator: apply each selector to cd_aliased, check it matches exactly target ids.
        #   5. If mismatch, send mismatch info as follow-up user msg; retry up to 2 times.
        #   6. If still mismatch, fall back to deterministic minimum-tag-set selector.
        # device-first already produced the selectors via device_resolve — use them
        # directly and skip the device_match LLM call + selector synthesis.
        if _df_precision is not None:
            return _df_precision
        if not selected_services:
            return {"selectors": {}, "resolved": {}, "reasoning": ""}

        # alias_of / real_of / cd_aliased computed upstream (see Stage 2 pre-work).

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

        # Order: static [Connected Devices] FIRST (right after the system prompt)
        # so `system + devices` forms a stable token prefix that vLLM prefix
        # caching can reuse across commands; the per-command dynamic sections go
        # last so only the small tail is re-prefilled.
        # Device-first mode injects MATCH from Stage 2 (device_resolve) — skip the
        # dedicated device_match LLM call and reuse the deterministic selector
        # machinery below verbatim.
        if injected_match_qids is not None:
            match_qids, step1_reasoning = injected_match_qids, "(from device_resolve)"
        else:
            step1_user = (
                f"[Connected Devices]\n{json.dumps(cd_aliased, indent=2, ensure_ascii=False)}\n\n"
                f"[Command]\n{sentence}\n\n"
                f"[Command Hints]\n{command_hints}\n\n"
                f"[Selected Services]\n{json.dumps(selected_services, ensure_ascii=False)}"
            )
            step1_raw = infer("mapping_device_match", step1_user).strip()
            match_qids, step1_reasoning = _parse_device_match_qids(step1_raw)
        # device_match produced NOTHING parseable (runaway reasoning truncated at
        # max_tokens, pure-prose output, etc.) — even the 3-tier JSON recovery in
        # _parse_device_match_qids salvaged zero services. This is a model/reasoning
        # failure, NOT a "device absent from scope" situation, so surface it as
        # REASONING_FAILED rather than letting every service default to an empty
        # group and mis-report as no_device_in_scope (Gate B / 1202).
        if not match_qids:
            raise JoiGenerationError(
                "Device matching produced no parseable result.",
                "\n".join(log_buf),
                error_code="device_match_failed",
            )
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

        def _selector_for_group(group_ids, q, service_prefix, sel_tags=None):
            wrap = "" if q == "one" else q
            # Preferred path: the LLM named the narrowing tags (device-class /
            # brand / location). Use them verbatim — they ARE the selector — so we
            # don't over-constrain with incidental shared tags (location/brand/
            # NoneNecessary) that creep in when a group has few devices.
            if sel_tags:
                filtered = [t for t in sel_tags
                            if t not in SUB_SKILL_TAGS or t == service_prefix]
                if filtered:
                    return f"{wrap}(#{' #'.join(filtered)})"
            # Fallback: intersection of the group's tags (legacy behavior).
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
            entry = match_qids.get(svc, {"q": "one", "groups": [[]], "sel": []})
            q = entry.get("q", "one")
            groups = entry.get("groups", [[]])
            sel = entry.get("sel", [])
            service_prefix = svc.split(".", 1)[0]
            sel_list = []
            for gi, g in enumerate(groups):
                if not g:
                    continue
                sel_tags = sel[gi] if gi < len(sel) else []
                s = _selector_for_group(g, q, service_prefix, sel_tags)
                if s:
                    sel_list.append(s)
            if not sel_list:
                # Gate B: device_match found NO connected device for this service
                # within the command's narrowing (every group empty). service_plan
                # should have caught a fully-absent category (Gate A); reaching here
                # means the category exists but not in the asked scope (e.g. a
                # PresenceSensor exists, but none in the named room). Fail loudly
                # instead of fabricating an all-category selector that fires on the
                # wrong devices.
                raise JoiGenerationError(
                    f"No connected device matches '{svc}' within the requested scope.",
                    "\n".join(log_buf),
                    error_code="no_device_in_scope",
                )
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

        # Resolved real devices per service (render-only): map device_match's
        # d1/d2 aliases back to real device ids so the confirmation rendering can
        # name the actual devices instead of guessing a noun from the IR service.
        resolved_devices = {
            svc: {
                "q": entry.get("q", "one"),
                "devices": [real_of.get(a, a)
                            for g in entry.get("groups", []) for a in g],
            }
            for svc, entry in match_qids.items()
        }

        combined_reasoning = (
            f"[Step1 device match]\n{step1_reasoning}\n\n"
            f"[Targets]\n{targets_block}\n\n"
            f"[Selectors generated deterministically by Python (intersection of target tags)]"
        )
        return {"selectors": selectors, "resolved": resolved_devices,
                "reasoning": combined_reasoning}

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
    if _gt_ir_obj is not None:
        # GT-IR mode: run precision only (we still need selectors for the
        # services referenced by GT IR); skip resolve_branch + extract_ir.
        precision_output = run_precision()
        ir = _gt_ir_obj
    else:
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

    translated_sentence = ""
    translated_sentence_kor = ""
    if os.environ.get("JOI_SKIP_NAME") != "1":
        is_korean = bool(re.search(r"[가-힣]", original_sentence))
        try:
            _eng_plan = f"\n\n[Code Plan]\n{code_plan}" if code_plan else ""
            _dur_hints = _duration_hints(joi_json)
            _re_in = (
                f"[Code]\n{joi_code_raw}{_eng_plan}{_dur_hints}\n\n"
                f"[Service Descriptions]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
            )
            translated_sentence = infer("re_translate", _re_in).strip()
            log_buf.append(f"📝 re_translate (EN): {translated_sentence}")
        except Exception as _e:
            log_buf.append(f"⚠️ re_translate failed ({_e})")
        if is_korean and translated_sentence:
            try:
                translated_sentence_kor = infer("re_translate_kor", translated_sentence).strip()
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
        # spaces → `_`; keep unicode word chars (Korean survives), drop punctuation.
        scenario_name = re.sub(r'\s+', '_', scenario_name.strip())
        scenario_name = re.sub(r'[^\w]', '', scenario_name).strip('_') or "Scenario"
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
