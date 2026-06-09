[Device Summary]
<Device "Humidifier">
  <Service "HumidifierMode" type="value">Current humidifier mode. Enum values: auto, low, medium, high.</Service>
  <Service "SetHumidifierMode" type="action">Set humidifier mode</Service>
</Device>

# Rules

- **Power on/off is `Switch.On` / `Switch.Off`** (a Humidifier device carries the `Switch` family). For "turn on/off the humidifier", "가습기 켜/꺼" → `Switch.On` / `Switch.Off`, NOT a mode change.
- **Mode/strength** (auto / low / medium / high, "약하게/세게") → `SetHumidifierMode`. The mode enum is for output strength, NOT power — it has no "off" member.

# Humidifier Examples

[Command]
Turn on the humidifier
["Switch.On"]

[Command]
Set the Humidifier to high mode
["Humidifier.SetHumidifierMode"]

[Command]
Run the humidifier weaker
["Humidifier.SetHumidifierMode"]

[Command]
Tell me the current HumidifierMode
["Humidifier.HumidifierMode"]

[Command]
When the humidity drops below 40%, set the humidifier to high
["HumiditySensor.Humidity", "Humidifier.SetHumidifierMode"]


# @ArgResolve

`SetHumidifierMode.Mode` (ENUM: auto, low, medium, high). Map the command's strength word:
- "auto / 자동" → `auto`
- "weak / low / 약하게 / 약" → `low`
- "medium / 중간" → `medium`
- "strong / high / max / 세게 / 강" → `high`

```
[Command] Set the humidifier to the strongest mode.
[Selected Services] ["Humidifier.SetHumidifierMode"]
Output:
{"Humidifier.SetHumidifierMode": {"Mode": "high"}}
```
