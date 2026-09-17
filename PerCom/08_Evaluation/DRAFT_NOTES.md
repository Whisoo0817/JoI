# Evaluation draft notes (2026-09-17)

## Status and scope

- User requested drafting and pushing the revised plan. Motivation onward remains pending user feedback.
- Local manuscript: `PerCom_version.md`. Overleaf: `/home/gnltnwjstk/overleaf-paper/sections/evaluation.tex`, included after behavioral validation as Section VII.
- Four compact tables, one per E1–E4. Captions remain short. No figures or earlier manuscript sections were changed.
- Counterexamples supply mismatch information for repair. The paragraph reports 36 equivalent, 26 divergent, five timeouts, one context error after one repair call on each of 68 cases. No no-counterexample comparison, significance test, or causal improvement claim appears in the manuscript. All comparison results remain in the research records.
- E4 is a descriptive report of the existing serial Explorer / four-worker baseline configurations, not a matched-load speedup result. No new experiment or complete scientific audit was performed.

## Evidence checks

- E1 (updated 2026-09-18): `E1_adequacy/breadth/remaining72/paper_summary.json` aggregates all 92 in-scope requests and 294/294 exact histories from raw traces. The original 20 contribute 53 histories; the added 72 contribute 241 after the E1-024 revision on unchanged expectations. Seventeen supplemental histories remain separate. `E1_SUMMARY.md` remains the historical 20-case report. These are final encodings under recorded interpretations, not universal coverage or independently validated intent.
- E2: recomputed from `E2_fidelity/runs/e2_run.timer-binding.jsonl.gz`, excluding the two invalid inputs in the fixed population definition. 140 pairs, verdicts 55 EQUIV / 75 DIVERGE / 5 REFUSED / 5 TIMEOUT. Agreement groups 55 checked-history equivalent / 67 reference-history divergent / 8 witness-confirmed divergent. These are different evidence strengths. The 75 observable fault variants and the 75 total divergent verdicts are distinct populations.
- E3: recomputed status counts from `explorer/eval/results/e3_single_binding_382_20260915_run/case_outcomes.jsonl`: 309/68/3/2. Generation, CPU, Python and checker budgets read from its `protocol.json`. Current corpus lineage is 63 regenerated and 319 reused candidates, exploratory familiar tasks.
- Example checked against candidate `qwen3_5-9b-fp8-e3-single-binding-v4/C20_001.json` and its replay-confirmed result. Confirmed IR waits for 30 seconds with no motion. Candidate increments at t=0 and each 1-second tick and acts at t=29 seconds. Witness has 28 seconds of prior dwell plus the final 1-second reaction, with no IR action and Switch.Off in candidate actions.
- E4: grouped both `e4_free_serial.jsonl` and `e4_explicit_w4.jsonl` by cell and required all three repeats to finish. Reproduced 30 total, 28 vs 12 decided, and 19 Explorer programs whose slowest run is below one second. Table values use the stored maximum per program. Memory units corrected to MiB (source uses ru_maxrss/1024).
- Repair: `E3_application/feedback/RESULTS_E3_FEEDBACK_2026-09-16.md`, one call, same model, temperature 0, 4096 tokens. No retries or second-round best results substituted.
- Legacy `results-audit-final` for E3 is withdrawn and does not authorize the current 382-case result. E2 optimization audits predate final reference confirmation. This draft follows the latest descriptive reports and raw counts without claiming a newly validated canonical audit pack.

## Writing and humanizer pass

Manuscript-writing, humanizer and manuscript-formatting skills were applied in that order, preserving local SenSys-derived style: purpose-led experiment paragraphs, consistent technical terms, IEEE title-case headings and selective bold lead-ins.

Draft repair close: "This reports one revision attempt per case without attributing repair success to the counterexample alone."

Anti-AI review: this was editorial commentary about what the prose does, not an experimental result. Remove it and state actual repair settings and outcomes. Other repeated generic summary language was avoided; table values are interpreted instead of recited in full in prose.

