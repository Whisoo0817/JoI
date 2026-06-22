import time
import ast
import json
import re
from collections import defaultdict

from loader import SERVICE_DATA, SUB_SKILL_TAGS


class JoiGenerationError(ValueError):
    """generate_joi_code 내부 오류. logs 속성에 오류 발생 전까지의 로그를 담는다."""
    def __init__(self, message, logs="", error_code=""):
        super().__init__(message)
        self.logs = logs
        self.error_code = error_code


def run_llm_inference(model, client, inference_type, messages, *, enable_thinking=False, max_tokens=512):
    start_inference = time.perf_counter()
    stream = client.chat.completions.create(
        messages=messages,
        model=model,
        temperature=0.1,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
        extra_body={"chat_template_kwargs": {"enable_thinking": enable_thinking}}
    )
    chunks = []
    usage = None
    finish_reason = None
    first_token_time = None
    for chunk in stream:
        if chunk.usage:
            usage = chunk.usage
        if chunk.choices:
            if chunk.choices[0].delta.content:
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                chunks.append(chunk.choices[0].delta.content)
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason
    elapsed = time.perf_counter() - start_inference
    content = "".join(chunks)

    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    # TTFT = prefill latency (time to first generated token). tg = pure decode
    # rate = generated tokens / (elapsed - TTFT), so the prefill of a large
    # prompt no longer drags the reported generation speed down.
    ttft = (first_token_time - start_inference) if first_token_time else elapsed
    gen_elapsed = elapsed - ttft
    tg_tps = completion_tokens / gen_elapsed if gen_elapsed > 0 and completion_tokens else 0
    log_line = (
        f"➡️ {inference_type}({prompt_tokens}) | TTFT: {ttft:.4f}s | "
        f"tg: {tg_tps:.1f} t/s | Total: {elapsed:.4f}s\n"
        f"===================================================\n"
        f"{content}"
    )
    # finish_reason == "length" → the model hit max_tokens mid-output (reasoning
    # runaway), so the result is TRUNCATED, not a real answer. This is distinct
    # from a clean finish that happens to be empty/unparseable: the latter is a
    # stage-specific failure, this is a reasoning overflow. Raise stage-agnostically
    # so it surfaces as a reasoning error, not (mis)attributed to the stage's
    # normal failure mode.
    if finish_reason == "length":
        raise JoiGenerationError(
            f"{inference_type}: generation truncated at token budget (reasoning overflow).",
            log_line,
            error_code="reasoning_overflow",
        )
    return content.strip(), log_line


# selected_services = ["Light.Off", "ContactSensor.Contact"]
# SERVICE_DATA에서 Parsing
def extract_service_details(selected_services, full_service_data):
    # Switch, LevelControl, ColorControl은 독립 카테고리지만
    # Light 같은 primary 디바이스에 포함되어 있어 여기서 fallback으로 탐색
    SECONDARY_CATS = ["LevelControl", "ColorControl", "Switch"]

    def _find_service(dev_id, svc_name):
        if dev_id not in full_service_data:
            return None
        item = full_service_data[dev_id]
        for entry in item.get("values", []) + item.get("functions", []):
            if entry["id"] == svc_name:
                return json.loads(json.dumps(entry))
        return None

    def _resolve_enum(svc_entry, enums_map):
        svc_entry = json.loads(json.dumps(svc_entry))
        for arg in svc_entry.get("arguments", []):
            if arg.get("type") == "ENUM" and "format" in arg:
                arg["enum_list"] = enums_map.get(arg["format"], [])
        if svc_entry.get("type") == "ENUM" and "format" in svc_entry:
            svc_entry["enum_list"] = enums_map.get(svc_entry["format"], [])
        return svc_entry

    extracted = {}
    dev_to_services = defaultdict(list)
    for s_pair in selected_services:
        if '.' in s_pair:
            dev, svc = s_pair.split('.', 1)
            dev_to_services[dev].append(svc.replace("()", ""))

    for dev_name, selected_svcs in dev_to_services.items():
        if dev_name not in full_service_data:
            continue
        enums_map = full_service_data[dev_name].get("enums_map", {})
        extracted[dev_name] = {}

        for svc_name in selected_svcs:
            svc_info = _find_service(dev_name, svc_name)
            if svc_info is None:
                for sec in SECONDARY_CATS:
                    svc_info = _find_service(sec, svc_name)
                    if svc_info is not None:
                        enums_map = {**enums_map, **full_service_data[sec].get("enums_map", {})}
                        break
            if svc_info is None:
                continue

            svc_info = _resolve_enum(svc_info, enums_map)
            extracted[dev_name][svc_name] = svc_info

    return extracted


