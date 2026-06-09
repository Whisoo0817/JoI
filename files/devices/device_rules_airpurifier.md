[Device Summary]
<Device "AirPurifier">
  <Service "AirPurifierMode" type="value">Current mode. Enum values: auto, sleep, low, medium, high, quiet, windFree, off.</Service>
  <Service "SetAirPurifierMode" type="action">Set air purifier operating mode.</Service>
</Device>

# Rules

- **Operating mode / strength** ("auto / sleep / quiet / 약하게 / 세게 / 청정모드") → `SetAirPurifierMode`. This mode enum DOES include an `off` member, so a plain "turn off the air purifier" can be expressed as `SetAirPurifierMode(off)`.
- **Power on/off** also works via the `Switch` family (an AirPurifier carries `Switch`): "켜/꺼", "turn on/off". Prefer `Switch.On` / `Switch.Off` for bare power commands; use `SetAirPurifierMode(off)` only when the command frames it as a mode (e.g. "set it to off mode"). For turning ON, use `Switch.On` (the mode enum has no generic "on").

# AirPurifier Examples

[Command]
Turn on the air purifier
["Switch.On"]

[Command]
Set the AirPurifier to auto mode
["AirPurifier.SetAirPurifierMode"]

[Command]
Run the air purifier on the quietest setting
["AirPurifier.SetAirPurifierMode"]

[Command]
What mode is the AirPurifier in?
["AirPurifier.AirPurifierMode"]


# @ArgResolve

`SetAirPurifierMode.Mode` (ENUM: auto, sleep, low, medium, high, quiet, windFree, off). Map the command:
- "auto / 자동" → `auto`; "sleep / 취침" → `sleep`; "quiet / silent / 조용" → `quiet`; "wind-free / no cold draft / 무풍" → `windFree`
- "strong / strong wind / high / 세게 / 강" → `high`; "medium / 중간" → `medium`; "weak / low / 약하게 / 약" → `low`
- "off / 끄기 (as a mode)" → `off`

```
[Command] Put the air purifier in sleep mode.
[Selected Services] ["AirPurifier.SetAirPurifierMode"]
Output:
{"AirPurifier.SetAirPurifierMode": {"Mode": "sleep"}}
```
