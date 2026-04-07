[Device Summary]
<Device "Humidifier">
  <Service "HumidifierMode" type="value">Current mode (auto, low, medium, high)</Service>
  <Service "SetHumidifierMode" type="action">Set humidifier mode</Service>
</Device>

# Humidifier Examples

[Command]
Set the Humidifier to high mode
["Humidifier.SetHumidifierMode"]

[Command]
Tell me the current HumidifierMode
["Humidifier.HumidifierMode"]