# "볼륨 10 높여줘" -> Need Volume value
_VALUE_SERVICE_MAP = {
    "SetSpinSpeed": "SpinSpeed", "SetVolume": "Volume", "SetChannel": "Channel",
    "MoveToBrightness": "CurrentBrightness", "MoveToLevel": "CurrentLevel",
}

def inject_value_service(selected_services):
    for s in list(selected_services):
        if '.' not in s:
            continue
        dev, svc = s.split('.', 1)
        if svc in _VALUE_SERVICE_MAP:
            companion = f"{dev}.{_VALUE_SERVICE_MAP[svc]}"
            if companion not in selected_services:
                selected_services.append(companion)
    return selected_services


# SERVICE_DATA 순회 -> { 서비스명: 카테고리 } 역방향 맵.
# Sub-skill 카테고리(Switch / LevelControl / ColorControl / RotaryControl)가
# primary 매핑을 덮어써 공유 서비스명이 sub-skill prefix로 해석되게 한다.
def _build_service_category_map(service_data):
    mapping = {}
    for cat, item in service_data.items():
        if cat not in SUB_SKILL_TAGS:
            for entry in item.get("values", []) + item.get("functions", []):
                svc = entry["id"]
                if svc not in mapping:
                    mapping[svc] = cat
    for cat in SUB_SKILL_TAGS:
        if cat in service_data:
            for entry in service_data[cat].get("values", []) + service_data[cat].get("functions", []):
                mapping[entry["id"]] = cat
    return mapping

_SERVICE_CATEGORY_MAP = _build_service_category_map(SERVICE_DATA)

# Sub-type tag → parent category hint. 같은 서비스명이 여러 카테고리에 존재할 때 사용.
_TAG_CATEGORY_HINT = {
    "Shade": "WindowCovering",
    "Blind": "WindowCovering",
    "Curtain": "WindowCovering",
    "Window": "WindowCovering",
}

# (#Light).On() → (#Light).switch_on()
def _apply_service_prefix(script):
    def _fmt(service, selector=None):
        if selector:
            # Tags may be a device-first real id (nickname→id restore) which can
            # contain hyphens (e.g. tc0_efb00b25-259e-…); [\w-] keeps them whole.
            tags = re.findall(r'#([\w-]+)', selector)
            for tag in tags:
                if tag in SERVICE_DATA:
                    item = SERVICE_DATA[tag]
                    svc_ids = {e["id"] for e in item.get("values", []) + item.get("functions", [])}
                    if service in svc_ids:
                        cat_fmt = tag[0].lower() + tag[1:]
                        svc_fmt = service[0].lower() + service[1:]
                        return f"{cat_fmt}_{svc_fmt}"
            for tag in tags:
                hinted = _TAG_CATEGORY_HINT.get(tag)
                if hinted and hinted in SERVICE_DATA:
                    item = SERVICE_DATA[hinted]
                    svc_ids = {e["id"] for e in item.get("values", []) + item.get("functions", [])}
                    if service in svc_ids:
                        cat_fmt = hinted[0].lower() + hinted[1:]
                        svc_fmt = service[0].lower() + service[1:]
                        return f"{cat_fmt}_{svc_fmt}"
        category = _SERVICE_CATEGORY_MAP.get(service, '')
        if category:
            cat_fmt = category[0].lower() + category[1:]
            svc_fmt = service[0].lower() + service[1:]
            return f"{cat_fmt}_{svc_fmt}"
        return service[0].lower() + service[1:]

    def replace_func(m):
        return f"{m.group(1)}.{_fmt(m.group(2), m.group(1))}({m.group(3)})"
    # `#[\w-]+`: a tag can be a hyphenated real device id (device-first
    # nickname→id restore), not just a bare category like #Light.
    script = re.sub(r'((?:all|any)?\((?:#[\w-]+\s*)+\))\.([A-Z]\w+)\(([^)]*)\)', replace_func, script)

    def replace_value(m):
        return f"{m.group(1)}.{_fmt(m.group(2), m.group(1))}"
    script = re.sub(r'((?:all|any)?\((?:#[\w-]+\s*)+\))\.([A-Z]\w+)(?!\w|\()', replace_value, script)

    return script


