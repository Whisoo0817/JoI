[Device Summary]
<Device "ColorControl">
  <Service "Color" type="value">Current color (Hue, Saturation, Value)</Service>
  <Service "SetColor" type="action">Set device color</Service>
</Device>

# ColorControl Examples

[Command]
Set the ColorControl color to blue
["ColorControl.SetColor"]

[Command]
What color is the ColorControl?
["ColorControl.Color"]
