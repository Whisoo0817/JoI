# OVLA PerCom 2027: skill-assisted research workflow

## 1. Objective and boundary

The workflow develops the new OVLA paper around behavioral verification of
LLM-generated reactive-temporal IoT automation code. It covers paper logic,
formalization, experiment planning, evidence auditing, manuscript structure,
drafting, and review.

The following source files are inputs only and remain unchanged:

- `../docs/OVLA_SenSys2027.pdf`
- `../docs/review.txt`
- `../docs/New_OVLA_Timeline_IR_Design_and_Verification.md`

All generated artifacts must be written below `skill_result/`. In particular,
PaperSpine must be launched with `skill_result/` as its working directory so
that its `paper_rewriting_output/` directory remains isolated here.

### Preservation-first advisory charter

`../docs/New_OVLA_Timeline_IR_Design_and_Verification.md` is the controlling
source for the new paper's problem statement, guarantee boundary, logic, and
flow. The installed skills are advisors to that design; they are not authorized
to replace it with a new paper direction.

Every skill-assisted recommendation must follow these rules:

1. Reconstruct the current `new_ovla` statement before suggesting anything.
2. Prefer clarification, connective reasoning, evidence, and scope control over
   new components, claims, or sections.
3. Do not add a new contribution, operator, system component, experiment family,
   or manuscript storyline merely because a skill template contains one.
4. Classify each suggestion as one of:
   - `clarification`: explains the existing logic more precisely;
   - `evidence-needed`: identifies proof, literature, or experiment needed by an
     existing claim;
   - `optional-extension`: goes beyond the current document and remains inactive
     until the user explicitly approves it.
5. Record the exact `new_ovla` section affected, why the suggestion is needed,
   and whether it changes scope. Silent restructuring is prohibited.
6. Preserve the paper flow in `new_ovla` Section 15 unless the user explicitly
   approves a separate flow revision proposal.
7. Keep all advice in `skill_result/`; never edit the controlling source file
   while providing advice.
8. Ground presentation and evidence advice in the official PerCom scope and in
   documented patterns from prior PerCom main-conference papers, while treating
   venue fit as a constraint on the existing flow rather than permission to
   replace it.

The default task for every helper skill is therefore: strengthen the reasoning
already present, identify missing support, and recommend the smallest experiment
set needed to substantiate the current claims.

### PerCom venue-grounding rule

Before finalizing the paper logic, experiment priorities, figure plan, or section
allocation, inspect both of the following:

1. **Official requirements:** the current PerCom call for papers, scope, topics,
   track definitions, review or artifact criteria when published, submission
   format, and page limits. These must be sourced from official IEEE/PerCom
   pages and labeled as explicit venue requirements.
2. **Observed paper patterns:** a documented sample of recent PerCom
   main-conference papers, prioritizing papers closest to IoT systems,
   pervasive computing, reactive systems, verification, edge intelligence, and
   LLM-enabled systems. Analyze how they frame the problem, state the systems
   contribution, connect method to deployment context, organize evaluation,
   select baselines, report limitations, and use figures or motivating examples.

Do not infer a venue rule from one or two papers. Record the sample years,
tracks, selection criteria, and paper paths or identifiers. Keep official rules
separate from recurring tendencies inferred from the paper sample.

The venue analysis may advise:

- which part of the existing `new_ovla` motivation should receive more space;
- where a logical transition needs a clearer systems or pervasive-computing
  connection;
- which already-planned experiment requires stronger realism, baselines, or
  reporting;
- which figure or section order best communicates the existing contribution;
- which claims should be narrowed to match the available evidence.

It may not automatically introduce a new contribution, system component,
application domain, or experiment family. Any such suggestion is an inactive
`optional-extension` requiring explicit user approval.

## 2. Installed skills and their assigned roles

