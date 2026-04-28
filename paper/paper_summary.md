# JoI-LLM Paper Plan

**Constraints**: English input only → JoI output. SLLM (≤9B) is the primary deployment target. No formal Idiom-Quotient theorem. No MC/DC.

> **Thesis**: In the deployable setting where natural-language IoT commands are compiled to a reactive DSL by a small (≤9B) LLM running on-device, three problems block end-to-end generation: unreliable idiom selection, absent verification, and opaque user feedback. We show all three share a single structural cause — reactive temporal semantics encoded as **idioms** rather than first-class primitives — and that one artifact, an executable **Timeline IR** that elevates those semantics to first-class, resolves all three together. The SLLM constraint forces the architecture; the root-cause structure makes the architecture sufficient.

---

## 0. JoI Language Overview

**JoI = service-level reactive IoT DSL.**

- Python-like imperative syntax over a multi-brand device service abstraction.
- Constructs: `if`, `wait until`, `cron`, `period`, device service calls.
- **No compiler, no return values, no deterministic execution result.** Side effects on physical devices are the only observable outcome.

Expressible scenario spectrum:

| Complexity | Example | Core structure |
|---|---|---|
| Trivial | "Turn on the lights in Sector A at 5 PM" | one-shot cron |
| Simple | "Close the window if it rains" | one-shot condition |
| **Bounded** | "Check the temperature every 5 min from 1–3 PM" | time window + periodic |
| **Persistent** | "Turn on the light every time the door opens" | rising-edge repeat |
| **Trigger→Periodic** | "Sound the siren every 5 min after motion detected" | event then periodic |

**Key fact:** Bounded / Persistent / Trigger→Periodic scenarios have **no first-class primitives** in JoI. Developers hand-encode these semantics using ordinary variables (`triggered`, `phase`, `start_time`) and control flow — **idioms**. Reactive temporal semantics live at the idiom level, not the language level.

---

## 0.5 Setting: Small LLMs at the Edge

This work targets a specific deployment regime: **the LLM that produces the JoI program runs on the same hub that executes it.** Three real-world requirements force this:

- **Privacy.** Device state and user behavior must not leave the home/factory.
- **Latency.** Reactive triggers (e.g., "when the door opens, turn on the light") cannot wait for a cloud round-trip — sub-second response is mandatory.
- **Offline operation.** The system must keep working when the household network or cloud service is unavailable.

On current and projected edge hardware, this means roughly **9B-parameter models or smaller** (SLLM).

**The SLLM constraint is what gives this work its shape.** Empirically, a 9B model cannot generate a correct JoI program for a reactive temporal command in a single forward pass. End-to-end NL → JoI asks the SLLM to simultaneously resolve:

1. **Idiom selection** — which `triggered`/`phase`/`alternation` pattern to use (semantic)
2. **JoI syntax** — exact `:=` vs `=` semantics, `wait until`, `cron`/`period` interplay (lexical)
3. **Device selectors** — `(#Loc #Skill)`, `all(#...)`, `any(#...)` (catalog lookup)
4. **Timing arithmetic** — `delay(N UNIT)` conversion, cron expressions (numeric)

Joint accuracy collapses far below per-aspect accuracy. End-to-end generation at SLLM scale is not just suboptimal — it is **not deployable**.

**Therefore the system must decompose the task.** The natural decomposition factors out the hardest aspect — idiom selection from idiom-encoded reactive semantics — into a structured intermediate representation the SLLM can extract reliably, and lowers the rest mechanically. **Timeline IR is that decomposition.** §1 will then argue that the *same* decomposition resolves two further problems (verification, user feedback) that look independent of the SLLM motivation. The SLLM constraint forces the architecture; the root-cause structure of the problem class makes that architecture sufficient.

A note on scale: even at GPT-4 scale, end-to-end accuracy on the hardest reactive commands does not approach 100% (§1.1). The SLLM setting makes the failure mode practically acute and visible, but the underlying problem class is scale-independent. This work optimizes for the deployable setting; the framework's value at larger scale is a secondary observation rather than the primary motivation.

---

## 1. Problem Statement

### 1.1 Motivating Example

Consider three English commands:

```
(a) "If the door is open, turn on the light."
(b) "Turn on the light when the door opens."
(c) "Turn on the light every time the door opens."
```

(a) is unambiguous — a one-shot snapshot check. (c) is unambiguous — persistent rising-edge behavior. (b) is the hard case: "when" can mean either a one-shot wait or a persistent trigger. The intended behavior differs radically, and text alone does not decide it.

These surface-similar commands map to **structurally different JoI programs**:

```
// (a) one-shot if
if ((#Door).door_doorState == "open") {
    (#Light).switch_on()
}

// (b-once) wait, then act once
wait until((#Door).door_doorState == "open")
(#Light).switch_on()

// (b-persistent) / (c) — rising-edge idiom (no language primitive; idiom-encoded)
triggered := false
if ((#Door).door_doorState == "open") {
    if (triggered == false) {
        (#Light).switch_on()
        triggered = true
    }
} else {
    triggered = false
}
```

**End-to-end 9B baseline failure** *(placeholder — to be filled by experiment)*:
- Correct idiom selection on reactive commands: 9B direct ~35%, GPT-4 direct ~65%
- Correct rising-edge idiom implementation given correct selection: 9B ~15%, GPT-4 ~50%

→ **Scale alone does not fix this.** Idiom selection is a systematic error class independent of model size, because the idiom is not recoverable from NL surface form alone.

### 1.2 Problem Setting

**Input:**
- $u$: natural language utterance (English)
- $D = \{(d_i, S_i, A_i)\}$: device catalog (device id, callable services, observable attributes)

**Output:**
- $P \in \mathcal{L}_{\text{JoI}}$: an executable JoI program whose behavior matches the intent of $u$ under a coverage-adequate set of event sequences.

### 1.3 Three Constraints That Define the Problem Class

**(C1) Idiomatically-encoded reactive semantics.**
$\mathcal{L}_{\text{JoI}}$ lacks first-class primitives for rising/falling edges, bounded time windows, phase transitions, and trigger-then-periodic structures. These are expressed only through a finite idiom set over ordinary variables and control flow.

**(C2) No verification anchor.**
There is no JoI compiler, no canonical NL→DSL ground-truth mapping, and no deterministic execution result. Generated programs produce side effects on physical devices that cannot be replayed or compared automatically.

**(C3) Local-only deployment.**
Production targets run on on-premise hardware (≤9B LLMs) due to privacy, sub-second latency, and offline constraints. This is the actual deployment constraint of consumer/industrial IoT hubs — not a self-imposed limitation. §1.1 shows the difficulty does not vanish at larger scale; C3 makes it visible, but the problem class is scale-independent.

### 1.4 One Root Cause, Three Problems

C1 is not simply a generation challenge. C2 is not simply a verification challenge. They share the same structural root, and that root produces a third problem as a byproduct:

```
Root cause: reactive temporal semantics encoded as idioms
          (triggered := false, phase := 0 — syntactically ordinary variables)
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
  Generation     Verification  User feedback
  LLM must       No executor,  JoI idioms are
  select idiom   no spec,      opaque; user
  from NL alone  no ground     cannot confirm
  (systematic    truth to      intent from
  failure)       check against generated code
```

**Claim:** These three problems cannot be solved independently. Any generation-only solution leaves verification open. Any verification-only solution requires the spec that doesn't exist. User feedback requires understanding what generated code *means* — which requires decompiling idioms.

**The same artifact that eliminates the root cause resolves all three.** A representation in which reactive temporal semantics are first-class primitives makes idiom selection explicit (helps generation), provides an executable reference (enables verification), and renders deterministically to English (enables user confirmation). That artifact is the **Timeline IR**.

### 1.5 Research Questions

- **RQ1.** Does decomposing NL→JoI into NL→IR + IR→JoI improve generation accuracy on reactive temporal commands over direct prompting baselines?
- **RQ2.** Can IR-guided simulation-trace comparison serve as behavioral equivalence checking for generated JoI — without a compiler, executor, or ground-truth program?
- **RQ3.** Does the same IR that enables RQ1 also enable RQ2 and user-readable rendering, empirically validating the root-cause argument?

### 1.6 Scope and Non-goals

