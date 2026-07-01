[Device Summary]
<Device "Button">
  <Service "Button" type="value">Button state. Enum values: pushed, held, double, pushed_2x, pushed_3x, pushed_4x, pushed_5x, pushed_6x, down, down_2x, down_3x, down_4x, down_5x, down_6x, down_hold, up, up_2x, up_3x, up_4x, up_5x, up_6x, up_hold, swipe_up, swipe_down, swipe_left, swipe_right.</Service>
</Device>

# @EnumResolve

Verb-to-member mapping for `Button.Button`:
- "pressed" / "clicked" / "pushed" → `pushed`
- "double-clicked" / "double press" → `double` or `pushed_2x` (prefer `double` if present)
- "held" / "held down" / "long press" → `held` (NOT `down` unless description says "held down")
- "swipe up/down/left/right" → matching `swipe_*` member

Example:
```
[Command] When the button is pressed, ...
Output: {"Button.Button": {"op": "==", "value": "pushed"}}
```
