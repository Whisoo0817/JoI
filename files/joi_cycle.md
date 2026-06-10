# IR Pattern: CYCLE

The IR timeline contains a top-level `{"op":"cycle",...}`. The hub re-runs the script every `period` ms; your job is to lower IR → script following the IR's idiom signals.

---

# Step 1 — Idiom selection + wrapper.period (apply IN ORDER, first match wins)

| # | Trigger (IR signal) | Idiom | Wrapper.period |
|---|---|---|---|
| 1 | `cycle.until != null` | D-9 (until window) | `parse_ms(cycle.period)` |
| 2 | body has `if{break}` step | D-6 (progressive update) | `parse_ms(cycle.period)` |
| 3 | body has `wait(...)` (`edge:"rising"` AND/OR `for:"<N>"`) | D-3 / D-10 (edge / sustained) | **100 (fixed)** |
| 4 | pre-cycle `wait(edge:"none"\|null)` at top level | D-4 (phase lifecycle) | `parse_ms(cycle.period)` |
| 5 | else | B-2 (simple periodic) | `parse_ms(cycle.period)` |

**Cadence consumption**: when wrapper.period = `parse_ms(cycle.period)`, the body's cadence `delay(N UNIT)` (whose N matches cycle.period) is consumed by the wrapper and does NOT appear in script.

**Iteration-internal sub-step delays** are KEPT in script: e.g. cycle.period = 1 MIN, body `delay(5 SEC)` between siren-on and switch-off — the 5 SEC has a different role (intra-iteration), distinguishable from cadence.

# Step 1.5 — `cycle.count` handling (orthogonal to idiom)

When the IR's `cycle` carries a `count` field (e.g. `count:"n"`), the cycle uses an iteration-index variable for alternation, rotation, or bounded-repeat patterns:

1. **Prepend** `<count> := 0` as the FIRST statement of the script (a single persistent init).
2. **Emit the idiom body** exactly as Step 3 dictates (the body references `<count>` in `if`/`until` expressions verbatim — no translation).
3. **Append** `<count> = <count> + 1` as the LAST statement of the script (advances the counter every tick).

`cycle.until` referencing `<count>` (e.g. `until:"n >= 10"`) is the D-9 idiom: emit `if (n >= 10) { break }` at the top of the body, same as any other `until` expression.

This handling is composable with every Step-1 idiom row — it adds two lines around the existing template.

---

# Step 2 — Cron field

From `joi_common` Rule A: `start_at(anchor:"cron", cron:X)` → `cron: X`; otherwise `cron: ""`.

---

# Step 3 — Apply the idiom template

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
else {
    Y
}
```
**Single `if/else` is mandatory** (NOT two separate `if (phase == 0)` and `if (phase == 1)` blocks). With two separate ifs, the first tick falls through into the second block after setting `phase = 1`, firing `Y` twice in the same tick. `if/else` is mutually exclusive within one tick — first tick takes the if branch, every subsequent tick takes the else branch.

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
For a time-of-day window end, `φ` reads the Clock service, NOT `clock.time`: a whole-hour end H → `(#Clock).Hour >= H`; with minutes H:M → `(#Clock).Hour > H or ((#Clock).Hour == H and (#Clock).Minute >= M)`. (The IR `until` carries `Clock.Hour …`; render it `(#Clock).Hour …`.)

## D-10 — sustained-cond polling (`wait.for`)
Detection: a `wait` op carries a `for` field (e.g. `for:"30 SEC"`). The cond must remain CONTINUOUSLY true for that duration; a mid-window flip resets the timer.

**Tick math**: `for_ticks = for_ms / wrapper.period_ms`. The wrapper period defaults to 100ms when the IR does not name a polling cadence; if the IR's `cycle.period` is something else (e.g. `"1 SEC"`), use that value as the wrapper period and recompute. Worked examples assuming the default 100ms tick:

| `for` | duration in ms | `for_ticks` (period=100) |
|---|---|---|
| `"5 SEC"` | 5000 | **50** |
| `"30 SEC"` | 30000 | **300** |
| `"1 MIN"` | 60000 | **600** |
| `"10 MIN"` | 600000 | **6000** |

If the IR specifies `cycle.period="1 SEC"`, then `for:"30 SEC"` → `30000 / 1000` = **30** ticks. The formula is constant; the period is the only variable. Never multiply duration by 1000 — `for_ms` is already in ms.

### Cycle-wrapped (re-arming): `cycle{ wait(C, rising, for:N); Y }`
Emits `Y` each time `C` becomes true AND stays true for the full window.
```
hold_ticks := 0
fired := false
if (C) {
    if (fired == false) {
        hold_ticks = hold_ticks + 1
        if (hold_ticks >= <for_ticks>) {
            Y
            fired = true
        }
    }
} else {
    hold_ticks = 0
    fired = false
}
```
- `hold_ticks` resets to 0 on cond-flip — this is the contract that distinguishes `wait.for` from `delay`.
- `fired` ensures one emit per sustained episode; resets when cond flips false → re-arms.

### One-shot: `wait(C, none, for:N); Y` (top-level, no enclosing cycle)
Use `break` to exit polling after first emit.
```
hold_ticks := 0
if (C) {
    hold_ticks = hold_ticks + 1
    if (hold_ticks >= <for_ticks>) {
        Y
        break
    }
} else {
    hold_ticks = 0
}
```

❌ **NEVER** lower `wait.for` as `wait until(C); delay(<for>); if(C){Y}` — endpoint-check only, fails the flap scenario. Always use the polling-counter template.

## B-2 — simple periodic (default)
Cycle without edge/until/break/pre-wait/multi-delay markers. Just emit body's calls/reads/ifs as-is, after the wrapper.period has consumed the cadence delay. ❌ Do NOT add `if{break}`, max-clamps, or safety guards not present in IR.

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
   {"op":"call","target":"Switch.On","args":{}}]}]}
