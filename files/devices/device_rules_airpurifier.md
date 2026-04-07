[Device Summary]
<Device "AirPurifier">
  <Service "AirPurifierMode" type="value">Current mode</Service>
  <Service "SetAirPurifierMode" type="action">Set air purifier mode (auto, sleep, low, medium, high, quiet, windless, off)</Service>
</Device>

# AirPurifier Examples

[Command]
Set the AirPurifier to auto mode
["AirPurifier.SetAirPurifierMode"]

[Command]
What mode is the AirPurifier in?
["AirPurifier.AirPurifierMode"]
