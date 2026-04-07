import time
import ast
import os
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

# Modify OpenAI's API key and API base to use llama-server's API server.
openai_api_key = "EMPTY"
openai_api_base = os.environ.get("LLM_BASE_URL", "http://localhost:8002/v1")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_LIST_PATH = os.path.join(_BASE_DIR, "files/service_list_ver2.0.3.json")
try:
    with open(SERVICE_LIST_PATH, 'r', encoding='utf-8') as f:
        SERVICE_DATA = json.load(f)
except FileNotFoundError:
    print(f"Warning: {SERVICE_LIST_PATH} not found.")
    SERVICE_DATA = {}

def run_llm_inference(model, client, inference_type, messages, debug=False):
    # Inference
    start_inference = time.perf_counter()
    stream = client.chat.completions.create(
        messages=messages,
        model=model,
        temperature=0.1,
        max_tokens=512,
        stream=True,
        stream_options={"include_usage": True},
        extra_body={"chat_template_kwargs": {"enable_thinking": False}}
    )
    chunks = []
    usage = None
    for chunk in stream:
        if chunk.usage:
            usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta.content:
            chunks.append(chunk.choices[0].delta.content)
    elapsed = time.perf_counter() - start_inference
    content = "".join(chunks)

    if debug:
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        decode_tps = completion_tokens / elapsed if elapsed > 0 and completion_tokens else 0
        print(f"➡️ {inference_type}({prompt_tokens}) | Decode: {decode_tps:.1f} t/s | Total: {elapsed:.4f}s")
        print("===================================================")
        print(content)

    return content.strip()

def _load_all_prompts(base_dir):
    prompts = {}
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith(".md"):
                prompts[f[:-3]] = open(os.path.join(root, f), "r", encoding='utf-8').read()
    return prompts


# Intent Result (Device.Service) -> Service List (full_service_data) -> Extract Details (Type, Parameter, etc.)
# 1. Find service description in full service list
# 2. If ENUM parameter is missing -> Fill with other ENUM pools of the device
def extract_service_details(selected_services, full_service_data):
    """Intent Result (Device.Service) → Service List → Extract Details (Type, Parameter, etc.)"""
    SECONDARY_CATS = ["LevelControl", "ColorControl", "Switch"]

    extracted = {}
    dev_to_services = defaultdict(list)
    for s_pair in selected_services:
        if '.' in s_pair:
            dev, svc = s_pair.split('.', 1)
            dev_to_services[dev].append(svc.replace("()", ""))

    for dev_name, selected_svcs in dev_to_services.items():
        if dev_name not in full_service_data:
            continue
        dev_info = full_service_data[dev_name]

        # Collect all available ENUM descriptors from this device (for fallback)
        pool_enums = [
            s["enums_descriptor"] for s in dev_info.values()
            if isinstance(s.get("enums_descriptor"), list) and s["enums_descriptor"]
        ]
        extracted[dev_name] = {}

        for svc_name in selected_svcs:
            # Search: primary device first, then secondary categories
            svc_info = None
            lookup_sources = [dev_info] + [
                full_service_data[c] for c in SECONDARY_CATS if c in full_service_data
            ]
            for source in lookup_sources:
                if svc_name in source:
                    svc_info = json.loads(json.dumps(source[svc_name]))  # deep copy
                    break
            if not svc_info:
                continue

            # Fill missing ENUM bounds for function arguments
            if (svc_info.get("type") == "function"
                    and "ENUM" in svc_info.get("argument_type", "")
                    and not isinstance(svc_info.get("argument_bounds"), list)):
                base = svc_name.replace("Set", "")
                if base in dev_info and isinstance(dev_info[base].get("enums_descriptor"), list):
                    svc_info["enum_list"] = dev_info[base]["enums_descriptor"]
                elif pool_enums:
                    svc_info["enum_list"] = pool_enums[0]

            # Fill missing ENUM descriptors for value returns
            if (svc_info.get("return_type") == "ENUM"
                    and not isinstance(svc_info.get("enums_descriptor"), list)
                    and pool_enums):
                svc_info["enums_descriptor"] = pool_enums[0]

            extracted[dev_name][svc_name] = svc_info

    return extracted


