import json
import random
import re
import uuid
from types import SimpleNamespace

from config import get_client, get_model_id
from run_local import _parse_dict_input
import asyncio
import os
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

def call_mcp_tool_sync(tool_name: str, args: dict, context: dict) -> dict:
    return asyncio.run(_call_mcp_tool(tool_name, args, context))

async def _call_mcp_tool(tool_name: str, args: dict, context: dict):
    mcp_url = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8100/sse")
    
    # [Intercept] Implicitly inject joi_llm_result to shield local LLM from complex variables
    if tool_name == "feedback_to_joi_llm":
        args["joi_llm_result"] = context.get("last_result", {})
    elif tool_name == "add_scenario":
        args["joi_llm_result"] = context.get("last_result", {})

    try:
        async with sse_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=args)
                
                # FastMCP CallToolResult evaluation
                if hasattr(result, 'content') and len(result.content) > 0:
                    text_content = result.content[0].text
                    try:
                        parsed_result = json.loads(text_content)
                        # Cache the LLM pipeline result to use in feedback and scenario tasks
                        if tool_name in ["request_to_joi_llm", "feedback_to_joi_llm"]:
                            context["last_result"] = parsed_result
                            context["last_result_updated"] = True
                        return parsed_result
                    except json.JSONDecodeError:
                        return {"result": text_content}
                return {"result": str(result)}
    except Exception as e:
        return {"error": f"MCP Tool calling failed: {str(e)}", "error_code": "mcp_failed"}


_ERROR_HINTS = {
    "no_services":       "연결된 기기가 해당 명령을 지원하는 서비스가 없습니다. 기기 연결 문제가 아니므로 기기 매핑을 제안하지 마세요. 지원되지 않는 명령임을 안내하고 다른 명령을 시도해달라고 하세요. 추가 tool을 호출하지 마세요.",
    "no_devices":        "연결된 기기가 없습니다. 기기를 연결한 후 다시 시도해달라고 안내하세요. 추가 tool을 호출하지 마세요.",
    "hub_failed":        "허브 서버에 시나리오를 등록하지 못했습니다. 오류 내용을 그대로 사용자에게 전달하세요. 추가 tool을 호출하지 마세요.",
    "weather_failed":    "날씨 정보를 가져오지 못했습니다. 네트워크 연결을 확인하거나, 도시 이름을 영어 대도시명(예: Seoul, Busan)으로 다시 시도해달라고 안내하세요. 추가 tool을 호출하지 마세요.",
    "generation_failed": "코드 생성 중 오류가 발생했습니다. 오류 내용을 그대로 사용자에게 전달하세요. 추가 tool을 호출하지 마세요.",
}

_AUX_CATEGORIES = {"Switch", "LevelControl", "ColorControl", "RotaryControl"}

# One example per device category. Covers varied JOI patterns.
_CATEGORY_EXAMPLES = {
    "Light":                "오전 8시에 조명을 꺼줘",
    "AirConditioner":       "오후 2시에 에어컨을 켜줘",
    "Plug":                 "1시간 뒤에 플러그를 꺼줘",
    "Humidifier":           "2시간마다 가습기를 켜줘",
    "Dehumidifier":         "오전 9시에 제습기를 켜줘",
    "AirPurifier":          "30분마다 공기청정기를 껐다 켜줘",
    "RobotVacuumCleaner":   "매일 오전 10시에 로봇청소기를 켜줘",
    "Television":           "오후 11시에 TV를 꺼줘",
    "Speaker":              "1시간마다 스피커로 인사해줘",
    "DoorLock":             "오후 10시에 도어락을 잠궈줘",
    "Door":                 "문이 열리면 잠궈줘",
    "Blind":                "오전 7시에 블라인드를 올려줘",
    "Shade":                "오후 9시에 커튼을 닫아줘",
    "Window":               "창문이 열려있으면 닫아줘",
    "Valve":                "1시간마다 밸브를 열었다가 닫아줘",
    "Siren":                "버튼이 눌리면 사이렌을 켜줘",
    "TemperatureSensor":    "온도가 28도 이상이 되면 알려줘",
    "HumiditySensor":       "습도가 70% 이상이면 알려줘",
    "PresenceSensor":       "사람이 감지될 때마다 조명을 켜줘",
    "ContactSensor":        "문이 열릴 때마다 알려줘",
    "MultiButton":          "2번 버튼이 눌릴 때마다 조명을 토글해줘",
    "Button":               "버튼이 눌리면 에어컨을 켜줘",
    "MotionSensor":         "움직임이 감지되면 조명을 켜줘",
    "LeakSensor":           "누수가 감지되면 밸브를 잠궈줘",
    "Camera":               "카메라로 사진을 찍어줘",
    "DimmerSwitch":         "디머 스위치를 누르면 조명 밝기를 50으로 설정해줘",
    "TapDialSwitch":        "탭다이얼 스위치를 돌리면 조명 밝기를 조절해줘",
}


