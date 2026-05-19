# IR Pattern: SIMPLE_PERIODIC (Rule B-2)

The IR is a `cycle` whose cadence is expressed by `cycle.period` (canonical) — or, in legacy form, by a single body `delay` step — with **NO `wait`, NO edge, NO `break`** inside the cycle, and `cycle.until` is null. The body may contain `call`/`read`/`if` ops; what makes this bucket is the absence of edge/until/break and the cycle.period (or single cadence delay) carrying the loop's period.

## Period rule
**Priority 1 — `cycle.period` precedence (HARD, the canonical post-2026-05-18 shape)**: if the IR's `cycle` op has a `period` field (e.g. `"5 MIN"`), wrapper.period = `parse_duration_to_ms(cycle.period)` (e.g. `300000`). The body has NO cadence delay; the hub pads between iterations. Emit body exactly.

**Priority 2 — legacy fallback (extractor lagging)**: when `cycle.period` is absent and the body contains a cadence `delay` step, wrapper.period = `parse_duration_to_ms(delay.duration)`. Then **REMOVE that delay step from the script body**, regardless of position (head, middle, or tail). The hub pads between iterations.

❌ Do NOT keep `delay(N UNIT)` in the script when its duration is also set as `wrapper.period` — this double-counts (hub re-runs every N AND script waits N → 2N effective cadence).

## Script body
Emit the cycle body's calls (and any non-cadence steps) in order, exactly as the IR states. **One statement per line**, no extra control flow.

## ⚠️ NOT D-6
This bucket is the **simple repeating action**. It is **NOT** the progressive-update-with-break idiom (D-6).
- D-6 requires an explicit `if{break}` step in the IR. If the IR has none — you are HERE.
- Do NOT add `if (val >= max) { ... break }` — that is hallucination.
- Do NOT clamp values, add safety guards, or "improve" the loop.

If the IR's call uses an expression argument like `Speaker.Volume + 10`, just pass that expression through verbatim — `(#Speaker).SetVolume((#Speaker).Volume + 10)`. No max check.

## Examples

### Ex1 — every-N action with expression argument
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"1 HOUR","body":[
   {"op":"call","target":"Speaker.SetVolume","args":{"Volume":"Speaker.Volume + 10"}}]}]}
```
[Precision Selectors] `(#Speaker)`
<Reasoning>
cycle.period = 1 HOUR → wrapper.period = 3600000; emit body as-is (no cadence delay to consume); no D-6 max-clamp.
</Reasoning>
{"cron":"","period":3600000,"script":"(#Speaker).SetVolume((#Speaker).Volume + 10)"}

### Ex2 — every-N with literal-arg call
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"5 MIN","body":[
   {"op":"call","target":"Camera.Capture","args":{}}]}]}
```
[Precision Selectors] `(#Camera)`
<Reasoning>
cycle.period = 5 MIN → wrapper.period = 300000; emit single call.
</Reasoning>
{"cron":"","period":300000,"script":"(#Camera).Capture()"}

### Ex3 — multiple calls in one iteration
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"cron","cron":"0 8 * * *"},
 {"op":"cycle","until":null,"period":"24 HOUR","body":[
   {"op":"call","target":"Light.On","args":{}},
   {"op":"call","target":"Speaker.Speak","args":{"Text":"Good morning"}}]}]}
```
[Precision Selectors] `(#Light)` / `(#Speaker)`
<Reasoning>
Cron-anchored cycle; cycle.period = 24 HOUR → wrapper.period = 86400000; emit both calls in order.
</Reasoning>
{"cron":"0 8 * * *","period":86400000,"script":"(#Light).On()\n(#Speaker).Speak(\"Good morning\")"}

