# Handoff — 2026-05-22 evening (`cycle.count` primitive landed)

Short, fact-only resume doc for the next session.

## TL;DR — what changed this session

- **D-5 idiom removed.** It was a JoI-sim-asymmetry workaround dressed as an idiom. Replaced by `cycle.count` field-level IR primitive.
- **`cycle.count` field**: optional tick-index var (`"n"`). Lowering = `n := 0` + body verbatim + `n = n + 1`. Handles alternation (`if n%2==0`), N-way rotation (`n%3`), bounded repeat (`until: n >= K`).
- **9-op invariant preserved** (field-level extension like `wait.for`). Idiom count: 7 → 5 (D-3, D-4, D-6, D-9, D-10) + B-2.
- **Dataset**: `gt_old` + `gt_new` columns dropped. New C22 (bounded period, 10 rows). 360 rows total. C13 + C22 ir_gt regenerated to new count shape.
- **Stage B (C13 + C22, 17 rows)**: 17/17 PASS both off/on modes.
- **Critical fix**: removed `_parse_list_of_strings_from_llm` dedup — it was collapsing alternation's `[X, X]` → `[X]` and breaking arg_resolve list form for every alternation/staged-call row.
- **Open paper task**: §7.5 RQ4 needs confusion matrix (TP/FP/FN/TN) not just recovery rate. See [[project-verifier-fp-fn-2026-05-22]].

## What's runnable right now

```bash
# E2E pipeline (full NL → IR → JoI)
python3 test.py target                  # uses test_targets dict in test.py

# Confirm mode: IR-only → readable → user prompt (yes / correction)
python3 test.py target confirm

# Pre-analysis only
python3 test.py pre

# Eval batches (paper §7)
python3 paper/run_ir_only_batch.py          # IR-only, dumps per-row
python3 paper/run_joi_eval_batch.py         # E2E both modes (off/on)
python3 paper/run_lower_gt_batch.py         # Stage B: GT IR → lowering

# Env knobs
JOI_IR_ONLY=1        # skip Stage 4 lowering, dump IR + state
JOI_GT_IR_PATH=...   # inject GT IR, skip service_plan/extract_ir
JOI_VERIFY=1         # enable verifier (L1+L2 + retry harness)
BATCH_WORKERS=N      # parallel subprocess workers
BATCH_CATEGORIES=C01,C20  # subset
BATCH_LIMIT=N        # cap rows for smoke
```

## Numbers

**Pre-count-field baseline (350 rows, l2 trace-equivalence vs ir_gt)**:

| Setting | OFF | ON | Δ |
|---|---|---|---|
| E2E (NL→IR→JoI) | 80.9% (283) | 81.4% (285) | +0.5%p |
| Stage B (GT IR → lowering) | 90.3% (316) | 93.1% (326) | +2.9%p |

Recovery rate (Stage B fails fixed by verifier): **35.5% (11/31)** — pre-count-field.
Per type: timing 71%, missing_call 67%, l2-parser 67%, arg_mismatch 8%, extra_call 0%.
Hurt cases (off-pass → on-fail) at Stage B: **1** (vs 17 at E2E — IR-extract noise was misfiring retries).

**Post-count-field Stage B (C13 alternation + C22 bounded, 17 rows)**: 17/17 PASS both modes. Full 360-row regression not yet measured.

## Dataset

