# JoI - IoT Automation Agent

JoI is an advanced IoT automation system that translates natural language commands into a custom DSL (JoI Code) optimized for persistent IoT environments. It features a multi-stage LLM pipeline for high precision and a conversational agent for interactive automation management.

---

## 📢 Latest Updates
- **[2026/04/27]** Unified output schema: `code` key (not `script`), `period: -1` for NO_SCHEDULE, `name` auto-generated from re-translate.
- **[2026/04/27]** Removed `get_weather` tool (not in MCP server). Auto-fetch `connected_devices` on `/generate-joi-code` when not provided.
- **[2026/04/07]** Added Agent capabilities (LocalAgentManager via joi-agent) for multi-turn conversational IoT control.
- **[2026/03/20]** Added support for vLLM with `Qwen3.5-9B-AWQ-4bit` optimization.

---

## 🚀 Getting Started

### Prerequisites
Ensure you have Python 3.9+ installed and a local LLM server (vLLM) running.

```bash
### 1. Install Dependencies ###
pip install -r requirements.txt

### 2. Start LLM Server ###
# Using vLLM (API Branch)
bash start_vllm.sh

### 3. Run Tests ###
# Modes: all / target / custom / agent
python test.py [mode] [debug]
```

---

## 🛠 Core APIs

### 1. `generate_joi_code`
The core engine that analyzes natural language intents and generates structured JoI automation code.

**Arguments:**
- `sentence` (str): The raw natural language command from the user.
- `connected_devices` (dict): Metadata of currently connected IoT devices.
- `other_params` (dict): Optional parameters for scenario generation.
- `modification` (str, optional): Feedback or modification request to refine previously generated code.

### 2. `LocalAgentManager` (joi-agent)
A streaming conversational agent served via `joi-agent` (port 8012). Handles multi-turn IoT control through a ReAct loop with MCP tool-calling. Session state is persisted in SQLite via `session_manager`.

**Endpoint:** `GET /chat?query=...&session_id=...&user_id=...`

**Key behaviors:**
- Streams SSE tokens to the frontend.
- Calls `request_to_joi_llm` → `app.py (49999)` → vLLM for code generation.
- Calls MCP tools (`add_scenario`, `control_thing_directly`, etc.) via `tools.py`.
- Session logs written to `data/logs/<session_id>.log`.

---

## ⚛️ JoI Code Specification
JoI is a Domain-Specific Language (DSL) specifically designed for IoT automation. For detailed syntax and behavioral specifications (Initialization `:=`, Evaluation `=`, Quantifiers `any`/`all`), please refer to [AGENTS.md](AGENTS.md).

---


