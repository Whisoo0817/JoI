# Simulator improvement backlog

Pending work on the IR/JoI simulator suite. Items are grouped by area and tagged with rough effort. Order within each group is suggested priority.

Current state (2026-04-28): 11/11 hand-crafted E2E tests pass; 85.1% (131/154) of C01–C07 dataset rows pass after sim normalizations. The 23 remaining failures are pipeline bugs (real lowering or IR-extractor issues) — they should NOT be hidden by further sim normalization.

---

## A. Quantifier semantics (`any`, `all`)

Currently `any/all` selectors and the `==|` / `>=|` / etc. quantifier operators are **parsed but degraded** — `==|` is treated as plain `==`, and `any(#X)`/`all(#X)` selectors collapse to last-tag canonical key. This works when only one device matches, but loses fidelity when:
- Multiple devices match the selector and only some satisfy the cond (`any` should be true if ≥1 satisfies; `all` requires every device to satisfy)
- The trace should reflect parallel-broadcast vs single-device action semantics

### A1. Multi-device world model — *medium*
- World state needs per-device-instance keys, not just per-service.
- e.g. `LivingRoom_Light.brightness=80`, `Kitchen_Light.brightness=60` — currently both collapse to `light.brightness`.
- Selector resolution: walk `connected_devices` from scenario, return matching device IDs given tag list.

### A2. `==|` / `>=|` quantifier evaluation — *small once A1 lands*
- Parser already accepts the operators (joi_parser._CMP_OPS).
- Evaluator needs: given selector resolving to N devices, evaluate cond per-device, then `any` (≥1 true) or `all` (every true).
- Distinguish `any(#X).Y == V` (default `any` semantics with `==`) from `any(#X).Y ==| V` (explicit any-form).

### A3. `any/all` synth coverage — *small*
- `event_synth.py` currently hard-errors / no-ops on quantifier conds.
- For paper-coverage scenarios, seed at least one device's attribute to satisfy `any`, all devices for `all`.

