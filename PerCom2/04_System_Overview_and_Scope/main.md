# System Overview

![VETS system overview](system.pdf)

*VETS system overview. Authoring generates JOI code from a user-confirmed Timeline IR, and verification compares the generated code's behavior with the confirmed IR. Dashed arrows indicate user-requested IR revision and optional counterexample-guided code revision.*

VETS implements the aforementioned design as a two-phase pipeline. In the authoring phase, the system constructs a Timeline IR from the user's request and converts it to executable JOI code after the user reviews and confirms its behavior. In the verification phase, Behavioral Explorer checks the generated code against the confirmed IR before deployment.

**Execution target.** VETS generates and verifies JOI code for execution on the edge hub of a commercial IoT platform. A JOI automation consists of a start schedule (`cron`), a re-execution interval (`period`), and a script body (`code`). Temporal behavior such as edge detection, sustained conditions, and counting must be implemented with persistent variables and ordinary conditionals in the repeatedly executed script.

**Phase 1: Authoring.** VETS first analyzes the user's natural-language request. This analysis identifies the temporal and behavioral slots required for the automation, such as the start time, repetition period, trigger or condition, delay or sustain duration, and target actions. It also establishes device bindings by matching devices mentioned in the request to the connected device list. Based on this analysis, a local LLM generates a Timeline IR that specifies the automation's temporal control flow. Section~\ref{sec:timeline-ir} describes the structure and presentation of Timeline IR.

The user reviews the IR's behavior and device bindings and may request revisions before confirmation. After confirmation, the IR is fixed as the behavioral reference, and the local LLM generates JOI code from the confirmed IR and bindings.

**Phase 2: Verification.** Behavioral Explorer receives the confirmed Timeline IR and the generated JOI code. The code is parsed before behavioral checking. Explorer configures the verification environment with the device binding, start time, input ranges, and execution rules. It then begins exploring both executions from the initial states allowed in this environment. The IR interpreter and JOI interpreter execute under the same external input values and logical clock, while each retains its own variables and timers and tracks its progress through execution. Explorer jointly explores possible executions by selecting the next inputs, advancing both executions, comparing timed actions, and adding successor states not yet covered.

Only a completed exploration establishing matching timed action traces for every allowed initial state and timed input sequence authorizes deployment. A divergence is reported only after replay confirms the mismatch; unsupported operations, execution errors, or exhausted checking budgets leave the pair uncertified and do not authorize deployment. Verification runs locally without LLM calls. Its guarantee concerns conformance to the confirmed IR within the specified input ranges and execution rules. \S6 describes the joint exploration procedure and verdict criteria in detail.

**Counterexample feedback.** A counterexample records the initial environment, timed input sequence, and expected and actual actions. It can be returned to the LLM to guide revision of the JOI code. The confirmed IR and binding remain unchanged, and the revised code must be checked again before deployment.
