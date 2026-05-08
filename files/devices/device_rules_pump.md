[Device Summary]
<Device "Pump">
  <Service "PumpMode" type="value">Current pump mode. Enum values: normal, minimum, maximum, localSetting.</Service>
  <Service "SetPumpMode" type="action">Set pump mode</Service>
</Device>

# Pump Examples

[Command]
Set the pump to maximum mode
["Pump.SetPumpMode"]

[Command]
Run the pump at minimum flow
["Pump.SetPumpMode"]

[Command]
Check the current pump mode
["Pump.PumpMode"]

[Command]
When the pump mode changes, do something
["Pump.PumpMode"]