| Order | Skill or plugin capability | Assigned role in this project |
|---:|---|---|
| 0 | `paper-spine` | Check the existing flow for continuity, contribution visibility, reviewer objections, and unsupported transitions; do not redesign the storyline by default |
| 1 | `opencite:opencite` | Search and retrieve literature specifically needed to support or delimit existing `new_ovla` statements |
| 2 | `manuscript:lit-review` | Synthesize targeted evidence and closest-work differences without generating a new research direction |
| 3 | `research-experiment-plan` | Recommend the minimum decisive experiments required by existing claims; additional experiment families remain optional until approved |
| 4 | `research-results-auditor` | Audit completed results for protocol integrity, fair baselines, confounds, uncertainty, provenance, and claim support |
| 5 | `research-paper-plan` | Bind evidence to the existing flow and identify unsupported links; do not add or broaden claims automatically |
| 6 | `manuscript:manuscript-writing` | Draft or revise sections while preserving the approved logic map and claim boundaries |
| 7 | `manuscript:humanizer` | Remove AI-style prose patterns without changing claims or technical meaning |
| 8 | `manuscript:paper-review` | Conduct a fresh-context peer-review pass over the complete manuscript |
| 9 | `manuscript:manuscript-formatting` | Apply the final PerCom template, bibliography, page limit, and submission checks |

`new_ovla` remains the authority. `paper-spine` only manages advice artifacts
and later drafting gates around that authority; it does not replace the existing
flow. The experiment planner, results auditor, and paper planner must all trace
their outputs back to existing statements in `new_ovla`.

## 3. Execution sequence

### Phase 0 — Isolated project intake

**Primary capability:** `paper-spine` intake concepts, without drafting.

Create a source inventory and freeze the current transition from the old paper
to the new plan. Record the prior paper's claims and evidence, the three review
records, the new formal-verification direction, and all declared non-goals.

Planned outputs:

- `01_intake/source_inventory.md`
- `01_intake/legacy_claims_and_evidence.md`
- `01_intake/reviewer_objection_register.md`
- `01_intake/new_direction_scope.md`
- `01_intake/new_ovla_logic_map.md`
- `01_intake/advice_change_register.md`

Gate G0:

- Every statement is traceable to one of the three source files.
- The old results are labeled as predecessor evidence, not automatically as
  evidence for the redesigned system.
- The new direction's exclusions are recorded: NL-to-IR intent accuracy,
  usability/readability, physical-device correctness, and post-deployment
  localization or repair.
- The logic map reproduces Sections 0, 1, 15, 16, and 19 of `new_ovla` without
  adding or reordering a contribution.
- Every later suggestion can be traced to the advice change register.

### Phase 1 — Literature and novelty grounding

**Skills:** `opencite:opencite` followed by `manuscript:lit-review`.

Use OpenCite to answer targeted support questions derived from `new_ovla`.
Use the literature-review skill in express mode by default. Escalate to a full
corpus protocol only when an existing novelty or related-work statement cannot
be assessed with a focused search and the user approves the larger collection.

Targeted support strands already implied by the current flow:

1. LLM-generated IoT automation and natural-language programming.
2. Trigger-action and reactive-temporal IoT languages and semantics.
3. Conformance testing, trace equivalence, model checking, and runtime
   verification for reactive systems.
4. Executable specifications, deterministic operational semantics, and
   compositionality.
5. Reachability exploration, state-space reduction, and bounded guarantees.
6. User-confirmed specifications and separation of authoring from
   implementation verification.

Planned outputs:

- `02_literature/_briefs/strand-*.md`
- `02_literature/collection/<strand>/<paper>/card.md`
- `02_literature/collection/<strand>/<paper>/meta.json`
- `02_literature/collection/<strand>/<strand>.bib`
- `02_literature/synthesis/ontology.md`
- `02_literature/synthesis/sota_gap_map.md`
- `02_literature/synthesis/claim_support_map.md`
- `02_literature/references.bib`
- `02_literature/percom/official_scope_and_requirements.md`
- `02_literature/percom/exemplar_selection_protocol.md`
- `02_literature/percom/exemplar_paper_cards/`
- `02_literature/percom/percom_paper_pattern_map.md`
- `02_literature/percom/new_ovla_venue_alignment.md`

