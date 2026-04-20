import asyncio
import json
import os

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession


# ── MCP Tool Calling ───────────────────────────────────────

def call_mcp_tool_sync(tool_name: str, args: dict, context: dict) -> dict:
    return asyncio.run(_call_mcp_tool(tool_name, args, context))


async def _call_mcp_tool(tool_name: str, args: dict, context: dict):
    mcp_url = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8100/mcp")

    if tool_name == "feedback_to_joi_llm":
        args["joi_llm_result"] = context.get("last_result", {})
    elif tool_name == "add_scenario":
        args["joi_llm_result"] = context.get("last_result", {})

    try:
        async with streamablehttp_client(mcp_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)

                if hasattr(result, 'content') and len(result.content) > 0:
                    text_content = result.content[0].text
                    try:
                        parsed_result = json.loads(text_content)
                        if tool_name in ["request_to_joi_llm", "feedback_to_joi_llm"]:
                            context["last_result"] = parsed_result
                            context["last_result_updated"] = True
                        return parsed_result
                    except json.JSONDecodeError:
                        return {"result": text_content}
                return {"result": str(result)}
    except Exception as e:
        return {"error": f"MCP Tool calling failed: {str(e)}", "error_code": "mcp_failed"}


# ── Tool Schemas ───────────────────────────────────────────

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "request_to_joi_llm",
            "description": (
                "Send a natural-language IoT command to the JOI code generator. "
                "ONLY call this after the user has EXPLICITLY confirmed scenario creation "
                "(e.g., said '생성해줘', '응', 'y', or confirmed when asked). "
                "NEVER call this on the first IoT command from the user — always ask for confirmation first."
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
            "description": "Get the list of currently connected IoT devices, including their UUIDs, nicknames, categories, functions, and current values. Use this whenever you need any device information.",
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
            "name": "get_thing_details",
            "description": "Get detailed functions and values for a specific device. Use this instead of get_connected_devices when you only need info about one device.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thing_id": {
                        "type": "string",
                        "description": "The unique UUID of the device from the connected devices list."
                    }
                },
                "required": ["thing_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_scenarios",
            "description": "Retrieve the list of previously registered IoT scenarios from the local DB.",
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
            "name": "get_current_values",
            "description": "Get the current real-time sensor values or status for a specific device.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thing_id": {
                        "type": "string",
                        "description": "The unique ID of the device"
                    }
                },
                "required": ["thing_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_thing_directly",
            "description": "Immediately control a device without creating a scenario. Use this for one-off actions like 'turn on the light now'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thing_id": {
                        "type": "string",
                        "description": "The unique ID (UUID) of the device"
                    },
                    "service_name": {
                        "type": "string",
                        "description": "The exact function name from the device's 'functions' list. NEVER guess — call get_thing_details or get_connected_devices first to get the exact name (e.g., 'switch_on', 'switch_off', 'light_moveToBrightness')."
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Arguments for the service (e.g., ['50'] for setLevel). For color, use ['R|G|B'] like ['255|0|0']."
                    },
                    "service_type": {
                        "type": "string",
                        "description": "Type of service, usually 'function'",
                        "default": "function"
                    }
                },
                "required": ["thing_id", "service_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_locations",
            "description": "Get the list of locations (rooms) registered in the IoT system.",
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
            "name": "get_value_history",
            "description": "Get historical data for a specific device attribute (e.g., temperature, energy consumption).",
            "parameters": {
                "type": "object",
                "properties": {
                    "thing_id": {
                        "type": "string",
                        "description": "The unique ID of the device"
                    },
                    "service_name": {
                        "type": "string",
                        "description": "The value name from the device's 'values' list (e.g., 'switch_switch', 'light_currentBrightness'). Call get_connected_devices first to check available values for the device."
                    },
                    "unit": {
                        "type": "string",
                        "description": "Time aggregation unit",
                        "enum": ["minutely", "hourly", "daily", "weekly"]
                    },
                    "data_server_id": {
                        "type": "string",
                        "description": "Data server ID, default is 'auto'",
                        "default": "auto"
                    }
                },
                "required": ["thing_id", "service_name", "unit"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_scenario_details",
            "description": "Get the detailed JOI script and configuration for a specific scenario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_name": {
                        "type": "string",
                        "description": "The name of the scenario"
                    }
                },
                "required": ["scenario_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_scenario",
            "description": "Activate or manually trigger a registered scenario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_name": {
                        "type": "string",
                        "description": "The name of the scenario to start"
                    }
                },
                "required": ["scenario_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_scenario",
            "description": "Deactivate a running scenario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_name": {
                        "type": "string",
                        "description": "The name of the scenario to stop"
                    }
                },
                "required": ["scenario_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_thing_tags",
            "description": "Add or remove tags from a device for better categorization.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thing_id": {
                        "type": "string",
                        "description": "The unique ID of the device"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to perform: 'add' or 'remove'",
                        "enum": ["add", "remove"]
                    },
                    "tag": {
                        "type": "string",
                        "description": "The tag name"
                    }
                },
                "required": ["thing_id", "action", "tag"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Fetch current weather information or air quality for a given location. (Calls external API via MCP)",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location, e.g. 'Seoul', 'Busan'"
                    }
                },
                "required": ["location"]
            }
        }
    },
]


