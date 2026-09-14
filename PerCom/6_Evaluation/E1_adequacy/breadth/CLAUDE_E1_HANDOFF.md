# Claude server handoff — finish E1 without contaminating the experiment

## Baseline and non-negotiable decisions

- Work from `Whisoo0817/JoI`, branch `paper`; baseline head is `0788969e5d313415276a6cf89151aca8cce7c047`. Verify it before importing; if it differs, record the newer head and diff.
- Preserve the existing 12 Stage A cases and their reported results: external requirements 12/12, input histories exact 41/41, after human semantic audit.
- Treat those 12 as a completed seed cohort. Do not invent a statistical reason for the number 12; it was a Stage A work unit.
- The breadth corpus is 100 items. The planned depth subset is 20: existing 12 plus 8 new cases after ambiguity resolution and coding.
- E1 adequacy is human semantic audit plus reference execution. Explorer is not the E1 oracle and its accept/reject result cannot change the adequacy numerator.
- Call expected traces `reference behavior` or `preregistered reference behavior`, not absolute ground truth.
- Do not edit Timeline IR, Explorer, the prompt, catalog, or runner after observing an encoding/execution outcome. Any separately motivated later change starts a new version and rerun.

## Inputs from GPT/web work

Use these files together:

- `corpus_100.csv`: 100 retained source-backed requirements from four source types (after the 2026-09-13 audit and C15 reclassification: official 25 / research 26 / elicited 24 / community 25; no fixed per-stratum quota is claimed).
- `screening_log_150.csv`: 100 retained plus 50 not-retained candidates.
- `E1_CORPUS_PROTOCOL.md`: sampling, coding, freeze, outcome, and stop rules.
- `E1_CORPUS_WORKBOOK.xlsx`: human-review view.
- `frozen_cases/`: eight IR-free depth-case records. Each fixes its interpretation, binding plan, bounded input history, and expected ACTION trace before encoding.

The `rb_preliminary` field is triage, not a paper result. `rb_coder_1` and `rb_coder_2` are intentionally blank. `screen_status` and `duplicate_family` hold the author's final screening (2026-09-13, `audit/AUTHOR_SCREENING_2026-09-13.md`); `rb_adjudicated` holds the author's final R/B codes for the 92 `IN_SCOPE` rows and `N/A` for the other 8 (`audit/AUTHOR_RB_CODING_2026-09-13.md`). Community `original_text` values are normalized requirements linked to opening posts and must not be called verbatim quotations.

## Work order

1. **Import without changing results.** Add the corpus artifacts to a new E1 breadth subdirectory. Do not overwrite `cases.py`, `irs.py`, probe files, or existing run JSON.
2. **Complete provenance pass.** Check every URL/locator. Add a short source excerpt only where licensing/quotation policy permits; otherwise retain the exact locator and normalization. Correct errors with a change log.
3. **Manual coding (single author, decision 2026-09-13).** The author assigns inclusion status and R/B labels. No second coder, agreement statistic, Cohen's κ, or adjudication is used or claimed. Keep ambiguous/out-of-scope/unmatched rows visible. `rb_preliminary` is triage, never a result.
4. **Resolve ambiguities one case at a time.** Ask whisoo a plain-language behavior question, record the answer, then move to the next case. Do not bundle all semantic choices into one approval request.
5. **Freeze each new depth case.** Write source, interpretation, assumptions, device/binding plan, histories, and expected ACTION traces in an IR-free case file. Hash or commit it before encoding.
6. **Attempt current Timeline IR.** Use the unchanged current language and frontend first. Record complete/partial/impossible/held plus exact syntax or semantic obstacle.
7. **Run the reference executor.** Compare action type, arguments, order, and time. Record exact match and tolerance match separately. Cron-anchor erasure, if still necessary, must be labeled runner accommodation.
8. **Separate backend from language.** For every partial/impossible IR case, implement the same fixed behavior with ordinary JoI variables and control flow. Record whether a missing catalog/history/aggregate service is the actual blocker.
9. **Record Explorer separately.** Run it only for auxiliary verifier-coverage evidence or the later E2 benchmark. Never count its verdict as E1 semantic correctness.
10. **Update documentation only where needed.** First verify whether the target documents still contain stale “B3/B4 untested” claims. Do not make a no-op edit when, as at the baseline head, those claims are already absent. Preserve the separate fact that P1–P3 expressed and executed successfully while Explorer alone rejected them due to joint guards or missing explicit input domains.

