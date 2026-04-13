[Device Summary]
<Device "Pump">
  <Service "PumpMode" type="value">Current pump operation mode (normal / minimum / maximum / localSetting)</Service>
  <Service "SetPumpMode" type="action">Set pump operation mode (normal / minimum / maximum / localSetting)</Service>
</Device>

# Pump Examples

[Command]
Set the pump to maximum speed
["Pump.SetPumpMode"]

[Command]
Run the pump at minimum flow
["Pump.SetPumpMode"]

[Command]
Check the current pump mode
["Pump.PumpMode"]

[Command]
Set the pump to normal operation
["Pump.SetPumpMode"]
