# OVLA PerCom 2027 research workspace

This directory is an isolated workspace for planning and developing the new
OVLA paper. Files under `../docs/` are read-only source materials and must not
be modified by this workflow.

## Current entry point

- [`SESSION_HANDOFF_2026-09-10.md`](SESSION_HANDOFF_2026-09-10.md): **single entry point for a new session**. It records the professor-aligned scope, current evaluation numbering, discarded directions, and next decision.
- [`06_manuscript/problem_framing_codegen_validation_2026-09-11.md`](06_manuscript/problem_framing_codegen_validation_2026-09-11.md): **highest-priority problem framing**. Timeline is justified by the NL→JoI code-generation validation problem, not as a universal IoT IR; the confirmed specification includes its binding plan, with one distinct selector per `Service.Method` in the current scope.
- [`06_manuscript/paper_flow_ir_contract_2026-09-10.md`](06_manuscript/paper_flow_ir_contract_2026-09-10.md): **canonical paper flow and Timeline IR contract**.
- [`05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md`](05_experiment_plan/confirmed_ir_evaluation_2026-09-10.md): **canonical E1–E4 evaluation outline**.
- [`05_experiment_plan/e1_ir_adequacy_design_2026-09-10.md`](05_experiment_plan/e1_ir_adequacy_design_2026-09-10.md): **current E1 working design**.

All other files are supporting evidence or historical artifacts unless one of the five files above links to them. They do not override the current entry point.

## Supporting evidence

- [`02_literature/related_work_review_2026-09-09/README.md`](02_literature/related_work_review_2026-09-09/README.md): Related Work index and primary-source cards.
- [`02_literature/related_work_review_2026-09-09/automation_ir_execution_matrix.md`](02_literature/related_work_review_2026-09-09/automation_ir_execution_matrix.md): automation/TAP IR, FSM, execution route, and output comparison.
- [`06_manuscript/flow_discussion_2026-09-09.md`](06_manuscript/flow_discussion_2026-09-09.md): historical decision log. Use only for rationale; newer canonical files win on conflict.
- [`06_manuscript/motivation_intro_timeline_2026-09-09.md`](06_manuscript/motivation_intro_timeline_2026-09-09.md): draft prose written before the latest evaluation discussion; revise before manuscript use.

- [`00_skill_workflow_plan.md`](00_skill_workflow_plan.md): ordered use of the
  installed research and manuscript skills, preservation-first advisory rules,
  stage gates, and planned outputs.
- [`PHASE_0_4_ADVISOR_SUMMARY.md`](PHASE_0_4_ADVISOR_SUMMARY.md): completed
  Phase 0–4 decisions, preserved logic, PerCom grounding, formal design advice,
  experiment blocks, gate status, and inactive optional extensions.

## Completed advisor phases

- `01_intake/`: source, scope, legacy evidence, review objections, and logic map.
- `02_literature/`: six targeted literature strands plus official PerCom and
  seven-paper exemplar analysis.
- `03_claims/`: frozen C1–C5 contribution language, candidate claims, and
  anti-claims.
- `04_formal_design/`: minimum executable/deterministic semantics, observation,
  Explorer, proof obligations, and lowering boundary.
- `05_experiment_plan/`: contains the current 2026-09-10 outline plus older 2026-09-04 tracked plans and development results. The older files use different E1/E2 numbering and are non-canonical.
- `06_manuscript/`: manuscript-facing drafts and decisions synthesized from the
  preceding phases. The current title candidates and fixed Korean abstract are
  in [`06_manuscript/title_candidates_and_abstract.md`](06_manuscript/title_candidates_and_abstract.md).

## Source materials

- `../docs/OVLA_SenSys2027.pdf`
- `../docs/review.txt`
- `../docs/New_OVLA_Timeline_IR_Design_and_Verification.md`

## Workspace rule

All newly generated research notes, literature records, experiment plans,
audits, paper plans, drafts, and PaperSpine artifacts stay under this directory.
The session handoff, the 2026-09-11 problem-framing decision, and the two canonical 2026-09-10 documents control the current paper flow.
Earlier source and planning documents remain evidence and history; they may not silently replace the current decisions.
Paper planning must also distinguish official PerCom requirements from patterns
observed across a documented sample of prior PerCom main-conference papers.