## First two new boundary probes

### E1-092 — independent parallel shutdown flows

External source: Home Assistant Community thread 955561. The intended stress is two live flows with independent progress and failure isolation: Alexa announcements/settings and physical house shutdown actions. Do not reduce this to a sequential list merely because the final action multiset matches.

**Confirmed interpretation (2026-09-13):** Preserve only the source-stated behavior. The Alexa and house-shutdown flows start together; an Alexa communication failure must not stop or delay the house-shutdown flow. Do not introduce arbitrary per-branch deadlines, because the source specifies none. Fix a simple action timing for the reference trace, then try the current single-flow Timeline IR unchanged. If exact independence is impossible, try ordinary JoI concurrency/control flow and record the distinction.

**Current author adjudication (2026-09-13, `depth/AUTHOR_ADJUDICATION_2026-09-13.md`):** the single-Timeline result (0/1) is kept; the flows are deployed as two independent Timeline IRs, each with its own JoI block. v2: 1/1 exact — `complete via multi-Timeline decomposition` (protocol §6, `depth/RESULTS.md`).

### E1-095 — internal post-start accumulation

External source: Home Assistant Community thread 654561. The source asks for daily average pH and chlorine readings over 10:00–15:00. A platform-provided statistics sensor would be backend delegation and does not test internal accumulation.

**Confirmed interpretation (2026-09-13):** Treat this as a discrete arithmetic mean. Read both sensors at 10:00, 11:00, 12:00, 13:00, and 14:00; report the mean of those five readings at 15:00. The reference history contains all five readings, so missing-sample recovery is not part of this case. Initialize the automation's internal sum and count at the beginning of each daily window. The primary version must read multiple post-start sensor values and require `sum = sum + value` (and a count if needed) inside the automation. Try current Timeline IR unchanged, then ordinary JoI mutable variables/control flow. Record a service-provided-average variant separately as backend delegation.

**Current author adjudication (2026-09-13):** internal sum/count is not required. Five snapshot variables and the arithmetic mean satisfy the interpretation — 1/1 exact, `complete for fixed-cardinality aggregation`. General dynamic aggregation is described as backend history/statistics delegation.

### E1-086 — cancelable sequential sprinklers

External source: Home Assistant Community thread 878961. The opening post supplies a sequential two-zone irrigation program and asks to stop the entire program when its input boolean turns off. Its accepted revised version explicitly handles the stop trigger by turning both zones off.

**Confirmed interpretation (2026-09-13):** Start zone 1 for 10 minutes, wait 30 seconds, then start zone 2 for 10 minutes. If the input boolean turns off at any point, immediately turn off both zones and cancel all remaining waits and actions. Do not include Home Assistant restart behavior in this case.

### E1-099 — manual light with motion extension

External source: Home Assistant Community thread 729908. The request says that manually switched-on lights must stay on at least five minutes and that each motion event increases the on time by two minutes, while no motion must be detected for two minutes before switch-off.

**Confirmed interpretation (2026-09-13):** A manual switch-on creates an initial switch-off deadline five minutes later. Each motion event while the light is on extends the current deadline by two minutes. At the deadline, turn the light off only if no motion was detected during the preceding two minutes. This is deadline extension, not timer restart.

