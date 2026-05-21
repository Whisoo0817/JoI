# Why FSM Model Checking Does Not Apply to JoI

Companion note to `paper_summary.md` §5 and §6.1. Systematizes the negative-result argument for the paper's §4/§5 negative-result section, and pre-empts reviewer questions of the form "why not just compare final states / observe transitions / use SPIN / use SMT?"

Sources: `paper_summary.md` §5, §6.1, §6.4; `project_paper_framework.md` (canonical framework, 2026-05-08); `project_open_design_options.md`; `project_simulator_design_decisions.md`. Sections marked **[reasoned]** are not in the existing documents and are added by inference from the framework's first principles.

---

## A. Why FSM model checking is not viable — root causes on the JoI side

### A-1. JoI semantics is not formally defined (documented, §5(1), §6.1(a))

JoI's behavior is described in **manual prose** only. There is no small-step operational semantics, denotational semantics, or axiomatic specification.

Consequence: extracting an FSM `M(JoI program)` requires first defining JoI's semantics from scratch — *itself a separate research problem* and the very problem we set out to avoid. Without a formal `M`, the model-checking decision problem `M ⊨ φ` is undefined.

### A-2. There is no temporal-logic property φ (documented, §5(1))

Our specification is an **LLM-extracted, user-confirmed IR**, not an LTL/CTL/μ-calculus formula. Translating IR to a standard temporal logic is itself a research problem; furthermore, some IR reactive obligations (e.g., `cycle.until` semantics, register-dependency obligations like `$v2 - $v1 > 5`) do not fall cleanly into the prefix-closed safety/liveness classification used by standard model checkers.

### A-3. JoI's state space is intrinsically infinite/continuous (documented, §6.1(b))

| State dimension | Why it breaks finite-state abstraction |
|---|---|
| Continuous sensor values (temperature, brightness, lux) | A boundary bug at exactly 30°C disappears between any discretization grid points. |
| Virtual time spanning day/week (cron-anchored) | "Mon/Wed 04:00" patterns require reasoning over week-long reachability. |
| Dynamic tag resolution (`all(#X)`, `any(#Y)`) | Device-set membership is runtime-dependent; not captured by static finite abstraction. |
| Persistent register state (`:=`, `=`) | Flags, phases, prior-value caches accumulate; JoI's `period+if` idiom encodes effectively unbounded history. |

### A-4. Idiom multiplicity — ground truth has multiple valid encodings (documented, §6.1(c); `project_paper_framework.md` C3 = "multi-form validity")

The same NL intent (e.g., "fire once on rising edge") can be lowered to JoI in at least three structurally distinct ways:

- `triggered := false` flag idiom
- `prev/curr` value comparison idiom
- `phase` enum idiom

These produce **different internal state shapes**. Naïvely comparing spec-FSM transition tables against impl-FSM transition tables fails on all valid idioms simultaneously.

Patching this with an *idiom catalog* baked into the verifier reintroduces a **closed-set assumption** — exactly the assumption we demoted catalog-as-hero to avoid (decision 2026-05-06). When the LLM produces a novel encoding outside the catalog, the verifier silently misjudges.

### A-5. Strict bisimulation is not a practical verifier target across idioms **[reasoned, sharpened from §5(3); codex-reviewed 2026-05-21]**

Strict bisimulation is formally *definable* whenever two transition systems and an observable label set are defined — declaring an equivalence relation is a free operation, not blocked by anything in the source DSL. The defeating claim must therefore be sharper: **a canonical, syntax-independent bisimulation relation that holds across all valid idiom lowerings simultaneously is unavailable** without one of two additional artifacts: (i) a formal small-step semantics for JoI plus per-idiom abstraction functions reducing each lowering to a canonical state shape, or (ii) a closed idiom catalog embedded in the verifier that pattern-matches each lowering to a known abstraction. Both options reintroduce exactly what the rest of this argument excludes — formal JoI semantics (A-1) or closed-catalog assumptions (A-4).

Weakening to **weak bisimulation** (τ-hiding internal actions) or **trace inclusion** only relocates the problem: deciding which internal actions to hide requires *knowing the idiom*, returning us to A-4. The only escape is to discard internal state alignment entirely and observe purely **external** behavior — which is what §6.2 (trace-level verification) does.