### A4. Trace emission for multi-target — *small*
- Decision needed: when `all(#Light).On()` fires across N devices, do we emit 1 record or N?
- Locked design says 1 record per IR `call` op (selector cardinality is precision-stage's domain, out of scope for trace equivalence). Verify both sims honor this once A1 lands.

---

## B. Fuller idiom coverage in test_e2e

`test_e2e.py` covers D-1..D-5, D-7, D-9, B-2 with hand-crafted IR/JoI pairs. Missing:

### B1. D-6 progressive update + break — *small*
- IR: `cycle{ delay; call(SetX, X+step); if(X>=max){break} }`.
- Test expression-as-arg evaluation against current world state.
- Verify cycle-with-break + cap clamp behavior.

### B2. D-8 read+delay+diff — *small*
- IR: `read(t1); delay(D); read(t2); if(abs(t2-t1)>=K, ...)`.
- Test variable persistence across `delay`, `abs` workaround (`if(diff<0){diff=b-a}`), conditional emission.
- Already partially covered by C01 #11/#13 dataset rows.

### B3. Edge wait at top-level (rule 1b) — *small*
- IR: `wait(edge:"rising", cond)` outside any cycle → JoI collapses to `wait until(C)`.
- Both sims should fire once (button-press one-shot pattern).

---

## C. Event synthesis improvements

### C0. Period-aware trigger placement — *small, REQUIRED for periodic categories*
- Currently event_synth.py uses hardcoded magic numbers:
  - `fire_ms = cursor + 1000` (1s after wait reached)
  - `prelude_ms = fire_ms - 200` (200ms before fire for transitions)
- This is the root cause of D-4 tick-aliasing: when JoI period >> 200ms (e.g., 60s),
  prelude lands inside a tick interval where JoI doesn't observe → IR/JoI traces diverge.
- Fix: snap fire_ms to next period-aligned tick boundary; place prelude one tick earlier:
  ```python
  def aligned_fire(cursor, period):
      if period == 0: return cursor + 1000
      return ((cursor // period) + 1) * period
  prelude_ms = fire_ms - period  # one full tick earlier so JoI observes prev=false
  ```
- Required before C13–C18 (periodic-heavy) and any large-period D-4 cases.

### C0a. Event-jump simulation (avoid full tick polling) — *small, big speedup*
- For periodic JoI scripts with small `period` (100ms) running over long virtual windows
  (weekend = 1.7M ticks), naive tick-by-tick simulation costs 10–30s per row.
- Optimization: when a tick produces no trace records AND no events drain, jump the clock
  directly to the next pending scenario event time (or next clock-based cond transition,
  e.g., next "SAT 00:00" for `clock.dayOfWeek == "SAT"`).
- Implementation:
  - World already has `_pending` list. Add `peek_next_event_time()`.
  - In JoI tick loop and IR wait poll, after each step check: if no progress + pending
    next event known, `advance_to(next_event.at_ms)` instead of `advance_by(period)`.
  - For clock-dep conds: precompute next-true-time analytically (cron-like).
- Reduces "weekend 100ms" case from 1.7M ticks to <100. Brings worst-case row from 10s to ~ms.
- Required only if real-time inline verification is needed; for §9 batch evaluation the
  naive cost is tolerable (≤5 min per 154 rows).

### C2. Multi-trigger cycles for whenever idiom — *small, depends on C0*
- Current synth places ONE rising edge per cycle wait.
- Cannot detect lowering bugs where `triggered` flag fails to reset (cycle stops re-arming after first fire).
- Fix: walk cycle body once to compute its duration (sum of `delay`s + nested wait gaps), then place
  N (=2-3) trigger events spaced by `body_duration + tick_padding`, so each iteration's wait
  re-arms after the previous body completes.
- Why "after body": during a body's `delay`, scenario events drain into world.state but no one
  observes them — `wait` is already past, `delay` doesn't poll. So a transition placed during
  the delay window is effectively lost. Triggers MUST land after `cursor + body_duration`.
- Body duration calculation (deterministic IR walk):
  ```python
  def body_duration(steps):
      total = 0
      for s in steps:
          if s["op"] == "delay": total += s["ms"]
          elif s["op"] == "wait" and s.get("edge") in ("rising","falling"):
              total += 1000  # transition gap
          elif s["op"] == "if":
              total += max(body_duration(s["then"]), body_duration(s.get("else",[])))
      return total
  ```

### C1. Branch coverage — *medium*
- Currently emits ONE happy-path scenario (every wait satisfies, every if takes `then`).
- For `if/else`, emit two scenarios — one for `then`, one for `else`. Compare both.
- For `cycle.until`, scenario where `until` triggers vs scenarios where loop bound (timeout) triggers.

### C2. Multi-trigger scenarios for `cycle{wait(rising)...}` — *small*
- Currently synth places one rising edge. For D-3 cycles we should optionally place 2-3 transitions to verify the `triggered` flag resets correctly.

### C3. Cron alignment — *small*
- For cron-anchored IR (`start_at(cron)`), virtual clock currently snaps to first cron fire. Verify multi-fire (Mon, Wed both within 7-day window) produces matching trace count.

---

## D0. IR-to-NL deterministic rendering (paper §5)

### D0a. Domain lexicon + pattern matching — *small, paper-critical*
- Current `ir_to_readable()` in `timeline_ir.py` produces template-y output:
  `"• [Door.DoorState == \"open\"]이(가) 참인 상태가 될 때까지 대기"`
- For user-confirmation step (paper §7), output must read like natural Korean.
- **Constraint: must remain 100% deterministic** — the paper's thesis is "no LLM in
  the verification path." LLM polishing reintroduces the unsoundness re-translation
  had in the prior pipeline.
- Approach:
  1. Service/attribute lexicon: `Door` → "문", `MotionSensor.Detected` → "움직임이 감지", etc.
  2. Cond pattern matchers: `X.DoorState == "open"` → "X이 열리", `X.Temperature >= V` → "X가 V도 이상이", etc.
  3. Idiom recognizer: detect cycle+wait(rising) → "~할 때마다", wait+cycle → "~되면 N마다", etc.
  4. Cron formatter: `0 12 * * SAT,SUN` → "주말 오후 12시"
- Target: 90%+ of C01-C07 cases readable without LLM polish; remaining 5-10% (compound
  conds, unknown services) fall back to current template.
- ~30-50 lexicon entries + ~20 patterns. Half-day work.

## D. Comparator robustness

### D1. Distinguish "real" mismatch from "sim limit" — *small*
- Current `unknown_op` class catches both unsupported ops AND runtime errors (NoneType, etc.). Split:
  - `unsupported_op` — explicit IR/JoI op not implemented
  - `runtime_error` — type/None error during eval
- Helps separate sim TODO items from genuine bugs in §9 numbers.

### D2. Diff visualization — *small*
- Comparator returns string-rendered diff. Add a structured diff (per-group, per-record) so the harness can summarize "X% of failures are at group 0, Y% at later groups, Z% are length-only".

---

## E. Pipeline integration

### E1. Non-LLM cache replay — *done* (current behavior with `--cache` default)

### E2. Run on more categories — *blocked on A* for full C08–C18
- C04 (n=3), C06 (data starved per priorities memo) — small, run as soon as IR-bucket completed.
- C08 (multi-button, n=41) — requires A1+A2 (any/all + multi-device).
- C09 (composed delayed actions) — should work with current code; not yet attempted.
- C10..C18 — periodic/cron heavy, mostly should work.

### E3. Pre-post-process IR/JoI capture — *medium*
- Memory note: `run_local.py` post-processing renames methods to `<svc>_<name>` form. Sim currently undoes this via canonical_key.
- Cleaner: have the pipeline emit both pre- and post-process JoI; sim consumes pre-process for direct comparison.

---

## F. Open semantic divergences (paper findings, NOT bugs)

### F1. D-4 tick aliasing — *documented*
- IR's wait satisfies on next 100ms poll; JoI's wait blocks until next `period` tick. With `period=60s`, JoI first emit can lag by up to 60s.
- Currently masked by using `period=1000` in test_e2e (within ±100ms tolerance).
- For §9 evaluation: keep large-period D-4 cases visible; report the lag as a lowering imprecision finding.

### F2. Selector multiplicity in trace — *design decision standing*
- Trace records `(method, args)` only; "who" stripped. Multi-device fanout invisible to comparator.
- Document explicitly in §6.2 that operational semantics is per-call-op, not per-device.

---

## G. Pipeline-side bugs surfaced (out of sim scope, but track for paper)

These are real pipeline issues found by the simulator. Listed here for §9 narrative; fix lives in the pipeline prompts / extractor, not in `simulators/`.

### G1. JoI lowering drops IR ops — *real bug*
- C01 #15 ("generate cat image and save"): IR has 2 calls, JoI has 1 (only save).
- C01 #18, #19: same pattern (cloud query + speak → only speak).
- Investigation: lowering prompt may be collapsing read+act sequences when there's no explicit `bind`.

### G2. IR extractor injects selector into args — *real bug*
- ~15 cases: IR `valve.Close` has `args=("['Kitchen', 'Valve']",)` — selector tag list serialized as a string arg.
- Lowering correctly emits `(#Kitchen #Valve).close()` with empty args.
- Likely the extractor's prompt is conflating selector grammar with argument grammar.

### G3. IR extractor misses literal args — *real bug*
- ~5 cases: IR `Speaker.Play` has `args=(None,)` while NL command says `Play "music.mp3"`.
- Extractor isn't pulling string literals out of the command into args.

---

## Priority suggestion

1. **C0** (period-aware trigger placement) — small but required before any cycle/period work.
2. **C2** (multi-trigger cycles) — depends on C0; verifies cycle re-arming.
3. **A1+A2** (any/all) — biggest unblock for C08+ scope; precondition for full §9.
4. **C1** (branch coverage) — strengthens claim ("we test BOTH branches").
5. **B1+B2** (D-6, D-8 idioms) — close out hand-crafted coverage.
6. **D1** (split unknown_op) — cleaner §9 numbers.
7. **E2** (C08–C18 once A and C0 are done).
8. **G1–G3** — separate pipeline workstream, not sim work but track.