**Current author adjudication (2026-09-13):** when motion and the deadline fall on the same instant, motion is handled first and extends the deadline by two minutes. v2 adds that history — 2/2 exact, `complete`.

### E1-028 — rolling-window feeder limit

External source: AutoTap User Study 1 public data, Result sheet, Excel row 26 (the earlier "participant P24, statement S2" label was a pandas row number, not a participant ID; `audit/PROVENANCE_AUDIT.md` item 3): “My smart pet feeder should never allow to dispense more than 2 bowls of food per every 4 hours.”

**Confirmed interpretation (2026-09-13):** Use a rolling four-hour window, not fixed clock-aligned four-hour bins. On a dispense request, dispense only when fewer than two bowls have been dispensed in the preceding four hours. Reject an over-limit request silently: emit no dispense ACTION and no notification.

### E1-034 — oven overrun confirmation

External source: AutoTap User Study 1 public data, Result sheet, Excel row 60 (the earlier "participant P58, statement S9" label was a pandas row number, not a participant ID; `audit/PROVENANCE_AUDIT.md` item 3): “My smart oven should never be on for than 4 hours, maximum without alerting if more time is needed, and shutting off if not responded to.”

**Confirmed interpretation (2026-09-13):** When the oven has been on for four hours, send a confirmation alert. Model an affirmative user response as a `ConfirmContinue` input. If no response arrives by one minute after the alert, turn the oven off. If confirmation arrives within that minute, leave the oven on for the bounded reference history; no further maximum duration is inferred.

**Current author adjudication (2026-09-13):** repeating policy. On confirmation (`ContinueConfirmed`, an external platform input event), keep the oven on, reset the four-hour timer and repeat. v2 runs "no response → off" and "confirmed → restart → second alert, no response → off" — 3/3 exact, `complete`.

### E1-072 — home and away lighting

External source: Google Home's official “Home and away lighting” scripted-automation example. It specifies two distinct rules: on transition to HOME, turn on two named lights only between sunset and sunrise; on transition to AWAY, turn off three named lights only between sunrise and sunset.

**Confirmed interpretation (source-specified):** Preserve the two rules and their distinct temporal guards exactly. Treat sunset and sunrise as supplied clock events in the reference history; do not infer any behavior for home arrival during daytime or departure during nighttime.

**Current author adjudication (2026-09-13):** the IR does not hard-code 06:00/18:00; it reads the platform's sunrise/sunset or daylight input (v2: `Sun.IsDaylight`). 06:00/18:00 are fixture input values of one run — 2/2 exact, `complete`.

### E1-062 — bidirectional light synchronization

External source: Google Home's official “Synchronize two lights” scripted-automation example. It spells out four guarded rules: each change of either light is copied to the other light only when their states differ.

**Confirmed interpretation (source-specified):** Model four event-driven, guarded synchronization rules. A command that makes the target match must not create an additional observable synchronization command, because the target guard is then false; this prevents feedback loops.

## Eight additions to the depth subset (final selection)

In priority order: `E1-092`, `E1-095`, `E1-086`, `E1-099`, `E1-028`, `E1-034`, `E1-072`, `E1-062`.

This selection is final (2026-09-13; protocol §6); it was not filtered by encoding success. Replace an item only for a documented reason such as unresolved ambiguity, confirmed duplicate semantics, or source invalidity. Do not replace a failed encoding with an easier case.

## Expected repository outputs

- breadth corpus and screening log under E1;
- a coding table holding the author's manual labels (no agreement calculation);
- eight new IR-free frozen case records plus hashes/commits;
- corresponding encoding attempts and immutable attempt history;
- reference-runner results with exact and tolerance matches;
- JoI fallback attempts for every partial/impossible case;
- an E1 result table whose denominator labels distinguish all 100 breadth items, in-scope items, and 20 depth items;
- updated handoff and limitations text;
- a clear E1 stop decision, followed by E2 rather than further unplanned E1 expansion.
