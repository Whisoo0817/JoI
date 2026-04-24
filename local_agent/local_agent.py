"""LocalAgentManager: Qwen3 9B ReAct loop wrapped in JOIAgentManager-compatible interface."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import sys
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from agent.tools import call_mcp_tool_sync, AGENT_TOOLS, error_hint, summarize_tool_result
from agent.config import get_client, get_model_id

# ── Constants ─────────────────────────────────────────────────
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8002/v1")
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8100/mcp")
MAX_AGENT_ROUNDS = 5


def set_mcp_server_url(url: str):
    """Override MCP server URL at runtime (matches joi_agent interface)."""
    import tools as _tools_module
    os.environ["MCP_SERVER_URL"] = url
    # tools.py reads MCP_SERVER_URL from env at call time, so setting env is enough
HISTORY_TOKEN_LIMIT = 4000

_AUX_CATEGORIES = {"Switch", "LevelControl", "ColorControl", "RotaryControl"}

_CATEGORY_EXAMPLES = {
    "Light":              "오전 8시에 조명을 꺼줘",
    "AirConditioner":     "오후 2시에 에어컨을 켜줘",
    "Plug":               "1시간 뒤에 플러그를 꺼줘",
    "Humidifier":         "2시간마다 가습기를 켜줘",
    "Dehumidifier":       "오전 9시에 제습기를 켜줘",
    "AirPurifier":        "30분마다 공기청정기를 껐다 켜줘",
    "RobotVacuumCleaner": "매일 오전 10시에 로봇청소기를 켜줘",
    "Television":         "오후 11시에 TV를 꺼줘",
    "Speaker":            "1시간마다 스피커로 인사해줘",
    "DoorLock":           "오후 10시에 도어락을 잠궈줘",
    "Door":               "문이 열리면 잠궈줘",
    "Blind":              "오전 7시에 블라인드를 올려줘",
    "Shade":              "오후 9시에 커튼을 닫아줘",
    "Window":             "창문이 열려있으면 닫아줘",
    "Valve":              "1시간마다 밸브를 열었다가 닫아줘",
    "Siren":              "버튼이 눌리면 사이렌을 켜줘",
    "TemperatureSensor":  "온도가 28도 이상이 되면 알려줘",
    "HumiditySensor":     "습도가 70% 이상이면 알려줘",
    "PresenceSensor":     "사람이 감지될 때마다 조명을 켜줘",
    "ContactSensor":      "문이 열릴 때마다 알려줘",
    "MultiButton":        "2번 버튼이 눌릴 때마다 조명을 토글해줘",
    "Button":             "버튼이 눌리면 에어컨을 켜줘",
    "MotionSensor":       "움직임이 감지되면 조명을 켜줘",
    "LeakSensor":         "누수가 감지되면 밸브를 잠궈줘",
    "Camera":             "카메라로 사진을 찍어줘",
    "DimmerSwitch":       "디머 스위치를 누르면 조명 밝기를 50으로 설정해줘",
    "TapDialSwitch":      "탭다이얼 스위치를 돌리면 조명 밝기를 조절해줘",
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


def _build_system_prompt(devices: Dict[str, Any]) -> str:
    """Build system prompt with device section and example commands."""
    present_cats = []
    for dev in (devices or {}).values():
        for cat in dev.get("category", []):
            if cat not in _AUX_CATEGORIES and cat not in present_cats and cat in _CATEGORY_EXAMPLES:
                present_cats.append(cat)

    sampled = random.sample(present_cats, min(3, len(present_cats)))
    example_lines = "\n".join(f"- {_CATEGORY_EXAMPLES[c]}" for c in sampled)
    example_section = (
        f"\n\n## Example Commands (use ONLY these when showing examples):\n{example_lines}"
        if example_lines
        else ""
    )

    device_section = ""
    if devices:
        device_lines = "\n".join(
            f"- {v.get('nickname') or k} (id={k}, category={v.get('category', '')}, tags={v.get('tags', '')})"
            for k, v in devices.items()
        )
        device_section = (
            f"\n\n## 현재 연결된 디바이스:\n{device_lines}\n"
            "사용자는 닉네임, 태그, 카테고리 등 어떤 방식으로든 디바이스를 지칭할 수 있습니다. "
            "위 목록에서 매핑하여 tool 호출 시 id(UUID)를 사용하세요. "
            "절대 사용자에게 UUID를 물어보지 마세요. "
            "get_connected_devices는 functions/values 상세 정보가 필요할 때만 호출하세요."
        )

    return AGENT_SYSTEM_PROMPT + example_section + device_section


def _truncate_history(chat_history: List[Dict]) -> List[Dict]:
    """Truncate history to fit within token limit (turn-level removal)."""
    truncated = list(chat_history)
    token_est = sum(len(json.dumps(m, ensure_ascii=False)) for m in truncated) // 2
    while token_est > HISTORY_TOKEN_LIMIT and truncated:
        first_user = next((i for i, m in enumerate(truncated) if m["role"] == "user"), None)
        if first_user is None:
            break
        next_user = next(
            (i for i, m in enumerate(truncated) if i > first_user and m["role"] == "user"),
            len(truncated),
        )
        removed = truncated[:next_user]
        truncated = truncated[next_user:]
        token_est -= sum(len(json.dumps(m, ensure_ascii=False)) for m in removed) // 2
    return truncated


class LocalAgentManager:
    """Qwen3 9B ReAct loop, compatible with JOIAgentManager interface."""

    def __init__(self):
        # JOIAgentManager-compatible attributes
        self.tool_executions: Dict[str, List[Dict]] = {}
        self.session_data: Dict[str, Dict] = {}
        self.session_languages: Dict[str, str] = {}
        self.session_id: Optional[str] = None
        self.joi_llm_model: Optional[str] = None

        # Internal state
        self._llm_histories: Dict[str, List[Dict]] = {}   # LLM context per session
        self._device_cache: Dict[str, Dict] = {}           # devices per session

    async def ainit(self):
        logger.info(f"[LocalAgent] Initializing with LLM_BASE_URL={LLM_BASE_URL}")
        try:
            client = get_client(LLM_BASE_URL)
            model = get_model_id(client)
            logger.info(f"[LocalAgent] LLM model: {model}")
        except Exception as e:
            logger.warning(f"[LocalAgent] LLM not reachable at startup: {e}")

    async def aclose(self):
        self._llm_histories.clear()
        self._device_cache.clear()
        self.tool_executions.clear()
        self.session_data.clear()

    def get_session_summary(self, session_id: str) -> str:
        """Return a brief summary of recent conversation for the session title."""
        history = self._llm_histories.get(session_id, [])
        user_msgs = [m["content"] for m in history if m.get("role") == "user" and m.get("content")]
        if not user_msgs:
            return ""
        return user_msgs[0][:50] if user_msgs else ""

    def _get_devices(self, session_id: str) -> Dict[str, Any]:
        """Load devices from cache; fetch from MCP if not cached."""
        if session_id in self._device_cache:
            return self._device_cache[session_id]

        logger.info(f"[LocalAgent] Fetching devices for session {session_id}")
        try:
            result = call_mcp_tool_sync("get_connected_devices", {}, {})
            logger.info(f"[LocalAgent] get_connected_devices raw result type={type(result)}: {str(result)[:200]}")
            if isinstance(result, dict) and "error" not in result:
                # 값이 dict인 항목만 남김 (int/str 등 잘못된 값 방어)
                devices = {k: v for k, v in result.items() if isinstance(v, dict)}
                self._device_cache[session_id] = devices
                logger.info(f"[LocalAgent] Loaded {len(devices)} devices for session {session_id}")
                return devices
        except Exception as e:
            logger.warning(f"[LocalAgent] get_connected_devices failed: {e}")
        return {}

    def _run_agent_sync(
        self,
        query: str,
        session_id: str,
        joi_llm_model: Optional[str],
        voice_mode: bool,
        event_queue: "asyncio.Queue",
        loop: asyncio.AbstractEventLoop,
    ):
        """
        Sync ReAct loop. Runs in a thread.
        Puts SimpleNamespace(event, content) objects into event_queue.
        Sentinel None signals completion.
        """
        def emit(event_type: str, content: str):
            ns = SimpleNamespace(event=event_type, content=content)
            loop.call_soon_threadsafe(event_queue.put_nowait, ns)

        def done():
            loop.call_soon_threadsafe(event_queue.put_nowait, None)

        try:
            client = get_client(LLM_BASE_URL)
            model = get_model_id(client)

            # Load history and devices
            chat_history = list(self._llm_histories.get(session_id, []))
            devices = self._get_devices(session_id)

            context = {
                "last_result": self.session_data.get(session_id, {}).get("joi_llm_result"),
                "last_result_updated": False,
                "session_id": session_id,
                "joi_llm_model": joi_llm_model,
            }

            if voice_mode:
                query = f"[VOICE_MODE] {query}"

            truncated_history = _truncate_history(chat_history)
            system_prompt = _build_system_prompt(devices)

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(truncated_history)
            messages.append({"role": "user", "content": query})

            # Init tool_executions for this session
            if session_id not in self.tool_executions:
                self.tool_executions[session_id] = []

            final_response = ""
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
                tool_call_chunks: Dict[int, SimpleNamespace] = {}

                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if delta.content:
                        visible_content += delta.content
                        emit("RunContent", delta.content)

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_call_chunks:
                                tool_call_chunks[idx] = SimpleNamespace(
                                    id=tc.id or f"call_{uuid.uuid4().hex[:8]}",
                                    type="function",
                                    function=SimpleNamespace(name="", arguments=""),
                                )
                            if tc.function.name:
                                tool_call_chunks[idx].function.name += tc.function.name
                            if tc.function.arguments:
                                tool_call_chunks[idx].function.arguments += tc.function.arguments

                round_num += 1
                parsed_tool_calls = list(tool_call_chunks.values())

                # Fallback: <tool_call> XML tags
                if not parsed_tool_calls and "<tool_call>" in visible_content:
                    tc_match = re.search(r"<tool_call>\s*({.*?})\s*</tool_call>", visible_content, re.DOTALL)
                    if tc_match:
                        try:
                            tc_json = json.loads(tc_match.group(1))
                            func_obj = SimpleNamespace(
                                name=tc_json["name"],
                                arguments=json.dumps(tc_json.get("arguments", {})),
                            )
                            parsed_tool_calls = [
                                SimpleNamespace(
                                    id=f"call_{uuid.uuid4().hex[:8]}",
                                    type="function",
                                    function=func_obj,
                                )
                            ]
                            visible_content = visible_content.replace(tc_match.group(0), "").strip()
                        except Exception:
                            pass

                visible_content = visible_content.strip()

                if not parsed_tool_calls:
                    if not visible_content:
                        messages.append({"role": "assistant", "content": ""})
                        messages.append({"role": "user", "content": "결과를 사용자에게 한국어로 알려주세요."})
                        continue
                    final_response = visible_content
                    messages.append({"role": "assistant", "content": final_response})
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": visible_content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                            }
                            for tc in parsed_tool_calls
                        ],
                    }
                )

                for tc in parsed_tool_calls:
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Inject session-level args for joi_llm tools
                    if tc.function.name in ("request_to_joi_llm", "feedback_to_joi_llm"):
                        tool_args["user_id"] = session_id
                        tool_args["selected_model"] = joi_llm_model

                    # Track tool start
                    exec_entry = {
                        "tool_name": tc.function.name,
                        "result": None,
                        "status": "started",
                        "arguments": tool_args,
                        "emitted": False,
                    }
                    self.tool_executions[session_id].append(exec_entry)

                    tool_result = call_mcp_tool_sync(tc.function.name, tool_args, context)

                    # Track tool completion
                    exec_entry["result"] = tool_result
                    exec_entry["status"] = "completed"

                    # Cache joi_llm result for feedback/add_scenario
                    if tc.function.name in ("request_to_joi_llm", "feedback_to_joi_llm"):
                        if isinstance(tool_result, dict):
                            if session_id not in self.session_data:
                                self.session_data[session_id] = {}
                            self.session_data[session_id]["joi_llm_result"] = tool_result
                            context["last_result"] = tool_result
                            context["last_result_updated"] = True

                    messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(tool_result, ensure_ascii=False),
                            "tool_call_id": tc.id,
                            "_tool_name": tc.function.name,
                        }
                    )

                    if tool_result.get("error"):
                        messages.append({"role": "user", "content": error_hint(tool_result)})
            else:
                for msg in reversed(messages):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        final_response = msg["content"]
                        break
                if not final_response:
                    final_response = "명령을 수행했습니다."

            # Save LLM history
            updated_history = []
            for m in messages[1:]:  # skip system
                tool_name = m.pop("_tool_name", None)
                updated_history.append(summarize_tool_result(tool_name, m) if tool_name else m)
            self._llm_histories[session_id] = updated_history

        except Exception as e:
            logger.error(f"[LocalAgent] ReAct loop error: {e}", exc_info=True)
            emit("RunContent", f"\n오류가 발생했습니다: {e}")
        finally:
            done()

    async def _stream_events(
        self,
        query: str,
        session_id: Optional[str],
        joi_llm_model: Optional[str],
        voice_mode: bool,
    ):
        """Async generator that streams RunContent events from the sync ReAct loop."""
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        thread_task = loop.run_in_executor(
            None,
            self._run_agent_sync,
            query,
            session_id,
            joi_llm_model,
            voice_mode,
            queue,
            loop,
        )

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

        await thread_task

    async def run_joi_agent(
        self,
        query: str,
        stream: bool = True,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        joi_llm_model: Optional[str] = None,
        voice_mode: bool = False,
    ):
        """
        Called with `await` by main.py — returns an async generator.
        main.py then does `async for event in response_stream`.
        """
        self.session_id = session_id
        self.joi_llm_model = joi_llm_model
        return self._stream_events(query, session_id, joi_llm_model, voice_mode)
