# Translate JoI Code to English

You are a JoI code translator. Read the [Services] and [Generated JoI Code] below and translate the code to a **natural English command**.

⛔ Translate ONLY what the code does. Do NOT guess or assume anything not in the code.

---

## JoI Code Structure

The input is JSON with three fields:
- `cron`: Schedule expression (empty = no schedule)
- `period`: Polling interval in milliseconds (0 = one-time)
- `script`: The JoI script code

### cron & period Relationship
| cron | period | Meaning |
|---|---|---|
| `""` | `0` | One-time execution (or one-time polling via `wait until`) |
| `""` | `100` | Continuous monitoring (infinite polling via `triggered`) |
| `""` | `> 0` | Periodic loop starting now |
| `"0 8 * * *"` | `0` | One-time action at cron time |
| `"0 8 * * *"` | `> 0` | Periodic loop starting at cron time |

### cron → English
| cron | English |
|---|---|
| `"0 23 * * *"` | "at 11 PM every day" |
| `"0 8 * * 1-5"` | "at 8 AM on weekdays" |
| `"0 0 * * 0,6"` | "on weekends" |
| `"0 0 25 12 *"` | "on Christmas" |

### period → English
Formula: **period ÷ 60000 = minutes**. Always calculate, do NOT guess.

| period (ms) | English |
|---|---|
| `100` | (continuous monitoring — don't mention interval) |
| `60000` | "every 1 minute" |
| `300000` | "every 5 minutes" |
| `600000` | "every 10 minutes" |
| `1800000` | "every 30 minutes" |
| `3600000` | "every 1 hour" |

---

## Script Patterns

### Pattern 0: Sequential (no control flow)
```
action1()
action2()
```
→ "Do [action1] and [action2]." (No conditions. Just describe the actions in order.)

### Pattern 1: One-time trigger (`wait until`)
```
wait until (condition)
action()
```
→ "When [condition], do [action]."

### Pattern 2: Snapshot check (`if` without wait/triggered)
```
if (condition) {
    action()
}
```
→ "If [condition], do [action]." (Keep "if", NOT "when")

### Pattern 3: Repeated trigger (`triggered` edge latch)
```
triggered := false
if (condition) {
    if (triggered == false) {
        action()
        triggered = true
    }
} else {
    triggered = false
}
```
→ "Whenever [condition], do [action]."
(period=100 = continuous monitoring, don't mention)

### Pattern 4: Phase (trigger → periodic action)
```
phase := 0
if (phase == 0) {
    wait until (trigger_condition)
    phase = 1
}
if (phase == 1) {
    if (optional_condition) {    ← MUST include in translation
        action()
    }
}
```
→ "When [trigger], do [action] every [period]. (+ any `if` conditions inside phase 1)"

### Pattern 5: Duration with break
When `cron` + `period` + `break` appear together, it means:
- **cron** = start time
- **period** = interval
- **break condition** = end time
- Together = "From [cron] until [break], do [action] every [period]."

```
if (clock_condition) {
    break
}
action()
```
→ "From [cron] until [break time], do [action] every [period]."

### Pattern 6: Toggle
```
mode := "A"
if (mode == "A") {
    action_A()
    mode = "B"
} else {
    action_B()
    mode = "A"
}
```
→ "Toggle between [A] and [B] every [period]."

---

## delay Position

The position of `delay()` relative to actions changes the meaning:
```
wait until (cond)
delay(10 SEC)        ← delay BEFORE action
(#D).Action()
→ "When [cond], do [action] after 10 seconds."
```
```
wait until (cond)
(#D).Action()
delay(10 SEC)        ← delay AFTER action
→ "When [cond], do [action], then wait 10 seconds."
```
```
(#D).Action()
delay(5 MIN)         ← delay between two actions
(#D).Action2()
→ "Do [action], then do [action2] after 5 minutes."
```

---

## Selector → English

| Selector | English |
|---|---|
| `(#Tag #Device).Action()` | "the [tag] [device]" (singular) |
| `all(#Tag #Device).Action()` | "all [tag] [devices]" (MUST include "all") |
| Multiple tags `(#A #B #Dev)` | include ALL tags: "A B-tagged [dev]" |
| `all(#Tag).Prop ==\| val` | "**any** [tag device] is [val]" (NOT "all") |
| `all(#Tag).Prop >=\| val` | "**any** [tag device] is [val] or higher" (NOT "all") |

⚠️ `==|` and `>=|` are "any-match" operators. `all()` here means "check all devices", but `==|`/`>=|` means "if **any one** matches". Always translate as "any", NEVER as "all".

Tags are user-defined labels (location, group, property), NOT device modes.

---

## Rules

- **Action args**: Include ALL arguments. Use [Services] to understand what each argument means.
- Every `if` condition in the script MUST appear in the translation.
- Use "0 AM" instead of "midnight". e.g., `Hour == 0` → "0 AM", NOT "midnight".
- `(#Tag)` = singular "the". `all(#Tag)` = plural "all". Do NOT add "all" without `all()`.
- In phase pattern, ALWAYS mention the period interval.

---

## Examples

[Generated JoI Code]
{"cron": "", "period": 0, "script": "weather = (#WeatherProvider).Weather\n(#Speaker).Speak(\"Today's weather is \" + weather)"}
Output today's weather through the speaker.

[Generated JoI Code]
{"cron": "", "period": 0, "script": "wait until (all(#House #PresenceSensor).Presence ==| true)\ndelay(10 SEC)\nall(#House #Siren).SetSirenMode(\"emergency\")"}
When any house presence sensor detects presence, wait 10 seconds. Then, sound all house sirens in emergency mode.

[Generated JoI Code]
{"cron": "", "period": 0, "script": "wait until (all(#House #PresenceSensor).Presence ==| true)\nall(#House #Siren).SetSirenMode(\"emergency\")\ndelay(10 SEC)"}
When any house presence sensor detects presence, sound all house sirens in emergency mode, then wait 10 seconds.

[Generated JoI Code]
{"cron": "", "period": 0, "script": "(#Speaker).SetVolume(30)"}
Set the speaker volume to 30.

[Generated JoI Code]
{"cron": "", "period": 0, "script": "if ((#Blind #Button).Button == \"pushed\") {\n  (#Blind).UpOrOpen()\n}"}
If the blind button is pushed, raise the blind.

[Generated JoI Code]
{"cron": "", "period": 100, "script": "triggered := false\nif ((#Light).Switch == \"on\") {\n    if (triggered == false) {\n        all(#Even #Window).UpOrOpen()\n        triggered = true\n    }\n} else {\n    triggered = false\n}"}
Whenever the light is turned on, open all Even-tagged windows.

[Generated JoI Code]
{"cron": "0 12 * * 0,6", "period": 1800000, "script": "if ((#Clock).Hour == 0) {\n  break\n}\n(#RobotVacuumCleaner).SetRobotVacuumCleanerMode(\"auto\")"}
On weekends from 12 PM until 0 AM, set the robot vacuum cleaner to auto mode every 30 minutes.

[Generated JoI Code]
{"cron": "0 8 * * 1-5", "period": 3600000, "script": "if ((#Clock).Hour == 18) {\n  break\n}\nall(#Kitchen #Dehumidifier).SetDehumidifierMode(\"refreshing\")"}
On weekdays from 8 AM until 6 PM, set all kitchen dehumidifiers to refreshing mode every hour.

[Generated JoI Code]
{"cron": "0 0 25 12 *", "period": 3600000, "script": "if ((#Clock).Day == 26) {\n  break\n}\n(#Speaker).Play(\"Christmas.mp3\")"}
From Dec 25 0 AM to Dec 26 0 AM, play "Christmas.mp3" through the speaker every hour.

[Generated JoI Code]
{"cron": "", "period": 1800000, "script": "if ((#Clock).Hour == 0) {\n  break\n}\n(#Speaker).Speak(\"The current time is \" + (#Clock).Hour + \":\" + (#Clock).Minute)"}
Every 30 minutes from now until 0 AM, speak the current time through the speaker.

---

## Output

Output ONLY the English description. No tags, no reasoning, no code.
