import time
import ast
import os
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from config import get_client, get_model_id
from loader import SERVICE_DATA, PROMPTS
from parser.validator import validate_joi

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class JoiGenerationError(ValueError):
    """generate_joi_code 내부 오류. logs 속성에 오류 발생 전까지의 로그를 담는다."""
    def __init__(self, message, logs="", error_code=""):
        super().__init__(message)
        self.logs = logs
        self.error_code = error_code


def run_llm_inference(model, client, inference_type, messages):
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

    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    decode_tps = completion_tokens / elapsed if elapsed > 0 and completion_tokens else 0
    log_line = (
        f"➡️ {inference_type}({prompt_tokens}) | Decode: {decode_tps:.1f} t/s | Total: {elapsed:.4f}s\n"
        f"===================================================\n"
        f"{content}"
    )
    return content.strip(), log_line


# selected_services = ["Light.Off", "ContactSensor.Contact"]
# SERVICE_DATA에서 Parsing
def extract_service_details(selected_services, full_service_data):
    # Switch, LevelControl, ColorControl은 독립 카테고리지만
    # Light 같은 primary 디바이스에 포함되어 있어 여기서 fallback으로 탐색
    SECONDARY_CATS = ["LevelControl", "ColorControl", "Switch"]

    def _find_service(dev_id, svc_name):
        """dev_id의 values/functions에서 svc_name을 찾아 반환. 없으면 None."""
        if dev_id not in full_service_data:
            return None
        item = full_service_data[dev_id]
        for entry in item.get("values", []) + item.get("functions", []):
            if entry["id"] == svc_name:
                return json.loads(json.dumps(entry))
        return None

    def _resolve_enum(svc_entry, enums_map):
        """svc_entry 내 arguments/return 의 ENUM format을 enums_map에서 해석해 enum_list 주입."""
        svc_entry = json.loads(json.dumps(svc_entry))
        # arguments의 ENUM 처리
        for arg in svc_entry.get("arguments", []):
            if arg.get("type") == "ENUM" and "format" in arg:
                arg["enum_list"] = enums_map.get(arg["format"], [])
        # return_type이 ENUM인 value 서비스
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
            # primary 디바이스에서 먼저 찾고, 없으면 secondary 카테고리 순으로 탐색
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


# SERVICE_DATA 순회 -> { 서비스명: 카테고리 } 역방향 맵을 생성.
# Secondary Category 우선
def _build_service_category_map(service_data):
    SECONDARY = {'Switch', 'LevelControl', 'ColorControl'}
    mapping = {}
    for cat, item in service_data.items():
        if cat not in SECONDARY:
            for entry in item.get("values", []) + item.get("functions", []):
                svc = entry["id"]
                if svc not in mapping:
                    mapping[svc] = cat
    for cat in SECONDARY:
        if cat in service_data:
            for entry in service_data[cat].get("values", []) + service_data[cat].get("functions", []):
                mapping[entry["id"]] = cat
    return mapping

_SERVICE_CATEGORY_MAP = _build_service_category_map(SERVICE_DATA)

# Add Prefix: (#Light).On() → (#Light).switch_on()
def _apply_service_prefix(script):
    def _fmt(service, selector=None):
        # 1순위: selector의 태그(예: #TemperatureSensor)가 SERVICE_DATA에 있으면 그 카테고리 사용
        if selector:
            tags = re.findall(r'#(\w+)', selector)
            for tag in tags:
                if tag in SERVICE_DATA:
                    item = SERVICE_DATA[tag]
                    svc_ids = {e["id"] for e in item.get("values", []) + item.get("functions", [])}
                    if service in svc_ids:
                        cat_fmt = tag[0].lower() + tag[1:]
                        svc_fmt = service[0].lower() + service[1:]
                        return f"{cat_fmt}_{svc_fmt}"
        # 2순위: 전역 service-category 맵에서 탐색
        category = _SERVICE_CATEGORY_MAP.get(service, '')
        if category:
            cat_fmt = category[0].lower() + category[1:]
            svc_fmt = service[0].lower() + service[1:]
            return f"{cat_fmt}_{svc_fmt}"
        return service[0].lower() + service[1:]

    # 함수 호출: (#Light).On(args) 형태
    def replace_func(m):
        return f"{m.group(1)}.{_fmt(m.group(2), m.group(1))}({m.group(3)})"
    script = re.sub(r'((?:all|any)?\((?:#\w+\s*)+\))\.([A-Z]\w+)\(([^)]*)\)', replace_func, script)

    # 값 참조: (#Light).Switch 형태
    def replace_value(m):
        return f"{m.group(1)}.{_fmt(m.group(2), m.group(1))}"
    script = re.sub(r'((?:all|any)?\((?:#\w+\s*)+\))\.([A-Z]\w+)(?!\w|\()', replace_value, script)

    return script

# 각 JoI 문장/블록 사이에 \n이 확실히 들어가도록 정규화. script 필드 값(이미 언이스케이프된 문자열)에만 적용
def _normalize_script_newlines(script):    
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

