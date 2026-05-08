[Device Summary]
<Device "RotaryControl">
  <Service "Rotation" type="value">Rotary direction. Enum values: clockwise, counter_clockwise.</Service>
  <Service "RotationSteps" type="value">Number of rotation steps (INTEGER)</Service>
</Device>

# RotaryControl Examples

[Command]
Read the current rotation direction of the RotaryControl
["RotaryControl.Rotation"]

[Command]
How many steps has the RotaryControl rotated?
["RotaryControl.RotationSteps"]

[Command]
When the RotaryControl turns clockwise, do something
["RotaryControl.Rotation"]

[Command]
When the RotaryControl is rotated, do something
["RotaryControl.RotationSteps"]
