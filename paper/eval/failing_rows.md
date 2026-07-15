# Failing Rows — Deferred Pipeline Diagnosis Backlog

Updated after Phase 1 baseline (2026-05-19 18:44). 35 residual failures across 7 clusters.

**Source logs**: `/tmp/joi_eval_<CAT>_20260519_184411.log`
**Cache**: `paper/simulators/cache/<CAT>_<idx:03d>.json` — contains the IR + JoI script per row.

LLM is stochastic; some rows that pass/fail here may flip on regen. Cluster classification by behavior shape, not specific row.

---

## Cluster A — Lowering drops 2nd call in two-call sequences (8 rows)

Pattern: `group 0: record count IR=2 JoI=1`. IR has two-call sequence (read+speak, record+save, generate+save, increment register+set), JoI lowering emits only first.

| Cat | Idx | Command (truncated) |
|---|---:|---|
| C01 | 15 | Generate a cat image and save as "cat.png" |
| C01 | 18 | Lunch menu for Building 301 through speaker |
| C01 | 19 | Ask cloud AI what an LLM is, output through speaker |
| C02 | 10 | Record 10s with meeting room recorder and save |
| C04 | 1  | If recording, stop recording and save |
| C14 | 1  | Button-1 press → increase volume (read + set) |
| C14 | 2  | Button-2 press → decrease volume |
| C14 | 4  | Whenever motion → increase light brightness |
| C15 | 9  | Noon: announce lunch menu (cron + read + speak) |
| C15 | 10 | 6PM: announce dinner menu |

**Suspect**: `paper/joi_from_ir.md` noncycle bucket — `read(X); call(Speak/Save, $X)` 2-step idiom collapse. Check whether lowering folds `read` into `call.args` then drops the explicit `call`. Same family includes counter-increment idioms (read + set ± delta).

---

## Cluster B — JoI emits 0 when IR emits 1 (key-namespace drift) (9 rows)

Pattern: `group count differs: IR=1 JoI=0`. IR cond key (`Light.IsOn` → `light.ison`)와 JoI cond key (`(#Light #Hallway).isOn` → SELECTOR last-tag `hallway.ison`)가 다른 네임스페이스. Synth seeds IR-side key only; JoI's cond reads from never-seeded key → `None == true` → False → body skipped.

Confirmed sub-pattern: `canonical_key` derives JoI's selector ref from LAST `#tag` inside `(#A #B #C)` (e.g. `Factory`), while IR's `Service.Attr` form uses the bare service name (e.g. `Switch`). These produce different `(service, attr)` tuples.

| Cat | Idx | Command (truncated) |
|---|---:|---|
| C03 | 13 | If face recognition at entrance is off, start it |
| C05 | 19 | CO₂ ≥ 1000ppm AND ... |
| C05 | 20 | Bathroom humidity ≥ 85% AND ... |
| C05 | 30 | LR light on AND illuminance 50 lux ... |
| C08 | 29 | Whenever light in upper part turned on |
| C08 | 30 | Whenever button with 'Light' tag pressed |
| C10 | 6  | Any light in hallway on → turn off all |
| C16 | 11 | Every 5min 10PM-11PM, check + turn off |
| C16 | 13 | Every 10PM, if door open, lock it |

**Suspect**: lowering prompt or precision-to-lowering selector translation. JoI side should canonicalize cond key to same namespace as IR uses. Or extend `apply_effect`+`expr` to alias the two forms.

---

## Cluster C — D-3 phase-flag double-emit (2 rows, timeout)

JoI lowering의 phase=0 init block과 phase=1 body block이 첫 tick에 둘 다 fire하는 off-by-one — paper §6.4 obligation violation의 정확한 예시.

| Cat | Idx | Pattern |
|---|---:|---|
| C12 | 5  | Smoke detected → siren every minute |
| C12 | 13 | Presence on 1F → speak every 5s |

