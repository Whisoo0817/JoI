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
