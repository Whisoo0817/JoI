# IR Pattern: EDGE_CYCLE (D-3)

The IR is `cycle{ wait(edge:"rising", cond:C); Y }` — a `whenever`-style trigger. The cycle wraps a rising-edge wait followed by the action.

## Period rule
**`period: 100`** (10 Hz polling — fine enough to catch fast transitions).

## D-3 idiom (rising-edge `triggered` flag)
```
triggered := false
if (C) {
    if (triggered == false) {
        Y
        triggered = true
    }
} else {
    triggered = false
}
```

This emits `Y` exactly once per false→true transition of `C`. The `:=` initializer persists across periodic ticks; the `=` updates it each tick.

## "Stops" / "no longer holds" cases
These are still rising-edge with a **negated cond** (e.g. `cond:"Motion == false"`). Same template — do NOT special-case as falling.

## Multi-statement Y
If `Y` is multiple ops in the IR (e.g. two calls), emit them one per line inside the inner `if` block, indented 8 spaces.

## ⚠️ Cycle is REQUIRED
If the IR has `wait(edge:"rising")` but NO surrounding cycle, this is a **one-shot** edge wait — it belongs to the NONCYCLE bucket and lowers to `wait until(C)` (B-1b). If you somehow get such an IR here, do not invent a triggered idiom.

## Examples

### Ex1 — whenever rising (multi-tag bare both sides)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"body":[
   {"op":"wait","cond":"Door.DoorState == \"open\"","edge":"rising"},
   {"op":"call","target":"Light.MoveToBrightness","args":{"Brightness":100,"Rate":0}}]}]}
```
[Precision Selectors] `(#Door #Bedroom)` / `(#Light #Bedroom)`
<Reasoning>
Rising-edge whenever idiom (D-3) with triggered flag; period 100. Both selectors are multi-tag bare — keep them bare in cond AND in call.
</Reasoning>
{"cron":"","period":100,"script":"triggered := false\nif ((#Door #Bedroom).DoorState == \"open\") {\n    if (triggered == false) {\n        (#Light #Bedroom).MoveToBrightness(100, 0)\n        triggered = true\n    }\n} else {\n    triggered = false\n}"}

### Ex2 — whenever … stops (negated cond, still rising) + MULTI-TAG bare selector
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"body":[
   {"op":"wait","cond":"MotionSensor.Motion == false","edge":"rising"},
   {"op":"call","target":"Light.Off","args":{}}]}]}
```
[Precision Selectors] `(#MotionSensor #Entrance)` / `(#Light #Entrance)`
<Reasoning>
"Stops" = negated cond with rising edge; same D-3 template. Multi-tag bare precision `(#Light #Entrance)` stays bare — NOT `all(#Light #Entrance)`.
</Reasoning>
{"cron":"","period":100,"script":"triggered := false\nif ((#MotionSensor #Entrance).Motion == false) {\n    if (triggered == false) {\n        (#Light #Entrance).Off()\n        triggered = true\n    }\n} else {\n    triggered = false\n}"}

### Ex3 — multi-step Y inside whenever
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"body":[
   {"op":"wait","cond":"RainSensor.Rain == true","edge":"rising"},
   {"op":"call","target":"Window.DownOrClose","args":{}},
   {"op":"call","target":"Speaker.Speak","args":{"Text":"Closing windows due to rain"}}]}]}
```
[Precision Selectors] `(#RainSensor)` / `all(#Window)` / `(#Speaker)`
<Reasoning>
Rising-edge whenever with two-step Y; both calls go inside the inner `if (triggered == false)` block.
</Reasoning>
{"cron":"","period":100,"script":"triggered := false\nif ((#RainSensor).Rain == true) {\n    if (triggered == false) {\n        all(#Window).DownOrClose()\n        (#Speaker).Speak(\"Closing windows due to rain\")\n        triggered = true\n    }\n} else {\n    triggered = false\n}"}
