# Author semantic audit — adjudication record (whisoo, 2026-09-13)

This record adds the author's decisions after reviewing the v1 encodings. It does not replace anything:
`../frozen_cases/*.md`, `depth_cases.py`, `fixture.py`, `depth_attempts.py` (v1) and `runs/e1_depth.json` (v1 run)
are kept unchanged. Changed interpretations and added histories live in `depth_cases_v2.py` / `fixture_v2.py`
(hashed before v2 encoding), v2 encodings in `depth_attempts_v2.py`, the v2 run in `runs/e1_depth_v2.json`.

E1 adequacy = this author audit + reference execution. Explorer results are auxiliary and never enter the
complete/partial/impossible counts.

## Per-case decisions

| Case | Decision | Effect on the record | Final label if the v2 run matches |
|---|---|---|---|
| E1-092 | The flows share no state, join or order dependency, so the requirement decomposes into two independent automations. v1 (no parallel branch inside one Timeline) is kept. v2: two Timeline IRs (A: Alexa tasks/news/alarm settings; B: lights off, locks, alarm set), each lowered to its own JoI block and deployed separately. No `IsAvailable` precondition. Same trigger and fault history; merged trace compared with the frozen trace. | new v2 encoding, same history | `complete via multi-Timeline decomposition` |
| E1-095 | Fixed interpretation: one sample at 10, 11, 12, 13, 14 h, arithmetic mean at 15 h, all samples present. Five snapshot variables and `(v1+…+v5)/5` fully satisfy it; the absence of `sum += value` is not a reason for partial. The lack of a general mutable accumulator / input-dependent aggregation is a separate language boundary; general averages, counts and history are described as backend-service delegation (typed result read by the IR), not as a Timeline capability or a measured gain. | label change only; v1 encoding kept | `complete for fixed-cardinality aggregation` |
| E1-099 | When motion and the current deadline fall on the same instant, motion is handled first: the deadline is extended by 2 min and the automation continues; reaching the extended deadline later without motion turns the light off. v1's deadline-first behaviour at that instant is kept as audit evidence. | new v2 encoding + added same-instant history | `complete` |
| E1-028 | Rolling 4-hour window; two most recent successful dispense times in two slots is equivalent for the fixed bound 2; over-limit requests emit nothing. No claim for run-time N or unbounded history; no new probe. | label only | `complete for the fixed bound of two` |
| E1-034 | Repeating policy: after 4 h on, alert; no `ContinueConfirmed` within 1 min → oven off; confirmation → keep the oven on, restart the 4-hour timer, repeat. v1 (ends after one confirmation) does not fully satisfy it and is kept. `ContinueConfirmed` is an external input event delivered by the platform when the user presses the app/notification button (the E1 stub input `Notify.ConfirmContinue`). | new v2 encoding + added history (confirm → restart → no response → off) | `complete` |
| E1-072 | Do not hard-code 06:00/18:00. The IR reads a platform-provided daylight input (sunrise/sunset computation is the platform's responsibility). In this reference fixture sunrise = 06:00 and sunset = 18:00 are input values of one run, not the general meaning. | new v2 encoding + environment input | `complete` |
| E1-062 | Current interpretation and previous-state feedback guard approved; syncing lights that start in different states is not required. | none | `complete` |
| E1-086 | Current interpretation approved: zone 1 10 min, 30 s gap, zone 2 10 min; master switch off cancels immediately and turns zones off. | none | `complete` |

## Transcription and comparison rules

T1, T2, T5 and T7 in `depth_cases.py` are approved as written:
T1 initial state first, frozen `t+0` injected at 1 s (artifact convention only, not described in the paper);
T2 momentary events as 1 s pulses, not applied to sustained states;
T5 same-timestamp independent actions compared as a multiset, with kind, target, arguments and count exact;
T7 an external action failure stops only the independent automation that issued it; no global stop, error value,
error-handling API or `IsAvailable` guard. E1-092's multi-Timeline deployment uses this meaning.

## Corpus decisions recorded with this audit

- C15 stays `research`; source counts stay official 25 / research 26 / elicited 24 / community 25.
- C05/C07 provenance uses the opening-post dates 2023-01-17 and 2024-10-18 UTC (already in `source_locator`);
  access dates stay separate. Not needed in the paper body or appendix.
- `screen_status`, `rb_adjudicated`, `duplicate_family` remain for the author's manual coding; no kappa.

## Reporting scope

- Not E1 results or limitations: the extractor-prompt grammar observation on the eight new encodings (E1 is not an
  extractor-coverage experiment); the reference runner's missing `Clock.Second` (it did not affect a Timeline result).
  Both are kept as internal engineering notes (`ENGINEERING_NOTES.md`).
- Not claimed from E1: general mutable accumulators, dynamic N, unbounded history, or "finite-state because the
  program is fixed". No new finite-state probe.
