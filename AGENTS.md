# Joi Code: Specification and AI Pipeline

This document defines the Joi automation language and the AI pipeline used to generate it.

---

## 1. What is Joi Code?
Joi is a Domain-Specific Language (DSL) specifically designed for IoT automation. It is evaluated in a persistent, ticking environment on an IoT hub.

### ⚛️ 1.1 JSON Metadata (The Wrap)
A Joi automation is typically delivered as a JSON object containing metadata and the script itself.

```json
{
  "name": "morning_routine",
  "cron": "0 7 * * *",
  "period": 300000,
  "code": "if (any(#Light).Switch == true) { (#Light).Off() }"
}
```
*   **`name`**: Scenario identifier, auto-generated from the English re-translation of the command (lowercased, spaces → `_`).
*   **`cron`**: Standard cron expression for scheduled triggers (e.g., `0 7 * * *` for 7 AM daily). If empty, the script is event-driven or manually triggered.
*   **`period` (milliseconds)**: Defines the polling/re-execution interval.
    *   `-1`: NO_SCHEDULE (one-shot, event-driven; no periodic re-execution).
    *   `N > 0`: The script re-executes every N milliseconds to poll for state changes.
*   **`code`**: The actual Joi logic string.

### ⚛️ 1.2 State Management: `:=` vs `=`
Joi scripts are executed repeatedly (if `period > 0`). 

*   **Initialization (`:=`)**: Values are assigned **ONLY ONCE** during the very first execution tick. Use this for persistent flags or counters.
    *   Example: `triggered := false`
*   **Assignment (`=`)**: Values are updated on **EVERY TICK**.
    *   Example: `count = count + 1`

### ⚛️ 1.3 Device Mapping: The Power of Tags
Devices are not targeted by hardcoded IDs in Joi. Instead, they are selected via **Tags** (e.g., `#Office`, `#Entrance`, `#Light`). These tags are resolved at runtime by the IoT hub.

*   **Single Selector `(#Tag)`**: Targets a specific device instance matching the tag.
    *   `(#DeskLamp).On()`
*   **Group Action `all(#Tag)`**: Executes a command on every device that has the specified tag.
    *   `all(#Light).Off()` — Turns off every device tagged with `#Light`.
*   **Conditional Evaluation `any(#Tag)`**: Checks if *at least one* device in the tagged group satisfies a condition.
    *   `if (any(#Sensor).Contact == true)` — Triggers if any entrance sensor is open.
*   **Tag Aliasing**: Multiple tags can be used to narrow down targets (e.g., `#Office` + `#Light`).

### ⚛️ 1.4 Temporal and Logic Constructs
*   **`delay(N UNIT)`**: Pauses the script flow without blocking the hub's other tasks.
    *   Units: `SEC`, `MIN`, `HOUR`.
    *   Example: `delay(5 MIN)`
*   **`wait until (Condition)`**: Pauses execution until a specific event or state transition occurs.
    *   Example: `wait until (any(#Motion).Motion == true)`
*   **Quantifier Comparison (`==|`, `>=|`, etc.)**: Special operators used with `any` to evaluate collection states.
    *   `any(#Light).Brightness >=| 80` (Is any light brighter than 80%?)

---

## 2. Input Data: Connected Devices Format
The AI uses the `connected_devices` metadata to resolve tags and categories.

**Example Structure:**
```json
{
  "device_id_001": {
    "category": ["ContactSensor"],
    "tags": ["Entrance", "Door", "ContactSensor"]
  },
  "device_id_002": {
    "category": ["Switch", "Light"],
    "tags": ["Office", "MainLight", "Light", "Switch"]
  }
}
```

---

## 3. Joi Code Generation Pipeline (Multi-Stage Funnel)
To ensure accuracy in local small models, the generation process is segmented into a multi-stage context funnel.

### ❇️ Stage 1: Pre-processing (Translation & Merging)
*   **목표**: 사용자 입력 명령어를 표준 영어로 정제하고 이전 피드백과 병합.
*   **예시**:
    *   *입력 (KOR)*: "문이 닫히면 사무실 불을 꺼줘"
    *   *입력 (Modification)*: "3초 뒤에 꺼줘"
    *   *결과 (Merged ENG)*: "If the door is closed, turn off the office light after 3 seconds."

### ❇️ Stage 2-1: Category Mapping (`connect_mapping_category`)
*   **Goal**: Identify necessary device categories from the `connected_devices` list to reduce context overhead.
*   **Example**:
    *   *Input*: "If the door is closed, turn off the office light..."
    *   *Output (JSON)*:
        ```json
        {
          "ContactSensor": "Verify if the door is closed",
          "Light": "Executing the turn-off command for office"
        }
        ```

### ❇️ Stage 2-2: Device-Specific Service Mapping (`intent_{dev}`)
*   **Goal**: Extract specific service methods for each category. Supports dynamic sub-component (Switch/Level/Color) injection.
*   **Example**:
    *   *Input for Light*: "Executing the turn-off command for office"
    *   *Prompt Logic*: Inject `switch.md` template -> replace `Switch` with `Light`.
    *   *Output (JSON)*: `["Light.Off", "ContactSensor.Contact"]`