# LLM이 any(#Tag).Prop == val 형태로 생성한 경우 Joi 문법에 맞게 후처리.
def _post_process_joi_any_quantifiers(script):
    pattern = r'any\(#(\w+)\)\.(\w+)\s*([=!<>:]=|[<>])\s*([^)\n{}|]+)'

    def replacer(match):
        tag = match.group(1)
        prop = match.group(2)
        op = match.group(3)
        val = match.group(4).strip()
        if op.endswith('|'): return match.group(0)  # 이미 처리된 경우 스킵
        return f'all(#{tag}).{prop} {op}| {val}'

    return re.sub(pattern, replacer, script)


def _parse_dict_input(val, default):
    if isinstance(val, dict): return val
    if isinstance(val, str):
        try: return ast.literal_eval(val)
        except Exception: pass
    return default

def generate_joi_code(sentence, connected_devices, other_params, modification=None, base_url=None):
    # 1. Parse Inputs - dict type
    connected_devices = _parse_dict_input(connected_devices, None)
    other_params = _parse_dict_input(other_params, {})

    # 2. Setup Client
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
            raise JoiGenerationError("No connected devices provided. IoT mapping requires a device list.", "\n".join(log_buf), error_code="no_devices")
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

        category_input = f"[Available Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}\n\n[Command]\n{sentence}"        
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

        # Filter by valid_categories to prevent hallucinations
        extracted_categories = {k: v for k, v in extracted_categories.items() if k in valid_categories}

        # ❇️ Stage 2-2: Mapping Intent (Per Device)
        missing_descriptors = [dev for dev in extracted_categories if not PROMPTS.get(f"device_rules_{dev.lower()}", "")]
        if missing_descriptors:
            raise JoiGenerationError(
                f"Mapped device(s) {missing_descriptors} are not registered in the service list.",
                "\n".join(log_buf),
                error_code="missing_descriptor"
            )

        raw_selected_services = []
        for dev, assigned_task in extracted_categories.items():
            device_rules = PROMPTS.get(f"device_rules_{dev.lower()}", "")

            # Identify sub-categories attached to this main device (e.g., Switch, ColorControl)
            sub_cats = set()
            for info in cd_simple.values():
                cats = info.get("category", [])
                if dev in cats:
                    for c in cats:
                        if c in exclude_categories: sub_cats.add(c)
                
            for sub_cat in sub_cats:
                sub_rule = PROMPTS.get(f"device_rules_{sub_cat.lower()}", "")
                if sub_rule:
                    # Safely map all SubCat (e.g., Switch) references to MainCat (e.g., Speaker)
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
            raise JoiGenerationError(f"No services found for the command: '{sentence}'. Category/Intent mapping failed.", "\n".join(log_buf), error_code="no_services")

        precision_input = f"[Command]\n{sentence}\n[Intent]\n{json.dumps(intent_categories, indent=2, ensure_ascii=False)}\n[Connected Devices]\n{json.dumps(cd_simple, indent=2, ensure_ascii=False)}"
        precision_output = infer("mapping_precision", precision_input)

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
    prompt_key = base_prompt_key
    
    # Prepare System Prompt
    system_prompt = PROMPTS.get(prompt_key, "")
    
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

    if cmd_type == "NO_SCHEDULE":
        # NO_SCHEDULE: LLM returns raw code, wrap it in JSON
        joi_json = {
            "name": "Scenario",
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
            joi_json.setdefault("name", "Scenario")
            joi_json = {"name": joi_json.pop("name"), **joi_json}
            joi_code_raw = json.dumps(joi_json, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            joi_code_raw = script
            joi_json = {}

    # ❇️ Validation
    _ = validate_joi(joi_json.get("script", ""), connected_devices, _SERVICE_CATEGORY_MAP)

    elapsed = time.perf_counter() - start
    # print(f"\nJoI ➡️ {elapsed:.4f} secs")

    # ❇️ Code -> ENG
    translated_sentence = ""
    try:
        eng_plan = f"\n\n[Code Plan]\n{code_plan}" if code_plan else ""
        eng_input = f"[Code]\n{joi_code_raw}{eng_plan}\n\n[Service Descriptions]\n{json.dumps(service_details, indent=2, ensure_ascii=False)}"
        translated_sentence = infer("re_translate", eng_input)
    except Exception as e:
        print(f"Re-translation failed: {e}")

    # ❇️ ENG -> KOR
    translated_sentence_kor = ""
    if translated_sentence:
        try:
            translated_sentence_kor = infer("re_translate_kor", translated_sentence)
        except Exception as e:
            print(f"Korean re-translation failed: {e}")

    # any → all + operator + | 후처리 (re_translate 이후 적용)
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
        "log": {
            "response_time": f"{elapsed:.4f} seconds",            
            "translated_sentence": re.sub(r'["""\'\'\'.,!?。、！？]', '', translated_sentence_kor or translated_sentence).strip(),
            "logs": "\n".join(log_buf),
        }
    }