# Map action → state-reading counterpart (auto-inject for incremental commands)
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

# 0. Parse the specification of the Original category (ex. Light, AirConditioner, etc.).
def _post_process_joi_any_quantifiers(script):
    # Pattern to match: any(#Tag).Property OP Value
    # OP can be ==, !=, >=, <=, >, <, :=
    # This converts it to: all(#Tag).Property OP| Value
    pattern = r'any\(#(\w+)\)\.(\w+)\s*([=!<>:]=|[<>])\s*([^)\n{}|]+)'
    
    def replacer(match):
        tag = match.group(1)
        prop = match.group(2)
        op = match.group(3)
        val = match.group(4).strip()
        # Ensure we don't double-pipe if it's already there (though the regex [^|] prevents this mostly)
        if op.endswith('|'): return match.group(0)
        return f'all(#{tag}).{prop} {op}| {val}'

    processed = re.sub(pattern, replacer, script)
    return processed

# 1. Parse the specification of the Original category (ex. Light, AirConditioner, etc.).
# 2. Merge the specifications of the Secondary categories (ex. Switch, LevelControl, etc.) included in the corresponding Primary device.
# 3. In the case of Light, if used together with LevelControl or ColorControl, filter out redundant services (ex. CurrentBrightness) to reduce token waste.
def _build_service_category_map(service_data):
    """Build {service_name: category} map. Secondary categories override primary."""
    SECONDARY = {'Switch', 'LevelControl', 'ColorControl'}
    mapping = {}
    for cat, services in service_data.items():
        if cat not in SECONDARY:
            for svc in services:
                if svc not in mapping:
                    mapping[svc] = cat
    for cat in SECONDARY:
        if cat in service_data:
            for svc in service_data[cat]:
                mapping[svc] = cat
    return mapping

_SERVICE_CATEGORY_MAP = _build_service_category_map(SERVICE_DATA)

# Service category map prefix resolver
_SERVICE_CATEGORY_MAP = _build_service_category_map(SERVICE_DATA)

def _apply_service_prefix(script):
    """(#Light).On() -> (#Light).switch_on()  /  (#Light).Switch -> (#Light).switch_switch"""
    def _fmt(service, selector=None):
        # 1st priority: resolve category from selector tags (e.g. #TemperatureSensor)
        if selector:
            tags = re.findall(r'#(\w+)', selector)
            for tag in tags:
                if tag in SERVICE_DATA and service in SERVICE_DATA[tag]:
                    cat_fmt = tag[0].lower() + tag[1:]
                    svc_fmt = service[0].lower() + service[1:]
                    return f"{cat_fmt}_{svc_fmt}"
        # 2nd priority: fallback to global map
        category = _SERVICE_CATEGORY_MAP.get(service, '')
        if category:
            cat_fmt = category[0].lower() + category[1:]
            svc_fmt = service[0].lower() + service[1:]
            return f"{cat_fmt}_{svc_fmt}"
        return service[0].lower() + service[1:]

    # 1. Function calls: (#Light).On(args)
    def replace_func(m):
        return f"{m.group(1)}.{_fmt(m.group(2), m.group(1))}({m.group(3)})"
    script = re.sub(r'((?:all|any)?\((?:#\w+\s*)+\))\.([A-Z]\w+)\(([^)]*)\)', replace_func, script)

    # 2. Value references: (#Light).Switch (not followed by '(')
    def replace_value(m):
        return f"{m.group(1)}.{_fmt(m.group(2), m.group(1))}"
    script = re.sub(r'((?:all|any)?\((?:#\w+\s*)+\))\.([A-Z]\w+)(?!\w|\()', replace_value, script)

    return script

