[Device Summary]
<Device "Light">
  <Service "CurrentBrightness" type="value">Current brightness (0-100%)</Service>
  <Service "CurrentHue" type="value">Current hue value</Service>
  <Service "CurrentSaturation" type="value">Current saturation value</Service>
  <Service "EnhancedCurrentHue" type="value">Current hue value with 16-bit precision</Service>
  <Service "ColorTemperatureMireds" type="value">Current color temperature in mireds</Service>
  <Service "ColorTempPhysicalMinMireds" type="value">Physical minimum limit of color temperature in mireds</Service>
  <Service "ColorTempPhysicalMaxMireds" type="value">Physical maximum limit of color temperature in mireds</Service>
  <Service "ColorMode" type="value">Current color mode (hsv, xy, ct)</Service>
  <Service "CurrentX" type="value">Current CIE 1931 X chromaticity coordinate (0.0-1.0)</Service>
  <Service "CurrentY" type="value">Current CIE 1931 Y chromaticity coordinate (0.0-1.0)</Service>
  <Service "MoveToBrightness" type="action">Set brightness to a target value over a transition time. (Use time 0.0 for instant change)</Service>
  <Service "MoveToHue" type="action">Move to a specific target hue over a transition time.</Service>
  <Service "MoveToSaturation" type="action">Move to a specific target saturation over a transition time.</Service>
  <Service "MoveToHueAndSaturation" type="action">Move to specific target hue and saturation over a transition time.</Service>
  <Service "EnhancedMoveToHue" type="action">Move to target hue with 16-bit precision</Service>
  <Service "EnhancedMoveToHueAndSaturation" type="action">Move to target hue and saturation with 16-bit precision</Service>
  <Service "MoveToColor" type="action">Set color to a specific target CIE xy coordinate over a Transition Time in seconds. (e.g., instant red: 0.675, 0.322, 0.0 -> 3rd arg is time)</Service>
  <Service "MoveToColorTemperature" type="action">Move to a specific target color temperature in mireds over a transition time.</Service>
  <Service "MoveHue" type="action">Continuously move hue at a specified Rate (NO destination).</Service>
  <Service "MoveColor" type="action">Continuously move XY color vectors at a specified Rate (NO destination).</Service>
  <Service "MoveColorTemperature" type="action">Continuously move color temperature at a specified Rate (NO destination).</Service>
  <Service "StepHue" type="action">Step hue by a specified amount (Delta step)</Service>
  <Service "StepColor" type="action">Step XY color by a specified amount (Delta step)</Service>
  <Service "StepColorTemperature" type="action">Step color temperature by a specified amount (Delta step)</Service>
</Device>

# Light Examples

We carefully distinguish between `MoveTo*` and `Move*`.
- `MoveToColor`/`MoveToColorTemperature`/`MoveToBrightness`: Reaching a target value.
- `MoveColor`/`MoveColorTemperature`/`MoveHue`: Continuously shifting WITHOUT a target.
- Use `Light.MoveToColor` for specific color names like "Red" or "Blue".

## On/Off Fallback
- To turn OFF: prefer `Switch.Off` if available. If not, use `Light.MoveToBrightness` with value 0.
- To turn ON: prefer `Switch.On` if available. If not, use `Light.MoveToBrightness` with value 100 (or a user-specified value).
- Never return an empty list because Switch is unavailable — always fall back to `MoveToBrightness`.

[Command]
Set the light color to red
["Light.MoveToColor"]

[Command]
Bring down the brightness slowly to 10
["Light.MoveToBrightness"]

[Command]
Keep changing the color temperature
["Light.MoveColorTemperature"]

[Command]
Check the current brightness of the light
["Light.CurrentBrightness"]

[Command]
Turn off the light (Switch not available)
["Light.MoveToBrightness"]

[Command]
Turn on the light (Switch not available)
["Light.MoveToBrightness"]

[Command]
Increase the brightness by 10
["Light.CurrentBrightness", "Light.MoveToBrightness"]


# @ArgResolve

Color name → CIE 1931 xy (use verbatim for any service taking `ColorX`/`ColorY`, e.g. `MoveToColor`):

| Color | x | y |
|---|---|---|
| red | 0.675 | 0.322 |
| green | 0.408 | 0.517 |
| blue | 0.167 | 0.040 |
| yellow | 0.432 | 0.500 |
| cyan | 0.225 | 0.329 |
| magenta | 0.385 | 0.157 |
| orange | 0.560 | 0.406 |
| purple | 0.279 | 0.142 |
| pink | 0.461 | 0.249 |
| white | 0.313 | 0.329 |

If the color isn't in this table, fall back to white (0.313, 0.329). Do NOT invent xy values.
