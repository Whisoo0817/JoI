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

Prefer the IR built-in `clock.time` / `clock.date` / `clock.dayOfWeek` over Clock.* services.
- For time comparisons / scheduling / duration (e.g. `clock.time >= 1800`, `clock.dayOfWeek == "MON"`) — NOT services. Do NOT include Clock in the plan; the IR stage uses these as built-in expressions.
- For reading the current time to speak/display — `clock.time` (hhmm integer) is also available as a built-in; prefer it over chaining Hour + Minute.
- Only include Clock.* services when a specific sub-component is needed (e.g., "say only the current minute" → `Clock.Minute`; "what year is it?" → `Clock.Year`).

# Clock Examples

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
