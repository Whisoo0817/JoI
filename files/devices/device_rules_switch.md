[Device Summary]
<Device "Switch">
  <Service "Switch" type="value">Current switch state (true: on, false: off). Use this to check whether the device is currently on or off.</Service>
  <Service "Off" type="action">Turn off</Service>
  <Service "On" type="action">Turn on</Service>
  <Service "Toggle" type="action">Toggle</Service>
</Device>

NOTE: A standalone Switch is rarely controlled in isolation. Most realistic commands pair it with another appliance — turn the Switch on/off as a follow-up to a Light, AirConditioner, or Humidifier state change, or read another device's state to decide whether to operate the Switch.

# Rules

- On/off (켜/꺼/켜기/끄기) → `On` / `Off`. Toggle (토글) → `Toggle`.
- "켜져 있으면/꺼져 있으면"(on/off state check) → `Switch` (the BOOL value), NOT an action.
