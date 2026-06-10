# IR Pattern: NONCYCLE

The IR has **no top-level `cycle`**. The script runs once and ends.

## Period rule
Default `period: 0` (script runs once and ends). The single exception is **D-10n** (sustained-cond `wait.for` one-shot, see below) which uses `period: 100` because polling is required to detect the sustain window.

## Patterns covered
- **D-1** one-shot action: `start_at(now) + call`.
- **D-2** one-shot wait: `wait(edge:"none", cond:C) + call`. Lower to `wait until(C)` then call.
- **D-7** cron-anchored: `start_at(cron) + ...` — same as D-1/D-2 but with `cron` field set.
- **D-8** read + delay + read + diff. Lower with the abs workaround:
  ```
  t1 = (#Sel).Attr
  delay(N UNIT)
  t2 = (#Sel).Attr
  diff = t2 - t1
  if (diff < 0) { diff = t1 - t2 }
  if (diff >= K) { Y }
  ```
- **B-1b** top-level `wait(edge:"rising", cond:C)` WITHOUT a cycle — collapse to **`wait until(C)`** (one-shot). **Do NOT use D-3** (the triggered idiom). D-3 requires a cycle; here there is none.
- **D-10n** top-level `wait(cond:C, for:"N UNIT")` (sustained-cond, one-shot, no cycle). Cannot use plain `wait until` + `delay` — the duration is a SUSTAIN window, not a delay. Override the bucket period to `100` and use a polling-counter + `break`:
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
  `<for_ticks>` = `for_ms / 100`, where `for_ms` = the duration in **milliseconds** (1 SEC = 1000 ms, 1 MIN = 60000 ms, 1 HOUR = 3600000 ms). **Compute it explicitly in `<Reasoning>`** — write the `for_ms` and the division — never copy a number from an example. Conversion table (memorize, do NOT reuse `"1 MIN"`'s 600 for other durations):
  | for | for_ms | for_ticks (÷100) |
  |---|---|---|
  | "5 SEC" | 5 000 | 50 |
  | "30 SEC" | 30 000 | 300 |
  | "1 MIN" | 60 000 | 600 |
  | "5 MIN" | 300 000 | 3000 |
  | "10 MIN" | 600 000 | 6000 |
  | "1 HOUR" | 3 600 000 | 36000 |

  So `"5 MIN"` → 3000 (NOT 300), `"10 MIN"` → 6000 (NOT 600). Set `period: 100` ONLY for this case; all other noncycle patterns keep `period: 0`.

## Script body
Walk the timeline in order. For each IR op, apply rule C from common. Emit each statement on its own line with `\n`.

## Examples

### Ex1 — trivial action
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
             {"op":"call","target":"Switch.On","args":{}}]}
```
[Precision Selectors] `(#SectorA #Light)`
<Reasoning>
One-shot action.
</Reasoning>
{"cron":"","period":0,"script":"(#SectorA #Light).On()"}

### Ex2 — if/elif chain
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
  {"op":"if","cond":"TempSensor.Temperature >= 30",
   "then":[{"op":"call","target":"AirConditioner.SetMode","args":{"Mode":"cool"}}],
   "else":[{"op":"if","cond":"TempSensor.Temperature < 20",
            "then":[{"op":"call","target":"AirConditioner.SetMode","args":{"Mode":"heat"}}],
            "else":[]}]}]}
```
[Precision Selectors] `(#TemperatureSensor)` / `(#AirConditioner)`
<Reasoning>
One-shot nested if-else.
</Reasoning>
{"cron":"","period":0,"script":"if ((#TemperatureSensor).Temperature >= 30) {\n    (#AirConditioner).SetMode(\"cool\")\n} else {\n    if ((#TemperatureSensor).Temperature < 20) {\n        (#AirConditioner).SetMode(\"heat\")\n    }\n}"}

### Ex3 — when one-shot wait (D-2)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"wait","cond":"Door.DoorState == \"open\"","edge":"none"},
 {"op":"call","target":"Switch.On","args":{}}]}
```
[Precision Selectors] `(#Door)` / `(#Light)`
<Reasoning>
One-shot wait then action.
</Reasoning>
{"cron":"","period":0,"script":"wait until((#Door).DoorState == \"open\")\n(#Light).On()"}

### Ex4 — top-level wait(rising) WITHOUT cycle (B-1b, button-press style)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"wait","cond":"MultiButton.Button1 == \"pushed\"","edge":"rising"},
 {"op":"call","target":"Switch.On","args":{}}]}
