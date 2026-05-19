# IR Pattern: CYCLE

The IR timeline contains a top-level `{"op":"cycle",...}`. The hub re-runs the script every `period` ms; your job is to lower IR → script following the IR's idiom signals.

---

# Step 1 — Pick idiom from IR signals (apply IN ORDER, first match wins)

| # | Trigger (IR signal) | Idiom | Wrapper.period |
|---|---|---|---|
| 1 | `cycle.until != null` AND body has ≥2 `delay` ops interleaving calls | D-9+D-5 hybrid (until + alternation) | each delay (or `cycle.period`) |
| 2 | `cycle.until != null` | D-9 (until window) | `cycle.period` (preferred) or trailing/cadence delay |
| 3 | body has `if{break}` step | D-6 (progressive update) | `cycle.period` or cadence delay |
| 4 | body has `wait(edge:"rising")` | D-3 (triggered whenever) | **100 (fixed, 10Hz polling)** |
| 5 | pre-cycle `wait(edge:"none"\|null)` at top level | D-4 (phase lifecycle) | `cycle.period` or cadence delay |
| 6 | body has ≥2 `delay` ops interleaving calls | D-5 (alternation) | each delay (or `cycle.period`) |
| 7 | else | B-2 (simple periodic) | `cycle.period` or cadence delay |

---

# Step 2 — Wrapper.period rule

`cycle.period` is always present in IR. Apply per Step-1 idiom:

- **D-3** (edge cycle): wrapper.period = `100` (fixed; cycle.period is `"100 MSEC"` by convention, ignore the value).
- **D-5 / D-9+D-5** (alternation): wrapper.period = `parse_duration_to_ms(cycle.period)`. The body's inter-call `delay`s are consumed by the state-toggle template; they do NOT appear in script.
- **All others** (B-2 / D-4 / D-6 / D-9): wrapper.period = `parse_duration_to_ms(cycle.period)`. Body emits as-is.

❌ Do NOT emit `delay(N UNIT)` in the script when its duration is `cycle.period` (cadence is consumed).
✅ Iteration-internal sub-step delays (e.g. cycle.period = 1 MIN, body has `delay(5 SEC)` between siren-on and switch-off) ARE kept in script — distinguish by role.

---

# Step 3 — Cron field

From `joi_common` Rule A: `start_at(anchor:"cron", cron:X)` → `cron: X`; otherwise `cron: ""`.

---

# Step 4 — Apply the idiom template

## D-3 — rising-edge `triggered` flag (whenever idiom)
Wraps `wait(rising, cond:C); Y` in cycle. Emits `Y` exactly once per `false→true` transition of `C`.
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
**"Stops" / "no longer holds"** = negated cond with rising edge (e.g. `cond:"Motion == false"`). Same template; do NOT special-case as falling.

## D-4 — phase lifecycle (`when X, thereafter every N`)
Pre-cycle `wait(none, cond:X)` + cycle `{Y; ...}`.
```
phase := 0
if (phase == 0) {
    wait until(X)
    phase = 1
    Y
}
if (phase == 1) {
    Y
}
```

## D-5 — alternation (every N, A then B)
Cycle body has 2+ delays between alternating calls.
```
state := "A"
if (state == "A") {
    A
    state = "B"
} else {
    B
    state = "A"
}
```
For 3-way (A/B/C), extend the toggle: `state := "A" → "B" → "C" → "A"`.

## D-6 — progressive update with break
Cycle body has explicit `if{break}` step.
```
new_val = (#Sel).Attr + step
if (new_val >= max) {
    (#Sel).Set(max)
    break
} else {
    (#Sel).Set(new_val)
}
```
⚠️ D-6 ONLY when IR has `if{...break}`. If IR is plain `cycle{call; delay}` with no break — that is **B-2**, do NOT invent a max-clamp.

## D-9 — cycle.until window
`cycle.until != null`. Break-guard at top of script body.
```
if (φ) { break }
... body without the cadence delay ...
```

## D-9 + D-5 hybrid — `cycle.until` WITH alternation
Detection: `cycle.until != null` AND body has ≥2 delays.
```
if (φ) { break }
state := "A"
if (state == "A") { A; state = "B" }
else { B; state = "A" }
```

