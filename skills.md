# AI Workflow and Joi Code Generation Pipeline

This document details the architecture, methodology, and pipeline design for generating optimal Joi automation code using a small local LLM (Qwen3.5-9B-Q4_K_M).

## 1. What is Joi Code? (Differences from Python)
Joi is a Domain-Specific Language (DSL) tailored for IoT automation. While it looks similar to Python or C-style languages, it has strict temporal and state-management rules that distinguish it from general-purpose languages.

### Key Characteristics & Restrictions
*   **Initialization vs. Assignment**: Joi strictly differentiates between state initialization (`:=`) which happens only on the very first execution tick, and ticking assignment (`=`) which happens on every polling cycle.
*   **No Native Loops**: Standard iteration tools like `for` or `while` loops are strictly prohibited. Iteration must be achieved by leveraging the external `period` JSON property to reinvoke the script.
*   **Temporal Delays**: Instead of `time.sleep()`, Joi uses specialized `delay(N UNIT)` constructs (e.g., `delay(10 MIN)`), which pause execution at that specific line without blocking the entire IoT ecosystem.
*   **Wait Blocks**: Unlike standard `if` statements, `wait until (Condition)` pauses the script entirely until the event occurs, which is heavily used for event-driven triggers.
*   **Quantifiers**: Multi-device operations rely on explicit [all(#Tag).Action()](run_local.py#50-68) and specialized "any" operators like `==|` or `>=|` to evaluate if at least one device in a group meets a condition.
*   **No Native Math Libraries**: Built-in functions like `math.abs()` are not allowed. Absolute value logic must be written out explicitly (e.g., `diff = a - b; if (diff < 0) { diff = b - a }`).

---

## 2. Dataset Overview & Category Characteristics
The pipeline is evaluated using [local_dataset.csv](local_dataset.csv), which consists of **280 experimental records** across 8 complexity categories.

### Dataset Input Types
*   **"all" Cases**: Commands where no `connected_devices` input is provided. The model must navigate the entire service list to find the correct `Device.Service` mapping.
*   **"connected" Cases**: Commands where a specific list of `connected_devices` is provided. The model's selection is strictly limited to these available units.
*   *Note*: Categories 1 and 2 are specialized (all vs connected), while Categories 3–8 maintain a 50/50 split between these input types.

### Category Mapping
1.  **Category 1 (Immediate - All)**: 
    *   *Characteristic*: Simple state manipulation using the full service list.
    *   *Example*: "Turn on the light", "Switch to dry mode".
2.  **Category 2 (Immediate - Connected)**: 
    *   *Characteristic*: Simple state manipulation restricted to tagging and specific connected devices.
    *   *Example*: "Turn on the light in the kitchen".
3.  **Category 3 (Snapshot Conditions)**: 
    *   *Characteristic*: **If/Else** logic. Check sensor state exactly once. 
4.  **Category 4 (Event-Driven Polling)**: 
    *   *Characteristic*: **Wait until** logic. Waiting for a future state transition.
5.  **Category 5 (Sequences and Delays)**: 
    *   *Characteristic*: Actions separated by explicit **delay(N UNIT)** gaps.
6.  **Category 6 (Complex Logic)**: 
    *   *Characteristic*: Snapshot checks with **multiple conditions** (2 or more `and`/`or` logic).
7.  **Category 7 (Schedules & Continuous Polling)**: 
    *   *Characteristic*: Recurring actions or specific clock times. High use of **cron**, **period**, and **duration** (internal break logic).
8.  **Category 8 (Global State Management)**: 
    *   *Characteristic*: Scenarios requiring **persistent state (:=)** and global variables.

---

## 3. What to Distinguish and Emphasize via Prompts
The prompts are engineered to extract nuanced semantic meaning from the natural language commands before generating code.

*   **When vs. Whenever vs. If** (`condition_extractor`):
    *   **If**: Immediate one-time snapshot check. (Generates `if` block, scheduled as `NO_SCHEDULE`).
    *   **When**: Polling for a future event exactly once. (Generates `wait until`, scheduled as `SCHEDULED`).
    *   **Whenever**: Infinite polling for a recurring event. (Generates latched `if` block with `triggered := false`, `period=100`, scheduled as `SCHEDULED`).
*   **All vs. Any vs. Single** (`quantifier`):
    *   **Single**: Controls or queries a single device unit.
    *   **All**: Applies to all units in an array (e.g., [all(#Light).Off()](run_local.py#50-68)).
    *   **Any**: Evaluates if *at least one* device satisfies a condition (e.g., "if any sensor is triggered"). Triggers the use of the special Joi operator `==|`.
*   **Delay vs. Schedule vs. Duration** (`router_classifier`):
    *   *Delays* ("30 mins later") belong in `NO_SCHEDULE` script blocks.
    *   *Schedules* ("Every day at 7 AM") get a `cron` assignment.
    *   *Durations* ("From 2 PM to 5 PM") get a `cron` start, a `period` interval, and MUST have a `break` condition inside the Joi script.

---

## 4. Current Situation (The Model)
*   **Environment**: Running locally on an IoT hub or local server.
*   **Model**: Small local LLMs like Qwen3.5-9B-Q4_K_M.
*   **Problem**: Small models suffer significantly from "Lost-in-the-Middle" syndrome when given large contexts (like a massive IoT schema). They also hallucinate syntax rules and logical structures when asked to plan time, select devices, and generate specialized DSL code all in one single prompt step.
*   **Goal**: Generate optimal, accurate Joi code without hallucinations for a real-world IoT environment.

---

## 5. Pipeline & Skills to Improve Accuracy (The Solution)
To mitigate the limitations of small models, the workflow is highly segmented into dedicated, single-purpose steps to reduce cognitive load and control context size.

### Stage 1: Context Funneling (Mapping)
*   **Intent Mapping**: Identifies only the crucial `DeviceCategory.ServiceName` pairs needed.
*   **Deterministic Python Filtering**: The backend (e.g., [run_local.py]) fetches *only* the mapped schemas. The final generation prompt is incredibly lean because the 14B model never sees irrelevant devices.
*   **Dynamic Switch Injection**: When `connected_devices` is provided, generic `Switch` services (On/Off/Toggle) are not blindly added; they are injected *only* if a specific device's `tags` expressly contain `Switch`. However, if `connected_devices` is completely absent, the full service summary is used, meaning `Switch` is included by default. This dynamic filtering saves tokens while preserving necessary generic controls.

### Stage 2: Intent Decomposition & Routing
The temporal logic is solved before a single line of Joi code is written.
*   **Condition Filter**: Binary check (Is there a condition/schedule?).
*   **Condition Extractor**: Describes the temporal logic explicitly in English.
*   **Router Classifier**: Categorizes the approach rigidly into `NO_SCHEDULE`, `SCHEDULED`, or `DURATION`.
*   **Quantifier**: explicitly decides Target size (`SINGLE`, `ALL`, `ANY`)

### Stage 3: Specialized Code Generation
*   Instead of a massive master prompt, the system injects specialized prompts (`prompt_joi_duration`, `prompt_joi_scheduled`, `prompt_joi_no_schedule`) based on the router's classification. This prevents the LLM from mixing up `wait until` functionality with simple `duration` logic.

### Stage 4: Forced Chain of Thought (CoT)
*   The LLM must output a `<Reasoning>` XML block explaining its logic *before* generating the Joi script. This "thinking out loud" sets up a perfect prior-context window for the small model to follow its own plan on the next output line. The reasoning block is then deterministically stripped via Python regex.

### Stage 5: Hybrid Fallbacks and Self-Correction
*   **WindowCovering Refinement**: Complex rule sets (like `#Window` vs `#Blind` vs `#Shade`) are handled by generating a generic tag, and running a secondary prompt and `exec()` block to mutate the script natively in Python.
*   **Error Retry Loops**: If the LLM hallucinates an invalid device category, the Python executor catches the error and feeds it back to the LLM to self-correct up to 2 times.

---

## 6. History and Trial & Error
Developing with the **Qwen3.5-9B-Q4_K_M** model (a relatively small model) revealed several technical hurdles that shaped the current multi-stage pipeline.

### Common Model Failures
1.  **Format Deviations**: Frequent errors in JSON or XML structure output.
2.  **Schema Hallucinations**: Utilizing devices or services that do not exist in the provided IoT context.
3.  **Argument Mismatch**: Passing invalid values or types to service methods.
4.  **Syntax Errors**: Hallucinating Joi DSL rules (e.g., using native Python loops or forbidden libraries).
5.  **Temporal Discrepancies**: Incorrect `cron` or `period` values that conflict with the natural language command.
6.  **Logical Drift**: Generating code that performs a different sequence of actions than requested.

### Rationale for Segmentation
*   **Token Complexity Limit**: Performance degrades sharply when the input context exceeds **4,000–5,000 tokens**. Above this threshold, hallucinations and information retrieval errors spike.
*   **Cognitive Load Management**: Small models struggle to perform complex planning (time, devices, and logic) in a single step. 
*   **Modular Workflow**: By breaking the process into specialized, single-purpose steps (Context Funneling -> Intent Mapping -> Routing -> Generation), we ensure that each inference is lean and highly focused, significantly improving the overall reliability of the generated Joi code.