def _normalize_script_newlines(script):
    """각 JoI 문장/블록 사이에 \n이 확실히 들어가도록 정규화.
    script 필드 값(이미 언이스케이프된 문자열)에만 적용."""
    # 1. { 뒤에 개행 보장 (중복 방지)
    script = re.sub(r'\{\s*', '{\n', script)
    # 2. } 앞에 개행 보장 및 뒤에 개행 보장
    script = re.sub(r'\s*\}', '\n}', script)
    script = re.sub(r'\}\s*', '}\n', script)
    # 3. 문장 사이 개행 보장: ) (#Device) -> ) \n (#Device)
    script = re.sub(r'(\))\s+((?:all|any)?\(#)', r'\1\n\2', script)
    # 4. 연속된 개행을 하나로 합침 (공백 포함)
    script = re.sub(r'\n\s*\n+', '\n', script)
    return script.strip()

def _parse_dict_input(val, default):
    if isinstance(val, dict): return val
    if isinstance(val, str):
        try: return ast.literal_eval(val)
        except Exception: pass
    return default

def warmup(debug=False, base_url=None):
    """서버 시작 후 모든 system prompt를 미리 캐싱"""
    client = OpenAI(api_key=openai_api_key, base_url=base_url or openai_api_base)
    model = client.models.list().data[0].id
    prompts = _load_all_prompts(os.path.join(_BASE_DIR, "files"))

    prompts.pop("connect_service_summary", None)
    print(f"[warmup] Caching {len(prompts)} prompts...")
    start = time.perf_counter()
    for name, prompt in prompts.items():
        try:
            user_content = "hi"
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=1,
                temperature=0.0,
                stream=False,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}}
            )
            if debug:
                print(f"[warmup] cached: {name}")
        except Exception as e:
            print(f"[warmup] failed: {name} ({e})")
    print(f"[warmup] Done in {time.perf_counter() - start:.2f}s")

