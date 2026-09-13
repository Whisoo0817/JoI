# Items the author must complete by hand (E1 breadth + depth)

Nothing below may be filled by Claude or taken from `rb_preliminary`. Until these are done, no corpus distribution and
no final E1 adequacy number is reported.

## 1. Manual screening — `corpus_100.csv` / `E1_CORPUS_WORKBOOK.xlsx`
- [ ] `screen_status` for all 100 rows (the imported values are a machine-assisted pass).
      Note E1-095 is still `AMBIGUOUS` although its interpretation was fixed on 2026-09-13.
- [ ] Confirm the duplicate rule on the `duplicate_family` groups; E1-039/E1-040 are similar, not duplicates.

## 2. Manual R/B coding
- [ ] R1–R10 / B1–B5 (and `L-ACCUM` if kept) for all 100 rows in `rb_adjudicated`. `rb_coder_1`/`rb_coder_2` stay empty.

## 3. Semantic audit of the eight new depth encodings (column B, as in Stage A)
For each case, check the IR and JoI in `depth/depth_attempts.py` against `frozen_cases/*.md`:
- [ ] E1-092 — IR interleaving is a fair single-flow attempt; the JoI two-block deployment counts as the fallback.
- [ ] E1-095 — "partial" (trace matches only by unrolling a literal five samples) is the right label.
- [ ] E1-086 — cancel closes both valves; the `break` ends the single run (restart excluded).
- [ ] E1-099 — the branch "deadline reached but motion within 2 min" is unreachable (every motion extends the
      deadline by 2 min) and ends without Off; acceptable?
- [ ] E1-028 — two parity-indexed timestamp slots equal "fewer than two dispenses in (t−4h, t)".
- [ ] E1-034 — one-shot (a second 4-hour period is outside the frozen record).
- [ ] E1-072 — sunrise/sunset as fixed 06:00/18:00 clock guards.
- [ ] E1-062 — four guarded branches; resulting-state events 100 ms after the command.

## 4. Transcription rules to confirm (`depth/depth_cases.py`)
- [ ] T1 (frozen t+0 = rel 1 s), T2 (1 s pulses), T5 (same-instant commands unordered), T7 (failure delivered 1 s
      after issue terminates the issuing instance before its next step).

## 5. Left from the provenance audit
- [ ] `cases.py` source names date C05/C07 as 2023-01-18 / 2024-10-20; opening posts are 2023-01-17 / 2024-10-18 UTC.
      `cases.py` is hashed Stage A data, so only decide how the paper cites them.
