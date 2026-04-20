import json
import random
import re
import uuid
from types import SimpleNamespace

from config import get_client, get_model_id
from run_local import _parse_dict_input
import os
from tools import call_mcp_tool_sync, AGENT_TOOLS, error_hint, summarize_tool_result


_AUX_CATEGORIES = {"Switch", "LevelControl", "ColorControl", "RotaryControl"}

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


AGENT_SYSTEM_PROMPT = """You are JoI, a helpful and efficient IoT assistant. Your primary goal is to help users manage their smart home.

## Core Principles (CRITICAL):
- **NEVER PROVIDE AN EMPTY RESPONSE**: You MUST ALWAYS output a natural language response to the user, even after calling a tool. If a tool was successful, confirm it to the user.
- **Language**: 반드시 한국어로만 답변하세요. 중국어, 일본어, 영어 등 다른 언어는 절대 사용하지 마세요.
- **IoT Only**: Focus strictly on IoT-related tasks.
- **Example Commands**: When showing examples, use ONLY the exact list provided in "## Example Commands" below — copy them verbatim. NEVER invent, paraphrase, or add examples outside that list. If the list is empty, do not show any examples.

## Capabilities & Tools Usage:
- **Immediate Action**: If user wants to do something "now" (e.g. "불 켜줘", "에어컨 꺼"), use `control_thing_directly`.
- **Automation (Scenario)**: If user wants something scheduled or event-driven (e.g. "매일 아침 7시에", "문이 열리면"), use the `request_to_joi_llm` -> `add_scenario` flow.
- **Monitoring**: Use `get_current_values` for real-time status and `get_value_history` for historical data or trends.
- **Device Management**: Use `get_connected_devices` for all devices overview, `get_thing_details` for one specific device's functions/values, and `manage_thing_tags` to organize devices.
- **Scenario Management**: Use `get_scenarios` to list, `start_scenario`/`stop_scenario` to toggle, and `get_scenario_details` to inspect.
- **External Info**: Use `get_weather` for weather and air quality info.

## Guidelines for Tools:
- **Direct Control confirmation**: After calling `control_thing_directly`, confirm the result to the user.
- **Data Interpretation**: When using `get_value_history` or `get_current_values`, interpret the data for the user (e.g. "현재 온도는 25도이며, 지난 1시간 동안 일정하게 유지되었습니다").
- **JOI LLM Flow**:
  - After "confirmation_needed", use the format: "[translated_sentence]\\n이 시나리오가 맞나요? (y/n/수정사항)"
  - If user approves ('y'), call `add_scenario`. If user requests modification, call `request_to_joi_llm` again with the updated command.
  - If rejected ('n'), respond with ONLY: "생성된 시나리오 등록을 거부했습니다. 어떤 것을 도와드릴까요?"

## 자기소개 시:
JoI 에이전트로서 (1) 기기 직접 제어, (2) JOI 언어를 활용한 자동화 시나리오 생성, (3) 센서 데이터 및 이력 모니터링, (4) 등록된 시나리오 관리가 가능하다고 한 문단으로 간결하게 소개하세요.
"""

MAX_AGENT_ROUNDS = 5