Gate G1:

- Novelty statements link to primary paper cards and verified identifiers.
- Closest systems are compared by reference specification, execution model,
  explored behavior space, equivalence criterion, and guarantee boundary.
- Unsupported novelty language remains marked as unresolved.
- PerCom 2027 venue rules are recorded from the official call/template when
  they are available and checked.
- Official PerCom requirements are distinguished from tendencies inferred from
  the sampled papers.
- The PerCom paper sample has documented years, tracks, inclusion criteria, and
  traceable sources; isolated examples are not presented as conference-wide
  norms.
- `new_ovla_venue_alignment.md` evaluates the existing seven-step flow without
  proposing a replacement flow.
- Literature findings may qualify or delimit the existing novelty statement,
  but a newly discovered research direction is logged as `optional-extension`
  rather than inserted into the paper flow.

### Phase 2 — Contribution and claim freeze

**Primary capability:** contribution-first discipline from `paper-spine`.

Translate the five expected contributions already stated in `new_ovla` Section
16 into bounded claim records. Do not create additional contributions during
this phase:

- **C1 — Behavioral verification:** verify LLM-generated reactive-temporal IoT
  code over reachable observable behavior rather than source form.
- **C2 — Executable reference specification:** use a user-confirmed Timeline IR
  to make event, state, and time semantics explicit and generate reference
  traces.
- **C3 — Determinism-enabling semantics:** define and establish operational
  semantics and determinism-preserving composition for the expected trace.
- **C4 — Reachable behavior exploration:** explore modeled event, state, and
  time histories and compare normalized IR/code traces.
- **C5 — Evaluation:** evaluate the already-declared axes of expressiveness,
  semantics conformance, equivalence checking, and Explorer scalability.

These records split existing contribution language into evidence-bearing units;
they must not broaden its scope. A useful subclaim may be attached to one of C1
through C5, but it does not become a new contribution without user approval.

Anti-claims to freeze at the same time:

- The system does not prove that natural language matches latent user intent.
- It does not claim that arbitrary users understand the IR.
- It does not verify all real-world executions or physical device outcomes.
- A bounded Explorer is not described as unbounded formal equivalence.
- Backend independence is not asserted from a single backend implementation.

Planned outputs:

- `03_claims/confirmed_motivation.md`
- `03_claims/confirmed_contribution.md`
- `03_claims/candidate_claim_register.md`
- `03_claims/anti_claims.md`
- `03_claims/claim_decision_log.md`

Gate G2 requires explicit user confirmation that the claim records preserve the
controlling motivation, contribution order, and guarantee boundary in
`new_ovla`. Any proposed addition remains in the change register as an inactive
`optional-extension`.

### Phase 3 — Formal design freeze

**Input:** the new design document, G1 literature synthesis, and G2 claims.

This phase resolves only the open semantics already listed in `new_ovla`
Section 18 before implementation or confirmatory experiment planning:

- operator and type system;
- time model and interval boundaries;
- event batching and timer/event tie rules;
- state snapshot and commit behavior;
- parallel effect representation and conflict policy;
- reentry and derived-event policy;
- zero-time-cycle termination rules;
- observable trace vocabulary;
- environment model and exploration bounds;
- backend adapter contract;
- deterministic compiler versus LLM-assisted lowering decision.

The goal is to make the current flow executable and provable, not to expand the
language. For each decision, first identify the minimum choice required by an
existing claim. Richer operators or policies are recorded separately as
optional extensions.

Formal artifacts:

