# JoI Dataset Migration Rules — 2.0.4 target

You are migrating a JoI IoT dataset from old service references to JoI 2.0.4. For every row, produce a migrated `gt` and a `connected_devices` dict.

## CRITICAL — JoI surface syntax

JoI calls/reads use **flat lowercase compound names** that fuse the 2.0.4 skill and function/value with a single underscore. The skill namespace is NOT explicit in the script.

Mapping rule from a 2.0.4 entry `<Skill>.<Function>(<args>)`:
- skill: first letter lowercase, rest unchanged (`Light`→`light`, `AirConditioner`→`airConditioner`, `RobotVacuumCleaner`→`robotVacuumCleaner`, `TemperatureSensor`→`temperatureSensor`, `WindowCovering`→`windowCovering`)
- function/value: first letter lowercase, rest unchanged (`On`→`on`, `SetTargetTemperature`→`setTargetTemperature`, `Temperature`→`temperature`, `MoveToBrightness`→`moveToBrightness`, `CurrentPosition`→`currentPosition`)
- joiner: single underscore
- args: **positional**. Use ENUM values as plain strings (`"dry"`, `"cool"`, NEVER `Mode:"dry"`).

### Examples (canonical)

| 2.0.4 service | JoI surface |
|---|---|
| `Switch.On()` | `(#Light).switch_on()` |
| `Switch.Off()` | `(#Speaker).switch_off()` |
| `AirConditioner.SetTargetTemperature(19)` | `(#AC).airConditioner_setTargetTemperature(19)` |
| `AirConditioner.SetAirConditionerMode("cool")` | `(#AC).airConditioner_setAirConditionerMode("cool")` |
| `TemperatureSensor.Temperature` (read) | `(#TempSensor).temperatureSensor_temperature` |
| `Light.MoveToBrightness(80, 0.0)` | `(#Light).light_moveToBrightness(80, 0.0)` |
| `Light.MoveToColor(0.675, 0.322, 0.0)` | `(#Light).light_moveToColor(0.675, 0.322, 0.0)` |
| `Switch.Switch` value (= on/off state) | `(#Sel).switch_switch` |
| `WindowCovering.SetLevel(50)` | `(#Blind).windowCovering_setLevel(50)` |
| `WindowCovering.CurrentPosition` | `(#Window).windowCovering_currentPosition` |
| `Door.Open()` | `(#Door).door_open()` |
| `Door.DoorState` | `(#Door).door_doorState` |
| `Speaker.Speak("hello")` | `(#Speaker).speaker_speak("hello")` |
| `Speaker.SetVolume(30)` | `(#Speaker).speaker_setVolume(30)` |
| `Camera.CaptureImage()` | `(#Camera).camera_captureImage()` |
| `Clock.Hour` | `(#Clock).clock_hour` |

## Other rules

- Old GT was lowercase too but referenced services that may not exist in 2.0.4. Re-derive every method/value name from the 2.0.4 catalog. Do NOT keep old names that don't correspond to a real 2.0.4 service.
- Light On/Off: prefer `switch_on`/`switch_off` (Switch skill is implemented by Light devices). Fall back to `light_moveToBrightness(0|100, 0.0)` only if Switch isn't available for the device's category.
- Color: named colors → `light_moveToColor(x, y, 0.0)` with CIE xy. (yellow≈0.4317,0.5008; red≈0.675,0.322; blue≈0.167,0.040; green≈0.27,0.6; white≈0.32,0.33; orange≈0.5,0.42; purple≈0.27,0.13; pink≈0.45,0.25)
- **Selector preservation**: Keep selectors from the original GT verbatim. Do NOT rename `(#TemperatureSensor)` to `(#TempSensor)` etc.
- **Switch.Switch value**: when checking on/off state in a condition, use `(#Sel).switch_switch`. Single underscore.
- If old GT references a service that doesn't exist in 2.0.4 (e.g., a deprecated method, weather lookups not in WeatherProvider), find the closest valid 2.0.4 service. If genuinely unmappable, leave the GT script intact but note it in `notes` field.
- For `(#Clock)` reads: skill is `Clock`, values include `hour`, `minute`, `second`, `time`, `date`, `weekday`, `day`, `month`, `year`, `isHoliday`, `datetime`, `timestamp`. Surface form: `clock_hour`, `clock_time`, `clock_weekday`, etc.

## Connected devices schema

```
{ "<DeviceId>": { "category": ["<SkillId>", ...], "tags": ["<Loc>", "<Skill>", ...] } }
```
- Semantic device ids (LivingRoom_Light, Kitchen_Dishwasher, ...).
- For each row: include every device the new GT's selectors target, PLUS exactly one same-category distractor in a DIFFERENT location.
- Tags must support every selector in the GT. If GT has `(#LivingRoom #Light)`, the device must have `LivingRoom` AND `Light` in its tags.
- For `all(...)` selectors, you may need 2+ matching devices (otherwise `all` is meaningless). In that case still add 1 different-location distractor.
- Categories: a Light device's `category` should be `["Light", "Switch", "ColorControl", "LevelControl"]` (or subset if the device doesn't support color/dimming). Sirens are typically `["Siren", "Switch"]`. AirConditioners `["AirConditioner", "Switch"]`. Pure sensors are single-category.
- If the original GT uses an unusual selector tag (e.g., `(#TemperatureSensor)` rather than `(#LivingRoom #TempSensor)`), the device's tags must include that exact tag — even if it's a category-shaped tag rather than a location.

## Reference files

- 2.0.4 catalog: `/home/gnltnwjstk/joi-agent/dataset_migration/skills_2.0.4.md`
- Per-device migration rules: `/home/gnltnwjstk/joi/files/devices/device_rules_<lowercase>.md`
- Selector grammar: `/home/gnltnwjstk/joi/files/mapping_precision.md`

## Output schema

Each migrated row is an object:
```json
{
  "index": <int>,
  "category": <int>,
  "command_kor": <str>,
  "command_eng": <str>,
  "gt_old": <str — original gt verbatim>,
  "gt_new": <str — JSON-encoded {"name":"","cron":...,"period":...,"script":...}>,
  "connected_devices": <dict>,
  "notes": <str — short note or "ok">
}
```
Output as a JSON array.
