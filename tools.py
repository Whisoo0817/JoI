import json
import os
import urllib.request
import urllib.parse

from config import get_client, get_model_id
from run_local import generate_joi_code
from loader import PROMPTS
import db

# ── Tool Implementations ──────────────────────────────────

def tool_request_to_joi_llm(args, memory):
    # Preprocess: refine command before code generation
    raw_sentence = args["sentence"]
    refined = _preprocess_command(raw_sentence, memory)
    sentence = refined if refined else raw_sentence

    if memory.get("debug"):
        print(f"[Preprocess] \"{raw_sentence}\" → \"{sentence}\"")

    try:
        result = generate_joi_code(
            sentence=sentence,
            connected_devices=memory.get("connected_devices", {}),
            other_params={},
            base_url=memory.get("base_url"),
        )
    except Exception as e:
        return {"error": str(e)}
    memory["last_result"] = result
    return {
        "status": "confirmation_needed",
        "translated_sentence": result.get("log", {}).get("translated_sentence", ""),
        "response_time": result.get("log", {}).get("response_time", ""),
    }


def tool_feedback_to_joi_llm(args, memory):
    feedback = args["feedback"].strip().lower()
    last = memory.get("last_result") or {}

    if feedback in ("y", "yes"):
        last["status"] = "approved"
        memory["last_result"] = last
        return {"status": "approved", "message": "User approved. Ready to register via add_scenario."}

    if feedback in ("n", "no"):
        memory["last_result"] = None
        return {"status": "rejected", "message": "User rejected. Task terminated and context cleared."}

    result = generate_joi_code(
        sentence=last.get("merged_command", ""),
        connected_devices=memory.get("connected_devices", {}),
        other_params={},
        modification=feedback,
        base_url=memory.get("base_url"),
    )
    memory["last_result"] = result
    return {
        "status": "confirmation_needed",
        "translated_sentence": result.get("log", {}).get("translated_sentence", ""),
        "response_time": result.get("log", {}).get("response_time", ""),
    }


def tool_add_scenario(args, memory):
    last = memory.get("last_result") or {}
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

    # DB 저장
    session_id = memory.get("session_id", "default")
    db.save_scenario(
        session_id=session_id,
        command=last.get("merged_command", ""),
        code=json.dumps(code, ensure_ascii=False),
        translated=scenario["command"],
    )

    hub_url = os.getenv("HUB_CONTROLLER_URL", "")
    if not hub_url:
        return {
            "status": "registered_locally",
            "scenario": scenario,
            "message": "No HUB_CONTROLLER_URL configured. Scenario saved to DB.",
        }

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


def tool_get_connected_devices(args, memory):
    devices = memory.get("connected_devices", {})
    if devices:
        return {"connected_devices": devices}
    return {"connected_devices": {}, "message": "No devices currently connected."}



def tool_get_weather(args, memory):
    """wttr.in을 이용한 날씨 정보 조회 (네트워크 필요)"""
    location = args.get("location", "Seoul")
    try:
        url = f"https://wttr.in/{urllib.parse.quote(location)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "joi-agent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        current = data["current_condition"][0]
        return {
            "location": location,
            "temp_c": current.get("temp_C"),
            "feels_like_c": current.get("FeelsLikeC"),
            "humidity": current.get("humidity"),
            "description": current.get("weatherDesc", [{}])[0].get("value", ""),
        }
    except Exception as e:
        return {"error": f"Weather fetch failed: {e}"}


def tool_get_scenarios(args, memory):
    """저장된 시나리오 목록 조회"""
    session_id = memory.get("session_id", "default")
    scenarios = db.get_scenarios(session_id)
    if not scenarios:
        return {"message": "등록된 시나리오가 없습니다.", "scenarios": []}
    # 코드 raw는 너무 길어서 제외하고 요약만 반환
    summary = [
        {
            "id": s["id"],
            "command": s["command"],
            "translated": s["translated"],
            "created_at": s["created_at"],
        }
        for s in scenarios
    ]
    return {"session_id": session_id, "count": len(summary), "scenarios": summary}


def tool_delete_scenario(args, memory):
    """시나리오 삭제"""
    scenario_id = args.get("scenario_id")
    if scenario_id is None:
        return {"error": "scenario_id is required"}
    db.delete_scenario(int(scenario_id))
    return {"status": "deleted", "scenario_id": scenario_id}