# ── Error Handling ─────────────────────────────────────────

_ERROR_HINTS = {
    "no_services":       "연결된 기기가 해당 명령을 지원하는 서비스가 없습니다. 기기 연결 문제가 아니므로 기기 매핑을 제안하지 마세요. 지원되지 않는 명령임을 안내하고 다른 명령을 시도해달라고 하세요. 추가 tool을 호출하지 마세요.",
    "no_devices":        "연결된 기기가 없습니다. 기기를 연결한 후 다시 시도해달라고 안내하세요. 추가 tool을 호출하지 마세요.",
    "hub_failed":        "허브 서버에 시나리오를 등록하지 못했습니다. 오류 내용을 그대로 사용자에게 전달하세요. 추가 tool을 호출하지 마세요.",
    "weather_failed":    "날씨 정보를 가져오지 못했습니다. 네트워크 연결을 확인하거나, 도시 이름을 영어 대도시명(예: Seoul, Busan)으로 다시 시도해달라고 안내하세요. 추가 tool을 호출하지 마세요.",
    "generation_failed": "코드 생성 중 오류가 발생했습니다. 오류 내용을 그대로 사용자에게 전달하세요. 추가 tool을 호출하지 마세요.",
}


def error_hint(tool_result: dict) -> str:
    code = tool_result.get("error_code", "")
    msg = tool_result.get("error", "")
    return _ERROR_HINTS.get(code, f"도구 실행 중 오류가 발생했습니다. 오류 내용을 그대로 사용자에게 전달하세요: {msg}\n추가 tool을 호출하지 마세요.")


# ── History Summarization ──────────────────────────────────

def summarize_tool_result(tool_name: str, msg: dict) -> dict:
    """history 저장용: tool result를 한 줄 요약 문자열로 축약한다."""
    if msg.get("role") != "tool":
        return msg
    try:
        result = json.loads(msg["content"])
    except (json.JSONDecodeError, KeyError):
        return msg

    if isinstance(result, dict) and result.get("error"):
        summary = f"[{tool_name}: failed - {result.get('error', '')}]"

    elif tool_name == "get_connected_devices":
        devices = result.get("devices", {})
        names = [v.get("nickname") or k for k, v in devices.items()]
        summary = f"[get_connected_devices: {len(names)} devices - {', '.join(names[:5])}{'...' if len(names) > 5 else ''}]"

    elif tool_name == "get_thing_details":
        nickname = result.get("nickname") or result.get("id", "")
        funcs = [f["name"] for f in result.get("functions", [])]
        summary = f"[get_thing_details: {nickname} - functions: {', '.join(funcs[:8])}{'...' if len(funcs) > 8 else ''}]"

    elif tool_name == "control_thing_directly":
        thing_id = result.get("thing_id", "")
        service = result.get("service_name", "")
        action = result.get("action", "completed")
        summary = f"[control_thing_directly: {service} on {thing_id} → {action}]"

    elif tool_name in ("request_to_joi_llm", "feedback_to_joi_llm"):
        status = result.get("status", "")
        translated = result.get("merged_command") or (result.get("log") or {}).get("translated_sentence", "")
        summary = f"[{tool_name}: {status} - {translated}]"

    elif tool_name == "add_scenario":
        scenario = result.get("scenario", {})
        name = scenario.get("name", "")
        summary = f"[add_scenario: registered '{name}']"

    elif tool_name == "get_scenarios":
        scenarios = result.get("scenarios", [])
        names = [s.get("name", "") for s in scenarios]
        summary = f"[get_scenarios: {len(names)} scenarios - {', '.join(names[:5])}]"

    elif tool_name == "get_current_values":
        count = len(result.get("values", result.get("current_values", [])))
        summary = f"[get_current_values: {count} values retrieved]"

    elif tool_name == "get_value_history":
        count = len(result.get("history", []))
        summary = f"[get_value_history: {count} records retrieved]"

    else:
        summary = f"[{tool_name}: completed]"

    return {**msg, "content": summary}
