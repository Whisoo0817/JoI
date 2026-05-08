[Device Summary]
<Device "Button">
  <Service "Button" type="value">Button state. Enum values: pushed, held, double, pushed_2x, pushed_3x, pushed_4x, pushed_5x, pushed_6x, down, down_2x, down_3x, down_4x, down_5x, down_6x, down_hold, up, up_2x, up_3x, up_4x, up_5x, up_6x, up_hold, swipe_up, swipe_down, swipe_left, swipe_right.</Service>
</Device>

# Button Examples

[Command]
Check if the Button was pushed
["Button.Button"]

[Command]
When the button is pushed, do something
["Button.Button"]
