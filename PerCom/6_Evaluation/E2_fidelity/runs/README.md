# E2 run outputs

Committed compressed (`*.jsonl.gz`); restore with `gunzip -k *.gz`. The uncompressed files are ignored by git.

| File | Made by | Content |
|---|---|---|
| `e2_run.jsonl.gz` | `run_e2.py` (2026-09-14, frozen inputs `649cb9c`) | 142 rows; Explorer verdict and witness per pair. Its in-run `reference`/`agreement` fields are **not reported** (witness conversion bug and possible reference version mix, see `../FREEZE_MANIFEST.md`). |
| `e2_run.log`, `e2_run.meta.json` | `run_e2.py` | progress log, run metadata |
| `e2_run.ref-frozen.jsonl.gz` | `rerun_reference.py --label frozen` (reference at `649cb9c`) | reference side, witness replay and agreement recomputed; Explorer fields unchanged |
| `e2_run.ref-current.jsonl.gz` | `rerun_reference.py --label current` (reference after the None-comparison decision) | same |
| `e2_run.ref-current-supp.jsonl.gz`, `.partial.jsonl.gz` | `run_supplement.py` (PROTOCOL_DRAFT §9) | the 59 REF-EQUIV-CHECKED pairs rerun on the supplementary histories; combined reference outcome and agreement; per-pair results |
| `run_supplement.log`, `run_supplement.try2.log` | `run_supplement.py` | the first run (stopped with the session after 57/59 pairs, no output file) and the full rerun |

`recheck_witnesses.py` (witness replay only) was superseded by `rerun_reference.py`, which also recomputes the
witness replay; its output was not kept. Tables: `../RESULTS.md` (`make_e2_results.py`); hand inspection:
`../INSPECTION_2026-09-14.md`.
