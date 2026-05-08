[Device Summary]
<Device "Humidifier">
  <Service "HumidifierMode" type="value">Current humidifier mode. Enum values: auto, low, medium, high.</Service>
  <Service "SetHumidifierMode" type="action">Set humidifier mode</Service>
</Device>

# Humidifier Examples

[Command]
Set the Humidifier to high mode
["Humidifier.SetHumidifierMode"]

[Command]
Tell me the current HumidifierMode
["Humidifier.HumidifierMode"]

[Command]
Switch the Humidifier to auto mode
["Humidifier.SetHumidifierMode"]

[Command]
When the Humidifier mode changes, do something
["Humidifier.HumidifierMode"]