**In scope:**
- English single-utterance commands
- Temporal triggers, time windows, periodic and edge-driven semantics
- Behavioral verification of generated programs against an executable IR
- ≤9B local LLM as primary generator; GPT-4 class as upper-bound comparison

**Out of scope:**
- Multi-utterance dialogue
- Spatial reasoning over room geometry ($D$ gives device IDs, not positions)
- Device authentication, access control, security
- Conflict resolution between concurrent automations
- Device service abstraction synthesis ($D$ is fixed)
- Continuous-time / hybrid-system semantics

---

## 2. Why It Matters

1. **No existing solution for this problem class.** NL→reactive-IoT-DSL with behavioral verification is open. Existing NL→automation tools (IFTTT, Home Assistant) use structured forms. NL→code work (NL2Code, CodeBERT) does not address reactive temporal semantics or the absence of an executor.

2. **Wrong idioms cause physical-world errors.** One-shot vs persistent misclassification → automation fires once and stops, or runs forever. Wrong delay ordering or missing edge detection → devices stuck in unsafe states.

3. **Evaluation gap.** Existing NL→DSL evaluation uses BLEU or exact match. Neither captures reactive semantic correctness — two programs can score identically on BLEU while having opposite temporal behavior (one-shot vs cycle).

4. **Broad generalization surface.** The idiom-encoding problem exists across a wide class of reactive languages:

| Domain | System | Representative idiom |
|---|---|---|
| Smart home | JoI, Home Assistant, openHAB | `triggered` flag for edge |
| Workflow automation | n8n, Zapier code | state-tracking variable |
| Robotics | ROS, behavior trees | `phase` enum |
| Game scripting | Roblox Luau, Unity events | tick-based polling |
| Stream processing | KSQL, Flink | window via aggregation |

JoI is the instantiation. The problem class — and the IR-based solution structure — is broader.

---

## 3. Approach

### 3.0 Design Evolution

**First attempt (failed):** Generate JoI end-to-end, then reverse-translate JoI→NL and compare with the original command. The reverse-translation prompt (`re_translate.md`) was effectively a hand-curated lookup table — one NL phrasing per JoI pattern. Failure modes:
- Familiar patterns translated reasonably; **roughly 1 in 4 commands was misinterpreted**
- Any unfamiliar idiom or slight composition fell outside the lookup
- The deeper problem (analyzed in §4): **NL ↔ JoI is asymmetric**

**Key insight from failure:** *NL → JoI is tractable, but JoI → NL is intrinsically hard.*

| Direction | Difficulty | Reason |
|---|---|---|
| NL → JoI (forward) | tractable | LLM can pattern-match NL onto known idioms |
| JoI → NL (reverse) | hard | Idioms are syntactically indistinguishable from ordinary code; recovery requires decompilation-level analysis |
| IR → NL | easy | IR's 9 ops are first-class temporal primitives; each op maps deterministically to an English phrase |

**The verification reframing:**

```
Original verification problem:    NL ──────?────── JoI    (no automation possible)
                                      │
                  ┌───────────────────┴────────────────────┐
                  ▼                                        ▼
After decomposition:    NL ──[user-confirm]── IR ──[trace eq]── JoI
                                  │                        │
                          human-in-the-loop          automatic
                          (NL→IR readable;           (IR is the reference;
                          user OKs intent)            simulator-based check)
```

Once the user confirms the IR-readable rendering, the NL→IR mapping is **grounded**. The user does not need to read JoI; they read step-by-step English derived from the IR (made possible by the 1:1 op-to-NL mapping). This is **not a UX convenience — it is what makes verification possible**:

- **Before user OK:** verification target is "NL → JoI as a whole" and there is no spec → automatic verification impossible.
- **After user OK:** verification target shrinks to "IR → JoI" and IR plays the spec role → simulation-trace comparison becomes a sufficient check.

User-in-the-loop is the structural element that turns an unsolvable verification problem into a solvable one.

### 3.1 Pipeline

```
[NL (English)]
    │  Stage 1: NL → Timeline IR  (9B LLM, schema-validated)
    ▼
[Timeline IR] ─► readable English ─► user confirm/edit ─► [IR']
    │
    │  Stage 2: IR → JoI  (deterministic lowering, rule-based)
    ▼
[JoI code]
    │
    │  Verification: same event sequences fed to IR simulator and JoI simulator
    ▼
trace(IR') ≟ trace(JoI)  ── on mismatch, retry Stage 2 with diff signal

※ The same mechanism powers evaluation: compare generated JoI against
   reference IR via trace equality on synthesized events.
```

