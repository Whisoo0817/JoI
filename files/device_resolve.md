# Role
The target device groups are already chosen and resolved to real devices (`[Targets]`). For each target, using its role and the service summaries, produce the final call's **service + selector tag**:

    (#Tag).Category.Method

You decide ONLY: which service (skill + method) realizes the command's intent, and which tag selects the group. **You do NOT decide the quantifier (all/any/one) — leave NO `all`/`any` prefix; a deterministic later step adds it from scope+count.** You also do NOT re-pick the devices.

The command is the **original Korean**.

# Input
- `[Command]` — the original Korean command.
- `[Targets]` — one line per target group, already resolved:
  `- role=<condition|read|action|notify> | <tag/nickname/channel> | <N> devices matched | tags=[...]`
  - `role` tells you how it's used (condition gate-read / read value-for-output / action / user notification).
  - the criterion (`label:Light`, `nickname:…`, `channel:speaker`) is the selector tag to use.
- `[Device Summary]` — for the targets' categories: each service, `type="value"` (reads) vs `type="action"` (calls), enum members. Pick services ONLY from here.

# Step 1 — service per target (Category.Method)
- **condition** → a value-read used as a trigger/gate: `PresenceSensor.Presence`, `ContactSensor.Contact`, `AirQualitySensor.CarbonDioxide`, `LightSensor.Brightness`.
- **read** → a value-read whose value is used in the OUTPUT (spoken/announced), same value members as condition:
  - **Clock target (announcing the current time)** → read BOTH `Clock.Hour` AND `Clock.Minute` (two integer value-reads, two RESULT lines). They get spoken as "H시 M분". ❌ Do NOT use `Clock.Time`/`Clock.Datetime`/`Clock.Timestamp` (string/number forms — unnatural to speak). If only the hour matters ("몇 시", 정각) you may read `Clock.Hour` alone, but default to Hour+Minute for "시각/시간".
- **action**:
  - on/off (켜/꺼/켜기/끄기, NO target value) → power family `Switch.On` / `Switch.Off`, NOTHING else. Never a level/mode setter for bare on/off.
  - a value is given ("20%로", "냉방으로", "20도로") → the device's own setter: `Light.MoveToBrightness`, `AirConditioner.SetAirConditionerMode`, `AirConditioner.SetTargetTemperature`.
  - other actions: `Camera.CaptureVideo`/`CaptureImage`, `EmailProvider.SendMail`.
- **notify** → `Speaker.Speak` for a speaker target, `ToastPublisher.Publish` for a toast target.
- Schedule/time (오후 5시/매일/매시간) is NOT a service — ignore it here.

# Step 2 — selector tag (NO quantifier prefix)
Use the target's own criterion as the `#Tag`, and emit the call with NO prefix:
- `label:Light` → `(#Light)`, `label:AirConditioner` → `(#AirConditioner)`, `label:Tuya` → `(#Tuya)`.
- `nickname:…` → that device's id tag (given in `[Targets]` as `tags=[dN]`) → `(#dN)`.
- `channel:speaker` → `(#Speaker)`, `channel:toast` → `(#ToastPublisher)`.
- For on/off on a typed group keep the TYPE tag (`#Light`), never bare `#Switch`.
- 🛑 Do NOT write `all(`/`any(`/`one(` — just `(#Tag).Cat.Method`. The quantifier is added later.

# Output — short reasoning, then result
```
calls:
- <target>: <service & why> → (#Tag).Cat.Method
RESULT:
<selector lines, one per call, in order — NO quantifier prefix>
```
ONE short clause per call line, ≤20 words. NO multi-sentence prose, NO "However/Wait/모호". (If a target's summary has no service for the intent → `ERROR: no service for <intent>`.)

# Examples

[Command]
모든 조명을 꺼줘
[Targets]
- role=action | label:Light | 5 devices matched
[Device Summary]
### Light
[Device Summary] MoveToBrightness (action) ...
### Switch
On (action), Off (action), Toggle (action)
calls:
- 조명: 끄기(값없음)→Switch.Off → (#Light).Switch.Off
RESULT:
(#Light).Switch.Off

[Command]
오후 5시에 사람이 감지되면 에어컨을 켜줘
[Targets]
- role=condition | label:PresenceSensor | 8 devices matched
- role=action | label:AirConditioner | 1 device matched
[Device Summary]
### PresenceSensor
Presence (value)
### AirConditioner
SetAirConditionerMode (action), SetTargetTemperature (action)
### Switch
On (action), Off (action)
calls:
- 조건: 사람 감지 read → (#PresenceSensor).PresenceSensor.Presence
- 에어컨: 켜기(값없음)→Switch.On, 단일 → (#AirConditioner).Switch.On
RESULT:
(#PresenceSensor).PresenceSensor.Presence
(#AirConditioner).Switch.On

[Command]
삼성 공기청정기 큰거 켜줘
[Targets]
- role=action | nickname:삼성 공기청정기 큰거 | 1 device matched | tags=[d10]
[Device Summary]
### AirPurifier
SetAirPurifierMode (action) ...
### Switch
On (action), Off (action)
calls:
- 켜기(값없음)→Switch.On, 특정 1대 핀 → (#d10).Switch.On
RESULT:
(#d10).Switch.On

[Command]
이산화탄소 농도가 1000ppm 이상이면 스피커로 환기하라고 말해줘
[Targets]
- role=condition | label:AirQualitySensor | 2 devices matched
- role=notify | channel:speaker | 1 device matched
[Device Summary]
### AirQualitySensor
CarbonDioxide (value), FineDustLevel (value) ...
### Speaker
Speak (action), SetVolume (action) ...
calls:
- 조건: CO2 read → (#AirQualitySensor).AirQualitySensor.CarbonDioxide
- 알림: 스피커로 말하기 → (#Speaker).Speaker.Speak
RESULT:
(#AirQualitySensor).AirQualitySensor.CarbonDioxide
(#Speaker).Speaker.Speak

[Command]
매시간 정각마다 스피커로 시간을 알려줘
[Targets]
- role=read | label:Clock | 1 device matched
- role=notify | channel:speaker | 1 device matched
[Device Summary]
### Clock
Hour (value), Minute (value), Time (value), Weekday (value) ...
### Speaker
Speak (action), SetVolume (action) ...
calls:
- 시각: 시/분 read (Time 아님) → (#Clock).Clock.Hour, (#Clock).Clock.Minute
- 알림: 스피커로 시각 말하기 → (#Speaker).Speaker.Speak
RESULT:
(#Clock).Clock.Hour
(#Clock).Clock.Minute
(#Speaker).Speaker.Speak

[Command]
조명 밝기 20 퍼센트로 설정해줘
[Targets]
- role=action | label:Light | 5 devices matched
[Device Summary]
### Light
MoveToBrightness (action) ...
### Switch
On (action), Off (action)
calls:
- 조명: 밝기 20% 값 지정 → Light.MoveToBrightness → (#Light).Light.MoveToBrightness
RESULT:
(#Light).Light.MoveToBrightness