- `04_formal_design/language_scope.md`
- `04_formal_design/grammar.md`
- `04_formal_design/well_formedness.md`
- `04_formal_design/operational_semantics.md`
- `04_formal_design/observation_model.md`
- `04_formal_design/explorer_model.md`
- `04_formal_design/proof_obligations.md`
- `04_formal_design/proof_sketch.md`
- `04_formal_design/lowering_decision.md`

Gate G3:

- Every valid configuration/input pair has a defined transition or stutter.
- Simultaneous events, conflicts, timer ties, missing values, and reentry have
  explicit semantics.
- The proof obligations cover expression totality, primitive determinism,
  merge invariance, constructor preservation, progress, preservation, and
  reaction termination.
- The empirical claim does not depend on an unresolved semantic choice.

### Phase 4 — Decisive experiment plan

**Skill:** `research-experiment-plan`.

Initialize a tracked experiment pack under `05_experiment_plan/`. Freeze at
most two primary empirical claims and separate exploratory pilot work from
confirmatory runs. Derive the experiment set from `new_ovla` Sections 12.2,
12.3, 12.4, and 15.7. The skill advises which concrete methods, metrics,
baselines, and controls are needed inside those axes; it does not add a new
evaluation storyline by default.

Each recommendation must state: the existing claim it supports, the reviewer
question it answers, the minimum protocol, decisive metric, necessary control,
expected failure interpretation, paper artifact, and whether it is core or
optional.

Experiment advice must also compare the planned evidence shape with the
documented PerCom exemplar pattern map. This comparison may strengthen the
realism, baseline choice, workload design, metrics, deployment context, or
presentation of E1–E4. It cannot create a fifth core block solely to imitate a
venue pattern. If the PerCom sample suggests evidence outside E1–E4, record it
as an `optional-extension` with the exact existing claim it would support.

Candidate experiment blocks to evaluate during planning:

| Block | Question already present in `new_ovla` | Default status |
|---|---|---|
| E1 Interpreter conformance | Does the implementation conform to the defined Timeline IR semantics and determinism properties? | Core |
| E2 Expressive adequacy | Does the IR cover the explicitly declared target behavior space without semantic loss? | Core |
| E3 IR–code equivalence verification | Does the checker identify behavioral agreement and divergence under the same modeled inputs and observation rules? | Core |
| E4 Explorer scalability | What finite model and bounds can be explored in time and memory as state, timer, event, and rule complexity grows? | Core |

E1 should include property-based AST/state/event generation, permutation tests,
merge algebra tests, boundary suites, small-model exhaustive successor checks,
and differential testing against an independently implemented evaluator where
available.

The following are not default experiment blocks. They may be recommended only
when an existing claim cannot otherwise be supported, and they remain inactive
until the user approves them:

- comparison against the old boundary-event method or another verifier;
- deterministic compiler versus LLM-assisted lowering comparison;
- a second backend or DSL portability study;
- a physical deployment study;
- a usability or human-subject study, which the current scope excludes.

When one is proposed, the advice record must explain which existing claim needs
it, whether it changes the contribution or scope, and what happens to the claim
if the experiment is not performed.

Planned canonical outputs from the skill:

- `05_experiment_plan/experiment-plan.md`
- `05_experiment_plan/experiment-tracker.md`
- `05_experiment_plan/claim-map.json`
- `05_experiment_plan/run-blocks.json`
- `05_experiment_plan/decision-gates.md`
- `05_experiment_plan/execution-bridge.md`

Gate G4:

- Claims are falsifiable and connected reciprocally to experiment blocks.
- The non-vacuity preflight shows at least one plausible discriminating case.
- Must-run blocks precede optional paper-enhancement runs.
- Failed, skipped, null, retried, and timed-out cases remain in outcome
  accounting.
- No confirmatory case, metric, or threshold is selected after observing the
  desired outcome.
- Every core block maps to one of the four evaluation axes already declared in
  `new_ovla`.
- Optional blocks cannot enter `run-blocks.json` as active work without explicit
  user approval in `advice_change_register.md`.