**Error absorption:**
- **NL ↔ IR gap**: bridged by user confirmation. IR → readable English is deterministic (9 ops, 1:1 NL mapping), so non-developers can review.
- **IR ↔ JoI gap**: bridged by simulation-trace comparison. IR is the executable specification; JoI is mechanically checked against it.

### 3.2 Contributions

The four contributions all flow from one artifact (Timeline IR) and are linked by a single structural argument: idiomatic encoding is the root cause; first-class primitives are the resolution.

**C1 — Timeline IR.** A 9-op fixed-grammar executable IR that promotes reactive temporal semantics (rising/falling edges, time windows, phase transitions, periodic-after-event) to first-class primitives. Designed to be (a) extractable by a 9B LLM via left-to-right pattern matching, (b) renderable to English deterministically, (c) executable as a reference simulator. **The artifact that resolves the root cause.**

**C2 — Two-stage generation (NL → IR → JoI).** The decomposition isolates idiom selection (Stage 1, semantic) from code syntax (Stage 2, mechanical). Nine deterministic lowering rules cover the full expressible idiom set. This is the mechanism by which C1 improves generation accuracy on reactive temporal commands.

**C3 — Simulation-based behavioral verification.** IR as executable reference + IR-guided event synthesis (covering each branch condition and edge transition in the IR) + trace comparison between IR and JoI simulators. Achieves behavioral equivalence checking **without a compiler, executor, ground-truth program, or formal specification** — this combination of absences defines the problem class, and simulation-trace comparison is the first technique that resolves it for reactive IoT DSLs.

**C4 — IR-mediated user feedback loop.** IR → readable English is deterministic *because* IR ops are first-class primitives — which is the same property that enables C2 and C3. User confirmation of the rendered IR grounds the NL→IR mapping, which is what makes C3's verification meaningful (it gives the verifier something to verify *against*). This is not a UX feature bolted on; it is the closing link in the verification chain.

---

## 4. Why NL Round-Trip Fails as Verification

A natural first attempt is round-trip: generate JoI from NL, back-translate JoI → NL, and compare with the original. We tried this; it fails for three structural reasons.

### 4.1 The Asymmetry

Forward and reverse directions are not equally tractable. Forward (NL → JoI) is a pattern-matching task an LLM can do. Reverse (JoI → NL) is decompilation.

### 4.2 Why JoI → NL Is Intrinsically Hard

**Idiom opacity.** JoI lacks language-level constructs for reactive primitives like rising edges or phase transitions. Developers encode these with ordinary variables (`triggered`, `phase`), producing code that is **syntactically indistinguishable from non-reactive logic**. Recovering the intended semantic role requires program analysis at decompilation level, not parsing.

**Many-to-many mapping.** A single NL command admits multiple correct JoI implementations (different idiom choices, different sequencing). A single JoI program compresses reactive timing information that NL cannot uniquely recover. The mapping is non-canonical in both directions.

**No evaluation anchor.** Even if back-translation produced fluent NL, BLEU and semantic-similarity metrics fail to distinguish "one-shot" from "persistent" behavior — exactly the distinction that matters most. Two surface-similar NL strings can describe opposite temporal semantics.

Empirically, we observed roughly 1 in 4 commands misinterpreted by a curated JoI→NL prompt; novel idiom compositions fell outside the lookup entirely.

### 4.3 Why the Asymmetry Resolves Through IR

The asymmetry is *directional*: JoI → NL is hard, but **IR → NL is easy**. IR ops are first-class temporal primitives — each maps deterministically to a short English phrase (`wait(edge:rising)` → "every time X becomes true"). We did not abandon round-trip; we relocated it from NL ↔ JoI to NL ↔ IR. That relocation is what makes user-mediated confirmation possible (§3.0), and it is the precondition for the verification method in §6.

---

## 5. Why Model Checking Does Not Apply

A natural reviewer reaction is "use SPIN / NuSMV / UPPAAL." We address this directly: the technique does not fit the problem class.

