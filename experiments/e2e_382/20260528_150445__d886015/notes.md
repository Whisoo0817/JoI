# e2e_382 — 2026-05-28 15:04 (git d886015, dataset.csv 382 rows)

First post-dataset.csv re-run. run_joi_eval_batch.py, workers=6, ~114min wall.

## E2E accuracy (l2 trace-equiv vs ir_gt as PASS)
- verifier OFF: 308/382 = 80.6%
- verifier ON : 321/382 = 84.0%  (+3.4pp)
- 2 err (off) / 3 err (on) = pipeline exceptions; 0 no_gt / 0 missing.

## Verifier detector matrix (on-mode, attempt-1 vs ir_gt; n_scored=379)
- TP=39 FP=4 FN=30 TN=306  -> precision=0.907 recall=0.565
- FN split: upstream_ir=30, verifier_miss=0
  -> ALL 30 unflagged-wrong rows = JoI faithfully matches its OWN internal IR,
     but the internal IR diverged from ir_gt = IR-EXTRACTION error, not a
     verifier/lowering miss. Against its spec (the IR) the verifier missed 0.
- recovery: helped 13, hurt 2, both_correct 308, both_wrong 56.

## Framing (HANDOFF enforcement)
- verifier_miss=0 = the load-bearing honest claim (NOT old stale "R=1.0 on 350").
- 30 FN=upstream IR extraction -> motivates user-confirming the IR (E2E-vs-StageB gap).
- E2E used only as baseline axis + usability proxy + IR-bottleneck diagnosis,
  NOT headlined as verifier evidence (that = mutation/coverage + recovery + confusion).
