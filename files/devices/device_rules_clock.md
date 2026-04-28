[Device Summary]
<Device "Clock">
  <Service "Year/Month/Day/Weekday/Hour/Minute/Second" type="value">Current date and time information</Service>
  <Service "Timestamp" type="value">Current Unix timestamp</Service>
  <Service "Datetime" type="value">Date and time in YYYYMMddhhmm format</Service>
</Device>

# Rules

⚠️ **Prefer the IR built-in `clock.time` / `clock.date` / `clock.dayOfWeek` over Clock.* services.**
- For **time comparisons / scheduling / duration** (e.g. `clock.time >= 1800`, `clock.dayOfWeek == "MON"`) — NOT services. Do NOT include Clock in the plan; the IR stage uses these as built-in expressions.
- For **reading the current time to speak/display** — `clock.time` (hhmm integer) is also available as a built-in; prefer it over chaining Hour + Minute.
- Only include Clock.* services when a **specific sub-component** is needed (e.g., "say only the current minute" → `Clock.Minute`; "what year is it?" → `Clock.Year`).

# Clock Examples

[Command]
What is the current time? (announce via speaker)
<Reasoning>
Use IR built-in `clock.time`; no Clock service needed.
</Reasoning>
["Speaker.Speak"]

[Command]
Say the current minute only
<Reasoning>
Specific sub-component → Clock.Minute.
</Reasoning>
["Clock.Minute", "Speaker.Speak"]

[Command]
Check the current date on the Clock
<Reasoning>
Date components requested separately → sub-services.
</Reasoning>
["Clock.Year", "Clock.Month", "Clock.Day"]