### 5.1 Five Mismatches

**Property checking vs. equivalence checking.** Model checking decides M ⊨ φ — whether a model satisfies a formal specification. We have no φ. Translating natural language into LTL/CTL is itself the original NL → semantic-representation problem in a different target language. Circular.

**Idiom-induced bisimulation gap.** IR's `wait(edge:rising)` and JoI's `triggered`-flag idiom yield different finite state structures. They are not bisimilar in the strict sense; equivalence holds only modulo an idiom-aware abstraction that off-the-shelf model checkers cannot perform without manual encoding per idiom.

**State-space explosion.** A `period:100ms` JoI program over a one-hour scenario yields 36,000 ticks. Combined with continuous-valued sensor variables (temperature, humidity) and persistent flag/phase state, the reachable space is intractable for explicit-state methods. Symbolic abstraction is possible in principle but loses the device-level granularity we need.

**Tooling barrier.** SPIN consumes Promela; NuSMV consumes SMV; UPPAAL consumes timed automata. None accepts JoI directly. JoI → any of these is a semantics-preserving program transformation — a research problem itself.

**Output mismatch.** Model checkers return ✓/✗ + counterexample. We need continuous quantitative signals (per-difficulty trace-match rate, per-idiom error attribution, retry signals for self-correction) to drive evaluation and pipeline feedback.

### 5.2 Comparison

| Dimension | Model Checking | Our approach |
|---|---|---|
| Goal | property satisfaction (M ⊨ φ) | behavioral equivalence (trace(IR) = trace(JoI)) |
| Specification | LTL/CTL — absent here | reference IR plays the spec role |
| Real values / continuous time | manual abstraction; decidability risk | discrete simulator runs them directly |
| Idiom abstraction | requires custom equivalence relation | absorbed by simulator's tick semantics |
| State explosion | exponential in sensors × ticks × variables | bounded by IR-guided test event set |
| Input language | re-translation to Promela/SMV | JoI consumed directly (parser + simulator) |
| Output | ✓/✗ + counterexample | quantitative trace-match rate |

### 5.3 Limitation We Accept

The trace approach is **sample-based**: it tests behavior on a synthesized event set, not all events. We make no completeness claim. The empirical claim is that IR-guided synthesis reaches every behaviorally significant decision point in the IR (each branch, each edge transition, each cycle entry/exit), which is what the failure modes in this domain hinge on. Mutation testing (§9) measures this directly: programs with injected semantic mutations are detected at high rate while behaviorally equivalent variants are not flagged.

---

## 6. Verification Method: IR-Guided Simulation Trace Comparison

The verification approach has four mechanical components and one design property that justifies them all.

### 6.1 The Design Property

Timeline IR is **executable**: its semantics are given by a reference simulator (§6.2). This is the design property that lets the rest of the verification framework exist — IR provides the reference behavior that NL alone cannot, and JoI lacks. Every component below follows mechanically from this.

### 6.2 IR Simulator (Reference Execution)

A small interpreter walks the IR's `timeline` linearly, evaluating expressions against an event-driven device state. Each `call` op emits an observable record `(target, args, timestamp)`. The output is a sequence of these records — the **IR trace**. The simulator is small enough to be auditable; it is the operational definition of what the IR *means*.

### 6.3 JoI Simulator (Target Execution)

JoI has a deployed runtime on IoT hubs but no formal operational semantics: the language behavior is documented prose, and live execution produces non-replayable physical side effects. We provide a tick-based reference interpreter over JoI's parsed AST that constitutes the **operational semantics we verify against**. It models:
- `:=` initializers persist across ticks (state for `triggered`, `phase`, `color`, etc.)
- `=` assignments update each tick
- `wait until` blocks the script until its condition is satisfied
- `period` controls the polling cadence (`period: 100` for rising-edge idiom; `period: N` for periodic actions)

The same observable record format is emitted, producing the **JoI trace**.

We treat this simulator not as an approximation of an ideal runtime, but as **the formal definition of JoI semantics for verification purposes** — JoI lacks one, and providing one is part of this work's contribution. The simulator is a small, auditable artifact; downstream verification verdicts are sound with respect to it. Drift between this definition and real-hub behavior is itself a finding worth measuring (and is orthogonal to the verification framework).