def agent_chat_stream(user_message, session_id="default", connected_devices=None, base_url=None, on_complete=None, on_tool_call=None):

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
        "connected_devices": devices,
        "base_url": base_url,
        "last_result": last_result,
        "last_result_updated": False,

        "session_id": session_id,
    }

    # history truncation: DB 요약본 기준 글자 수로 토큰 추정, 턴 단위 제거
    HISTORY_TOKEN_LIMIT = 4000
    truncated_history = list(chat_history)
    history_token_est = sum(len(json.dumps(m, ensure_ascii=False)) for m in truncated_history) // 2
    while history_token_est > HISTORY_TOKEN_LIMIT and len(truncated_history) > 0:
        first_user = next((i for i, m in enumerate(truncated_history) if m["role"] == "user"), None)
        if first_user is None:
            break
        next_user = next((i for i, m in enumerate(truncated_history) if i > first_user and m["role"] == "user"), len(truncated_history))
        removed = truncated_history[:next_user]
        truncated_history = truncated_history[next_user:]
        history_token_est -= sum(len(json.dumps(m, ensure_ascii=False)) for m in removed) // 2

    # system prompt 빌드
    present_cats = []
    for dev in (devices or {}).values():
        for cat in dev.get("category", []):
            if cat not in _AUX_CATEGORIES and cat not in present_cats and cat in _CATEGORY_EXAMPLES:
                present_cats.append(cat)
    sampled = random.sample(present_cats, min(3, len(present_cats)))
    example_lines = "\n".join(f"- {_CATEGORY_EXAMPLES[c]}" for c in sampled)
    example_section = f"\n\n## Example Commands (use ONLY these when showing examples):\n{example_lines}" if example_lines else ""

    device_section = ""
    if devices:
        device_lines = "\n".join(
            f"- {v.get('nickname') or k} (id={k}, category={v.get('category', '')}, tags={v.get('tags', '')})"
            for k, v in devices.items()
        )
        device_section = f"\n\n## 현재 연결된 디바이스:\n{device_lines}\n사용자는 닉네임, 태그, 카테고리 등 어떤 방식으로든 디바이스를 지칭할 수 있습니다. 위 목록에서 매핑하여 tool 호출 시 id(UUID)를 사용하세요. 절대 사용자에게 UUID를 물어보지 마세요. get_connected_devices는 functions/values 상세 정보가 필요할 때만 호출하세요."

    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT + example_section + device_section}]
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": user_message})

    original_len = len(chat_history)
    truncated_len = len(truncated_history)

    final_response = ""
    token_log_buf = []
    if original_len != truncated_len:
        token_log_buf.append(f"  [HISTORY] trimmed {original_len - truncated_len} msgs")
    round_num = 0

    for _ in range(MAX_AGENT_ROUNDS):
        clean_messages = [{k: v for k, v in m.items() if k != "_tool_name"} for m in messages]
        stream = client.chat.completions.create(
            model=model,
            messages=clean_messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            temperature=0.4,
            max_tokens=4096,
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

        round_num += 1
        if usage:
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            token_log_buf.append(
                f"  [Round {round_num}] prompt={prompt_tokens}/16384 ({prompt_tokens/16384*100:.1f}%)"
                f"  completion={completion_tokens}"
            )


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
            if not visible_content:
                # thinking만 하고 텍스트 응답을 생성하지 않은 경우 — 재시도
                messages.append({"role": "assistant", "content": ""})
                messages.append({"role": "user", "content": "결과를 사용자에게 한국어로 알려주세요."})
                continue
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
                "_tool_name": tc.function.name,
            })

            if tool_result.get("error"):
                messages.append({"role": "user", "content": error_hint(tool_result)})
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

    updated_history = []
    for m in messages[1:]:
        tool_name = m.pop("_tool_name", None)
        if tool_name:
            updated_history.append(summarize_tool_result(tool_name, m))
        else:
            updated_history.append(m)
    _db.save_session(session_id, updated_history, context.get("last_result"), devices)

    updated_result = context.get("last_result") if context.get("last_result_updated") else None

    if token_log_buf:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs", f"{session_id.replace('/', '_').replace('..', '_')}.log")
        with open(log_path, "a", encoding="utf-8") as _f:
            _f.write(f"  [TOKENS]\n" + "\n".join(token_log_buf) + "\n")

    if on_complete:
        on_complete(final_response, updated_result)

    if updated_result and "log" in updated_result:
        client_result = {**updated_result, "log": {k: v for k, v in updated_result["log"].items() if k != "logs"}}
    else:
        client_result = updated_result

    yield f"data: [DONE] {json.dumps({'last_result': client_result}, ensure_ascii=False)}\n\n"
