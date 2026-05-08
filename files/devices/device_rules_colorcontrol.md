[Device Summary]
<Device "ColorControl">
  <Service "Color" type="value">Current color in RGB format (r|g|b)</Service>
  <Service "SetColor" type="action">Set the color of the device</Service>
</Device>

# ColorControl Examples

[Command]
Set the ColorControl color to blue
["ColorControl.SetColor"]

[Command]
What color is the ColorControl?
["ColorControl.Color"]

[Command]
Change the ColorControl to red
["ColorControl.SetColor"]
