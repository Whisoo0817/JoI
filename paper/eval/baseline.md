# Phase 0/1 Baseline — 2026-05-19

## History

| Run | Date | Pass | Total | % | Notes |
|---|---|---:|---:|---:|---|
| Phase 0 baseline | 2026-05-19 14:42 | 271 | 307 | 88.3 | Fresh cache, post 5/19 lowering overhaul (commit 172c6bd). 36 failures. |
| **Phase 1 baseline** | **2026-05-19 18:44** | **270** | **307** | **87.9** | After Phase 1 sim fixes. Fresh cache. 32 failures. Net pass-rate ~unchanged (LLM stochasticity); sim model gaps removed from failure vocabulary. |
| Group P (pipeline residuals) | 2026-05-20 | 262 | 307 | 85.3 | Post Group P pipeline hardening. Cache used (Phase 1 cache). Group P closure brought 6 cluster residuals down to known shapes (`paper/eval/HANDOFF.md`). |
| **Phase 2 v2 (sim/L2 fixes, cache)** | **2026-05-21 15:01** | **278** | **307** | **90.6** | Verifier-v2 simulator + L2 fixes only (no LLM re-run). +16 vs Group P from: JoI `Var = Call(...)` trace emit fix; IR `$Var` raw-type preservation + `_maybe_eval` arithmetic-marker refinement; L2 within-group missing+extra+arg → arg_mismatch collapse + cross-group occurrences merge; canonical-key symmetric L1 catalog check. |
| **Phase 2 v2 (fresh, partial 4 cats)** | **2026-05-21 15:08** | 28/39 | – | 71.8 | 4 cats (C14/C16/C17/C18). `--no-cache` LLM re-run with new prompts + IR-extract validator + arg_resolve expression form. +3 rows over cache for the same 4 cats. Failures dominated by IR/JoI cycle-iteration-count mismatch (e.g. C18#7 IR=840 vs JoI=120 groups), not lowering bugs. |

**Phase 2 v2 structural changes** (detailed in [[project-verifier-v2-2026-05-21]] memory). Highlights:

- IR-extract validator retry (`IRViolation` codes: `service_not_in_catalog`, `member_not_in_service`, `service_not_in_devices`, `arg_not_in_catalog`, `enum_value_unquoted`) — catches catalog/sub-service/enum-quoting failures before downstream stages.
- JoI lowering retry harness wired into `run_local_ir.py` (env `JOI_VERIFY=0/1`).
- Prompt audit: `joi_common.md` surface-mirror + clamp anti rules; `joi_noncycle/cycle.md` Light.On → Switch.On; `timeline_ir_extractor.md` R1.1 sub-service + R1.2 enum quote; `arg_resolve.md` §7.1 relative-change expression, §7.2 ceiling/floor `min/max`, §7.3 omit-undeclared-args.
- Simulator symmetry fixes (JoI assign-call emit, IR captured-return canonical, IR `_maybe_eval` not over-matching).
- L2 violation collapse (within-group disjoint→arg_mismatch; cross-group same-key occurrences) — eliminates per-iteration explosion that confused retry hints.
- Tool: `paper/eval/verifier_replay.py` — LLM-free cache sweep, ~seconds.

Phase 1 sim fixes (all in `paper/simulators/`):
1. `expr.py` — added `all/any/avg` to `_BUILTIN_FUNCS` and evaluator (single-device collapse fallback per framework 2026-05-08).
2. `event_synth.py` `_gather_assignments` / `_unwrap_quantifier` — recurse into FuncCall quantifier wrappers when extracting satisfying-value seeds.
3. `comparator.py` `compare_traces(prefix_mode=...)` — trim to common prefix excluding last group when MAX_TRACE saturation. Eval_harness passes `prefix_mode=True` on saturation.
4. `event_synth.py` `_synth_wait(period_ms=...)` + `_walk(period_stack=[...])` — period-aware prelude/fire placement for edge waits inside cycles with known period (paper hygiene; no measurable pass-rate impact in current dataset).

## Aggregate (Phase 1)

| Class | n | % |
|---|---:|---:|
| pass | 270 | 87.9 |
| trace_mismatch | 32 | 10.4 |
| timeout | 2 | 0.7 |
| pipeline_error | 2 | 0.7 |
| parse_fail_joi | 1 | 0.3 |
| unknown_op | 0 | 0.0 |
| parse_fail_ir | 0 | 0.0 |
| **total** | **307** | **100** |

**Key win**: `unknown_op` (sim limitation) → 0. `timeout` 1건 감소.

## Per-category (Phase 1)

| Cat | n | pass | mismatch | parse_fail_joi | timeout | pipeline_error | pass% |
|---|---:|---:|---:|---:|---:|---:|---:|
| C01 | 28 | 24 | 4 | 0 | 0 | 0 | 85.7 |
| C02 | 33 | 31 | 2 | 0 | 0 | 0 | 93.9 |
| C03 | 30 | 28 | 2 | 0 | 0 | 0 | 93.3 |
| C04 | 3 | 2 | 1 | 0 | 0 | 0 | 66.7 |
| C05 | 30 | 25 | 5 | 0 | 0 | 0 | 83.3 |
| C07 | 32 | 31 | 0 | 1 | 0 | 0 | 96.9 |
| C08 | 41 | 39 | 2 | 0 | 0 | 0 | 95.1 |
| C09 | 18 | 18 | 0 | 0 | 0 | 0 | 100.0 |
| C10 | 9 | 8 | 1 | 0 | 0 | 0 | 88.9 |
| C11 | 1 | 1 | 0 | 0 | 0 | 0 | 100.0 |
| C12 | 15 | 13 | 0 | 0 | 2 | 0 | 86.7 |
| C13 | 7 | 4 | 3 | 0 | 0 | 0 | 57.1 |
| C14 | 4 | 1 | 3 | 0 | 0 | 0 | 25.0 |
| C15 | 21 | 17 | 3 | 0 | 0 | 1 | 81.0 |
| C16 | 13 | 10 | 2 | 0 | 0 | 1 | 76.9 |
| C17 | 12 | 11 | 1 | 0 | 0 | 0 | 91.7 |
| C18 | 10 | 7 | 3 | 0 | 0 | 0 | 70.0 |

## Failure clusters (Phase 1 residual)

Phase 1 사후 잔존 32 실패 + 2 timeout + 1 parse_fail_joi + 2 pipeline_error. 거의 모든 케이스가 pipeline 결함.

### Cluster A — Lowering drops 2nd call in two-call sequences (8건)
`group 0: record count IR=2 JoI=1`. Pattern: `read+speak`, `record+save`, `generate+save` 등 2-step 시퀀스에서 lowering이 둘째 call을 흡수·삭제.
- C01 #15, #18, #19
- C02 #10
- C04 #1
- C14 #1, #2, #4 (counter increment 등)
- C15 #9, #10

### Cluster B — JoI emits 0, IR emits 1 (key-namespace drift) (7건)
`group count differs: IR=1 JoI=0`. IR cond key (`Light.IsOn`)와 JoI cond key (`(#Light #Hallway).isOn`)가 canonical 매핑에서 다른 네임스페이스 (canonical_key가 마지막 tag 기준 svc 추출 vs IR의 명시 service). Synth seeded IR side만.
- C03 #13 "If face recognition off"
- C05 #19, #20, #30 compound cond
- C08 #29, #30 D-3 rising-edge cycle
- C10 #6 D-3 hallway light
- C16 #11 cycle-bound check
- C16 #13 every 10PM cron

### Cluster D — D-3 phase-flag double-emit (2건, timeout)
JoI lowering의 phase=0 init block과 phase=1 body block이 첫 tick에 둘 다 fire → group 1에서 IR=1 JoI=2.
- C12 #5, #13

### Cluster E — Cron cycle 의미 / IR-JoI 구조 차이 (3건)
- C17 #3 "every hour, volume+10" — IR shape collapses recurring cron to one-shot (extractor bug).
- C18 #4 "every 10min until 3PM" — lowering alternation idiom mismatch.
- C18 #5 "weekends pump check" — IR `Pump.Switch` key + apply_effect not handling toggle.
- C18 #10 "midnight + every hour" — JoI puts Door.close inside loop, IR has it outside cycle.

### Cluster F — D-5 alternation back-to-back (3건)
IR extractor가 `cycle.body=[callA, callB]` (delay 없음)으로 alternation 의미 손실.
- C13 #2, #4, #7

### Cluster G — Misc per-row (10건)
- C01 #24 "Play music.mp3" args mismatch
- C02 #12 record mismatch
- C03 #2 "If cloud activated" args mismatch
- C05 #8, #24 compound cond record mismatch
- C07 #10 parse_fail_joi: lowering emits unclosed paren / brace
- C15 #12 "every hour on Christmas" group 0 mismatch
- C15 #15, C16 #5 multi-cron pipeline reject (알려진 policy)

## Decisions

1. **Phase 1 sim 작업 완료**. 잔존 35 실패는 거의 모두 pipeline 결함. sim model gap은 사실상 0.
2. **Cluster A (2-call collapse)**, **Cluster B (key-namespace drift)**, **Cluster D (phase-flag double-emit)** 가 가장 큰 패턴 — paper §6.4 verification system이 잡아야 할 정확한 종류의 obligation 위반. Phase 2~3 IR-FSM + scenario synthesis가 이걸 자동 진단해야 함.
3. **Phase 2 진입 가능**. IR-FSM 유도 + L1 static check 작업으로 이동.
4. Pipeline 결함 fix는 Phase 4 self-correction 또는 별도 prompt 작업 (사용자 지시상 deferred).

## Reproduction

```bash
cd /home/gnltnwjstk/joi
./paper/eval/run_baseline.sh           # all 17 cats
./paper/eval/run_baseline.sh C13 C14   # subset
```

Cache 삭제 후 재실행:
```bash
rm -rf paper/simulators/cache/*.json
./paper/eval/run_baseline.sh
```

## Logs

- Phase 0: `/tmp/joi_eval_*_20260519_144214.log`
- Phase 1: `/tmp/joi_eval_*_20260519_184411.log`