### 6.4 IR-Guided Event Synthesis

Given an IR, we synthesize event sequences that exercise its decision structure. Walking the IR AST, for each behaviorally significant node we emit:

| IR node | Synthesized events |
|---|---|
| `if(cond, then, else)` | one sequence satisfying `cond`, one violating it |
| `wait(cond, edge:none)` | events transitioning `cond` from undefined/false to true |
| `wait(cond, edge:rising)` | events that hold `cond` false then drive false→true (and back, for cycles) |
| `cycle(until:φ)` | events keeping φ false then driving φ true |

Coupled with the `devices_referenced` annotation, the synthesizer knows which sensors to manipulate and in what order. The result is a small (typically <20) set of event sequences that touch every branching and edge-detecting point in the IR.

This replaces the formal coverage construction of earlier drafts with a directly implementable rule set. We do not claim it is provably sufficient; we claim it is empirically adequate for the failure modes that matter (§5.3, validated by mutation testing in §9).

### 6.5 Trace Comparison

For each synthesized event sequence E:
1. Run IR simulator on E → `trace_IR`
2. Run JoI simulator on E → `trace_JoI`
3. Compare as ordered sequences of `(target, args, timestamp)` tuples, with timestamp tolerance bounded by the JoI period

If all comparisons match across the synthesized set, we declare IR and JoI behaviorally equivalent under our coverage. If any comparison fails, the diff (which event, which step, what was expected vs. observed) is fed back to Stage 2 as a structured retry signal — this drives self-correction.

### 6.6 Scope and Honest Limitations

- **Sample-based.** The method tests behavior on synthesized events, not all events. No completeness claim. The empirical case for adequacy is made through mutation detection rate (§9).
- **Discrete time.** Both simulators operate on discrete ticks. Continuous-time reactive devices (analog feedback loops) are out of scope.
- **Single-program.** We verify one JoI program against one IR. Concurrent automation interaction is out of scope (§1.6).
- **Semantics are stipulative.** Our verdicts are sound with respect to the operational semantics defined by our simulators (§6.2, §6.3). This is the strongest soundness guarantee a language without a formal spec can support; it is also *exactly* the guarantee a real deployment needs once the simulator becomes the canonical reference.

---

## 7. Why This IR Design

§3 argues *why an IR* resolves the root cause; this section argues *why this particular IR shape* (linear timeline of 9 ops) over the alternatives we considered.

### 7.1 Alternatives We Rejected

| Approach | Why we rejected it |
|---|---|
| **End-to-end NL → JoI** | LLM must simultaneously resolve idiom selection, syntax, selectors, and timing. Errors cannot be attributed to a stage; verification has no anchor. |
| **Phase-graph IR** (early design) | Sequential logic (delayed diff, progressive update with break) collapses into a single phase node, producing oversized JSON and degraded 9B extraction accuracy. |
| **AST-level IR** | Sits too close to JoI syntax; loses the abstraction lift that makes both extraction and equivalence checking tractable. Idiom identity is still hidden. |

### 7.2 Design Choices Specific to Timeline IR

1. **Linear time-order** matches NL's narrative order, allowing left-to-right LLM extraction without reordering.
2. **Fixed 9-op grammar** bounds the hallucination surface and enables schema-level rejection of malformed outputs.
3. **Separate `cycle.until` / `read` / `delay` ops** flatten complex composite commands (delayed-diff, progressive update, time-bounded loops) into a single step list rather than nested phase structures.
4. **Explicit `edge` annotation** (`none | rising | falling`) elevates trigger semantics to a typed field — the very piece NL surface form fails to disambiguate.
5. **Convention β** (an `args` string is an expression iff it contains `.`, `$`, or an operator) lets the schema infer literal-vs-expression without an extra type tag, keeping the JSON small enough for reliable extraction.

---

## 8. Timeline IR Schema (Reference)

Appendix-bound in the paper; included here for completeness of the planning doc.

### 8.1 Top-level schema
```json
{
  "devices_referenced": ["<Device_id>", ...],
  "timeline": [ <step>, <step>, ... ]
}
```

