# JoI-LLM Paper Plan

**Constraints**: English input only → JoI output. SLLM (≤9B) is the primary deployment target. No formal Idiom-Quotient theorem. No MC/DC.

> **Thesis**: In the deployable setting where natural-language IoT commands are compiled to a reactive DSL by a small (≤9B) LLM running on-device, three problems block end-to-end generation: unreliable idiom selection, absent verification, and opaque user feedback. We show all three share a single structural cause — reactive temporal semantics encoded as **idioms** rather than first-class primitives — and resolve them by **decomposing NL→JoI into NL→IR→JoI with a user-confirmed IR as the spec**. The user-confirmed IR is also the source from which we *deterministically derive a finite-state machine of transition obligations*; covering every transition point with synthesized scenarios gives a structurally-grounded coverage claim (transition-obligation completeness) without requiring a formal property language or full-state enumeration. The SLLM constraint forces the architecture; the IR-as-spec structure makes verification tractable.

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

**Hero contribution (the structural insight).** NL→JoI verification is unsolvable as a single problem because no spec exists. Decomposing it into NL→IR (LLM, human-confirmable) + IR→JoI (deterministic lowering), where the **user-confirmed IR plays the spec role**, transforms the problem into IR↔JoI behavioral equivalence — which is solvable by transition-obligation coverage on a deterministic verdict path (no LLM in verdict). This decomposition is what makes the rest of the framework possible. C1–C3 enable it as artifact + interface; C4 is the verification mechanism that realizes it; C5 closes the LLM-correction loop.

**C1 — Timeline IR.** A 9-op fixed-grammar executable IR that promotes reactive temporal semantics (rising/falling edges, time windows, phase transitions, periodic-after-event) to first-class primitives. Designed to be (a) extractable by a 9B LLM via left-to-right pattern matching, (b) renderable to Korean/English deterministically, (c) executable as a reference simulator AND derivable as a finite-state machine of transition obligations. **The artifact whose four properties together enable the hero decomposition.**

**C2 — Two-stage generation (NL → IR → JoI).** The decomposition isolates idiom selection (Stage 1, semantic) from code syntax (Stage 2, mechanical). Nine deterministic lowering rules cover the expressible idiom set observed in our deployment regime. This is the mechanism by which the hero decomposition improves generation accuracy on reactive temporal commands.

**C3 — IR-mediated user feedback loop (spec grounding).** IR → readable Korean/English is deterministic *because* IR ops are first-class primitives. User confirmation of the rendered IR is the structural element that gives the verifier something to verify *against*. Without it, NL→JoI has no spec; with it, IR↔JoI has one. The closing link of the hero argument.

**C4 — Transition-obligation coverage on IR-derived FSM (the verification mechanism).** From the user-confirmed IR we deterministically derive an IR-FSM whose transitions encode the reactive obligations the lowered JoI must honor. Scenarios are synthesized to cover every transition point in the IR-FSM. The lowered JoI runs in a reference simulator; its observable trace is checked against IR-FSM transition rules (L2). For composition cases where transition-locality breaks, full differential simulation between IR and JoI simulators is the conservative fallback (L3). All static (L1), live (L2), and fallback (L3) checks are deterministic — verdict path is LLM-free. We claim **transition-obligation completeness** under explicitly stated assumptions (§6.5): a weaker guarantee than full equivalence, stronger than ad-hoc testing. Position: model-based testing adapted to NL-derived smart-home DSL lowering — not a new paradigm, but the first principled MBT application to this setting (§6.10).

**C5 — Counterexample-guided self-correction.** Failed transition obligations from C4 produce structured retry signals at IR-feature granularity ("rising-edge encoding broken" rather than just "trace mismatch"). The signal feeds Stage 2 (lowering) for LLM retry. This closes the loop from verification failure to LLM-actionable diagnosis. Optional mutation-based diagnostic enrichment (§6.8) is included as evaluation-decided ablation — kept if it improves retry success, cut otherwise.

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

## 5. Why Standard Model Checking Does Not Apply (Even Though Our Method Borrows Its Spirit)

A natural reviewer reaction is "use SPIN / NuSMV / UPPAAL." Our method (§6) is in fact a model-based testing technique — a *lightweight cousin* of model checking — but the standard heavy-weight tooling does not fit. Two specific mismatches are the operative reasons; the rest follow.

