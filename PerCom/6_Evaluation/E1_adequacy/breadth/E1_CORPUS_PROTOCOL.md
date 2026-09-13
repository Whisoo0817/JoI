# E1 breadth corpus protocol — frozen before Timeline IR encoding

Date: 2026-09-13  
Repository baseline: `Whisoo0817/JoI`, branch `paper`, commit `0788969e5d313415276a6cf89151aca8cce7c047`  
Corpus version: `e1-corpus-v0.1-preaudit`

## 1. What this corpus supports

The breadth corpus asks whether 100 externally sourced automation requirements fall inside the intended scope of Timeline IR and which reactive-temporal elements they contain. It is a source-diverse, purposive corpus. It does **not** estimate the prevalence of automation patterns in the population of smart-home users.

The depth subset asks whether a selected requirement can be encoded without changing its fixed meaning and whether a reference execution produces the preregistered ACTION trace. E1's semantic adequacy decision is based on human audit plus reference execution. Explorer is recorded only as an auxiliary support result; an Explorer rejection cannot change an E1 adequacy result.

## 2. Unit, source types, and stopping rule

One corpus item is one externally stated automation behavior with one source locator. Closely related clauses that jointly define one automation remain one item. Two statements are duplicates only when trigger, temporal condition, guard, actions, and re-entry/reset semantics are equivalent after device-name substitution.

The corpus stops at 100 retained items drawn from four source types. Collection aimed at 25 per type; the 2026-09-13 provenance audit moved C15 from elicited to research (a participant remark quoted in a paper, with no released-data locator), and no item was added or removed to rebalance. Final counts:

| Stratum | Definition | Seed | New | Total |
|---|---|---:|---:|---:|
| Official | Platform documentation, blueprint, or example | 1 | 24 | 25 |
| Research | Published task, stimulus, reported example, or paper-quoted participant remark | 8 | 18 | 26 |
| Elicited | Participant-authored statement directly checkable in released study data | 1 | 23 | 24 |
| Community | Naturalistic public request or community-published example | 2 | 23 | 25 |
| **Total** |  | **12** | **88** | **100** |

Drawing from four source types keeps one convenient dataset from dominating. The paper reports a source-diverse corpus with these actual counts; it does not claim a fixed quota per source type, and the counts are not a claim about how common each source type is in practice.

## 3. Existing Stage A cases

The completed 12 cases remain unchanged as the seed cohort. Their 12/12 adequacy and 41/41 exact-history results remain a completed depth result.

The reason exactly 12 were done is historical: they were the first Stage A work unit assembled to combine R1–R10 and selected B elements. There was no statistical sample-size calculation, random draw, saturation analysis, or claim that they were representative. The corpus records this fact verbatim rather than constructing a retrospective sampling rationale.

**Provenance audit (2026-09-13).** Every seed's provenance type was reconciled against the repository source record and every locator was checked on the server. The final provenance evidence is `audit/PROVENANCE_AUDIT.md`, `audit/changes_2026-09-13.csv` and `audit/changes_2026-09-13_decisions.csv`. The E1-099 text change there is a provenance correction (the opening post states both off conditions); it does not alter the frozen behavioral interpretation.

## 4. Collection and screening

Candidate status is one of:

- `IN_SCOPE`: the source determines a reactive-temporal automation behavior once explicit researcher assumptions are fixed.
- `AMBIGUOUS`: a behavior-defining choice is unresolved; the item is retained and no IR is written until the user resolves it.
- `OUT_OF_SCOPE`: the source is real but the behavior is outside the smart-home automation unit used by E1.
- `UNMATCHED`: the behavior is clear but depends on a platform/catalog facility absent from the current JoI setup. This is separated from an IR-language failure.
- `DUPLICATE`: semantically equivalent to an earlier item under the duplicate rule. Duplicates remain in the screening log and do not enter the retained 100.

