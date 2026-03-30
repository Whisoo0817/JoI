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
SERVICE_LIST_PATH = os.path.join(_BASE_DIR, "files/service_list_ver2.0.1.json")
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
    ttft = None
    for chunk in stream:
        if chunk.usage:
            usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta.content:
            if ttft is None:
                ttft = time.perf_counter() - start_inference
            chunks.append(chunk.choices[0].delta.content)
    elapsed = time.perf_counter() - start_inference
    content = "".join(chunks)

    if debug:
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        decode_time = elapsed - ttft if ttft else elapsed
        prefill_tps = prompt_tokens / ttft if ttft and prompt_tokens else 0
        decode_tps = completion_tokens / decode_time if decode_time > 0 and completion_tokens else 0
        print(f"➡️ {inference_type} | Prefill: {prompt_tokens}tok/{ttft:.4f}s ({prefill_tps:.1f} t/s) | Decode: {completion_tokens}tok/{decode_time:.4f}s ({decode_tps:.1f} t/s) | Total: {elapsed:.4f}s")
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
    extracted = {}
    dev_to_services = defaultdict(list)
    for s_pair in selected_services:
        if '.' in s_pair:
            dev, svc = s_pair.split('.', 1)
            dev_to_services[dev].append(svc.replace("()", ""))
            
    for dev_name, selected_svcs in dev_to_services.items():
        if dev_name not in full_service_data: continue
        full_dev_info = full_service_data[dev_name]
        
        pool_enums = [s.get("enums_descriptor") for s in full_dev_info.values() if isinstance(s.get("enums_descriptor"), list) and s.get("enums_descriptor")]
        extracted[dev_name] = {}
        
        for s_name in selected_svcs:
            s_info = next((json.loads(json.dumps(data[s_name])) for cat, data in [("Primary", full_dev_info)] + [(c, full_service_data[c]) for c in ["LevelControl", "ColorControl", "Switch", "RotaryControl"] if c in full_service_data] if s_name in data), None)
            if not s_info: continue

            # Case: Function with ENUM argument missing bounds
            if s_info.get("type") == "function" and "ENUM" in s_info.get("argument_type", "") and not isinstance(s_info.get("argument_bounds"), list):
                base_name = s_name.replace("Set", "")
                if base_name in full_dev_info and isinstance(full_dev_info[base_name].get("enums_descriptor"), list):
                    s_info["enum_list"] = full_dev_info[base_name]["enums_descriptor"]
                elif pool_enums:
                    s_info["enum_list"] = pool_enums[0]
                
            # Case: Value with ENUM return missing enums list
            if s_info.get("return_type") == "ENUM" and not isinstance(s_info.get("enums_descriptor"), list) and pool_enums:
                s_info["enums_descriptor"] = pool_enums[0]

            extracted[dev_name][s_name] = s_info
            
    return extracted

# Auto-inject state reading services (e.g., CurrentBrightness) for incremental commands (e.g., MoveToBrightness).
def inject_value_service(selected_services):
    reading_service_map = {"SetSpinSpeed": "SpinSpeed", "SetVolume": "Volume", "SetChannel": "Channel", "MoveToBrightness": "CurrentBrightness", "MoveToLevel": "CurrentLevel"}
    additions = [f"{s.split('.')[0]}.{reading_service_map[s.split('.')[1]]}" for s in selected_services if '.' in s and s.split('.')[1] in reading_service_map]
    for a in additions:
        if a not in selected_services:
            selected_services.append(a)
    return selected_services