### ❇️ Stage 2-3: Precision Mapping & Quantifier Integration (`connect_mapping_precision`)
*   **Goal**: Map identified intents to specific device Tags and determine Quantifiers (`SINGLE`, `ALL`, `ANY`).
*   **Example**:
    *   *Input*: `["Light.Off", "ContactSensor.Contact"]` + Full Device Metadata.
    *   *Output (Mapping)*: 
        *   `any(#Entrance).Contact == true` (Quantifier: `ANY`, Tag: `#Entrance`)
        *   `(#Office).Off()` (Quantifier: `SINGLE`, Tag: `#Office`)

### ❇️ Stage 3: Routing & Targeted Generation
*   **Goal**: Route the metadata and mapping results to a specialized JoI template (`NO_SCHEDULE`, `SCHEDULED`, or `DURATION`) for final script output.
*   **Example**:
    *   *Route*: `NO_SCHEDULE` (Snapshot check with delay).
    *   *Reasoning Trace*: "<Reasoning> Check Entrance Contact state -> True? -> Wait 3s -> Turn off Office Light </Reasoning>"
    *   *Final Code*:
        ```javascript
        if (any(#Entrance).Contact == true) {
          delay(3 SEC)
          (#Office).Off()
        }
        ```

---

## 4. Agent Chat API
A conversational interface for multi-turn IoT automation.

### ⚛️ 4.1 Stateful Architecture & Session DB
`agent_chat` 함수는 **Stateful(상태유지)**로 설계됨. 서버는 사용자의 대화 기록과 기기 상태를 로컬 SQLite DB(`data/joi.db`)에 저장함. 클라이언트는 복잡한 대화 내역(`context`)을 들고 다닐 필요 없이 `session_id`만 전달하면 됨.

*   **세션 데이터 흐름**:
    1. 클라이언트가 `session_id`와 함께 메시지 전달.
    2. 서버가 DB에서 해당 세션의 `chat_history`, `last_result`, `connected_devices` 로드.
    3. 에이전트가 내부적으로 상태를 조립하여 연산 수행.
    4. 연산 완료 후 업데이트된 내역을 DB에 다시 저장.

### ⚛️ 4.2 KV Prefix Caching 최적화
vLLM 서버의 **Prefix Caching** 성능을 극대화하기 위해 다음과 같은 전략을 사용함.

1.  **Fixed System Prompt at Index 0**: 모든 요청의 `messages[0]`에 동일한 `AGENT_SYSTEM_PROMPT`를 배치하여 KV Cache의 공통 접두사를 유지함.
2.  **Context Slicing**: 대화가 길어질 경우 DB에서 로드한 전체 히스토리 중 `chat_history[-10:]`로 슬라이싱하여 컨텍스트 윈도우를 안정적으로 관리함.
3.  **Header-first logic**: 시스템 지침을 가장 먼저 배치하여 지시사항 이행력을 높이고 캐시 재사용률을 높임.

### ⚛️ 4.3 Tool-Calling Workflow
1. **Eval**: Assistant thinking `<think>` ... `</think>` (내부 추론, 사용자에게 노출 안 됨).
2. **Tool Call**: Invokes `request_to_joi_llm` to trigger the stage-based pipeline.
3. **Confirm**: Displays the result and asks "Is this correct? (y/n/mod)".
4. **Action**: Depending on `y` or `n`, calls `feedback_to_joi_llm` or `add_scenario`.

### ⚛️ 4.4 Available Tools

| Tool | 설명 |
|------|------|
| `request_to_joi_llm` | 자연어 명령 → Joi 코드 생성 파이프라인 호출 |
| `add_scenario` | 승인된 시나리오를 Hub Controller에 등록 |
| `get_connected_devices` | 현재 연결된 IoT 디바이스 목록 조회 |
| `get_thing_details` | 특정 디바이스의 함수/값 상세 조회 |
| `get_scenarios` | 등록된 시나리오 목록 조회 |
| `get_scenario_details` | 특정 시나리오의 JoI 스크립트 상세 조회 |
| `get_current_values` | 특정 디바이스의 실시간 센서값 조회 |
| `get_value_history` | 특정 디바이스 속성의 히스토리 조회 |
| `get_locations` | 등록된 위치(방) 목록 조회 |
| `control_thing_directly` | 시나리오 없이 디바이스 즉시 제어 |
| `start_scenario` | 등록된 시나리오 활성화 |
| `stop_scenario` | 실행 중인 시나리오 비활성화 |
| `manage_thing_tags` | 디바이스 태그 추가/제거 |

대화 세션 정보는 `joi-agent` 서버의 SQLite DB(`data/sessions.db`)에 저장됩니다.

```
sessions 테이블
  session_id  - PK, 세션 식별자
  user_id     - 사용자 식별자
  title       - 세션 제목 (첫 메시지에서 자동 생성)
  created_at  - 생성 시각
  updated_at  - 마지막 업데이트 시각

messages 테이블
  id          - 고유 ID
  session_id  - FK → sessions
  sender      - "user" | "agent"
  content     - 메시지 내용 (JSON 직렬화)
  created_at  - 저장 시각
```

*   `session_id`를 지정하지 않으면 자동 생성.
*   시나리오 등록은 `add_scenario` 툴 → MCP 서버 → Hub Controller로 직접 전달.

---

## 5. Performance Optimization
*   **Lost-in-the-Middle Mitigation**: Context filtering ensures the model never sees irrelevant hardware schemas.
*   **Local LLM Ready**: Specifically tuned for Qwen-9B/Llama-8B class models running locally.
*   **Self-Correction**: Python backend catches schema errors and loops back to the model for retries.
