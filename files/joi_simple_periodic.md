# IR Pattern: SIMPLE_PERIODIC (Rule B-2)

The IR is `cycle{ call(s) ... ; ONE trailing delay }` with **NO `wait`, NO `if`, NO `break`** inside the cycle, and `cycle.until` is null.

## Period rule
**`period = <trailing delay ms>`**. The trailing delay is consumed by the `period` field and **does NOT appear in the script body**.

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
 {"op":"cycle","until":null,"body":[
   {"op":"call","target":"Speaker.SetVolume","args":{"Volume":"Speaker.Volume + 10"}},
   {"op":"delay","ms":3600000}]}]}
```
[Precision Selectors] `(#Speaker)`
<Reasoning>
Cycle with one call + trailing delay; period = delay; ONE-line script, no D-6 max-clamp.
</Reasoning>
{"cron":"","period":3600000,"script":"(#Speaker).SetVolume((#Speaker).Volume + 10)"}

### Ex2 — every-N with literal-arg call
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"body":[
   {"op":"call","target":"Camera.Capture","args":{}},
   {"op":"delay","ms":300000}]}]}
```
[Precision Selectors] `(#Camera)`
<Reasoning>
Cycle with one call + trailing delay; period = 300000; emit single call.
</Reasoning>
{"cron":"","period":300000,"script":"(#Camera).Capture()"}

### Ex3 — multiple calls + trailing delay
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"cron","cron":"0 8 * * *"},
 {"op":"cycle","until":null,"body":[
   {"op":"call","target":"Light.On","args":{}},
   {"op":"call","target":"Speaker.Speak","args":{"Text":"Good morning"}},
   {"op":"delay","ms":86400000}]}]}
```
[Precision Selectors] `(#Light)` / `(#Speaker)`
<Reasoning>
Cron-anchored cycle with two calls then trailing daily delay; period = delay; emit calls in order.
</Reasoning>
{"cron":"0 8 * * *","period":86400000,"script":"(#Light).On()\n(#Speaker).Speak(\"Good morning\")"}