def generate_joi_code(sentence, connected_devices, other_params, model=None, current_time=None, modification=None, debug=False, base_url=None):
    # 1. Parse Inputs - dict type
    connected_devices = _parse_dict_input(connected_devices, None)
    other_params = _parse_dict_input(other_params, {})

    # 2. Setup Client
    start = time.perf_counter()
    # OpenAI Library
    client = OpenAI(api_key=openai_api_key, base_url=base_url or openai_api_base)
    models = client.models.list()
    model = models.data[0].id

    prompts = _load_all_prompts(os.path.join(_BASE_DIR, 'files'))

    # Helper: single-line LLM call (captures model, client, prompts, debug)
    def infer(key, user_input, *, system=None):
        sys_content = system or prompts.get(key, "")
        return run_llm_inference(model, client, key, [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_input}
        ], debug=debug)

    # ❇️ Stage 0: Command Merge (original + modification)
    merged_command = sentence
    if modification:
        merge_raw = infer("command_merge", f"Original: {sentence}\nModification: {modification}")
        if "</Reasoning>" in merge_raw:
            merged_command = merge_raw.split("</Reasoning>")[-1].strip()
        else:
            merged_command = merge_raw.strip()
        sentence = merged_command

    # ❇️ Stage 1: Translation (KOR -> ENG)
    first_word = sentence.strip().split()[0] if sentence.strip() else ""
    if re.search("[가-힣]", first_word):
        sentence = infer("translation", sentence)

    def run_mapping():
        if not isinstance(connected_devices, dict) or not connected_devices:
            raise ValueError("No connected devices provided. IoT mapping requires a device list.")
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

        # ❇️ Stage 2-1: Mapping Category
        exclude_categories = {"Switch", "RotaryControl", "ColorControl", "LevelControl"}
        exposed_categories = [c for c in valid_categories if c not in exclude_categories]
        
        # Build category-to-tags summary for Stage 1 to support tag-based mapping
        cat_tags_summary = {}
        for info in cd_simple.values():
            for cat in info["category"]:
                if cat in exclude_categories: continue
                if cat not in cat_tags_summary:
                    cat_tags_summary[cat] = set()
                cat_tags_summary[cat].update(info["tags"])
        cat_tags_summary = {k: sorted(list(v)) for k, v in cat_tags_summary.items()}

        category_input = f"[Available Devices (Category: Tags)]\n{json.dumps(cat_tags_summary, indent=2, ensure_ascii=False)}\n\n[Command]\n{sentence}"
        cat_output = infer("connect_mapping_category", category_input)
        clean_cat = re.sub(r'```(?:json)?\s*', '', cat_output).strip()
        try:
            extracted_categories = json.loads(clean_cat)
            if isinstance(extracted_categories, list):
                extracted_categories = {k: "Identify relevant services" for k in extracted_categories}
            elif not isinstance(extracted_categories, dict):
                extracted_categories = {}
        except Exception:
            extracted_categories = {}

        # Filter by valid_categories to prevent hallucinations
        extracted_categories = {k: v for k, v in extracted_categories.items() if k in valid_categories}

        # ❇️ Stage 2-2: Mapping Intent (Per Device)
        raw_selected_services = []
        for dev, assigned_task in extracted_categories.items():
            device_rules = prompts.get(f"device_rules_{dev.lower()}", "")
            
            # Identify sub-categories attached to this main device (e.g., Switch, ColorControl)
            sub_cats = set()
            for info in cd_simple.values():
                cats = info.get("category", [])
                if dev in cats:
                    for c in cats:
                        if c in exclude_categories: sub_cats.add(c)
                
            for sub_cat in sub_cats:
                sub_rule = prompts.get(f"device_rules_{sub_cat.lower()}", "")
                if sub_rule:
                    # Safely map all SubCat (e.g., Switch) references to MainCat (e.g., Speaker)
                    sub_rule = re.sub(rf'\b{sub_cat}\b', dev, sub_rule, flags=re.IGNORECASE)
                    device_rules += f"\n\n--- Sub-Component: {sub_cat} ---\n{sub_rule}"
            
            sys_prompt = f"{prompts.get('connect_mapping_service_common', '')}\n\n{device_rules}"
            if debug:
                print(f"--- Final [intent_{dev.lower()}] System Prompt ---")
                print(sys_prompt)
                print("-------------------------------------------------")
            
            dev_input = f"[Command]\n{sentence}\n\n[Assigned Task for {dev}]\n{assigned_task}"
            dev_output = infer(f"intent_{dev.lower()}", dev_input, system=sys_prompt)
            clean_dev = re.sub(r'```(?:json)?\s*', '', dev_output).strip()
            try:
                srv_list = json.loads(clean_dev)
                if isinstance(srv_list, list):
                    raw_selected_services.extend(srv_list)
            except Exception:
                pass
        
        # Eliminate duplicates
        selected_services = []
        for s in raw_selected_services:
            if s not in selected_services:
                selected_services.append(s)

        inject_value_service(selected_services)
        local_service_details = extract_service_details(selected_services, SERVICE_DATA)
        
        # Validate Formats
        format_errors = []
        not_found_errors = []
        for s in selected_services:
            if '.' not in s:
                format_errors.append(s)
                continue
            device_name, service_name = s.split('.', 1)
            service_name = service_name.replace("()", "")
            if device_name not in valid_categories or service_name not in local_service_details.get(device_name, {}):
                not_found_errors.append(s)

        # ❇️ Mapping Precision + Quantifier (merged)
        intent_categories = list(set(s.split('.')[0] for s in selected_services if '.' in s))
        if not intent_categories:
            raise ValueError(f"No services found for the command: '{sentence}'. Category/Intent mapping failed.")

        precision_input = f"[Command]\n{sentence}\n[Intent]\n{json.dumps(intent_categories, indent=2, ensure_ascii=False)}\n[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}"
        precision_output = infer("connect_mapping_precision", precision_input)

        # Pass the full precision output (including <Reasoning>) to JoI generation for better context
        step2_selectors = precision_output.strip()

        local_services = f"[Service Tagging]\n{step2_selectors}\n\n[Service Details]\n{json.dumps(local_service_details, indent=2, ensure_ascii=False)}"

        return local_services, intent_categories, local_service_details

    def run_router():
        # ❇️ Phase 1: Condition Filter
        filter_output = infer("filter", sentence)
        cmd_type = "UNKNOWN"
        conclusion = ""

        # ❇️ Phase 2: Condition Extractor
        if "true" in filter_output.lower():
            extractor_output = infer("extractor", sentence)
            if extractor_output:
                conclusion = extractor_output.strip()

            # ❇️ Phase 3: Classifier (NO_SCHEDULE / SCHEDULED / DURATION)
            if conclusion:
                classifier_output = infer("router", f"[Command]\n{sentence}\n\n[Extractor Analysis]\n{conclusion}")
                
                try:
                    # Find JSON block in the classifier output
                    match = re.search(r'\{.*\}', classifier_output, re.DOTALL)
                    if match:
                        cat_data = json.loads(match.group())
                        cmd_type = cat_data.get("type", "UNKNOWN")
                    else:
                        if "NO_SCHEDULE" in classifier_output: cmd_type = "NO_SCHEDULE"
                        elif "SCHEDULED" in classifier_output: cmd_type = "SCHEDULED"                        
                        elif "DURATION" in classifier_output: cmd_type = "DURATION"
                except:
                    pass
        else:
            cmd_type = "NO_SCHEDULE"
            conclusion = "Sequential action composition."
            
        return cmd_type, conclusion

    # 5. Execute Parallel Tasks (Mapping & Routing)
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_mapping = executor.submit(run_mapping)
        f_router = executor.submit(run_router)
        services, mapped_devices, service_details = f_mapping.result()
        cmd_type, router_conclusion = f_router.result()

    # 6. Joi Generation Branching
    type_to_prompt_key = {
        "NO_SCHEDULE": "joi_no_schedule",
        "SCHEDULED": "joi_scheduled",
        "DURATION": "joi_duration"
    }

    # Fallback to SCHEDULED if unknown type
    base_prompt_key = type_to_prompt_key.get(cmd_type, "joi_scheduled")
    prompt_key = f"connect_{base_prompt_key}"
    
    # Prepare System Prompt
    system_prompt = prompts.get(prompt_key, "")
    
    # ❇️ JoI Code Generation
    if cmd_type == "NO_SCHEDULE":
        joi_input = f"[Command]\n{sentence}\n\n[Services]\n{services}"
    else:
        joi_input = f"[Command]\n{sentence}\n\n[Extractor Analysis]\n{router_conclusion}\n\n[Services]\n{services}"
    joi_code_raw = infer(prompt_key, joi_input, system=system_prompt)

    # Post-processing: strip reasoning and standardize output format
    reasoning_match = re.search(r'<Reasoning>(.*?)</Reasoning>', joi_code_raw, re.DOTALL)
    code_plan = reasoning_match.group(1).strip() if reasoning_match else ""
    script = re.sub(r'<Reasoning>.*?</Reasoning>', '', joi_code_raw, flags=re.DOTALL).strip()
    script = _apply_service_prefix(script)
    script = _post_process_joi_any_quantifiers(script)

    if cmd_type == "NO_SCHEDULE":
        # NO_SCHEDULE: LLM returns raw code, wrap it in JSON
        joi_json = {
            "cron": "",
            "period": 0,
            "script": _normalize_script_newlines(script)
        }
        joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
    else:
        # SCHEDULED/DURATION: LLM returns JSON
        # Pre-process literal newlines in "script" string before parsing
        match = re.search(r'"script"\s*:\s*"(.*?)"\s*\}', script, re.DOTALL)
        if match:
            fixed_inner = match.group(1).replace('\n', '\\n')
            script = script[:match.start(1)] + fixed_inner + script[match.end(1):]
            
        try:
            joi_json = json.loads(script)
            if "script" in joi_json:
                joi_json["script"] = _normalize_script_newlines(joi_json["script"])
            joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            joi_code_raw = script

    elapsed = time.perf_counter() - start
    # print(f"\nJoI ➡️ {elapsed:.4f} secs")

    # ❇️ Korean Reconversion
    translated_sentence = ""
    try:
        kor_plan = f"\n\n[Code Plan]\n{code_plan}" if code_plan else ""
        kor_input = f"[Code]\n{joi_code_raw}{kor_plan}\n\n[Service Descriptions]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
        translated_sentence = infer("re_translate", kor_input)
    except Exception as e:
        print(f"Re-translation failed: {e}")

    # ❇️ Korean Re-translation (ENG -> KOR)
    translated_sentence_kor = ""
    if translated_sentence:
        try:
            translated_sentence_kor = infer("re_translate_kor", translated_sentence)
        except Exception as e:
            print(f"Korean re-translation failed: {e}")

    return {
        "code": joi_code_raw,
        "merged_command": merged_command,
        "log": {
            "response_time": f"{elapsed:.4f} seconds",
            "inference_time": f"{elapsed:.4f} seconds",
            "translated_sentence": re.sub(r'["""\'\'\'.,!?。、！？]', '', translated_sentence_kor or translated_sentence).strip(),
            "mapped_devices": mapped_devices,
        }
    }


