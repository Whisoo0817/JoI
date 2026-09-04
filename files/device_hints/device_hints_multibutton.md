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
