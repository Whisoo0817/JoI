[Device Summary]
<Device "Switch">
  <Service "Switch" type="value">State (on/off)</Service>
  <Service "On" type="action">Turn on</Service>
  <Service "Off" type="action">Turn off</Service>
  <Service "Toggle" type="action">Toggle</Service>
</Device>

# Switch Examples

[Command]
Turn on the Switch
["Switch.On"]

[Command]
Turn off the Switch
["Switch.Off"]

[Command]
Toggle the Switch
["Switch.Toggle"]

[Command]
Read the switch state of the Switch
["Switch.Switch"]
