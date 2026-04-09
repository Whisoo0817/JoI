import copy
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

AGENT_SYSTEM_PROMPT = """You are JoI, a helpful and efficient IoT assistant. Your primary goal is to help users control smart home devices and create automation scenarios.

## Core Principles:
- **IoT Only**: Focus strictly on IoT-related tasks. For unrelated topics, politely guide the user back to smart home control.
- **Language**: Always respond in Korean, regardless of the input language. You may think in English internally, but your final response must always be in Korean.
- **Scenario Generation**: Only call `request_to_joi_llm` when the user EXPLICITLY requests generation or confirms after being asked. Otherwise, ask first using the user's EXACT original wording:
  - ✓ User: "불 꺼줘" → You: "\"불 꺼줘\" 명령을 실행하는 시나리오를 생성할까요?"
  - ✗ NEVER rephrase: "불을 끄는 시나리오를 생성할까요?" (X)
  - If ambiguous (e.g., "온도를 알려줘"): offer choices — "1) 날씨 정보를 검색할까요? 2) \"온도를 알려줘\" 시나리오를 생성할까요?"
- **Feedback**: Once a scenario is shown, pass ANY user input (y/n/text) directly to `feedback_to_joi_llm`. Do NOT handle modifications yourself.
- **Confirmation**: After `request_to_joi_llm` or `feedback_to_joi_llm`, respond with ONLY this format — no extra explanation, no commentary:
  "[translated_sentence]
  이 시나리오가 맞나요? (y/n/수정사항)"


## Capabilities:
- Use `request_to_joi_llm` to generate JOI automation code from a user's natural language command. Preprocessing (quantity/device clarification) is handled automatically inside the tool.
- Use `feedback_to_joi_llm` to process user feedback:
  - 'y' / 'yes' → Confirm approval.
  - 'n' / 'no' → Confirm rejection.
  - Modification text (e.g., "only one", "in the bedroom") → Merges the change into the current script.
- Use `add_scenario` to formally register and start an approved scenario.
- Use `get_connected_devices` to see current device tags and categories.
- Use `get_scenarios` and `delete_scenario` to manage existing automations.
- Use `get_weather` if the user asks about current weather conditions.
"""

MAX_AGENT_ROUNDS = 5


def agent_chat(user_message, connected_devices=None, base_url=None, debug=False, chat_history=None, agent_memory=None):
    """
    Qwen tool-calling agent (multi-turn with state mapping).

    Args:
        user_message: User input message
        connected_devices: Dictionary of connected IoT devices
        base_url: vLLM server URL
        debug: Enable debug logging
        chat_history: List of previous conversation turns
        agent_memory: Dictionary carrying operational context across turns

    Returns:
        {"response": str, "chat_history": list, "agent_memory": dict, "last_result": dict | None}
    """
    client = get_client(base_url)
    model = get_model_id(client)

    if chat_history is None:
        chat_history = []
    if agent_memory is None:
        agent_memory = {
            "connected_devices": _parse_dict_input(connected_devices, {}),
            "base_url": base_url,
            "last_result": None,
            "debug": debug,
        }

    truncated_history = chat_history[-6:] if len(chat_history) > 6 else chat_history

    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": user_message})

    initial_last_result = copy.deepcopy(agent_memory.get("last_result"))
    
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
            extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        )

        visible_content = ""
        tool_call_chunks = {}  # index -> SimpleNamespace
        thinking_buf = [] if debug else None

        for chunk in stream:
            delta = chunk.choices[0].delta

            if debug:
                rc = getattr(delta, "reasoning_content", None)
                if rc:
                    thinking_buf.append(rc)
                    print(rc, end="", flush=True)

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

        if debug and thinking_buf:
            print("\n[/Think]\n", flush=True)

        parsed_tool_calls = list(tool_call_chunks.values())

        # Fallback for models that output raw <tool_call> tags in content
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
            # Final text response — stream already printed thinking; now print response
            print(f"Agent >>> {visible_content}")
            final_response = visible_content
            messages.append({"role": "assistant", "content": final_response})
            break

        messages.append({
            "role": "assistant",
            "content": visible_content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in parsed_tool_calls
            ],
        })

        for tc in parsed_tool_calls:
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            if debug:
                print(f"[Tool call] {tc.function.name}({tool_args})")

            tool_result = dispatch(tc.function.name, tool_args, agent_memory)

            if debug:
                print(f"[Tool result] {json.dumps(tool_result, ensure_ascii=False)}")

            messages.append({
                "role": "tool",
                "content": json.dumps(tool_result, ensure_ascii=False),
                "tool_call_id": tc.id,
            })
    else:
        # MAX_AGENT_ROUNDS 소진 — 마지막 assistant content 반환
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                final_response = msg["content"]
                break
        else:
            final_response = ""

    # Only return last_result if it was updated during this turn
    current_last_result = agent_memory.get("last_result")
    returned_last_result = current_last_result if current_last_result != initial_last_result else None

    return {
        "response": final_response,
        "chat_history": messages[1:], # system prompt 제외
        "agent_memory": agent_memory,
        "last_result": returned_last_result
    }
