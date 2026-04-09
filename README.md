# JoI - IoT Automation Agent

JoI is an advanced IoT automation system that translates natural language commands into a custom DSL (JoI Code) optimized for persistent IoT environments. It features a multi-stage LLM pipeline for high precision and a conversational agent for interactive automation management.

---

## 📢 Latest Updates
- **[2026/04/07]** Added Agent capabilities (`agent_chat` API) for multi-turn conversational IoT control.
- **[2026/03/20]** Added support for vLLM with `Qwen3.5-9B-AWQ-4bit` optimization.
- **[2026/03/16]** Added support for `Qwen3.5-9B-Q4_K_M` GGUF models via llama.cpp.

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

### 2. `agent_chat`
A conversational API that enables iterative IoT control and scenario building through tool-calling.

**Arguments:**
- `user_message` (str): The user's input message.
- `connected_devices` (dict): Metadata of currently connected IoT devices.
- `chat_history` (list, optional): List of previous messages to maintain stateless conversation history.
- `agent_memory` (dict, optional): Operational state containing `last_result`, `base_url`, etc.

---

## ⚛️ JoI Code Specification
JoI is a Domain-Specific Language (DSL) specifically designed for IoT automation. For detailed syntax and behavioral specifications (Initialization `:=`, Evaluation `=`, Quantifiers `any`/`all`), please refer to [AGENTS.md](AGENTS.md).

---