The corrected wording for paper §6.1(d): *"strict bisimulation is not a practical verifier target across idioms without formal JoI semantics + abstraction functions or an idiom catalog,"* rather than *"not even definable."* The contribution claim does not depend on the stronger framing.

### A-6. Output mismatch with standard MC tooling (documented, §5(4))

Standard model checkers return ✓/✗ plus a single counterexample. We need **per-feature transition-coverage rate** and **IR-feature-grained retry signals** for Stage 2 self-correction (C5). The tool output shape is mismatched.

### A-7. Tool-chain encoding barrier **[reasoned]**

For any standard target — Promela (SPIN), SMV (NuSMV), timed automata (UPPAAL) — encoding JoI's register semantics + cron + tag resolution + continuous sensors is a **major undertaking, publication-sized on its own**, and an encoding error invalidates the verdict. Mismatched with our budget: 9B local model on edge, ≤2 s verdict budget, offline.

---

## B. Why exhaustive model checking is impossible — state explosion decomposed

Drivers, multiplicatively combined:

| Explosion axis | Rough size | Source |
|---|---|---|
| Virtual time (weekly cron) | 7 days × 86 400 s × 10 ticks/s ≈ **6.05 M ticks** | §5(2), simulator design |
| `period:100 ms` over 1 h | 36 000 ticks | §5(2) |
| Continuous sensor values | ℝ in theory; ≥10⁴ resolution in practice | §6.1(b) |
| Persistent registers (N variables) | Multiplicative in N | §6.1(b) **[reasoned]** |
| Tag fan-out (`all(#X)`) | Runtime-dependent; combinatorial | §6.1(b) |
| Branching (`if`, `cycle.until`, nested) | Branch fan-out × depth, multiplicative | §6.6 |

Product ≫ 2^(tens to hundreds). Edge budget is **≤ 2 s on a 9B local model**. Both memory and time are infeasible.

**Symbolic and bounded variants also fail [reasoned]:**

- **Symbolic MC (BDD-based)** — continuous-valued sensor predicates collapse BDD compression efficiency.
- **SMT-backed MC** — register obligations like `$v2 - $v1 > 5` combined with cron arithmetic enter nonlinear-arithmetic decidability territory.
- **Bounded MC (k-step)** — cron patterns demand `k` reaching a week (≥6 M ticks); outside BMC's productive regime.
- **CEGAR (abstraction refinement)** — predicate selection is **idiom-specific** (A-4), so the abstraction itself becomes a closed-catalog problem.

---

## C. Why "final-state only" was rejected **[reasoned; not in current paper draft]**

A reviewer or simpler-baseline advocate might propose: skip transitions, just compare end states after a long simulation horizon.

| # | Failure | Concrete example |
|---|---|---|
| C-1 | **Reactive programs have no final state.** `cycle`, `period`, `wait`, `start_at(cron)` are non-terminating; "final state" is undefined. | A house-rules program runs indefinitely. |
| C-2 | **Idempotent end states hide bugs.** | "Blink twice" lowered to "never blink" still ends with light off — indistinguishable. |
| C-3 | **Re-arming bugs invisible.** | A one-shot-after-first-trigger bug yields the same end state as the bug-free run. |
| C-4 | **Ordering of side-effects lost.** | "Stop recording then save" vs "save then stop recording" — same end state, opposite externally-visible order. |
| C-5 | **Timing obligations lost.** | `delay 5min` mutated to `delay 5s` yields the same end state. |
| C-6 | **Frequency lost.** | Two firings vs zero firings can both end with the same state. |
| C-7 | **Liveness obligations invisible.** | A failed-to-fire `wait` looks like benign idle. |
| C-8 | **No retry signal for Stage 2.** | End-state mismatch tells you "something is wrong" but not which IR feature; C5 self-correction (paper §6.9) has nothing to act on. |

Net: final-state-only is **timing-blind, ordering-blind, rearm-blind, frequency-blind, and liveness-blind**. It cannot serve as the verification mechanism for a reactive DSL.

