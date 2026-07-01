[Device Summary]
<Device "ColorControl">
  <Service "Color" type="value">Current color in RGB format (r|g|b)</Service>
  <Service "SetColor" type="action">Set the color of the device</Service>
</Device>

# Rules

- Set a color → `SetColor` (Color is an `r|g|b` RGB string). Read current color → `Color`.
- ColorControl is the generic color sub-skill; on a `Light` a named color usually goes to `Light.MoveToColor` (xy) instead — prefer that when the device is a Light.
