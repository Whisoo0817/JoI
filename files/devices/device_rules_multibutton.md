[Device Summary]
<Device "MultiButton">
  <Service "Button1" type="value">State of button 1. Enum values: pushed, held, double, pushed_2x, pushed_3x, down, down_hold, up, up_hold.</Service>
  <Service "Button2" type="value">State of button 2. Enum values: pushed, held, double, pushed_2x, pushed_3x, down, down_hold, up, up_hold.</Service>
  <Service "Button3" type="value">State of button 3. Enum values: pushed, held, double, pushed_2x, pushed_3x, down, down_hold, up, up_hold.</Service>
  <Service "Button4" type="value">State of button 4. Enum values: pushed, held, double, pushed_2x, pushed_3x, down, down_hold, up, up_hold.</Service>
</Device>

# @EnumResolve

Verb-to-member mapping for `Button1` / `Button2` / `Button3` / `Button4`:
- "pressed" / "clicked" / "pushed" → `pushed`
- "double-clicked" / "double press" → `double` or `pushed_2x` (prefer `double` if present)
- "held" / "long press" → `held`

Example:
```
[Command] When button 1 of the multi-button is pressed, ...
Output: {"MultiButton.Button1": {"op": "==", "value": "pushed"}}
```