---

## D. Why "state-less pointwise transition observation" was rejected **[reasoned; corresponds to §6.4's argument that per-op rules alone are insufficient]**

A second weakened scheme: observe each transition emitted by the JoI simulator and check it against per-op rules, **without keeping an FSM-level state context**.

Our method *does* check transition obligations — but **always with state context on the IR-FSM**. Stripping the state context reintroduces the following failures:

D-1. **Sequencing obligations lost.** `cycle{wait; call}` requires `call` to follow a fired `wait` in the same iteration. State-less: a free-standing `call` looks like a legal transition.

D-2. **Re-arming obligations lost.** After a cycle body completes, `wait` must re-arm. State-less observation cannot detect a missed re-arm.

D-3. **Register-dependency obligations lost.** `read $v1; delay; read $v2; if ($v2-$v1 > 5, ...)` requires `$v1` to be observed and stored *before* `$v2` is read. This dependency is non-local to any single transition.

D-4. **Reachability lost.** The legal successor of a transition depends on which `if` branch was taken — a state fact.

D-5. **Off-by-one / first-iteration obligations lost.** Intents that "skip the first cycle, then act each subsequent cycle" require iteration-index state.

D-6. **Idiom multiplicity re-enters.** The same external transition (`Switch.Off`) has different legal pre-states under `triggered`-flag vs `phase`-enum lowerings; only state-aware checking distinguishes them. We return to A-4.

D-7. **Coverage-completeness claim is forfeited.** Our defensible claim is *"every transition point of IR-FSM is covered ⇒ every IR-prescribed obligation is verified"* under A1–A6. "Every transition point" is meaningful only on an FSM. Without the FSM, there is no grammar over which to define coverage.

D-8. **Diagnostic granularity collapses.** Failures can no longer be tied to IR control-flow tree positions; C5 retry signals lose their IR-feature labels.

D-9. **Conflicts with the existing simulator-comparator design.** The trace comparator already uses ±100 ms grouping + dedup + within-group ordered comparison (`project_simulator_design_decisions.md` §4) — i.e., already a weak state-aware notion. Pure pointwise comparison breaks the dedup rule used to absorb selector fan-out.

---

## D'. The real adversary baseline: runtime verification / monitor synthesis **[added 2026-05-21 post-codex]**

§C (final-state) and §D (state-less pointwise) are strawmen — no serious reviewer or system advocates them. The credible weaker baseline a top-tier reviewer will press, and that we must explicitly differentiate from, is **runtime verification via monitor synthesis**: compile the spec into a finite-state monitor automaton, stream the implementation's external trace through it, report violation. Variants the reviewer may name: LTL₃ finite-trace monitors (Bauer-Leucker-Schallhart), behavioral types / session types, refinement on labeled transition systems, contract-based runtime checking. These are not rejected; some of them are structurally close to what we do.

**The differentiation must be in the spec's source and language, not in the verification engine.** What is genuinely new for top-tier:

| Dimension | Standard monitor synthesis | This work |
|---|---|---|
| Spec source | hand-authored LTL / regular property | LLM-extracted, user-confirmed reactive program (IR) |
| Spec language | temporal logic over atomic propositions | reactive DSL grammar (9-op IR) with reactive structure as typed fields |
| Spec audience | engineers writing formulas | end-users reading rendered NL of the IR |
| Coverage notion | trace satisfaction of one formula | transition-obligation coverage over an IR-derived FSM |
| Diagnostic granularity | "formula violated" | IR-path-grained obligation (e.g., `timeline[2].then[0]` missing call) |
| Closing the LLM-correction loop | not applicable | IR-feature-grained retry signal feeds Stage 2 lowering |

The contribution is not a new monitor-synthesis technique; it is the **integration of monitor-synthesis-flavored runtime checking into an NL→DSL lowering loop where (a) the spec is drawn from NL by an LLM and confirmed by a non-engineer user, and (b) verdicts return IR-feature-level retry signals that the lowerer can act on.** Paper wording should not say *"verified"* or *"model-checked"*; the defensible claim is *"conditional finite-trace monitor coverage under specified test generator and observation model."*