The imported machine-assisted first pass (91 `IN_SCOPE`, 6 `AMBIGUOUS`, 2 `OUT_OF_SCOPE`, 1 `UNMATCHED`) was replaced by the author's manual screening on 2026-09-13: 92 `IN_SCOPE`, 6 `AMBIGUOUS`, 2 `OUT_OF_SCOPE`, 0 `UNMATCHED`, and no retained duplicate (`audit/AUTHOR_SCREENING_2026-09-13.md`). Similar-topic groups are kept in `topic_family`, not in `duplicate_family`. Difficult cases remain visible in the 100; the paper should report both the full 100 and the in-scope denominator once the author's labels are final. The screening log contains 150 candidates: all 100 retained items plus 50 released AutoTap statements beyond the fixed elicited-source cap.

For every retained item, preserve the URL, document/table/thread locator, access date, and text handling. `VERBATIM_*` identifies text copied from a task/data record. `OFFICIAL_DESCRIPTION_OR_STRUCTURED_EXTRACTION` identifies behavior reconstructed from structured official examples. Community items currently contain a concise researcher normalization linked to the opening post; they must not be described as verbatim quotations.

## 5. Coding procedure

Use the definitions already fixed in E1 `README.md`: R1–R10 and B1–B5. `L-ACCUM` is a provisional label for the newly tested language-boundary hypothesis, internal accumulation. The `rb_preliminary` field is machine-assisted triage only.

One author performed the screening and the R/B coding by hand (decisions 2026-09-13; `audit/AUTHOR_SCREENING_2026-09-13.md`, `audit/AUTHOR_RB_CODING_2026-09-13.md`):

1. The author manually screened all 100 rows (`screen_status`), using the eligibility definitions in §4 and the duplicate rule in §2.
2. Final R/B codes are assigned only to the 92 `IN_SCOPE` rows, and the R/B distribution is computed over those 92. The 6 `AMBIGUOUS` and 2 `OUT_OF_SCOPE` rows have `rb_adjudicated = N/A` and are excluded from the distribution.
3. The author's codes are in `rb_adjudicated` (column name kept for file compatibility; no adjudication between coders takes place). `rb_coder_1`/`rb_coder_2` stay empty. `L-ACCUM` is not a final code.
4. `rb_preliminary` is kept unchanged for provenance. It is never reported or used in a statistic; where the author approved a preliminary value after review, the approved value is what counts.
5. Unresolved and excluded cases stay in the public artifact.

No second coder, Cohen's κ, or inter-rater reliability is used or claimed. The paper's wording is limited to: “We manually screened candidate requirements using predefined eligibility and duplicate criteria.” Corpus distributions are computed only from the author's values: screening status over all 100 rows, R/B over the 92 `IN_SCOPE` rows.

This follows the useful procedural ideas in AutoTap (classify elicited requirements and retain ambiguous/out-of-scope cases) and Dwyer et al. (preserve unmatched cases and distinguish authored from external examples). It does not present either prior corpus as held-out data, because those data helped shape the systems being studied.

## 6. Depth subset

The target is 20 cases: the completed 12 seeds plus 8 new maximum-variation candidates. The current proposal is:

| Rank | ID | Main reason |
|---:|---|---|
| 1 | E1-092 | True independent parallel flows and failure isolation |
| 2 | E1-095 | Post-start observations requiring sum/average state |
| 3 | E1-086 | Mid-run cancellation of a sequential automation |
| 4 | E1-099 | Minimum-on deadline extended by later events |
| 5 | E1-028 | Rate/count constraint; separates history service from IR |
| 6 | E1-034 | Alert, response timeout, and fallback shutdown |
| 7 | E1-072 | Separate arrival and vacancy flows in an official example |
| 8 | E1-062 | Bidirectional synchronization in an official example |

This list is provisional until ambiguity resolution and the author's manual coding. Selection is for semantic variation and boundary pressure, not success probability.

### Resolved semantic decisions

