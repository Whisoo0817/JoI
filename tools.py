import json
import os
import urllib.request
import urllib.parse

from run_local import generate_joi_code
from loader import PROMPTS, get_device_capability, get_joi_syntax
import db

# ── Tool Implementations ──────────────────────────────────

def tool_request_to_joi_llm(args, state):
    try:
        result = generate_joi_code(
            sentence=args["sentence"],
            connected_devices=state.get("connected_devices", {}),
            other_params={},
            base_url=state.get("base_url"),
        )
    except Exception as e:
        return {"error": str(e)}
    state["last_result"] = result
    return {
        "status": "confirmation_needed",
        "translated_sentence": result.get("log", {}).get("translated_sentence", ""),
        "response_time": result.get("log", {}).get("response_time", ""),
    }


def tool_feedback_to_joi_llm(args, state):
    feedback = args["feedback"].strip().lower()
    last = state.get("last_result") or {}

    if feedback in ("y", "yes"):
        last["status"] = "approved"
        state["last_result"] = last
        return {"status": "approved", "message": "User approved. Ready to register via add_scenario."}

    if feedback in ("n", "no"):
        state["last_result"] = None
        return {"status": "rejected", "message": "User rejected. Task terminated and context cleared."}

    result = generate_joi_code(
        sentence=last.get("merged_command", ""),
        connected_devices=state.get("connected_devices", {}),
        other_params={},
        modification=feedback,
        base_url=state.get("base_url"),
    )
    state["last_result"] = result
    return {
        "status": "confirmation_needed",
        "translated_sentence": result.get("log", {}).get("translated_sentence", ""),
        "response_time": result.get("log", {}).get("response_time", ""),
    }


def tool_add_scenario(args, state):
    last = state.get("last_result") or {}
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
    session_id = state.get("session_id", "default")
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


def tool_get_connected_devices(args, state):
    devices = state.get("connected_devices", {})
    if devices:
        return {"connected_devices": devices}
    return {"connected_devices": {}, "message": "No devices currently connected."}


def tool_get_device_capability(args, state):
    """SERVICE_DATA 또는 device_rules .md에서 카테고리 capability 조회"""
    category = args.get("category", "")
    if not category:
        return {"error": "category is required"}

    capability = get_device_capability(category)
    if capability:
        return capability

    doc = PROMPTS.get(f"device_rules_{category.lower()}")
    if doc:
        return {"category": category, "description": doc}

    return {"error": f"No capability info found for category: {category}"}


def tool_get_joi_syntax(args, state):
    """Joi code 문법 설명 문서 반환"""
    syntax = get_joi_syntax()
    if syntax:
        return {"syntax": syntax}
    return {"error": "Joi syntax documentation not found."}


def tool_get_weather(args, state):
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


def tool_get_scenarios(args, state):
    """저장된 시나리오 목록 조회"""
    session_id = state.get("session_id", "default")
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


def tool_delete_scenario(args, state):
    """시나리오 삭제"""
    scenario_id = args.get("scenario_id")
    if scenario_id is None:
        return {"error": "scenario_id is required"}
    db.delete_scenario(int(scenario_id))
    return {"status": "deleted", "scenario_id": scenario_id}




# ── Dispatch ──────────────────────────────────────────────

_TOOL_MAP = {
    "request_to_joi_llm":    tool_request_to_joi_llm,
    "feedback_to_joi_llm":   tool_feedback_to_joi_llm,
    "add_scenario":          tool_add_scenario,
    "get_scenarios":         tool_get_scenarios,
    "delete_scenario":       tool_delete_scenario,
    "get_connected_devices": tool_get_connected_devices,
    "get_device_capability": tool_get_device_capability,
    "get_joi_syntax":        tool_get_joi_syntax,
    "get_weather":           tool_get_weather,
}


def dispatch(tool_name: str, tool_args: dict, agent_state: dict) -> dict:
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    return fn(tool_args, agent_state)
