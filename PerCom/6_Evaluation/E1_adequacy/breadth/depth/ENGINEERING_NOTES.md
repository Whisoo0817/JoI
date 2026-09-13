# Internal engineering notes (not E1 results, not limitations)

Kept out of E1 results by the author adjudication of 2026-09-13.

- **Extractor-prompt grammar.** Of the eight v1 depth encodings, seven use constructs that
  `files/timeline_ir/extractor.md` does not document (`wait.timeout`, nested `cycle`, `period 0 MSEC`,
  `Clock.Timestamp`, `null` operand); see `grammar_check.py` output in `runs/e1_depth.json`. E1 is not an
  extractor-coverage experiment, so this is tooling information for the NL→IR pipeline only.
- **Reference runner clock.** `explorer.runtime.interp.clock_state` provides timestamp, hour, minute and weekday but
  not `Clock.Second`, which the catalog lists; a JoI condition on `(#Clock).Second` reads null. It affected only
  the E1-095 JoI fallback draft v2 (replaced by v3); no Timeline result depended on it.
