# IR Pattern: NONCYCLE

The IR has **no top-level `cycle`**. The script runs once and ends.

## Period rule
**ALWAYS `period: 0`** for this bucket.

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

## Script body
Walk the timeline in order. For each IR op, apply rule C from common. Emit each statement on its own line with `\n`.

## Examples

### Ex1 — trivial action
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
             {"op":"call","target":"Light.On","args":{}}]}
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
 {"op":"call","target":"Light.On","args":{}}]}
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
 {"op":"call","target":"Light.On","args":{}}]}
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
 {"op":"delay","ms":600000},
 {"op":"read","var":"t2","src":"TempSensor.Temperature"},
 {"op":"if","cond":"abs($t2 - $t1) >= 10",
  "then":[{"op":"call","target":"Light.On","args":{}}],
  "else":[]}]}
```
[Precision Selectors] `(#TemperatureSensor)` / `(#Light)`
<Reasoning>
Snapshot pair with abs workaround on the diff.
</Reasoning>
{"cron":"","period":0,"script":"t1 = (#TemperatureSensor).Temperature\ndelay(10 MIN)\nt2 = (#TemperatureSensor).Temperature\ndiff = t2 - t1\nif (diff < 0) {\n    diff = t1 - t2\n}\nif (diff >= 10) {\n    (#Light).On()\n}"}

### Ex7 — sensor value → Speaker (variable binding)
[Timeline IR]
```
{"timeline":[{"op":"start_at","anchor":"now"},
 {"op":"read","var":"temp","src":"TemperatureSensor.Temperature"},
 {"op":"call","target":"Speaker.Speak","args":{"Text":"The current temperature is $temp"}}]}
```
[Precision Selectors] `(#TemperatureSensor)` / `(#Speaker)`
<Reasoning>
Bind sensor value, then use in the string with `+`.
</Reasoning>
{"cron":"","period":0,"script":"temp = (#TemperatureSensor).Temperature\n(#Speaker).Speak(\"The current temperature is \" + temp)"}

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