The §C / §D strawmen are kept in this note as part of a completeness sweep — readers asking *"what about final-state? what about pointwise?"* deserve answers — but §D' is the load-bearing differentiation.

---

## E. Where the method ends up

The negative results above leave a narrow viable corridor:

- *Not* spec-FSM ↔ impl-FSM bisimulation (A-4, A-5; no practical relation across idioms).
- *Not* full reachable-state enumeration (B; state explosion).
- *Not* final-state comparison (C; reactive programs don't terminate, and most obligations are not end-state-visible).
- *Not* state-less pointwise transition checking (D; loses sequencing, re-arming, register dependency, branch reachability, idiom-context).
- *Close to but not identical to* standard monitor synthesis (D'; same engine flavor, different spec source/language/audience/diagnostic).

The remaining defensible position: **transition obligations on a deterministically IR-derived FSM, verified by streaming an external JoI trace through that FSM, with the spec sourced from an LLM-extracted user-confirmed reactive program rather than a hand-authored formula**. This is what §6.4 specifies and what the paper claims as the contribution — borrowing the FSM's structural discipline while avoiding reachable-state enumeration and idiom-specific bisimulation, and adapting runtime-verification machinery to a setting (NL→DSL lowering with end-user-confirmable spec) where it has not been applied.

---

## F. One-paragraph summary (for paper §5 lead-in or response-letter use)

Standard FSM model checking does not apply to JoI for three operative reasons: (i) JoI has no formal small-step semantics, so `M` cannot be extracted; (ii) our spec is an LLM-extracted user-confirmed IR, not an LTL/CTL formula, so `φ` does not exist; (iii) the same NL intent admits multiple valid lowerings with different internal state shapes (`triggered`-flag, `prev/curr`, `phase` enum), so strict bisimulation between spec-FSM and impl-FSM is **not a practical verifier target across idioms** without either formal JoI semantics plus abstraction functions or a closed idiom catalog — both of which we set out to avoid. On top of these, continuous sensor values, week-long virtual time, persistent registers, and dynamic tag resolution make exhaustive exploration infeasible within an edge-runtime budget of ≤2 s. Two strawman weakenings — final-state comparison and state-less pointwise transition checking — are timing-/ordering-/rearm-/frequency-/liveness-blind and sequencing-/rearming-/dependency-/reachability-/idiom-blind respectively. The genuine adversary baseline is runtime verification via monitor synthesis (LTL₃, behavioral types, contract checking); we are structurally close to it, and differentiate by spec source (user-confirmed reactive program, not LTL formula), spec audience (end-users), coverage notion (transition obligations on IR-FSM), and diagnostic granularity (IR-path-grained retry signal closing the LLM-correction loop). The defensible position that remains is transition-obligation coverage on a deterministically IR-derived FSM, verified through external JoI trace — borrowing the FSM's structural discipline while sidestepping reachable-state enumeration, idiom-specific bisimulation, and the formula-shaped spec that monitor synthesis traditionally assumes.

---

## G. Recommended paper-side wording diffs

- **§6.1 (d) wording softened (2026-05-21).** "not even definable" → "not a practical verifier target across idioms without formal JoI semantics + abstraction functions or an idiom catalog." Updated in `paper_summary.md`.
- **§6.10 monitor-synthesis differentiation table (2026-05-21).** Added explicit row-by-row comparison (spec source / spec language / audience / coverage notion / diagnostic granularity / loop closure) — the load-bearing differentiation, not the strawman dismissals. Updated in `paper_summary.md`.
- **Claim discipline (2026-05-21).** Throughout the paper: never "verified" or "model-checked"; use *"covered under specified test generator and observation model"* or *"conditional finite-trace monitor coverage"*. Codex flagged this as the single highest soundness risk a reviewer will attack.
- **§6.1bis kept** as a completeness sweep for strawman alternatives, but §6.10's monitor-synthesis paragraph is the one that decides reviewer reception.
- **§5 forward reference**: "Section 6.1 sharpens the bisimulation argument; Section 6.1bis dismisses strawman weakenings; Section 6.10 differentiates from the credible runtime-verification baseline."
