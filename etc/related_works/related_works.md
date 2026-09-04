# Related Works — consolidated catalog

> **Purpose**: single source of truth for related work. Per system, TWO axes:
> **Axis 1 — primitive/feature support** (which reactive-temporal expressions the language/platform supports).
> **Axis 2 — verification** (how it checks correctness: syntax only? execution result? predictive simulation? re-translation/round-trip? test harness? AND — does verification cover only TRIVIAL tasks, or complex reactive-temporal behavior? trivial-only verification is meaningless for our argument).
> Replaces the per-folder `*_ko_overleaf/` dirs (those are KOR-LaTeX working copies; keep the PDFs/txt there as sources).
> **Discipline (lesson)**: read sources CLOSELY — we initially missed TaskSense's result→NL re-translation step. Quote exact constructs; don't trust shallow summaries.

## Legend
**Primitives (Axis 1)** — ✅ first-class keyword / ⚠️ idiom-only / ❌ unsupported:
P1 one-shot if · P2 level "when X true" · P3 edge "when X changes/becomes" (event-vs-state) · P4 sustain-for-duration · P5 debounce/flap · P6 hysteresis/deadband · P7 periodic "every N" · P8 cron/time-window · P9 alternation/toggle/phase · P10 bounded repeat/count · P11 delay/sequencing · P12 persistent state var · P13 timer/schedule · P14 cross-device all/any.

**Verification tiers (Axis 2)** — ✅/⚠️/❌:
T1 syntax/schema · T2 static (lint/conflict/loop/safety) · T3 predictive sim / dry-run / behavior preview · T4 test harness / replay / regression · T5 formal (model-check LTL/CTL/FSM) · T6 **intent-conformance** (user-confirmed *positive* behavioral spec + expected-trace oracle) · T7 post-hoc runtime trace/log.
*(Cross-system fact from the 2026-05-26 survey: **T6 is empty across the field**; see [[reference-iot-dsl-verification-landscape]].)*

---

## A. LLM-for-IoT: codegen / agents (the direct competitors)

### GPIoT — SenSys'25 (local: related_works/sensys_gpiot_ko_overleaf/)
- **What**: fine-tunes locally-deployable SLMs (Llama2-13B + LoRA, "PECT" co-tuning) for IoT **program synthesis**. 3 decomposed stages: TDSLM (task decomposition) → RTSLM (requirement→spec, CoT+RAG) → CGSLM (code gen). Datasets TDD (36k) / CGD (35k); benchmark **IoTBench** (100 held-out).
- **Target language**: **Python (DSP/ML algorithms** — ECG Pan-Tompkins, HAR, WiFi-CSI). NOT reactive automation.
- **Axis 1 (reactive primitives)**: N/A — different problem class (algorithm synthesis). P3–P9 not attempted.
- **Axis 2**: **Pass@k execution tests** (oracle EXISTS: algorithm + test input + gold output) + SonarQube (bugs/smells, post-hoc) + manual review + user trials (URC 1–5). **Task complexity**: meaningful — real DSP/ML tasks with executable oracle.
- **Delta to us**: verifies BECAUSE its target has an oracle (test I/O); reactive automation has none. No user-confirmed behavioral spec, no intent-conformance check. Same local-SLM premise as us → key baseline (RQ1 FT-SLM).