- `dataset_migration/local_dataset2.csv` — **360 rows** (350 + new C22×10).
- Columns: `index, index_old, category, category_v2, command_kor, command_eng, ir_gt, connected_devices, notes` (gt_old + gt_new dropped 2026-05-22).
- **C22 = "bounded period"** (cycle.count + until=n>=K). 10 rows. NL convention: use action-only services (Speaker, Camera) — avoid services with a stop counterpart (RobotVacuum's "stop after 4" gets unrolled by service_plan).
- **C13 = alternation** (cycle.count + if n%2==0). 7 rows. ir_gt re-generated to new count-based shape (replaces old D-5 trailing-delay convention).
- **ir_gt fill**: 360/360 (all rows).

## Uncommitted (intentional — user said commit later)

```
 M dataset_migration/local_dataset2.csv  ← ir_gt column + AC Switch + C19 hysteresis NL + multi-cron rewrite
 M files/service_plan.md                 ← + "No invention (HARD)" rule
 M paper/run_local_ir.py                 ← catalog drop in filter + GT-IR mode + share d-alias
 M test.py                               ← confirm mode (extract_ir retry_context)
?? paper/run_joi_eval_batch.py           ← E2E both-modes batch
?? paper/run_lower_gt_batch.py           ← Stage B batch
```

Recent committed (in branch `paper`):
```
60d552e dataset: rewrite C19 hysteresis NL as 'every N seconds, if A; otherwise if B'
2082692 prompts/timeline_ir_extractor: 'every <duration>' → cycle, not cron
fd41bbb dataset: add Switch category to all AirConditioner devices
26e75c5 paper/timeline_ir: prefix-prefill for start_at + valid_categories in retry hint
fbf40fc paper: IR-only dump mode + share device alias across LLM stages
2671fa8 dataset: boost starved categories +25 rows (325 → 350)
```

## Key clarifications

- **`when` = D-2 noncycle wait** (one-shot); **`whenever / each time / every time` = D-3 cycle+rising**. Locked NL convention.
- **`every <duration>` (pure period, no clock anchor) → top-level cycle**. Wall-clock anchor (`at 8 AM`, `weekends`) → cron.
- **`if` = single snapshot check**. For polling, NL must say "every N seconds" or similar.
- **Hysteresis** in NL needs `"Every 1 sec, if A on; otherwise if B off"` to land on `cycle{ if A {On} else { if B {Off} } }`.
- **Verifier's internal accept = `l2(extracted_ir, joi)`**; external grading uses `l2(ir_gt, joi)`. These can diverge (e.g., enum literal `"open"` vs `"unlocked"`); that's why E2E gain looks small.
- **Multi-cron** (two distinct cron schedules in one NL) is a 9-op closure limit — preprocess agent's job to split. Only 2 dataset rows hit this; rewritten as 1-hour-delay.

## Paper §7 mapping (what data already exists)

- §7.2 E2E (RQ1) — base 80.9% off / 81.4% on. No baseline comparison yet.
- **§7.3 Stage B / C2 (RQ3 lowering correctness given gold IR) — DATA READY**. 90.3% off / 93.1% on. Per-cat table available.
- **§7.5 Self-correction lift (RQ4) — DATA READY**. Recovery 35.5%, per-type breakdown.
- §7.4 Verifier coverage (RQ3 obligation activation) — not measured yet.
- §7.6 User study (RQ7) — not run.
- §7.7 Deployment (RQ8) — not run.
- §7.8 Cost/edge (RQ6) — not measured.
- §8 Ablation (RQ2) — not run.

## Open next actions (priority)

1. **Confusion matrix instrumentation** — pipeline needs per-row `verifier_decision_log` field (attempt#, accept/reject, hint_codes). Then Stage-B re-run gives TP/FP/FN/TN with GT-IR oracle. §7.5 hero metric becomes (precision, recall, hurt rate), not just recovery rate. See [[project-verifier-fp-fn-2026-05-22]].
2. **Full 360-row Stage B + E2E regression** after count-field changes. Check whether non-alternation categories still match prior 90.3% baseline.
3. **service_plan bounded-unroll fix** — planner sometimes unrolls "do X N times then stop" into N+1 calls (C22_5 originally). Prompt rule: bounded cycle stays 1-iteration body + cycle.until.
4. **arg_resolve list-form** — dedup removal helps but LLM still occasionally returns dict for N>=2. Sharpen prompt OR add deterministic guard (skip overlay when call-site count > 1 and resolved is dict).
5. **arg_mismatch surgical hint** — generic hint can't fix 87% of arg-mismatch failures. Per-arg expected/actual signal needed.
6. **OOD / adversarial set** (RQ5) — drop baseline to expose verifier gain.
7. **B4-B7 baselines** (RQ1) — GPT-4o + simulator-self-repair etc. Not built yet.

## Useful paths

- IR-only dumps: `/tmp/joi_ir_dump_full2/` (v2 batch)
- Stage-B dumps: `/tmp/joi_lower_gt/{off,on,gt_ir}/`
- E2E eval summary: `/tmp/joi_eval_full/_summary.json`
- Stage-B summary: `/tmp/joi_lower_gt/_summary.json`
- Grader v3 detail: `/tmp/joi_ir_grade.json`

## Cross-reference

Memory: `~/.claude/projects/-home-gnltnwjstk/memory/`
- `MEMORY.md` (index)
- `project_pipeline_state_2026_05_22.md` (this state, expanded)
- `project_evaluation_plan_2026_05_21.md` (paper RQ1-RQ8)
- `project_paper_narrative_2026_05_21.md` (§3-§6 flow)
- `project_joi_dataset_categories.md` (21-cat schema)