### Phase 5 — Implementation and experiment execution

No paper-writing skill interprets this phase as completed merely because a
script exits successfully. Execute only the blocks authorized by G4, preserving
configuration, code revision, environment, seeds, logs, failures, and raw
outputs.

Planned outputs:

- `06_experiments/<block-id>/protocol.md`
- `06_experiments/<block-id>/config/`
- `06_experiments/<block-id>/raw/`
- `06_experiments/<block-id>/logs/`
- `06_experiments/<block-id>/derived/`
- `06_experiments/<block-id>/manifest.json`

Gate G5a requires complete provenance and outcome accounting before result
interpretation.

### Phase 6 — Results audit

**Skill:** `research-results-auditor`.

Audit each claim separately. Reconstruct the intended claim, exact population,
task, split, condition, metric, run selection, failures, and artifacts before
reading the headline number. Audit protocol integrity, metric validity,
baseline fairness, outcome accounting, inferential support, confounds,
provenance, snapshot continuity, and independence.

Planned outputs:

- `07_results_audit/results-audit.json`
- `07_results_audit/results-audit.md`
- `07_results_audit/corrective_actions.md`

Gate G5b:

- Every empirical claim has a bounded audit verdict.
- Negative and inconclusive runs are retained.
- Confirmatory language is allowed only for results attaining the required
  assurance level.
- Unsupported claims are narrowed, converted to limitations, or removed before
  paper planning.

### Phase 7 — Claims-to-paper architecture

**Skill:** `research-paper-plan`.

Run only after G5b. The paper planner receives the literature corpus, formal
artifacts, claim map, all result audits, and predecessor reviewer objections.
The JSON binding is the authority for what the manuscript may assert, while
`new_ovla` remains the authority for the intended logic and flow. The planner
may narrow unsupported language or flag a missing link; it may not silently
replace the storyline.

The planner must also consume `percom_paper_pattern_map.md` and
`new_ovla_venue_alignment.md`. Venue patterns guide emphasis, section budget,
figure placement, and evidence presentation only after claim support is
established. A common PerCom pattern is not itself evidence for an OVLA claim.

Planned canonical outputs:

- `08_paper_plan/paper-plan.md`
- `08_paper_plan/claims-evidence-matrix.md`
- `08_paper_plan/claim-evidence-bindings.json`
- `08_paper_plan/figure-plan.md`
- `08_paper_plan/citation-plan.md`
- `08_paper_plan/results_validation.md`

Frozen manuscript flow from `new_ovla` Section 15, to be strengthened without
reordering:

1. Reactive-temporal implementation correctness cannot be judged from source
   similarity.
2. Behavior comparison requires an executable reference for each timed input.
3. User confirmation fixes a Timeline IR as the specification boundary.
4. The IR semantics provide one observable reference trace per fixed input.
5. Composition rules preserve that property for complex automations.
6. Explorer enumerates reachable histories within the declared finite model
   and bounds.
7. IR and generated code are compared under identical inputs and observation
   rules.

Formal and empirical evidence are attached to these seven steps through the
claim-evidence bindings. If a step lacks support, the planner records the gap and
suggests the minimum repair; it does not introduce a substitute storyline.

Gate G6:

- Every asserted claim has a proof artifact, audited empirical result, or
  verified citation appropriate to its evidence mode.
- Figures and citation needs link reciprocally to stable claim IDs.
- Old OVLA results are used only where scope and implementation compatibility
  are established.
- Reviewer objections appear either as resolved evidence, an explicit design
  choice, or a limitation.
- A flow-alignment check confirms that every planned section serves one of the
  seven existing steps and that no unapproved contribution has appeared.
- A venue-alignment check identifies which choices come from official PerCom
  requirements and which come from observed exemplar tendencies.

### Phase 8 — PaperSpine assembly and section drafting