- **E1-092 (2026-09-13):** The two groups start together. A failed or blocked Alexa group must not stop or delay the house-shutdown group. The reference behavior adds no deadline that is absent from the source request.
- **E1-095 (2026-09-13):** Read pH and chlorine at 10:00, 11:00, 12:00, 13:00, and 14:00; at 15:00, report each five-reading arithmetic mean. The reference history has no missing readings. Initialize the internal sum and count at the start of every daily window; do not use a platform history/statistics service in the primary version.
- **E1-086 (2026-09-13):** Run sprinkler zone 1 for 10 minutes, wait 30 seconds, then run zone 2 for 10 minutes. If the controlling input boolean turns off during the run, immediately turn both zones off and cancel the remaining program. Restart behavior is excluded.
- **E1-099 (2026-09-13):** A manual switch-on starts with a five-minute off deadline. Every motion event while the light is on adds two minutes to the current deadline. At the deadline, turn the light off only if there was no motion in the preceding two minutes.
- **E1-028 (2026-09-13):** Treat “every 4 hours” as a rolling four-hour window. A dispense request succeeds only when fewer than two bowls were dispensed in the preceding window; an over-limit request emits no action or notification.
- **E1-034 (2026-09-13):** At four hours of continuous oven-on time, send a confirmation alert. If `ConfirmContinue` does not arrive within one minute, turn the oven off; if it arrives, leave the oven on for the bounded reference history.
- **E1-072 (source-specified):** On HOME, turn on two lights only between sunset and sunrise. On AWAY, turn off three lights only between sunrise and sunset. No behavior is inferred for the complementary time ranges.
- **E1-062 (source-specified):** Synchronize two lights with four event-triggered, state-difference-guarded rules. A matching target state must not cause a feedback command.

## 7. Freeze rule for each new depth case

Before looking at an encoding result, commit or hash a case record containing:

- source text or normalized requirement, exact locator, and text form;
- one explicit interpretation;
- every researcher-added assumption, visibly labeled;
- initial device state and catalog/service assumptions;
- reset, re-entry, cancellation, concurrency, and termination semantics;
- 2–4 input histories, including at least one boundary history;
- expected ACTION tuples `(time, Service.Method, args, device)` and tolerance.

Only after this record is frozen may Claude write Timeline IR. Do not change Timeline IR, Explorer, catalog, prompt, or reference-runner semantics in response to the result. Corrections to a faulty reference trace must be logged with before/after versions and a source-based explanation.

## 8. Outcome taxonomy

For each depth case report these fields separately:

1. Timeline-language result: complete / partial / impossible / held for ambiguity.
2. Frontend grammar result.
3. Reference-runner support and exact trace match.
4. Current service-catalog sufficiency.
5. Hand-written JoI fallback result when Timeline IR is partial or impossible.
6. Explorer support, as an auxiliary verifier-coverage observation only.

If Timeline IR fails but ordinary JoI variables/control flow implement the fixed behavior, record an IR expressiveness limitation. If both fail because the required history or aggregate is unavailable, record a backend/catalog limitation. If a ready-made average/history service makes the case work, record backend delegation rather than claiming that the IR performs internal accumulation.

## 9. Stop condition for E1 and transition to E2

E1 is ready to close when all of the following hold:

- all 100 rows have checked provenance and the author's final manual screening status and R/B labels;
- ambiguous rows remain visible and are either resolved or explicitly held;
- the completed 12 seed results are preserved without reinterpreting their selection;
- eight new depth cases have frozen case records and reference traces;
- all 20 depth cases have human semantic audit and reference-runner outcomes;
- failures have been separated into ambiguity, catalog/backend, Timeline language, frontend, and runner categories;
- parallel-flow and internal-accumulation probes have an attempted current-IR encoding and JoI fallback result;
- Explorer outcomes are not used in the E1 adequacy numerator or denominator;
- the Evaluation handoff no longer says B3/B4 are untested and points to the P1–P3 results.

After those gates, further corpus expansion has diminishing value for E1 and should not delay E2, which evaluates Explorer accuracy/coverage on a separately defined benchmark.

## 10. Evidence files

- `corpus_100.csv`: retained corpus, the author's screening status and R/B labels (`rb_adjudicated`), and the preliminary triage fields.
- `screening_log_150.csv`: retained and not-retained candidate decisions.
- `E1_CORPUS_WORKBOOK.xlsx`: reviewer-facing workbook with summaries and filters.
- `CLAUDE_E1_HANDOFF.md`: exact execution and repository-update sequence for the server agent.