def _normalize_script_newlines(script):
    script = re.sub(r'\{\s*', '{\n', script)
    script = re.sub(r'\s*\}', '\n}', script)
    script = re.sub(r'\}\s*', '}\n', script)
    script = re.sub(r'(\))\s+((?:all|any)?\(#)', r'\1\n\2', script)
    script = re.sub(r'\n\s*\n+', '\n', script)
    return script.strip()


# ((#X #Y)).Method → (#X #Y).Method 류 redundant paren wrap 제거.
# _apply_service_prefix / _post_process_joi_any_quantifiers 전에 호출해야 후속 regex가 매칭됨.
def _strip_selector_extra_parens(script):
    script = re.sub(r'\((all\([^)]+\)|any\([^)]+\))\)(?=\.)', r'\1', script)
    script = re.sub(r'\((\(#[^)]+\))\)(?=\.)', r'\1', script)
    return script


def _reapply_precision_quantifiers(script, selectors):
    """Re-apply any/all quantifiers the lowering LLM may have dropped.

    `selectors` is the precision stage's {service: [selector_str, ...]} map, e.g.
    {'PresenceSensor.Presence': ['any(#PresenceSensor)'], 'Switch.On': ['all(#Switch)']}.
    The device-match stage already decided the quantifier; the lowering LLM is
    only meant to copy the selector verbatim, but sometimes emits a bare
    `(#PresenceSensor)` and drops the `any`/`all`. For each quantified selector
    `Q(#tags)`, rewrite a bare `(#tags)` (not already prefixed by a quantifier)
    back to `Q(#tags)` so the device-match decision is honored deterministically.
    `q=one` selectors are bare by design and left untouched.
    """
    seen = set()
    for sel_list in (selectors or {}).values():
        for qsel in sel_list or []:
            m = re.match(r'\s*(any|all)\((#[^)]*)\)\s*$', qsel or '')
            if not m:
                continue
            q, inner = m.group(1), m.group(2)
            if (q, inner) in seen:
                continue
            seen.add((q, inner))
            bare = f'({inner})'
            # `(` not preceded by a letter → skips an already-present any(/all(.
            script = re.sub(r'(?<![A-Za-z])' + re.escape(bare),
                            f'{q}({inner})', script)
    return script


# `any(#Tag1 [#Tag2 ...]).Prop op val` → canonical `all(...).Prop op| val` 변환.
def _post_process_joi_any_quantifiers(script):
    pattern = r'any\((#\w+(?:\s+#\w+)*)\)\.(\w+)\s*([=!<>]=|[<>])\s*("[^"]*"|[^\s)]+)'

    def replacer(match):
        tags = match.group(1)
        prop = match.group(2)
        op = match.group(3)
        val = match.group(4).strip()
        if op.endswith('|'):
            return match.group(0)
        return f'all({tags}).{prop} {op}| {val}'

    return re.sub(pattern, replacer, script)


def _parse_dict_input(val, default):
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except Exception:
            pass
    return default
