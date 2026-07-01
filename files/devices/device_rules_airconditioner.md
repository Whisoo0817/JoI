[Device Summary]
<Device "AirConditioner">
  <Service "AirConditionerMode" type="value">Current operation mode</Service>
  <Service "TargetTemperature" type="value">Target temperature</Service>
  <Service "SetAirConditionerMode" type="action">Set AC mode (enum: auto, cool, heat — NO "off"). For power-off use `Switch.Off`.</Service>
  <Service "SetTargetTemperature" type="action">Set target temperature (arg: Temperature DOUBLE)</Service>
</Device>

# AirConditioner Rules

- On/off (켜/꺼, no value) → `Switch.On` / `Switch.Off` (the AC carries `Switch`; the mode enum has NO "off"). "켜져 있으면"(on/off state) → `Switch.Switch`, NOT `AirConditionerMode`.
- A mode named (자동/냉방/난방 → auto/cool/heat) → `SetAirConditionerMode`.
- A target temperature ("24도로") → `SetTargetTemperature`. A relative change ("1도 낮춰") reads `TargetTemperature` then `SetTargetTemperature`.
- Reading current state → `AirConditionerMode` (mode) / `TargetTemperature` (setpoint).