```
[Precision Selectors] `(#MultiButton)` / `(#Light)`
<Reasoning>
No cycle → one-shot. Collapse edge:"rising" to a level wait. NOT D-3.
</Reasoning>
{"cron":"","period":0,"script":"wait until((#MultiButton).Button1 == \"pushed\")\n(#Light).On()"}

### Ex5 — cron + branch (D-7)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"cron","cron":"0 9 * * *"},
 {"op":"if","cond":"MotionSensor.Motion == \"detected\"",
  "then":[{"op":"call","target":"Door.Open","args":{}}],
  "else":[{"op":"call","target":"Door.Close","args":{}}]}]}
```
[Precision Selectors] `(#MotionSensor)` / `(#Door)`
<Reasoning>
Cron + snapshot branch.
</Reasoning>
{"cron":"0 9 * * *","period":0,"script":"if ((#MotionSensor).Motion == \"detected\") {\n    (#Door).Open()\n} else {\n    (#Door).Close()\n}"}

### Ex6 — read + delay + read + diff (D-8)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"read","var":"t1","src":"TempSensor.Temperature"},
 {"op":"delay","duration":"10 MIN"},
 {"op":"read","var":"t2","src":"TempSensor.Temperature"},
 {"op":"if","cond":"abs($t2 - $t1) >= 10",
  "then":[{"op":"call","target":"Switch.On","args":{}}],
  "else":[]}]}
```
[Precision Selectors] `(#TemperatureSensor)` / `(#Light)`
<Reasoning>
Snapshot pair with abs workaround on the diff.
</Reasoning>
{"cron":"","period":0,"script":"t1 = (#TemperatureSensor).Temperature\ndelay(10 MIN)\nt2 = (#TemperatureSensor).Temperature\ndiff = t2 - t1\nif (diff < 0) {\n    diff = t1 - t2\n}\nif (diff >= 10) {\n    (#Light).On()\n}"}

### Ex7 — sensor → multi-selector Speaker (binding + fan-out)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"read","var":"temp","src":"TemperatureSensor.Temperature"},
 {"op":"call","target":"Speaker.Speak","args":{"Text":"The current temperature is $temp"}}]}
```
[Precision Selectors]
TemperatureSensor.Temperature: `(#TemperatureSensor)`
Speaker.Speak: `(#Speaker #LivingRoom)` / `(#Speaker #Kitchen)`
<Reasoning>
Bind sensor value; Speaker.Speak has 2 selectors → fan out to 2 calls with identical args.
</Reasoning>
{"cron":"","period":0,"script":"temp = (#TemperatureSensor).Temperature\n(#Speaker #LivingRoom).Speak(\"The current temperature is \" + temp)\n(#Speaker #Kitchen).Speak(\"The current temperature is \" + temp)"}

### Ex8 — function return chain (call + bind)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"call","target":"CloudServiceProvider.GenerateImage","args":{"Prompt":"cat"},"bind":"img"},
 {"op":"call","target":"CloudServiceProvider.SaveToFile","args":{"Data":"$img","FilePath":"cat.png"}}]}
```
[Precision Selectors] `(#CloudServiceProvider)`
<Reasoning>
Capture function return, feed into next call.
</Reasoning>
{"cron":"","period":0,"script":"img = (#CloudServiceProvider).GenerateImage(\"cat\")\n(#CloudServiceProvider).SaveToFile(img, \"cat.png\")"}

### Ex9 — sustained-cond one-shot (D-10n, period 100)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"wait","cond":"PresenceSensor.Presence == true","edge":"none","for":"10 MIN"},
 {"op":"call","target":"Speaker.Speak","args":{"Text":"환기해 주세요."}}]}
```
[Precision Selectors] `(any(#PresenceSensor))`, `(#Speaker)`
<Reasoning>
D-10n sustained-cond. for "10 MIN" → for_ms = 10 × 60000 = 600000 → for_ticks = 600000 / 100 = 6000. period = 100.
</Reasoning>
{"cron":"","period":100,"script":"hold_ticks := 0\nif (any(#PresenceSensor).Presence == true) {\n    hold_ticks = hold_ticks + 1\n    if (hold_ticks >= 6000) {\n        (#Speaker).Speak(\"환기해 주세요.\")\n        break\n    }\n} else {\n    hold_ticks = 0\n}"}
