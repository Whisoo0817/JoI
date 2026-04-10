# Joi Code: Specification and AI Pipeline

This document defines the Joi automation language and the AI pipeline used to generate it.

---

## 1. What is Joi Code?
Joi is a Domain-Specific Language (DSL) specifically designed for IoT automation. It is evaluated in a persistent, ticking environment on an IoT hub.

### ⚛️ 1.1 JSON Metadata (The Wrap)
A Joi automation is typically delivered as a JSON object containing metadata and the script itself.

```json
{
  "name": "Morning Routine",
  "cron": "0 7 * * *",
  "period": 300000,
  "script": "if (any(#Light).Switch == true) { (#Light).Off() }"
}
```
*   **`cron`**: Standard cron expression for scheduled triggers (e.g., `0 7 * * *` for 7 AM daily). If empty, the script is event-driven or manually triggered.
*   **`period` (milliseconds)**: Defines the polling/re-execution interval. 
    *   `0`: Runs exactly once.
    *   `N > 0`: The script re-executes every N milliseconds to poll for state changes.
*   **`script`**: The actual Joi logic string.

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

### ⚛️ 4.3 Available Tools

| Tool | 설명 |
|------|------|
| `request_to_joi_llm` | 자연어 명령 → Joi 코드 생성 파이프라인 호출 |
| `feedback_to_joi_llm` | 사용자 피드백 처리 (`y` / `n` / 수정사항 텍스트) |
| `add_scenario` | 승인된 시나리오를 Hub Controller에 등록 + 로컬 DB 저장 |
| `get_scenarios` | 로컬 DB에 저장된 시나리오 목록 조회 (id, command, translated, created_at) |
| `delete_scenario` | 시나리오 ID로 로컬 DB에서 삭제 |
| `get_connected_devices` | 현재 연결된 IoT 디바이스 목록 조회 |
| `get_weather` | 지역명으로 현재 날씨 조회 (wttr.in, 네트워크 필요) |

승인된 시나리오 및 대화 세션 정보는 `joi/data/joi.db` (SQLite)에 저장됩니다.

```
scenarios 테이블 (승인된 자동화 기록)
  id          - 고유 ID
  session_id  - 세션 식별자
  command     - 원본 명령어
  translated  - 한국어 설명
  code        - 생성된 Joi JSON 코드
  created_at  - 저장 시각 (UTC)

sessions 테이블 (실시간 대화 맥락 유지)
  session_id        - PK, 세션 식별자
  chat_history      - JSON 직렬화된 대화 기록
  last_result       - 마지막으로 생성된(승인 전) 결과
  connected_devices - 해당 세션에 귀속된 기기 목록
  updated_at        - 마지막 업데이트 시각
```

*   `HUB_CONTROLLER_URL` 환경변수가 없으면 DB에만 저장하고 허브 전송은 스킵.
*   `session_id`를 지정하지 않으면 `"default"`로 고정.

```python
while True:
    input_str = get_input()
    # Stateful API call (session_id만 유지)
    res = agent_chat(input_str, session_id="my_session")
    
    # 더 이상 context를 반환받아 다시 던질 필요 없음
    print(res["response"])
    if res.get("last_result"):
        print("Generated Code:", res["last_result"]["code"])
```

---

## 5. Performance Optimization
*   **Lost-in-the-Middle Mitigation**: Context filtering ensures the model never sees irrelevant hardware schemas.
*   **Local LLM Ready**: Specifically tuned for Qwen-9B/Llama-8B class models running locally.
*   **Self-Correction**: Python backend catches schema errors and loops back to the model for retries.