_PREPROCESS_PROMPT = """You are a command preprocessor for an IoT automation system called JOI.

Your job is to clarify a user's natural language command so the code generator understands it precisely — without losing or distorting any original intent.

## Connected Devices
{devices_info}

### How to read device info
- **Categories**: The device's type. The four categories Switch, LevelControl, ColorControl, RotaryControl are NOT standalone devices — they are auxiliary capability tags. Ignore them when identifying devices.
- **Tags**: Nicknames for this device. The code generator uses tags to map commands to devices.

---

## ABSOLUTE PROHIBITIONS — Never change these

### 1. Time & Schedule information
Preserve every time detail exactly as stated: repeat intervals, start times, durations, delays.
- "3분마다" must stay "3분마다". Do NOT omit or paraphrase it.
- "3초간 켜고 3초간 꺼줘" must stay as-is.

### 2. Korean verb endings carry semantic meaning — never alter them
These four forms have DIFFERENT meanings and MUST be preserved exactly:
- "불이 꺼져있으면" — static state check
- "불이 꺼진 상태면" — static state check
- "불이 꺼지면" — transition trigger 
- "불이 꺼지게 되면" — transition trigger (similar to 꺼지면 but more formal)
- "불이 꺼질때마다" - Repeated trigger (Every trigger)
NEVER substitute one for another.

---

## PERMITTED clarifications

### 1. AM/PM disambiguation
If the user says a bare time like "3시" with no AM/PM context, default to AM (오전): "오전 3시".

### 2. Device name clarification
Map vague device references to the actual device name from the connected device list.
- Auxiliary categories (Switch, LevelControl, ColorControl, RotaryControl) are NOT real device names. The real device is found in the non-auxiliary categories.
- Examples:
  - "스위치가 눌리면" → user means a button device → find the MultiButton → "멀티버튼의 버튼이 눌리면"
  - "온도를 알려줘" → telling = speaking → find the Speaker → "온도를 스피커로 알려줘"
  - "스피커 켜줘" → Speaker is a real device → keep as-is (just clarify quantity if needed)
- Only map if there is a clear unique match in the connected device list. If ambiguous, leave as-is.

### 3. Quantity clarification
If no quantity is stated, make it explicit using one of three modes:
- **하나**: one arbitrary device. Use when user says "하나", "임의의", or omits quantity entirely.
- **모두**: all devices of that type. Use when user says "모든", "전부", "다".
- **하나라도**: at least one. Only valid in conditions (if/when). Use when user says "하나라도".

---

## Examples
- "불을 아무거나 꺼줘" → "조명 하나를 꺼줘"
- "임의의 불을 꺼줘" → "조명 하나를 꺼줘"
- "불을 모두 꺼줘" → "모든 조명을 꺼줘"
- "3분마다 불을 토글해" → "3분마다 조명 하나를 토글해"
- "3분마다 조명 하나를 3초간 켰다가 꺼줘" → "3분마다 조명 하나를 3초간 켰다가 꺼줘"
- "스위치가 눌리면 불을 꺼줘" → "멀티버튼의 버튼이 눌리면 조명 하나를 꺼줘"
- "온도를 알려줘" → "온도를 스피커로 알려줘"
- "온도가 30도 이상이 되면 불을 모두 꺼" → "온도가 30도 이상이 되면 모든 조명을 꺼"
- "조명이 하나라도 켜져있으면 알려줘" → "조명이 하나라도 켜져있으면 스피커로 알려줘"
- "3시에 불 꺼줘" → "오전 3시에 조명 하나를 꺼줘"

## Output
Output ONLY the refined command. No JSON, no explanation, no quotes — just the refined Korean sentence."""


def _preprocess_command(user_command, memory):
    """사용자 명령어를 정제하여 명확한 명령어로 변환. 실패 시 빈 문자열 반환."""
    connected_devices = memory.get("connected_devices", {})

    devices_info = ""
    if isinstance(connected_devices, str):
        try:
            connected_devices = json.loads(connected_devices.replace("'", '"'))
        except Exception:
            pass
    for _, dev in connected_devices.items():
        tags = dev.get("tags", [])
        cats = dev.get("category", [])
        devices_info += f"- Tags: {tags}, Categories: {cats}\n"

    prompt = _PREPROCESS_PROMPT.format(
        devices_info=devices_info.strip() or "No devices connected.",
    )

    client = get_client(memory.get("base_url"))
    model = get_model_id(client)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_command},
            ],
            temperature=0.3,
            max_tokens=512,
            stream=False,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""


# ── Dispatch ──────────────────────────────────────────────

_TOOL_MAP = {
    "request_to_joi_llm":    tool_request_to_joi_llm,
    "feedback_to_joi_llm":   tool_feedback_to_joi_llm,
    "add_scenario":          tool_add_scenario,
    "get_scenarios":         tool_get_scenarios,
    "delete_scenario":       tool_delete_scenario,
    "get_connected_devices": tool_get_connected_devices,
    "get_weather":           tool_get_weather,
}


def dispatch(tool_name: str, tool_args: dict, agent_memory: dict) -> dict:
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    return fn(tool_args, agent_memory)