def _error_hint(tool_result: dict) -> str:
    code = tool_result.get("error_code", "")
    msg = tool_result.get("error", "")
    return _ERROR_HINTS.get(code, f"도구 실행 중 오류가 발생했습니다. 오류 내용을 그대로 사용자에게 전달하세요: {msg}\n추가 tool을 호출하지 마세요.")

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
            "name": "get_thing_details",
            "description": "Get detailed information about a specific device, including its capabilities (functions) and current status.",
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
                        "description": "The service/function name (e.g., 'switch_on', 'switch_off', 'setLevel', 'setTemperature')"
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
                        "description": "The sensor/attribute name (e.g., 'temperature', 'contact', 'power')"
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

AGENT_SYSTEM_PROMPT = """You are JoI, a helpful and efficient IoT assistant. Your primary goal is to help users manage their smart home.

## Core Principles (CRITICAL):
- **NEVER PROVIDE AN EMPTY RESPONSE**: You MUST ALWAYS output a natural language response to the user, even after calling a tool. If a tool was successful, confirm it to the user.
- **Language**: Always respond in Korean.
- **IoT Only**: Focus strictly on IoT-related tasks.
- **Example Commands**: When showing examples, use ONLY the exact list provided in "## Example Commands" below — copy them verbatim. NEVER invent, paraphrase, or add examples outside that list. If the list is empty, do not show any examples.

## Capabilities & Tools Usage:
- **Immediate Action**: If user wants to do something "now" (e.g. "불 켜줘", "에어컨 꺼"), use `control_thing_directly`.
- **Automation (Scenario)**: If user wants something scheduled or event-driven (e.g. "매일 아침 7시에", "문이 열리면"), use the `request_to_joi_llm` -> `feedback_to_joi_llm` -> `add_scenario` flow.
- **Monitoring**: Use `get_current_values` for real-time status and `get_value_history` for historical data or trends.
- **Device Management**: Use `get_connected_devices` (overview), `get_thing_details` (specifics), and `manage_thing_tags` to organize devices.
- **Scenario Management**: Use `get_scenarios` to list, `start_scenario`/`stop_scenario` to toggle, and `get_scenario_details` to inspect.
- **External Info**: Use `get_weather` for weather and air quality info.

## Guidelines for Tools:
- **Direct Control confirmation**: After calling `control_thing_directly`, confirm the result to the user.
- **Data Interpretation**: When using `get_value_history` or `get_current_values`, interpret the data for the user (e.g. "현재 온도는 25도이며, 지난 1시간 동안 일정하게 유지되었습니다").
- **JOI LLM Flow**:
  - Once a scenario is shown, pass y/n/modification text to `feedback_to_joi_llm`.
  - After "confirmation_needed", use the format: "[translated_sentence]\\n이 시나리오가 맞나요? (y/n/수정사항)"
  - If rejected, respond with ONLY: "생성된 시나리오 등록을 거부했습니다. 어떤 것을 도와드릴까요?"

## When introducing yourself:
Describe yourself as an intelligent IoT manager who can (1) control devices directly, (2) create complex automation scenarios using JOI language, (3) monitor sensor data and history, and (4) manage registered automations. Use a single concise paragraph.
"""