**Skills:** `paper-spine`, then `manuscript:manuscript-writing` for focused
section work.

Launch PaperSpine from `skill_result/` in `build_from_materials` mode and use
`01_intake/` through `08_paper_plan/` as local-first materials. Its output must
remain at `skill_result/paper_rewriting_output/`. PaperSpine's own research and
citation stages should index the existing corpus rather than silently replacing
the verified literature artifacts.

PaperSpine is used here as a flow and consistency advisor around the approved
logic map. Any alternative motivation, contribution order, or section spine it
suggests must be written to a separate proposal file and cannot enter the draft
without explicit user approval.

Before prose drafting, produce:

- section blueprints;
- writing rationale matrix;
- contribution-to-results validation map;
- reviewer objection register;
- figure and table sequence;
- page-budget allocation based on the verified PerCom template.

Draft Methods and Results in parallel structure. Draft the Abstract only after
the claim bindings and results language are stable.

Gate G7 is PaperSpine's integrity audit plus checks that every Results unit
validates a contribution promise and no prose exceeds the claim-evidence
binding.

### Phase 9 — Prose cleanup, independent review, and revision loop

**Skills:** `manuscript:humanizer` followed by `manuscript:paper-review`.

Run the humanizer only after technical content and claim language are stable.
Then request a fresh-context paper review that receives the manuscript, target
venue, and manuscript type, but not the authoring rationale. A panel review is
used only if explicitly requested.

Store outputs under:

- `09_review/humanizer_report.md`
- `09_review/review_round_<n>.md`
- `09_review/revision_matrix_<n>.md`
- `09_review/reviewer_objection_status.md`

Any review finding involving missing evidence routes back to Phase 4–6. A logic
or structure finding routes back to Phase 7. A prose-only finding routes back to
Phase 8–9.

Review feedback is advisory. Each item must be classified as strengthening the
existing flow, requiring evidence, or proposing an optional scope change before
revision begins.

### Phase 10 — Formatting and final audit

**Skills:** `manuscript:manuscript-formatting` and PaperSpine final audit.

Apply the official PerCom 2027 format only after technical review converges.
Compile citations from verified BibTeX records, check figure readability and
cross-references, and generate the requested PDF/Word outputs inside
`paper_rewriting_output/final_paper/`.

Before final assembly, recheck the current official PerCom instructions rather
than relying on the earlier venue snapshot, since calls, templates, and page
limits may change.

Final gate G8:

- contribution, results-validation, reviewer, citation, integrity, LaTeX, and
  output-artifact checks pass;
- the manuscript's guarantee uses the exact modeled environment and exploration
  bounds;
- all unresolved limitations are stated;
- no source or generated file exists outside `skill_result/`, except the
  unchanged read-only inputs under `docs/`.
- a final diff of the logic map against `new_ovla` shows no unapproved change to
  the problem, insight, contribution order, guarantee boundary, or evaluation
  axes.

## 4. Stage dependency map

```text
Source intake
  -> OpenCite corpus
  -> literature synthesis / novelty map
  -> user-confirmed motivation and contribution
  -> formal semantics freeze
  -> experiment plan and non-vacuity gate
  -> implementation and runs
  -> results audit
  -> claim-evidence paper plan
  -> PaperSpine assembly and manuscript writing
  -> humanizer
  -> fresh-context paper review
  -> revision loops
  -> PerCom formatting and final audit
```

The critical evidence dependency is:

```text
claim-map.json
  -> run-blocks.json
  -> raw experiment artifacts
  -> results-audit.json
  -> claim-evidence-bindings.json
  -> manuscript assertions
```

## 5. Recommended next execution unit

Begin with Phase 0 only. It is bounded, uses the three existing source files,
and creates the source inventory, exact `new_ovla` logic map, objection
register, and advice change register. This establishes the baseline that every
later skill must preserve. Do not start manuscript drafting or confirmatory
experiment design before G1–G3 are complete.
