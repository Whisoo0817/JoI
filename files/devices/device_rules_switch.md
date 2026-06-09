[Device Summary]
<Device "Switch">
  <Service "Switch" type="value">Current switch state (true: on, false: off). Use this to check whether the device is currently on or off.</Service>
  <Service "Off" type="action">Turn off</Service>
  <Service "On" type="action">Turn on</Service>
  <Service "Toggle" type="action">Toggle</Service>
</Device>

NOTE: A standalone Switch is rarely controlled in isolation. Most realistic commands pair it with another appliance — turn the Switch on/off as a follow-up to a Light, AirConditioner, or Humidifier state change, or read another device's state to decide whether to operate the Switch.

# Switch Examples

[Command]
When the light turns off, turn off the Switch
# why: the condition ("when the light turns off") needs a switch-state read first → Switch.Switch, then act → Switch.Off
["Switch.Switch", "Switch.Off"]

[Command]
If the AirConditioner is off, turn on the Switch
["Switch.Switch", "Switch.On"]

[Command]
When the Humidifier turns on, turn off the Switch
["Switch.Switch", "Switch.Off"]

[Command]
If the light is on, toggle the Switch
["Switch.Switch", "Switch.Toggle"]

[Command]
Turn off the Switch when the AirConditioner stops running
["Switch.Switch", "Switch.Off"]