### TaskSense — SenSys'25 (local: related_works/sensys_tasksense_ko_overleaf/main.tex — READ CLOSELY)
- **What**: "translation-like" approach — NL query → **sensor language** (tools=vocabulary, dependencies=grammar) → executable **tool-call plan** to coordinate heterogeneous sensors for **complex QA** ("Did Bob overwork without breaks?"). Cloud LLMs (6 models). Auto-registers sensor vocab/grammar; RAG query-plan examples.
- **Axis 1**: it's a planning/QA orchestrator, not a reactive-automation DSL. Has data-dependency + control-dependency grammar; P14-ish (multi-sensor composition). No P3–P10 reactive-temporal primitives.
- **Axis 2 — TWO mechanisms (don't conflate; we initially missed the 2nd):**
  1. **Plan verification = DETERMINISTIC subgraph matching** (§main.tex L224): grammar→DAG, plan→DAG, check plan-DAG ⊆ grammar-DAG → catches wrong dependencies + hallucinated tools. + **solvability check** (L220): are the needed tools/labels present; unsolvable → no plan. This is **structural well-formedness** (≈ AWS IoT Events "Run analysis" ≈ our L1), NOT intent-conformance.
  2. **Result→NL re-translation = ANSWER generation** (L58/L150/§5.4 L260, **LLM-based**): execution **result data** is re-translated to a natural-language **answer** to the query ("Yes, 3 hours without a break"). Metric = "answer accuracy". L268: "SQL 질의와 비슷하게 결과 테이블에서 정보 추출". This is the system OUTPUT (inspectable answer, like SQL rows), NOT a code-verification round-trip.
  + dynamic plan adaptation from runtime feedback (data availability/quality/exec results) — T7-ish online.
- **Task complexity**: complex multi-sensor QA — but verification (subgraph match) only checks *plan executability*, not behavioral intent.
- **Delta to us**: (1) FSM is *internal planning* rep, verified for *dependency solvability* — ours is a *behavioral* spec verified for *conformance*; (2) its intent-confirmation is "show the user an NL ANSWER" — works because QA has an **inspectable data result** (the SQL-row analogue); **reactive automation has NO such answer** (output = future device actions), so this doesn't transfer; (3) re-translation is **LLM-based** → on local ≤9B unreliable (our secondary defense). Closest "FSM + NL" system → must differentiate in §1/§5/§10.

### SimuHome — ICLR'26, SNU (local: related_works/iclr_simuhome_ko_overleaf/)
- **What**: high-fidelity **time-accelerated smart-home SIMULATOR** + **600-episode benchmark** for LLM smart-home **agents**, grounded in **Matter protocol**. Models how device ops **continuously affect environmental variables over time** (AC→temperature trajectory, humidity); existing benchmarks treat home as static. 3 task categories incl. explicit device control, (temperature/conditional) control, **workflow scheduling** (feasible + infeasible variants). Time-accelerated so scheduled workflows are evaluated immediately. Fully reproducible.
- **Axis 1**: not a DSL — a simulator/benchmark. Covers temporal env dynamics + **workflow scheduling** (closest to our cron/periodic/delayed behaviors). Models continuous physics (more than our abstract trace).
- **Axis 2**: each episode has a **verifiable goal** (oracle = simulator goal-state check); agents' actions produce observable verifiable state changes. **Evaluation oracle for a benchmark**, per-episode pre-defined goal. Suggests accelerated sim as an env for agents to **pre-validate** actions.
- **Key measured finding (supports OUR motivation)**: across **18 LLM agents, workflow SCHEDULING is the hardest category**, failures persist; CoT (GPT-5.1) helps but unresolved → reactive-temporal scheduling is genuinely hard for LLMs.
- **Delta to us**: SimuHome verifies *agent task-completion against a benchmark goal* (oracle = benchmark-supplied goal state); we verify a *generated reactive RULE against a user-confirmed behavioral spec* (oracle = derived from confirmed IR). It is an **agent-evaluation environment**, not a deploy-time rule-intent verifier. BUT: its physics-grounded temporal simulator is a candidate for our **sim-fidelity / deployment (RQ8)** and a strong citation that temporal smart-home simulation + scheduling difficulty are real. (Possible eval environment / baseline.)

### LLMind 2.0, Sasha, SAGE, NL→Home-Assistant (from survey [[reference-iot-dsl-verification-landscape]])
- **LLMind 2.0**: distributed coordinator → NL subtasks → on-device lightweight-LLM generates per-device **Python control scripts** (RAG + FT). Verification: templates/RAG arg-extraction, "best-effort, not guaranteed"; runtime timeout deadlock-avoidance. No intent oracle. Target inherits idiom problem.
- **Sasha**: single-step LLM reasoning ("make it cozy" → device settings). No decomposition, no persistent automation, no temporal structure, no verification.
- **SAGE**: runtime agent; tree of LLM prompts → tool-call sequence; persistent commands = Python condition + **polling loop** (edge/periodic collapsed to polling idiom). Sequencing first-class; no sustain/hysteresis/cron/FSM; no intent oracle.
- **NL→Home-Assistant (arXiv 2505.02802)**: zero-shot NL → HA automation JSON. Target (HA) is expressive (`for:`/state/time first-class), but dominant failure = **malformed trigger values/keywords** ("sunrise" w/o timestamp, "hot" not numeric) → LLM can't reliably POPULATE the idiom even when the slot exists. Correctness = JSON validity + manual inspection; conversational NL round-trip but **no behavioral oracle**. Closest NL→automation-codegen; lacks our verification loop.

---

## B. Production IoT automation platforms  [HA/openHAB = FOCUS — agent deep-dive PENDING MERGE]
*(Quick matrix from survey; HA & openHAB to be expanded with close doc reading from /tmp/rw_ha_openhab.md.)*

| Platform | first-class higher-order primitives | Verification (Axis 2) | trivial-vs-complex |
|---|---|---|---|
| **Home Assistant** (full entry below) | P4 `for:` (trigger+cond), P3 state `from/to`, P8 `time_pattern`, P11 `wait_template`/`wait_for_trigger`, P10 `repeat`, P12 helpers, `choose`; ⚠️ P6/P9 | T1 `check_config` (voluptuous schema, no behavior); **no predictive sim**; "Run actions" fires real devices + skips triggers/conditions; Trace = post-hoc; **no NL behavioral re-translation**; no end-user test harness | static/trivial only — **NO** intent-conformance |
| **openHAB** (full entry below) | P3 `changed from X to Y`/`received command`, P8 `Time cron`, P14 Group aggregation `OR/AND/AVG`; ⚠️ P4 DSL `createTimer` / ✅ P4 JRuby `for:`; Rule Templates | T1 **Xtext/Xbase typed compile** (stronger; type/ref errors) + VS Code LSP; **T4 JRuby RSpec + `timecop`** harness (offline, fires `for:` timers, CAN assert complex temporal pre-deploy) — but hand-written assertions, no intent/NL/coverage, JRuby-only | strongest tooling, but **NO** intent-conformance |
| ESPHome | P4 `for:`, P5 `delayed_on/off`, P7 `interval`, P8 cron, P10 `repeat:count`, P12 `globals` | T1 `compile` (schema+pin-reuse, not behavioral); T7 logs | trivial only |
| Hubitat Rule Machine | P4 "stays", P7 Periodic | form-validate; "Run Actions" fires real; T7 logs | trivial only |
| webCoRE | P3 `changes`, P4 `stays…for`, P7 `every` | piston editor validate; "Simulate" runs live; T7 trace | trivial only |
| Node-RED | P3 `rbe`, P5 trigger node, P7/P8 inject | T1 wiring; **T4 `node-red-node-test-helper` + flow-asserter** (manual unit tests); inject = ad-hoc; no behavioral oracle | partial T4, manual |
| SmartThings Rules API | P3 `changes`, P7 `every`, P14 `aggregation` | JSON schema; no sim; T7 history | trivial only |
| **AWS IoT Events** (retired 2026) | hand-authored **FSM** engine: states/onEnter/onInput/onExit, transitionEvents+nextState, SetTimer/timeout, $variable; P9/P12/P13 first-class; P3/P4/P5/P11 still idiom (counter `pressureThresholdBreached` +3/−1) | **"Run analysis"** = 7 STRUCTURAL checks (unreachable states, missing triggers) = well-formedness ≈ **our L1**; send test inputs (manual); no intent oracle | structural only |
| **IEC 61131-3** (PLC) | richest low-level first-class: `R_TRIG/F_TRIG` (P3), `TON` (P4), `TOF` (P5/P11), `CTU/CTD` (P10), `RETAIN` (P12) | vendor compilers (T1); **PLC simulators standard** (T3, manual scenario); **model-checking RESEARCH-only** (nuXmv/CBMC, ST→LTL, safety props) | T3 sim exists but manual; formal = research, safety-props not positive intent |

**Cross-platform verdict**: even the most expressive platforms (HA/ESPHome/IEC-61131) provide NO T6 (intent-conformance). Verification = syntax + post-hoc trace; "simulate" fires real devices or is manual. → **gap is verification, not expressiveness.**

### AWS IoT Events — the industrial FSM-as-automation precedent (CLOSEST to our IR-FSM substrate) [retired 2026-05-20]
- **What**: AWS managed service whose unit is a **"detector model" = an explicit hand-authored finite state machine**. Authored graphically (drag states, draw transition arrows) or as JSON; engineer-written.
- **FSM structure (precise, from docs)**: `states[]` + `initialStateName` + Start state. Each state: **`onEnter` / `onInput` / `onExit`** event hooks; each event = boolean `condition` + `actions` (run iff condition true). **`transitionEvents`** (in onInput) = condition + **`nextState`** → state transition. **Inputs** arrive as MQTT/IoT-Core messages, referenced `$input.X.sensorData.y`. **`$variable`** = persistent registers (`setVariable` assign/increment/decrement). **`SetTimer`/`ClearTimer` + `timeout("name")`** in conditions = the timer mechanism.
- **Axis 1 (primitives)**: P9 phase/state, P12 persistent var, P13 timer = first-class (it IS an FSM). **But P3 edge / P4 sustain / P5 debounce / P11 sequencing are STILL hand-coded idioms** — the official greenhouse example encodes "pressure>70 sustained ⇒ dangerous" via a **counter idiom** `pressureThresholdBreached` (+3 on high input, −1 on okay) over states+variables — i.e. the SAME idiom-encoding problem as JoI, even in an FSM-native tool. Devs also manually re-implement if/elseif/else via ordered transitionEvents + an `enteringNewState` flag.
- **Axis 2 — "Run analysis" = purely STRUCTURAL/static** (runs WITHOUT input data; must fix all errors before publish). **7 analysis types, ALL well-formedness/type/reachability — NONE behavioral or intent:**
  1. `supported-actions` (action type valid + region), 2. `service-limits` (≤20 states, ≤20 transitions, timer≥60s…), 3. `structure` (transition→existent state; unique state names; valid initialState; ≥1 input in a condition; **unreachable state/action detection**; **infinite-message-loop warning** on expiring timers; input-read-vs-timer-expiry `triggerType("MESSAGE")` guard), 4. `expression-syntax`, 5. `data-type` (int/dec/str/bool compat; condition→boolean), 6. `referenced-data` (variable/timer **set-before-use** "broken variable"), 7. `referenced-resource` (input/resource exists).
  - **NO simulation, NO predictive behavioral preview, NO intent-conformance, NO NL rendering/confirmation.** "Testing" = publish, then send real-ish inputs and watch (manual, post-deploy). So T1 ✅, T2 ✅ (reachability/loop — slightly richer than our L1), **T3/T6 ❌, T7 ✅ (CloudWatch).**
- **Task complexity**: the FSM can express complex stateful behavior, but "Run analysis" only checks the FSM is **well-formed/typed/reachable**, never that it **does what the author intended**.
- **Delta to us (sharp — this is the key industrial comparison)**: AWS IoT Events proves **FSM is the right substrate** for reactive automation (states/timers/vars/phases first-class) — but (i) **hand-authored by an engineer**, not NL-derived; (ii) **no user-confirmation / no NL projection** for a non-developer to approve; (iii) its checking is **structural well-formedness (≈ our L1 + reachability), not behavioral trace-conformance (our L2)**; (iv) edge/sustain/sequencing remain **author-discharged idioms**, whereas our lowering discharges them and the IR keeps them first-class for the spec. → Cite as: "industrial validation of FSM-as-automation-substrate; our novelty = the FSM is *derived from a user-confirmed NL-projected behavioral spec* and checked by *trace-conformance*, not hand-authored and structurally linted." (Honest: their `structure` reachability/loop checks overlap our L1 — L1 is not the novel part; L2 + confirmation is.)

### Home Assistant & openHAB — verification details (the strongest platform counterpoints, handled)
*(from close doc reading 2026-05-26; HA/openHAB are the FOCUS platforms — these nuances must not be missed.)*
- **Neither does NL behavioral re-translation / round-trip.** Important caveat to state precisely (else a reviewer thinks HA does it): HA shipped an opt-in **"Suggest" AI button (2025)** that sends the automation config to an LLM — but it proposes only **name/description/category/labels (metadata)**, NOT a behavioral paraphrase; `alias`/`description` are **user-typed free text**. openHAB `description` likewise user-typed. → no intent round-trip on either.
- **No predictive simulation / dry-run on either.** Behavior appears only after a REAL trigger on REAL devices. HA **"Run actions"** fires real devices AND **skips triggers+conditions** (leaves `trigger.*` unpopulated → can't test trigger-reading or chained logic — documented limitation). HA community has long-standing unmet requests for a simulator.
- **HA Automation Trace = strictly post-hoc** (Trace Timeline / Step Details / Changed Variables / A-B condition branches / full config) — debugs ONE past real run; not predictive.
- **openHAB JRuby RSpec + `timecop` = the closest pre-deploy behavioral test we found (must concede honestly).** `openhab-scripting` ships an endorsed **RSpec harness**: runs *real rules* in an *embedded openHAB runtime, offline, no hardware*; `Timecop.travel(5.minutes)` + `execute_timers` **fires the implicit timers behind the `for:` sustain feature** → can deterministically assert sustain/edge/timing **before deploy**. **DELTA (why it's still not us)**: it is a **generic xUnit framework needing human-written assertions per rule** — NO user-confirmed spec, NO auto-derived obligations, NO coverage notion, NO NL/intent linkage; opt-in, **JRuby-only** (JS limited, classic DSL none). So it sits at **T4 (test harness), not T6 (intent-conformance)**. This is the single most important "prior art can test temporal behavior" concession — frame as: *the capability exists as a developer test harness, but the spec (assertions) is hand-written, not user-confirmed/auto-derived, and only on one scripting surface.*
- **Static validation differs in kind**: HA = voluptuous **schema** (keys/types/enums, no behavior); openHAB classic `.rules` = real **Xtext/Xbase typed compile** (catches type errors, unresolved refs; stronger static layer) via VS Code LSP.
- **Verdicts**: HA = **NO** intent-conformance (schema + post-hoc trace only). openHAB = **NO** intent-conformance (strongest tooling of the two; typed static + offline RSpec temporal test, but hand-written assertions, no intent/NL/coverage linkage).

---

## C. Academic TAP / end-user automation (EUD)
- **Ur et al. CHI'14** — practical TAP; ~¼ of desired behaviors need multi-trigger conjunction base IFTTT can't express; event-vs-state observed empirically, not formalized. (`ur14tap`)
- **Brackenbury/Ur CHI'19 "How Users Interpret Bugs in TAP"** — formalizes **Event–Event / Event–State / State–State** temporal paradigms; event=instantaneous edge, state=sustained level; **10 bug classes** incl. Infinite Loop, Repeated Triggering, Nondeterministic Timing, Time-Window Fallacy. Study of paradigms, not a language. (`brackenbury19`) — strong cite for "edge/level is load-bearing & users misread it".
- **SENSATION INTERACT'21** — authoring language with **`when` (event) vs `while` (state) as distinct keywords** → clearest first-class edge/level counterexample. (`sensation21`)
- **IoT-Spaces survey IS-EUD'21 (Corno)** — argues ECA must distinguish trigger{state,event} × action{instantaneous,extended,**sustained**}; proposes **"sustained actions" (P4) as first-class needed but missing**. (`corno21`)
- **AutoTap ICSE'19** — users click **invariant LTL properties** ("AC-on & window-open never together"); compiles to LTL, **synthesizes/repairs** TAP to satisfy. **DELTA (closest neighbor)**: invariant/negative guardrails, satisfaction-checked vs our positive complete behavioral spec + trace-equivalence; never shows user an expected device-action timeline. (`autotap19`)
- **Trace2TAP IMWUT'20** — synthesizes TAP rules from sensor traces (SAT); handles out-of-order events; target = standard SmartThings TAP, no first-class duration/repeat.
- **"Helping Users Debug TAP" IMWUT'22 / UbiComp'23 (Zhang/Lu/Ur)** — KEY NEIGHBOR (full entry in §F#1): traces + user feedback + 3-D smart-home sim + 10 bug classes (incl. timing) → SAT repair of *human-authored* TAP. Closest "traces+intent+sim" prior work; delta = implicit-feedback spec + SAT-repair vs our confirmed-positive-spec + trace-equivalence on LLM-generated code.
- **AwareAuto arXiv'24** — NL→automation IR; trigger quadruple incl. event/state **"mode" field**; 9 complexity classes, time triggers + timer-delays. **Closest NL→IR neighbor**; lacks the verification loop. (`awareauto24`)

## D. IoT automation verification — **active but targets SAFETY/CONFLICT/ANOMALY, not intent-conformance** (post-2020 focus)
**[CLAIM, the wedge-reinforcer]** Smart-home automation verification is a hot, highly-cited area through 2024 — but EVERY system verifies *safety properties / rule-interaction vulnerabilities / anomalies* (avoid known-bad states/conflicts), targets *human-authored* TAP rules, and uses model-checking against *negative/fixed* properties. **None verifies whether a (generated) automation matches the USER's positive intent.** → T6 still empty, even in the security branch.

**Post-2020 (primary):**
- **TAPFixer — USENIX Security 2024** — automatic **detection + repair** of home-automation vulnerabilities via **negated-property reasoning** (model checking); 86.65% repair success; benchmark + user studies. **DELTA (new closest-neighbor, alongside AutoTap & TAP-debug)**: repairs against *negated safety/liveness properties* on *human-authored* TAP — vs our *positive behavioral spec + trace-equivalence* on *LLM-generated* code. (arXiv 2407.09095)
- **TAPInspector — IEEE TIFS 2022** — auto-extracts TAP rules → hybrid model → **model-check safety + liveness** of *concurrent* TAP; 9 new rule-interaction vuln types; 533 violations / 1108 market apps. Verifies *interaction safety/liveness*, not intent. (arXiv 2102.01468)
- **HAWatcher — USENIX Security 2021** — semantics-aware **runtime ANOMALY detection**: mines hypothetical correlations (apps/device-types/relations/locations) as invariants, checks against event logs (prec 97.8/recall 94.1). **RUNTIME, post-deploy, anomaly — not pre-deploy intent.** (sec21-fu-chenglong)
- **Detecting & Handling IoT Interaction Threats (USENIX Security 2023, Chi et al.)** — extends iRuler to multi-platform/multi-control-channel (voice/app/physical) inter-rule threats. (iRuler successor)
- **Sigfrid (recent)** — scene-interaction graphs + LLM to detect rule *interferences/conflicts* (LLM-based conflict detection; still conflict, not intent).

**Seminal (pre-2020, cite briefly as origins, de-emphasize):**
- **Soteria ATC'18 / IoTSan MobiSys'18** — apps→model→model-check FIXED safety props (NuSMV/SPIN), author-independent. **iRuler CCS'19** — SMT+model-check inter-rule vulns (6 types) via NLP on trigger/action text. **Fernandes S&P'16** (Distinguished Paper) — first SmartThings empirical security analysis (overprivilege) → motivates verification need. **SAFECHAIN DSN'19** — FSM model-check attack chains. **DeLorean S&P'22** — delay-attack model; weaponizes absence of debounce/ordering/timer guarantees in TAP (evidence P5/P11/P13 unspecified in deployed TAP).

## E. NL→code verification PRECEDENT (positive — oracle exists)
- **text-to-SQL**: execution accuracy (gold result), **execution-guided decoding** (`wang18execguided`), self-consistency, Spider/test-suite (`yu18spider`). Verifiable b/c DB engine = executable oracle + result rows = inspectable output.
- **code-gen**: **CodeT** (`chen22codet`, test-based filtering), **Self-Debug** (`chen23selfdebug`, execution-feedback repair). Oracle = unit tests.
- **Our framing**: these prove oracle-backed NL→code verification works; their *prerequisites* (executable reference + inspectable output) are exactly what reactive automation lacks → we DERIVE the missing reference oracle from a user-confirmed IR; trace-equivalence = reactive analogue of execution accuracy. ("Execution ≠ verification": emulator runs candidate, not an oracle.)

## F. Cited secondary IoT papers (triaged 2026-05-26)
**Verdict: only #1 does automation verification relevant to us; the other 5 use HA/openHAB as substrate/citation only.**
- **#1 "Helping Users Debug Trigger-Action Programs" (IMWUT 2022 / UbiComp'23, Zhang/Lu/Ur) — HIGH relevance, a KEY neighbor (promote to §C/§D).** USER-facing TAP debugging (not a new language): **10 bug classes** spanning control-flow + **timing** (Time-Window Fallacy, Missing Reversal, Flipped Triggers, Secure-Default Bias), studied in a **3-D smart-home simulator**; two tools collect **implicit/explicit user feedback on simulated traces** ("what should/shouldn't have happened") → **SAT-solving auto-repair** of the TAP. **DELTA to us**: spec = user's *implicit feedback on past traces* (not a confirmed positive behavioral artifact); target = **human-authored** TAP repaired by **SAT over feedback**; ours = **LLM-generated** automation verified by **trace-equivalence against a user-confirmed behavioral spec**. (Closest "traces + user-intent + smart-home-sim" prior work — must differentiate alongside AutoTap.) PDF: people.cs.uchicago.edu/~shanlu/paper/UbiComp23.pdf
- **#5 IoTRepair (IoTDI'20, PSU/Purdue)** — MEDIUM-LOW, contrast point. Runtime **device-FAULT** handling (restart/retry/checkpoint/restore); fault model = device failure / network disruption / stuck-unsafe states (~50–63% fewer incorrect states). Ground truth = correct *device state*, NOT user intent; no trace-equivalence. Good explicit contrast: "automation-goes-wrong → fix" but faults are hardware/runtime, orthogonal to our LLM logic/intent mismatch.
- **#2 SoundOff (IMWUT'25)** — LOW. Battery-free ultrasound sensing; HA = downstream actuation sink only. No automation model, no verification.
- **#3 Sovereign (IEEE IoT-J'22, UCLA)** — LOW. Data-centric network+security system; HA & openHAB cited as centralized/cloud baselines it positions against. No automation-behavior verification.
- **#4 FSAIoT (forensic state acquisition, openHAB substrate)** — LOW. **CITATION FLAG: matches ARES 2017, NOT "IEEE IoT-J 2019" — verify venue/year before citing.** openHAB = forensic state collector; no automation/verification.
- **#6 Unvoiced (SenSys'24)** — NONE. Silent-speech earable; HA Alexa integration cited as a voice endpoint only.

---

## F-bg / verification background
- Model-based testing (`utting12mbt`); runtime verification / monitor synthesis LTL3 (`bauer11lt3`) — we are lightweight MBT+RV in a new setting (NL→DSL loop), not a new paradigm.

## Citation slots — verification/security branch (add)
- `tapfixer24` TAPFixer (USENIX Sec'24, detect+repair, negated-property) — new closest-neighbor
- `tapinspector22` TAPInspector (IEEE TIFS'22, safety+liveness model-check concurrent TAP)
- `hawatcher21` HAWatcher (USENIX Sec'21, runtime anomaly via mined invariants)
- `chi23` Detecting&Handling IoT Interaction Threats (USENIX Sec'23, multi-channel inter-rule)
- `soteria18`/`iotsan18`/`iruler19`/`fernandes16` (seminal origins, brief)
- `tapdebug22` Helping Users Debug TAP (IMWUT'22/UbiComp'23) — §C/§F#1 key neighbor

## TODO
- [x] merge HA + openHAB deep-dive (Axis-1/2 + trivial-vs-complex + RSpec/timecop concession) → §B.
- [x] §F cited-papers triaged (only #1 TAP-debug relevant; others substrate-only).
- [x] §D rebuilt post-2020-first (TAPFixer'24 / TAPInspector'22 / HAWatcher'21); seminal de-emphasized.
- [ ] **CITATION FIX**: "IoT-forensics" = **FSAIoT, ARES 2017**, not IEEE IoT-J 2019 — correct venue.
- [ ] AWS IoT Events deep-dive added — done.
- [ ] confirm GPIoT user-study N + TaskSense re-translation lines if quoting verbatim.
- [ ] SCOPING NOTE for paper: synchronous reactive langs (Lustre/Esterel/SCADE) ARE formally verified — but not end-user, not idiom-encoded, require formal expertise; out of our RA-DSL scope. (pre-empt "but reactive DSLs are verified".)
