# Author manual screening of the 100-item corpus (whisoo, 2026-09-13)

One author screened all 100 rows by hand. No second coder, kappa or inter-rater agreement is used or claimed.
Paper wording: “We manually screened candidate requirements using predefined eligibility and duplicate criteria.”

Applied by `apply_author_screening.py`; every changed value is in `changes_2026-09-13_author_screening.csv`
(55 changes). The machine/GPT preliminary values were not carried over.

## 1. Final screen status

| Status | Count | Rows |
|---|---:|---|
| IN_SCOPE | 92 | all others |
| AMBIGUOUS | 6 | E1-015, E1-017, E1-018, E1-027, E1-083, E1-091 |
| OUT_OF_SCOPE | 2 | E1-036, E1-037 |
| UNMATCHED | 0 | — |

Changed from the preliminary pass: E1-031 UNMATCHED → IN_SCOPE, E1-095 AMBIGUOUS → IN_SCOPE, E1-027 IN_SCOPE → AMBIGUOUS.

Author interpretations recorded in `notes`:
- **E1-031.** A backend history/count service provides the day's toothbrush use count; the automation reads it as a
  guard. This is separate from, and not evidence for, internal accumulation in the IR.
- **E1-095.** Read pH and chlorine at 10:00, 11:00, 12:00, 13:00 and 14:00 (five samples); report each mean at 15:00.
- **E1-020.** Minimal operational interpretation: if one appliance is already running, a later start request is not
  started. No notification action is added.

Ambiguity reasons recorded in `screen_reason`:
- **E1-027.** The clock meaning of “between 7 and 12 pm” is unclear. The original text is not changed or normalized.
- **E1-091.** The content of the joint condition is not given.

## 2. Duplicates

No retained duplicate. `duplicate_family` is cleared for all rows. The former similar-topic groups (E1-039/040
`lights/sun`, E1-067/068 `motion-light`, E1-087/090 `timed-on`, E1-092/093/094/097 `parallel-flow`) are kept in the
new column `topic_family`; it is not a duplicate mark.

## 3. Author behavior statements

Class-column corrections applied as stated (`trigger_class`, `temporal_class`, `action_cardinality`,
`control_class`):

| Row | Statement | Applied |
|---|---|---|
| E1-042 | presence sync; no time condition | trigger event/state |
| E1-050 | lights on at a fixed time | trigger clock/calendar |
| E1-056 | first-arrival event; not a time condition | trigger event/state |
| E1-058, E1-072 | `after dark` is a time/environment guard, not a delay | trigger + clock/calendar; temporal immediate |
| E1-069 | whole-home vacancy state change; not a time condition | trigger event/state |
| E1-071 | manual voice command, then several actions | trigger manual |
| E1-073, E1-082, E1-100 | one notification | action_cardinality single |
| E1-088 | sunset−2 h to sunset is a sun-based time guard, not a duration | temporal immediate |
| E1-093 | no time condition | trigger event/state |
| E1-097 | doorbell event + presence/zone guard; not clock/manual | trigger event/state; control + guard/branch |
| E1-099 | manual start, ≥5 min, each motion adds 2 min, off only if no motion in the 2 min before the deadline | text already contains the last guard (corpus, screening log, frozen case); no change |

`rb_adjudicated` filled only where the statement fixes the R/B set under README §1 (8 rows):

| Row | rb_adjudicated | Reason |
|---|---|---|
| E1-042 | R1 | presence change → light at once |
| E1-050 | R9 | fixed clock time |
| E1-056 | R1 | arrival event |
| E1-058 | R1, R9 | TV-on event under an after-dark guard |
| E1-069 | R1 | vacancy change |
| E1-071 | R1 | manual command, actions at once |
| E1-072 | R1, R9 | arrival/vacancy events under an after-dark guard |
| E1-088 | R1, R9 | weather event under a sun-based time guard |

## 4. Provenance (unchanged by this step)

- C15 (E1-008) is `research`. Source types: official 25 / research 26 / elicited 24 / community 25.
- C05 (E1-004) and C07 (E1-005) locators carry the first-post dates 2023-01-17 and 2024-10-18 (UTC); `accessed_date`
  stays separate. Not needed in the paper.

## 5. Distribution from the author's status

| Source type | IN_SCOPE | AMBIGUOUS | OUT_OF_SCOPE | Total |
|---|---:|---:|---:|---:|
| Official | 25 | 0 | 0 | 25 |
| Research | 24 | 0 | 2 | 26 |
| Elicited | 20 | 4 | 0 | 24 |
| Community | 23 | 2 | 0 | 25 |
| **Total** | **92** | **6** | **2** | **100** |

No R/B distribution is computed: `rb_adjudicated` is filled for 8 of 100 rows.

## 6. Open author decisions (R/B)

Resolved on 2026-09-13 by the author's R/B coding: `AUTHOR_RB_CODING_2026-09-13.md`. The list below is kept as it was.

1. **The other 92 rows have no author R/B statement.** `rb_adjudicated` stays blank for them and `rb_preliminary` is
   not copied. Needed: the author's R/B set per row, or an explicit decision about which preliminary values are
   accepted. The 12 seeds already have Stage A codes in `../../README.md` §5; `rb_preliminary` equals them.
2. Rows in the author's list whose R/B set is not fixed by the statement:
   - **E1-099:** which codes (preliminary `R3`; the deadline extension and the motion-vs-deadline order could also
     be read as B1 or R10).
   - **E1-073, E1-082, E1-100:** only the action count was stated.
   - **E1-093:** whether R2 (delays inside the scripts) and B2 apply once R9 is removed.
   - **E1-097:** whether simultaneous actions count as B2, and whether the guard adds a code.
   - **E1-020, E1-031, E1-095:** codes under the new interpretations (preliminary `R9, B2` / `R1, R8` /
     `R5, R9, L-ACCUM` no longer fit as they stand).