MAX_AGENT_ROUNDS = 5


def _trim_tool_result(msg: dict) -> dict:
    """tool 메시지에서 history에 불필요한 대용량 필드를 제거한다."""
    if msg.get("role") != "tool":
        return msg
    try:
        result = json.loads(msg["content"])
    except (json.JSONDecodeError, KeyError):
        return msg

    # get_connected_devices: 디바이스 전체 JSON → category/tags 요약만 남김
    if "connected_devices" in result and isinstance(result["connected_devices"], dict):
        result["connected_devices"] = {
            k: {"category": v.get("category", []), "tags": v.get("tags", [])}
            for k, v in result["connected_devices"].items()
        }

    # request_to_joi_llm / feedback_to_joi_llm: log 필드 제거
    if "log" in result:
        del result["log"]

    # get_scenarios: code 필드 제거 (name, command만 남김)
    if "scenarios" in result and isinstance(result["scenarios"], list):
        result["scenarios"] = [
            {k: v for k, v in s.items() if k not in ["code", "script"]}
            for s in result["scenarios"]
        ]

    # get_value_history: 데이터가 너무 많으면 최근 5개만 남김
    if "history" in result and isinstance(result["history"], list):
        if len(result["history"]) > 5:
            result["history"] = result["history"][-5:]
            result["_note"] = "Showing only the most recent 5 records to save context space."

    # get_thing_details: functions 리스트가 너무 길면 요약? (일단 유지)

    return {**msg, "content": json.dumps(result, ensure_ascii=False)}