```
[Precision Selectors] `(#Door)` / `(#Light)`
<Reasoning>
D-4: pre-cycle wait(none) + cycle. Phase 0→1 transition. cycle.period 3 MIN → wrapper.period = 180000.
</Reasoning>
{"cron":"","period":180000,"script":"phase := 0\nif (phase == 0) {\n    wait until((#Door).DoorState == \"open\")\n    phase = 1\n    (#Light).On()\n}\nelse {\n    (#Light).On()\n}"}

### Ex5 — alternation via `cycle.count` (Step 1.5)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":null,"period":"3 SEC","count":"n","body":[
   {"op":"if","cond":"n % 2 == 0",
    "then":[{"op":"call","target":"WindowCovering.UpOrOpen","args":{}}],
    "else":[{"op":"call","target":"WindowCovering.DownOrClose","args":{}}]}]}]}
```
[Precision Selectors] `(#WindowCovering)`
<Reasoning>
B-2 base idiom (no until/edge/break). cycle.count present → prepend `n := 0`, append `n = n + 1`. Body is a single `if` that picks the call by `n % 2`. cycle.period = 3 SEC → wrapper.period = 3000.
</Reasoning>
{"cron":"","period":3000,"script":"n := 0\nif (n % 2 == 0) {\n    (#WindowCovering).UpOrOpen()\n} else {\n    (#WindowCovering).DownOrClose()\n}\nn = n + 1"}

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
 {"op":"cycle","until":"Clock.Hour >= 15","period":"5 MIN","body":[
   {"op":"call","target":"TempSensor.Temperature","bind":"t"},
   {"op":"call","target":"Speaker.Speak","args":{"Text":"Current $t degrees"}}]}]}
```
[Precision Selectors] `(#TempSensor)` / `(#Speaker)`
<Reasoning>
D-9: cycle.until set (time-of-day end → (#Clock).Hour, NOT clock.time), no alternation. Break-guard then body. wrapper.period from cycle.period.
</Reasoning>
{"cron":"","period":300000,"script":"if ((#Clock).Hour >= 15) {\n    break\n}\nt = (#TempSensor).Temperature\n(#Speaker).Speak(\"Current \" + t + \" degrees\")"}

### Ex8 — bounded cycle via `cycle.count` in `until` (D-9 + Step 1.5)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"cycle","until":"n >= 5","period":"20 MIN","count":"n","body":[
   {"op":"call","target":"Speaker.Speak","args":{"Text":"meeting reminder"}}]}]}
```
[Precision Selectors] `(#Speaker)`
<Reasoning>
D-9 idiom (cycle.until set) with cycle.count: prepend `n := 0`, append `n = n + 1`. Until references `n` → break-guard at top of body. cycle.period = 20 MIN → wrapper.period = 1200000.
</Reasoning>
{"cron":"","period":1200000,"script":"n := 0\nif (n >= 5) {\n    break\n}\n(#Speaker).Speak(\"meeting reminder\")\nn = n + 1"}

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
