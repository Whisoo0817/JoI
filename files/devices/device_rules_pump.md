[Device Summary]
<Device "Pump">
  <Service "PumpMode" type="value">Current pump mode. Enum values: normal, minimum, maximum, localSetting.</Service>
  <Service "SetPumpMode" type="action">Set pump mode</Service>
</Device>

# Rules

- A pump mode named (normal/minimum/maximum/localSetting) → `SetPumpMode`. Read current mode → `PumpMode`.
- On/off → `Switch.On`/`Switch.Off` if the pump has a Switch.
