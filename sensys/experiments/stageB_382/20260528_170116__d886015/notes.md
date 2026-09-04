# stageB_382 — 2026-05-28 17:01 (git d886015, dataset.csv 382 rows)

Stage-B = gold IR injected, lowering only (IR->JoI). The on-contribution accuracy
(deployment regime = user-confirmed IR). run_lower_gt_batch.py, workers=6, ~71min.

## Stage-B accuracy (l2 trace-equiv vs gt_ir)
- verifier OFF: 347/382 = 90.8%
- verifier ON : 357/382 = 93.5%  (+2.7pp)
- 0 err / 0 no_gt / 0 missing.

## Verifier detector matrix (on-mode, attempt-1 vs gt_ir; n=382)
- TP=37 FP=1 FN=0 TN=344 -> precision=0.974 recall=1.000
- fn_split: upstream_ir=0, verifier_miss=0  (gold IR => internal IR == gt_ir,
  so the upstream-extraction FN bucket from E2E VANISHES here)
- recovery: helped 12, hurt 0, both_correct 345, both_wrong 25.

## Cross-run story (with e2e_382)
- E2E FN=30 were ALL upstream_ir; Stage-B (gold IR) FN=0 -> CONFIRMS the E2E
  misses were IR-extraction errors, not verifier insensitivity.
- In the deployment regime (correct/confirmed IR), verifier recall=1.0 on the
  measured set, hurt=0. Report as "on the measured set", NOT a soundness proof.
- This is the on-contribution accuracy (enforcement #2): correctness weight =
  Stage-B + verifier, not E2E.
