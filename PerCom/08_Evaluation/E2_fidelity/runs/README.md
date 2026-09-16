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

Binding decision (`../BINDING_DECISION_2026-09-14.md`, both tools changed; frozen results above unchanged):

| File | Made by | Content |
|---|---|---|
| `e2_run.binding-v1.jsonl.gz`, `.partial.jsonl.gz`, `.meta.json`, `run_binding_v1.log` | `run_binding_v1.py` (B1/B2) | 142 rows: reference (frozen + supplementary histories), Explorer, witness replay, agreement |
| `e2_run.binding-b5.partial.jsonl.gz`, `run_binding_b5.log` | `run_binding_b5.py` (B5 selector assignments) | the 22 pairs with selector assignments |
| `e2_run.binding-final.jsonl.gz` | `run_binding_b5.py` merge | binding-v1 rows with the 22 B5 rows replaced; C05/fault2–3 Explorer rerun alone after a CPU-contended TIMEOUT (`explorer_under_load` keeps it) |

Final version (semantics-preserving exploration optimizations from the merged timer branch, with the binding decision):

| File | Made by | Content |
|---|---|---|
| `e2_run.timer-binding.jsonl.gz`, `.meta.json`, `run_timer_binding.log` | `../run_timer_binding.py` (Explorer-only rerun; the meta file records the timer worktree and head `476faeb` it ran from; reference outcomes from `e2_run.binding-final`) | 142 rows; `explorer_binding_final` keeps the Explorer verdict before the optimizations; new witnesses replayed on the reference. The C03_008 row was rerun with a parser change that accepted a bound `any` action (`explorer_before_parser_fix` keeps the refusal); that change was withdrawn on 2026-09-14 and the pair is excluded (below) |

Other logs: `rerun_frozen.log`, `rerun_current.log` (`../rerun_reference.py`).

**Population (2026-09-14, whisoo).** Every reported table uses the 140 pairs of `../handoff_timer/e2_population.json`:
`C03_008/llm` (`any(...)` in ACTION position; `any` is allowed only inside a condition, so it is a syntax error) and `C20_011/llm` (invalid service mapping) are excluded.
The run files keep all 142 rows unchanged.

`recheck_witnesses.py` (witness replay only) was superseded by `rerun_reference.py`, which also recomputes the
witness replay; its output was not kept. Tables: `../RESULTS.md` (`make_e2_results.py`, which reads the `.jsonl` or
the committed `.jsonl.gz`); hand inspection: `../INSPECTION_2026-09-14.md`.
