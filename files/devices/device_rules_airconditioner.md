[Device Summary]
<Device "AirConditioner">
  <Service "AirConditionerMode" type="value">Current operation mode</Service>
  <Service "TargetTemperature" type="value">Target temperature</Service>
  <Service "SetAirConditionerMode" type="action">Set AC mode (auto, cool, heat). NOTE: enum has NO "off". For power-off: use `Switch.Off` if the AC has `Switch` in its category; if not, return `[]` (no off path).</Service>
  <Service "SetTargetTemperature" type="action">Set target temperature</Service>
</Device>

# AirConditioner Examples

[Command]
Set the AC to cool mode
["AirConditioner.SetAirConditionerMode"]

[Command]
Change the target temperature to 24 degrees
["AirConditioner.SetTargetTemperature"]

[Command]
What is the current mode of the AirConditioner?
["AirConditioner.AirConditionerMode"]