**(1) No formal property φ to check, and no formal target semantics.** Model checking decides M ⊨ φ for a formal model M and a temporal-logic property φ. We have neither: the spec is an LLM-extracted user-confirmed IR (not LTL/CTL); the target JoI has no formal small-step semantics (manual prose only). Translating either into a standard model-checker's input language is itself the research problem we are trying to avoid. **Our method sidesteps this by treating the IR-derived FSM as the spec and the JoI simulator as the operational definition** — a stipulative semantics route (see §6.7 T1 for honest scoping).

**(2) Heavy state-space explosion under JoI's reactive setting.** A `period:100 ms` JoI program over a one-hour scenario produces 36,000 ticks; continuous sensor values and persistent flag/phase state multiply on top. Standard model checking explores reachable states; we cannot afford that under a ≤2 s edge-runtime budget. **Our method sidesteps this by checking transition obligations along observed traces, not by enumerating reachable states.** The cost is bounded by IR shape, not by JoI's reachable configuration space.

Two further frictions confirm the choice:

**(3) Idiom-induced bisimulation gap.** IR's `wait edge:rising` and JoI's `triggered`-flag idiom (or `prev/curr`, or `phase` enum) have different state shapes. Strict bisimulation fails. Our trace-level approach observes only external behavior, sidestepping the alignment problem.

**(4) Output mismatch.** Standard model checkers return ✓/✗ plus a counterexample. We need quantitative signals (per-feature transition-coverage rate, retry signals for Stage 2 self-correction). Trace-based verification gives these naturally.

| Dimension | Standard heavy MC | Our method (transition-obligation coverage) |
|---|---|---|
| Goal | M ⊨ φ | IR-FSM transition obligations on JoI trace |
| Specification | LTL/CTL formula | LLM-extracted user-confirmed IR |
| Target semantics | requires formal definition | simulator stipulates operational semantics |
| Continuous values / time | manual abstraction; decidability risk | concrete simulation |
| Idiom abstraction | custom equivalence per idiom | external trace only |
| State exploration | reachable states (exponential) | transition points in IR-FSM (bounded by IR) |
| Input language | Promela/SMV/timed automata | JoI parsed directly into simulator AST |
| Output | ✓/✗ + counterexample | per-transition pass/fail + diagnostic feature label |
| Runtime budget fit (≤ 2 s edge) | typically no | yes (§6.6 affordability) |

**Position summary.** Our method is **lightweight model-based testing**, in the lineage of MBT (Utting-Legeard) and runtime verification (Bauer-Leucker), not a new verification paradigm. What is new is the *setting* (NL→IR→LLM-lowered DSL on edge runtime) and the *coverage notion* (transition-obligation completeness on a small grammar-derived IR-FSM). Heavy model checking does not fit; lightweight MBT, adapted to this setting, does. See §6.10 for full prior-art positioning.

---

## 6. Verification Method: Transition-Obligation Coverage on IR-Derived FSM

The verification mechanism that makes the §3 decomposition useful in practice. We position this as **model-based testing adapted to NL-derived smart-home DSL lowering** — not a new verification paradigm, but the first principled application of MBT to this setting (NL→IR pipeline, LLM-generated reactive code, no formal target semantics, edge-runtime budget).

### 6.1 Why Direct FSM-FSM Comparison Is Not Viable for JoI

The textbook model-checking move is to compile both the spec and the implementation into FSMs and compare transition tables. For JoI as the implementation side, this fails for three reasons:

**(a) Informal target semantics.** JoI's behavior is documented in manual prose, not by a formal small-step semantics. FSM extraction would require defining JoI semantics from scratch — a separate research problem.

**(b) Continuous values, time, and tag resolution.** Sensor values (temperature, brightness), virtual time spanning days (cron-anchored), and dynamic device sets behind `all/any` selectors introduce infinite or continuous state dimensions. Finite-state abstraction loses boundary precision (a bug at exactly 30°C disappears between discretization grid points).

**(c) Idiom multiplicity.** The same intent can be lowered to JoI in multiple valid ways (`triggered := false` flag, `prev/curr` comparison, `phase` enum). FSM extraction by static code analysis must pattern-match these idioms; novel encodings the LLM produces fall outside any pattern catalog. Embedding such a catalog inside the verifier reintroduces precisely the closed-set assumption we want to avoid.

