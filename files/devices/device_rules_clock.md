[Device Summary]
<Device "Clock">
  <Service "Date" type="value">Current date as string - format: YYYYMMdd</Service>
  <Service "Datetime" type="value">Current date and time as string - format: YYYYMMddhhmm</Service>
  <Service "Day" type="value">Current day</Service>
  <Service "Hour" type="value">Current hour</Service>
  <Service "IsHoliday" type="value">Whether today is a holiday</Service>
  <Service "Minute" type="value">Current minute</Service>
  <Service "Month" type="value">Current month</Service>
  <Service "Second" type="value">Current second</Service>
  <Service "Time" type="value">Current time as string - format: hhmm</Service>
  <Service "Timestamp" type="value">Current timestamp (return current unix time - unit: seconds with floating point)</Service>
  <Service "Weekday" type="value">Current weekday. Enum values: monday, tuesday, wednesday, thursday, friday, saturday, sunday.</Service>
  <Service "Year" type="value">Current year</Service>
</Device>

# Rules

Read the Clock through its **`Clock.*` integer/enum value services** (`Clock.Hour`, `Clock.Minute`, `Clock.Weekday`, …). Do NOT use the deprecated `clock.time`/`clock.date` string built-ins.
- **Speaking / announcing / displaying the current time** → read `Clock.Hour` AND `Clock.Minute` (two integer reads, spoken as "H시 M분"). 🛑 Do NOT pick `Clock.Time` / `Clock.Datetime` / `Clock.Timestamp` (raw string / unix forms — unnatural to speak, e.g. "1430"). Default to Hour+Minute for "시각/시간"; use `Clock.Hour` alone only for "몇 시"/정각.
- **Time comparisons / scheduling / windows** ("오후 6시 이후", "until 3 PM") are handled by the IR/cron stage via `(#Clock).Hour`/`Minute` conditions — surface a Clock read here ONLY when the command speaks/uses the value.
- Pick the specific sub-component the command names: "무슨 요일" → `Clock.Weekday`; "what year" → `Clock.Year`.

# Clock Examples

[Command]
Announce the current time / 현재 시각을 말해줘
["Clock.Hour", "Clock.Minute"]

[Command]
Say the current minute only
["Clock.Minute"]

[Command]
Check the current date on the Clock
["Clock.Year", "Clock.Month", "Clock.Day"]

[Command]
What weekday is it today?
["Clock.Weekday"]

[Command]
Is today a holiday?
["Clock.IsHoliday"]