## B-2 — simple periodic (default)
Cycle without edge/until/break/pre-wait/multi-delay markers. Just emit body's calls/reads/ifs as-is, after the wrapper.period has consumed the cadence delay.

---

# Anti-pattern reminders (consolidated)

- ❌ Do NOT add `if{break}` to a B-2 cycle — only D-6 has it (because IR has it).
- ❌ Do NOT add max-clamp / safety guards / range checks not present in IR.
- ❌ Do NOT delete IR ops — every `call`/`read`/`if` must appear (cadence `delay` is the only consumable).
- ❌ Do NOT use `wait until(...)` inside a D-3 cycle body — the `wait(rising)` is consumed by the triggered template, never emitted as `wait until`.
- ❌ Do NOT inject `all(...)` / `any(...)` around precision selectors (see `joi_common` Strict Selector Rule).
- ❌ Do NOT keep cadence `delay(N UNIT)` in script when N became wrapper.period.

---

# Examples (1 per idiom)

### Ex1 — B-2 simple periodic (canonical, with `cycle.period`)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"5 MIN","body":[
   {"op":"call","target":"Camera.Capture","args":{}}]}]}
```
[Precision Selectors] `(#Camera)`
<Reasoning>
B-2: cycle without edge/until/break/pre-wait. cycle.period = 5 MIN → wrapper.period = 300000; emit body as-is.
</Reasoning>
{"cron":"","period":300000,"script":"(#Camera).Capture()"}

### Ex2 — B-2 with conditional body
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"10 MIN","body":[
   {"op":"if","cond":"TemperatureSensor.Temperature >= 30",
    "then":[{"op":"call","target":"AirConditioner.SetMode","args":{"Mode":"cool"}}],"else":[]}]}]}
```
[Precision Selectors] `(#TemperatureSensor)` / `(#AirConditioner)`
<Reasoning>
B-2: cycle.period = 10 MIN → wrapper.period = 600000; emit the `if` as body.
</Reasoning>
{"cron":"","period":600000,"script":"if ((#TemperatureSensor).Temperature >= 30) {\n    (#AirConditioner).SetMode(\"cool\")\n}"}

### Ex3 — D-3 rising-edge whenever with MULTI-STEP Y (call + delay + call)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"100 MSEC","body":[
   {"op":"wait","cond":"MotionSensor.Motion == true","edge":"rising"},
   {"op":"call","target":"Light.MoveToBrightness","args":{"Brightness":100,"Rate":0}},
   {"op":"delay","duration":"3 SEC"},
   {"op":"call","target":"Light.MoveToBrightness","args":{"Brightness":0,"Rate":0}}]}]}
```
[Precision Selectors] `(#MotionSensor #Entrance)` / `(#Light #Entrance)`
<Reasoning>
D-3 with multi-step Y: ALL body ops AFTER `wait(rising)` (call, delay, call) go INSIDE the inner `if (triggered == false) { ... }` block in order, then `triggered = true` at the end. NEVER place any Y op outside the triggered block.
</Reasoning>
{"cron":"","period":100,"script":"triggered := false\nif ((#MotionSensor #Entrance).Motion == true) {\n    if (triggered == false) {\n        (#Light #Entrance).MoveToBrightness(100, 0)\n        delay(3 SEC)\n        (#Light #Entrance).MoveToBrightness(0, 0)\n        triggered = true\n    }\n} else {\n    triggered = false\n}"}

### Ex4 — D-4 phase lifecycle
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"wait","cond":"Door.DoorState == \"open\"","edge":"none"},
 {"op":"cycle","until":null,"period":"3 MIN","body":[
   {"op":"call","target":"Light.On","args":{}}]}]}
```
[Precision Selectors] `(#Door)` / `(#Light)`
<Reasoning>
D-4: pre-cycle wait(none) + cycle. Phase 0→1 transition. cycle.period 3 MIN → wrapper.period = 180000.
</Reasoning>
{"cron":"","period":180000,"script":"phase := 0\nif (phase == 0) {\n    wait until((#Door).DoorState == \"open\")\n    phase = 1\n    (#Light).On()\n}\nif (phase == 1) {\n    (#Light).On()\n}"}

### Ex5 — D-5 alternation
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"10 SEC","body":[
   {"op":"call","target":"Light.MoveToColor","args":{"X":0.167,"Y":0.040,"TransitionTime":0.0}},
   {"op":"delay","duration":"10 SEC"},
   {"op":"call","target":"Light.MoveToColor","args":{"X":0.675,"Y":0.322,"TransitionTime":0.0}},
   {"op":"delay","duration":"10 SEC"}]}]}