Group 1에서 IR=1 (after first iteration's siren-only) vs JoI=2 (off + siren simultaneously due to phase=1 firing in same tick as phase=0 init).

**Suspect**: `files/joi_cycle.md` switchboard에서 D-3 phase-lifecycle template — phase=0 transition body가 phase=1 body 정의를 inline 포함하거나, 첫 tick에서 phase=1 block 실행을 skip해야 함.

---

## Cluster D — Cron cycle 의미 / IR-JoI 구조 차이 (4 rows)

각각 다른 원인:

| Cat | Idx | Symptom | Suspect |
|---|---:|---|---|
| C17 | 3 | IR=1 JoI=168 | IR shape: `start_at(cron); call` (no cycle) — recurring cron collapsed to one-shot. **Extractor bug** — should be `start_at(cron); cycle{call} period:1HOUR`. |
| C18 | 4 | IR=180 JoI=90 | Lowering alternation idiom mismatch. IR has body=[A, delay 5s, B] within one iteration; JoI alternates A/B across iterations. **Lowering bug**. |
| C18 | 5 | IR=96 JoI=0 | IR `Pump.Switch` key + `apply_effect` not handling `Switch` method as toggle. Both key-namespace drift (Cluster B) AND effect handler gap. |
| C18 | 10 | IR=6 JoI=7 | JoI puts Door.close inside tick loop (fires every hour), IR has it outside cycle. **Lowering structure bug**. |

---

## Cluster E — D-5 alternation back-to-back (3 rows)

IR extractor가 `cycle.body=[callA, callB]` (no inter-call delay)으로 alternation semantics 손실.

| Cat | Idx | Command |
|---|---:|---|
| C13 | 2  | Every 30min toggle living room air purifier |
| C13 | 4  | Every 30min toggle air purifier sleep/auto |
| C13 | 7  | Every hour alternate AC target temperature |

**Suspect**: `paper/timeline_ir_extractor.md` D-5 idiom — should emit `[A, delay, B, delay]` with `cycle.period`. Known issue from 5/19 memo, may have regressed with stochastic re-runs.

---

## Cluster F — Misc per-row (10 rows)

| Cat | Idx | Class | Symptom / Suspect |
|---|---:|---|---|
| C01 | 24 | trace_mismatch | "Play music.mp3" group 0 record mismatch — args normalization |
| C02 | 12 | trace_mismatch | "Play Golden.mp3 in playroom" |
| C03 | 2  | trace_mismatch | "If cloud activated, upload test.png" args |
| C05 | 8  | trace_mismatch | Compound cond + args |
| C05 | 24 | trace_mismatch | Baby room sound compound cond |
| C07 | 10 | parse_fail_joi | `expected OP ')' got '{'` — JoI parser hits malformed brace |
| C15 | 12 | trace_mismatch | "Every hour on Christmas" |
| C15 | 15 | pipeline_error | Multi-cron reject (known policy, paper §7 limitation) |
| C16 | 5  | pipeline_error | Multi-cron reject |

---

## Summary table

| Cluster | rows | Owner | Phase fixing it |
|---|---:|---|---|
| A — 2-call collapse | 10 | pipeline (lowering) | Phase 4 self-correction or prompt fix |
| B — key-namespace drift | 9 | pipeline (lowering or canonicalization) | Phase 4 |
| C — phase-flag double-emit | 2 | pipeline (lowering D-3 template) | Phase 4 |
| D — cron/cycle structure | 4 | mixed (extractor + lowering) | Phase 4 |
| E — D-5 alternation | 3 | pipeline (IR extractor) | Phase 4 |
| F — misc args / parse / multi-cron | 7 | mixed | Phase 4 + paper limitation |
| **total** | **35** | | |

Phase 2~3 (IR-FSM + scenario synthesis + verdict layer) 작업이 이런 결함을 **자동으로 진단**해 Phase 4 self-correction 입력을 만들어내는 게 목표.
