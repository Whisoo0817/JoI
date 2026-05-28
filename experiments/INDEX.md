# Experiment Ledger

Single source of truth for every experiment run from 2026-05-28 onward. **Append a row per run. Never delete rows.**

## How experiments are recorded (the contract)
Every run lives in `experiments/<exp-name>/<YYYYMMDD_HHMMSS>__<gitshort>/` and MUST contain:
- `run.json` — provenance: git commit, dataset path + **sha256**, model id + quant + vLLM args, exact command, params/seed, start/end time. (Use `experiments/init_run.py` to generate it.)
- `raw/` — raw logs verbatim (test.py stdout, per-row logs). Never edited; kept for re-parse.
- `results/` — parsed metrics: `aggregate.json`, `per_category.csv`, `per_row.csv`.
- `intermediate/` — generated IR, JoI, verifier traces, confusion matrices, mutants, etc.
- `notes.md` — human notes, anomalies, decisions.

**Provenance pinning**: results are only meaningful tied to (code commit + dataset sha256 + model+decode config). `init_run.py` captures all three. If the dataset changes, the sha256 changes → old results are flagged stale.

**What goes in git**: `run.json`, `results/`, `notes.md`, this INDEX. **Disk-only (large/optional)**: bulky `raw/` and `intermediate/` may be kept locally and not committed (decide per run); but always keep them on disk.

## Metrics always captured (where applicable)
E2E accuracy (verifier OFF) · Stage-B accuracy (gold IR→JoI) · self-correction recovery rate · verifier confusion matrix (TP/FP/FN/TN, precision/recall) · per-category breakdown · tokens + p50/p95 latency + GPU mem. Mutation: per-operator catch rate + survivors. Coverage: spec/impl two-sided.

## Ledger
| date | exp | git | dataset sha256 (short) | model | key result | dir |
|---|---|---|---|---|---|---|
| 2026-05-28 | e2e_382 | d886015 | fff8f044b2ce | Qwen3.5-9B-AWQ-4bit | E2E OFF 80.6% / ON 84.0% (+3.4); detector P=.907 R=.565, verifier_miss=0, FN=30 all upstream_ir; recovery helped13/hurt2 | experiments/e2e_382/20260528_150445__d886015 |
| 2026-05-28 | stageB_382 | d886015 | fff8f044b2ce | Qwen3.5-9B-AWQ-4bit | Stage-B OFF 90.8% / ON 93.5% (+2.7); detector P=.974 R=1.0 FN=0 FP=1; recovery helped12/hurt0 | experiments/stageB_382/20260528_170116__d886015 |
| 2026-05-28 | mutation_382 | d886015 | fff8f044b2ce | n/a (sim, stageB seeds) | 1424/1438=99.03%; comparator 86.3% rest 100%; 14 survivors ALL C20 comparator>=->> sub-tolerance by-design | experiments/mutation_382/20260528_181341__d886015 |
| 2026-05-28 | coverage_382 | d886015 | fff8f044b2ce | n/a (sim) | 441/480=91.9% two-sided IR-FSM obligation coverage; 39 uncovered=non-synth guards (var-cmp/quantifier/arith), input-synth limit not detection miss | experiments/coverage_382/20260528_194842__d886015 |
| 2026-05-28 | mutation_382_v2 | d886015+dirty | fff8f044b2ce | n/a (sim) | 1461/1475=99.05% (11 ops, +break_drop 37/37=100%); comparator 86.3% rest 100%; 14 survivors=same sub-tolerance class; sim MAX_TICKS/MAX_RAW caps added | experiments/mutation_382_v2/20260528_210527__d886015 |