```
[Precision Selectors] `(#Light)`
<Reasoning>
D-5: 2 inter-call delays interleaving. cycle.period = 10 SEC matches each delay → wrapper.period = 10000. State toggle; both body delays consumed.
</Reasoning>
{"cron":"","period":10000,"script":"color := \"red\"\nif (color == \"red\") {\n    (#Light).MoveToColor(0.167, 0.040, 0.0)\n    color = \"blue\"\n} else {\n    (#Light).MoveToColor(0.675, 0.322, 0.0)\n    color = \"red\"\n}"}

### Ex6 — D-6 progressive update + break
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"10 SEC","body":[
   {"op":"call","target":"Speaker.SetVolume","args":{"Value":"Speaker.Volume + 5"}},
   {"op":"if","cond":"Speaker.Volume >= 100",
    "then":[{"op":"break"}],"else":[]}]}]}
```
[Precision Selectors] `(#Speaker)`
<Reasoning>
D-6: body has if{break}. Fold +step + ceiling + break into one branch. cycle.period 10 SEC → 10000.
</Reasoning>
{"cron":"","period":10000,"script":"new_vol = (#Speaker).Volume + 5\nif (new_vol >= 100) {\n    (#Speaker).SetVolume(100)\n    break\n} else {\n    (#Speaker).SetVolume(new_vol)\n}"}

### Ex7 — D-9 cycle.until window (cron + multi-step body)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":"clock.time >= 1500","period":"5 MIN","body":[
   {"op":"call","target":"TempSensor.Temperature","bind":"t"},
   {"op":"call","target":"Speaker.Speak","args":{"Text":"Current $t degrees"}}]}]}
```
[Precision Selectors] `(#TempSensor)` / `(#Speaker)`
<Reasoning>
D-9: cycle.until set, no alternation (body has no delays). Break-guard then body. wrapper.period from cycle.period.
</Reasoning>
{"cron":"","period":300000,"script":"if (clock.time >= 1500) {\n    break\n}\nt = (#TempSensor).Temperature\n(#Speaker).Speak(\"Current \" + t + \" degrees\")"}

### Ex8 — D-9 + D-5 hybrid (cycle.until WITH alternation)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"cron","cron":"0 13 * * *"},
 {"op":"cycle","until":"clock.time >= 1500","period":"5 MIN","body":[
   {"op":"call","target":"Valve.Open","args":{}},
   {"op":"delay","duration":"5 MIN"},
   {"op":"call","target":"Valve.Close","args":{}},
   {"op":"delay","duration":"5 MIN"}]}]}
```
[Precision Selectors] `(#Valve)`
<Reasoning>
D-9+D-5: cycle.until + 2 inter-call delays. cycle.period = 5 MIN → wrapper.period = 300000. Break-guard then state toggle; both body delays consumed.
</Reasoning>
{"cron":"0 13 * * *","period":300000,"script":"if (clock.time >= 1500) {\n    break\n}\nstate := \"open\"\nif (state == \"open\") {\n    (#Valve).Open()\n    state = \"closed\"\n} else {\n    (#Valve).Close()\n    state = \"open\"\n}"}

### Ex9 — iteration-internal sub-step delay (NOT cadence)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"1 MIN","body":[
   {"op":"call","target":"Siren.SetSirenMode","args":{"Mode":"emergency"}},
   {"op":"delay","duration":"5 SEC"},
   {"op":"call","target":"Switch.Off","args":{}}]}]}
```
[Precision Selectors] `(#Siren)` / `(#Siren #Switch)`
<Reasoning>
B-2 with iteration-internal sub-step. cycle.period 1 MIN = cadence → wrapper.period 60000. The 5 SEC delay is iteration-internal (siren on → wait → off), NOT cadence — KEEP in script.
</Reasoning>
{"cron":"","period":60000,"script":"(#Siren).SetSirenMode(\"emergency\")\ndelay(5 SEC)\n(#Siren #Switch).Off()"}