We restrict this argument to JoI-style smart-home DSLs (informal semantics + continuous values + idiom multiplicity). We do not claim a general theorem about reactive DSLs.

### 6.2 Therefore: Simulation-Based Trace Verification

The remaining route is to run JoI in a reference simulator, observe its external trace, and compare against IR's expected behavior.

**JoI simulator** (paper §6.5): a tick-based AST interpreter that we treat as **the operational definition of JoI for verification purposes**. The simulator handles `:=`/`=` persistence, `wait until` blocking, `period` polling, and `cron` scheduling. We do not approximate an ideal runtime; we stipulate the simulator as the canonical semantics, and bound real-hardware drift as a separate fidelity question (§6.7).

**Observable trace alphabet**: each event is a tuple `(timestamp_ms, service, method, args, affected_set)` where `affected_set` is the device IDs reached after precision-stage selector resolution. Internal JoI variables (flags, phases) are not in the trace — idiom freedom is preserved by construction.

**Limitation** (this section's central tension): simulation is sample-based. Verdict soundness depends on which event sequences are input. Without a coverage discipline, sample bias is unavoidable.

### 6.3 The Question: How to Make Simulation Coverage Defensible

Three naïve approaches all fail.

| Approach | Failure mode |
|---|---|
| Random events | Edge cases (init state, rearm, boundary, race timing) reached only by chance |
| Hand-curated scenarios | Sample bias; cannot defend against "what about case X you didn't think of" |
| Full state enumeration | State explosion; exceeds the ≤2 s edge-runtime budget |

The required property is: cover every IR-prescribed structural behavior point, but avoid combinatorial explosion. This is the gap our method fills.

### 6.4 Method: IR-Derived Transition-Obligation Coverage

**Insight.** IR is itself a small spec with formal semantics (§6.5). The 9 IR ops produce a finite, structurally bounded set of *transition points* — moments where the IR's state must change in response to an event.

**Per-op transition rules** (the building blocks):

| IR op | Transition point |
|---|---|
| `wait(cond, edge:none)` | cond becomes true |
| `wait(cond, edge:rising)` | cond transitions false→true |
| `wait(cond, edge:falling)` | cond transitions true→false |
| `if(cond, then, else)` | cond evaluation, branching |
| `start_at(cron)` | cron firing instant |
| `delay(ms)` | timer expiration |
| `cycle.body` boundaries | iteration entry, iteration exit |
| `cycle.until` | termination evaluation |
| `read(var, src)` | src observation, var register write |
| `call(target, args)` | service invocation |

**IR-FSM as composition over per-op rules.** Per-op rules alone do not capture inter-op obligations:
- *Sequencing*: `cycle{wait; call}` requires `call` follows the wait's rising in every iteration; a `call` without preceding wait is a violation.
- *Rearming*: after the body completes, the wait must re-arm for the next iteration.
- *Register dependency*: `read $v1; delay; read $v2; if ($v2-$v1 > 5, ...)` forces v1 to be observed-then-stored before v2 is read, with delay between.
- *Reachability*: branches inside `if` can render parts of subsequent control flow unreachable on a given path.

The IR-FSM is the formal artifact obtained by composing per-op rules with the IR's control-flow tree. States encode "where in the timeline are we, and what register values do we carry." Transitions encode the obligations above. The IR-FSM is *derived deterministically* from the IR; no human authoring.

**Coverage scenario synthesis.** For each transition point in the IR-FSM, we synthesize the *minimum* event sequence that activates it. The synthesizer is a static IR walk that uses the per-op rules and the FSM's path structure to bound the event domain. The output is a finite scenario set S; |S| is a function of IR shape, not of the runtime universe.

### 6.5 Coverage Claim: Transition-Obligation Completeness (with Stated Assumptions)

We claim **transition-obligation completeness**, not full lowering correctness. Precisely:

> Under assumptions (A1)–(A6), if scenario set S covers every transition point of IR-FSM(IR), and the lowered JoI program is trace-equivalent to IR on every scenario in S, then every reactive obligation prescribed by IR's per-op semantic rules is verified.

**Required assumptions** (state explicitly in the paper, do not hide):

- **(A1) Deterministic IR semantics.** The IR-FSM is a deterministic transition system; same event under same state yields same successor.
- **(A2) Transition-local obligations.** Each per-op rule's obligation is expressible by a finite predicate over (current FSM state, event, observable next emission), without reference to global trace history beyond what is captured in registers.
- **(A3) Compositional lowering.** The IR→JoI lowering preserves IR's compositional structure: if op patterns A and B compose to AB in the IR, JoI's lowering of AB realizes the obligations of A's lowering plus B's lowering.
- **(A4) Simulator faithfulness (stipulative).** The JoI simulator is the canonical operational semantics of JoI; verdicts are sound with respect to it. Real-hub drift is bounded by the real-backend validation layer (§6.7).
- **(A5) Scenario activates pre-state.** For each transition point, the synthesized scenario establishes the FSM pre-state required for that transition to fire.
- **(A6) No unmodeled nondeterminism.** No scheduler races, device nondeterminism, or external interleaving outside the simulator's modeled tick semantics.

The claim is **weaker than full equivalence** but **stronger than "we tested some scenarios."** It is the strongest defensible statement under the constraints (A1)–(A6) hold by simulator construction; the contestable assumptions are (A4) and (A6), and we address both via the §6.7 threats discussion.

### 6.6 Combinatorial Affordability

**Concern**: the IR-FSM transition point count, naïvely combined, could explode (n! worst case for arbitrary interleavings).

**Argument**: IR's timeline is dominated by sequential composition with strong ordering dependencies. A `wait` must activate before its successor `call` is possible; a `cycle` body must complete before its next iteration's wait re-arms. These dependencies make most paths near-linear in IR control-flow tree depth, not factorial in transition point count. Branching (`if`, `cycle.until`) introduces multiplicative factors but bounded by branch fan-out, which is small in observed IRs.

**Empirical defense (mandatory experiment, §9)**:

- *Stress-test variables*: nesting depth (1–6), `if` branch fan-out (1–4), simultaneous timers (1–5), cycle iterations bound (3–20), connected devices per scenario (1–10), tags per device (1–5).
- *Metrics*: per-IR scenario count |S|, total simulation time, worst-case scenario length.
- *Baselines for comparison*: random testing (matched scenario count), naïve path enumeration (when feasible), hand-crafted suite.
- *Target evidence*: |S| grows near-linearly with IR depth on the dataset and on synthetic stress tests; p95 verification time stays under 2 s.

We claim affordability empirically; we do not claim a closed-form complexity theorem, since IR variants outside the dataset may exhibit different behavior.

### 6.7 Three-Layer Verification Architecture

The transition-obligation coverage is operationalized in three layers, ordered by increasing cost. Each scenario flows through layers sequentially; early failure short-circuits later layers.

**L1 — Static well-formedness checks (≪ ms per IR/JoI pair).** AST-level checks: missing flag initializations, malformed selectors, unit-mismatched delay, references to undefined services. Catches simple lowering bugs without execution. Runs once per IR/JoI pair, not per scenario.

**L2 — IR-FSM transition coverage (~tens of ms per scenario, the hero layer).** For each scenario in S: run the JoI simulator, stream the resulting trace through the IR-FSM, and check whether each FSM transition obligation is satisfied. The IR-FSM is derived once per IR (cached); the scenario set S is derived from the IR-FSM. Most lowering bugs are detected here.

**L3 — Differential simulation (≤ 1 s per scenario, conservative fallback).** For IRs whose composition violates assumption (A2)'s transition-locality — deeply nested cycles, multi-device fan-out with cross-device state, complex compositional interactions — the IR-FSM cannot encode all obligations as local transitions. For these residual cases we fall back to running both IR simulator and JoI simulator and comparing full traces. This catches global behavioral mismatches that L2's transition-local check misses.

L3 is **honest fallback**, not a hidden weakness: it bounds the scope of L2's coverage claim by handling exactly the cases where (A2) does not hold. The criterion for routing an IR to L3 is structural (presence of nested cycles ≥ depth 3, multi-device cross-tag conditions, etc.), determined statically.

**Verdict path is LLM-free**: L1 (static analyzer), L2 (FSM derivation + simulator + transition checker), and L3 (two simulators + comparator) are all deterministic. No LLM judges correctness. This addresses circular-judging concerns common in LLM-evaluation papers.

**Diagnostic output**: when L2 fails, the violating transition obligation (with its IR feature label, optionally enriched by mutation-based diagnostics in §6.8) is the structured retry signal sent to Stage 2 (lowering). Failure localization at the IR-feature granularity, not just "trace mismatch."

### 6.8 Optional Layer: Mutation-Based Diagnostic Enrichment

A failing scenario in L2 already identifies the violating transition. We additionally label each scenario with which IR features it discriminates, by perturbing each IR field (e.g., `wait.edge:rising → none`, `cycle.until X → ¬X`, `delay 100 → 200`) and checking which perturbation causes the IR-FSM trace to diverge under that scenario. Labels are attached as metadata.

This is **mutation-based diagnostic**, not scenario synthesis. It does not add scenarios; it annotates the ones produced by §6.4. Its contribution is empirical: does richer per-feature labeling improve self-correction (Stage 2 retry) success rate over plain trace-mismatch reporting?

**Status**: included as an evaluation-decided component. If ablation (§9) shows meaningful retry-success improvement, kept as a contribution. Otherwise demoted to engineering detail or cut.

### 6.9 Threats to Validity

**(T1) Stipulative semantics / circularity.** IR semantics, simulator, and expected traces are all defined by us. Passing tests means the JoI conforms to our simulator's interpretation of IR, not necessarily to a human's intent or to real-hub behavior. *Mitigation*: human study on user-confirmed IR rendering (Stage 1's NL→IR check) grounds intent; real-backend validation layer (running representative counterexamples on actual JoI runtime) bounds simulator-vs-runtime drift.

**(T2) Real-runtime fidelity.** Edge-hub deployment may diverge from simulator on timing, scheduling, or device peculiarities. *Mitigation*: report drift rate empirically; document scope clearly.

**(T3) Idiom catalog creep.** The mutation diagnostic (§6.8) and the routing criterion for L3 (§6.7) involve some hand-crafted rules. *Mitigation*: keep the rules small, derived from IR grammar (not from JoI patterns); document each rule explicitly; report which rules fire how often.

**(T4) Tag resolution timing.** `all/any` device sets are resolved by the precision stage; we assume resolution is fixed for a scenario (devices do not appear/disappear mid-scenario). *Mitigation*: state explicitly; note that dynamic device-set verification is out of scope.

**(T5) Concurrency / races.** Out of scope. We verify single-program lowering against single-IR. Concurrent automations and runtime races are explicitly excluded (§1.6).

**(T6) LLM lowering bug class coverage.** Our framework verifies *lowering correctness against IR*. It does not verify whether the LLM-extracted IR matches the user's actual intent — that is Stage 1's user-confirmation responsibility. We do not double-count: the verifier's claim is conditional on the user-confirmed IR being the spec.

**(T7) Failure localization granularity.** L2 reports the violating transition obligation; L3 reports trace divergence. We claim IR-feature-level localization for L2-caught bugs; L3 reports require additional analysis. Both failure modes feed Stage 2 retries.

### 6.10 Positioning and Prior Art

The technique is **model-based testing adapted to a new setting**. We do not claim a new verification paradigm.

- **Standard MBT** (Utting-Legeard 2007 and successors): derive tests from a model, compare implementation traces. We do this.
- **Conformance testing** (Tretmans IOSTS, distinguishing-sequence generation): also relates to our transition-coverage approach.
- **Runtime verification / monitoring** (Bauer-Leucker): L2's transition-stream check is in this lineage.

What is novel for top-tier:

- **Spec source**: the model is not hand-authored. It is an LLM-extracted user-confirmed IR from a NL→DSL pipeline.
- **Target**: LLM-generated reactive DSL code with informal semantics and idiom multiplicity.
- **Domain**: edge-runtime smart-home automation with ≤2 s budget and offline operation.
- **Coverage discipline**: IR-FSM transition-obligation coverage as a structurally-derived completeness notion (weaker than full equivalence, stronger than test sample).
- **Integration**: verification feeds Stage 2 retry signal at IR-feature granularity, closing the LLM-correction loop.

The contribution is the **integration and adaptation of these techniques to a setting where MBT has not been applied**, plus the structural completeness notion (transition-obligation coverage on IR-FSM derived from a small IR grammar).

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
