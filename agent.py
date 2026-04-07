import json
import re
import uuid
from types import SimpleNamespace

from config import get_client, get_model_id
from run_local import _parse_dict_input
from tools import dispatch

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
            "name": "delete_scenario",
            "description": "Delete a registered scenario from the local DB by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "integer",
                        "description": "The ID of the scenario to delete (get it from get_scenarios first)"
                    }
                },
                "required": ["scenario_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Fetch current weather information for a given location. "
                "Use this when the user asks about weather to help decide on IoT automation "
                "(e.g. closing blinds on sunny days, turning on heating when cold)."
            ),
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

AGENT_SYSTEM_PROMPT = """You are JoI, an IoT assistant that helps users control smart home devices and create automation scenarios.

## Strict Conversational Guidelines
- **IoT Focus**: Primarily assist with IoT control and smart home scenarios. Reject all other unrelated topics.
- Always respond in the same language as the user.
- Never guess device states — use `get_connected_devices` if needed.
- Do not retry automatically on error — inform the user.
- Handle one task at a time.
- **NEVER output a summary or description of what you are about to do before a tool call.** Call the tool silently — only speak after you have the tool result.

## Chain of Thought (Thinking before acting)
- **CRITICAL**: Before invoking ANY tool or writing a final response, you MUST first write your thought process inside `<think>` and `</think>` tags.
- Inside `<think>`, evaluate what the user wants, check if you have an appropriate tool, and plan your next action.
- ONLY call a tool if it directly solves the user's request. If you do not have a suitable tool (e.g., to list existing scenarios), do NOT call an unrelated tool (like `get_connected_devices`). Instead, explain your limitations to the user directly after the `</think>` tag.

## Your capabilities (via tool calls)
- **request_to_joi_llm**: Generate JOI scenario code from a natural language command.
- **feedback_to_joi_llm**: Process user feedback ('y'=approve, 'n'=reject, or modification text) on generated code.
- **add_scenario**: Register an approved scenario to the Hub Controller and save to local DB.
- **get_scenarios**: Retrieve the list of previously registered scenarios from local DB (includes id, command, translated, created_at).
- **delete_scenario**: Delete a scenario by ID. Always call get_scenarios first to get the ID.
- **get_connected_devices**: Retrieve the list of connected IoT devices.
- **get_weather**: Fetch current weather for a location.

## Strict Workflow for IoT commands
1. User gives an IoT command → `<think>` evaluation `</think>` → call `request_to_joi_llm`.
2. Present the `translated_sentence` from the result and ask explicitly: "이 시나리오가 맞나요? (y/n/수정사항)"
3. Wait for user feedback. When they reply, YOU MUST `<think>` about it `</think>` → call `feedback_to_joi_llm` FIRST to process the feedback.
4. If the feedback tool returns "approved" → call `add_scenario` to register it.
5. If the feedback tool returns "rejected" → inform the user it was cancelled.
"""

MAX_AGENT_ROUNDS = 5




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
    client = get_client(base_url)
    model = get_model_id(client)

    if chat_history is None:
        chat_history = []
    if agent_state is None:
        agent_state = {
            "connected_devices": _parse_dict_input(connected_devices, {}),
            "base_url": base_url,
            "last_result": None,
        }

    truncated_history = chat_history[-6:] if len(chat_history) > 6 else chat_history

    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": user_message})

    final_response = ""

    for _ in range(MAX_AGENT_ROUNDS):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            temperature=0.6,
            max_tokens=2048,
            stream=False,
            extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        )

        msg = response.choices[0].message

        # Fallback for models that output raw <tool_call> tags in content
        parsed_tool_calls = msg.tool_calls if getattr(msg, "tool_calls", None) else []
        if not parsed_tool_calls and msg.content and "<tool_call>" in msg.content:
            tc_match = re.search(r'<tool_call>\s*({.*?})\s*</tool_call>', msg.content, re.DOTALL)
            if tc_match:
                try:
                    tc_json = json.loads(tc_match.group(1))
                    func_obj = SimpleNamespace(name=tc_json["name"], arguments=json.dumps(tc_json.get("arguments", {})))
                    parsed_tool_calls = [SimpleNamespace(id=f"call_{uuid.uuid4().hex[:8]}", type="function", function=func_obj)]
                    msg.content = msg.content.replace(tc_match.group(0), "").strip()
                except Exception:
                    pass

        # <think>...</think> 블록은 history에 남기지 않음
        visible_content = re.sub(r'<think>.*?</think>', '', msg.content or '', flags=re.DOTALL)
        visible_content = re.sub(r'</think>', '', visible_content).strip()

        assistant_entry = {"role": "assistant", "content": visible_content}
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
            final_response = visible_content
            break

        for tc in parsed_tool_calls:
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            if debug:
                print(f"[Tool call] {tc.function.name}({tool_args})")

            tool_result = dispatch(tc.function.name, tool_args, agent_state)

            if debug:
                print(f"[Tool result] {json.dumps(tool_result, ensure_ascii=False)[:200]}")

            messages.append({
                "role": "tool",
                "content": json.dumps(tool_result, ensure_ascii=False),
                "tool_call_id": tc.id,
            })
    else:
        # MAX_AGENT_ROUNDS 소진 — 마지막 assistant content 반환 (tool 메시지면 빈 문자열)
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                final_response = msg["content"]
                break
        else:
            final_response = ""

    return {
        "response": final_response,
        "chat_history": messages[1:],
        "agent_state": agent_state,
        "last_result": agent_state.get("last_result")
    }
