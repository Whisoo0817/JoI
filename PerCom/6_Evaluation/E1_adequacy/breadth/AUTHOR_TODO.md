# Items the author must complete by hand (E1 breadth)

Status 2026-09-13:
- The semantic audit of the eight depth encodings is done (`depth/AUTHOR_ADJUDICATION_2026-09-13.md`, v2 run in
  `depth/RESULTS.md`).
- The manual screening is done (`audit/AUTHOR_SCREENING_2026-09-13.md`): 92 IN_SCOPE, 6 AMBIGUOUS, 2 OUT_OF_SCOPE,
  0 UNMATCHED, no retained duplicate.

What remains is R/B coding. No R/B distribution goes into the paper until it is done, and no kappa or inter-rater
agreement is computed.

Paper wording is limited to: "We manually screened candidate requirements using predefined eligibility and
duplicate criteria."

## R/B coding — open

`rb_adjudicated` is filled for 8 rows (E1-042, 050, 056, 058, 069, 071, 072, 088), taken from your behavior statements.
The open questions are in `audit/AUTHOR_SCREENING_2026-09-13.md` §6:

- [ ] R/B for the other 92 rows: code them, or state which `rb_preliminary` values you accept. For the 12 seeds,
      `rb_preliminary` equals the Stage A codes in `../README.md` §5.
- [ ] Codes for E1-099, E1-073, E1-082, E1-100, E1-093, E1-097, E1-020, E1-031, E1-095.

Definitions: R1–R10 / B1–B5 in `../README.md` §1. Enter labels in `corpus_100.csv` (source file) or tell Claude. When
the codes are complete, Claude rebuilds the workbook and computes the R/B counts from your labels only.
