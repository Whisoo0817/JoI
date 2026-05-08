[Device Summary]
<Device "PressureSensor">
  <Service "Presence" type="value">Current pressure value (DOUBLE)</Service>
</Device>

NOTE: The catalog service ID is "Presence" (not "Pressure"). Use PressureSensor.Presence to read pressure.

# PressureSensor Examples

[Command]
Read the PressureSensor pressure
["PressureSensor.Presence"]

[Command]
What is the current pressure?
["PressureSensor.Presence"]

[Command]
When the pressure exceeds a threshold, do something
["PressureSensor.Presence"]
