# C15_002 technical retry: cron start-time correction

The frozen extension pair has `t_start_ms: null` for cron
`0 */2 * * 6,7`, causing a harness error. The original
`pairs/build_388_pairs.py:start_of` returns `(None, cron)` whenever a cron
minute or hour field is not a numeric literal. This differs from its prose
description, which says other IRs start at Monday noon. C15_002 is a valid
weekly schedule, and its IR and generated JoI contain the same cron.

The correction extends the start-time rule for weekly cron expressions
whose day-of-month and month fields are both `*`: select the earliest
matching minute in the canonical seven-day week, with Monday 00:00 at
0 ms. Cron weekday numbers are 1=Monday through 6=Saturday and 0 or 7=Sunday.
Fields support `*`, comma lists, inclusive ranges, and positive steps.
The original daily numeric-minute/hour rule remains unchanged.

For `0 */2 * * 6,7`, the first matching minute is Saturday 00:00,
`t_start_ms = 432000000`. The retry changes only this model start-time
parameter. Pair identity, IR, binding, inventory, generated JoI, selected
cohort, and history-generation rules are preserved. The same candidate is
retried; no outcome-based replacement occurs. No evaluation engine is run
by this preparation script.

All 12 frozen new LLM pairs were inspected for null start times. Only
C15_002 is affected. C01_006 and every other pair remain untouched.

Original and supplementary histories are regenerated with the original
300-pulse cap, 200-start cap, 1500-additional-pulse cap, seeds, horizon rule,
and original-history reproduction assertion. The frozen input files and
runs are preserved. `audit.json` records the exact pair difference and
history comparison; `ARTIFACT_HASHES.json` records retry inputs.