def agent_chat_stream(user_message, session_id="default", connected_devices=None, base_url=None, debug=False, on_complete=None, on_tool_call=None):
    """
    agent_chat의 스트리밍 버전. 최종 텍스트 응답을 토큰 단위로 yield하고
    마지막에 last_result를 JSON 이벤트로 yield한다.

    Yields:
        str: SSE 형식 문자열
            - 텍스트 토큰: "data: <token>\n\n"
            - 완료: "data: [DONE] <json>\n\n"
    """
    import db as _db

    client = get_client(base_url)
    model = get_model_id(client)

    session = _db.load_session(session_id)
    chat_history = session["chat_history"]
    last_result = session["last_result"]
    stored_devices = session["connected_devices"]

    if connected_devices is not None:
        devices = _parse_dict_input(connected_devices, stored_devices)
    else:
        devices = stored_devices

    context = {
        "chat_history": chat_history,
        "connected_devices": devices,
        "base_url": base_url,
        "last_result": last_result,
        "last_result_updated": False,
        "debug": debug,
        "session_id": session_id,
    }

    truncated_history = list(chat_history)
    while True:
        history_tokens_est = sum(len(json.dumps(m, ensure_ascii=False)) for m in truncated_history) // 4
        if history_tokens_est <= 2000 or len(truncated_history) <= 5:
            break
        truncated_history = truncated_history[5:]

    # Build example commands from connected device categories
    present_cats = []
    for dev in (devices or {}).values():
        for cat in dev.get("category", []):
            if cat not in _AUX_CATEGORIES and cat not in present_cats and cat in _CATEGORY_EXAMPLES:
                present_cats.append(cat)
    sampled = random.sample(present_cats, min(3, len(present_cats)))
    example_lines = "\n".join(f"- {_CATEGORY_EXAMPLES[c]}" for c in sampled)
    example_section = f"\n\n## Example Commands (use ONLY these when showing examples):\n{example_lines}" if example_lines else ""
    
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT + example_section}]    
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": user_message})

    final_response = ""

    for _ in range(MAX_AGENT_ROUNDS):
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            temperature=0.6,
            max_tokens=2048,
            stream=True,
            stream_options={"include_usage": True},
            extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        )

        visible_content = ""
        tool_call_chunks = {}
        usage = None

        for chunk in stream:
            if chunk.usage:
                usage = chunk.usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                visible_content += delta.content

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_chunks:
                        tool_call_chunks[idx] = SimpleNamespace(
                            id=tc.id or f"call_{uuid.uuid4().hex[:8]}",
                            type="function",
                            function=SimpleNamespace(name="", arguments="")
                        )
                    if tc.function.name:
                        tool_call_chunks[idx].function.name += tc.function.name
                    if tc.function.arguments:
                        tool_call_chunks[idx].function.arguments += tc.function.arguments

        if usage:
            prompt_tokens = usage.prompt_tokens
            history_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in truncated_history)
            history_tokens_est = history_chars // 4
            print(f"[TOKEN] prompt={prompt_tokens} / 16384 ({prompt_tokens / 16384 * 100:.1f}%)  history≈{history_tokens_est}", flush=True)

        parsed_tool_calls = list(tool_call_chunks.values())

        # Fallback: raw <tool_call> tags
        if not parsed_tool_calls and "<tool_call>" in visible_content:
            tc_match = re.search(r'<tool_call>\s*({.*?})\s*</tool_call>', visible_content, re.DOTALL)
            if tc_match:
                try:
                    tc_json = json.loads(tc_match.group(1))
                    func_obj = SimpleNamespace(name=tc_json["name"], arguments=json.dumps(tc_json.get("arguments", {})))
                    parsed_tool_calls = [SimpleNamespace(id=f"call_{uuid.uuid4().hex[:8]}", type="function", function=func_obj)]
                    visible_content = visible_content.replace(tc_match.group(0), "").strip()
                except Exception:
                    pass

        visible_content = visible_content.strip()

        if not parsed_tool_calls:
            # 최종 텍스트 응답 — 토큰 단위로 yield
            final_response = visible_content
            messages.append({"role": "assistant", "content": final_response})
            for char in final_response:
                yield f"data: {json.dumps(char, ensure_ascii=False)}\n\n"
            break

        messages.append({
            "role": "assistant",
            "content": visible_content,
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in parsed_tool_calls
            ],
        })

        for tc in parsed_tool_calls:
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            tool_result = call_mcp_tool_sync(tc.function.name, tool_args, context)

            if on_tool_call:
                on_tool_call(tc.function.name, tool_args, tool_result)

            messages.append({
                "role": "tool",
                "content": json.dumps(tool_result, ensure_ascii=False),
                "tool_call_id": tc.id,
            })

            if tool_result.get("error"):
                messages.append({"role": "user", "content": _error_hint(tool_result)})
    else:
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                final_response = msg["content"]
                break
        if not final_response:
            final_response = "명령을 수행했습니다."
        for char in final_response:
            yield f"data: {json.dumps(char, ensure_ascii=False)}\n\n"

    if not final_response:
        final_response = "명령을 수행했습니다."

    updated_history = [_trim_tool_result(m) for m in messages[1:]]
    _db.save_session(session_id, updated_history, context.get("last_result"), devices)

    updated_result = context.get("last_result") if context.get("last_result_updated") else None

    if on_complete:
        on_complete(final_response, updated_result)

    # 웹 클라이언트에는 logs 제외한 last_result 전달
    if updated_result and "log" in updated_result:
        client_result = {**updated_result, "log": {k: v for k, v in updated_result["log"].items() if k != "logs"}}
    else:
        client_result = updated_result

    done_payload = json.dumps({"last_result": client_result}, ensure_ascii=False)
    yield f"data: [DONE] {done_payload}\n\n"



