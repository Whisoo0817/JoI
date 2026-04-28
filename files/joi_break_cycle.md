# IR Pattern: BREAK_CYCLE (D-6 progressive, D-9 until)

A cycle that contains a **break-out condition**, either:
- An explicit `if{break}` step inside the cycle body (D-6), OR
- A non-null `cycle.until` field (D-9).

## D-6. Progressive update + break
**IR shape**: `cycle{ delay(N); call(update); if(maxed){break} }` (or any cycle whose body contains an explicit `if{break}` step).

**Period rule**: `period = N` (the cadence delay).

**Idiom**:
```
new_val = (#Sel).Attr + step
if (new_val >= max) {
    (#Sel).SetAttr(max)
    break
} else {
    (#Sel).SetAttr(new_val)
}
```

The IR carries the break condition explicitly. Fold the increment + ceiling check into one branch with `break` in the saturated case.

⚠️ **D-6 is ONLY appropriate when the IR has `if{...{break}}` inside the cycle.** If the IR is a plain `cycle{ call; delay }` with no `if`/`break`, that is **NOT** D-6 — it's the SIMPLE_PERIODIC bucket. Do NOT invent a max-clamp guard out of thin air.

## D-9. Cycle with `until` (duration window)
**IR shape**: `cycle(until=φ){ body; delay(N) }` — `cycle.until` is non-null.

**Period rule**: `period = N` (the cycle's trailing delay).

**Idiom**: insert a break-guard at the **start** of the script body, then the body without the trailing delay.
```
if (φ) { break }
... body without trailing delay ...
```

This means each tick first checks the until-condition; if satisfied, exit. Otherwise run the body. The trailing delay is consumed by `period`.

## D-9 + D-5. cycle.until WITH alternation (hybrid)
**IR shape**: `cycle(until=φ){ A; delay(N); B; delay(N) }` — non-null `cycle.until` AND **two or more delays** inside the body. This is D-9 (duration window) layered on D-5 (alternation): each tick the script runs ONE of the two actions, alternating.

**⚠️ Detection rule**: if the cycle body has **≥ 2 `delay` ops**, you are in the hybrid case — you MUST emit a state toggle. Do NOT collapse to "remove all delays + back-to-back calls" (that would fire both A and B every tick — wrong).

**Period rule**: `period = N` (each delay equals the period; both delays are consumed).

**Idiom**: break-guard FIRST, then a state toggle that fires A on one tick and B on the next.
```
if (φ) { break }
state := "A"
if (state == "A") {
    A
    state = "B"
} else {
    B
    state = "A"
}
```

For 3-way (A; delay; B; delay; C; delay) extend the toggle: `state := "A" → "B" → "C" → "A"`.

## Examples

### Ex1 — D-6 progressive update with max ceiling
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"body":[
   {"op":"delay","ms":10000},
   {"op":"call","target":"Speaker.SetVolume","args":{"Value":"Speaker.Volume + 5"}},
   {"op":"if","cond":"Speaker.Volume >= 100",
    "then":[{"op":"break"}],"else":[]}]}]}
```
[Precision Selectors] `(#Speaker)`
<Reasoning>
Progressive update with explicit if{break}; fold +step + ceiling check + break into one branch.
</Reasoning>
{"cron":"","period":10000,"script":"new_vol = (#Speaker).Volume + 5\nif (new_vol >= 100) {\n    (#Speaker).SetVolume(100)\n    break\n} else {\n    (#Speaker).SetVolume(new_vol)\n}"}

### Ex2 — D-9 cycle.until duration window (from 2 PM to 6 PM, every hour)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"cron","cron":"0 14 * * *"},
 {"op":"cycle","until":"clock.time >= 1800","body":[
   {"op":"call","target":"Light.Toggle","args":{}},
   {"op":"delay","ms":3600000}]}]}
```
[Precision Selectors] `(#Light)`
<Reasoning>
cycle.until inserts an early break-guard; trailing delay becomes period; cron passes through.
</Reasoning>
{"cron":"0 14 * * *","period":3600000,"script":"if (clock.time >= 1800) {\n    break\n}\n(#Light).Toggle()"}

### Ex3 — D-9 with multi-step body
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":"clock.time >= 1500","body":[
   {"op":"call","target":"TempSensor.Temperature","bind":"t"},
   {"op":"call","target":"Speaker.Speak","args":{"Text":"Current $t degrees"}},
   {"op":"delay","ms":300000}]}]}
```
[Precision Selectors] `(#TempSensor)` / `(#Speaker)`
<Reasoning>
cycle.until with multi-step body; emit break-guard, then the body without the trailing delay.
</Reasoning>
{"cron":"","period":300000,"script":"if (clock.time >= 1500) {\n    break\n}\nt = (#TempSensor).Temperature\n(#Speaker).Speak(\"Current \" + t + \" degrees\")"}

### Ex4 — D-9 + D-5 hybrid (cycle.until WITH alternation)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"cron","cron":"0 13 * * *"},
 {"op":"cycle","until":"clock.time >= 1500","body":[
   {"op":"call","target":"Valve.Open","args":{}},
   {"op":"delay","ms":300000},
   {"op":"call","target":"Valve.Close","args":{}},
   {"op":"delay","ms":300000}]}]}
```
[Precision Selectors] `(#Valve)`
<Reasoning>
cycle.until + 2 delays in body → hybrid: break-guard + state toggle. Each tick fires ONE of Open/Close, alternating; period = 5 min.
</Reasoning>
{"cron":"0 13 * * *","period":300000,"script":"if (clock.time >= 1500) {\n    break\n}\nstate := \"open\"\nif (state == \"open\") {\n    (#Valve).Open()\n    state = \"closed\"\n} else {\n    (#Valve).Close()\n    state = \"open\"\n}"}
