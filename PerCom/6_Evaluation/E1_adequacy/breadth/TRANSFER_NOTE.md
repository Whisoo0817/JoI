# Import note for Claude

Import this entire directory under `PerCom/6_Evaluation/E1_adequacy/breadth/` without overwriting existing Stage A files. The directory is a `preaudit` corpus package: it supplies the candidate corpus, screening log, workbook, frozen depth-case records, protocol, and handoff, but it is not a completed paper dataset.

The repository baseline is `paper @ 0788969e5d313415276a6cf89151aca8cce7c047`.

Before reporting paper results, verify every locator and the provenance type of all 12 seed cases against repository source records. Do not claim the current source-stratum counts, two independent human coders, or final R/B coding until those audits are performed. `rb_preliminary` is machine-assisted triage only.

Post-import decisions (2026-09-13): the provenance audit is in `audit/`; C15 moved to research, so the corpus is reported as source-diverse (25/26/24/25), not as fixed 25 per stratum; screening and R/B coding are done manually by one author, with no second coder or κ. See protocol §2 and §5. The author's screening is final (`audit/AUTHOR_SCREENING_2026-09-13.md`); the author's R/B coding is final as well (`audit/AUTHOR_RB_CODING_2026-09-13.md`).

The eight files in `frozen_cases/` are semantic decisions made before new IR encoding. Hash/commit them before attempting an encoding; do not alter them in response to an encoding result.
