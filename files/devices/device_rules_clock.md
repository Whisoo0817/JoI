[Device Summary]
<Device "Clock">
  <Service "Year/Month/Day/Weekday/Hour/Minute/Second" type="value">Current date and time information</Service>
  <Service "Timestamp" type="value">Current Unix timestamp</Service>
  <Service "Datetime" type="value">Date and time in YYYYMMddhhmm format</Service>
</Device>

# Clock Examples

[Command]
What is the current time? (Ask Clock)
["Clock.Hour", "Clock.Minute"]

[Command]
Check the current date on the Clock
["Clock.Year", "Clock.Month", "Clock.Day"]
