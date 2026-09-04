# Strand: LLM-generated IoT automation

**Goal:** identify systems that translate natural language into IoT rules or programs and record what they use as correctness evidence.

## Scope

1. Trigger-action rule generation: ChatIoT and related systems.
2. Rich AIoT program synthesis: AutoIOT and GPIoT.
3. Evaluation oracle: compilation, execution tests, model judges, user studies, or no code-level behavioral oracle.

## Per-entry deliverable

Each entry has `card.md`, `source.md`, `meta.json`; the strand has `INDEX.md` and a BibTeX file.

## Seed material

- `../../../docs/OVLA_SenSys2027.pdf` §2.
- `../../../docs/New_OVLA_Timeline_IR_Design_and_Verification.md` §2, §3, §6.

## Acceptance criteria

- At least 3 primary systems, including trigger-action and general AIoT code generation.
- Each card states the artifact generated and the exact verification reference.

## Out of scope

- General code generation without an IoT execution context.
- Treating generation accuracy as evidence of IR–code behavioral equivalence.

