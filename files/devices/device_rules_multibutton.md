[Device Summary]
<Device "MultiButton">
  <Service "Button1" type="value">State of button 1. Enum values: pushed, held, double, pushed_2x, pushed_3x, down, down_hold, up, up_hold.</Service>
  <Service "Button2" type="value">State of button 2. Enum values: pushed, held, double, pushed_2x, pushed_3x, down, down_hold, up, up_hold.</Service>
  <Service "Button3" type="value">State of button 3. Enum values: pushed, held, double, pushed_2x, pushed_3x, down, down_hold, up, up_hold.</Service>
  <Service "Button4" type="value">State of button 4. Enum values: pushed, held, double, pushed_2x, pushed_3x, down, down_hold, up, up_hold.</Service>
</Device>

# MultiButton Examples

[Command]
If the first button of the MultiButton is pushed
["MultiButton.Button1"]

[Command]
Check if MultiButton button 3 is held
["MultiButton.Button3"]
