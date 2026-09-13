# Items the author must complete by hand (E1 breadth)

Status 2026-09-13: the semantic audit of the eight depth encodings is done (`depth/AUTHOR_ADJUDICATION_2026-09-13.md`,
v2 run in `depth/RESULTS.md`). What remains is the manual corpus coding. Until it is done, no IN_SCOPE count,
R/B distribution or other corpus statistic goes into the paper, and no kappa or inter-rater agreement is computed.

Paper wording is limited to: "We manually screened candidate requirements using predefined eligibility and
duplicate criteria."

## Manual corpus coding — procedure

Work in `E1_CORPUS_WORKBOOK.xlsx` (sheet `Corpus_100`) or directly in `corpus_100.csv`; if you edit the workbook,
copy the final values back to the CSV, which is the source file. Definitions: `E1_CORPUS_PROTOCOL.md` §2 (unit,
duplicate rule), §4 (status values), §5 (coding); R1–R10 / B1–B5 in `../README.md`.

For each of the 100 rows:
1. Read `original_text` and open `source_url` at `source_locator` if the text alone is unclear.
2. `screen_status`: choose IN_SCOPE / AMBIGUOUS / OUT_OF_SCOPE / UNMATCHED yourself. The current value is a
   machine/GPT pass; do not copy it.
   - [ ] **E1-095 is still `AMBIGUOUS` from the preliminary pass, but its meaning is now fixed** (five hourly samples,
         mean at 15 h). Do not carry the preliminary label over.
3. `duplicate_family`: keep, change or clear. It currently marks similar groups, not verified duplicates
   (e.g. E1-039 sunset vs E1-040 19:00 are not duplicates under §2).
4. `rb_adjudicated`: enter your R/B elements (comma-separated). `rb_preliminary` is reference only; do not copy it.
   `rb_coder_1` / `rb_coder_2` stay empty.
5. Leave provenance columns as they are (audited; see `audit/`).

When all 100 rows are done, tell Claude; it will rebuild the workbook and compute the counts from your labels only.

- [ ] screen_status × 100
- [ ] duplicate_family reviewed
- [ ] rb_adjudicated × 100
