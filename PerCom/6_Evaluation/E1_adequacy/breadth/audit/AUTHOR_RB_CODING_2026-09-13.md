# Author R/B coding of the corpus (whisoo, 2026-09-13)

whisoo reviewed all 100 source texts and their behavior elements by hand, ten at a time. One author; no second
coder, kappa or inter-rater agreement.

Applied by `apply_rb_coding.py`; every changed value is in `changes_2026-09-13_rb_coding.csv` (92 changes).
`rb_preliminary` is kept unchanged for provenance; `rb_coder_1` / `rb_coder_2` stay empty.

## Scope

- R/B codes only for the 92 `IN_SCOPE` rows; the distribution is computed over 92.
- The 6 `AMBIGUOUS` (E1-015, 017, 018, 027, 083, 091) and 2 `OUT_OF_SCOPE` (E1-036, 037) rows: `N/A`.

## Sources of the final codes

| Rows | Count | Source |
|---|---:|---|
| Seeds E1-001…E1-012 | 12 | Stage A codes in `../../README.md` §5 |
| Author exceptions (below) | 17 | exact author values |
| Other `IN_SCOPE` rows | 63 | `rb_preliminary`, reviewed and approved by the author |
| AMBIGUOUS / OUT_OF_SCOPE | 8 | `N/A` |

## Author exceptions

| Row | Code | Reason |
|---|---|---|
| E1-020 | R1, R6 | a later start request is blocked by a state guard; not two appliances running in parallel, so not B2 |
| E1-031 | R1, R6 | branches on the day's use count provided by the backend; the IR does not count, so not R8 |
| E1-042 | R1 | presence sync; no time condition |
| E1-050 | R9 | fixed clock time |
| E1-056 | R1 | first-arrival event |
| E1-058 | R1, R9 | after-dark guard, not a delay |
| E1-069 | R1 | vacancy state change |
| E1-071 | R1 | manual voice command |
| E1-072 | R1, R9 | after-dark guard, not a delay |
| E1-073 | R1 | one notification |
| E1-082 | R1, R3 | door open > 5 min, then closed |
| E1-088 | R1, R9 | sun-based time guard, not a duration |
| E1-093 | R1, R2, B2 | immediate doorbell reaction, delays inside each flow, independent flows |
| E1-095 | R5, R8, R9 | five fixed snapshots flow into the later mean; fixed count; clock schedule. `L-ACCUM` removed |
| E1-097 | R1, R6, B2 | immediate doorbell reaction, presence/zone branch, enabled actions run independently |
| E1-099 | R3, R10 | two-minute no-motion condition; deadline vs motion race. Nothing is cancelled or restarted, so not B1 |
| E1-100 | R1 | `unlocked` is a guard combined with the trigger, not a separate branch |

## Final counts (denominator 92 `IN_SCOPE` rows; a row can carry several codes)

| Code | Rows | | Code | Rows |
|---|---:|---|---|---:|
| R1 | 65 | | B1 | 6 |
| R2 | 14 | | B2 | 5 |
| R3 | 13 | | B3 | 2 |
| R4 | 3 | | B4 | 0 |
| R5 | 8 | | B5 | 1 |
| R6 | 23 | | | |
| R7 | 5 | | | |
| R8 | 3 | | | |
| R9 | 28 | | | |
| R10 | 2 | | | |

Rows with at least one B code: 13 of 92. Screening stays 92 / 6 / 2.

Checks: no `IN_SCOPE` row has a blank or `N/A` code; every token is one of R1–R10 / B1–B5; no `L-ACCUM` in
`rb_adjudicated` (it remains in `rb_preliminary` of E1-095 for provenance).
