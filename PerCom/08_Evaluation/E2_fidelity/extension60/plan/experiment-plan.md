# Experiment Plan

## Context
Standalone extension of existing E2, authorized 2026-09-18 (session date). Goal: preserve old140 pairs and add48 E1-derived pairs plus12 LLM candidates for200total. Old results have been inspected; this is a prospectively frozen extension of an exploratory engineering evaluation, not a retroactively preregistered experiment. Run and report outcomes regardless of favorability. No commit/push requested.

## Claim Map
C1: Explorer decisions agree with independent-implementation reference checks on these finite histories. No universal correctness, population representativeness, independent-auditor or exhaustive-input claim. Confirmed false verdict falsifies the zero-contradiction claim.

## Experimental Storyline
B1 adds new single-fault variants on existing20 requests (21automations), B2 adds12 actual generated programs. Total150 hand-built and50generated. Added48 do not mean48new requests. Existing140results retained and currentversion regression explicitly tracked.

## Non-Vacuity Preflight
Old correct/fault examples must produce expected contrasting observable behavior under reference and stable runner. Cache must preserve exact uncached results. Static candidate screening cannot inspect Explorer success. All failure,timeout,unsupported and mismatch states retained. Preflight pending.

## Experiment Blocks
B1 andB2 are must-run; see run-blocks.json for selection and fixed budgets. Each batch is independently frozen before execution to allow immediate LLM execution while fault construction completes. OldE1 histories reused, newLLM histories generated without candidatecode or outcomes. Supplemental policy follows existingE2.

## Run Order
| Order | Block | Purpose | Dependency | Gate ID | Stop / go gate | Est. cost |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | B1 |48 new faults|static freeze and smoke|G1|all48 accounted|hours,parallel|
| 2 | B2 |12 generated|static freeze and smoke|G2|all12 accounted|minutes|

## Decision Gates
| Gate ID | Opens after | Decision question | Proceed if | Revise if | Stop if |
| --- | --- | --- | --- | --- | --- |
| G1 | B1 | Are results interpretable? | complete accounting | contradiction or unsupported narrows claim | harness invalid or data changed |
| G2 | B2 | Are results interpretable? | complete accounting | contradiction or unsupported narrows claim | harness invalid or data changed |

## Risks and Confounds
Originalcaseschosenwithoutoperatorcriterion. Additionalfaultssharesame20requests; notindependent samples. Newmutations may be behaviorally inert; retain them. Runtimeversions may differ from old140; run current-version Explorer regression and check referencehashhistory before combinedclaim. Fixedeightworkerloadcaninfluence timeout; keepruntimeenvironment and allretries. Successful execution is not scientific confirmation. Root audits own work, notindependent verification.

## Pre-execution speed refinement
Before running any extension pair, enable logically sufficient reference short-circuiting: for a fixed selector assignment, a single concrete action/time or contract-runtime divergence establishes REF-DIVERGE, so stop its remaining histories. Under B5, still examine every alternative selector assignment unless one passes all histories; equivalence always requires a complete pass for an assignment. Retain the first discriminating history and actual examined-history counts. All available histories remain frozen. Original conditional supplementary policy retained. This changes work performed, not the reference verdict criterion; validate against full execution on existing correct/fault controls before launch. Do not describe all available histories as executed. Historical140referencecounts are retained separately.