Final repair close: "The resulting outcomes were 36 equivalent, 26 divergent, five checking timeouts, and one model context error out of 68 cases."

No em-dash prose, invented citations, significance claims, universal accuracy, or new device-safety claims were added. IEEE headings and local bold lead-ins intentionally override generic humanizer style preferences.

## Build and remaining work

- Tectonic build succeeded. Tables III–VI were inspected in the rendered PDF on pages 8–9, with no clipped content or table overflow.
- Evaluation occupies about 1.7 pages in the current float layout. Complete draft is 11 pages including references and appendix, before Limitations/Conclusion. This is not a submission-ready page count. Planned earlier-section/figure reductions remain separate work.
- Existing algorithm-package UTF-8 warning, PDF-version warnings and earlier-section underfull boxes remain. No new overfull boxes or unresolved references were seen.
- No runtime code changed and no experiments were rerun. New writing does not approve Motivation or any following section on the user's behalf.
- E4 matched-load runs, if a causal efficiency comparison is desired, remain future work rather than implied completed checks. Exact E4 host/RAM/software snapshot details are not fully established by the E4 logs; the draft uses the recorded eight-core/worker-count information only. E3 hardware is explicitly scoped to E3.
- Fig. 2's optional revision path is consistent with the Evaluation paragraph. No additional figure changes are needed for this section; prior Section VI label suggestions remain in its own notes.


## E1 선정 기준 저자 확인 (2026-09-17)

- 사용자가 기존 기록에는 명시되어 있지 않지만, 100건의 요청에서 확인한 연산자 유형을 모두 포함하는 대표 요청 20건을 선정한 것이 사실이라고 직접 확인했다.
- 이 저자 확인에 근거해 영문·한글·LaTeX의 선정 기준을 수정했다. 기존 기록에서 대응표를 발견했거나 독립적으로 전수 검증한 것으로 서술하지 않는다.
- 연산자 유형의 포괄과 요청 전체의 표현 가능성은 구분한다. 연산자의 모든 조합을 시험했다거나, 100건 모두를 IR로 실행했거나, 전체 스마트홈 요청에 대한 통계적 대표성을 확보했다는 주장으로 확대하지 않는다.
- 수집 100건, 범위 분류 92/6/2, 상세 평가 20건, 추가 조건 없는 17건과 조건부 3건, 재현 이력 53/53이라는 수치는 유지했다. 본문에서 해석 수정 이력 보존 설명은 빼고, 수집·선정·표현 및 실행 확인 흐름을 명시했다.

## E1 full-cohort rewrite (2026-09-18)

- Rewrote English, Korean and Overleaf E1 around all 92 in-scope requests. Removed the obsolete representative-20 selection rationale and the old 17+3 outcome table.
- New source table: official 25 collected / 25 evaluated / 97 exact histories; research 26 / 24 / 74; participant responses 24 / 20 / 58; community 25 / 23 / 65. Totals: 100 / 92 / 294.
- `make_paper_summary.py` checks cohort identity, unchanged E1-024 core expectations, and raw action/timestamp comparisons, then generates `paper_summary.json` and `PAPER_TABLE.md`. Input hashes and per-case counts make the table reproducible. No experiment was rerun for this rewrite.
- The text distinguishes the original author-reviewed 20 interpretations from 72 agent-derived interpretations and their expected traces. It reports final encodings, retains previous failures, and states material scope assumptions. Examples explain compositions rather than claiming every operator combination.
- E2 still uses the initial 20 requirements and 53 reference traces. Its wording now identifies that original cohort; its counts and results did not change.
- Humanizer pass removed the selection-history emphasis and kept concrete behavioral examples and plain descriptions of the measured result. The remaining qualifications affect interpretation of the 92-case claim.
- Tectonic build succeeded at `/tmp/percom-e1-92-review/main.pdf`; no overfull boxes or unresolved references. The table was visually checked on PDF page 7. Existing package/PDF-version, font-substitution and underfull-box warnings remain. No commit or push performed for this rewrite.
