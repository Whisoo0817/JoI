[Device Summary]
<Device "RotaryControl">
  <Service "Button" type="value">State of button (pushed, held, double, etc.)</Service>
  <Service "Rotation" type="value">Rotary dial state (clockwise, counter_clockwise)</Service>
  <Service "RotationSteps" type="value">Number of rotation steps</Service>
</Device>

# RotaryControl Examples

[Command]
Turn on the RotaryControl
["RotaryControl.On"]

[Command]
Turn off the RotaryControl
["RotaryControl.Off"]

[Command]
Toggle the RotaryControl
["RotaryControl.Toggle"]
