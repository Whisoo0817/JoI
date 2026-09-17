# Official remaining22: agent interpretation and reference execution

This batch evaluates E1-054 through E1-077 except previously completed E1-062 and E1-072. E1-061 and E1-071 are included. Interpretation and encoding provenance is ASTRA agent work under the current delegated task, **not author adjudication or author approval**. No original20, prior depth, runtime, global catalog or corpus files were changed.

The source URLs in `cases.py` were opened live on 2026-09-17 before freezing. Google and the zone blueprint were downloaded afterward to `source_snapshots/`, with retrieval times and hashes. Direct download of the HA trigger page returned HTTP 403 (recorded in the manifest); the web tool successfully read that page during source inspection. Thus the source access date is an actual fresh access, not a claim that the corpus's earlier audit was performed again by its author. The Google page currently reports an update of 2026-09-16. These dynamic sources are not immutable 2026-09-13 source versions.

## Freeze and execution order

1. Read original20 `cases.py`, `irs.py`, depth cases/attempts v1 and v2, runner, and `AUTHOR_ADJUDICATION_2026-09-13.md`.
2. Write source-grounded interpretations and expected traces with no encoding import. Initial freeze: 22 cases / 88 histories at 14:44:14 UTC. Retained as `cases_v1_frozen.py`, `frozen_cases_v1.json`, `FREEZE_MANIFEST_v1.json`.
3. Before any encoding, add two sensitivity histories requested in agent review: a motion before 09:00 followed by one exactly at 09:00 (075); motion immediately before and exactly at the twenty-hour cooldown expiry (074). Revise weekday metadata from an integer convention to a string convention. Final pre-encoding freeze: 22 cases / 90 histories at 14:45:05 UTC (`FREEZE_MANIFEST.json` records `encoding_existed_at_freeze=false`). The final transcription's `MON` is shorthand; inspection shows the actual runtime value is `monday`, which the encoding compares. This documentary shorthand does not affect expected traces.
4. Write `attempts.py`, deriving policies directly from frozen specs. No expected-trace iteration or simulator output is used to generate IR. All timing, previous-state detection, cooldown, deadline reset and pulse sequencing are encoded in standard Timeline operators.
5. Execute all 22 cases using unchanged shared `../run_batch.py`; all 90 histories match exactly, all frontend/catalog checks accepted, all automations compiled. No encoding repair was needed. Explorer was not run and is not part of this adequacy evidence.

Reproduce from repository root:

```sh
/home/gnltnwjstk/temp/bin/python PerCom/08_Evaluation/E1_adequacy/breadth/remaining72/run_batch.py batch_official
```

`runs/results.json` contains complete expected and actual action traces, marked IR lowering, bindings, checks and file hashes. `runs_stdout_v1.txt` preserves the first full execution's log. `RESULTS.csv` and `RESULTS.md` summarize the run. `AUDIT.json` verifies final frozen hashes, cohort membership and result counts.

## Interpretation qualifications

- **All cases:** transition semantics suppress initial-level activation. Reliable complete fixture observations, fixed configured devices, discrete sample grids and lack of physical action feedback are favorable modeling choices. Tests are finite evidence, not universal equivalence or device/network reliability results. Same-time independent actions are compared as an unordered multiset under prior T5; exact matching here did not require the one-second tolerance.
- **055/061:** clock actions use local logical clock transitions, without cron erasure. 061 sunset is the platform daylight transition, as in the previously approved 072 convention. Two-day coverage checks continued scheduling and a changed sunset. Startup/catch-up and timezone/DST policy are outside these histories.
- **056/057/069:** household Home is the native platform observation in the source, not a fixture computation over person events. Additional arrivals while Home stays true do not constitute household-presence transitions.
- **063:** source's finite red/off/blue/off/red sequence and five-second intervals are retained. Source does not specify busy retrigger policy; the frozen assumption ignores retriggers while a sequence runs. The label preserves this qualification.
- **066/070:** source's native `LightEffectPulse(5min)` does not define its waveform. We choose 150 one-second On/Off pairs and a final Off state; both phases and finite repetition live in the controller, with no timed fixture effect. Source-equivalent native pulsing is **not** established. Single-flight suppression is also assumed. Results are qualified complete for this operational waveform only.
- **067/068:** continuous absence resets on renewed presence. Renewal at the deadline wins. 068's abbreviated prose sounds like a fixed delay after occupancy, while source YAML requires five minutes of UNOCCUPIED. The executable source is selected and the competing prose interpretation is explicitly not tested; the label says source-YAML absence interpretation.
- **071:** the platform delivers the source-normalized `Movie Night` query as a raw string, cleared between utterances. Recognition and free-text/case normalization are outside the controller; selected washer is a fixed configured device.
- **074:** source time condition gives 05:00 and 12:00; the freeze chooses [05:00,12:00). Twenty-hour suppression begins after a successful opening, with inclusive expiry. An alternative applies suppression to raw triggers before the time guard; that interpretation is not established. An outside-morning event is deliberately tested and does not consume cooldown. The label is qualified complete for success-based suppression.
- **075:** three source motion starters and two notification destinations are retained. [09:00,18:00) is an explicit endpoint choice. Independent simultaneous device events each notify both members. One early original negative history has zero duration, but the added pre-09:00 event distinguishes the time guard from startup suppression. The Saturday history crosses several full weekdays and remains silent until its deliberately ineligible event.
- **076:** fixed person and configured Work zone; arbitrary raw destination zones are compared inside the controller. The other-zone departure negative excludes a mere generic state-change trigger.
- **077:** strict crossing below -4.0, including equality and already-below-start negative histories.

`OfficialInput` supplies only typed raw states/events/environment values. `OfficialAction` supplies only atomic typed commands. In particular the fixture supplies no cooldown, timer, absence-duration flag, flashing service, trigger-policy decision, computed history, or average. Ordinary string/message payloads and source action parameters are fixed constants. Pulse unrolling is a finite encoding for a fixed effect duration, not a claim of dynamic unbounded computation.