### 8.2 Step grammar (9 ops)
| Op | Meaning | Key fields |
|---|---|---|
| `start_at` | scenario anchor | `anchor: "now"`, or `anchor:"cron", cron:"<5-field>"` |
| `wait` | block until cond | `cond`, `edge: none\|rising\|falling` |
| `delay` | pause for ms | `ms:<int>` |
| `read` | snapshot a value to a local var | `var`, `src:"<Device.attr>"` |
| `call` | device method call | `target:"<Device.method>"`, `args:{...}` |
| `if` | one-shot branch | `cond`, `then:[...]`, `else:[...]` |
| `cycle` | repeat body | `until:"<expr>\|null"`, `body:[...]` |
| `break` | exit nearest cycle | — |

### 8.3 Expression grammar
- **Literals**: numbers, strings, booleans.
- **Device attribute reference**: `Device_id.attr` (e.g., `TempSensor_1.temperature`).
- **Local variable reference**: `$varname` (from prior `read`).
- **Clock**: `clock.time` (`"HH:MM"`), `clock.date` (`"MM-DD"` or `"YYYY-MM-DD"`), `clock.dayOfWeek` (`"MON".."SUN"`).
- **Operators**: `+ - * / ( )`, `== != < > <= >=`, `&& || !`, `abs(x)`.
- **Convention β**: an `args` string is an expression iff it contains `.`, `$`, or any operator; otherwise it is a literal.

### 8.4 Trigger mapping (the disambiguation rule)
| English | IR pattern |
|---|---|
| `if X, do Y` | `if` one-shot branch (no wait, no cycle) |
| `when X, do Y` | `wait(edge:"none") + Y` — one-shot level wait, no cycle, no rising |
| `whenever X, do Y` / `every time X, do Y` | `cycle { wait(edge:"rising"); Y }` |

### 8.5 Validator rules
- Top level: `devices_referenced` (list of str) + `timeline` (non-empty list).
- First step must be `start_at`.
- `cycle.body` must contain at least one `delay` or one edge-triggered `wait` (cadence guarantee).
- `wait.edge` ∈ `{none, rising, falling}`.
- Every `Device.attr` / `Device.method` must exist in the provided service catalog.
- Nested cycles forbidden.

### 8.6 Reject conditions
- Cycle requested but no period or interval specified (e.g., "alternate A and B" without an interval).
- Undefined device or attribute referenced.
- Nested loop requested.

---

## 9. Roadmap

### 9.1 Implementation (near-term)

- **Stage 2 (IR → JoI) lowering** — finalize the 9 idiom templates against the canonical example set; measure per-template extraction + lowering accuracy.
- **IR simulator** — Python reference interpreter; the operational definition of IR semantics.
- **JoI simulator** — tick-based AST interpreter modeling `:=`/`=` persistence, `wait until`, `period`, `cron`. Defines JoI's operational semantics for verification (§6.3).
- **IR-guided event synthesizer** — walks the IR AST, emits a small set of event sequences covering each branch and edge transition.
- **Self-correction loop** — diff trace mismatches → structured retry signal for Stage 2.

### 9.2 Evaluation Plan

The evaluation is built around three experiments, each tied to one RQ.

**E1 — Generation accuracy (RQ1).** Compare four systems on the dataset:

| System | Pipeline |
|---|---|
| **A: Direct few-shot** | NL → JoI, same example pool, no IR |
| **B: CoT** | NL → step-by-step reasoning → JoI |
| **C: Ours** | NL → IR → JoI |
| **D: GPT-4 direct** | upper bound |

Stratify accuracy by command difficulty (cat 1–9). The central hypothesis: A/B/C tie on cat 1–3 (trivial/simple); C dominates on cat 4–9 (reactive temporal). The widening gap with difficulty visualizes the central thesis.

**E2 — Verification adequacy (RQ2): mutation testing.** Inject mutations into ground-truth JoI:
- *Semantics-preserving* (50): variable rename, equivalent expression rewrite, redundant-but-safe code insertion.
- *Semantics-changing* (50): one-shot ↔ persistent flip, edge removal, delay reordering, missing reset, off-by-one threshold.