# ═══════════════════════════════════════════════════════════
# Agent Chat — Qwen tool-calling 기반 IoT 어시스턴트
# ═══════════════════════════════════════════════════════════

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "request_to_joi_llm",
            "description": (
                "Send a natural-language IoT command to the JOI code generator. "
                "Use this when the user asks to create a scenario or automate IoT devices."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sentence": {
                        "type": "string",
                        "description": "Natural language command, e.g. 'turn on living room lights at 9am'"
                    }
                },
                "required": ["sentence"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "feedback_to_joi_llm",
            "description": (
                "Process user feedback on previously generated JOI code. "
                "'y' = approve, 'n' = reject, or free text = modification request."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feedback": {
                        "type": "string",
                        "description": "'y' to approve, 'n' to reject, or modification text"
                    }
                },
                "required": ["feedback"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_scenario",
            "description": "Register the approved JOI scenario to the Hub Controller and start it.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_connected_devices",
            "description": "Get the list of currently connected IoT devices with their status and services.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]

AGENT_SYSTEM_PROMPT = """You are JoI, an IoT assistant that helps users control smart home devices and create automation scenarios.

## Strict Conversational Guidelines
- **IoT Only**: You MUST explicitly and politely reject any queries that are NOT related to IoT control or smart home scenarios. (e.g. weather, general knowledge). Do NOT attempt to answer them or use tool calls.
- Always respond in the same language as the user.
- Never guess device states — use `get_connected_devices` if needed.
- Do not retry automatically on error — inform the user.
- Handle one task at a time.

## Chain of Thought (Thinking before acting)
- **CRITICAL**: Before invoking ANY tool or writing a final response, you MUST first write your thought process inside `<think>` and `</think>` tags.
- Inside `<think>`, evaluate what the user wants, check if you have an appropriate tool, and plan your next action.
- ONLY call a tool if it directly solves the user's request. If you do not have a suitable tool (e.g., to list existing scenarios), do NOT call an unrelated tool (like `get_connected_devices`). Instead, explain your limitations to the user directly after the `</think>` tag.

## Your capabilities (via tool calls)
- **request_to_joi_llm**: Generate JOI scenario code from a natural language command.
- **feedback_to_joi_llm**: Process user feedback ('y'=approve, 'n'=reject, or modification text) on generated code.
- **add_scenario**: Register an approved scenario to the Hub Controller.
- **get_connected_devices**: Retrieve the list of connected IoT devices.

## Strict Workflow for IoT commands
1. User gives an IoT command → `<think>` evaluation `</think>` → call `request_to_joi_llm`.
2. Present the `translated_sentence` from the result and ask explicitly: "이 시나리오가 맞나요? (y/n/수정사항)"
3. Wait for user feedback. When they reply, YOU MUST `<think>` about it `</think>` → call `feedback_to_joi_llm` FIRST to process the feedback.
4. If the feedback tool returns "approved" → call `add_scenario` to register it.
5. If the feedback tool returns "rejected" → inform the user it was cancelled.
"""

MAX_AGENT_ROUNDS = 5


def _execute_agent_tool(tool_name, tool_args, agent_state):
    """Execute a tool call and return the result dict."""
    connected_devices = agent_state.get("connected_devices", {})
    base_url = agent_state.get("base_url")

    def _summarize_result(result):
        """Tool result를 agent context에 넣을 최소 정보만 추출."""
        return {
            "status": result.get("status", ""),
            "translated_sentence": result.get("log", {}).get("translated_sentence", ""),
            "response_time": result.get("log", {}).get("response_time", ""),
        }

    if tool_name == "request_to_joi_llm":
        result = generate_joi_code(
            sentence=tool_args["sentence"],
            connected_devices=connected_devices,
            other_params={},
            base_url=base_url,
        )
        agent_state["last_result"] = result
        summary = _summarize_result(result)
        summary["status"] = "confirmation_needed"
        return summary

    elif tool_name == "feedback_to_joi_llm":
        feedback = tool_args["feedback"].strip().lower()
        last = agent_state.get("last_result", {})

        if feedback in ("y", "yes"):
            last["status"] = "approved"
            agent_state["last_result"] = last
            return {"status": "approved", "message": "User approved. Ready to register via add_scenario."}

        elif feedback in ("n", "no"):
            agent_state["last_result"] = None
            return {"status": "rejected", "message": "User rejected. Task terminated and context cleared."}

        else:
            original_sentence = last.get("merged_command", "")
            result = generate_joi_code(
                sentence=original_sentence,
                connected_devices=connected_devices,
                other_params={},
                modification=feedback,
                base_url=base_url,
            )
            agent_state["last_result"] = result
            summary = _summarize_result(result)
            summary["status"] = "confirmation_needed"
            return summary

    elif tool_name == "add_scenario":
        last = agent_state.get("last_result", {})
        code_raw = last.get("code", "")
        if isinstance(code_raw, str):
            try:
                code = json.loads(code_raw)
            except json.JSONDecodeError:
                return {"error": f"Failed to parse code: {code_raw[:100]}"}
        else:
            code = code_raw
        if isinstance(code, list):
            code = code[0]

        import uuid
        scenario_name = code.get("name", "Scenario")
        if "Scenario" in scenario_name:
            scenario_name += f"_{uuid.uuid4().hex[:3]}"

        scenario = {
            "name": scenario_name,
            "cron": code.get("cron", ""),
            "period_in_msec": code.get("period", -1),
            "script": code.get("script") or code.get("code", ""),
            "command": last.get("log", {}).get("translated_sentence", ""),
        }

        hub_url = os.getenv("HUB_CONTROLLER_URL", "")
        if not hub_url:
            return {
                "status": "registered_locally",
                "scenario": scenario,
                "message": "No HUB_CONTROLLER_URL configured. Scenario prepared but not sent.",
            }

        # Synchronous HTTP to Hub Controller
        import urllib.request
        hub_token = os.getenv("HUB_AUTH_TOKEN", "")
        headers = {"Content-Type": "application/json"}
        if hub_token:
            headers["Authorization"] = f"Bearer {hub_token}"
        req = urllib.request.Request(
            f"{hub_url}/user/scenarios/",
            data=json.dumps(scenario).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode())
                return {
                    "status": "scenario_created",
                    "scenario": resp_data,
                    "message": f"Scenario '{resp_data.get('name', scenario_name)}' registered and started.",
                }
        except Exception as e:
            return {"error": f"Hub Controller request failed: {e}"}

    elif tool_name == "get_connected_devices":
        if connected_devices:
            return {"connected_devices": connected_devices}
        return {"connected_devices": {}, "message": "No devices currently connected."}

    return {"error": f"Unknown tool: {tool_name}"}


def agent_chat(user_message, connected_devices=None, base_url=None, debug=False, chat_history=None, agent_state=None):
    """
    Qwen tool-calling agent (multi-turn with state mapping).

    Args:
        user_message: 사용자 메시지
        connected_devices: 연결된 IoT 디바이스 정보 dict
        base_url: vLLM 서버 URL (None이면 기본값)
        debug: 디버그 출력
        chat_history: list of previous conversation turns
        agent_state: dict carrying operational state across turns

    Returns:
        {"response": str, "chat_history": list, "agent_state": dict, "last_result": dict}
    """
    client = OpenAI(api_key=openai_api_key, base_url=base_url or openai_api_base)
    model = client.models.list().data[0].id

    if chat_history is None:
        chat_history = []
    if agent_state is None:
        agent_state = {
            "connected_devices": _parse_dict_input(connected_devices, {}),
            "base_url": base_url,
            "last_result": None,
        }

    # Sliding window (take last 6 messages) to avoid token limit
    truncated_history = chat_history[-6:] if len(chat_history) > 6 else chat_history

    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": user_message})

    final_response = ""

    for _round in range(MAX_AGENT_ROUNDS):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=1024,
            stream=False,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

        msg = response.choices[0].message

        # --- Fallback for models (like 30B) that output raw <tool_call> tags in content ---
        parsed_tool_calls = msg.tool_calls if getattr(msg, "tool_calls", None) else []
        if not parsed_tool_calls and msg.content and "<tool_call>" in msg.content:
            tc_match = re.search(r'<tool_call>\s*({.*?})\s*</tool_call>', msg.content, re.DOTALL)
            if tc_match:
                try:
                    tc_json = json.loads(tc_match.group(1))
                    import uuid
                    from types import SimpleNamespace
                    func_obj = SimpleNamespace(name=tc_json["name"], arguments=json.dumps(tc_json.get("arguments", {})))
                    parsed_tool_calls = [SimpleNamespace(id=f"call_{uuid.uuid4().hex[:8]}", type="function", function=func_obj)]
                    msg.content = msg.content.replace(tc_match.group(0), "").strip()
                except Exception:
                    pass
        # ----------------------------------------------------------------------------------

        assistant_entry = {"role": "assistant", "content": msg.content or ""}
        if parsed_tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in parsed_tool_calls
            ]
        messages.append(assistant_entry)

        if not parsed_tool_calls:
            final_response = msg.content or ""
            break

        for tc in parsed_tool_calls:
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            if debug:
                print(f"[Tool call] {tc.function.name}({tool_args})")

            tool_result = _execute_agent_tool(tc.function.name, tool_args, agent_state)

            if debug:
                print(f"[Tool result] {json.dumps(tool_result, ensure_ascii=False)[:200]}")

            messages.append({
                "role": "tool",
                "content": json.dumps(tool_result, ensure_ascii=False),
                "tool_call_id": tc.id,
            })
    else:
        final_response = messages[-1].get("content", "") if messages else ""

    # Exclude the system prompt to keep cleanly for the next run
    return {
        "response": final_response, 
        "chat_history": messages[1:], 
        "agent_state": agent_state, 
        "last_result": agent_state.get("last_result")
    }