# 1. Parse the specification of the Original category (ex. Light, AirConditioner, etc.).
# 2. Merge the specifications of the Secondary categories (ex. Switch, LevelControl, etc.) included in the corresponding Primary device.
# 3. In the case of Light, if used together with LevelControl or ColorControl, filter out redundant services (ex. CurrentBrightness) to reduce token waste.
def parse_service_summary(connected_devices_info, summary_file_path):
    SECONDARY_CATEGORIES = ['LevelControl', 'ColorControl', 'Switch', 'RotaryControl']
    
    try:
        with open(summary_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {summary_file_path}: {e}")
        return ""

    # Parse devices
    pattern = r'<Device\s+(?:name=)?\"([^\"]+)\">\s*(.*?)\s*</Device>'
    matches = re.finditer(pattern, content, re.DOTALL)
    cat_to_content = {m.group(1).strip(): m.group(2).strip() for m in matches}
    
    # Identify if there is a secondary category in the primary category
    hierarchy = defaultdict(set)
    all_categories = set()
    for info in connected_devices_info.values():
        cats = info.get('category', [])
        if isinstance(cats, str): cats = [cats]                
        tags = info.get('tags', [])
        cats.extend(t for t in tags if t in SECONDARY_CATEGORIES and t not in cats)
        all_categories.update(cats)
        
        prims = [c for c in cats if c not in SECONDARY_CATEGORIES]
        secs = [c for c in cats if c in SECONDARY_CATEGORIES]
        for p in prims: hierarchy[p].update(secs)
    
    # Generate result
    parsed_summary = ""
    
    # 1. Process Primary categories (including Secondary)
    for cat in sorted(all_categories - set(SECONDARY_CATEGORIES)):
        if cat in cat_to_content:
            section_content = cat_to_content[cat]
            h_set = hierarchy.get(cat, set())
            
            # Filtering obsolete metrics from Light
            if cat == "Light":
                lines = section_content.split('\n')
                if "LevelControl" in h_set: lines = [l for l in lines if 'CurrentBrightness' not in l and 'MoveToBrightness' not in l]
                if "ColorControl" in h_set: lines = [l for l in lines if 'CurrentRGB' not in l and 'MoveToRGB' not in l]
                section_content = '\n'.join(lines).strip()

            # Merge Secondary categories
            for sec in sorted(h_set):
                if sec in cat_to_content: section_content += f"\n  {cat_to_content[sec]}"
            parsed_summary += f'<Device "{cat}">\n  {section_content}\n</Device>\n\n'

    # 2. Process standalone Secondary categories
    used_secs = {s for secs in hierarchy.values() for s in secs}
    for sec in sorted(all_categories.intersection(SECONDARY_CATEGORIES) - used_secs):
        if sec in cat_to_content:
            parsed_summary += f'<Device "{sec}">\n  {cat_to_content[sec]}\n</Device>\n\n'
            
    return parsed_summary.strip()

def _build_service_category_map(service_data):
    """Build {service_name: category} map. Secondary categories override primary."""
    SECONDARY = {'Switch', 'LevelControl', 'ColorControl', 'RotaryControl'}
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

_CONNECT_SUMMARY_PATH = os.path.join(_BASE_DIR, 'files/connect/connect_service_summary.md')
with open(_CONNECT_SUMMARY_PATH, 'r', encoding='utf-8') as _f:
    _FULL_CONNECT_SUMMARY = _f.read()

def _apply_service_prefix(script):
    """(#Light).On() -> (#Light).switch_on()"""
    def replace(m):
        selector = m.group(1)   # e.g., "(#Light)" or "all(#Light)"
        service  = m.group(2)   # e.g., "On"
        args     = m.group(3)   # e.g., "" or "50"
        category = _SERVICE_CATEGORY_MAP.get(service, '')
        if category:
            cat_fmt = category[0].lower() + category[1:]
            svc_fmt = service[0].lower() + service[1:]
            new_svc = f"{cat_fmt}_{svc_fmt}"
        else:
            new_svc = service[0].lower() + service[1:]
        return f"{selector}.{new_svc}({args})"
    return re.sub(r'((?:all|any)?\((?:#\w+\s*)+\))\.([A-Z]\w+)\(([^)]*)\)', replace, script)

def _parse_dict_input(val, default):
    if isinstance(val, dict): return val
    if isinstance(val, str):
        try: return ast.literal_eval(val)
        except Exception: pass
    return default

def warmup(debug=False):
    """서버 시작 후 모든 system prompt를 미리 캐싱"""
    client = OpenAI(api_key=openai_api_key, base_url=openai_api_base)
    model = client.models.list().data[0].id
    prompts = _load_all_prompts(os.path.join(_BASE_DIR, "files"))

    print(f"[warmup] Caching {len(prompts)} prompts...")
    start = time.perf_counter()
    for name, prompt in prompts.items():
        try:
            if name == "connect_mapping_intent":
                user_content = f"[Service List]\n{_FULL_CONNECT_SUMMARY}\n\n[Command]\nhi"
            else:
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

def generate_joi_code(sentence, connected_devices, other_params, model=None, current_time=None, modification=None, debug=False):
    # 1. Parse Inputs - dict type
    connected_devices = _parse_dict_input(connected_devices, None)
    other_params = _parse_dict_input(other_params, {})

    # 2. Setup Client
    start = time.perf_counter()
    # OpenAI Library
    client = OpenAI(api_key=openai_api_key, base_url=openai_api_base)
    models = client.models.list()
    model = models.data[0].id

    prompts = _load_all_prompts(os.path.join(_BASE_DIR, 'files'))

    # ❇️ Stage 0: Command Merge (original + modification)
    merged_command = sentence
    if modification:
        merge_input = f"Original: {sentence}\nModification: {modification}"
        merge_raw = run_llm_inference(model, client, "command_merge", [
            {"role": "system", "content": prompts.get("command_merge", "")},
            {"role": "user", "content": merge_input}
        ], debug=debug)
        # Parse: extract final command after </Reasoning> tag
        if "</Reasoning>" in merge_raw:
            merged_command = merge_raw.split("</Reasoning>")[-1].strip()
        else:
            merged_command = merge_raw.strip()
        sentence = merged_command

    # ❇️ Stage 1: Translation (KOR -> ENG)
    # Check if the first word contains Korean
    first_word = sentence.strip().split()[0] if sentence.strip() else ""
    if re.search("[가-힣]", first_word):
        sentence = run_llm_inference(model, client, "translation", [{"role": "system", "content": prompts.get("translation", "")}, {"role": "user", "content": sentence}], debug=debug)

    def run_mapping():
        # connected_devices 있으면 필터링된 summary, 없으면 전체 summary 사용
        if isinstance(connected_devices, dict) and connected_devices:
            local_service_summary = parse_service_summary(connected_devices, _CONNECT_SUMMARY_PATH)
            valid_categories = set()
            for v in connected_devices.values():
                cats = v.get("category", [])
                if isinstance(cats, list):
                    valid_categories.update(cats)
                elif isinstance(cats, str):
                    valid_categories.add(cats)
            cd_simple = {k: {"tags": v.get("tags", [])} for k, v in connected_devices.items()}
        else:
            local_service_summary = _FULL_CONNECT_SUMMARY
            valid_categories = set(SERVICE_DATA.keys())
            cd_simple = {}

        # ❇️ Mapping Intent
        intent_input = f"[Service List]\n{local_service_summary}\n\n[Command]\n{sentence}"
        messages = [
            {"role": "system", "content": prompts.get("connect_mapping_intent", "")},
            {"role": "user", "content": intent_input}
        ]
        for attempt in range(2):  # Fail -> Retry
            intent_output = run_llm_inference(model, client, "connect_mapping_intent", messages, debug=debug)
            clean = re.sub(r'```(?:json)?\s*', '', intent_output).strip()
            selected_services = json.loads(clean)
            inject_value_service(selected_services)
            local_service_details = extract_service_details(selected_services, SERVICE_DATA)

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

            if not (format_errors or not_found_errors) or attempt == 1:
                break

            retry_checklist = []
            if format_errors:
                retry_checklist.append(f"1. [Format Error]: {format_errors} must follow 'Device.Service' format. Do not return service alone.")
            if not_found_errors:
                retry_checklist.append(f"2. [Service Not Found]: {not_found_errors} are not in the [Service List]. Use ONLY exact names from the list.")

            feedback = "I found some issues. Please follow this checklist to correct them:\n" + "\n".join(retry_checklist)
            messages.append({"role": "assistant", "content": intent_output})
            messages.append({"role": "user", "content": feedback})

        # ❇️ Mapping Precision
        intent_categories = list(set(s.split('.')[0] for s in selected_services if '.' in s))
        precision_input = f"[Command]\n{sentence}\n[Intent]\n{json.dumps(intent_categories, indent=2, ensure_ascii=False)}\n[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}"
        precision_messages = [{"role": "system", "content": prompts.get("connect_mapping_precision", "")}, {"role": "user", "content": precision_input}]
        precision_output = run_llm_inference(model, client, "connect_mapping_precision", precision_messages, debug=debug)

        # Parse selectors after </Reasoning>
        reasoning_split = re.split(r'</Reasoning>', precision_output, maxsplit=1)
        step2_selectors = reasoning_split[1].strip() if len(reasoning_split) > 1 else precision_output.strip()

        # ❇️ Quantifier (single/all/any)
        quant_input = f"[Command]\n{sentence}\n[Devices]\n{step2_selectors}"
        quant_messages = [{"role": "system", "content": prompts.get("connect_quantifier", "")}, {"role": "user", "content": quant_input}]
        quant_output = run_llm_inference(model, client, "connect_quantifier", quant_messages, debug=debug)

        local_services = f"[Service Tagging]\n{step2_selectors}\n\n[Quantifier]\n{quant_output.strip()}\n\n[Service Details]\n{json.dumps(local_service_details, indent=2, ensure_ascii=False)}"

        return local_services, intent_categories, local_service_details

    def run_router():
        # ❇️ Phase 1: Condition Filter
        filter_messages = [{"role": "system", "content": prompts.get("filter", "")}, {"role": "user", "content": sentence}]
        filter_output = run_llm_inference(model, client, "filter", filter_messages, debug=debug)
        
        cmd_type = "UNKNOWN"
        conclusion = ""

        # ❇️ Phase 2: Condition Extractor
        if "true" in filter_output.lower():
            extractor_messages = [{"role": "system", "content": prompts.get("extractor", "")}, {"role": "user", "content": sentence}]
            extractor_output = run_llm_inference(model, client, "extractor", extractor_messages, debug=debug)

            if extractor_output:
                conclusion = extractor_output.strip()

            # ❇️ Phase 3: Classifier (NO_SCHEDULE / SCHEDULED / DURATION)
            if conclusion:
                classifier_input = f"[Command]\n{sentence}\n\n[Extractor Analysis]\n{conclusion}"
                classifier_messages = [{"role": "system", "content": prompts.get("router", "")}, {"role": "user", "content": classifier_input}]
                classifier_output = run_llm_inference(model, client, "router", classifier_messages, debug=debug)
                
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
    joi_input = f"[Command]\n{sentence}\n\n[Extractor Analysis]\n{router_conclusion}\n\n[Services]\n{services}"
    if cmd_type == "NO_SCHEDULE":
        joi_input = f"[Command]\n{sentence}\n\n[Services]\n{services}"
        
    joi_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": joi_input}]
    joi_code_raw = run_llm_inference(model, client, prompt_key, joi_messages, debug=debug)

    # Post-processing: strip reasoning and standardize output format
    reasoning_match = re.search(r'(<Reasoning>.*?</Reasoning>)', joi_code_raw, re.DOTALL)
    script = re.sub(r'<Reasoning>.*?</Reasoning>', '', joi_code_raw, flags=re.DOTALL).strip()
    script = _apply_service_prefix(script)
    
    if cmd_type == "NO_SCHEDULE":
        # NO_SCHEDULE: LLM returns raw code, wrap it in JSON
        joi_json = {
            "cron": "",
            "period": 0,
            "script": script
        }
        joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
    else:
        # SCHEDULED/DURATION: LLM already returns JSON, just use stripped version
        joi_code_raw = script

    elapsed = time.perf_counter() - start
    # print(f"\nJoI ➡️ {elapsed:.4f} secs")

    # ❇️ Korean Reconversion
    translated_sentence = ""
    try:
        kor_system = prompts.get("kor_reconversion", "")
        kor_input = f"[Code]\n{joi_code_raw}\n\n[Service Descriptions]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
        kor_messages = [
            {"role": "system", "content": kor_system},
            {"role": "user", "content": kor_input}
        ]
        translated_sentence = run_llm_inference(model, client, "kor_reconversion", kor_messages, debug=debug)
    except Exception as e:
        print(f"Korean reconversion failed: {e}")

    return {
        "code": joi_code_raw,
        "merged_command": merged_command,
        "log": {
            "response_time": f"{elapsed:.4f} seconds",
            "inference_time": f"{elapsed:.4f} seconds",
            "translated_sentence": translated_sentence,
            "mapped_devices": mapped_devices,
        }
    }