Compare detection rates of:
- BLEU / exact-match (token baseline)
- AST diff (structural baseline)
- LLM-as-judge ("does this JoI match this NL?")
- JoI → NL re-translation similarity (§4's failed approach — included as ablation)
- **Ours**: IR-guided trace comparison

The empirical claim: ours catches semantics-changing mutations at high rate (target ≥95%) while keeping false positives on semantics-preserving mutations low (target ≤5%); baselines miss substantial fractions of semantics-changing mutations or flag preserving ones.

This experiment directly substantiates §4 and §5 (round-trip and model-checking inadequacy) and is the *adequacy argument for §6* in lieu of a formal coverage theorem.

**E3 — End-to-end pipeline (RQ3).** Full NL → IR → JoI run with simulator-driven self-correction. Measure: end-to-end trace-match against reference, retry count distribution, terminal failure cases.

### 9.3 Dataset

The current English benchmark is 310 commands stratified across cat 1–9 (`local_dataset2.csv`). Expansion to ~600 commands is planned before submission, weighted toward cat 4–9 (reactive temporal — where the central claim lives). For E1/E2 reporting, accuracy and detection rates are stratified by category.

### 9.4 Long-term (post-submission)

- **Generalization probe**: port the framework to a second reactive DSL (Home Assistant automations or a behavior-tree DSL) on a small sample, to test the §2 generalization claim.
- **Boundary analysis**: characterize commands the IR cannot express (nested cycles, analog-time conditions, distributed triggers) and what extending the grammar would cost.

---

## 10. Target Venues

The paper's natural fit is now systems-leaning rather than theory-leaning (formal contribution dropped, empirical evaluation centralized). Ranked by current fit:

- **ACM IMWUT / UbiComp** (primary). Directly competitive with ChatIoT'24, HomeGenii'25, Sasha'24. The systems-with-evaluation framing matches the venue. Adding even a small user study on IR-readable confirmation would strengthen this fit substantially.
- **ICSE / FSE** (secondary). The DSL synthesis + behavioral verification angle fits, especially with mutation-testing as the adequacy argument. Requires sharper evaluation rigor and possibly the "compositional rule-by-rule verification" extension.
- **IEEE IoT Journal** (fallback). Lower bar, slower turnaround.
- **ACL / EMNLP**. Possible only with a substantially larger dataset (≥1000 commands) and an explicit linguistic analysis of trigger ambiguity.
- **NeurIPS / ICLR**. Unlikely without restoring formal theory — out of scope under current constraints.

---

## Reviewer-rebuttal Checklist (for §1 drafting)

| Anticipated objection | Where it's addressed |
|---|---|
| "Just use GPT-4" | §1.1 numbers + §1.3 (C3) — error class is scale-independent |
| "Smart-home only?" | §1.4 + §2 — idiomatically-encoded reactive languages generalize |
| "Use model checking" | §5 — no spec; bisimulation gap; tooling barrier |
| "Use NL round-trip" | §4 — JoI ↔ NL asymmetry; round-trip is relocated, not abandoned |
| "Why this IR specifically" | §7 — alternatives rejected (phase-graph, AST-level); design choices justified |
| "Sample-based verification is incomplete" | §5.3 + §9 (E2 mutation testing) — empirical adequacy in lieu of completeness |
| "Simulator might not match real runtime" | §6.3 — simulator *is* the operational semantics for verification; soundness is w.r.t. that definition |

---

## Appendix — Current Implementation Status

- `joi/paper/timeline_ir_extractor.md` — NL → IR extraction prompt with 17 few-shot examples.
- `joi/paper/joi_from_ir.md` — IR → JoI lowering prompt with 9 idiom templates (D-1..D-9).
- `joi/paper/timeline_ir.py` — pipeline module (`extract_ir`, `validate_ir`, `ir_to_readable`, `DEFAULT_TEST_DEVICES`).
- `joi/paper/ir_code_example.md` — 11 canonical NL/IR/JoI triples (lowering reference).
- `joi/dataset_migration/local_dataset2.csv` — 310-command English benchmark, stratified cat 1–9, validated.

**Verified**: NL → IR end-to-end on the canonical examples.
**Pending**: IR → JoI lowering implementation, IR/JoI simulators, IR-guided event synthesizer, mutation-test harness, all baseline systems for E1.
