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
| _(first run appends here)_ | | | | | | |
