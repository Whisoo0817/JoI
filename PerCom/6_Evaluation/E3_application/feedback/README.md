# feedback — counterexample-guided repair (feedback loop)

**결과를 쓸 때는 `HANDOFF.md` 부터 읽는다** — 동결된 수치 네 가지, 대조군 해석, 주장 틀 결정이 거기 있다.
2026-09-16 에 `joi/self_feedback/` 에서 이 자리로 옮겼다. 동결된 JSON 안의 경로 문자열은 실행 당시 값이다.

State on 2026-09-16. The 2026-09-15 implementation (commits up to c8b020d on this branch) was
reset by the author after an error; this directory is the rebuilt, smaller version.

- `prompts/repair.md` — the repair prompt actually used (= `repair_v5.md`): reset-era instruction,
  a 7-row "repair shape checklist", worked examples A–G. Older versions `repair_v0_noexamples.md`
  … `repair_v5.md` are kept for the record; `prompts/fewshot_check.py` verifies every example.
- `dev/` — prompt development: `cases.py` (14 fresh cases, 7 error types × 2, disjoint from the
  E3 data and the examples), `run_repair.py` (one-shot runner), `runs/` (every run, raw responses).
  Summary and decisions: `DEV_NOTES_2026-09-16.md`.
- `repair_core.py` — shared pieces: Explorer verification, F1/F2/F3 feedback, IR timing facts,
  model call, output parsing.
- `protocol_e3_feedback_v1.json` + `PROTOCOL_E3_FEEDBACK_2026-09-16.md` — the frozen protocol of
  the 68-case E3 run. `run_e3_feedback.py` executes it (`preflight` → `repair` → `evaluate`).
- `e3_68_divergence_types.json` — per-case divergence type from the 2026-09-15 audit (reporting only).
- `runs/` — E3 feedback runs (evidence payloads, raw responses, summaries). `runs/harness_check_*`
  evaluated the unrepaired copy through the same pipeline before any model call.
- `RESULTS_E3_FEEDBACK_ABLATION_2026-09-16.md` — the same 68 without the counterexample: **31/68**
  against 36/68 with it (McNemar p = 0.30).
- `RESULTS_E3_FEEDBACK_ROUND2_2026-09-16.md` — round 2 on the 26 still-rejected cases: **40/68**
  with the unchanged prompt; a second exploratory arm with the quantifier rules reaches 42/68.
- `RESULTS_E3_FEEDBACK_2026-09-16.md` — the 68-case run (`runs/e3_feedback_68_20260916`):
  **36/68 EQUIV-FIXPOINT**, cost, and why the other 32 did not make it.
